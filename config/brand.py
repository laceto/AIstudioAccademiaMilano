import json
import re
from functools import lru_cache
from pathlib import Path

BRAND_PATH = Path(__file__).parent / "brand.json"


@lru_cache(maxsize=1)
def brand() -> dict:
    if not BRAND_PATH.exists():
        raise RuntimeError(
            f"config/brand.json not found at {BRAND_PATH}. "
            "Copy config/brand.json.example and fill in your values."
        )
    return json.loads(BRAND_PATH.read_text(encoding="utf-8"))


def b(key: str) -> str:
    """Dot-path accessor: b('studio.name') -> 'AI Studio Accademia Milano'"""
    parts = key.split(".")
    node = brand()
    for p in parts:
        node = node[p]
    return node


def fmt(template: str) -> str:
    """Resolve {studio.name}-style placeholders in a string."""
    return re.sub(r"\{([\w.]+)\}", lambda m: b(m.group(1)), template)
