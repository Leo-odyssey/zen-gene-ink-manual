# Windows 智能翻译与优化工具 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows system-tray app that intercepts a global hotkey, reads the active input box, sends text to Claude API for English optimization or Chinese-to-English translation, shows results in a floating PyQt5 popup, and pastes the confirmed result back.

**Architecture:** A persistent Python/PyQt5 process lives in the system tray. A background `keyboard` hook fires a Qt signal on hotkey press; a `QThread` worker streams tokens from the Claude API to the popup in real-time. All window focus and clipboard operations are handled via `pywin32` before and after the popup is shown, so keystrokes always target the correct application.

**Tech Stack:** Python 3.11, PyQt5, `anthropic` SDK, `keyboard`, `pywin32`, PyInstaller

---

## File Map

| File | Responsibility |
|---|---|
| `translator-app/config.py` | Read/write `%APPDATA%/TranslatorApp/config.json`; provide typed getters |
| `translator-app/language.py` | Detect translate vs optimize mode from text |
| `translator-app/window_detector.py` | Get active window title; infer scene from config map |
| `translator-app/clipboard_io.py` | Save/restore clipboard; read input box via Ctrl+A+C; write back via Ctrl+V |
| `translator-app/claude_client.py` | `ClaudeWorker(QThread)` — streams tokens from Claude API |
| `translator-app/popup.py` | `TranslatorPopup(QWidget)` — frameless always-on-top result window |
| `translator-app/settings.py` | `SettingsDialog(QDialog)` — API key, hotkey, startup config |
| `translator-app/tray.py` | `TrayApp(QSystemTrayIcon)` — tray icon, menu, wires tray↔App |
| `translator-app/hotkey.py` | `HotkeyListener(QObject)` — registers global hotkey, emits Qt signal |
| `translator-app/main.py` | `App(QObject)` — orchestrates all modules; entry point |
| `tests/test_config.py` | Unit tests for config read/write/defaults |
| `tests/test_language.py` | Unit tests for language detection |
| `tests/test_claude_client.py` | Unit tests for prompt building (mocked API) |
| `tests/test_window_detector.py` | Unit tests for scene inference (mocked win32) |
| `requirements.txt` | Pinned dependencies |
| `translator-app.spec` | PyInstaller spec for single-exe build |

---

## Task 1: Project Setup

**Files:**
- Create: `translator-app/` (directory)
- Create: `tests/` (directory)
- Create: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `.gitignore`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p translator-app tests
touch tests/__init__.py
```

- [ ] **Step 2: Write `requirements.txt`**

```
anthropic>=0.40.0
PyQt5>=5.15.11
keyboard>=0.13.5
pywin32>=306
pyinstaller>=6.3.0
pytest>=8.0.0
pytest-mock>=3.12.0
```

- [ ] **Step 3: Write `.gitignore`**

```
__pycache__/
*.pyc
dist/
build/
*.spec.bak
.pytest_cache/
```

- [ ] **Step 4: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: All packages install without errors. Confirm with `pip show anthropic PyQt5 keyboard pywin32`.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt tests/__init__.py .gitignore
git commit -m "chore: project setup and dependencies"
```

---

## Task 2: Config Module

**Files:**
- Create: `translator-app/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def make_config(tmp_path):
    with patch("config.CONFIG_DIR", tmp_path), \
         patch("config.CONFIG_FILE", tmp_path / "config.json"):
        from importlib import import_module, reload
        import config as cfg_module
        reload(cfg_module)
        return cfg_module.Config()


def test_defaults_when_no_file(tmp_path):
    with patch("config.CONFIG_DIR", tmp_path), \
         patch("config.CONFIG_FILE", tmp_path / "config.json"):
        import config as cfg_module
        from importlib import reload
        reload(cfg_module)
        c = cfg_module.Config()
    assert c.get("hotkey") == "ctrl+shift+space"
    assert c.get("api_key") == ""
    assert c.get("startup_with_windows") is False
    assert c.get("window_scene_map") == {"outlook": "email", "mail": "email", "whatsapp": "casual"}


def test_save_and_reload(tmp_path):
    config_file = tmp_path / "config.json"
    with patch("config.CONFIG_DIR", tmp_path), \
         patch("config.CONFIG_FILE", config_file):
        import config as cfg_module
        from importlib import reload
        reload(cfg_module)
        c = cfg_module.Config()
        c.set("api_key", "sk-ant-test")
        c.save()
        c2 = cfg_module.Config()
    assert c2.get("api_key") == "sk-ant-test"


def test_get_missing_key_returns_none(tmp_path):
    with patch("config.CONFIG_DIR", tmp_path), \
         patch("config.CONFIG_FILE", tmp_path / "config.json"):
        import config as cfg_module
        from importlib import reload
        reload(cfg_module)
        c = cfg_module.Config()
    assert c.get("nonexistent") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd translator-app && pytest ../tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: Write `translator-app/config.py`**

```python
import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("APPDATA", "~")) / "TranslatorApp"
CONFIG_FILE = CONFIG_DIR / "config.json"

