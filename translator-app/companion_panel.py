import time
import win32gui
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QApplication, QTextEdit, QSizeGrip,
    QGraphicsOpacityEffect,
)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QPropertyAnimation, QEasingCurve, QTimer
from PyQt5.QtGui import QTextOption

from claude_client import ClaudeWorker, build_system_prompt, load_custom_prompts, get_provider_headers
from clipboard_io import read_input_box, write_input_box, restore_clipboard
from language import detect_mode
from popup import _FONT, _ClickableTextEdit
from version import VERSION

_STYLE = f"""
/* ── Container ────────────────────────────────────────────── */
QWidget#panel_container {{
    background-color: #13171d;
    border: 1px solid #1e2636;
    border-radius: 16px;
}}
QWidget#header_row {{
    background-color: #13171d;
    border-radius: 16px 16px 0 0;
    border-bottom: 1px solid #1a2030;
}}
/* ── Labels ───────────────────────────────────────────────── */
QLabel {{
    color: #dde4ee; font-family: {_FONT}; font-size: 13px;
    background: transparent;
}}
QLabel#brand      {{ color: #4f84c4; font-size: 13px; font-weight: 600; }}
QLabel#tag        {{ color: #2a3348; font-size: 10px; letter-spacing: 0.3px; }}
QLabel#section_lbl {{ color: #49556a; font-size: 11px; letter-spacing: 0.2px; }}
QLabel#result_lbl  {{ color: #4f84c4; font-size: 11px; font-weight: 600; letter-spacing: 0.2px; }}
QLabel#ver2_lbl    {{ color: #49556a; font-size: 11px; }}
QLabel#status_lbl  {{ color: #49556a; font-size: 11px; font-style: italic; }}
QLabel#gen_lbl     {{ color: #4f84c4; font-size: 11px; letter-spacing: 2px; }}
QLabel#hint_lbl    {{ color: #2a3448; font-size: 10px; font-style: italic; }}
/* ── Buttons — default ghost ──────────────────────────────── */
QPushButton {{
    background: transparent; border: none;
    padding: 5px 12px; border-radius: 8px;
    color: #49556a; font-family: {_FONT}; font-size: 12px;
}}
QPushButton:hover {{ background-color: #181e2a; color: #adbac7; }}
QPushButton:disabled {{ color: #1e2636; }}
/* ── Apply (green filled) ─────────────────────────────────── */
QPushButton#apply_btn {{
    background-color: #1a7f37; color: #fff;
    font-size: 13px; font-weight: 600;
    padding: 7px 22px; border-radius: 8px;
}}
QPushButton#apply_btn:hover {{ background-color: #238636; }}
QPushButton#apply_btn:disabled {{
    background-color: #131921; color: #252e3d;
}}
/* ── Close / collapse / icon ghost ───────────────────────── */
QPushButton#close_btn {{
    background: transparent; border: none;
    color: #2e3a4d; font-size: 14px; padding: 2px 8px; border-radius: 6px;
}}
QPushButton#close_btn:hover {{ color: #e05c5c; background-color: #1e1a1a; }}
QPushButton#collapse_btn {{
    background: transparent; border: none;
    color: #2e3a4d; font-size: 14px; padding: 2px 8px; border-radius: 6px;
}}
QPushButton#collapse_btn:hover {{ color: #adbac7; background-color: #181e2a; }}
QPushButton#icon_btn {{
    background: transparent; border: none;
    color: #49556a; font-size: 13px; padding: 3px 8px; border-radius: 6px;
}}
QPushButton#icon_btn:hover {{ color: #adbac7; background-color: #181e2a; }}
QPushButton#refresh_btn {{
    background: transparent; border: none;
    color: #49556a; font-size: 11px; padding: 3px 8px; border-radius: 6px;
}}
QPushButton#refresh_btn:hover {{ color: #adbac7; background-color: #181e2a; }}
QPushButton#refresh_btn:disabled {{ color: #1e2636; }}
/* ── Scene pills ──────────────────────────────────────────── */
QPushButton#scene_active {{
    background-color: #162240;
    color: #79b8ff; font-size: 12px; font-weight: 600;
    padding: 4px 12px; border-radius: 100px;
}}
QPushButton#scene_active:hover {{ background-color: #1c2f52; }}
QPushButton#scene_inactive {{
    background: transparent;
    color: #49556a; font-size: 12px;
    padding: 4px 12px; border-radius: 100px;
}}
QPushButton#scene_inactive:hover {{ background-color: #181e2a; color: #adbac7; }}
/* ── Text areas ───────────────────────────────────────────── */
QTextEdit {{
    background: transparent; border: none; font-family: {_FONT};
}}
QTextEdit#orig_box {{ color: #2d3a4d; font-size: 13px; }}
QTextEdit#result_box {{
    color: #dde4ee; font-size: 15px; font-weight: 600;
}}
QTextEdit#result_box_active {{
    color: #dde4ee; font-size: 15px; font-weight: 600;
    background: #0a1322; border: 1px solid #182845;
    border-radius: 8px; padding: 4px 8px;
}}
QTextEdit#result_box2 {{ color: #49556a; font-size: 13px; }}
QTextEdit#result_box2_active {{
    color: #b0bac9; font-size: 13px;
    background: #0a1322; border: 1px solid #182845;
    border-radius: 8px; padding: 4px 8px;
}}
/* ── Scrollbars ───────────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent; width: 5px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #1e2636; border-radius: 3px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover   {{ background: #4f84c4; }}
QScrollBar::handle:vertical:pressed {{ background: #3a6fa8; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
/* ── Resize grip ──────────────────────────────────────────── */
QSizeGrip {{ background: transparent; width: 12px; height: 12px; }}
"""


