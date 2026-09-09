"""Deterministic protection of source code before LLM translation.

Explicit code fences and inline-code are always protected. Unlabeled source code
is detected conservatively from strong language/syntax signals and indentation.
Protected spans are restored exactly by the common protection store.
"""

from __future__ import annotations

import re


_LANGUAGE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Python
    re.compile(r"^\s*(?:def|class)\s+[A-Za-z_]\w*\s*\("),
    re.compile(r"^\s*(?:import\s+[A-Za-z_]\w*|from\s+[A-Za-z_]\w*\s+import\s+)"),
    re.compile(r"^\s*if\s+__name__\s*==\s*[\"']__main__[\"']\s*:"),
    # MATLAB / Octave
    re.compile(r"^\s*function(?:\s+\w+\s*=)?\s*\w+\s*\("),
    re.compile(r"^\s*(?:fprintf|disp|zeros|ones|linspace|subplot|figure|hold\s+on)\s*\("),
    # R
    re.compile(r"^\s*(?:library|require)\s*\("),
    # Julia
    re.compile(r"^\s*function\s+\w+\s*(?:\([^)]*\))?\s*$"),
    # C / C++ / Java / JavaScript / TypeScript / C#
    re.compile(r"^\s*(?:public|private|protected|static|const|let|var|class|interface|namespace)\b.*[{}]"),
    re.compile(r"^\s*(?:#include\s*[<\"]|using\s+namespace\s+|std::)"),
    # Shell
    re.compile(r"^\s*#!\s*/(?:usr/bin/env\s+)?(?:bash|sh|zsh|fish)\b"),
    re.compile(r"^\s*(?:echo|printf|export|source|chmod|mkdir|grep|awk|sed)\s+.+"),
    # SQL
    re.compile(r"^\s*(?:SELECT|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|CREATE\s+(?:TABLE|VIEW)|ALTER\s+TABLE)\b", re.I),
    # Fortran
    re.compile(r"^\s*(?:PROGRAM|SUBROUTINE|FUNCTION|MODULE|DO\s+\w+\s*=)\b", re.I),
    # Wolfram / Mathematica and Maple
    re.compile(r"^\s*(?:Integrate|Solve|DSolve|Plot|NIntegrate)\s*\["),
    re.compile(r"^\s*(?:solve|dsolve|int|plot)\s*\([^)]*\)\s*;?$", re.I),
)

_STRONG_SYNTAX = re.compile(
    r"(?:\b(?:def|class|return|import|from|lambda|elif|yield|async|await)\b|"
    r"\b(?:function|end|elseif|fprintf|disp|zeros|ones|linspace|plot)\b|"
    r"\b(?:SELECT|FROM|WHERE|JOIN|GROUP\s+BY|ORDER\s+BY)\b|"
    r"(?:\+=|-=|\*=|/=|==|!=|<=|>=|&&|\|\||->|::|\*\*)|"
    r"[{};]\s*$)",
    re.I,
)
_ASSIGNMENT = re.compile(r"^\s*[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s*=\s*.+")
_BLOCK_START = re.compile(
    r"(?:^|\s)(?:def|class|function|if|for|while|try|switch|namespace)\b.*(?:[:{]|$)",
    re.I,
)


def _line_offsets(text: str) -> list[tuple[int, int, str]]:
    lines: list[tuple[int, int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        lines.append((offset, offset + len(body), body))
        offset += len(line)
    if text and offset < len(text):
        lines.append((offset, len(text), text[offset:]))
    return lines


def _indent(line: str) -> int:
    expanded = line.expandtabs(4)
    return len(expanded) - len(expanded.lstrip(" "))


def _looks_like_code_line(line: str) -> bool:
    if not line.strip():
        return False
    if any(pattern.search(line) for pattern in _LANGUAGE_PATTERNS):
        return True
    if _ASSIGNMENT.match(line) and ("(" in line or ";" in line or "[" in line or "**" in line):
        return True
    return bool(_STRONG_SYNTAX.search(line))


def _language_hint(line: str) -> bool:
    return any(pattern.search(line) for pattern in _LANGUAGE_PATTERNS)


def _consume_indented_block(lines: list[tuple[int, int, str]], i: int, base_indent: int) -> int:
    """Consume a Python-like indented body, including indented comments."""
    j = i + 1
    saw_body = False
    while j < len(lines):
        line = lines[j][2]
        if not line.strip():
            if saw_body and j + 1 < len(lines):
                j += 1
                continue
            break
        if _indent(line) > base_indent:
            saw_body = True
            j += 1
            continue
        break
    return j


def _consume_end_block(lines: list[tuple[int, int, str]], i: int) -> int:
    """Consume MATLAB/Octave/Fortran-like blocks through their closing end."""
    j = i + 1
    while j < len(lines):
        stripped = lines[j][2].strip().lower()
        if stripped in {"end", "endfunction", "endsubroutine", "endprogram", "endmodule"}:
            return j + 1
        j += 1
    return j


def find_code_spans(text: str) -> list[tuple[int, int, str]]:
    """Return (start, end, kind) spans that should be protected as code."""
    if not text:
        return []

    spans: list[tuple[int, int, str]] = []

    # Explicit Markdown fences are definitive, including unknown languages.
    for match in re.finditer(r"```[\s\S]*?```", text):
        spans.append((match.start(), match.end(), "code"))

    # Inline code is definitive too.
    for match in re.finditer(r"`[^`\n]+`", text):
        spans.append((match.start(), match.end(), "code"))

    lines = _line_offsets(text)
    i = 0
    while i < len(lines):
        start, end, line = lines[i]
        if not _looks_like_code_line(line):
            i += 1
            continue

        base_indent = _indent(line)
        explicit = _language_hint(line)
        block_start = _BLOCK_START.search(line) is not None
        is_python_style = bool(re.search(r"\b(?:def|class|if|for|while|try)\b.*:\s*$", line, re.I))
        is_end_style = explicit and bool(re.search(r"^\s*function\b", line, re.I))

        if is_python_style:
            j = _consume_indented_block(lines, i, base_indent)
        elif is_end_style:
            j = _consume_end_block(lines, i)
        else:
            j = i + 1
            code_like = 1
            while j < len(lines):
                next_line = lines[j][2]
                if not next_line.strip():
                    if j + 1 < len(lines) and (_looks_like_code_line(lines[j + 1][2]) or _indent(lines[j + 1][2]) > base_indent):
                        j += 1
                        continue
                    break
                if _indent(next_line) > base_indent or _looks_like_code_line(next_line):
                    code_like += 1
                    j += 1
                    continue
                break
            if code_like < 2 and not explicit and not block_start:
                i += 1
                continue

        block_end = lines[j - 1][1] if j > i else end
        block = text[start:block_end]
        has_structure = bool(re.search(r"[{};]|\b(?:return|end|elseif|else)\b", block, re.I))

        if explicit or block_start or is_python_style or is_end_style or has_structure or j > i + 1:
            spans.append((start, block_end, "code"))
            i = j
        else:
            i += 1

    # Merge nested/overlapping spans so a code block is restored as one unit.
    spans.sort(key=lambda item: (item[0], -item[1]))
    merged: list[tuple[int, int, str]] = []
    for start, end, kind in spans:
        if not merged or start > merged[-1][1]:
            merged.append((start, end, kind))
        elif end > merged[-1][1]:
            merged[-1] = (merged[-1][0], end, "code")
    return merged


class CodeProtector:
    """Public helper for code detection."""

    def detect(self, text: str) -> list[str]:
        return [text[start:end] for start, end, _ in find_code_spans(text)]
