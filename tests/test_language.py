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
