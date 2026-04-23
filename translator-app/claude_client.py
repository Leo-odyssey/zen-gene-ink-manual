import threading
from openai import (
    OpenAI, AuthenticationError, RateLimitError,
    APIConnectionError, APITimeoutError, BadRequestError,
)
from PyQt5.QtCore import QThread, pyqtSignal

# ── Provider registry ────────────────────────────────────────────────────────
PROVIDERS: dict[str, dict] = {
    "anthropic": {
        "label": "Anthropic",
        "base_url": "https://api.anthropic.com/v1/",
        "models": [
            "claude-haiku-4-5-20251001",
            "claude-sonnet-4-6",
            "claude-opus-4-7",
        ],
        "fetch_models": False,
        "headers": {"anthropic-version": "2023-06-01"},
    },
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "fetch_models": True,
        "headers": {},
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "fetch_models": True,
        "headers": {},
    },
    "gemini": {
        "label": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "models": [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ],
        "fetch_models": True,
        "headers": {},
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "fetch_models": True,
        "headers": {},
    },
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "fetch_models": True,
        "headers": {},
    },
    "ollama": {
        "label": "Ollama（本地）",
        "base_url": "http://localhost:11434/v1",
        "fetch_models": True,
        "headers": {},
        "default_key": "ollama",
    },
    "custom": {
        "label": "自定义",
        "base_url": "",
        "fetch_models": True,
        "headers": {},
    },
}


def get_provider_headers(provider: str) -> dict:
    return PROVIDERS.get(provider, {}).get("headers", {})


def fetch_available_models(base_url: str, api_key: str, extra_headers: dict | None = None) -> list[str]:
    """Fetch model list from provider's /v1/models endpoint. Raises RuntimeError on failure."""
    client = OpenAI(
        base_url=base_url,
        api_key=api_key or "none",
        default_headers=extra_headers or {},
        timeout=15.0,
    )
    models = client.models.list()
    return sorted([m.id for m in models.data])


# ── Prompt building ──────────────────────────────────────────────────────────

_REGION_ADDENDUM = {
    "us": (
        "Use American English spelling and idioms "
        "(e.g. color, gotten, reach out, touch base)."
    ),
    "uk": (
        "Use British English spelling and idioms "
        "(e.g. colour, have got, cheers, get back to you)."
    ),
    "sg": (
        "Use Singapore English. In casual and spoken contexts you may occasionally use "
        "Singlish particles (lah, leh, liao, le, lor, can, right?) where they feel "
        "natural — at most once or twice per message, never forced. "
        "In professional/email contexts use standard formal English only."
    ),
}

SYSTEM_PROMPT = (
    "You are a native English speaker who writes naturally in different contexts.\n\n"
    "In spoken mode: write naturally for everyday conversation — clear, warm, and "
    "friendly. Use contractions and everyday words. No heavy internet slang or "
    "abbreviations, but not stiff or formal either. Sound like a real person talking.\n\n"
    "In casual mode: write like texting a close friend — use everyday contractions, "
    "informal expressions, and common internet shorthand where it fits naturally "
    "(e.g. lol, lmk, omw, ngl, tbh, imo). Never sound stiff or robotic.\n\n"
    "In professional mode: write clear, polished business English "
    "— friendly but formal, using common everyday words. Avoid "
    "jargon, overly complex vocabulary, or stiff phrases like "
    '"please do not hesitate to contact me."\n\n'
    "Rules for all responses:\n"
    "- Return only the final text, no explanations, no quotes\n"
    "- Preserve the original meaning\n"
    "- Fix all spelling and grammar errors"
)

DEFAULT_USER_PROMPTS: dict[tuple[str, str], str] = {
    ("optimize", "spoken"): "Spoken mode. Improve this English for a natural conversation:\n{text}",
    ("optimize", "casual"): "Casual mode. Improve this English for a chat message:\n{text}",
    ("optimize", "email"):  "Professional mode. Improve this English for a business email:\n{text}",
    ("translate", "spoken"): "Spoken mode. Translate to English for a natural conversation:\n{text}",
    ("translate", "casual"): "Casual mode. Translate to English for a chat message:\n{text}",
    ("translate", "email"):  "Professional mode. Translate to English for a business email:\n{text}",
}



