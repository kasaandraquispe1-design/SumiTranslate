"""Validation gate for translated text."""

from __future__ import annotations

import re
from collections import Counter

from backend.protection.math_protector import ProtectedElement

LEFTOVER_MARKER_RE = re.compile(r"\[\[(?:MATH|CODE|URL|CITE|NUMBER)_\d+\]\]")
NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w.])")


def validate(original_text: str, restored_text: str, store: dict[str, ProtectedElement]) -> dict:
    """Block delivery when protected content or numeric invariants changed."""
    issues: list[dict] = []

    for marker, info in store.items():
        count_source = original_text.count(info.original)
        count_result = restored_text.count(info.original)
        if count_result < count_source:
            issues.append({
                "marker": marker,
                "type": info.type,
                "missing": info.original,
                "expected_occurrences": count_source,
                "found_occurrences": count_result,
            })

    leftovers = LEFTOVER_MARKER_RE.findall(restored_text)
    if leftovers:
        issues.append({"type": "leftover_marker", "count": len(leftovers), "samples": leftovers[:5]})

    # Numeric content is an important invariant for academic/scientific text.
    source_numbers = Counter(NUMBER_RE.findall(original_text))
    result_numbers = Counter(NUMBER_RE.findall(restored_text))
    if source_numbers != result_numbers:
        missing = list((source_numbers - result_numbers).elements())
        added = list((result_numbers - source_numbers).elements())
        issues.append({
            "type": "numbers_changed",
            "missing": missing[:20],
            "added": added[:20],
        })

    return {"passed": not issues, "checked": len(store), "issues": issues}
