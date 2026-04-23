import sys
import winreg
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QLineEdit, QCheckBox, QPushButton, QMessageBox, QTextEdit,
    QWidget, QComboBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from claude_client import SYSTEM_PROMPT, DEFAULT_USER_PROMPTS, PROVIDERS, build_system_prompt
from usage_tracker import UsageTracker
from version import APP_NAME, VERSION

_APP_NAME = APP_NAME

_FONT = '"Inter", "Segoe UI", "Source Han Sans CN", "Microsoft YaHei UI"'

_STYLE = f"""
QDialog {{ background-color: #161b22; color: #e6edf3; font-family: {_FONT}; }}
QWidget {{ background-color: #161b22; }}
QLabel {{ color: #e6edf3; font-size: 11px; font-family: {_FONT}; }}
QLabel#section {{ color: #4f84c4; font-size: 10px; font-weight: bold; }}
QLabel#hint {{ color: #7d8590; font-size: 9px; font-style: italic; }}
QLineEdit {{
    background-color: #21262d; border: 1px solid #30363d; border-radius: 6px;
    padding: 4px 8px; color: #e6edf3; font-size: 11px; font-family: {_FONT};
}}
QLineEdit:focus {{ border-color: #4f84c4; }}
QTextEdit {{
    background-color: #21262d; border: 1px solid #30363d; border-radius: 6px;
    padding: 4px 8px; color: #e6edf3; font-size: 10px; font-family: {_FONT};
}}
QTextEdit:focus {{ border-color: #4f84c4; }}
QTextEdit[readOnly="true"] {{
    background-color: #0d1117; color: #7d8590;
    border: 1px solid #21262d;
}}
QCheckBox {{ color: #e6edf3; font-size: 11px; font-family: {_FONT}; }}
QCheckBox::indicator {{ width: 13px; height: 13px; }}
QPushButton {{
    background-color: #21262d; border: 1px solid #30363d; padding: 5px 16px;
    border-radius: 6px; color: #e6edf3; font-size: 11px; font-family: {_FONT};
}}
QPushButton:hover {{ background-color: #2d333b; border-color: #444c56; }}
QPushButton:checked {{
    background-color: #1f3a5f; border: 1px solid #4f84c4;
    color: #79b8ff; font-weight: bold;
}}
QPushButton:checked:hover {{ background-color: #243b55; }}
QPushButton#save {{
    background-color: #238636; border-color: #2ea043; color: #fff; font-weight: bold;
}}
QPushButton#save:hover {{ background-color: #2ea043; }}
QPushButton#danger {{ color: #f85149; }}
QPushButton#danger:hover {{ background-color: #2d333b; }}
QComboBox {{
    background-color: #21262d; border: 1px solid #30363d; border-radius: 6px;
    padding: 4px 8px; color: #e6edf3; font-size: 11px; font-family: {_FONT};
}}
QComboBox:focus {{ border-color: #4f84c4; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: #21262d; border: 1px solid #30363d;
    color: #e6edf3; selection-background-color: #1f3a5f;
    font-family: {_FONT};
}}
QScrollBar:vertical {{
    background: transparent; width: 6px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #30363d; border-radius: 3px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: #4f84c4; }}
QScrollBar::handle:vertical:pressed {{ background: #3a6fa8; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollArea {{ border: none; }}
"""

_PROMPT_LABELS = [
    (("optimize", "spoken"), "优化 — 日常"),
    (("optimize", "casual"), "优化 — 随意"),
    (("optimize", "email"),  "优化 — 商务"),
    (("translate", "spoken"), "翻译 — 日常"),
    (("translate", "casual"), "翻译 — 随意"),
    (("translate", "email"),  "翻译 — 商务"),
]

_SCENE_OPTIONS = [
    ("spoken", "日常"),
    ("casual", "随意"),
    ("email",  "商务"),
]


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


