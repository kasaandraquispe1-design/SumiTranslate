"""Strict validation for translated documents.

Validation is deliberately fail-closed: missing, duplicated, reordered or
leftover protection markers are considered unsafe, as are restored protected
spans that no longer match the source exactly.
"""

from __future__ import annotations

import re
from collections import Counter

from backend.protection.math_protector import ProtectedElement

MARKER_RE = re.compile(r"\[\[([A-Z]+)_([0-9]+)\]\]")


def _marker_sequence(text: str) -> list[str]:
    return [match.group(0) for match in MARKER_RE.finditer(text)]


def validate_markers(protected_source: str, translated_protected: str) -> dict:
    """Validate the LLM output while markers are still visible."""
    expected = _marker_sequence(protected_source)
    actual = _marker_sequence(translated_protected)
    issues: list[dict] = []

    if actual != expected:
        issues.append({
            "type": "marker_sequence_changed",
            "expected": expected,
            "actual": actual,
        })

    expected_counts = Counter(expected)
    actual_counts = Counter(actual)
    if expected_counts != actual_counts:
        issues.append({
            "type": "marker_count_changed",
            "expected": dict(expected_counts),
            "actual": dict(actual_counts),
        })

    return {
        "passed": not issues,
        "expectedMarkers": len(expected),
        "actualMarkers": len(actual),
        "issues": issues,
    }


def validate(
    original_text: str,
    restored_text: str,
    store: dict[str, ProtectedElement],
    *,
    protected_source: str | None = None,
    translated_protected: str | None = None,
) -> dict:
    """Check protected originals, marker integrity and restoration.

    ``protected_source`` and ``translated_protected`` should be supplied when
    available so marker order/count can be checked before restoration.
    """
    issues: list[dict] = []
    checked = len(store)

    if protected_source is not None and translated_protected is not None:
        marker_validation = validate_markers(protected_source, translated_protected)
        issues.extend(marker_validation["issues"])
    else:
        marker_validation = {"passed": True, "expectedMarkers": checked, "actualMarkers": None, "issues": []}

    # Every protected source span must occur exactly once in the restored text.
    for marker, info in store.items():
        occurrences = restored_text.count(info.original)
        if occurrences != 1:
            issues.append({
                "marker": marker,
                "type": info.type,
                "expectedOccurrences": 1,
                "actualOccurrences": occurrences,
                "missing": info.original if occurrences == 0 else None,
            })

    # A marker from our namespace must never reach the final document.
    leftover = MARKER_RE.findall(restored_text)
    if leftover:
        issues.append({
            "type": "leftover_marker",
            "count": len(leftover),
            "samples": [f"[[{kind}_{number}]]" for kind, number in leftover[:5]],
        })

    # The final output must not be empty when the source was non-empty.
    if original_text.strip() and not restored_text.strip():
        issues.append({"type": "empty_translation"})

    return {
        "passed": not issues,
        "checked": checked,
        "markerValidation": marker_validation,
        "issues": issues,
    }
