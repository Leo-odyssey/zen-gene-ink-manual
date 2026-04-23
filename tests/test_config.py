# tests/test_config.py
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "translator-app")
import config as _cfg_module


def test_defaults_when_no_file(tmp_path):
    with patch.object(_cfg_module, "CONFIG_DIR", tmp_path), \
         patch.object(_cfg_module, "CONFIG_FILE", tmp_path / "config.json"):
        c = _cfg_module.Config()
    assert c.get("hotkey") == "ctrl+shift+space"
    assert c.get("api_key") == ""
    assert c.get("startup_with_windows") is False
    assert c.get("window_scene_map") == {
        "outlook": "email", "mail": "email", "whatsapp": "casual"
    }


def test_save_and_reload(tmp_path):
    config_file = tmp_path / "config.json"
    with patch.object(_cfg_module, "CONFIG_DIR", tmp_path), \
         patch.object(_cfg_module, "CONFIG_FILE", config_file):
        c = _cfg_module.Config()
        c.set("api_key", "sk-ant-test")
        c.save()
        c2 = _cfg_module.Config()
    assert c2.get("api_key") == "sk-ant-test"


def test_get_missing_key_returns_none(tmp_path):
    with patch.object(_cfg_module, "CONFIG_DIR", tmp_path), \
         patch.object(_cfg_module, "CONFIG_FILE", tmp_path / "config.json"):
        c = _cfg_module.Config()
    assert c.get("nonexistent") is None
