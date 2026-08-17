"""Deterministic word counting for translation and billing.

Only natural-language tokens left after protection are billable/translated.
Numbers, formulas, code, URLs, citations and table structure are excluded from
``translatable`` even when they contain letters or digits.
"""

from __future__ import annotations

import re
from collections import Counter

from backend.protection.math_protector import protect_text

# Python's stdlib ``re`` has no ``\\p{L}``; this expression is Unicode-aware
# because ``[^\\W_]`` matches Unicode letters/numbers while excluding ``_``.
WORD_RE = re.compile(r"(?u)[^\W_]+(?:[-'’][^\W_]+)*")
MARKER_RE = re.compile(r"\[\[[A-Z]+_\d+\]\]")


def _count_words(text: str) -> int:
    return len(WORD_RE.findall(text))


def count_words(text: str) -> dict[str, float | int | dict[str, int]]:
    """Return total, translatable and protected word statistics."""
    total = _count_words(text)
    protected_text, store, protected_count = protect_text(text)
    stripped = MARKER_RE.sub(" ", protected_text)
    translatable = _count_words(stripped)

    by_type = Counter(item.type for item in store.values())
    protected_word_count = max(total - translatable, 0)
    ratio = protected_word_count / total if total else 0.0

    return {
        "total": total,
        "translatable": translatable,
        "protected": protected_count,
        "protectedWords": protected_word_count,
        "protectedRatio": ratio,
        "protectedByType": dict(sorted(by_type.items())),
    }