class WindowMapDialog(QDialog):
    """Edit window title → scene auto-mapping."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._rows: list[tuple[QLineEdit, QComboBox, QWidget]] = []
        self._setup_ui()
        self.setStyleSheet(_STYLE)
        self.setWindowTitle("窗口场景映射")
        self.setMinimumWidth(480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)

        title = QLabel("窗口场景映射")
        title.setObjectName("section")
        layout.addWidget(title)

        hint = QLabel(
            "当前活动窗口的标题包含以下关键词时，自动切换到对应场景（不区分大小写）。"
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addSpacing(4)

        # Column headers
        header_row = QHBoxLayout()
        kw_hdr = QLabel("窗口标题关键词")
        kw_hdr.setObjectName("hint")
        header_row.addWidget(kw_hdr, 1)
        sc_hdr = QLabel("场景")
        sc_hdr.setObjectName("hint")
        sc_hdr.setFixedWidth(80)
        header_row.addWidget(sc_hdr)
        header_row.addSpacing(58)  # space for delete button
        layout.addLayout(header_row)

        # Scrollable rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setMaximumHeight(220)
        rows_widget = QWidget()
        self._rows_layout = QVBoxLayout(rows_widget)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(6)
        scroll.setWidget(rows_widget)
        layout.addWidget(scroll)

        # Load existing mappings
        existing = self._config.get("window_scene_map", {})
        for keyword, scene in existing.items():
            self._add_row(keyword, scene)

        add_btn = QPushButton("+ 添加映射")
        add_btn.clicked.connect(lambda: self._add_row("", "spoken"))
        layout.addWidget(add_btn)

        layout.addStretch()

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

    def _add_row(self, keyword: str = "", scene: str = "spoken"):
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        kw_edit = QLineEdit(keyword)
        kw_edit.setPlaceholderText("如：outlook、whatsapp、slack")
        row.addWidget(kw_edit, 1)

        scene_combo = QComboBox()
        for key, label in _SCENE_OPTIONS:
            scene_combo.addItem(label, key)
        for i, (key, _) in enumerate(_SCENE_OPTIONS):
            if key == scene:
                scene_combo.setCurrentIndex(i)
                break
        scene_combo.setFixedWidth(80)
        row.addWidget(scene_combo)

        del_btn = QPushButton("删除")
        del_btn.setObjectName("danger")
        del_btn.setFixedWidth(50)
        del_btn.clicked.connect(lambda: self._delete_row(row_widget, kw_edit, scene_combo))
        row.addWidget(del_btn)

        self._rows_layout.addWidget(row_widget)
        self._rows.append((kw_edit, scene_combo, row_widget))

    def _delete_row(self, row_widget, kw_edit, scene_combo):
        self._rows = [(k, s, w) for k, s, w in self._rows
                      if k is not kw_edit or s is not scene_combo]
        self._rows_layout.removeWidget(row_widget)
        row_widget.hide()
        row_widget.deleteLater()

    def _save(self):
        mapping: dict[str, str] = {}
        for kw_edit, scene_combo, _ in self._rows:
            kw = kw_edit.text().strip().lower()
            scene = scene_combo.currentData()
            if kw:
                mapping[kw] = scene
        self._config.set("window_scene_map", mapping)
        self._config.save()
        self.accept()


class PromptsDialog(QDialog):
    """Edit system prompt and all six user prompt templates."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._setup_ui()
        self.setStyleSheet(_STYLE)
        self.setWindowTitle("编辑提示词")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        from PyQt5.QtWidgets import QApplication as _QApp
        screen = _QApp.primaryScreen().availableGeometry()
        self.setMaximumHeight(screen.height() - 80)

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 12)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 8)
        layout.setSpacing(8)

        saved = self._config.get("prompts", {})

        # ── Default system prompt (read-only reference) ───────────────────
        default_lbl = QLabel("默认系统提示词（只读）")
        default_lbl.setObjectName("section")
        layout.addWidget(default_lbl)

        hint1 = QLabel("这是内置的默认指令，控制 AI 的整体翻译风格和行为。")
        hint1.setObjectName("hint")
        hint1.setWordWrap(True)
        layout.addWidget(hint1)

        default_view = QTextEdit()
        default_view.setReadOnly(True)
        default_view.setPlainText(SYSTEM_PROMPT)
        default_view.setMinimumHeight(130)
        default_view.setMaximumHeight(160)
        layout.addWidget(default_view)

        layout.addSpacing(4)

        # ── Custom system prompt override ─────────────────────────────────
        custom_lbl = QLabel("自定义系统提示词（替换上方默认，留空则使用默认）")
        custom_lbl.setObjectName("section")
        layout.addWidget(custom_lbl)

        hint2 = QLabel(
            "在此输入你的完整系统提示词。保存后将替换默认内容。\n"
            "注意：无论是否自定义，英文风格设置和个人风格指南（在设置主页配置）都会自动追加到提示词末尾。"
        )
        hint2.setObjectName("hint")
        hint2.setWordWrap(True)
        layout.addWidget(hint2)

        self._sys_edit = QTextEdit()
        self._sys_edit.setPlaceholderText("留空即使用上方默认提示词……")
        self._sys_edit.setPlainText(saved.get("system", ""))
        self._sys_edit.setMinimumHeight(120)
        self._sys_edit.setMaximumHeight(180)
        layout.addWidget(self._sys_edit)

        layout.addSpacing(12)

        # ── User prompt templates ─────────────────────────────────────────
        user_lbl = QLabel("用户提示词模板")
        user_lbl.setObjectName("section")
        layout.addWidget(user_lbl)

        hint3 = QLabel(
            "每个场景/模式组合都有独立的提示词模板。{text} 会被替换为实际输入内容。\n"
            "留空则使用内置默认模板。"
        )
        hint3.setObjectName("hint")
        hint3.setWordWrap(True)
        layout.addWidget(hint3)

        layout.addSpacing(4)

        self._user_edits: dict[tuple, QTextEdit] = {}
        for key, label in _PROMPT_LABELS:
            row_lbl = QLabel(label)
            row_lbl.setStyleSheet("color: #8b949e; font-size: 12px;")
            layout.addWidget(row_lbl)
            edit = QTextEdit()
            edit.setPlaceholderText(DEFAULT_USER_PROMPTS[key])
            cfg_key = f"{key[0]}_{key[1]}"
            edit.setPlainText(saved.get(cfg_key, ""))
            edit.setFixedHeight(56)
            layout.addWidget(edit)
            self._user_edits[key] = edit

        scroll.setWidget(content)
        outer.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(20, 4, 20, 0)
        reset_btn = QPushButton("恢复默认")
        reset_btn.setObjectName("danger")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存")
        save_btn.setObjectName("save")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        outer.addLayout(btn_row)

    def _reset_defaults(self):
        self._sys_edit.setPlainText("")
        for edit in self._user_edits.values():
            edit.setPlainText("")

    def _save(self):
        prompts: dict[str, str] = {}
        sys_text = self._sys_edit.toPlainText().strip()
        if sys_text:
            prompts["system"] = sys_text
        for key, edit in self._user_edits.items():
            text = edit.toPlainText().strip()
            if text:
                prompts[f"{key[0]}_{key[1]}"] = text
        self._config.set("prompts", prompts)
        self._config.save()
        self.accept()