_DEFAULTS = {
    "api_key": "",
    "hotkey": "ctrl+shift+space",
    "window_scene_map": {
        "outlook": "email",
        "mail": "email",
        "whatsapp": "casual",
    },
    "startup_with_windows": False,
}


class Config:
    def __init__(self):
        self._data = dict(_DEFAULTS)
        if CONFIG_FILE.exists():
            try:
                self._data.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd translator-app && pytest ../tests/test_config.py -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add translator-app/config.py tests/test_config.py
git commit -m "feat: config module with JSON persistence"
```

---

## Task 3: Language Detection

**Files:**
- Create: `translator-app/language.py`
- Create: `tests/test_language.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_language.py
import sys
sys.path.insert(0, "translator-app")
from language import detect_mode


def test_pure_english_returns_optimize():
    assert detect_mode("hello how are you") == "optimize"


def test_pure_chinese_returns_translate():
    assert detect_mode("你好，最近怎么样？") == "translate"


def test_mixed_returns_translate():
    assert detect_mode("我 want to meet at 3pm lol") == "translate"


def test_empty_string_returns_optimize():
    assert detect_mode("") == "optimize"


def test_numbers_and_punctuation_returns_optimize():
    assert detect_mode("Meeting at 3:00pm! Budget: $500.") == "optimize"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd translator-app && pytest ../tests/test_language.py -v
```

Expected: `ModuleNotFoundError: No module named 'language'`

- [ ] **Step 3: Write `translator-app/language.py`**

```python
import re

_CJK = re.compile(r"[一-鿿]")


def detect_mode(text: str) -> str:
    """Return 'translate' if text contains any CJK character, else 'optimize'."""
    return "translate" if _CJK.search(text) else "optimize"
```

- [ ] **Step 4: Run tests**

```bash
cd translator-app && pytest ../tests/test_language.py -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add translator-app/language.py tests/test_language.py
git commit -m "feat: language detection for translate vs optimize mode"
```

---

## Task 4: Window Detector

**Files:**
- Create: `translator-app/window_detector.py`
- Create: `tests/test_window_detector.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_window_detector.py
import sys
sys.path.insert(0, "translator-app")
import pytest
from unittest.mock import patch
from window_detector import infer_scene, get_active_window_title

SCENE_MAP = {"outlook": "email", "mail": "email", "whatsapp": "casual"}


def test_outlook_maps_to_email():
    assert infer_scene("Inbox - Outlook", SCENE_MAP) == "email"


def test_whatsapp_maps_to_casual():
    assert infer_scene("WhatsApp", SCENE_MAP) == "casual"


def test_unknown_window_defaults_to_casual():
    assert infer_scene("Notepad", SCENE_MAP) == "casual"


def test_case_insensitive_match():
    assert infer_scene("OUTLOOK - john@example.com", SCENE_MAP) == "email"


def test_empty_map_returns_casual():
    assert infer_scene("Anything", {}) == "casual"


def test_get_active_window_title_returns_string():
    with patch("window_detector.win32gui.GetForegroundWindow", return_value=12345), \
         patch("window_detector.win32gui.GetWindowText", return_value="Test Window"):
        title = get_active_window_title()
    assert title == "test window"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd translator-app && pytest ../tests/test_window_detector.py -v
```

Expected: `ModuleNotFoundError: No module named 'window_detector'`

- [ ] **Step 3: Write `translator-app/window_detector.py`**

```python
import win32gui


def get_active_window_title() -> str:
    hwnd = win32gui.GetForegroundWindow()
    return win32gui.GetWindowText(hwnd).lower()


def infer_scene(window_title: str, window_scene_map: dict) -> str:
    title = window_title.lower()
    for keyword, scene in window_scene_map.items():
        if keyword.lower() in title:
            return scene
    return "casual"
