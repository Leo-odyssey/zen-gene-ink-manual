from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QApplication, QTextEdit, QSizeGrip,
    QGraphicsOpacityEffect,
)
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer
from PyQt5.QtGui import QCursor, QTextOption

from version import VERSION

_FONT = '"Inter", "Segoe UI", "Source Han Sans CN", "Microsoft YaHei UI"'

_STYLE = f"""
/* ── Container ────────────────────────────────────────────── */
QWidget#popup_container {{
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
QLabel#version_lbl {{ color: #252e3d; font-size: 10px; }}
QLabel#section_lbl {{ color: #49556a; font-size: 11px; letter-spacing: 0.2px; }}
QLabel#result_lbl  {{ color: #4f84c4; font-size: 11px; font-weight: 600; letter-spacing: 0.2px; }}
QLabel#ver2_lbl    {{ color: #49556a; font-size: 11px; }}
QLabel#gen_lbl     {{ color: #4f84c4; font-size: 11px; letter-spacing: 2px; }}
QLabel#hint_lbl    {{ color: #2a3448; font-size: 10px; font-style: italic; }}
/* ── Buttons — default ghost ──────────────────────────────── */
QPushButton {{
    background: transparent; border: none;
    padding: 5px 12px; border-radius: 8px;
    color: #49556a; font-family: {_FONT}; font-size: 12px;
}}
QPushButton:hover {{ background-color: #181e2a; color: #adbac7; }}
/* ── Confirm (green filled) ───────────────────────────────── */
QPushButton#confirm {{
    background-color: #1a7f37; color: #fff;
    font-size: 13px; font-weight: 600;
    padding: 7px 22px; border-radius: 8px;
}}
QPushButton#confirm:hover {{ background-color: #238636; }}
QPushButton#confirm:disabled {{
    background-color: #131921; color: #252e3d;
}}
/* ── Cancel ghost ─────────────────────────────────────────── */
QPushButton#cancel_btn {{
    background: transparent; border: none;
    color: #49556a; font-size: 13px;
    padding: 7px 14px; border-radius: 8px;
}}
QPushButton#cancel_btn:hover {{ color: #adbac7; background-color: #181e2a; }}
/* ── Close / icon ghost ───────────────────────────────────── */
QPushButton#close_btn {{
    background: transparent; border: none;
    color: #2e3a4d; font-size: 14px; padding: 2px 8px; border-radius: 6px;
}}
QPushButton#close_btn:hover {{ color: #e05c5c; background-color: #1e1a1a; }}
QPushButton#icon_btn {{
    background: transparent; border: none;
    color: #49556a; font-size: 13px; padding: 3px 8px; border-radius: 6px;
}}
QPushButton#icon_btn:hover {{ color: #adbac7; background-color: #181e2a; }}
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
QTextEdit#orig_box  {{ color: #2d3a4d; font-size: 13px; }}
QTextEdit#result_box {{
    color: #dde4ee; font-size: 15px; font-weight: 600;
}}
QTextEdit#result_box_active {{
    color: #dde4ee; font-size: 15px; font-weight: 600;
    background: #0a1322; border: 1px solid #182845;
    border-radius: 8px; padding: 4px 8px;
}}
QTextEdit#result_box2 {{
    color: #49556a; font-size: 13px;
}}
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
QScrollBar::handle:vertical:hover  {{ background: #4f84c4; }}
QScrollBar::handle:vertical:pressed {{ background: #3a6fa8; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
/* ── Resize grip ──────────────────────────────────────────── */
QSizeGrip {{ background: transparent; width: 12px; height: 12px; }}
"""


class _ClickableTextEdit(QTextEdit):
    clicked = pyqtSignal()
    double_clicked = pyqtSignal()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.clicked.emit()

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        self.double_clicked.emit()


