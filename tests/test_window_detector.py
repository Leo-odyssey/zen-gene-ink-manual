# tests/test_window_detector.py
import sys
sys.path.insert(0, "translator-app")
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


def test_longer_keyword_wins_over_shorter_substring():
    # "outlook" (7 chars) should win over "mail" (4 chars) when both match
    scene_map = {"mail": "email", "outlook": "email"}
    assert infer_scene("Outlook Mail Window", scene_map) == "email"