```

- [ ] **Step 4: Run tests**

```bash
cd translator-app && pytest ../tests/test_window_detector.py -v
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add translator-app/window_detector.py tests/test_window_detector.py
git commit -m "feat: window detector and scene inference"
```

---

## Task 5: Claude API Client

**Files:**
- Create: `translator-app/claude_client.py`
- Create: `tests/test_claude_client.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_claude_client.py
import sys
sys.path.insert(0, "translator-app")
import pytest
from unittest.mock import MagicMock, patch
from claude_client import build_prompt, SYSTEM_PROMPT


def test_optimize_email_prompt_contains_professional():
    prompt = build_prompt("hello", "optimize", "email")
    assert "Professional mode" in prompt
    assert "business email" in prompt
    assert "hello" in prompt


def test_optimize_casual_prompt_contains_casual():
    prompt = build_prompt("hey wats up", "optimize", "casual")
    assert "Casual mode" in prompt
    assert "chat message" in prompt
    assert "hey wats up" in prompt


def test_translate_email_prompt():
    prompt = build_prompt("你好", "translate", "email")
    assert "Professional mode" in prompt
    assert "Translate" in prompt
    assert "你好" in prompt


def test_translate_casual_prompt():
    prompt = build_prompt("明天见", "translate", "casual")
    assert "Casual mode" in prompt
    assert "Translate" in prompt
    assert "明天见" in prompt


def test_system_prompt_mentions_native_speaker():
    assert "native English speaker" in SYSTEM_PROMPT


def test_system_prompt_mentions_no_explanations():
    assert "no explanations" in SYSTEM_PROMPT
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd translator-app && pytest ../tests/test_claude_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'claude_client'`

- [ ] **Step 3: Write `translator-app/claude_client.py`**

```python
import anthropic
from PyQt5.QtCore import QThread, pyqtSignal

SYSTEM_PROMPT = (
    "You are a native English speaker who writes naturally in both "
    "casual and professional contexts.\n\n"
    "In casual mode: write like a real person texting a friend — "
    "use everyday contractions, informal expressions, and common "
    "internet shorthand where it fits naturally (e.g. lol, lmk, "
    "omw, ngl, tbh, imo). Never sound stiff or robotic.\n\n"
    "In professional mode: write clear, polished business English "
    "— friendly but formal, using common everyday words. Avoid "
    "jargon, overly complex vocabulary, or stiff phrases like "
    '"please do not hesitate to contact me."\n\n'
    "Rules for all responses:\n"
    "- Return only the final text, no explanations, no quotes\n"
    "- Preserve the original meaning\n"
    "- Fix all spelling and grammar errors"
)

_USER_PROMPTS = {
    ("optimize", "email"): "Professional mode. Improve this English for a business email:\n{text}",
    ("optimize", "casual"): "Casual mode. Improve this English for a chat message:\n{text}",
    ("translate", "email"): "Professional mode. Translate to English for a business email:\n{text}",
    ("translate", "casual"): "Casual mode. Translate to English for a chat message:\n{text}",
}


def build_prompt(text: str, mode: str, scene: str) -> str:
    return _USER_PROMPTS[(mode, scene)].format(text=text)


