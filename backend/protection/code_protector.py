"""Deterministic protection of source code before LLM translation.

The detector is intentionally conservative: explicit code fences/inline-code are
always protected, while unlabeled code is protected only when several strong
syntax signals indicate that a span is actually source code.
"""

from __future__ import annotations

import re


# Languages commonly encountered in scientific/technical documents.
_LANGUAGE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Python
    re.compile(r"^\s*(?:def|class)\s+[A-Za-z_]\w*\s*\("),
    re.compile(r"^\s*(?:import\s+[A-Za-z_]\w*|from\s+[A-Za-z_]\w*\s+import\s+)"),
    re.compile(r"^\s*if\s+__name__\s*==\s*[\"']__main__[\"']\s*:"),
    # MATLAB / Octave
    re.compile(r"^\s*function(?:\s+\w+\s*=)?\s*\w+\s*\("),
    re.compile(r"^\s*(?:for|while|if|switch|try)\b.*(?:;)?$"),
    # R / Julia
    re.compile(r"^\s*(?:library|require)\s*\("),
    re.compile(r"^\s*function\s+\w+\s*(?:\([^)]*\))?\s*$"),
    # C / C++ / Java / JavaScript / TypeScript / C#
    re.compile(r"^\s*(?:public|private|protected|static|const|let|var|class|interface|namespace)\b.*[{}]"),
    re.compile(r"^\s*(?:#include\s*[<\"]|using\s+namespace\s+|std::)"),
    # Shell
    re.compile(r"^\s*#!\s*/(?:usr/bin/env\s+)?(?:bash|sh|zsh|fish)\b"),
    re.compile(r"^\s*(?:echo|printf|export|source|chmod|mkdir|cd|grep|awk|sed)\s+.+"),
    # SQL
    re.compile(r"^\s*(?:SELECT|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|CREATE\s+(?:TABLE|VIEW)|ALTER\s+TABLE)\b", re.I),
    # Fortran
    re.compile(r"^\s*(?:PROGRAM|SUBROUTINE|FUNCTION|MODULE|DO\s+\w+\s*=)\b", re.I),
    # Wolfram / Mathematica and Maple
    re.compile(r"^\s*(?:Integrate|Solve|DSolve|Plot|NIntegrate)\s*\["),
    re.compile(r"^\s*(?:solve|dsolve|int|plot)\s*\([^)]*\)\s*;?$", re.I),
)

# Strong line-level signals. These are used together, not individually, for
# unlabeled blocks so normal mathematical prose is not accidentally protected.
_STRONG_SYNTAX = re.compile(
    r"(?:\b(?:def|class|return|import|from|lambda|elif|yield|async|await)\b|"
    r"\b(?:function|end|elseif|fprintf|disp|zeros|ones|linspace|plot)\b|"
    r"\b(?:SELECT|FROM|WHERE|JOIN|GROUP\s+BY|ORDER\s+BY)\b|"
    r"(?:\+=|-=|\*=|/=|==|!=|<=|>=|&&|\|\||->|::|\*\*|\$\$)|"
    r"[{};]$|\{\s*$|\}\s*$)",
    re.I,
)

_ASSIGNMENT = re.compile(r"^\s*[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s*=\s*.+")


def _line_offsets(text: str) -> list[tuple[int, int, str]]:
    lines: list[tuple[int, int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        lines.append((offset, offset + len(body), body))
        offset += len(line)
    if text and (not lines or offset < len(text)):
        lines.append((offset, len(text), text[offset:]))
    return lines


def _looks_like_code_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if any(pattern.search(line) for pattern in _LANGUAGE_PATTERNS):
        return True
    if _ASSIGNMENT.match(line) and ("(" in line or ";" in line or "[" in line or "**" in line):
        return True
    return bool(_STRONG_SYNTAX.search(line))


def find_code_spans(text: str) -> list[tuple[int, int, str]]:
    """Return (start, end, kind) spans that should be protected as code."""
    if not text:
        return []

    spans: list[tuple[int, int, str]] = []

    # Explicit Markdown fences are definitive, including unknown languages.
    for match in re.finditer(r"```[\s\S]*?```", text):
        spans.append((match.start(), match.end(), "code"))

    # Inline code is also definitive.
    for match in re.finditer(r"`[^`\n]+`", text):
        spans.append((match.start(), match.end(), "code"))

    lines = _line_offsets(text)
    i = 0
    while i < len(lines):
        start, end, line = lines[i]
        if not _looks_like_code_line(line):
            i += 1
            continue

        # A single isolated assignment can be ordinary mathematics/prose.
        # Require a second code-like line, or a block-opening/closing pattern.
        j = i + 1
        code_like = 1
        while j < len(lines):
            _, _, next_line = lines[j]
            if not next_line.strip():
                # Allow one blank line inside a code block.
                if j + 1 < len(lines) and _looks_like_code_line(lines[j + 1][2]):
                    j += 1
                    continue
                break
            if _looks_like_code_line(next_line):
                code_like += 1
                j += 1
                continue
            # Natural-language continuation ends the candidate block.
            break

        block_end = lines[j - 1][1] if j > i else end
        block = text[start:block_end]
        has_explicit_language = any(pattern.search(line) for pattern in _LANGUAGE_PATTERNS)
        has_structure = bool(re.search(r"[{};]|\b(?:return|end)\b", block, re.I))

        if has_explicit_language or code_like >= 2 or has_structure:
            spans.append((start, block_end, "code"))
            i = j
        else:
            i += 1

    # Merge nested/adjacent code spans so restoration is exact.
    spans.sort(key=lambda item: (item[0], -item[1]))
    merged: list[tuple[int, int, str]] = []
    for start, end, kind in spans:
        if not merged or start > merged[-1][1]:
            merged.append((start, end, kind))
        elif end > merged[-1][1]:
            merged[-1] = (merged[-1][0], end, "code")
    return merged


class CodeProtector:
    """Public helper for code protection and exact restoration."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def detect(self, text: str) -> list[str]:
        return [text[start:end] for start, end, _ in find_code_spans(text)]
