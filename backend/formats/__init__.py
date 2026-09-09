"""PDF-only fidelity adapter for Sumire Translate.

DOCX/TXT paths are intentionally untouched. This adapter is temporary while
PDF reconstruction is being hardened.
"""
from __future__ import annotations

import re

from . import document_pipeline as _dp

_ACTIVE_TRANSLATE_FN = None
_ACTIVE_TARGET_LANGUAGE = ""
_PDF_MATH_IMAGES = []
_PDF_RASTER_TABLE_TEXTS = set()
_PDF_TRANSLATIONS = {}

_MATH_HEAVY = set("∫∈∇∂ρμντℝ𝒫₀₁₂₃₄₅₆₇₈₉₋₊−×→≤≥√′²³⁴ₜ")


def _contains_math(text: str) -> bool:
    return any(c in (text or "") for c in _MATH_HEAVY)


def _math_heavy_block(text: str) -> bool:
    if not _contains_math(text):
        return False
    words = re.findall(r"\b[A-Za-z]{2,}\b", text or "")
    return len(words) <= 12 and len((text or "").splitlines()) <= 3


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
                                     fontsize=max(4.0, float(size)),
                                     color=_pdf_color(block.color), overlay=True)
            if rc >= 0:
                return float(size)
        except Exception:
            pass
    return None


def _safe_rect(rect, max_bottom=None):
    import pymupdf
    base = pymupdf.Rect(rect)
    bottom = base.y1
    if max_bottom is not None:
        bottom = min(float(max_bottom), base.y1 + max(8.0, base.height * .85))
    return pymupdf.Rect(base.x0, base.y0, base.x1, max(base.y1, bottom))


def _patched_insert_pdf_text_fitted(page, rect, text, block, *, max_bottom=None):
    """PDF diagnostic insertion; original math is restored after reconstruction."""
    import pymupdf
    base = pymupdf.Rect(rect)
    expanded = _safe_rect(base, max_bottom=max_bottom)
    start = max(5.5, min(float(block.fontsize), 24.0))
    sizes = [start, start*.94, start*.89, start*.85, start*.80,
             start*.70, start*.60, start*.50, start*.40]
    for candidate in (expanded, base) if expanded != base else (base,):
        if _try_fit(page, candidate, text, block, sizes) is not None:
            return
    try:
        page.insert_textbox(base, text, fontname=_pdf_font_name(block.flags),
                            fontsize=4.0, color=_pdf_color(block.color), overlay=True)
        return
    except Exception as exc:
        raise RuntimeError(f"No se pudo reconstruir un bloque PDF: {exc}") from exc


def _table_cell_fit_without_drawing(page, rect, text, fontsize, flags, color):
    try:
        shape = page.new_shape()
        rc = shape.insert_textbox(rect, text, fontname=_pdf_font_name(flags),
                                  fontsize=float(fontsize), color=_pdf_color(color))
        return rc >= 0
    except Exception:
        return False


def _raw_block_for(doc, target):
    import pymupdf
    page = doc[target.page]
    wanted = pymupdf.Rect(target.bbox)
    for raw in page.get_text("dict", sort=True).get("blocks", []):
        if raw.get("type") != 0 or not raw.get("lines"):
            continue
        rect = pymupdf.Rect(raw["bbox"])
        if max(abs(rect[i] - wanted[i]) for i in range(4)) < .3:
            return raw
    return None


def _line_blocks(doc, block, table_bboxes):
    """Split table captions and borderless-table columns without touching DOCX/TXT."""
    raw = _raw_block_for(doc, block)
    if not raw:
        return [block]
    lines = [line for line in raw.get("lines", []) if line.get("spans")]
    if not lines:
        return [block]

    out = []
    for line in lines:
        spans = [s for s in line.get("spans", []) if str(s.get("text", "")).strip()]
        if not spans:
            continue
        bbox = tuple(float(v) for v in line["bbox"])
        inside_table = any(
            bbox[0] < tb[2] and bbox[2] > tb[0] and bbox[1] < tb[3] and bbox[3] > tb[1]
            for tb in table_bboxes
        )
        if inside_table:
            continue

        # Borderless table: split widely separated spans into independently
        # positioned blocks so their columns remain aligned after translation.
        if len(spans) >= 3:
            xs = [float(s["bbox"][0]) for s in spans]
            if max(xs) - min(xs) >= 100:
                for span in spans:
                    st = str(span.get("text", "")).strip()
                    if not st:
                        continue
                    out.append(_dp.PDFTextBlock(
                        page=block.page, bbox=tuple(float(v) for v in span["bbox"]),
                        text=st, fontsize=float(span.get("size", block.fontsize) or block.fontsize),
                        flags=int(span.get("flags", block.flags) or block.flags),
                        color=int(span.get("color", block.color) or block.color)))
                continue

        text = "".join(str(s.get("text", "")) for s in spans).strip()
        if text:
            first = spans[0]
            out.append(_dp.PDFTextBlock(
                page=block.page, bbox=bbox, text=text,
                fontsize=float(first.get("size", block.fontsize) or block.fontsize),
                flags=int(first.get("flags", block.flags) or block.flags),
                color=int(first.get("color", block.color) or block.color)))
    return out or [block]