class ClaudeWorker(QThread):
    token_received = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, api_key: str, text: str, mode: str, scene: str, parent=None):
        super().__init__(parent)
        self._api_key = api_key
        self._text = text
        self._mode = mode
        self._scene = scene
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            client = anthropic.Anthropic(api_key=self._api_key)
            prompt = build_prompt(self._text, self._mode, self._scene)
            result = ""
            with client.messages.stream(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for token in stream.text_stream:
                    if self._cancelled:
                        return
                    result += token
                    self.token_received.emit(token)
            self.finished.emit(result)
        except anthropic.AuthenticationError:
            self.error.emit("API Key 无效，请在设置中更新")
        except anthropic.RateLimitError:
            self.error.emit("请求过于频繁，请稍后重试")
        except Exception as e:
            self.error.emit(f"请求失败：{e}")
```

- [ ] **Step 4: Run tests**

```bash
cd translator-app && pytest ../tests/test_claude_client.py -v
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add translator-app/claude_client.py tests/test_claude_client.py
git commit -m "feat: Claude API client with streaming QThread worker"
```

---

## Task 6: Clipboard I/O

**Files:**
- Create: `translator-app/clipboard_io.py`

No automated unit tests — this module drives real Windows UI automation. Manual test instructions are in Step 4.

- [ ] **Step 1: Write `translator-app/clipboard_io.py`**

```python
import time
import win32clipboard
import win32con
import keyboard


def _get_clipboard_text() -> str:
    try:
        win32clipboard.OpenClipboard()
        try:
            return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        except TypeError:
            return ""
    except Exception:
        return ""
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass


def _set_clipboard_text(text: str) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def save_clipboard() -> str | None:
    try:
        return _get_clipboard_text()
    except Exception:
        return None


def restore_clipboard(saved: str | None) -> None:
    if saved is not None:
        try:
            _set_clipboard_text(saved)
        except Exception:
            pass


def read_input_box() -> tuple[str, str | None, bool]:
    """
    Returns (text, saved_clipboard, had_selection).
    Tries to read selected text first; falls back to Ctrl+A select-all.
    """
    saved = save_clipboard()

    # Try reading existing selection first
    _set_clipboard_text("")
    time.sleep(0.05)
    keyboard.send("ctrl+c")
    time.sleep(0.15)
    selected = _get_clipboard_text()

    if selected.strip():
        return selected, saved, True

    # No selection — select all and copy
    keyboard.send("ctrl+a")
    time.sleep(0.05)
    keyboard.send("ctrl+c")
    time.sleep(0.15)
    text = _get_clipboard_text()

    return text, saved, False


def write_input_box(text: str, saved_clipboard: str | None, had_selection: bool) -> None:
    """
    Replace input box content with text, then restore the original clipboard.
    If had_selection is True, only the selected region is replaced (Ctrl+V).
    If had_selection is False, Ctrl+A is sent first to select all before pasting.
    """
    _set_clipboard_text(text)
    if not had_selection:
        keyboard.send("ctrl+a")
        time.sleep(0.05)
    keyboard.send("ctrl+v")
    time.sleep(0.15)
    restore_clipboard(saved_clipboard)
```

- [ ] **Step 2: Manual smoke test**

Open Notepad, type `hello world`. Run this in a Python shell from the `translator-app/` directory:

```python
import sys, time
sys.path.insert(0, ".")
from clipboard_io import read_input_box, write_input_box

# Click into Notepad first, then switch to this shell within 3 seconds
time.sleep(3)
text, saved, had_selection = read_input_box()
print(repr(text))          # Expected: 'hello world'
print(repr(saved))         # Expected: whatever was in clipboard before
print(had_selection)       # Expected: False

# Now test write-back
time.sleep(2)
write_input_box("REPLACED", saved, had_selection)
# Expected: Notepad now shows "REPLACED"
```

- [ ] **Step 3: Commit**

```bash
git add translator-app/clipboard_io.py
git commit -m "feat: clipboard I/O module for input box read/write"
```

---

## Task 7: Floating Popup Window

**Files:**
- Create: `translator-app/popup.py`

- [ ] **Step 1: Write `translator-app/popup.py`**

```python
import sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QApplication,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QCursor

_STYLE = """
QWidget#popup {
    background-color: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 8px;
}
QLabel { color: #cdd6f4; font-family: "Segoe UI"; }
QPushButton {
    background-color: #313244; border: none; padding: 6px 18px;
    border-radius: 4px; color: #cdd6f4; font-family: "Segoe UI"; font-size: 13px;
}
QPushButton:hover { background-color: #45475a; }
QPushButton#confirm {
    background-color: #a6e3a1; color: #1e1e2e; font-weight: bold;
}
QPushButton#confirm:hover { background-color: #94d9a0; }
QPushButton#confirm:disabled { background-color: #313244; color: #6c7086; }
QPushButton#scene {
    background-color: #313244; font-size: 11px; padding: 2px 8px;
}
QFrame#sep { color: #313244; }
"""


class TranslatorPopup(QWidget):
    confirmed = pyqtSignal(str)
    cancelled = pyqtSignal()
    scene_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._result = ""
        self._scene = "casual"
        self._original = ""
        self._setup_ui()
        self.setObjectName("popup")
        self.setStyleSheet(_STYLE)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setFixedWidth(440)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        # Scene row
        scene_row = QHBoxLayout()
        scene_lbl = QLabel("场景")
        scene_lbl.setStyleSheet("color: #6c7086; font-size: 11px;")
        self._scene_btn = QPushButton()
        self._scene_btn.setObjectName("scene")
        self._scene_btn.clicked.connect(self._toggle_scene)
        scene_row.addWidget(scene_lbl)
        scene_row.addWidget(self._scene_btn)
        scene_row.addStretch()
        root.addLayout(scene_row)

        sep1 = QFrame(); sep1.setFrameShape(QFrame.HLine); sep1.setObjectName("sep")
        root.addWidget(sep1)

        # Original text
        orig_lbl = QLabel("原文"); orig_lbl.setStyleSheet("color: #6c7086; font-size: 11px;")
        root.addWidget(orig_lbl)
        self._orig_text = QLabel()
        self._orig_text.setWordWrap(True)
        self._orig_text.setStyleSheet("color: #585b70; font-size: 12px; font-family: 'Segoe UI';")
        self._orig_text.setMaximumHeight(56)
        root.addWidget(self._orig_text)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine); sep2.setObjectName("sep")
        root.addWidget(sep2)

        # Result text
        result_lbl = QLabel("建议"); result_lbl.setStyleSheet("color: #89b4fa; font-size: 11px;")
        root.addWidget(result_lbl)
        self._result_text = QLabel()
        self._result_text.setWordWrap(True)
        self._result_text.setStyleSheet(
            "color: #cdd6f4; font-size: 14px; font-weight: bold; font-family: 'Segoe UI';"
            "min-height: 40px;"
        )
        root.addWidget(self._result_text)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton("✗ 取消")
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._confirm_btn = QPushButton("✓ 替换")
        self._confirm_btn.setObjectName("confirm")
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._on_confirm)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._confirm_btn)
        root.addLayout(btn_row)

    @property
    def original_text(self) -> str:
        return self._original

    def show_for(self, original: str, scene: str):
        self._original = original
        self._result = ""
        self._scene = scene
        display = original if len(original) <= 120 else original[:120] + "…"
        self._orig_text.setText(display)
        self._result_text.setText("…")
        self._confirm_btn.setEnabled(False)
        self._update_scene_btn()
        self.adjustSize()
        self._position_near_cursor()
        self.show()
        self.raise_()
        self.activateWindow()

    def _position_near_cursor(self):
        screen = QApplication.primaryScreen().availableGeometry()
        pos = QCursor.pos()
        x = min(pos.x() + 12, screen.right() - self.width() - 10)
        y = min(pos.y() + 12, screen.bottom() - self.height() - 10)
        self.move(x, y)

    def append_token(self, token: str):
        self._result += token
        self._result_text.setText(self._result)
        self.adjustSize()

    def show_complete(self, full_result: str):
        self._result = full_result
        self._result_text.setText(full_result)
        self._confirm_btn.setEnabled(True)
        self.adjustSize()

    def show_error(self, message: str):
        self._result_text.setText(f"⚠ {message}")
        self._confirm_btn.setEnabled(False)
        self.adjustSize()

    def reset(self):
        self._result = ""
        self._result_text.setText("…")
        self._confirm_btn.setEnabled(False)

    def _toggle_scene(self):
        self._scene = "email" if self._scene == "casual" else "casual"
        self._update_scene_btn()
        self.scene_changed.emit(self._scene)

    def _update_scene_btn(self):
        if self._scene == "casual":
            self._scene_btn.setText("日常  ⇄ 邮件")
        else:
            self._scene_btn.setText("邮件  ⇄ 日常")

    def _on_confirm(self):
        self.hide()
        self.confirmed.emit(self._result)

    def _on_cancel(self):
        self.hide()
        self.cancelled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._on_cancel()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self._confirm_btn.isEnabled():
                self._on_confirm()
        else:
            super().keyPressEvent(event)