class TranslatorPopup(QWidget):
    confirmed      = pyqtSignal(str)
    cancelled      = pyqtSignal()
    scene_changed  = pyqtSignal(str)
    suffix_toggled = pyqtSignal(bool)  # kept for API compat
    retried        = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results = ["", ""]
        self._version_idx = 0
        self._version_ready = [False, False]
        self._scene = "spoken"
        self._original = ""
        self._suffix_enabled = True
        self._multi_version = False
        self._drag_pos = None
        self._fade_anim = None
        self._opacity_effect = None
        self._auto_confirm = False
        self._gen_timer = QTimer(self)
        self._gen_timer.setInterval(450)
        self._gen_timer.timeout.connect(self._tick_gen)
        self._gen_dots = 0
        self._is_generating = False


        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setMinimumWidth(520)
        self.setMinimumHeight(200)

        self._container = QWidget(self)
        self._container.setObjectName("popup_container")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._container)

        self.setStyleSheet(_STYLE)
        self._setup_ui()

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

        close_btn = QPushButton("✕")
        close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self._on_cancel)
        h.addWidget(close_btn)

        root.addWidget(header)
        self._header = header

        # ── Body ───────────────────────────────────────────────────────────
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(18, 14, 18, 14)
        bl.setSpacing(0)

        orig_lbl = QLabel("原文")
        orig_lbl.setObjectName("section_lbl")
        bl.addWidget(orig_lbl)
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
        self._orig_text.setToolTip("提示：选中部分文字后再触发，可只处理所选内容")
        bl.addWidget(self._orig_text)

        # Selection hint — always visible, very muted
        hint_lbl = QLabel("选中部分文字后触发，只处理所选内容")
        hint_lbl.setObjectName("hint_lbl")
        bl.addSpacing(3)
        bl.addWidget(hint_lbl)

        bl.addSpacing(14)

        # Result row: label | gen dots | retry | copy
        result_row = QHBoxLayout()
        self._result_lbl = QLabel("建议")
        self._result_lbl.setObjectName("result_lbl")
        result_row.addWidget(self._result_lbl)
        result_row.addSpacing(6)
        self._gen_lbl = QLabel("")
        self._gen_lbl.setObjectName("gen_lbl")
        result_row.addWidget(self._gen_lbl)
        result_row.addStretch()
        self._retry_btn = QPushButton("↺")
        self._retry_btn.setObjectName("icon_btn")
        self._retry_btn.setToolTip("重新生成")
        self._retry_btn.setEnabled(False)
        self._retry_btn.clicked.connect(self._on_retry)
        result_row.addWidget(self._retry_btn)
        self._copy_btn = QPushButton("复制")
        self._copy_btn.setObjectName("icon_btn")
        self._copy_btn.clicked.connect(self._on_copy)
        result_row.addWidget(self._copy_btn)
        bl.addLayout(result_row)
        bl.addSpacing(6)

        self._result_text = _ClickableTextEdit()
        self._result_text.setObjectName("result_box_active")
        self._result_text.setReadOnly(True)
        self._result_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._result_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._result_text.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self._result_text.setMinimumHeight(70)
        self._result_text.setMaximumHeight(220)
        self._result_text.setFocusPolicy(Qt.NoFocus)
        self._result_text.clicked.connect(lambda: self._switch_version(0))
        self._result_text.double_clicked.connect(lambda: self._on_double_click(0))
        bl.addWidget(self._result_text)

        # V2 section
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
        hint_lbl = QLabel("Enter 替换 · Esc 取消")
        hint_lbl.setObjectName("version_lbl")
        footer.addWidget(hint_lbl)
        footer.addStretch()
        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setObjectName("cancel_btn")
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._confirm_btn = QPushButton("✓  替换")
        self._confirm_btn.setObjectName("confirm")
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._on_confirm)
        footer.addWidget(self._cancel_btn)
        footer.addWidget(self._confirm_btn)
        footer.addWidget(QSizeGrip(self._container))
        bl.addLayout(footer)

        root.addWidget(body)

    # ── Fade animation ────────────────────────────────────────────────────────

    def _fade_in(self):
        if self._opacity_effect is None:
            self._opacity_effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(180)
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

    # ── Explain animation ─────────────────────────────────────────────────────

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def original_text(self) -> str:
        return self._original

    @property
    def current_scene(self) -> str:
        return self._scene

    def set_multi_version(self, enabled: bool):
        self._multi_version = enabled
        self._v2_section.setVisible(enabled)
        # Update V1 label to clarify click-to-select when V2 is present
        if enabled:
            self._result_lbl.setText("版 1  — 点击选用")
        else:
            self._result_lbl.setText("建议")

    def set_auto_confirm(self, enabled: bool):
        self._auto_confirm = enabled

    def set_suffix_enabled(self, enabled: bool):
        self._suffix_enabled = enabled

    def show_for(self, original: str, scene: str):
        self._original = original
        self._results = ["", ""]
        self._version_idx = 0
        self._version_ready = [False, False]
        self._scene = scene
        self._orig_text.setPlainText(original)
        self._result_text.setPlainText("…")
        self._result2_text.setPlainText("…" if self._multi_version else "")

        self._confirm_btn.setEnabled(False)
        self._retry_btn.setEnabled(False)
        self._update_scene_btns()
        self._update_ver_display()
        self._start_gen()
        self.adjustSize()
        was_hidden = not self.isVisible()
        if was_hidden:
            self._position_near_cursor()
            self.show()
        self.raise_()
        self.activateWindow()
        if was_hidden:
            self._fade_in()

    def append_token(self, token: str, version: int = 0):
        self._results[version] += token
        if version == 0:
            self._result_text.setPlainText(self._results[version])
        elif version == 1:
            self._result2_text.setPlainText(self._results[version])

    def show_complete(self, full: str, version: int = 0):
        self._results[version] = full
        self._version_ready[version] = True
        if version == 0:
            self._result_text.setPlainText(full)
        elif version == 1:
            self._result2_text.setPlainText(full)
        self._confirm_btn.setEnabled(self._version_ready[self._version_idx])
        if self._version_ready[0]:
            self._stop_gen()
            self._retry_btn.setEnabled(True)
            if self._auto_confirm and not self._multi_version and full:
                self._on_confirm()
                return
        self._update_ver_display()

    def show_error(self, message: str):
        self._result_text.setPlainText(f"⚠  {message}")
        self._confirm_btn.setEnabled(False)
        self._stop_gen()
        self._retry_btn.setEnabled(bool(self._original))

    def reset(self):
        self._results = ["", ""]
        self._version_ready = [False, False]
        self._result_text.setPlainText("…")
        self._result2_text.setPlainText("…" if self._multi_version else "")

        self._confirm_btn.setEnabled(False)
        self._retry_btn.setEnabled(False)
        self._stop_gen()
        self._start_gen()
        self._update_ver_display()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _position_near_cursor(self):
        pos = QCursor.pos()
        screen = QApplication.screenAt(pos) or QApplication.primaryScreen()
        geo = screen.availableGeometry()
        x = min(pos.x() + 12, geo.right() - self.width() - 10)
        y = min(pos.y() + 12, geo.bottom() - self.height() - 10)
        x = max(x, geo.left() + 10)
        y = max(y, geo.top() + 10)
        self.move(x, y)

    def _switch_version(self, idx: int):
        self._version_idx = idx
        self._confirm_btn.setEnabled(self._version_ready[idx])

        self._update_ver_display()

    def _update_ver_display(self):
        v1_active = (self._version_idx == 0)
        self._result_text.setObjectName("result_box_active" if v1_active else "result_box")
        self._result_text.style().unpolish(self._result_text)
        self._result_text.style().polish(self._result_text)
        if self._multi_version:
            v2_active = (self._version_idx == 1)
            self._result2_text.setObjectName(
                "result_box2_active" if v2_active else "result_box2"
            )
            self._result2_text.style().unpolish(self._result2_text)
            self._result2_text.style().polish(self._result2_text)

    def _on_copy(self):
        text = self._results[self._version_idx]
        if text:
            QApplication.clipboard().setText(text)

    def _on_retry(self):
        if self._original:
            self.retried.emit()

    def _select_scene(self, scene: str):
        if scene == self._scene:
            return
        self._scene = scene
        self._update_scene_btns()
        self.scene_changed.emit(scene)

    def _update_scene_btns(self):
        for scene, btn in (
            ("spoken", self._spoken_btn),
            ("casual", self._casual_btn),
            ("email",  self._email_btn),
        ):
            btn.setObjectName("scene_active" if scene == self._scene else "scene_inactive")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _on_double_click(self, idx: int):
        self._switch_version(idx)
        if self._confirm_btn.isEnabled():
            self._on_confirm()

    def _on_confirm(self):
        self.hide()
        self.confirmed.emit(self._results[self._version_idx])

    def _on_cancel(self):
        self._stop_gen()
        self.hide()
        self.cancelled.emit()

    # ── Drag (header zone) ────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.y() < self._header.height():
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
        else:
            self._drag_pos = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._on_cancel()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self._confirm_btn.isEnabled():
                self._on_confirm()
        else:
            super().keyPressEvent(event)