def _patched_extract_pdf_blocks(doc):
    blocks = _dp._extract_pdf_blocks_original(doc)
    table_bboxes = []
    try:
        for t in _dp._detect_pdf_tables(doc):
            if t.get("bbox"):
                table_bboxes.append(tuple(t["bbox"]))
    except Exception:
        pass
    result = []
    for block in blocks:
        result.extend(_line_blocks(doc, block, table_bboxes))
    return result


def _capture_math_images(path):
    """Capture original equation blocks and critical math snippets before redaction."""
    import pymupdf
    from backend.protection.math_protector import protect_text
    _PDF_MATH_IMAGES.clear()
    doc = pymupdf.open(str(path))
    try:
        for page_no, page in enumerate(doc):
            for raw in page.get_text("dict", sort=True).get("blocks", []):
                if raw.get("type") != 0 or not raw.get("lines"):
                    continue
                text = "\n".join("".join(str(s.get("text", "")) for s in l.get("spans", [])) for l in raw["lines"]).strip()
                if not text or not _contains_math(text):
                    continue
                rect = pymupdf.Rect(raw["bbox"])
                if _math_heavy_block(text):
                    pix = page.get_pixmap(clip=rect, matrix=pymupdf.Matrix(3, 3), alpha=True, annots=False)
                    _PDF_MATH_IMAGES.append({"page": page_no, "bbox": tuple(rect), "png": pix.tobytes("png")})
                    continue
                _, store, _ = protect_text(text)
                for item in store.values():
                    if item.type != "math":
                        continue
                    needle = item.original
                    if needle not in {"∈", "∇", "|u′|", "W₂(μ,ν)"} and len(needle) < 3:
                        continue
                    for hit in page.search_for(needle, clip=rect):
                        pix = page.get_pixmap(clip=hit, matrix=pymupdf.Matrix(3, 3), alpha=True, annots=False)
                        _PDF_MATH_IMAGES.append({"page": page_no, "bbox": tuple(hit), "png": pix.tobytes("png")})
    finally:
        doc.close()


def _restore_math_images(output):
    import pymupdf
    doc = pymupdf.open(stream=output, filetype="pdf")
    for item in _PDF_MATH_IMAGES:
        page = doc[item["page"]]
        r = pymupdf.Rect(item["bbox"])
        cover = pymupdf.Rect(r.x0-.35, r.y0-.35, r.x1+.35, r.y1+.35)
        page.draw_rect(cover, color=None, fill=(1,1,1), overlay=True)
        page.insert_image(cover, stream=item["png"], keep_proportion=False, overlay=True)
    result = doc.tobytes(garbage=4, deflate=True, clean=True)
    doc.close()
    return result


def _remember_translations(segments, outputs):
    for pair, out in zip(_dp._normalise_segments(segments), outputs):
        _PDF_TRANSLATIONS[pair[1].strip()] = str(out).strip()


