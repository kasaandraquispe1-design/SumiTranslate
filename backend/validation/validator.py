"""Validate that protected content survived translation unchanged."""

from __future__ import annotations

import re
from backend.protection.math_protector import ProtectedElement

LEFTOVER_MARKER_RE = re.compile(r"\[\[(?:MATH|CODE|URL|CITE)_\d+\]\]")


def validate(
    original_text: str,
    restored_text: str,
    store: dict[str, ProtectedElement],
) -> dict:
    """Check protected originals and leftover markers.

    ``original_text`` is kept in the signature for parity with the Base44
    implementation and future structural checks.
    """
    del original_text
    issues = []
    checked = 0

    for marker, info in store.items():
        checked += 1
        if info.original not in restored_text:
            issues.append(
                {
                    "marker": marker,
                    "type": info.type,
                    "missing": info.original,
                }
            )

    leftover = LEFTOVER_MARKER_RE.findall(restored_text)
    if leftover:
        issues.append(
            {
                "type": "leftover_marker",
                "count": len(leftover),
                "samples": leftover[:5],
            }
        )

    return {
        "passed": not issues,
        "checked": checked,
        "issues": issues,
    }
