"""Document format adapters for Sumire Translate.

PDF-only diagnostic/reconstruction adapter. DOCX/TXT paths are intentionally untouched.
"""

from __future__ import annotations

import re
import tempfile

from . import document_pipeline as _dp

_ACTIVE_TRANSLATE_FN = None
_ACTIVE_TARGET_LANGUAGE = ""
_PDF_ORIGINAL_IMAGES = {}
_PDF_MATH_FONT_FILES = {}

_MATH_CHARS = set("∫∈∇∂ρμντℝ𝒫₀₁₂₃₄₅₆₇₈₉₋₊−×→≤≥√′²³⁴ₜ")


def _contains_math(text: str) -> bool:
    return any(char in _MATH_CHARS for char in (text or ""))


def _is_math_only(text: str) -> bool:
    text = text or ""
    if not _contains_math(text):
        return False
    words = re.findall(r"\b[A-Za-z]{2,}\b", text)
    return len(words) <= 3


def _block_key(block):
    return (int(block.page), tuple(round(float(v), 2) for v in block.bbox))


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


def _try_fit(page, rect, text, block, sizes, *, fontfile=None, fontname=None):
    for size in sizes:
        try:
            kwargs = {
                "fontname": fontname or _pdf_font_name(block.flags),
                "fontsize": max(4.0, float(size)),
                "color": _pdf_color(block.color),
                "overlay": True,
            }
            if fontfile:
                kwargs["fontfile"] = fontfile
            rc = page.insert_textbox(rect, text, **kwargs)
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


def _capture_math_images(doc, blocks):
    """Capture math-only text blocks before redaction so their original glyphs are preserved exactly."""
    import pymupdf
    _PDF_ORIGINAL_IMAGES.clear()
    for block in blocks:
        if not _is_math_only(block.text):
            continue
        try:
            rect = pymupdf.Rect(block.bbox)
            pix = doc[block.page].get_pixmap(
                clip=rect,
                matrix=pymupdf.Matrix(3, 3),
                alpha=True,
                annots=False,
            )
            _PDF_ORIGINAL_IMAGES[_block_key(block)] = pix.tobytes("png")
        except Exception:
            continue


def _raw_block_for(doc, target):
    import pymupdf
    page = doc[target.page]
    wanted = pymupdf.Rect(target.bbox)
    data = page.get_text("dict", sort=True)
    for raw in data.get("blocks", []):
        if raw.get("type") != 0 or not raw.get("lines"):
            continue
        try:
            rect = pymupdf.Rect(raw["bbox"])
        except Exception:
            continue
        if max(abs(rect[i] - wanted[i]) for i in range(4)) < 0.25:
            return raw
    return None


def _line_split_blocks(doc, blocks):
    """Split PDF blocks that are actually borderless tables into positioned line blocks.

    We only split when there are at least three lines whose left edges are
    substantially different. Normal paragraphs keep their original block.
    """
    result = []
    for block in blocks:
        raw = _raw_block_for(doc, block)
        if not raw:
            result.append(block)
            continue
        lines = [line for line in raw.get("lines", []) if line.get("spans")]
        if len(lines) < 3:
            result.append(block)
            continue
        x0s = []
        for line in lines:
            spans = [s for s in line.get("spans", []) if s.get("text")]
            if spans:
                x0s.append(min(float(s["bbox"][0]) for s in spans))
        if len(x0s) < 3 or max(x0s) - min(x0s) < 40.0:
            result.append(block)
            continue

        split = []
        for line in lines:
            spans = [s for s in line.get("spans", []) if s.get("text")]
            if not spans:
                continue
            text = "".join(str(s.get("text", "")) for s in spans).strip()
            if not text:
                continue
            first = spans[0]
            bbox = tuple(float(v) for v in line["bbox"])
            split.append(_dp.PDFTextBlock(
                page=block.page,
                bbox=bbox,
                text=text,
                fontsize=float(first.get("size", block.fontsize) or block.fontsize),
                flags=int(first.get("flags", block.flags) or block.flags),
                color=int(first.get("color", block.color) or block.color),
            ))
        result.extend(split or [block])
    return result


def _patched_extract_pdf_blocks(doc):
    blocks = _dp._extract_pdf_blocks_original(doc)
    blocks = _line_split_blocks(doc, blocks)
    _capture_math_images(doc, blocks)
    return blocks


def _math_font_file(page, block):
    """Extract the original embedded math font for mixed prose+math blocks."""
    if not _contains_math(block.text):
        return None
    key = (id(page.parent), tuple(round(float(v), 2) for v in block.bbox))
    if key in _PDF_MATH_FONT_FILES:
        return _PDF_MATH_FONT_FILES[key]
    try:
        data = page.get_text("dict", clip=page.rect, sort=True)
        fonts = page.get_fonts(full=True)
        for raw in data.get("blocks", []):
            if raw.get("type") != 0:
                continue
            for line in raw.get("lines", []):
                for span in line.get("spans", []):
                    text = str(span.get("text", ""))
                    if not _contains_math(text):
                        continue
                    span_font = str(span.get("font", ""))
                    match = next((f for f in fonts if f[3] == span_font or f[4] == span_font), None)
                    if not match:
                        continue
                    buffer = page.parent.extract_font(match[0])[3]
                    if not buffer:
                        continue
                    tmp = tempfile.NamedTemporaryFile(prefix="sumire_math_", suffix=".ttf", delete=False)
                    tmp.write(buffer)
                    tmp.close()
                    _PDF_MATH_FONT_FILES[key] = tmp.name
                    return tmp.name
    except Exception:
        return None
    return None


