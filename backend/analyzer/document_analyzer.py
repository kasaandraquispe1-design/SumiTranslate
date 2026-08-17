"""Deterministic analysis equivalent to Base44's analyzeDocument function."""

from __future__ import annotations

from backend.protection.math_protector import list_markers, protect_text
from backend.processing.word_counter import count_words

PRICE_PER_WORD_PEN = 0.05
MAX_TEXT_LENGTH = 200_000


def analyze_text(text: str) -> dict:
    """Count words and expose protected elements without an LLM call."""
    if not text.strip():
        raise ValueError("Texto vacío")
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError("Documento demasiado grande")

    counts = count_words(text)
    _, store, protected_count = protect_text(text)
    elements = list_markers(store)
    cost = round(counts["translatable"] * PRICE_PER_WORD_PEN, 2)

    return {
        "counts": counts,
        "protectedCount": protected_count,
        "protectedElements": elements,
        "cost": cost,
    }
