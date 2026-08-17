"""Core Sumire translation pipeline migrated from Base44."""

from __future__ import annotations

from collections.abc import Callable

from backend.core.languages import language_name
from backend.protection.math_protector import list_markers, protect_text, restore_markers
from backend.processing.word_counter import count_words
from backend.validation.validator import validate

TranslateFn = Callable[[str], str]


def build_translator_prompt(
    source_lang: str,
    target_lang: str,
    protected_text: str,
    marker_list: list[dict[str, str]],
) -> str:
    marker_doc = (
        "\n".join(f"{item['marker']} (tipo: {item['type']})" for item in marker_list)
        if marker_list
        else "(ninguno)"
    )
    return f"""You are a professional academic and scientific translator. Translate the following text from {language_name(source_lang)} to {language_name(target_lang)}.

STRICT RULES:
1. Translate ONLY natural language. Do NOT translate, rephrase, reorder, or explain any protected marker.
2. Protected markers such as [[MATH_001]], [[CODE_002]], [[URL_003]], [[CITE_004]] MUST appear exactly as in the input.
3. Do NOT modify numbers, variables, symbols, formulas, LaTeX, code, URLs, citations, or table structure.
4. Do NOT add notes, explanations, prefaces, or commentary. Output ONLY the translated text.
5. Preserve line breaks, paragraph breaks, and structural layout characters exactly whenever possible.
6. Segment delimiters such as {{SEG0}}, {{SEG1}}, {{SEG2}} are structural separators. Keep them exactly and in order.

Protected markers present in the text:
{marker_doc}

TEXT TO TRANSLATE:
"""
{protected_text}
"""

Output ONLY the translated text, nothing else."""


def run_pipeline(
    *,
    text: str,
    source_lang: str,
    target_lang: str,
    translate_fn: TranslateFn,
) -> dict:
    """Protect -> count -> translate -> restore -> validate."""
    protected_text, store, protected_count = protect_text(text)
    counts = count_words(text)
    prompt = build_translator_prompt(
        source_lang,
        target_lang,
        protected_text,
        [{"marker": item["marker"], "type": item["type"]} for item in list_markers(store)],
    )
    llm_result = translate_fn(prompt)
    restored = restore_markers(llm_result, store)
    validation = validate(text, restored, store)

    return {
        "translated": restored,
        "counts": counts,
        "protectedCount": protected_count,
        "protectedElements": list_markers(store),
        "validation": validation,
    }