```

- [ ] **Step 2: Smoke-test the popup in isolation**

```python
# Run from translator-app/ directory
import sys
sys.path.insert(0, ".")
from PyQt5.QtWidgets import QApplication
from popup import TranslatorPopup

app = QApplication(sys.argv)
p = TranslatorPopup()
p.show_for("我想约你明天下午三点开个会", "casual")
p.confirmed.connect(lambda t: (print("Confirmed:", t), app.quit()))
p.cancelled.connect(app.quit)

# Simulate streaming tokens
from PyQt5.QtCore import QTimer
tokens = ["Hey, ", "are you ", "free tomorrow ", "at 3pm ", "for a meeting?"]
i = [0]
def next_token():
    if i[0] < len(tokens):
        p.append_token(tokens[i[0]])
        i[0] += 1
    else:
        p.show_complete("Hey, are you free tomorrow at 3pm for a meeting?")
QTimer.singleShot(500, lambda: [QTimer.singleShot(300 * j, next_token) for j in range(len(tokens) + 1)])

sys.exit(app.exec_())
```

Expected: popup appears near cursor, tokens appear one by one, confirm button enables, ESC and Enter work.

- [ ] **Step 3: Commit**

```bash
git add translator-app/popup.py
git commit -m "feat: PyQt5 floating popup with streaming display and scene toggle"
```

---

## Task 8: Settings Dialog

**Files:**
- Create: `translator-app/settings.py`

- [ ] **Step 1: Write `translator-app/settings.py`**

```python
import sys
import winreg
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QCheckBox, QPushButton, QMessageBox,
)
from PyQt5.QtCore import Qt

