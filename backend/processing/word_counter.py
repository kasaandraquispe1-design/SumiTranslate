"""Deterministic word counting for translation and billing.

Only natural-language tokens left after protection are billable/translated.
Numbers, formulas, code, URLs, citations and table structure are excluded
from translatable words. Tables are reported as structures, not as one
protected element for every ``|`` or separator dash.
"""

from __future__ import annotations

import re
from collections import Counter

from backend.protection.math_protector import protect_text

WORD_RE = re.compile(r"(?u)[^\W_]+(?:[-'’][^\W_]+)*")
MARKER_RE = re.compile(r"\[\[[A-Z]+_\d+\]\]")
SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)+\|?\s*$")


def _count_words(text: str) -> int:
    return len(WORD_RE.findall(text))


def _detect_pipe_tables(text: str) -> list[dict[str, int]]:
    """Conservatively detect contiguous pipe/Markdown tables and dimensions."""
    lines = text.splitlines()
    tables: list[dict[str, int]] = []
    i = 0
    while i < len(lines):
        if lines[i].count("|") < 2:
            i += 1
            continue

        start = i
        rows = 0
        max_cols = 0
        while i < len(lines) and lines[i].count("|") >= 2:
            current = lines[i]
            if not SEPARATOR_RE.match(current):
                parts = current.strip().strip("|").split("|")
                max_cols = max(max_cols, len(parts))
                rows += 1
            i += 1

        if i > start and rows > 0:
            tables.append({"rows": rows, "columns": max_cols})

    return tables


def count_words(text: str) -> dict:
    """Return word statistics and accurate table-structure statistics.

    ``protected`` keeps the internal marker count used by validation. The
    user-facing ``protectedByType.table`` is the number of detected tables,
    so a 3x2 table is not misleadingly reported as ``table: 20`` merely
    because its delimiters were protected individually.
    """
    total = _count_words(text)
    protected_text, store, protected_count = protect_text(text)
    stripped = MARKER_RE.sub(" ", protected_text)
    translatable = _count_words(stripped)

    by_type = Counter(item.type for item in store.values())
    tables = _detect_pipe_tables(text)
    if tables:
        by_type["table"] = len(tables)

    protected_word_count = max(total - translatable, 0)
    ratio = protected_word_count / total if total else 0.0

    return {
        "total": total,
        "translatable": translatable,
        "protected": protected_count,
        "protectedWords": protected_word_count,
        "protectedRatio": ratio,
        "protectedByType": dict(sorted(by_type.items())),
        "tables": tables,
        "tableCount": len(tables),
    }
