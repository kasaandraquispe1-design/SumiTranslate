"""Word counting migrated from Base44's shared/wordCounter.ts."""

from __future__ import annotations

import re

from backend.protection.math_protector import MARKER_PREFIX, MARKER_SUFFIX, protect_text

WORD_RE = re.compile(r"[\w\d]+(?:[-'’][\w\d]+)*", re.UNICODE)
MARKER_RE = re.compile(r"\[\[[A-Z]+_\d+\]\]")


def _count_words(text: str) -> int:
    return len(WORD_RE.findall(text))


def count_words(text: str) -> dict[str, float | int]:
    total = _count_words(text)
    protected_text, _, protected_count = protect_text(text)
    stripped = MARKER_RE.sub(" ", protected_text)
    translatable = _count_words(stripped)
    ratio = protected_count / total if total else 0.0
    return {
        "total": total,
        "translatable": translatable,
        "protected": protected_count,
        "protectedRatio": ratio,
    }