_APP_NAME = "TranslatorApp"

_STYLE = """
QDialog { background-color: #1e1e2e; color: #cdd6f4; font-family: "Segoe UI"; }
QLabel { color: #cdd6f4; font-size: 13px; }
QLineEdit {
    background-color: #313244; border: 1px solid #45475a; border-radius: 4px;
    padding: 5px 8px; color: #cdd6f4; font-size: 13px;
}
QCheckBox { color: #cdd6f4; font-size: 13px; }
QPushButton {
    background-color: #313244; border: none; padding: 6px 18px;
    border-radius: 4px; color: #cdd6f4; font-size: 13px;
}
QPushButton:hover { background-color: #45475a; }
QPushButton#save { background-color: #89b4fa; color: #1e1e2e; font-weight: bold; }
QPushButton#save:hover { background-color: #74c7ec; }
"""


def _set_startup_registry(enabled: bool, exe_path: str) -> None:
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE,
    )
    try:
        if enabled:
            winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, exe_path)
        else:
            try:
                winreg.DeleteValue(key, _APP_NAME)
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)


class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._setup_ui()
        self.setStyleSheet(_STYLE)
        self.setWindowTitle(f"{_APP_NAME} 设置")
        self.setMinimumWidth(420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel("Claude API Key"))
        self._api_key = QLineEdit(self._config.get("api_key", ""))
        self._api_key.setEchoMode(QLineEdit.Password)
        self._api_key.setPlaceholderText("sk-ant-api03-...")
        layout.addWidget(self._api_key)

        layout.addWidget(QLabel("快捷键（例：ctrl+shift+space）"))
        self._hotkey = QLineEdit(self._config.get("hotkey", "ctrl+shift+space"))
        layout.addWidget(self._hotkey)

        self._startup_cb = QCheckBox("开机自启动")
        self._startup_cb.setChecked(self._config.get("startup_with_windows", False))
        layout.addWidget(self._startup_cb)

        layout.addSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存")
        save_btn.setObjectName("save")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _save(self):
        api_key = self._api_key.text().strip()
        hotkey = self._hotkey.text().strip()
        if not hotkey:
            QMessageBox.warning(self, "错误", "快捷键不能为空")
            return

        self._config.set("api_key", api_key)
        self._config.set("hotkey", hotkey)
        startup = self._startup_cb.isChecked()
        self._config.set("startup_with_windows", startup)
        self._config.save()

        try:
            exe_path = str(Path(sys.executable).resolve())
            _set_startup_registry(startup, exe_path)
        except Exception:
            pass

        self.accept()
```

- [ ] **Step 2: Smoke-test**

```python
import sys
sys.path.insert(0, "translator-app")
from PyQt5.QtWidgets import QApplication
from config import Config
from settings import SettingsDialog

app = QApplication(sys.argv)
cfg = Config()
dlg = SettingsDialog(cfg)
dlg.exec_()
print(cfg.get("api_key"))
```

Expected: dialog opens, saving updates the config object.

- [ ] **Step 3: Commit**

```bash
git add translator-app/settings.py
git commit -m "feat: settings dialog with API key, hotkey, startup config"
```

---

## Task 9: System Tray + Hotkey Listener

**Files:**
- Create: `translator-app/hotkey.py`
- Create: `translator-app/tray.py`

- [ ] **Step 1: Write `translator-app/hotkey.py`**

```python
import keyboard
from PyQt5.QtCore import QObject, pyqtSignal


class HotkeyListener(QObject):
    triggered = pyqtSignal()

    def __init__(self, hotkey: str, parent=None):
        super().__init__(parent)
        self._hotkey = hotkey
        self._active = True
        self._registered = False

    def start(self):
        keyboard.add_hotkey(self._hotkey, self._fire)
        self._registered = True

    def _fire(self):
        if self._active:
            self.triggered.emit()

    def set_hotkey(self, new_hotkey: str):
        if self._registered:
            try:
                keyboard.remove_hotkey(self._hotkey)
            except KeyError:
                pass
        self._hotkey = new_hotkey
        keyboard.add_hotkey(self._hotkey, self._fire)
        self._registered = True

    def pause(self):
        self._active = False

    def resume(self):
        self._active = True