class _ModelFetcher(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, base_url: str, api_key: str, extra_headers: dict, parent=None):
        super().__init__(parent)
        self._base_url = base_url
        self._api_key = api_key
        self._extra_headers = extra_headers

    def run(self):
        try:
            from claude_client import fetch_available_models
            models = fetch_available_models(self._base_url, self._api_key, self._extra_headers)
            self.finished.emit(models)
        except Exception as e:
            self.error.emit(self._classify(e))

    @staticmethod
    def _classify(e: Exception) -> str:
        from openai import (
            AuthenticationError, PermissionDeniedError, NotFoundError,
            APIConnectionError, APITimeoutError,
        )
        if isinstance(e, (AuthenticationError, PermissionDeniedError)):
            return "API Key 无效或无权限，请检查后重试"
        if isinstance(e, NotFoundError):
            return "该服务商未开放模型列表接口，请手动输入模型名称"
        if isinstance(e, APIConnectionError):
            return "网络连接失败，请检查网络或 Base URL 是否正确"
        if isinstance(e, APITimeoutError):
            return "请求超时，请检查网络后重试"
        msg = str(e)
        if "401" in msg:
            return "API Key 无效或未授权（401）"
        if "403" in msg:
            return "无访问权限（403），请确认 Key 是否有效"
        if "404" in msg:
            return "该服务商未开放模型列表接口（404），请手动输入模型名称"
        return f"获取失败：{msg}"


