from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication, QWidgetAction, QLabel
from PyQt5.QtGui import QIcon, QPixmap, QColor, QPainter, QPen, QFont, QPolygonF
from PyQt5.QtCore import Qt, QPointF

from version import APP_NAME, VERSION

_MENU_STYLE = """
QMenu {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 4px 0px;
    font-family: "Segoe UI";
    font-size: 11px;
    color: #e6edf3;
}
QMenu::item {
    padding: 6px 22px 6px 12px;
    border-radius: 4px;
    margin: 1px 4px;
}
QMenu::item:selected {
    background-color: #21262d;
}
QMenu::item:checked {
    color: #4f84c4;
    font-weight: bold;
}
QMenu::indicator {
    width: 0px; height: 0px;
}
QMenu::separator {
    height: 1px;
    background-color: #30363d;
    margin: 3px 0px;
}
QMenu::right-arrow { image: none; }
"""

_SCENE_LABELS = {
    "spoken": "日常",
    "casual": "随意",
    "email":  "商务",
}

_REGION_LABELS = {
    "us": "🇺🇸 美式",
    "uk": "🇬🇧 英式",
    "sg": "🇸🇬 新式",
}


def _check_icon(checked: bool) -> QIcon:
    """14×14 icon: blue checkmark if checked, transparent if not."""
    px = QPixmap(14, 14)
    px.fill(Qt.transparent)
    if checked:
        p = QPainter(px)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#4f84c4"), 1.8)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.drawPolyline(QPolygonF([QPointF(2, 7), QPointF(5, 10), QPointF(12, 3)]))
        p.end()
    return QIcon(px)


_IC = "#49556a"  # muted icon color, same family as menu palette


def _ic(draw_fn, color: str = _IC) -> QIcon:
    px = QPixmap(14, 14)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.4)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    draw_fn(p)
    p.end()
    return QIcon(px)


def _scene_icon() -> QIcon:
    def draw(p):
        for y in (4, 7, 10):
            p.drawLine(2, y, 12, y)
    return _ic(draw)


def _region_icon() -> QIcon:
    def draw(p):
        p.drawEllipse(2, 2, 10, 10)
        p.drawLine(7, 2, 7, 12)
        p.drawLine(2, 7, 12, 7)
    return _ic(draw)


def _suffix_icon(enabled: bool = False) -> QIcon:
    def draw(p):
        p.drawRoundedRect(1, 4, 5, 6, 1, 1)
        p.drawRoundedRect(8, 4, 5, 6, 1, 1)
    return _ic(draw, "#4f84c4" if enabled else _IC)


def _panel_icon(enabled: bool = False) -> QIcon:
    def draw(p):
        p.drawRect(1, 2, 12, 10)
        p.drawLine(1, 6, 13, 6)
    return _ic(draw, "#4f84c4" if enabled else _IC)


def _pause_icon() -> QIcon:
    def draw(p):
        pen2 = QPen(QColor(_IC), 2.2)
        pen2.setCapStyle(Qt.RoundCap)
        p.setPen(pen2)
        p.drawLine(4, 3, 4, 11)
        p.drawLine(10, 3, 10, 11)
    return _ic(draw)


def _settings_icon() -> QIcon:
    def draw(p):
        p.drawEllipse(4, 4, 6, 6)
        p.drawLine(7, 1, 7, 3)
        p.drawLine(7, 11, 7, 13)
        p.drawLine(1, 7, 3, 7)
        p.drawLine(11, 7, 13, 7)
    return _ic(draw)


def _exit_icon() -> QIcon:
    def draw(p):
        p.drawArc(2, 3, 10, 10, 50 * 16, 260 * 16)
        p.drawLine(7, 1, 7, 7)
    return _ic(draw)


def _make_enso_icon(paused: bool = False) -> QIcon:
    """Draw a zen/enso circle icon at 64×64 and return as QIcon."""
    size = 64
    px = QPixmap(size, size)
    px.fill(Qt.transparent)

    painter = QPainter(px)
    painter.setRenderHint(QPainter.Antialiasing)

    color = "#ef4444" if paused else "#4f84c4"
    pen = QPen(QColor(color), 9)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)

    # Enso: open circle with a gap at bottom-right (~300° arc)
    margin = 7
    rect_size = size - 2 * margin
    painter.drawArc(margin, margin, rect_size, rect_size, 60 * 16, 300 * 16)

    # Tiny teal accent dot (matches logo's tech element)
    if not paused:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#56cfe1"))
        dot = 10
        painter.drawEllipse(size - margin - dot, size - margin - dot, dot, dot)

    painter.end()
    return QIcon(px)


