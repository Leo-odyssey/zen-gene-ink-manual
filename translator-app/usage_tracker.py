import json
import os
from datetime import date
from pathlib import Path

_USAGE_FILE = Path(os.environ.get("APPDATA", "~")) / "TranslatorApp" / "usage.json"

_COST_PER_TOKEN: dict[str, dict] = {
    "claude-haiku-4-5-20251001": {"input": 0.80e-6,  "output": 4.00e-6},
    "claude-sonnet-4-6":        {"input": 3.00e-6,  "output": 15.00e-6},
    "claude-opus-4-7":          {"input": 15.00e-6, "output": 75.00e-6},
    # OpenAI
    "gpt-4o":                   {"input": 2.50e-6,  "output": 10.00e-6},
    "gpt-4o-mini":              {"input": 0.15e-6,  "output": 0.60e-6},
    "gpt-4-turbo":              {"input": 10.00e-6, "output": 30.00e-6},
    # DeepSeek
    "deepseek-chat":            {"input": 0.27e-6,  "output": 1.10e-6},
    "deepseek-reasoner":        {"input": 0.55e-6,  "output": 2.19e-6},
}


class UsageTracker:
    def __init__(self):
        self._data: dict = {}
        if _USAGE_FILE.exists():
            try:
                self._data = json.loads(_USAGE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass

    def record(self, model: str, input_tokens: int, output_tokens: int):
        month = date.today().strftime("%Y-%m")
        bucket = self._data.setdefault(month, {}).setdefault(
            model, {"input": 0, "output": 0}
        )
        bucket["input"] += input_tokens
        bucket["output"] += output_tokens
        _USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _USAGE_FILE.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def monthly_summary(self) -> list[dict]:
        """Return up to 2 months newest-first: [{month, input, output, cost_usd}]."""
        months = sorted(self._data.keys(), reverse=True)[:2]
        result = []
        for month in months:
            inp = out = 0
            cost = 0.0
            for model, counts in self._data[month].items():
                i = counts.get("input", 0)
                o = counts.get("output", 0)
                inp += i
                out += o
                rates = _COST_PER_TOKEN.get(model)
                if rates:
                    cost += i * rates["input"] + o * rates["output"]
            result.append({"month": month, "input": inp, "output": out, "cost_usd": cost})
        return result
