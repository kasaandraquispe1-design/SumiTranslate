"""Deterministic word counting for Sumire Translate.

The public statistics describe semantic protected elements, not every character
used internally to preserve a table. A 3x2 table therefore appears as one table
with dimensions 3x2 instead of ``table: 11`` because of its pipes and separators.
"""

from __future__ import annotations

import re
from collections import Counter

from backend.protection.math_protector import protect_text

WORD_RE = re.compile(r"(?u)[^\W_]+(?:[-'’][^\W_]+)*")
MARKER_RE = re.compile(r"\[\[[A-Z]+_\d+\]\]")
SEPARATOR_RE = re.compile(
    r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)+\|?\s*$"
)


def _count_words(text: str) -> int:
    return len(WORD_RE.findall(text))


def _split_pipe_row(line: str) -> list[str]:
    """Split one Markdown-style table row into cells."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [cell.strip() for cell in body.split("|")]


def _detect_pipe_tables(text: str) -> list[dict[str, int]]:
    """Detect contiguous Markdown/pipe tables and return their dimensions."""
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
            line = lines[i]
            if not SEPARATOR_RE.match(line):
                cells = _split_pipe_row(line)
                if cells and any(cell for cell in cells):
                    max_cols = max(max_cols, len(cells))
                    rows += 1
            i += 1

        # At least two real rows and two columns avoids false positives.
        if i > start and rows >= 2 and max_cols >= 2:
            tables.append({"rows": rows, "columns": max_cols})

    return tables


def count_words(text: str) -> dict:
    """Return word statistics plus semantic table statistics.

    Internal table delimiter markers are collapsed into one logical table per
    detected table, so the UI never reports values such as ``table: 11`` for a
    small 3x2 table. Validation still uses the original marker store elsewhere.
    """
    total = _count_words(text)
    protected_text, store, raw_protected_count = protect_text(text)
    stripped = MARKER_RE.sub(" ", protected_text)
    translatable = _count_words(stripped)

    by_type = Counter(item.type for item in store.values())
    raw_table_markers = by_type.get("table", 0)
    tables = _detect_pipe_tables(text)

    if tables:
        logical_table_count = len(tables)
    elif raw_table_markers:
        # PDF extraction can flatten a visual table and remove pipe characters.
        # If table structure was still detected, report one logical table.
        logical_table_count = 1
    else:
        logical_table_count = 0

    if logical_table_count:
        by_type["table"] = logical_table_count
    else:
        by_type.pop("table", None)

    # User-facing protected count is semantic. The internal marker count is not
    # exposed because a table's pipes/separator dashes are not separate content.
    semantic_protected = raw_protected_count - raw_table_markers + logical_table_count
    protected_word_count = max(total - translatable, 0)
    ratio = protected_word_count / total if total else 0.0

    return {
        "total": total,
        "translatable": translatable,
        "protected": semantic_protected,
        "protectedWords": protected_word_count,
        "protectedRatio": ratio,
        "protectedByType": dict(sorted(by_type.items())),
        "tables": tables,
        "tableCount": logical_table_count,
    }