class TrayApp(QSystemTrayIcon):
    def __init__(self, app_controller, config, parent=None):
        super().__init__(parent)
        self._ctrl = app_controller
        self._config = config
        self._paused = False
        self.setIcon(_make_enso_icon())
        self.setToolTip(f"{APP_NAME} v{VERSION} — 运行中")
        self._build_menu()
        self.show()

    def _build_menu(self):
        self._menu = QMenu()
        self._menu.setStyleSheet(_MENU_STYLE)

        # Brand header — centered via QWidgetAction
        brand_lbl = QLabel(f"✦ {APP_NAME}  v{VERSION}")
        brand_lbl.setAlignment(Qt.AlignCenter)
        brand_lbl.setStyleSheet(
            "color: #4f84c4; font-weight: bold; font-size: 11px;"
            "font-family: 'Segoe UI'; padding: 8px 16px; background: transparent;"
        )
        brand_wa = QWidgetAction(self._menu)
        brand_wa.setDefaultWidget(brand_lbl)
        self._menu.addAction(brand_wa)
        self._menu.addSeparator()

        # ── 场景 submenu ──────────────────────────
        scene_menu = QMenu("场景", self._menu)
        scene_menu.setStyleSheet(_MENU_STYLE)
        self._scene_actions: dict[str, QAction] = {}
        current = self._config.get("default_scene", "spoken")
        for key, label in _SCENE_LABELS.items():
            act = QAction(label, scene_menu)
            act.setCheckable(True)
            act.setChecked(key == current)
            act.triggered.connect(lambda checked, s=key: self._set_scene(s))
            scene_menu.addAction(act)
            self._scene_actions[key] = act
        self._menu.addMenu(scene_menu).setIcon(_scene_icon())

        # ── 英文风格 submenu ──────────────────────────
        region_menu = QMenu("英文风格", self._menu)
        region_menu.setStyleSheet(_MENU_STYLE)
        self._region_actions: dict[str, QAction] = {}
        current_region = self._config.get("region", "sg")
        for key, label in _REGION_LABELS.items():
            act = QAction(label, region_menu)
            act.setCheckable(True)
            act.setChecked(key == current_region)
            act.triggered.connect(lambda checked, r=key: self._set_region(r))
            region_menu.addAction(act)
            self._region_actions[key] = act
        self._menu.addMenu(region_menu).setIcon(_region_icon())

        # ── 后缀触发 toggle ────────────────────────
        self._suffix_action = QAction("后缀触发", self._menu)
        self._suffix_action.triggered.connect(self._toggle_suffix)
        self._menu.addAction(self._suffix_action)
        self._set_suffix_label(self._config.get("suffix_enabled", True))

        # ── 固定面板 toggle ───────────────────────
        self._companion_action = QAction("固定面板", self._menu)
        self._companion_action.triggered.connect(self._toggle_companion)
        self._menu.addAction(self._companion_action)
        self._set_companion_label(self._config.get("companion_enabled", False))

        self._menu.addSeparator()

        # ── 暂停 / 设置 / 退出 ─────────────────────
        self._pause_action = QAction("暂停监听", self._menu)
        self._pause_action.setIcon(_pause_icon())
        self._pause_action.triggered.connect(self._toggle_pause)
        self._menu.addAction(self._pause_action)

        settings_action = QAction("设置…", self._menu)
        settings_action.setIcon(_settings_icon())
        settings_action.triggered.connect(self._ctrl.open_settings)
        self._menu.addAction(settings_action)

        self._menu.addSeparator()

        quit_action = QAction("退出", self._menu)
        quit_action.setIcon(_exit_icon())
        quit_action.triggered.connect(QApplication.quit)
        self._menu.addAction(quit_action)

        self.setContextMenu(self._menu)
        self.activated.connect(self._on_activated)

    def _set_scene(self, scene: str):
        for key, act in self._scene_actions.items():
            act.setChecked(key == scene)
        self._ctrl.set_default_scene(scene)

    def _set_region(self, region: str):
        for key, act in self._region_actions.items():
            act.setChecked(key == region)
        self._ctrl.set_region(region)

    def update_region_check(self, region: str):
        for key, act in self._region_actions.items():
            act.setChecked(key == region)

    def _set_suffix_label(self, enabled: bool):
        self._suffix_action.setIcon(_check_icon(enabled))

    def _set_companion_label(self, enabled: bool):
        self._companion_action.setIcon(_check_icon(enabled))

    def _toggle_suffix(self):
        self._ctrl.set_suffix_enabled(not self._config.get("suffix_enabled", True))

    def _toggle_companion(self):
        self._ctrl.set_companion_enabled(not self._config.get("companion_enabled", False))

    def update_companion_check(self, enabled: bool):
        self._set_companion_label(enabled)

    def update_suffix_check(self, enabled: bool):
        self._set_suffix_label(enabled)

    def update_scene_check(self, scene: str):
        for key, act in self._scene_actions.items():
            act.setChecked(key == scene)

    def _toggle_pause(self):
        self._paused = not self._paused
        if self._paused:
            self._ctrl.pause_hotkey()
            self._pause_action.setText("恢复监听")
            self.setIcon(_make_enso_icon(paused=True))
            self.setToolTip(f"{APP_NAME} v{VERSION} — 已暂停")
        else:
            self._ctrl.resume_hotkey()
            self._pause_action.setText("暂停监听")
            self.setIcon(_make_enso_icon())
            self.setToolTip(f"{APP_NAME} v{VERSION} — 运行中")

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._ctrl.open_settings()

    def flash_message(self, title: str, msg: str):
        self.showMessage(title, msg, QSystemTrayIcon.Information, 2000)