def build_system_prompt(
    base: str | None = None,
    region: str = "sg",
    style_guide: str = "",
    vocab_prefs: str = "",
) -> str:
    parts = [base or SYSTEM_PROMPT]
    addendum = _REGION_ADDENDUM.get(region, "")
    if addendum:
        parts.append(addendum)
    if style_guide.strip():
        parts.append(f"Personal style guide: {style_guide.strip()}")
    if vocab_prefs.strip():
        pairs = []
        for line in vocab_prefs.strip().splitlines():
            if "→" in line:
                a, _, b = line.partition("→")
                if a.strip() and b.strip():
                    pairs.append(f'prefer "{b.strip()}" over "{a.strip()}"')
        if pairs:
            parts.append("Vocabulary preferences: " + "; ".join(pairs) + ".")
    return "\n\n".join(parts)


def build_prompt(
    text: str,
    mode: str,
    scene: str,
    user_prompts: dict[tuple[str, str], str] | None = None,
) -> str:
    templates = user_prompts if user_prompts else DEFAULT_USER_PROMPTS
    template = templates.get((mode, scene))
    if template is None:
        raise ValueError(f"Unknown mode/scene combination: {mode!r}/{scene!r}")
    return template.format(text=text)


# ── Worker ───────────────────────────────────────────────────────────────────

class ClaudeWorker(QThread):
    token_received = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    usage = pyqtSignal(str, int, int)  # model_id, input_tokens, output_tokens

    def __init__(
        self,
        api_key: str,
        text: str,
        mode: str,
        scene: str,
        system_prompt: str | None = None,
        user_prompts: dict[tuple[str, str], str] | None = None,
        model: str = "claude-haiku-4-5-20251001",
        base_url: str = "https://api.anthropic.com/v1/",
        extra_headers: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._api_key = api_key
        self._text = text
        self._mode = mode
        self._scene = scene
        self._system_prompt = system_prompt or SYSTEM_PROMPT
        self._user_prompts = user_prompts
        self._model = model
        self._base_url = base_url
        self._extra_headers = extra_headers or {}
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def run(self):
        try:
            client = OpenAI(
                api_key=self._api_key or "none",
                base_url=self._base_url,
                default_headers=self._extra_headers,
                timeout=30.0,
            )
            prompt = build_prompt(
                self._text, self._mode, self._scene,
                self._user_prompts,
            )
            result = ""
            inp_tokens = out_tokens = 0
            stream = client.chat.completions.create(
                model=self._model,
                max_tokens=min(1500, max(600, len(self._text) * 4)),
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": prompt},
                ],
                stream=True,
                stream_options={"include_usage": True},
            )
            for chunk in stream:
                if self._cancel_event.is_set():
                    self.finished.emit(result)
                    return
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    result += token
                    self.token_received.emit(token)
                if hasattr(chunk, "usage") and chunk.usage:
                    inp_tokens = chunk.usage.prompt_tokens or 0
                    out_tokens = chunk.usage.completion_tokens or 0
            self.usage.emit(self._model, inp_tokens, out_tokens)
            self.finished.emit(result)
        except AuthenticationError:
            self.error.emit("API Key 无效，请在设置中更新")
        except RateLimitError:
            self.error.emit("请求过于频繁，请稍后重试")
        except APIConnectionError:
            self.error.emit("网络连接失败，请检查网络后重试")
        except APITimeoutError:
            self.error.emit("请求超时，请重试")
        except BadRequestError as e:
            self.error.emit(f"请求内容有误：{e}")
        except Exception as e:
            self.error.emit(f"请求失败：{e}")


def load_custom_prompts(config):
    """Return (system_prompt, user_prompts) from config, or (None, None) if default."""
    raw = config.get("prompts", {})
    if not raw:
        return None, None
    system_prompt = raw.get("system", "").strip() or None
    user_prompts = {}
    for key in DEFAULT_USER_PROMPTS:
        cfg_key = f"{key[0]}_{key[1]}"
        val = raw.get(cfg_key, "").strip()
        user_prompts[key] = val if val else DEFAULT_USER_PROMPTS[key]
    return system_prompt, user_prompts if any(
        raw.get(f"{k[0]}_{k[1]}", "") for k in DEFAULT_USER_PROMPTS
    ) else None
