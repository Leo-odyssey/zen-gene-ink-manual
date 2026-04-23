import sys
import threading
import time
import win32gui
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot, Qt

from version import APP_FULL  # noqa: F401 — ensures PyInstaller bundles version.py
from config import Config
from language import detect_mode
from window_detector import infer_scene
from clipboard_io import read_input_box, write_input_box, restore_clipboard
from claude_client import ClaudeWorker, DEFAULT_USER_PROMPTS, load_custom_prompts, build_system_prompt, get_provider_headers
from usage_tracker import UsageTracker
from popup import TranslatorPopup
from tray import TrayApp
from hotkey import HotkeyListener
from suffix_listener import SuffixListener
from settings import SettingsDialog
from companion_panel import CompanionPanel


class ClipboardReader(QThread):
    """Background thread: waits, reads the source input box, signals back."""

    ready = pyqtSignal(object)
    empty = pyqtSignal()

    def __init__(
        self,
        hwnd: int,
        window_title: str,
        window_scene_map: dict,
        default_scene: str = "spoken",
        wait_ms: int = 400,
        strip_suffix: bool = False,
    ):
        super().__init__()
        self._hwnd = hwnd
        self._window_title = window_title
        self._window_scene_map = window_scene_map
        self._default_scene = default_scene
        self._wait_ms = wait_ms
        self._strip_suffix = strip_suffix
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def run(self):
        try:
            # Interruptible wait: sleep in 20ms increments so cancel() works promptly
            elapsed = 0
            step = 20
            while elapsed < self._wait_ms:
                if self._cancel.is_set():
                    return
                time.sleep(min(step, self._wait_ms - elapsed) / 1000)
                elapsed += step

            if self._cancel.is_set():
                return

            try:
                win32gui.SetForegroundWindow(self._hwnd)
                time.sleep(0.05)
            except Exception:
                pass

            text, saved, had_selection = read_input_box()

            if not text.strip():
                self.empty.emit()
                return

            scene = infer_scene(
                self._window_title, self._window_scene_map, default=self._default_scene
            )
            self.ready.emit({
                "text": text,
                "scene": scene,
                "saved": saved,
                "had_selection": had_selection,
                "strip_suffix": self._strip_suffix,
            })
        except Exception:
            self.empty.emit()


def _load_custom_prompts(config: Config):
    return load_custom_prompts(config)


