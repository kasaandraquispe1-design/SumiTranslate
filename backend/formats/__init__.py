"""Document format adapters for Sumire Translate.

PDF-only diagnostic override. DOCX/TXT paths are intentionally untouched.
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
            rc = page.insert_textbox(rect, text, fontname=_pdf_font_name(block.flags),
                                     fontsize=max(4.0, float(size)), color=_pdf_color(block.color), overlay=True)
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
    if not _ACTIVE_TRANSLATE_FN or not text.strip():
        return None
    try:
        protected, store, _ = _dp.protect_text(text)
        prompt = f"""You are editing an already translated academic/scientific document.
The target language is {_ACTIVE_TARGET_LANGUAGE or 'the current target language'}.
Rewrite the complete phrase more concisely while preserving meaning.
Preserve every protected marker exactly. Output ONLY the shortened phrase.

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
    """PDF diagnostic mode: prioritize producing a PDF over perfect layout."""
    import pymupdf
    base = pymupdf.Rect(rect)
    expanded = _safe_rect(base, max_bottom=max_bottom)
    start = max(5.5, min(float(block.fontsize), 24.0))
    candidates = (base, expanded) if expanded != base else (base,)
    sizes = [start, start * .90, start * .80, start * .70, start * .60,
             start * .50, start * .40]

    for candidate in candidates:
        if _try_fit(page, candidate, text, block, sizes) is not None:
            return

    shortened = _shorten_preserving_protected(text)
    if shortened:
        for candidate in candidates:
            if _try_fit(page, candidate, shortened, block,
                        [start * .60, start * .50, start * .40, start * .35]) is not None:
                return

    # Diagnostic fallback: intentionally accept clipping/overlap if necessary.
    fallback_text = shortened or text
    try:
        page.insert_textbox(base, fallback_text, fontname=_pdf_font_name(block.flags),
                            fontsize=4.0, color=_pdf_color(block.color), overlay=True)
        return
    except Exception:
        pass

    try:
        page.insert_text((base.x0, base.y0 + 4.0), fallback_text[:12000],
                         fontname=_pdf_font_name(block.flags), fontsize=4.0,
                         color=_pdf_color(block.color), overlay=True)
        return
    except Exception as exc:
        raise RuntimeError(f"No se pudo insertar un bloque PDF ni siquiera en modo diagnóstico: {exc}") from exc


def _table_cell_fit_without_drawing(page, rect, text, fontsize, flags, color):
    """Measure table cells without committing temporary text."""
    try:
        shape = page.new_shape()
        rc = shape.insert_textbox(rect, text, fontname=_pdf_font_name(flags),
                                  fontsize=float(fontsize), color=_pdf_color(color))
        return rc >= 0
    except Exception:
        return False


_original_translate_pdf_document = _dp.translate_pdf_document


def _patched_translate_pdf_document(path, source_lang, target_lang, translate_fn, *, batch_size=18):
    """PDF-only wrapper; DOCX/TXT are not routed through this function."""
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
_dp._table_cell_fit = _table_cell_fit_without_drawing
_dp.translate_pdf_document = _patched_translate_pdf_document

translate_pdf_document = _dp.translate_pdf_document
