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


import os
import anthropic
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QCoreApplication
from claude_client import ClaudeWorker


def _get_app():
    app = QCoreApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_worker_emits_tokens_and_finished(mocker):
    _get_app()
    mock_stream = mocker.MagicMock()
    mock_stream.__enter__ = mocker.MagicMock(return_value=mock_stream)
    mock_stream.__exit__ = mocker.MagicMock(return_value=False)
    mock_stream.text_stream = iter(["Hello", " world"])

    mocker.patch("claude_client.anthropic.Anthropic", return_value=mocker.MagicMock(
        messages=mocker.MagicMock(stream=mocker.MagicMock(return_value=mock_stream))
    ))

    tokens = []
    finished_results = []
    worker = ClaudeWorker("fake-key", "test", "optimize", "casual")
    worker.token_received.connect(tokens.append)
    worker.finished.connect(finished_results.append)
    worker.run()

    assert tokens == ["Hello", " world"]
    assert finished_results == ["Hello world"]


def test_worker_emits_error_on_auth_failure(mocker):
    _get_app()
    import httpx
    mock_response = mocker.MagicMock(spec=httpx.Response)
    mock_response.status_code = 401
    mock_response.headers = {}
    mocker.patch(
        "claude_client.anthropic.Anthropic",
        side_effect=anthropic.AuthenticationError(
            message="invalid key", response=mock_response, body={}
        ),
    )
    errors = []
    worker = ClaudeWorker("bad-key", "test", "optimize", "casual")
    worker.error.connect(errors.append)
    worker.run()
    assert len(errors) == 1
    assert "API Key" in errors[0]


def test_worker_cancel_emits_finished_with_partial(mocker):
    _get_app()

    def token_gen():
        yield "Hello"
        yield " world"

    mock_stream = mocker.MagicMock()
    mock_stream.__enter__ = mocker.MagicMock(return_value=mock_stream)
    mock_stream.__exit__ = mocker.MagicMock(return_value=False)
    mock_stream.text_stream = token_gen()

    mocker.patch("claude_client.anthropic.Anthropic", return_value=mocker.MagicMock(
        messages=mocker.MagicMock(stream=mocker.MagicMock(return_value=mock_stream))
    ))

    finished_results = []
    worker = ClaudeWorker("fake-key", "test", "optimize", "casual")
    worker.finished.connect(finished_results.append)
    worker.cancel()  # cancel before run
    worker.run()

    # Should emit finished with empty string (cancelled before any tokens)
    assert finished_results == [""]


def test_build_prompt_raises_on_invalid_combination():
    import pytest
    with pytest.raises(ValueError, match="Unknown mode/scene"):
        build_prompt("text", "invalid_mode", "casual")
