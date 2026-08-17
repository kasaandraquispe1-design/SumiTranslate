"""Deterministic protection of non-linguistic document content.

The translator must only see natural language. This module protects content
that must survive translation byte-for-byte: mathematics, numbers, table
structure, code, URLs and citations. Protected spans are replaced with stable
markers and restored from the original source after translation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MARKER_PREFIX = "[["
MARKER_SUFFIX = "]]"

MATH_OP = "∇∂∫∑∏√→←↔⇒⇔≤≥≠≈±×÷∈∉∀∃∪∩⊂⊃⊆⊇⊕⊗∝≡∼≅⋆·∙∘"
GREEK = "αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"
SUPER = "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽ⁿⁱ"
SUB = "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₔₕₖₗₘₙₚₛₜ"


@dataclass(frozen=True)
class ProtectedElement:
    marker: str
    type: str
    original: str


def _patterns() -> list[tuple[str, re.Pattern[str]]]:
    """Patterns are ordered from largest/most specific to smallest tokens."""
    op = re.escape(MATH_OP)
    greek = re.escape(GREEK)
    sup = re.escape(SUPER)
    sub = re.escape(SUB)
    return [
        # Code must be protected before inline math/numbers inside it.
        ("code", re.compile(r"```[\\s\\S]*?```")),
        ("code", re.compile(r"`[^`\\n]+`")),

        # LaTeX / TeX display and inline math.
        ("math", re.compile(r"\\$\\$[\\s\\S]+?\\$\\$|\\\\\[[\\s\\S]+?\\\\\]")),
        ("math", re.compile(r"\\\\\([\\s\\S]+?\\\\\)|\\$[^$\\n]+?\\$")),
        ("math", re.compile(r"\\\\[a-zA-Z]+\\*?(?:\\{[^{}]*\\}){0,3}")),

        # URLs and common DOI forms.
        ("url", re.compile(r"https?://[^\\s)\\]}>]+")),
        ("url", re.compile(r"(?:ftp://|www\\.)[^\\s)\\]}>]+", re.I)),
        ("cite", re.compile(r"(?:doi:|https?://doi\\.org/)?10\\.\\d{4,9}/[-._;()/:A-Z0-9]+", re.I)),

        # Citation commands and citation-like bracket forms.
        ("cite", re.compile(r"\\\\(?:cite|citet|citep|parencite|textcite|autocite|ref|eqref|pageref|label)\\{[^{}]*\\}")),
        ("cite", re.compile(r"\\[@[^\\]]+\\]")),
        ("cite", re.compile(r"\\[\\d+(?:\\s*,\\s*\\d+)*\\]")),

        # Mathematical norms / absolute values before protecting their numbers.
        ("math", re.compile(r"\\|\\|[^|\\n]+\\|\\|")),
        ("math", re.compile(r"(?<!\\w)\\|[^|\\n]+\\|(?!\\w)")),

        # Numbers: integers, decimals, percentages, signs, scientific notation,
        # dates and simple numeric ranges. This intentionally protects numbers
        # even when they appear in otherwise translatable prose.
        ("number", re.compile(
            r"(?<![A-Za-z0-9_])[-+]?\\d+(?:[.,]\\d+)?(?:[eE][-+]?\\d+)?%?(?:[-/]\\d+(?:[.,]\\d+)?)*"
        )),
        ("number", re.compile(
            r"(?<![A-Za-z0-9_])(?:\\d{1,3}(?:[.,]\\d{3})+)(?![A-Za-z0-9_])"
        )),

        # Numbers with units, including superscript units.
        ("number", re.compile(
            r"(?<![A-Za-z0-9_])[-+]?\\d+(?:[.,]\\d+)?\\s?(?:rad|m/s(?:²)?|kg|cm|mm|km|Hz|MHz|GHz|kW|MW|J|N|Pa|V|A|Ω|mol|lx|dB|°C|°F|K|s|ms|µs|ns|min|h|eV|nm|pm|ppm)\\b"
        )),

        # Variables with explicit superscripts/subscripts.
        ("math", re.compile(r"[A-Za-z][A-Za-z]?\\s*[\\^_]\\s*\\{?[A-Za-z0-9]+\\}?")),
        ("math", re.compile(rf"[A-Za-z0-9]+[{sup}]+")),
        ("math", re.compile(rf"[A-Za-z0-9]+[{sub}]+")),
        ("math", re.compile(rf"[{greek}]+")),
        ("math", re.compile(rf"[{op}][A-Za-z0-9²³⁰¹⁴⁵⁶⁷⁸⁹]*")),
        ("math", re.compile(rf"[{op}]")),
    ]


def _table_matches(text: str) -> list[tuple[int, int, str, str]]:
    """Protect Markdown/pipe table structure without protecting cell prose."""
    matches: list[tuple[int, int, str, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\\r\\n")
        # A Markdown table row normally contains at least two pipe separators.
        if body.count("|") >= 2:
            for match in re.finditer(r"\\|", body):
                matches.append((offset + match.start(), offset + match.end(), "|", "table"))
            # Separator rows contain only pipes, spaces, colons and hyphens.
            if re.fullmatch(r"\\s*\\|?[\\s:|-]+\\|?\\s*", body) and "-" in body:
                for match in re.finditer(r"-+", body):
                    matches.append((offset + match.start(), offset + match.end(), match.group(0), "table"))
        offset += len(line)
    return matches


def _overlaps(used: bytearray, start: int, end: int) -> bool:
    return any(used[start:end])


def protect_text(text: str) -> tuple[str, dict[str, ProtectedElement], int]:
    """Return protected text, marker store, and number of protected spans."""
    if not text:
        return "", {}, 0

    used = bytearray(len(text))
    matches: list[tuple[int, int, str, str]] = []

    # Specific patterns first. A span can only be protected once.
    for kind, pattern in _patterns():
        for match in pattern.finditer(text):
            start, end = match.span()
            if start == end or _overlaps(used, start, end):
                continue
            matches.append((start, end, match.group(0), kind))
            used[start:end] = b"\\x01" * (end - start)

    # Table structure is scanned separately so that cell language remains
    # translatable while pipes/separator syntax remains deterministic.
    for start, end, original, kind in _table_matches(text):
        if start == end or _overlaps(used, start, end):
            continue
        matches.append((start, end, original, kind))
        used[start:end] = b"\\x01" * (end - start)

    matches.sort(key=lambda item: (item[0], item[1]))
    store: dict[str, ProtectedElement] = {}
    output: list[str] = []
    cursor = 0

    for index, (start, end, original, kind) in enumerate(matches, start=1):
        marker = f"{MARKER_PREFIX}{kind.upper()}_{index:03d}{MARKER_SUFFIX}"
        output.append(text[cursor:start])
        output.append(marker)
        store[marker] = ProtectedElement(marker=marker, type=kind, original=original)
        cursor = end

    output.append(text[cursor:])
    return "".join(output), store, len(store)


def restore_markers(text: str, store: dict[str, ProtectedElement]) -> str:
    """Restore protected spans exactly as they appeared in the source."""
    result = text
    for marker in sorted(store, key=len, reverse=True):
        result = result.replace(marker, store[marker].original)
    return result


def list_markers(store: dict[str, ProtectedElement]) -> list[dict[str, str]]:
    return [
        {"marker": item.marker, "type": item.type, "original": item.original}
        for item in store.values()
    ]


class MathProtector:
    """Compatibility wrapper for the original root ``MathProtector`` API."""

    def __init__(self) -> None:
        self.store: dict[str, ProtectedElement] = {}

    def protect(self, text: str) -> str:
        protected, self.store, _ = protect_text(text)
        return protected

    def restore(self, text: str) -> str:
        return restore_markers(text, self.store)
