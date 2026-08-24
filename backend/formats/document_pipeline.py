"""Layout-aware document translation for Sumire Translate.

PDF tables are handled as real matrices: detect the table first, obtain each
cell rectangle, translate each non-empty cell independently, then write the
translation back into the same cell. DOCX translation deliberately preserves
all non-text XML (images, drawings, hyperlinks, formatting and relationships).
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable

from backend.core.languages import language_name
from backend.protection.math_protector import ProtectedElement, protect_text, restore_markers
from backend.processing.word_counter import count_words
from backend.validation.validator import validate

TranslateFn = Callable[[str], str]
MARKER_RE = re.compile(r"\[\[[A-Z]+_\d{3}\]\]")


@dataclass
class PDFTextBlock:
    page: int
    bbox: tuple[float, float, float, float]
    text: str
    fontsize: float
    flags: int
    color: int


def _block_text(block: dict) -> str:
    lines: list[str] = []
    for line in block.get("lines", []):
        spans = line.get("spans", [])
        lines.append("".join(str(span.get("text", "")) for span in spans).rstrip())
    return "\n".join(lines).strip()


def _extract_pdf_blocks(doc) -> list[PDFTextBlock]:
    blocks: list[PDFTextBlock] = []
    for page_index, page in enumerate(doc):
        data = page.get_text("dict", sort=True)
        for block in data.get("blocks", []):
            if block.get("type") != 0 or not block.get("lines"):
                continue
            text = _block_text(block)
            if not text:
                continue
            spans = [span for line in block.get("lines", []) for span in line.get("spans", []) if span.get("text")]
            if not spans:
                continue
            first = spans[0]
            blocks.append(PDFTextBlock(
                page=page_index, bbox=tuple(float(x) for x in block["bbox"]), text=text,
                fontsize=float(first.get("size", 10.0) or 10.0), flags=int(first.get("flags", 0) or 0),
                color=int(first.get("color", 0) or 0),
            ))
    return blocks


def _detect_pdf_tables(doc) -> list[dict]:
    tables: list[dict] = []
    for page_index, page in enumerate(doc):
        try:
            finder = page.find_tables()
            found = getattr(finder, "tables", []) or []
        except (AttributeError, TypeError, RuntimeError):
            found = []
        for table_index, table in enumerate(found, start=1):
            extracted = []
            try:
                extracted = [list(row) for row in (table.extract() or [])]
            except (AttributeError, TypeError, RuntimeError):
                pass
            rows = len(extracted)
            columns = max((len(row) for row in extracted), default=0)
            cell_rects = _table_cell_rects(table)
            if not rows or not columns:
                rows, columns = _infer_matrix(cell_rects)
            bbox = getattr(table, "bbox", None)
            tables.append({
                "number": table_index, "page": page_index + 1, "rows": rows, "columns": columns,
                "cells": rows * columns if rows and columns else len(cell_rects),
                "size": f"{rows}×{columns}" if rows and columns else "desconocido",
                "bbox": tuple(float(x) for x in bbox) if bbox else None,
            })
    return tables


def _table_cell_rects(table) -> list[tuple[float, float, float, float]]:
    rects = []
    for cell in getattr(table, "cells", []) or []:
        if cell is None:
            continue
        try:
            if len(cell) >= 4:
                rects.append(tuple(float(v) for v in cell[:4]))
        except (TypeError, ValueError):
            continue
    return rects


def _infer_matrix(rects: list[tuple[float, float, float, float]]) -> tuple[int, int]:
    if not rects:
        return 0, 0
    ys = sorted({round((r[1] + r[3]) / 2, 2) for r in rects})
    xs = sorted({round((r[0] + r[2]) / 2, 2) for r in rects})
    return len(ys), len(xs)


def inspect_pdf_tables(path: str | Path) -> list[dict]:
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("Falta PyMuPDF. La dependencia está declarada en requirements.txt.") from exc
    doc = pymupdf.open(str(path))
    try:
        return _detect_pdf_tables(doc)
    finally:
        doc.close()


def _marker_sequence(text: str) -> list[str]:
    return MARKER_RE.findall(text)


def _build_segment_prompt(source_lang: str, target_lang: str, segments: list[tuple[str, str]]) -> str:
    body = []
    for segment_id, protected in segments:
        body.append(f"[[SUMIRE_SEG_{segment_id}_START]]")
        body.append(protected)
        body.append(f"[[SUMIRE_SEG_{segment_id}_END]]")
    return f"""You are a professional academic and scientific translator.
Translate from {language_name(source_lang)} to {language_name(target_lang)}.

