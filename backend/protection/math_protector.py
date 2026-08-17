"""Deterministic protection of non-linguistic content before translation.

The LLM receives markers instead of formulas, code, URLs, citations and
numeric/math tokens. Restoration always puts the exact original text back.
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
    op, greek, sup, sub = map(re.escape, (MATH_OP, GREEK, SUPER, SUB))
    return [
        ("code", re.compile(r"```[\s\S]*?```")),
        ("code", re.compile(r"`[^`\n]+`")),
        ("math", re.compile(r"\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]")),
        ("math", re.compile(r"\\\([\s\S]+?\\\)|\$[^$\n]+?\$")),
        ("math", re.compile(r"\\[a-zA-Z]+\*?(?:\{[^{}]*\}){0,2}")),
        ("url", re.compile(r"https?://[^\s)]+")),
        ("cite", re.compile(r"\\(?:cite|ref|eqref|label)\{[^{}]*\}|\[\d+(?:\s*,\s*\d+)*\]")),
        # Protect norms, but never a single | used as a table delimiter.
        ("math", re.compile(r"\|\|[^|\n]+\|\|")),
        ("math", re.compile(r"\d+(?:[.,]\d+)?\s?(?:rad|m/s²|m/s|kg|cm|mm|km|Hz|MHz|GHz|kW|MW|J|N|Pa|V|A|Ω|mol|lx|dB|°C|°F|K|s|ms|µs|ns|min|h|eV|nm|pm|ppm)\b")),
        ("math", re.compile(r"[A-Za-z][A-Za-z]?\s*[\^_]\s*\{?[A-Za-z0-9]+\}?")),
        ("math", re.compile(rf"[A-Za-z0-9]+[{sup}]+")),
        ("math", re.compile(rf"[A-Za-z0-9]+[{sub}]+")),
        ("math", re.compile(rf"[{greek}]+")),
        ("math", re.compile(rf"[{op}][A-Za-z0-9²³⁰¹⁴⁵⁶⁷⁸⁹]*")),
        # Protect comparison expressions without consuming Markdown table pipes.
        ("math", re.compile(r"(?<!\w)[A-Za-z](?:\([^\n()]{1,80}\))?\s*(?:[<>]=?|=|≤|≥|≠)\s*(?:[A-Za-z0-9α-ωΑ-Ω]+(?:\^[A-Za-z0-9]+)?|[0-9]+(?:\.[0-9]+)?)(?!\w)")),
        ("math", re.compile(rf"[{op}]")),
        # Numbers are protected independently so constants and years cannot change.
        ("number", re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w.])")),
    ]


def protect_text(text: str) -> tuple[str, dict[str, ProtectedElement], int]:
    if not text:
        return "", {}, 0
    used = bytearray(len(text))
    matches: list[tuple[int, int, str, str]] = []
    for kind, pattern in _patterns():
        for match in pattern.finditer(text):
            start, end = match.span()
            if any(used[start:end]):
                continue
            matches.append((start, end, match.group(0), kind))
            used[start:end] = b"\x01" * (end - start)
    matches.sort(key=lambda item: item[0])
    store: dict[str, ProtectedElement] = {}
    output: list[str] = []
    cursor = 0
    for index, (start, end, original, kind) in enumerate(matches, start=1):
        marker = f"{MARKER_PREFIX}{kind.upper()}_{index:03d}{MARKER_SUFFIX}"
        output.extend((text[cursor:start], marker))
        store[marker] = ProtectedElement(marker=marker, type=kind, original=original)
        cursor = end
    output.append(text[cursor:])
    return "".join(output), store, len(store)


def restore_markers(text: str, store: dict[str, ProtectedElement]) -> str:
    result = text
    for marker in sorted(store, key=len, reverse=True):
        result = result.replace(marker, store[marker].original)
    return result


def list_markers(store: dict[str, ProtectedElement]) -> list[dict[str, str]]:
    return [{"marker": x.marker, "type": x.type, "original": x.original} for x in store.values()]


class MathProtector:
    def __init__(self) -> None:
        self.store: dict[str, ProtectedElement] = {}

    def protect(self, text: str) -> str:
        protected, self.store, _ = protect_text(text)
        return protected

    def restore(self, text: str) -> str:
        return restore_markers(text, self.store)
