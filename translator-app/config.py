import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("APPDATA", "~")) / "TranslatorApp"
CONFIG_FILE = CONFIG_DIR / "config.json"

_SCHEMA_VERSION = 3

_OLD_MODEL_MAP = {
    "haiku":  "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
}

_DEFAULTS = {
    "_schema_version": _SCHEMA_VERSION,
    "api_key": "",
    "hotkey": "ctrl+shift+space",
    "suffix_enabled": True,
    "suffix_chars": "··",
    "default_scene": "spoken",
    "window_scene_map": {
        "outlook": "email",
        "mail": "email",
        "whatsapp": "casual",
    },
    "startup_with_windows": False,
    "companion_enabled": False,
    "region": "sg",
    "provider": "anthropic",
    "base_url": "https://api.anthropic.com/v1/",
    "model": "claude-haiku-4-5-20251001",
    "style_guide": "",
    "vocab_prefs": "",
    "multi_version": False,
    "explain_changes": False,
    "prompts": {},
    "panel_position": None,
    "panel_collapsed": False,
}


class Config:
    def __init__(self):
        self._data = dict(_DEFAULTS)
        if CONFIG_FILE.exists():
            try:
                loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                self._migrate(loaded)
                self._data.update(loaded)
            except (json.JSONDecodeError, OSError):
                pass

    def _migrate(self, data: dict) -> None:
        version = data.get("_schema_version", 0)
        if version < 1:
            data["_schema_version"] = 1
            data.setdefault("panel_position", None)
            data.setdefault("panel_collapsed", False)
        if version < 2:
            data["_schema_version"] = 2
            data.setdefault("suffix_chars", "··")
        if version < 3:
            data["_schema_version"] = 3
            data.setdefault("provider", "anthropic")
            data.setdefault("base_url", "https://api.anthropic.com/v1/")
            # migrate old shorthand model names to full IDs
            old = data.get("model", "haiku")
            data["model"] = _OLD_MODEL_MAP.get(old, old)

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
