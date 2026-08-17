"""Core Sumire translation pipeline.

Protect -> count -> translate -> validate markers -> restore -> validate final.
The LLM never receives original protected content.
"""

from __future__ import annotations

from collections.abc import Callable

from backend.core.languages import language_name
from backend.protection.math_protector import list_markers, protect_text, restore_markers
from backend.processing.word_counter import count_words
from backend.validation.validator import validate, validate_markers

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
2. Every marker such as [[MATH_001]], [[NUMBER_002]], [[TABLE_003]], [[CODE_004]], [[URL_005]], [[CITE_006]] MUST be copied exactly.
3. Markers are structural tokens. The complete marker sequence MUST remain identical: no marker may be removed, duplicated, renamed or reordered.
4. Never modify protected numbers, mathematical notation, formulas, code, URLs, citations or table delimiters.
5. Do NOT add notes, explanations, prefaces, or commentary. Output ONLY the translated text.
6. Preserve line breaks and paragraph boundaries whenever possible.
7. Translate the natural-language text between markers, but never translate marker text itself.

Protected markers present in the text:
{marker_doc}

TEXT TO TRANSLATE:
<<<SUMIRE_TEXT>>>
{protected_text}
<<<END_SUMIRE_TEXT>>>

Output ONLY the translated text, nothing else."""


def run_pipeline(
    *,
    text: str,
    source_lang: str,
    target_lang: str,
    translate_fn: TranslateFn,
) -> dict:
    """Protect -> count -> translate -> validate -> restore -> validate."""
    protected_text, store, protected_count = protect_text(text)
    counts = count_words(text)
    marker_list = list_markers(store)
    prompt = build_translator_prompt(source_lang, target_lang, protected_text, marker_list)
    llm_result = translate_fn(prompt)

    # Fail closed before restoration. If the model changed marker structure,
    # restoring could silently produce an incomplete or duplicated document.
    marker_validation = validate_markers(protected_text, llm_result)
    if not marker_validation["passed"]:
        return {
            "translated": None,
            "counts": counts,
            "protectedCount": protected_count,
            "protectedElements": marker_list,
            "validation": {
                "passed": False,
                "checked": protected_count,
                "markerValidation": marker_validation,
                "issues": marker_validation["issues"],
            },
            "error": "Translation blocked: protected markers were modified.",
        }

    restored = restore_markers(llm_result, store)
    validation = validate(
        text,
        restored,
        store,
        protected_source=protected_text,
        translated_protected=llm_result,
    )

    return {
        "translated": restored if validation["passed"] else None,
        "counts": counts,
        "protectedCount": protected_count,
        "protectedElements": marker_list,
        "validation": validation,
    }
