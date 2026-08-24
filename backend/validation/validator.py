"""Strict validation for translated documents.

Validation is fail-closed for the things Sumire explicitly protects, but it
must not re-run the protector over the translated natural language. Doing that
can create false failures because a translation may legitimately introduce a
new number, symbol, Greek letter, etc. The source protection store is the
canonical contract: every protected item must survive exactly and in order.
"""

from __future__ import annotations

import re

from backend.protection.math_protector import ProtectedElement

MARKER_RE = re.compile(r"\[\[([A-Z]+)_([0-9]+)\]\]")


def _marker_sequence(text: str) -> list[str]:
    return [match.group(0) for match in MARKER_RE.finditer(text)]


def _protected_sequence(store: dict[str, ProtectedElement]) -> list[tuple[str, str]]:
    return [(item.type, item.original) for item in store.values()]


def _find_protected_items_in_order(
    restored_text: str,
    store: dict[str, ProtectedElement],
) -> list[dict]:
    """Check exact protected source spans without re-protecting translated text."""
    issues: list[dict] = []
    cursor = 0

    for marker, item in store.items():
        original = str(item.original)
        if not original:
            continue

        position = restored_text.find(original, cursor)
        if position < 0:
            issues.append({
                "type": "protected_content_missing",
                "marker": marker,
                "kind": item.type,
                "missing": original,
            })
            # Do not move the cursor when the item is missing. A later identical
            # value can still be checked independently and reported correctly.
            continue

        cursor = position + len(original)

    return issues


def validate_markers(protected_source: str, translated_protected: str) -> dict:
    """Validate the LLM output while Sumire's structural markers are visible."""
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
    """Validate that all source-protected elements survive exactly and in order.

    Important: do NOT call ``protect_text(restored_text)`` here. The translated
    natural language is allowed to contain characters that the protector would
    classify as protected. Re-protecting it was causing valid PDF segments to
    be rejected (for example when a translation introduced a number or symbol).
    """
    issues: list[dict] = []
    expected_elements = _protected_sequence(store)
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

    # The restored document must contain every protected source span exactly.
    # Searching in sequence also catches reordering when duplicated values occur.
    issues.extend(_find_protected_items_in_order(restored_text, store))

    # A marker from Sumire's namespace must never reach the final document.
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