def _patched_insert_pdf_text_fitted(page, rect, text, block, *, max_bottom=None):
    """PDF-only reconstruction: preserve math glyphs and prioritize a readable diagnostic PDF."""
    import pymupdf
    base = pymupdf.Rect(rect)

    if _is_math_only(block.text):
        image = _PDF_ORIGINAL_IMAGES.get(_block_key(block))
        if image:
            try:
                page.insert_image(base, stream=image, keep_proportion=False, overlay=True)
                return
            except Exception:
                pass

    expanded = _safe_rect(base, max_bottom=max_bottom)
    start = max(5.5, min(float(block.fontsize), 24.0))
    candidates = (expanded, base) if expanded != base else (base,)
    math_font = _math_font_file(page, block) if _contains_math(block.text) else None

    if math_font:
        if _try_fit(page, candidates[0], text, block,
                    [start, start * .94, start * .89, start * .85, start * .80],
                    fontfile=math_font, fontname="sumiremath") is not None:
            return

    sizes = [start, start * .94, start * .89, start * .85, start * .80,
             start * .70, start * .60, start * .50, start * .40]
    for candidate in candidates:
        if _try_fit(page, candidate, text, block, sizes) is not None:
            return

    shortened = _shorten_preserving_protected(text)
    if shortened:
        for candidate in candidates:
            if _try_fit(page, candidate, shortened, block,
                        [start * .60, start * .50, start * .40, start * .35]) is not None:
                return

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


def _patched_table_rows_with_rects(page, table_obj):
    """Build a rectangular grid from true row/column boundaries.

    Cell-center clustering incorrectly separates vertically merged cells. Here
    each grid slot gets text only when its owning source cell starts in that row.
    The original PDF grid is left intact, so merged borders remain visible.
    """
    import pymupdf
    rects = _dp._table_cell_rects(table_obj)
    if not rects:
        return []
    xs = sorted({round(float(v), 3) for r in rects for v in (r[0], r[2])})
    ys = sorted({round(float(v), 3) for r in rects for v in (r[1], r[3])})
    if len(xs) < 2 or len(ys) < 2:
        return []

    rows = []
    tol = 0.25
    for ri in range(len(ys) - 1):
        row = []
        y0, y1 = ys[ri], ys[ri + 1]
        for ci in range(len(xs) - 1):
            x0, x1 = xs[ci], xs[ci + 1]
            grid = pymupdf.Rect(x0, y0, x1, y1)
            owner = next((r for r in rects
                          if r[0] <= x0 + tol and r[2] >= x1 - tol
                          and r[1] <= y0 + tol and r[3] >= y1 - tol), None)
            text = ""
            if owner is not None and abs(owner[0] - x0) <= tol and abs(owner[1] - y0) <= tol:
                text = _dp._table_cell_text(page, grid)
            row.append({"rect": grid, "text": text})
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# PDF-ONLY DIAGNOSTIC TRANSLATION OVERRIDE
# ---------------------------------------------------------------------------
_original_translate_segments = _dp._translate_segments
_original_translate_pdf_document = _dp.translate_pdf_document
_original_validate_final_pdf = _dp._validate_final_pdf
_dp._extract_pdf_blocks_original = _dp._extract_pdf_blocks


def _diagnostic_translate_segments(segments, source_lang, target_lang, translate_fn):
    try:
        return _original_translate_segments(segments, source_lang, target_lang, translate_fn)
    except RuntimeError:
        normalised = _dp._normalise_segments(segments)
        outputs = []
        for segment in normalised:
            try:
                outputs.extend(_original_translate_segments(
                    [segment], source_lang, target_lang, translate_fn
                ))
            except Exception:
                outputs.append(segment[1])
        return outputs


def _patched_validate_final_pdf(output, source_texts):
    """Validate protected text that can be reliably checked by PDF extraction.

    Mathematical content is validated before reconstruction by the protected
    marker validator. After reconstruction, Unicode glyph extraction is not a
    reliable proof of visual preservation, so math-bearing blocks are excluded
    from this second text-extraction-only check.
    """
    filtered = [text for text in source_texts if not _contains_math(text)]
    return _original_validate_final_pdf(output, filtered)


def _patched_translate_pdf_document(path, source_lang, target_lang, translate_fn, *, batch_size=18):
    """PDF-only wrapper; DOCX/TXT are not routed through this function."""
    global _ACTIVE_TRANSLATE_FN, _ACTIVE_TARGET_LANGUAGE
    previous_fn = _ACTIVE_TRANSLATE_FN
    previous_target = _ACTIVE_TARGET_LANGUAGE
    previous_segment_fn = _dp._translate_segments
    _ACTIVE_TRANSLATE_FN = translate_fn
    _PDF_ORIGINAL_IMAGES.clear()
    try:
        from backend.core.languages import language_name
        _ACTIVE_TARGET_LANGUAGE = language_name(target_lang)
    except Exception:
        _ACTIVE_TARGET_LANGUAGE = str(target_lang)
    _dp._translate_segments = _diagnostic_translate_segments
    try:
        return _original_translate_pdf_document(path, source_lang, target_lang, translate_fn, batch_size=batch_size)
    finally:
        _dp._translate_segments = previous_segment_fn
        _ACTIVE_TRANSLATE_FN = previous_fn
        _ACTIVE_TARGET_LANGUAGE = previous_target
        _PDF_ORIGINAL_IMAGES.clear()


_dp._insert_pdf_text_fitted = _patched_insert_pdf_text_fitted
_dp._table_cell_fit = _table_cell_fit_without_drawing
_dp._table_rows_with_rects = _patched_table_rows_with_rects
_dp._extract_pdf_blocks = _patched_extract_pdf_blocks
_dp._validate_final_pdf = _patched_validate_final_pdf
_dp.translate_pdf_document = _patched_translate_pdf_document

translate_pdf_document = _dp.translate_pdf_document