class CompanionPanel(QWidget):
    """Persistent fixed panel — same triggers as popup, always-on-top."""

    closed = pyqtSignal()
    usage_recorded = pyqtSignal(str, int, int)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._source_hwnd: int | None = None
        self._saved_clipboard = None
        self._had_selection: bool = False
        self._scene = config.get("default_scene", "spoken")
        self._worker: ClaudeWorker | None = None
        self._worker2: ClaudeWorker | None = None
        self._results = ["", ""]
        self._version_idx = 0
        self._version_ready = [False, False]
        self._clearing_pending = False
        self._drag_pos = None
        self._collapsed = False
        self._fade_anim = None
        self._opacity_effect = None
        self._gen_timer = QTimer(self)
        self._gen_timer.setInterval(450)
        self._gen_timer.timeout.connect(self._tick_gen)
        self._gen_dots = 0
        self._is_generating = False

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setMinimumWidth(400)

        self._container = QWidget(self)
        self._container.setObjectName("panel_container")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._container)

        self.setStyleSheet(_STYLE)
        self._setup_ui()
        self._position_default()

        # Restore collapsed state after positioning (so size calc uses full height)
        if self._config.get("panel_collapsed", False):
            self._collapsed = True
            self._body.setVisible(False)
            self._collapse_btn.setText("+")
            self.adjustSize()

    def _setup_ui(self):
        root = QVBoxLayout(self._container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("header_row")
        h = QHBoxLayout(header)
        h.setContentsMargins(18, 11, 12, 11)
        h.setSpacing(4)

        brand = QLabel("ZEN GENE")
        brand.setObjectName("brand")
        h.addWidget(brand)

        tag = QLabel("固定面板")
        tag.setObjectName("tag")
        h.addWidget(tag)
        h.addStretch()

        self._spoken_btn = QPushButton("日常")
        self._spoken_btn.clicked.connect(lambda: self._select_scene("spoken"))
        self._casual_btn = QPushButton("随意")
        self._casual_btn.clicked.connect(lambda: self._select_scene("casual"))
        self._email_btn  = QPushButton("商务")
        self._email_btn.clicked.connect(lambda: self._select_scene("email"))
        h.addWidget(self._spoken_btn)
        h.addWidget(self._casual_btn)
        h.addWidget(self._email_btn)

        self._collapse_btn = QPushButton("−")
        self._collapse_btn.setObjectName("collapse_btn")
        self._collapse_btn.setFixedSize(28, 28)
        self._collapse_btn.setToolTip("折叠面板")
        self._collapse_btn.clicked.connect(self._toggle_collapse)
        h.addWidget(self._collapse_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self._on_close)
        h.addWidget(close_btn)

        root.addWidget(header)
        self._header = header

        # ── Body ───────────────────────────────────────────────────────────
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(18, 14, 18, 14)
        bl.setSpacing(0)

        orig_header = QHBoxLayout()
        orig_lbl = QLabel("原文")
        orig_lbl.setObjectName("section_lbl")
        orig_header.addWidget(orig_lbl)
        orig_header.addStretch()
        self._refresh_btn = QPushButton("↻ 刷新原文")
        self._refresh_btn.setObjectName("refresh_btn")
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.clicked.connect(self._on_refresh)
        orig_header.addWidget(self._refresh_btn)
        bl.addLayout(orig_header)
        bl.addSpacing(5)

        self._orig_text = QTextEdit()
        self._orig_text.setObjectName("orig_box")
        self._orig_text.setReadOnly(True)
        self._orig_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._orig_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._orig_text.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self._orig_text.setMinimumHeight(36)
        self._orig_text.setMaximumHeight(84)
        self._orig_text.setFocusPolicy(Qt.NoFocus)
        self._orig_text.setPlaceholderText("使用快捷键或 ;; 触发…")
        self._orig_text.setToolTip("提示：选中部分文字后再触发，可只处理所选内容")
        bl.addWidget(self._orig_text)

        hint_lbl = QLabel("选中部分文字后触发，只处理所选内容")
        hint_lbl.setObjectName("hint_lbl")
        bl.addSpacing(3)
        bl.addWidget(hint_lbl)

        bl.addSpacing(14)

        # Result row: label | gen dots | copy
        result_row = QHBoxLayout()
        self._result_lbl = QLabel("建议")
        self._result_lbl.setObjectName("result_lbl")
        result_row.addWidget(self._result_lbl)
        result_row.addSpacing(6)
        self._gen_lbl = QLabel("")
        self._gen_lbl.setObjectName("gen_lbl")
        result_row.addWidget(self._gen_lbl)
        result_row.addStretch()
        self._copy_btn = QPushButton("复制")
        self._copy_btn.setObjectName("icon_btn")
        self._copy_btn.clicked.connect(self._on_copy)
        result_row.addWidget(self._copy_btn)
        bl.addLayout(result_row)
        bl.addSpacing(6)

        # V1 result (clickable — click to select as active version)
        self._result_text = _ClickableTextEdit()
        self._result_text.setObjectName("result_box_active")
        self._result_text.setReadOnly(True)
        self._result_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._result_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._result_text.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self._result_text.setMinimumHeight(80)
        self._result_text.setMaximumHeight(260)
        self._result_text.setFocusPolicy(Qt.NoFocus)
        self._result_text.clicked.connect(lambda: self._switch_version(0))
        self._result_text.double_clicked.connect(lambda: self._on_double_click(0))
        bl.addWidget(self._result_text)

        # V2 section (visible only in multi_version mode)
        self._v2_section = QWidget()
        v2 = QVBoxLayout(self._v2_section)
        v2.setContentsMargins(0, 10, 0, 0)
        v2.setSpacing(5)
        ver2_lbl = QLabel("版 2  — 点击选用")
        ver2_lbl.setObjectName("ver2_lbl")
        v2.addWidget(ver2_lbl)
        self._result2_text = _ClickableTextEdit()
        self._result2_text.setObjectName("result_box2")
        self._result2_text.setReadOnly(True)
        self._result2_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._result2_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._result2_text.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self._result2_text.setMinimumHeight(50)
        self._result2_text.setMaximumHeight(120)
        self._result2_text.setFocusPolicy(Qt.NoFocus)
        self._result2_text.clicked.connect(lambda: self._switch_version(1))
        self._result2_text.double_clicked.connect(lambda: self._on_double_click(1))
        v2.addWidget(self._result2_text)
        self._v2_section.setVisible(False)
        bl.addWidget(self._v2_section)

        bl.addSpacing(14)

        footer = QHBoxLayout()
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("status_lbl")
        footer.addWidget(self._status_lbl)
        footer.addStretch()
        self._apply_btn = QPushButton("✓  应用")
        self._apply_btn.setObjectName("apply_btn")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._on_apply)
        footer.addWidget(self._apply_btn)
        footer.addWidget(QSizeGrip(self._container))
        bl.addLayout(footer)

        root.addWidget(body)
        self._body = body
        self._update_scene_btns()
        self._update_ver_display()

    # ── Collapse ──────────────────────────────────────────────────────────────

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self._body.setVisible(not self._collapsed)
        self._collapse_btn.setText("+" if self._collapsed else "−")
        self._collapse_btn.setToolTip("展开面板" if self._collapsed else "折叠面板")
        self.adjustSize()
        self._config.set("panel_collapsed", self._collapsed)
        self._config.save()

    # ── Fade animation ────────────────────────────────────────────────────────

    def _fade_in(self):
        if self._opacity_effect is None:
            self._opacity_effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(200)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_anim.start()

    # ── Streaming indicator ───────────────────────────────────────────────────

    def _start_gen(self):
        if not self._is_generating:
            self._is_generating = True
            self._gen_dots = 0
            self._gen_lbl.setText("·")
            self._gen_timer.start()

    def _stop_gen(self):
        self._is_generating = False
        self._gen_timer.stop()
        self._gen_lbl.setText("")

    def _tick_gen(self):
        self._gen_dots = (self._gen_dots % 3) + 1
        self._gen_lbl.setText("·" * self._gen_dots)

    # ── Public API ────────────────────────────────────────────────────────────

    def process_text(self, text, scene, source_hwnd, saved_clipboard, had_selection):
        self._source_hwnd = source_hwnd
        self._saved_clipboard = saved_clipboard
        self._had_selection = had_selection
        self._scene = scene
        self._update_scene_btns()
        self._orig_text.setPlainText(text)
        self._clearing_pending = True
        self._version_idx = 0
        self._version_ready = [False, False]
        self._apply_btn.setEnabled(False)
        self._refresh_btn.setEnabled(False)
        self._set_status("处理中…")
        self._update_ver_display()
        self._start_gen()
        self._run_claude(text)
        # Auto-expand if collapsed when new content arrives
        if self._collapsed:
            self._toggle_collapse()
        was_hidden = not self.isVisible()
        if was_hidden:
            self.show()
        self.raise_()
        if was_hidden:
            self._fade_in()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _make_worker(self, text: str) -> ClaudeWorker:
        custom_sys, user_prompts = load_custom_prompts(self._config)
        system_prompt = build_system_prompt(
            custom_sys,
            region=self._config.get("region", "sg"),
            style_guide=self._config.get("style_guide", ""),
            vocab_prefs=self._config.get("vocab_prefs", ""),
        )
        mode = detect_mode(text)
        provider = self._config.get("provider", "anthropic")
        return ClaudeWorker(
            self._config.get("api_key", ""),
            text, mode, self._scene,
            system_prompt=system_prompt,
            user_prompts=user_prompts,
            model=self._config.get("model", "claude-haiku-4-5-20251001"),
            base_url=self._config.get("base_url", "https://api.anthropic.com/v1/"),
            extra_headers=get_provider_headers(provider),
        )

    def _stop_worker(self, w):
        if w and w.isRunning():
            w.cancel(); w.wait()
        if w:
            try:
                w.token_received.disconnect()
                w.finished.disconnect()
                w.error.disconnect()
                w.usage.disconnect()
            except Exception:
                pass

    def _run_claude(self, text: str):
        self._stop_worker(self._worker)
        self._stop_worker(self._worker2)
        self._worker2 = None
        self._results = ["", ""]

        self._worker = self._make_worker(text)
        self._worker.token_received.connect(lambda t: self._on_token(t, 0))
        self._worker.finished.connect(lambda r: self._on_finished(r, 0))
        self._worker.error.connect(self._on_error)
        self._worker.usage.connect(self.usage_recorded)
        self._worker.start()

        multi = self._config.get("multi_version", False)
        self._v2_section.setVisible(multi)
        if multi:
            # Update V1 label to match popup symmetry
            self._result_lbl.setText("版 1  — 点击选用")
            self._worker2 = self._make_worker(text)
            self._worker2.token_received.connect(lambda t: self._on_token(t, 1))
            self._worker2.finished.connect(lambda r: self._on_finished(r, 1))
            self._worker2.error.connect(lambda _: None)
            self._worker2.usage.connect(self.usage_recorded)
            self._worker2.start()
        else:
            self._result_lbl.setText("建议")

    @pyqtSlot(str)
    def _on_token(self, token: str, version: int = 0):
        if self._clearing_pending and version == 0:
            self._results = ["", ""]
            self._clearing_pending = False
        self._results[version] += token
        if version == 0:
            self._result_text.setPlainText(self._results[version])
        elif version == 1:
            self._result2_text.setPlainText(self._results[version])

    @pyqtSlot(str)
    def _on_finished(self, full: str, version: int = 0):
        self._results[version] = full
        self._version_ready[version] = True
        if version == 0:
            self._result_text.setPlainText(full)
            self._apply_btn.setEnabled(bool(full))
        elif version == 1:
            self._result2_text.setPlainText(full)
        if self._version_ready[0]:
            self._refresh_btn.setEnabled(bool(self._source_hwnd))
            self._stop_gen()
            self._set_status("")
            multi = self._config.get("multi_version", False)
            if not multi and self._config.get("auto_confirm", False) and full:
                self._on_apply()
                return
        self._update_ver_display()

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self._result_text.setPlainText(f"⚠  {msg}")
        self._refresh_btn.setEnabled(bool(self._source_hwnd))
        self._stop_gen()
        self._set_status("")

    def _on_refresh(self):
        if not self._source_hwnd:
            return
        try:
            win32gui.SetForegroundWindow(self._source_hwnd)
            time.sleep(0.05)
        except Exception:
            return
        try:
            text, saved, had_selection = read_input_box()
        except Exception:
            return
        if not text.strip():
            return
        self._saved_clipboard = saved
        self._had_selection = had_selection
        self._orig_text.setPlainText(text)
        self._rerun_claude(text)

    def _rerun_claude(self, text: str):
        self._clearing_pending = True
        self._version_idx = 0
        self._version_ready = [False, False]
        self._apply_btn.setEnabled(False)
        self._refresh_btn.setEnabled(False)
        self._set_status("处理中…")
        self._update_ver_display()
        self._start_gen()
        self._run_claude(text)

    def _on_apply(self):
        result = self._results[self._version_idx]
        if not result:
            return
        if self._source_hwnd:
            try:
                win32gui.SetForegroundWindow(self._source_hwnd)
                time.sleep(0.12)
            except Exception:
                restore_clipboard(self._saved_clipboard)
                return
        write_input_box(result, self._saved_clipboard, self._had_selection)
        self._set_status("已应用 ✓")
        QTimer.singleShot(2000, lambda: self._set_status(""))

    def _on_copy(self):
        text = self._results[self._version_idx]
        if text:
            QApplication.clipboard().setText(text)

    def _on_close(self):
        self._stop_gen()
        self.hide()
        self.closed.emit()

    def _on_double_click(self, idx: int):
        self._switch_version(idx)
        if self._apply_btn.isEnabled():
            self._on_apply()

    def _switch_version(self, idx: int):
        self._version_idx = idx
        self._apply_btn.setEnabled(self._version_ready[idx] and bool(self._results[idx]))
        self._update_ver_display()

    def _select_scene(self, scene: str):
        if scene == self._scene:
            return
        self._scene = scene
        self._config.set("default_scene", scene)
        self._config.save()
        self._update_scene_btns()
        text = self._orig_text.toPlainText()
        if text.strip():
            self._rerun_claude(text)

    def _update_scene_btns(self):
        for scene, btn in (
            ("spoken", self._spoken_btn),
            ("casual", self._casual_btn),
            ("email",  self._email_btn),
        ):
            btn.setObjectName("scene_active" if scene == self._scene else "scene_inactive")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _update_ver_display(self):
        v1_active = (self._version_idx == 0)
        self._result_text.setObjectName("result_box_active" if v1_active else "result_box")
        self._result_text.style().unpolish(self._result_text)
        self._result_text.style().polish(self._result_text)
        if self._config.get("multi_version", False):
            v2_active = (self._version_idx == 1)
            self._result2_text.setObjectName(
                "result_box2_active" if v2_active else "result_box2"
            )
            self._result2_text.style().unpolish(self._result2_text)
            self._result2_text.style().polish(self._result2_text)

    def _set_status(self, text: str):
        self._status_lbl.setText(text)

    def _position_default(self):
        self.adjustSize()
        screen = QApplication.primaryScreen().availableGeometry()
        saved = self._config.get("panel_position")
        if saved and isinstance(saved, list) and len(saved) == 2:
            x = max(screen.left(), min(int(saved[0]), screen.right() - self.width()))
            y = max(screen.top(), min(int(saved[1]), screen.bottom() - self.height()))
        else:
            x = screen.right() - self.width() - 24
            y = screen.center().y() - self.height() // 2
        self.move(x, y)

    # ── Drag (header zone) + position persistence ─────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.y() < self._header.height():
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
        else:
            self._drag_pos = None

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        if self._drag_pos is not None:
            # Persist position after dragging
            self._config.set("panel_position", [self.x(), self.y()])
            self._config.save()
        self._drag_pos = None