class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._setup_ui()
        self.setStyleSheet(_STYLE)
        self.setWindowTitle(f"{_APP_NAME}  设置  v{VERSION}")
        self.setMinimumWidth(420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        from PyQt5.QtWidgets import QApplication as _QApp
        screen = _QApp.primaryScreen().availableGeometry()
        self.setMaximumHeight(screen.height() - 80)
        self.adjustSize()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 12)

        conn_lbl = QLabel("API 连接")
        conn_lbl.setObjectName("section")
        layout.addWidget(conn_lbl)

        layout.addWidget(QLabel("API Key"))
        self._api_key = QLineEdit(self._config.get("api_key", ""))
        self._api_key.setEchoMode(QLineEdit.Password)
        self._api_key.setPlaceholderText("sk-ant-api03-…  /  AIza…  /  sk-or-…")
        layout.addWidget(self._api_key)

        self._provider_combo = QComboBox()
        for key, info in PROVIDERS.items():
            self._provider_combo.addItem(info["label"], key)
        current_provider = self._config.get("provider", "anthropic")
        idx = self._provider_combo.findData(current_provider)
        if idx >= 0:
            self._provider_combo.setCurrentIndex(idx)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        layout.addWidget(self._provider_combo)

        url_row = QHBoxLayout()
        url_lbl = QLabel("Base URL")
        url_lbl.setFixedWidth(60)
        url_row.addWidget(url_lbl)
        self._base_url_edit = QLineEdit(self._config.get("base_url", "https://api.anthropic.com/v1/"))
        self._base_url_edit.setPlaceholderText("https://api.openai.com/v1")
        url_row.addWidget(self._base_url_edit)
        layout.addLayout(url_row)

        model_fetch_row = QHBoxLayout()
        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        self._model_combo.lineEdit().setPlaceholderText("选择或手动输入模型名称")
        model_fetch_row.addWidget(self._model_combo, 1)
        self._fetch_btn = QPushButton("获取列表")
        self._fetch_btn.clicked.connect(self._fetch_models)
        model_fetch_row.addWidget(self._fetch_btn)
        layout.addLayout(model_fetch_row)

        model_hint = QLabel("无法获取时可直接输入模型名称，如 gpt-4o-mini")
        model_hint.setObjectName("hint")
        layout.addWidget(model_hint)

        self._populate_model_combo(
            self._config.get("provider", "anthropic"),
            self._config.get("model", "claude-haiku-4-5-20251001"),
        )

        layout.addSpacing(4)

        layout.addWidget(QLabel("快捷键（例：ctrl+shift+space）"))
        self._hotkey = QLineEdit(self._config.get("hotkey", "ctrl+shift+space"))
        layout.addWidget(self._hotkey)

        self._startup_cb = QCheckBox("开机自启动")
        self._startup_cb.setChecked(self._config.get("startup_with_windows", False))
        layout.addWidget(self._startup_cb)

        self._companion_cb = QCheckBox("固定面板（快捷键 / ;; 自动呼出固定翻译面板）")
        self._companion_cb.setChecked(self._config.get("companion_enabled", False))
        layout.addWidget(self._companion_cb)

        self._multi_cb = QCheckBox("生成双版本（每次翻译生成两个备选）")
        self._multi_cb.setChecked(self._config.get("multi_version", False))
        layout.addWidget(self._multi_cb)

        self._auto_confirm_cb = QCheckBox("生成后自动替换（非双版本模式下，生成完成立即应用）")
        self._auto_confirm_cb.setChecked(self._config.get("auto_confirm", False))
        layout.addWidget(self._auto_confirm_cb)

        suffix_row = QHBoxLayout()
        self._suffix_cb = QCheckBox("后缀触发（输入后缀后自动翻译）")
        self._suffix_cb.setChecked(self._config.get("suffix_enabled", True))
        suffix_row.addWidget(self._suffix_cb)
        suffix_row.addStretch()
        suffix_row.addWidget(QLabel("后缀字符"))
        self._suffix_chars = QLineEdit(self._config.get("suffix_chars", "··"))
        self._suffix_chars.setFixedWidth(60)
        self._suffix_chars.setMaxLength(4)
        self._suffix_chars.setPlaceholderText("··")
        suffix_row.addWidget(self._suffix_chars)
        layout.addLayout(suffix_row)

        layout.addSpacing(4)

        layout.addWidget(QLabel("英文风格"))
        region_row = QHBoxLayout()
        self._region_btns: dict[str, QPushButton] = {}
        current_region = self._config.get("region", "sg")
        self._selected_region = current_region
        for key, label in (("us", "🇺🇸 美式"), ("uk", "🇬🇧 英式"), ("sg", "🇸🇬 新式")):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(key == current_region)
            btn.clicked.connect(lambda _, k=key: self._select_region(k))
            region_row.addWidget(btn)
            self._region_btns[key] = btn
        layout.addLayout(region_row)

        layout.addWidget(QLabel("个人风格指南（注入到每次翻译的 prompt 中）"))
        self._style_edit = QTextEdit()
        self._style_edit.setPlaceholderText(
            "例：我叫 Leo，偏好简洁直接的表达，不喜欢 \"reach out\" 或 \"utilize\" 等词。"
        )
        self._style_edit.setPlainText(self._config.get("style_guide", ""))
        self._style_edit.setFixedHeight(64)
        layout.addWidget(self._style_edit)

        layout.addWidget(QLabel("词汇偏好（每行一条，格式：旧词 → 新词）"))
        self._vocab_edit = QTextEdit()
        self._vocab_edit.setPlaceholderText("utilize → use\nreach out → contact\nleverage → use")
        self._vocab_edit.setPlainText(self._config.get("vocab_prefs", ""))
        self._vocab_edit.setFixedHeight(64)
        layout.addWidget(self._vocab_edit)

        layout.addSpacing(4)

        # Usage stats
        layout.addWidget(QLabel("API 用量统计"))
        tracker = UsageTracker()
        summary = tracker.monthly_summary()
        if summary:
            for entry in summary:
                tokens_k = (entry["input"] + entry["output"]) / 1000
                cost = entry["cost_usd"]
                lbl = QLabel(
                    f"{entry['month']}：{tokens_k:.1f}K tokens  ≈  ${cost:.3f} USD"
                )
                lbl.setStyleSheet("color: #7d8590; font-size: 12px;")
                layout.addWidget(lbl)
        else:
            lbl = QLabel("暂无记录")
            lbl.setStyleSheet("color: #484f58; font-size: 12px;")
            layout.addWidget(lbl)

        layout.addSpacing(4)

        btn_group = QHBoxLayout()
        prompts_btn = QPushButton("编辑提示词…")
        prompts_btn.clicked.connect(self._open_prompts)
        btn_group.addWidget(prompts_btn)
        window_map_btn = QPushButton("窗口场景映射…")
        window_map_btn.clicked.connect(self._open_window_map)
        btn_group.addWidget(window_map_btn)
        preview_btn = QPushButton("预览最终 Prompt")
        preview_btn.clicked.connect(self._preview_prompt)
        btn_group.addWidget(preview_btn)
        layout.addLayout(btn_group)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(20, 10, 20, 16)
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存")
        save_btn.setObjectName("save")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        outer.addLayout(btn_row)

    def _select_region(self, key: str):
        for k, btn in self._region_btns.items():
            btn.setChecked(k == key)
        self._selected_region = key

    def _on_provider_changed(self, _idx: int):
        key = self._provider_combo.currentData()
        info = PROVIDERS.get(key, {})
        self._base_url_edit.setText(info.get("base_url", ""))
        self._populate_model_combo(key, "")

    def _populate_model_combo(self, provider: str, current_model: str):
        self._model_combo.clear()
        info = PROVIDERS.get(provider, {})
        for m in info.get("models", []):
            self._model_combo.addItem(m)
        if current_model:
            idx = self._model_combo.findText(current_model)
            if idx >= 0:
                self._model_combo.setCurrentIndex(idx)
            else:
                self._model_combo.setEditText(current_model)

    def _fetch_models(self):
        from claude_client import get_provider_headers
        self._fetch_btn.setEnabled(False)
        self._fetch_btn.setText("获取中…")
        provider = self._provider_combo.currentData()
        base_url = self._base_url_edit.text().strip()
        api_key = self._api_key.text().strip() or self._config.get("api_key", "")
        headers = get_provider_headers(provider)
        self._fetcher = _ModelFetcher(base_url, api_key, headers)
        self._fetcher.finished.connect(self._on_models_fetched)
        self._fetcher.error.connect(self._on_fetch_error)
        self._fetcher.start()

    def _on_models_fetched(self, models: list):
        current = self._model_combo.currentText()
        self._model_combo.clear()
        for m in models:
            self._model_combo.addItem(m)
        if current:
            idx = self._model_combo.findText(current)
            if idx >= 0:
                self._model_combo.setCurrentIndex(idx)
            else:
                self._model_combo.setEditText(current)
        self._fetch_btn.setEnabled(True)
        self._fetch_btn.setText("获取模型列表")

    def _on_fetch_error(self, msg: str):
        QMessageBox.warning(self, "获取模型列表失败", msg)
        self._fetch_btn.setEnabled(True)
        self._fetch_btn.setText("获取列表")

    def _preview_prompt(self):
        custom_sys = self._config.get("prompts", {}).get("system", "").strip() or None
        preview = build_system_prompt(
            custom_sys,
            region=self._selected_region,
            style_guide=self._style_edit.toPlainText(),
            vocab_prefs=self._vocab_edit.toPlainText(),
        )
        dlg = QDialog(self)
        dlg.setWindowTitle("最终 System Prompt 预览")
        dlg.setMinimumWidth(520)
        dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        dlg.setStyleSheet(_STYLE)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(16, 16, 16, 12)
        hint = QLabel("以下是每次翻译实际发送给模型的 System Prompt（含风格指南和词汇偏好）：")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        v.addWidget(hint)
        v.addSpacing(6)
        box = QTextEdit()
        box.setReadOnly(True)
        box.setPlainText(preview)
        box.setMinimumHeight(300)
        v.addWidget(box)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dlg.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close_btn)
        v.addLayout(row)
        dlg.exec_()

    def _open_prompts(self):
        dlg = PromptsDialog(self._config, self)
        dlg.exec_()

    def _open_window_map(self):
        dlg = WindowMapDialog(self._config, self)
        dlg.exec_()

    def _save(self):
        api_key = self._api_key.text().strip()
        hotkey = self._hotkey.text().strip()
        if not hotkey:
            QMessageBox.warning(self, "错误", "快捷键不能为空")
            return
        modifiers = {"ctrl", "alt", "shift", "win"}
        parts = {p.strip().lower() for p in hotkey.split("+")}
        if not parts.intersection(modifiers):
            QMessageBox.warning(self, "错误", "快捷键必须包含修饰键（Ctrl/Alt/Shift/Win）")
            return

        self._config.set("api_key", api_key)
        self._config.set("hotkey", hotkey)
        self._config.set("startup_with_windows", self._startup_cb.isChecked())
        self._config.set("companion_enabled", self._companion_cb.isChecked())
        self._config.set("multi_version", self._multi_cb.isChecked())
        self._config.set("auto_confirm", self._auto_confirm_cb.isChecked())
        self._config.set("suffix_enabled", self._suffix_cb.isChecked())
        suffix_chars = self._suffix_chars.text().strip() or "··"
        self._config.set("suffix_chars", suffix_chars)
        self._config.set("region", self._selected_region)
        self._config.set("provider", self._provider_combo.currentData())
        self._config.set("base_url", self._base_url_edit.text().strip())
        self._config.set("model", self._model_combo.currentText().strip())
        self._config.set("style_guide", self._style_edit.toPlainText().strip())
        self._config.set("vocab_prefs", self._vocab_edit.toPlainText().strip())
        self._config.save()
        startup = self._config.get("startup_with_windows")

        try:
            exe_path = str(Path(sys.executable).resolve())
            _set_startup_registry(startup, exe_path)
        except Exception as e:
            QMessageBox.warning(
                self, "注册表写入失败",
                f"无法设置开机自启动：{e}\n其他设置已保存。"
            )

        self.accept()