```

- [ ] **Step 2: Write `translator-app/tray.py`**

```python
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication
from PyQt5.QtGui import QIcon, QPixmap, QColor


def _make_icon(color: str = "#89b4fa") -> QIcon:
    px = QPixmap(16, 16)
    px.fill(QColor(color))
    return QIcon(px)


class TrayApp(QSystemTrayIcon):
    def __init__(self, app_controller, config, parent=None):
        super().__init__(parent)
        self._ctrl = app_controller
        self._config = config
        self._paused = False
        self.setIcon(_make_icon())
        self.setToolTip("TranslatorApp — 运行中")
        self._build_menu()
        self.show()

    def _build_menu(self):
        menu = QMenu()

        self._pause_action = QAction("暂停监听")
        self._pause_action.triggered.connect(self._toggle_pause)
        menu.addAction(self._pause_action)

        settings_action = QAction("设置…")
        settings_action.triggered.connect(self._ctrl.open_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        quit_action = QAction("退出")
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    def _toggle_pause(self):
        self._paused = not self._paused
        if self._paused:
            self._ctrl.pause_hotkey()
            self._pause_action.setText("恢复监听")
            self.setIcon(_make_icon("#f38ba8"))
            self.setToolTip("TranslatorApp — 已暂停")
        else:
            self._ctrl.resume_hotkey()
            self._pause_action.setText("暂停监听")
            self.setIcon(_make_icon("#89b4fa"))
            self.setToolTip("TranslatorApp — 运行中")

    def flash_message(self, title: str, msg: str):
        self.showMessage(title, msg, QSystemTrayIcon.Information, 2000)
```

- [ ] **Step 3: Commit**

```bash
git add translator-app/hotkey.py translator-app/tray.py
git commit -m "feat: global hotkey listener and system tray"
```

---

## Task 10: Main Application — Wire Everything

**Files:**
- Create: `translator-app/main.py`

- [ ] **Step 1: Write `translator-app/main.py`**

```python
import sys
import time
import win32gui
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QObject, pyqtSlot

from config import Config
from language import detect_mode
from window_detector import get_active_window_title, infer_scene
from clipboard_io import read_input_box, write_input_box, restore_clipboard
from claude_client import ClaudeWorker
from popup import TranslatorPopup
from tray import TrayApp
from hotkey import HotkeyListener
from settings import SettingsDialog


class App(QObject):
    def __init__(self):
        super().__init__()
        self._config = Config()
        self._original_hwnd: int | None = None
        self._saved_clipboard: str | None = None
        self._had_selection: bool = False
        self._worker: ClaudeWorker | None = None

        self._popup = TranslatorPopup()
        self._popup.confirmed.connect(self._on_confirmed)
        self._popup.cancelled.connect(self._on_cancelled)
        self._popup.scene_changed.connect(self._on_scene_changed)

        hotkey = self._config.get("hotkey", "ctrl+shift+space")
        self._hotkey = HotkeyListener(hotkey)
        self._hotkey.triggered.connect(self._on_hotkey)
        self._hotkey.start()

        self._tray = TrayApp(self, self._config)

        if not self._config.get("api_key"):
            self.open_settings()

    @pyqtSlot()
    def _on_hotkey(self):
        if not self._config.get("api_key"):
            self._tray.flash_message("TranslatorApp", "请先在设置中填写 API Key")
            self.open_settings()
            return

        # Capture original window BEFORE any clipboard operations
        self._original_hwnd = win32gui.GetForegroundWindow()

        text, saved, had_selection = read_input_box()
        self._saved_clipboard = saved
        self._had_selection = had_selection

        if not text.strip():
            self._tray.flash_message("TranslatorApp", "输入框内容为空")
            restore_clipboard(saved)
            return

        window_title = get_active_window_title()
        scene = infer_scene(window_title, self._config.get("window_scene_map", {}))
        mode = detect_mode(text)

        self._popup.show_for(text, scene)
        self._start_worker(text, mode, scene)

    def _start_worker(self, text: str, mode: str, scene: str):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()

        self._worker = ClaudeWorker(
            self._config.get("api_key", ""), text, mode, scene
        )
        self._worker.token_received.connect(self._popup.append_token)
        self._worker.finished.connect(self._popup.show_complete)
        self._worker.error.connect(self._popup.show_error)
        self._worker.start()

    @pyqtSlot(str)
    def _on_scene_changed(self, scene: str):
        self._popup.reset()
        text = self._popup.original_text
        mode = detect_mode(text)
        self._start_worker(text, mode, scene)

    @pyqtSlot(str)
    def _on_confirmed(self, result_text: str):
        if self._original_hwnd:
            try:
                win32gui.SetForegroundWindow(self._original_hwnd)
                time.sleep(0.12)
            except Exception:
                pass
        write_input_box(result_text, self._saved_clipboard, self._had_selection)

    @pyqtSlot()
    def _on_cancelled(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        restore_clipboard(self._saved_clipboard)

    def pause_hotkey(self):
        self._hotkey.pause()

    def resume_hotkey(self):
        self._hotkey.resume()

    def open_settings(self):
        old_hotkey = self._config.get("hotkey")
        dlg = SettingsDialog(self._config)
        if dlg.exec_():
            new_hotkey = self._config.get("hotkey")
            if new_hotkey != old_hotkey:
                self._hotkey.set_hotkey(new_hotkey)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    controller = App()  # noqa: F841 — keeps object alive
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run all unit tests to confirm nothing broken**

```bash
cd translator-app && pytest ../tests/ -v
```

Expected: All previously written tests still pass (config, language, window_detector, claude_client).

- [ ] **Step 3: End-to-end manual test**

```bash
cd translator-app && python main.py
```

Test sequence:
1. Tray icon appears (blue square) — confirms app started
2. Settings dialog opens automatically (API Key empty)
3. Fill in a real Claude API Key, click Save
4. Open Notepad, type: `我今天有个会议`
5. Press `Ctrl+Shift+Space`
6. Popup appears near cursor with original text visible
7. Streaming result appears token by token
8. Press Enter or click ✓ 替换
9. Notepad text is replaced with translated English
10. Test scene toggle: type email text, trigger hotkey, click "日常 ⇄ 邮件" in popup — verify result changes to formal style

- [ ] **Step 4: Commit**

```bash
git add translator-app/main.py
git commit -m "feat: main app orchestrator — wires all modules end-to-end"
```

---

## Task 11: PyInstaller Packaging

**Files:**
- Create: `translator-app.spec`

- [ ] **Step 1: Generate base spec**

```bash
cd translator-app && pyinstaller --name TranslatorApp --onefile --windowed --noconsole main.py
```

Expected: `dist/TranslatorApp.exe` created (may have DLL warnings — that's OK for now).

- [ ] **Step 2: Edit `translator-app.spec` to include PyQt5 and pywin32 hooks**

Replace the generated `TranslatorApp.spec` with:

```python
# translator-app.spec
block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=[
        "win32gui", "win32con", "win32clipboard", "win32process",
        "pywintypes", "keyboard",
        "anthropic", "httpx", "certifi",
        "PyQt5.QtWidgets", "PyQt5.QtCore", "PyQt5.QtGui",
        "PyQt5.sip",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="TranslatorApp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

- [ ] **Step 3: Build using the spec**

```bash
pyinstaller translator-app.spec
```

Expected: `dist/TranslatorApp.exe` (single file, ~80-150 MB).

- [ ] **Step 4: Test the exe**

```bash
dist\TranslatorApp.exe
```

Expected: tray icon appears, app behaves identically to `python main.py`.

- [ ] **Step 5: Commit**

```bash
git add translator-app.spec
git commit -m "chore: PyInstaller spec for single-exe packaging"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by task |
|---|---|
| 全局快捷键触发 | Task 9 (hotkey.py) + Task 10 (main.py) |
| 自动检测输入语言（含中英夹杂→翻译） | Task 3 (language.py) |
| 基于场景的 Claude prompt | Task 5 (claude_client.py) |
| 悬浮窗流式展示 | Task 7 (popup.py) |
| 场景切换后立即重新请求 | Task 10 (_on_scene_changed) |
| 手动选中模式（只替换选中区域） | Task 6 (clipboard_io.py) |
| 剪贴板保护（读写前后恢复） | Task 6 (save/restore_clipboard) |
| 原始窗口焦点恢复后再粘贴 | Task 10 (_on_confirmed with SetForegroundWindow) |
| 系统托盘 + 暂停/恢复/设置/退出 | Task 9 (tray.py) |
| Settings dialog (API Key / hotkey / startup) | Task 8 (settings.py) |
| 开机自启动注册表 | Task 8 (_set_startup_registry) |
| 错误处理（超时/无效Key/空输入框） | Task 5 (ClaudeWorker exceptions) + Task 10 |
| 打包单 exe | Task 11 |

All requirements covered. No placeholders remain.