Translate ONLY natural language. Preserve every marker exactly.
Never translate, modify, reorder, remove or add protected markers.
Do not change formulas, variables, numbers, symbols, code, URLs, citations,
table delimiters or document structure.
Keep every segment delimiter exactly as supplied.
Output only the translation.

{chr(10).join(body)}"""


def _translate_segments(segments: list[tuple[str, str]], source_lang: str, target_lang: str,
                        translate_fn: TranslateFn) -> list[str]:
    if not segments:
        return []
    prepared: list[tuple[str, str, dict[str, ProtectedElement]]] = []
    for segment_id, text in segments:
        protected, store, _ = protect_text(text)
        prepared.append((segment_id, protected, store))

    translated = translate_fn(_build_segment_prompt(
        source_lang, target_lang, [(segment_id, protected) for segment_id, protected, _ in prepared]
    ))

    expected = []
    for segment_id, protected, _ in prepared:
        expected.append(f"[[SUMIRE_SEG_{segment_id}_START]]")
        expected.extend(_marker_sequence(protected))
        expected.append(f"[[SUMIRE_SEG_{segment_id}_END]]")
    actual = re.findall(r"\[\[[A-Z_]+_\d{3,6}(?:_(?:START|END))?\]\]", translated)
    if actual != expected:
        raise RuntimeError("La traducción fue bloqueada: el modelo alteró la estructura protegida del documento.")

    outputs: list[str] = []
    for segment_id, original_protected, store in prepared:
        start = f"[[SUMIRE_SEG_{segment_id}_START]]"
        end = f"[[SUMIRE_SEG_{segment_id}_END]]"
        a = translated.find(start)
        b = translated.find(end, a + len(start))
        if a < 0 or b < 0:
            raise RuntimeError("La traducción fue bloqueada: falta un delimitador de segmento.")
        segment_output = translated[a + len(start):b].strip("\n")
        if _marker_sequence(segment_output) != _marker_sequence(original_protected):
            raise RuntimeError(f"La traducción fue bloqueada: se alteraron elementos protegidos en el segmento {segment_id}.")
        restored = restore_markers(segment_output, store)
        validation = validate(
            original_protected.replace("[[", "").replace("]]", ""), restored, store,
            protected_source=original_protected, translated_protected=segment_output,
        )
        if not validation["passed"]:
            raise RuntimeError(f"La traducción fue bloqueada por la validación del segmento {segment_id}.")
        outputs.append(restored)
    return outputs


def _aggregate_counts(texts: list[str]) -> dict:
    total = translatable = protected = protected_words = 0
    by_type: dict[str, int] = {}
    for text in texts:
        c = count_words(text)
        total += int(c.get("total", 0)); translatable += int(c.get("translatable", 0))
        protected += int(c.get("protected", 0)); protected_words += int(c.get("protectedWords", 0))
        for kind, amount in c.get("protectedByType", {}).items():
            by_type[kind] = by_type.get(kind, 0) + int(amount)
    return {
        "total": total, "translatable": translatable, "protected": protected,
        "protectedWords": protected_words, "protectedRatio": protected_words / total if total else 0.0,
        "protectedByType": dict(sorted(by_type.items())),
    }


def _pdf_color(value: int) -> tuple[float, float, float]:
    return ((value >> 16 & 255) / 255, (value >> 8 & 255) / 255, (value & 255) / 255)


def _pdf_font_name(flags: int) -> str:
    bold, italic = bool(flags & 16), bool(flags & 2)
    if bold and italic: return "figbi"
    if bold: return "figbo"
    if italic: return "figit"
    return "figo"


def _insert_pdf_text_fitted(page, rect, text: str, block: PDFTextBlock) -> float:
    fontsize = max(5.5, min(block.fontsize, 24.0))
    while fontsize >= 4:
        rc = page.insert_textbox(rect, text, fontname=_pdf_font_name(block.flags), fontsize=fontsize,
                                 color=_pdf_color(block.color), overlay=True)
        if rc >= 0: return fontsize
        fontsize -= 0.5
    raise RuntimeError("La reconstrucción fue bloqueada: un bloque traducido no cabe en su región original.")


def _table_cell_text(page, rect) -> str:
    try: return page.get_text("text", clip=rect, sort=True).strip()
    except (TypeError, RuntimeError): return ""


def _table_cells_for_page(page, table_obj) -> list[dict]:
    import pymupdf
    cells = []
    for rect in _table_cell_rects(table_obj):
        r = pymupdf.Rect(rect); text = _table_cell_text(page, r)
        if text: cells.append({"rect": r, "text": text})
    cells.sort(key=lambda c: (round(c["rect"].y0, 1), round(c["rect"].x0, 1)))
    return cells


def _block_inside_table(block: PDFTextBlock, table_infos: list[dict]) -> bool:
    cx = (block.bbox[0] + block.bbox[2]) / 2; cy = (block.bbox[1] + block.bbox[3]) / 2
    for table in table_infos:
        bbox = table.get("bbox")
        if bbox and bbox[0] <= cx <= bbox[2] and bbox[1] <= cy <= bbox[3] and table["page"] - 1 == block.page:
            return True
    return False


def _validate_final_pdf(output: bytes, source_texts: list[str]) -> dict:
    import pymupdf
    result = pymupdf.open(stream=output, filetype="pdf")
    extracted = "\n".join(page.get_text("text") for page in result); result.close()
    issues = []; checked = 0
    for text in source_texts:
        _, store, _ = protect_text(text)
        for item in store.values():
            checked += 1; needle = item.original
            if needle not in extracted:
                normalized_source = re.sub(r"\s+", " ", needle).strip()
                normalized_pdf = re.sub(r"\s+", " ", extracted).strip()
                if normalized_source not in normalized_pdf:
                    issues.append({"type": "protected_content_missing_in_pdf", "kind": item.type, "original": needle})
                    if len(issues) >= 20: break
        if len(issues) >= 20: break
    return {"passed": not issues, "checked": checked, "issues": issues}


def translate_pdf_document(path: str | Path, source_lang: str, target_lang: str,
                           translate_fn: TranslateFn, *, batch_size: int = 18) -> tuple[bytes, dict]:
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("Falta PyMuPDF. La dependencia está declarada en requirements.txt.") from exc
    source = pymupdf.open(str(path)); page_count = source.page_count; table_infos = _detect_pdf_tables(source)
    page_tables: dict[int, list] = {}
    for page_index, page in enumerate(source):
        try: page_tables[page_index] = list(getattr(page.find_tables(), "tables", []) or [])
        except (AttributeError, TypeError, RuntimeError): page_tables[page_index] = []
    blocks = [b for b in _extract_pdf_blocks(source) if not _block_inside_table(b, table_infos)]
    original_block_texts = [b.text for b in blocks]; original_table_texts: list[str] = []; translated_blocks: list[str] = []
    for start in range(0, len(blocks), batch_size):
        batch = blocks[start:start + batch_size]
        translated_blocks.extend(_translate_segments([(f"{start + i + 1:06d}", b.text) for i, b in enumerate(batch)], source_lang, target_lang, translate_fn))
    if len(translated_blocks) != len(blocks):
        source.close(); raise RuntimeError("La traducción no produjo todos los bloques del documento.")
    for page_index, table_list in page_tables.items():
        page = source[page_index]
        for table_obj in table_list:
            cells = _table_cells_for_page(page, table_obj)
            if not cells: continue
            cell_results = []
            for cell in cells:
                original_table_texts.append(cell["text"])
                cell_results.append((cell, _translate_segments([("900000", cell["text"])], source_lang, target_lang, translate_fn)[0]))
            for cell, _ in cell_results: page.add_redact_annot(cell["rect"], fill=False, cross_out=False)
            page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE, text=pymupdf.PDF_REDACT_TEXT_REMOVE)
            for cell, value in cell_results:
                r = cell["rect"]; rect = pymupdf.Rect(r.x0 + 1.2, r.y0 + 1.0, r.x1 - 1.2, r.y1 - 1.0)
                _insert_pdf_text_fitted(page, rect, value, PDFTextBlock(page_index, tuple(rect), cell["text"], 9.5, 0, 0))
    for block in blocks: source[block.page].add_redact_annot(pymupdf.Rect(block.bbox), fill=False, cross_out=False)
    for page in source: page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE, text=pymupdf.PDF_REDACT_TEXT_REMOVE)
    for block, value in zip(blocks, translated_blocks):
        rect = pymupdf.Rect(block.bbox); rect = pymupdf.Rect(rect.x0, rect.y0 - 0.5, rect.x1, rect.y1 + max(1.0, block.fontsize * 0.18))
        _insert_pdf_text_fitted(source[block.page], rect, value, block)
    output = source.tobytes(garbage=4, deflate=True, clean=True); source.close()
    final_validation = _validate_final_pdf(output, original_block_texts + original_table_texts)
    if not final_validation["passed"]:
        raise RuntimeError("La reconstrucción PDF fue bloqueada: la validación final detectó contenido protegido que no sobrevivió al renderizado.")
    counts = _aggregate_counts(original_block_texts + original_table_texts)
    if table_infos: counts["protectedByType"]["table"] = len(table_infos)
    else: counts["protectedByType"].pop("table", None)
    return output, {"format": "pdf", "pages": page_count, "textBlocks": len(blocks), "tables": len(table_infos), "tableDetails": table_infos, "counts": counts, "validation": final_validation}


# ---------------------------------------------------------------------------
# DOCX: image-safe translation
# ---------------------------------------------------------------------------

def _docx_media_inventory(path_or_bytes) -> set[str]:
    """Return every embedded image part in a DOCX ZIP.

    This is intentionally independent of python-docx. It catches both inline
    and floating images because both are stored under word/media/ in the OOXML
    package. The images are never sent to Gemini and never recreated by it.
    """
    if hasattr(path_or_bytes, "read"):
        raw = path_or_bytes.read()
        path_or_bytes.seek(0)
        z = zipfile.ZipFile(BytesIO(raw))
    elif isinstance(path_or_bytes, (bytes, bytearray)):
        z = zipfile.ZipFile(BytesIO(path_or_bytes))
    else:
        z = zipfile.ZipFile(str(path_or_bytes))
    try:
        return {name for name in z.namelist() if name.startswith("word/media/") and not name.endswith("/")}
    finally:
        z.close()


def _set_paragraph_text_preserve_drawings(paragraph, value: str) -> None:
    """Replace visible text while preserving drawings/images in the paragraph.

    python-docx's ``run.text = ...`` replaces the run XML children. If the run
    also contains a drawing, that can delete the image. We therefore edit only
    existing w:t nodes and leave every w:drawing/w:pict element untouched.
    """
    from docx.oxml.ns import qn

    text_nodes = []
    for run in paragraph.runs:
        for child in run._r.iterchildren():
            if child.tag == qn("w:t"):
                text_nodes.append(child)
    if text_nodes:
        text_nodes[0].text = value
        for node in text_nodes[1:]:
            node.text = ""
    else:
        # Paragraph has no existing text node (for example image-only). Do not
        # touch it: adding translated text here could alter image-only layout.
        if value and not any(el.tag == qn("w:drawing") or el.tag == qn("w:pict") for el in paragraph._p.iter()):
            paragraph.add_run(value)


def _translate_docx_paragraphs(document, source_lang: str, target_lang: str, translate_fn: TranslateFn):
    texts: list[str] = []; locations = []

    def add_paragraph(paragraph) -> None:
        text = paragraph.text.strip()
        if text:
            texts.append(text); locations.append(paragraph)

    for paragraph in document.paragraphs: add_paragraph(paragraph)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs: add_paragraph(paragraph)

    translated: list[str] = []
    for start in range(0, len(texts), 18):
        batch = texts[start:start + 18]
        translated.extend(_translate_segments([(f"{start + i + 1:06d}", text) for i, text in enumerate(batch)], source_lang, target_lang, translate_fn))
    for paragraph, value in zip(locations, translated):
        _set_paragraph_text_preserve_drawings(paragraph, value)
    return texts, translated


def translate_docx_document(path: str | Path, source_lang: str, target_lang: str,
                            translate_fn: TranslateFn) -> tuple[bytes, dict]:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("Falta python-docx. La dependencia está declarada en requirements.txt.") from exc

    # Image protector: images are treated as immutable binary assets. Gemini
    # receives only text; the DOCX package carries the original images through.
    original_media = _docx_media_inventory(path)
    document = Document(str(path))
    original_texts, _ = _translate_docx_paragraphs(document, source_lang, target_lang, translate_fn)
    counts = _aggregate_counts(original_texts)

    output = BytesIO(); document.save(output); data = output.getvalue()
    output_media = _docx_media_inventory(data)
    if original_media != output_media:
        missing = sorted(original_media - output_media)
        raise RuntimeError(f"La reconstrucción DOCX fue bloqueada: se perderían {len(missing)} imagen(es) del documento original.")

    # A lightweight final validation: the number of image assets is identical.
    image_count = len(original_media)
    return data, {
        "format": "docx", "pages": None, "textBlocks": len(original_texts),
        "tables": len(document.tables), "images": image_count,
        "imagesPreserved": original_media == output_media,
        "tableDetails": [
            {"number": i + 1, "page": None, "rows": len(table.rows), "columns": len(table.columns),
             "cells": len(table.rows) * len(table.columns), "size": f"{len(table.rows)}×{len(table.columns)}"}
            for i, table in enumerate(document.tables)
        ],
        "counts": counts, "validation": {"passed": True, "checked": image_count, "issues": []},
    }


def translate_document(path: str | Path, source_lang: str, target_lang: str,
                       translate_fn: TranslateFn) -> tuple[bytes, str, dict]:
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        data, info = translate_pdf_document(path, source_lang, target_lang, translate_fn); return data, "pdf", info
    if suffix == ".docx":
        data, info = translate_docx_document(path, source_lang, target_lang, translate_fn); return data, "docx", info
    raise ValueError("Formato de documento no soportado.")
