"""Document format adapters for Sumire Translate.

The PDF fitting hook below is intentionally isolated here so the working
DOCX/TXT/image pipeline is not rewritten.
"""

from __future__ import annotations

import re

from . import document_pipeline as _dp

_ACTIVE_TRANSLATE_FN = None
_ACTIVE_TARGET_LANGUAGE = ""


def _pdf_font_name(flags: int) -> str:
    bold, italic = bool(flags & 16), bool(flags & 2)
    if bold and italic:
        return "figbi"
    if bold:
        return "figbo"
    if italic:
        return "figit"
    return "figo"


def _pdf_color(value: int):
    return ((value >> 16 & 255) / 255, (value >> 8 & 255) / 255, (value & 255) / 255)


def _try_fit(page, rect, text, block, sizes):
    for size in sizes:
        try:
            rc = page.insert_textbox(
                rect,
                text,
                fontname=_pdf_font_name(block.flags),
                fontsize=max(4.0, float(size)),
                color=_pdf_color(block.color),
                overlay=True,
            )
        except Exception:
            rc = -1
        if rc >= 0:
            return float(size)
    return None


def _safe_rect(rect, max_bottom=None):
    import pymupdf
    base = pymupdf.Rect(rect)
    bottom = base.y1
    if max_bottom is not None:
        bottom = min(float(max_bottom), base.y1 + max(8.0, base.height * 0.85))
    return pymupdf.Rect(base.x0, base.y0, base.x1, max(base.y1, bottom))


def _shorten_preserving_protected(text: str) -> str | None:
    """Rewrite the complete phrase more concisely without touching protected markers."""
    if not _ACTIVE_TRANSLATE_FN or not text.strip():
        return None
    try:
        protected, store, _ = _dp.protect_text(text)
        prompt = f"""You are editing an already translated academic/scientific document.
The target language is {_ACTIVE_TARGET_LANGUAGE or 'the current target language'}.

Rewrite the COMPLETE phrase below so it is shorter while keeping the exact
meaning and all important information. Prefer a concise synonym, shorter
equivalent expression, or natural idiom when appropriate. Never sacrifice
technical or mathematical meaning.

IMPORTANT:
- Preserve every protected marker exactly.
- Never translate, edit, reorder, remove or add markers.
- Output ONLY the shortened phrase.

{protected}"""
        result = _ACTIVE_TRANSLATE_FN(prompt)
        if not isinstance(result, str):
            result = str(result)
        marker_re = re.compile(r"\[\[[A-Z]+_\d{3}\]\]")
        if marker_re.findall(result) != marker_re.findall(protected):
            return None
        shortened = _dp.restore_markers(result.strip(), store)
        if not shortened or shortened.strip() == text.strip():
            return None
        return shortened.strip()
    except Exception:
        return None


def _patched_insert_pdf_text_fitted(page, rect, text, block, *, max_bottom=None):
    """PDF only: five fit attempts, then a shorter whole-phrase fallback."""
    import pymupdf

    base = pymupdf.Rect(rect)
    expanded = _safe_rect(base, max_bottom=max_bottom)
    start = max(5.5, min(float(block.fontsize), 24.0))

    # 1-5: keep the translation exactly as produced and reduce its font size.
    first_sizes = [start, start * 0.90, start * 0.80, start * 0.70, start * 0.60]
    candidates = (base, expanded) if expanded != base else (base,)
    for candidate in candidates:
        if _try_fit(page, candidate, text, block, first_sizes) is not None:
            return

    # If the literal translation still does not fit, shorten the COMPLETE
    # phrase. Protected mathematics, numbers, URLs, citations, etc. are
    # protected again before this auxiliary Gemini call.
    shortened = _shorten_preserving_protected(text)
    if shortened:
        second_sizes = [start * 0.60, start * 0.55, start * 0.50, start * 0.45, start * 0.40]
        for candidate in candidates:
            if _try_fit(page, candidate, shortened, block, second_sizes) is not None:
                return

    # Last controlled fallback: PyMuPDF can scale HTML content to the box.
    # It is used only after the requested five attempts + whole-phrase retry.
    try:
        css = f"font-size:{max(4.0, start * 0.40):.2f}pt; color:rgb({(block.color >> 16) & 255},{(block.color >> 8) & 255},{block.color & 255});"
        candidate_text = shortened or text
        spare, scale = page.insert_htmlbox(expanded, candidate_text, css=css, scale_low=0.35, overlay=True)
        if spare >= 0 and scale > 0:
            return
    except Exception:
        pass

    raise RuntimeError("La reconstrucción PDF fue bloqueada: el texto traducido no cabe después de cinco intentos y una reformulación más corta.")


_original_translate_pdf_document = _dp.translate_pdf_document


def _patched_translate_pdf_document(path, source_lang, target_lang, translate_fn, *, batch_size=18):
    global _ACTIVE_TRANSLATE_FN, _ACTIVE_TARGET_LANGUAGE
    previous_fn = _ACTIVE_TRANSLATE_FN
    previous_target = _ACTIVE_TARGET_LANGUAGE
    _ACTIVE_TRANSLATE_FN = translate_fn
    try:
        try:
            from backend.core.languages import language_name
            _ACTIVE_TARGET_LANGUAGE = language_name(target_lang)
        except Exception:
            _ACTIVE_TARGET_LANGUAGE = str(target_lang)
        return _original_translate_pdf_document(path, source_lang, target_lang, translate_fn, batch_size=batch_size)
    finally:
        _ACTIVE_TRANSLATE_FN = previous_fn
        _ACTIVE_TARGET_LANGUAGE = previous_target


_dp._insert_pdf_text_fitted = _patched_insert_pdf_text_fitted
_dp.translate_pdf_document = _patched_translate_pdf_document

translate_pdf_document = _dp.translate_pdf_document
