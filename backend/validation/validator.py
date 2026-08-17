"""Strict validation for translated documents.

Validation is fail-closed: missing, duplicated or reordered markers and any
change to deterministic protected spans block delivery.
"""

from __future__ import annotations

import re

from backend.protection.math_protector import ProtectedElement, protect_text

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
    """Check marker integrity and exact restoration of protected spans.

    The restored text is re-protected and compared as an ordered sequence of
    ``(type, original)`` pairs. This avoids false failures when the same source
    value occurs more than once, such as the number ``10`` appearing twice.
    """
    issues: list[dict] = []
    expected_elements = [(item.type, item.original) for item in store.values()]
    checked = len(expected_elements)

    if protected_source is not None and translated_protected is not None:
        marker_validation = validate_markers(protected_source, translated_protected)
        issues.extend(marker_validation["issues"])
    else:
        marker_validation = {
            "passed": True,
            "expectedMarkers": checked,
            "actualMarkers": None,
            "issues": [],
        }

    # Re-running the deterministic protector is the strongest final check:
    # every protected element must be identical and remain in the same order.
    _, restored_store, _ = protect_text(restored_text)
    actual_elements = [(item.type, item.original) for item in restored_store.values()]
    if actual_elements != expected_elements:
        issues.append({
            "type": "protected_content_changed",
            "expected": expected_elements,
            "actual": actual_elements,
        })

    # A marker from our namespace must never reach the final document.
    leftover = _marker_sequence(restored_text)
    if leftover:
        issues.append({
            "type": "leftover_marker",
            "count": len(leftover),
            "samples": leftover[:5],
        })

    if original_text.strip() and not restored_text.strip():
        issues.append({"type": "empty_translation"})

    return {
        "passed": not issues,
        "checked": checked,
        "markerValidation": marker_validation,
        "issues": issues,
    }
