import re

_CJK = re.compile(r"[぀-鿿가-힯豈-﫿]")


def detect_mode(text: str) -> str:
    """Return 'translate' if text contains any CJK character, else 'optimize'."""
    return "translate" if _CJK.search(text) else "optimize"