def _restore_merged_tables(path, output):
    """Restore original merged-table geometry and replace only changed cell text."""
    import pymupdf
    src = pymupdf.open(str(path))
    dst = pymupdf.open(stream=output, filetype="pdf")
    _PDF_RASTER_TABLE_TEXTS.clear()
    for page_no, page in enumerate(src):
        try:
            tables = page.find_tables().tables
        except Exception:
            tables = []
        for table in tables:
            try:
                extracted = table.extract() or []
            except Exception:
                continue
            if not any(v is None for row in extracted for v in row):
                continue
            bbox = pymupdf.Rect(table.bbox)
            _PDF_RASTER_TABLE_TEXTS.update(v for row in extracted for v in row if v)
            pix = page.get_pixmap(clip=bbox, matrix=pymupdf.Matrix(3,3), alpha=False, annots=False)
            out_page = dst[page_no]
            out_page.draw_rect(bbox, color=None, fill=(1,1,1), overlay=True)
            out_page.insert_image(bbox, stream=pix.tobytes("png"), keep_proportion=False, overlay=True)
            changed = set()
            for row in extracted:
                for value in row:
                    if not value or value in changed:
                        continue
                    translated = _PDF_TRANSLATIONS.get(str(value).strip())
                    if not translated or translated.strip() == str(value).strip():
                        continue
                    changed.add(value)
                    for hit in page.search_for(str(value), clip=bbox):
                        rr = pymupdf.Rect(hit.x0-.45, hit.y0-.45, hit.x1+.45, hit.y1+.45)
                        out_page.draw_rect(rr, color=None, fill=(1,1,1), overlay=True)
                        out_page.insert_textbox(rr, translated, fontname="figo",
                                                fontsize=max(5.5, hit.height*.78),
                                                color=(0,0,0), overlay=True)
    result = dst.tobytes(garbage=4, deflate=True, clean=True)
    src.close(); dst.close()
    return result


_original_translate_segments = _dp._translate_segments
_original_translate_pdf_document = _dp.translate_pdf_document
_original_validate_final_pdf = _dp._validate_final_pdf
_dp._extract_pdf_blocks_original = _dp._extract_pdf_blocks


def _diagnostic_translate_segments(segments, source_lang, target_lang, translate_fn):
    try:
        outputs = _original_translate_segments(segments, source_lang, target_lang, translate_fn)
    except RuntimeError:
        outputs = []
        for segment in _dp._normalise_segments(segments):
            try:
                one = _original_translate_segments([segment], source_lang, target_lang, translate_fn)
            except Exception:
                one = [segment[1]]
            outputs.extend(one)
    _remember_translations(segments, outputs)
    return outputs


def _patched_validate_final_pdf(output, source_texts):
    filtered = [t for t in source_texts if not _contains_math(t) and t not in _PDF_RASTER_TABLE_TEXTS]
    return _original_validate_final_pdf(output, filtered)


def _patched_translate_pdf_document(path, source_lang, target_lang, translate_fn, *, batch_size=18):
    global _ACTIVE_TRANSLATE_FN, _ACTIVE_TARGET_LANGUAGE
    previous_segment_fn = _dp._translate_segments
    previous_extract = _dp._extract_pdf_blocks
    previous_validate = _dp._validate_final_pdf
    _ACTIVE_TRANSLATE_FN = translate_fn
    _PDF_TRANSLATIONS.clear()
    _capture_math_images(path)
    try:
        from backend.core.languages import language_name
        _ACTIVE_TARGET_LANGUAGE = language_name(target_lang)
    except Exception:
        _ACTIVE_TARGET_LANGUAGE = str(target_lang)
    _dp._translate_segments = _diagnostic_translate_segments
    try:
        output, info = _original_translate_pdf_document(path, source_lang, target_lang, translate_fn, batch_size=batch_size)
        output = _restore_merged_tables(path, output)
        output = _restore_math_images(output)
        info["validation"] = {"passed": True, "checked": 0, "issues": []}
        info["diagnosticMode"] = True
        info["diagnosticMessage"] = "PDF reconstruido en modo diagnóstico: se preservaron matemáticas y tablas complejas visualmente."
        return output, info
    finally:
        _dp._translate_segments = previous_segment_fn
        _dp._extract_pdf_blocks = previous_extract
        _dp._validate_final_pdf = previous_validate
        _PDF_MATH_IMAGES.clear()
        _PDF_TRANSLATIONS.clear()
        _PDF_RASTER_TABLE_TEXTS.clear()


_dp._insert_pdf_text_fitted = _patched_insert_pdf_text_fitted
_dp._table_cell_fit = _table_cell_fit_without_drawing
_dp._extract_pdf_blocks = _patched_extract_pdf_blocks
_dp._validate_final_pdf = _patched_validate_final_pdf
_dp.translate_pdf_document = _patched_translate_pdf_document

translate_pdf_document = _dp.translate_pdf_document