class App(QObject):
    def __init__(self):
        super().__init__()
        self._config = Config()
        self._original_hwnd: int | None = None
        self._saved_clipboard: str | None = None
        self._had_selection: bool = False
        self._worker: ClaudeWorker | None = None
        self._worker2: ClaudeWorker | None = None
        self._reader: ClipboardReader | None = None
        self._tracker = UsageTracker()

        self._popup = TranslatorPopup()
        self._popup.confirmed.connect(self._on_confirmed)
        self._popup.cancelled.connect(self._on_cancelled)
        self._popup.scene_changed.connect(self._on_scene_changed)
        self._popup.suffix_toggled.connect(self._on_suffix_toggled)
        self._popup.retried.connect(self._on_popup_retry, Qt.QueuedConnection)
        self._popup.set_multi_version(self._config.get("multi_version", False))
        self._popup.set_auto_confirm(self._config.get("auto_confirm", False))

        # Hotkey trigger (always active)
        hotkey = self._config.get("hotkey", "ctrl+shift+space")
        self._hotkey = HotkeyListener(hotkey)
        self._hotkey.triggered.connect(
            lambda: self._trigger(strip_suffix=False, wait_ms=400),
            Qt.QueuedConnection,
        )
        self._hotkey.start()

        # Suffix trigger (toggleable, configurable chars)
        self._suffix = SuffixListener(self._config.get("suffix_chars", "··"))
        self._suffix.triggered.connect(
            lambda: self._trigger(strip_suffix=True, wait_ms=80),
            Qt.QueuedConnection,
        )
        self._suffix.start()
        suffix_on = self._config.get("suffix_enabled", True)
        self._suffix.set_enabled(suffix_on)
        self._popup.set_suffix_enabled(suffix_on)

        self._tray = TrayApp(self, self._config)

        # Companion panel — shown instead of popup when companion_enabled
        self._panel = CompanionPanel(self._config)
        self._panel.usage_recorded.connect(self._on_usage)

        if not self._config.get("api_key"):
            self.open_settings()

    # ── Public API for tray ──────────────────────────────────────────────────

    def set_default_scene(self, scene: str):
        self._config.set("default_scene", scene)
        self._config.save()

    def set_suffix_enabled(self, enabled: bool):
        self._suffix.set_enabled(enabled)
        self._config.set("suffix_enabled", enabled)
        self._config.save()
        self._popup.set_suffix_enabled(enabled)

    def set_region(self, region: str):
        self._config.set("region", region)
        self._config.save()
        self._tray.update_region_check(region)

    def set_companion_enabled(self, enabled: bool):
        self._config.set("companion_enabled", enabled)
        self._config.save()
        if not enabled and self._panel.isVisible():
            self._panel.hide()
        self._tray.update_companion_check(enabled)

    # ── Trigger ──────────────────────────────────────────────────────────────

    def _trigger(self, strip_suffix: bool = False, wait_ms: int = 400):
        if not self._config.get("api_key"):
            self._tray.flash_message("ZEN GENE", "请先在设置中填写 API Key")
            self.open_settings()
            return

        self._original_hwnd = win32gui.GetForegroundWindow()
        window_title = win32gui.GetWindowText(self._original_hwnd).lower()

        # Cancel any previous reader still in flight (safe cancel, no terminate())
        if self._reader and self._reader.isRunning():
            self._reader.cancel()
            self._reader.wait()

        self._reader = ClipboardReader(
            self._original_hwnd,
            window_title,
            self._config.get("window_scene_map", {}),
            default_scene=self._config.get("default_scene", "spoken"),
            wait_ms=wait_ms,
            strip_suffix=strip_suffix,
        )
        self._reader.ready.connect(self._on_text_ready, Qt.QueuedConnection)
        self._reader.empty.connect(self._on_text_empty, Qt.QueuedConnection)
        self._reader.start()

    @pyqtSlot(object)
    def _on_text_ready(self, data: dict):
        self._saved_clipboard = data["saved"]
        self._had_selection = data["had_selection"]
        text = data["text"]

        # Strip ;; suffix before displaying or sending to Claude
        if data.get("strip_suffix"):
            for suffix in (";;", "；；"):
                if text.endswith(suffix):
                    text = text[:-len(suffix)].rstrip()
                    break

        scene = data["scene"]

        if self._config.get("companion_enabled", False):
            self._panel.process_text(
                text, scene,
                self._original_hwnd,
                self._saved_clipboard,
                self._had_selection,
            )
        else:
            mode = detect_mode(text)
            self._popup.show_for(text, scene)
            self._start_worker(text, mode, scene)

    @pyqtSlot()
    def _on_text_empty(self):
        if not self._config.get("companion_enabled", False):
            self._popup.hide()
        self._tray.flash_message("ZEN GENE", "输入框内容为空")

    def _make_worker(self, text: str, mode: str, scene: str) -> ClaudeWorker:
        custom_sys, user_prompts = _load_custom_prompts(self._config)
        system_prompt = build_system_prompt(
            custom_sys,
            region=self._config.get("region", "sg"),
            style_guide=self._config.get("style_guide", ""),
            vocab_prefs=self._config.get("vocab_prefs", ""),
        )
        provider = self._config.get("provider", "anthropic")
        return ClaudeWorker(
            self._config.get("api_key", ""),
            text, mode, scene,
            system_prompt=system_prompt,
            user_prompts=user_prompts,
            model=self._config.get("model", "claude-haiku-4-5-20251001"),
            base_url=self._config.get("base_url", "https://api.anthropic.com/v1/"),
            extra_headers=get_provider_headers(provider),
        )

    def _stop_worker(self, w):
        if w and w.isRunning():
            w.cancel()
            w.wait()
        if w:
            try:
                w.token_received.disconnect()
                w.finished.disconnect()
                w.error.disconnect()
                w.usage.disconnect()
            except Exception:
                pass

    def _start_worker(self, text: str, mode: str, scene: str):
        self._stop_worker(self._worker)
        self._stop_worker(self._worker2)
        self._worker2 = None

        self._worker = self._make_worker(text, mode, scene)
        self._worker.token_received.connect(lambda t: self._popup.append_token(t, 0))
        self._worker.finished.connect(lambda r: self._popup.show_complete(r, 0))
        self._worker.error.connect(self._popup.show_error)
        self._worker.usage.connect(self._on_usage)
        self._worker.start()

        if self._config.get("multi_version", False):
            self._worker2 = self._make_worker(text, mode, scene)
            self._worker2.token_received.connect(lambda t: self._popup.append_token(t, 1))
            self._worker2.finished.connect(lambda r: self._popup.show_complete(r, 1))
            self._worker2.error.connect(lambda _: None)
            self._worker2.usage.connect(self._on_usage)
            self._worker2.start()

    def _fire_explain(self, original: str, result: str):
        provider = self._config.get("provider", "anthropic")
        self._explain_worker = ExplainWorker(
            self._config.get("api_key", ""),
            self._config.get("base_url", "https://api.anthropic.com/v1/"),
            get_provider_headers(provider),
            original, result,
            self._config.get("model", "claude-haiku-4-5-20251001"),
        )
        self._explain_worker.result.connect(self._popup.show_explain)
        self._explain_worker.start()

    def _on_usage(self, model: str, inp: int, out: int):
        self._tracker.record(model, inp, out)

    @pyqtSlot(str)
    def _on_scene_changed(self, scene: str):
        self._config.set("default_scene", scene)
        self._config.save()
        self._tray.update_scene_check(scene)
        self._popup.reset()
        text = self._popup.original_text
        mode = detect_mode(text)
        self._start_worker(text, mode, scene)

    @pyqtSlot()
    def _on_popup_retry(self):
        text = self._popup.original_text
        scene = self._popup.current_scene
        if text:
            mode = detect_mode(text)
            self._popup.reset()
            self._start_worker(text, mode, scene)

    @pyqtSlot(bool)
    def _on_suffix_toggled(self, enabled: bool):
        self._suffix.set_enabled(enabled)
        self._config.set("suffix_enabled", enabled)
        self._config.save()
        self._tray.update_suffix_check(enabled)

    @pyqtSlot(str)
    def _on_confirmed(self, result_text: str):
        if self._original_hwnd:
            try:
                win32gui.SetForegroundWindow(self._original_hwnd)
                time.sleep(0.12)
            except Exception:
                restore_clipboard(self._saved_clipboard)
                return
        write_input_box(result_text, self._saved_clipboard, self._had_selection)

    @pyqtSlot()
    def _on_cancelled(self):
        if self._reader and self._reader.isRunning():
            self._reader.cancel()
            self._reader.wait()
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        restore_clipboard(self._saved_clipboard)

    def pause_hotkey(self):
        self._hotkey.pause()

    def resume_hotkey(self):
        self._hotkey.resume()

    def open_settings(self):
        old_hotkey = self._config.get("hotkey")
        old_companion = self._config.get("companion_enabled", False)
        old_region = self._config.get("region", "sg")
        dlg = SettingsDialog(self._config)
        if dlg.exec_():
            new_hotkey = self._config.get("hotkey")
            if new_hotkey != old_hotkey:
                try:
                    self._hotkey.set_hotkey(new_hotkey)
                except RuntimeError as e:
                    QMessageBox.warning(None, "快捷键错误", str(e))
                    self._config.set("hotkey", old_hotkey)
                    self._config.save()
            new_companion = self._config.get("companion_enabled", False)
            if new_companion != old_companion:
                self.set_companion_enabled(new_companion)
            new_region = self._config.get("region", "sg")
            if new_region != old_region:
                self._tray.update_region_check(new_region)
            self._popup.set_multi_version(self._config.get("multi_version", False))
            self._popup.set_auto_confirm(self._config.get("auto_confirm", False))
            new_suffix = self._config.get("suffix_enabled", True)
            self._suffix.set_enabled(new_suffix)
            self._tray.update_suffix_check(new_suffix)
            self._suffix.set_suffix(self._config.get("suffix_chars", "··"))


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    controller = App()  # noqa: F841
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
