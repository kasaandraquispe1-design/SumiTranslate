"""Layout-aware document translation for Sumire Translate.

The original document remains the visual source of truth. PDF images/vector
art are never removed, DOCX drawing runs are preserved, and detected PDF tables
are translated cell-by-cell so columns do not collapse into the first column.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from backend.core.languages import language_name
from backend.protection.math_protector import ProtectedElement, protect_text, restore_markers
from backend.processing.word_counter import count_words
from backend.validation.validator import validate

TranslateFn = Callable[[str], str]
SEGMENT_RE = re.compile(r"\[\[SUMIRE_SEG_(\d{6})_(START|END)\]\]")
MARKER_RE = re.compile(r"\[\[[A-Z]+_\d{3}\]\]")


@dataclass
class PDFTextBlock:
    page: int
    bbox: tuple[float, float, float, float]
    text: str
    fontsize: float
    flags: int
    color: int
    kind: str = "text"


def _block_text(block: dict) -> str:
    lines: list[str] = []
    for line in block.get("lines", []):
        spans = line.get("spans", [])
        lines.append("".join(str(span.get("text", "")) for span in spans).rstrip())
    return "\n".join(lines).strip()


def _rect_center_inside(rect: tuple[float, float, float, float], container) -> bool:
    x0, y0, x1, y1 = rect
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2
    return container.x0 <= cx <= container.x1 and container.y0 <= cy <= container.y1


def _extract_pdf_blocks(doc) -> list[PDFTextBlock]:
    """Extract ordinary text plus PDF tables as independent cell blocks.

    A table is intentionally handled before ordinary blocks. PDF table text can
    be emitted by the PDF engine as one large block spanning several columns;
    translating that block and putting it back into one bbox is what caused the
    previous reconstruction to collapse table content into the first column.
    """
    blocks: list[PDFTextBlock] = []
    table_regions_by_page: dict[int, list] = {}

    for page_index, page in enumerate(doc):
        try:
            finder = page.find_tables()
            tables = list(getattr(finder, "tables", []) or [])
        except Exception:
            tables = []

        regions: list = []
        for table in tables:
            cells = list(getattr(table, "cells", []) or [])
            extracted = []
            try:
                extracted = table.extract() or []
            except Exception:
                extracted = []
            if not cells or not extracted:
                continue

            # PyMuPDF exposes cells in row-major order. Keep the cell rectangle
            # paired with its row/column text and skip empty/merged cells.
            cell_index = 0
            for row in extracted:
                for cell_text in row:
                    if cell_index >= len(cells):
                        break
                    cell_rect = cells[cell_index]
                    cell_index += 1
                    if not cell_rect or not str(cell_text or "").strip():
                        continue
                    rect = tuple(float(x) for x in cell_rect)
                    clip = page.get_text("dict", clip=page.rect.__class__(rect), sort=True)
                    spans = [
                        span
                        for b in clip.get("blocks", [])
                        for line in b.get("lines", [])
                        for span in line.get("spans", [])
                        if span.get("text")
                    ]
                    first = spans[0] if spans else {}
                    blocks.append(
                        PDFTextBlock(
                            page=page_index,
                            bbox=rect,
                            text=str(cell_text).strip(),
                            fontsize=float(first.get("size", 9.0) or 9.0),
                            flags=int(first.get("flags", 0) or 0),
                            color=int(first.get("color", 0) or 0),
                            kind="table_cell",
                        )
                    )
            try:
                regions.append(page.rect.__class__(table.bbox))
            except Exception:
                if cells:
                    xs = [c[0] for c in cells if c]
                    ys = [c[1] for c in cells if c]
                    xe = [c[2] for c in cells if c]
                    ye = [c[3] for c in cells if c]
                    if xs:
                        regions.append(page.rect.__class__(min(xs), min(ys), max(xe), max(ye)))
        table_regions_by_page[page_index] = regions

    for page_index, page in enumerate(doc):
        data = page.get_text("dict", sort=True)
        regions = table_regions_by_page.get(page_index, [])
        for block in data.get("blocks", []):
            if block.get("type") != 0 or not block.get("lines"):
                continue
            text = _block_text(block)
            if not text:
                continue
            bbox = tuple(float(x) for x in block["bbox"])
            # Do not add a large table block when its center is already covered
            # by a detected table. Its cells above are the authoritative layout.
            if any(_rect_center_inside(bbox, region) for region in regions):
                continue
            spans = [
                span
                for line in block.get("lines", [])
                for span in line.get("spans", [])
                if span.get("text")
            ]
            if not spans:
                continue
            first = spans[0]
            blocks.append(
                PDFTextBlock(
                    page=page_index,
                    bbox=bbox,
                    text=text,
                    fontsize=float(first.get("size", 10.0) or 10.0),
                    flags=int(first.get("flags", 0) or 0),
                    color=int(first.get("color", 0) or 0),
                    kind="text",
                )
            )

    # Reading order: page, then vertical position, then horizontal position.
    blocks.sort(key=lambda b: (b.page, b.bbox[1], b.bbox[0]))
    return blocks


def _marker_sequence(text: str) -> list[str]:
    return MARKER_RE.findall(text)


def _build_document_prompt(source_lang: str, target_lang: str, segments: list[tuple[str, str]]) -> str:
    body: list[str] = []
    for marker, protected in segments:
        body.append(f"[[SUMIRE_SEG_{marker}_START]]")
        body.append(protected)
        body.append(f"[[SUMIRE_SEG_{marker}_END]]")
    return f"""You are a professional academic and scientific document translator.
Translate from {language_name(source_lang)} to {language_name(target_lang)}.

This is a layout-preserving document job. Each SEGMENT corresponds to one
visual text block or one PDF table cell. Translate only natural language inside
that segment.

ABSOLUTE RULES:
1. Every segment START and END marker must be reproduced exactly, in exactly the
   same order. Never add, remove, rename, merge or reorder them.
2. Every protected marker such as [[MATH_001]], [[NUMBER_002]], [[TABLE_003]],
   [[CODE_004]], [[URL_005]] or [[CITE_006]] must be reproduced exactly and in
   the same order inside its segment.
3. Never translate or modify formulas, variables, mathematical symbols,
   numbers, code, URLs, citations or protected table content.
4. Preserve line breaks inside a segment whenever practical.
5. Do not add explanations, notes, headings or commentary.
6. Output only the segmented translated document.

DOCUMENT SEGMENTS:
{chr(10).join(body)}

OUTPUT ONLY THE TRANSLATION."""


def _translate_segments(segments: list[tuple[str, str]], source_lang: str, target_lang: str, translate_fn: TranslateFn) -> tuple[list[str], dict]:
    if not segments:
        return [], {"passed": True, "issues": []}

    prepared: list[tuple[str, str, dict[str, ProtectedElement]]] = []
    source_by_id: dict[str, str] = {}
    for segment_id, text in segments:
        protected, store, _ = protect_text(text)
        prepared.append((segment_id, protected, store))
        source_by_id[segment_id] = text

    prompt = _build_document_prompt(source_lang, target_lang, [(sid, protected) for sid, protected, _ in prepared])
    translated = translate_fn(prompt)

    expected_tokens: list[str] = []
    for segment_id, protected, _ in prepared:
        expected_tokens.append(f"[[SUMIRE_SEG_{segment_id}_START]]")
        expected_tokens.extend(_marker_sequence(protected))
        expected_tokens.append(f"[[SUMIRE_SEG_{segment_id}_END]]")

    actual_all_markers = re.findall(r"\[\[[A-Z_]+_\d{3,6}(?:_(?:START|END))?\]\]", translated)
    if actual_all_markers != expected_tokens:
        raise RuntimeError("La traducción fue bloqueada: el modelo alteró la estructura protegida del documento.")

    outputs: list[str] = []
    validation_issues: list[dict] = []
    for segment_id, original_protected, store in prepared:
        start = f"[[SUMIRE_SEG_{segment_id}_START]]"
        end = f"[[SUMIRE_SEG_{segment_id}_END]]"
        start_pos = translated.find(start)
        end_pos = translated.find(end, start_pos + len(start))
        if start_pos < 0 or end_pos < 0:
            raise RuntimeError("La traducción fue bloqueada: falta un delimitador de segmento.")
        segment_output = translated[start_pos + len(start):end_pos].strip("\n")
        if _marker_sequence(segment_output) != _marker_sequence(original_protected):
            validation_issues.append({"segment": segment_id, "type": "marker_sequence_changed"})
            continue
        restored = restore_markers(segment_output, store)
        validation = validate(source_by_id[segment_id], restored, store, protected_source=original_protected, translated_protected=segment_output)
        if not validation["passed"]:
            validation_issues.append({"segment": segment_id, "issues": validation["issues"]})
            continue
        outputs.append(restored)

    if validation_issues:
        raise RuntimeError("La traducción fue bloqueada por la validación estructural del documento.")
    return outputs, {"passed": True, "issues": []}


def _aggregate_counts(texts: list[str]) -> dict:
    total = translatable = protected = protected_words = 0
    by_type: dict[str, int] = {}
    for text in texts:
        counts = count_words(text)
        total += int(counts["total"])
        translatable += int(counts["translatable"])
        protected += int(counts["protected"])
        protected_words += int(counts.get("protectedWords", 0))
        for kind, amount in counts.get("protectedByType", {}).items():
            by_type[kind] = by_type.get(kind, 0) + int(amount)
    return {"total": total, "translatable": translatable, "protected": protected, "protectedWords": protected_words, "protectedRatio": protected_words / total if total else 0.0, "protectedByType": dict(sorted(by_type.items()))}


def _pdf_color(value: int) -> tuple[float, float, float]:
    return ((value >> 16 & 255) / 255.0, (value >> 8 & 255) / 255.0, (value & 255) / 255.0)


def _pdf_font_name(flags: int) -> str:
    bold = bool(flags & 16)
    italic = bool(flags & 2)
    if bold and italic:
        return "figbi"
    if bold:
        return "figbo"
    if italic:
        return "figit"
    return "figo"


def _insert_pdf_text_fitted(page, rect, text: str, block: PDFTextBlock) -> float:
    fontsize = max(5.5, min(block.fontsize, 24.0))
    fontname = _pdf_font_name(block.flags)
    while fontsize >= 4.0:
        rc = page.insert_textbox(rect, text, fontname=fontname, fontsize=fontsize, color=_pdf_color(block.color), overlay=True)
        if rc >= 0:
            return fontsize
        fontsize -= 0.5
    raise RuntimeError("La reconstrucción fue bloqueada: un bloque traducido no cabe en su región original.")


def _validate_final_pdf(output: bytes, blocks: list[PDFTextBlock]) -> dict:
    import pymupdf
    result = pymupdf.open(stream=output, filetype="pdf")
    extracted = "\n".join(page.get_text("text") for page in result)
    result.close()
    issues: list[dict] = []
    checked = 0
    for block in blocks:
        _, store, _ = protect_text(block.text)
        for item in store.values():
            checked += 1
            if item.original not in extracted:
                issues.append({"type": "protected_content_missing_in_pdf", "page": block.page + 1, "kind": item.type, "original": item.original})
                if len(issues) >= 20:
                    break
        if len(issues) >= 20:
            break
    return {"passed": not issues, "checked": checked, "issues": issues}


def translate_pdf_document(path: str | Path, source_lang: str, target_lang: str, translate_fn: TranslateFn, *, batch_size: int = 18) -> tuple[bytes, dict]:
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("Falta PyMuPDF. La dependencia está declarada en requirements.txt.") from exc

    source = pymupdf.open(str(path))
    page_count = source.page_count
    blocks = _extract_pdf_blocks(source)
    if not blocks:
        source.close()
        raise RuntimeError("Este PDF no contiene texto seleccionable. Para PDF escaneados necesitamos OCR.")

    original_texts = [block.text for block in blocks]
    translated_texts: list[str] = []
    for start in range(0, len(blocks), batch_size):
        batch = blocks[start:start + batch_size]
        segment_inputs = [(f"{index:06d}", block.text) for index, block in enumerate(batch, start=start + 1)]
        batch_outputs, _ = _translate_segments(segment_inputs, source_lang, target_lang, translate_fn)
        translated_texts.extend(batch_outputs)

    if len(translated_texts) != len(blocks):
        source.close()
        raise RuntimeError("La traducción no produjo todos los bloques del documento.")

    # Redact only text. images and vector graphics are deliberately retained.
    for block in blocks:
        source[block.page].add_redact_annot(pymupdf.Rect(block.bbox), fill=False, cross_out=False)
    for page in source:
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE, text=pymupdf.PDF_REDACT_TEXT_REMOVE)

    for block, translated in zip(blocks, translated_texts):
        page = source[block.page]
        rect = pymupdf.Rect(block.bbox)
        # Cell blocks get a little horizontal/vertical breathing room but never
        # cross their cell boundary, preventing text from entering the next col.
        if block.kind == "table_cell":
            rect = pymupdf.Rect(rect.x0 + 1, rect.y0 + 0.5, rect.x1 - 1, rect.y1 + 0.5)
        else:
            rect = pymupdf.Rect(rect.x0, rect.y0 - 0.5, rect.x1, rect.y1 + max(1.0, block.fontsize * 0.18))
        _insert_pdf_text_fitted(page, rect, translated, block)

    output = source.tobytes(garbage=4, deflate=True, clean=True)
    source.close()
    final_validation = _validate_final_pdf(output, blocks)
    if not final_validation["passed"]:
        raise RuntimeError("La reconstrucción PDF fue bloqueada: la validación final detectó contenido protegido que no sobrevivió al renderizado.")

    return output, {"format": "pdf", "pages": page_count, "textBlocks": len(blocks), "counts": _aggregate_counts(original_texts), "validation": final_validation}


def _run_has_drawing(run) -> bool:
    """True for a Word run containing an inline/floating image or drawing."""
    return bool(run._r.xpath(".//*[local-name()='drawing' or local-name()='pict' or local-name()='object']"))


def _translate_docx_paragraphs(document, source_lang: str, target_lang: str, translate_fn: TranslateFn):
    texts: list[str] = []
    locations = []

    def add_paragraph(paragraph) -> None:
        text = paragraph.text.strip()
        if text:
            texts.append(text)
            locations.append(paragraph)

    for paragraph in document.paragraphs:
        add_paragraph(paragraph)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    add_paragraph(paragraph)

    translated: list[str] = []
    for start in range(0, len(texts), 18):
        batch = texts[start:start + 18]
        segment_inputs = [(f"{i:06d}", text) for i, text in enumerate(batch, start=start + 1)]
        outputs, _ = _translate_segments(segment_inputs, source_lang, target_lang, translate_fn)
        translated.extend(outputs)

    for paragraph, value in zip(locations, translated):
        # Never assign run.text on a run containing a drawing: python-docx would
        # replace the run XML and remove its image. Translate text-only runs and
        # leave drawing runs byte-for-byte in the document structure.
        text_runs = [run for run in paragraph.runs if not _run_has_drawing(run)]
        if text_runs:
            text_runs[0].text = value
            for run in text_runs[1:]:
                run.text = ""
        else:
            # A paragraph containing only an image must remain untouched.
            continue
    return texts, translated


def translate_docx_document(path: str | Path, source_lang: str, target_lang: str, translate_fn: TranslateFn) -> tuple[bytes, dict]:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("Falta python-docx. La dependencia está declarada en requirements.txt.") from exc

    document = Document(str(path))
    original_texts, _ = _translate_docx_paragraphs(document, source_lang, target_lang, translate_fn)
    output_path = Path(path).with_name(f"{Path(path).stem}_sumire_temp.docx")
    try:
        document.save(str(output_path))
        output = output_path.read_bytes()
    finally:
        try:
            output_path.unlink()
        except OSError:
            pass
    return output, {"format": "docx", "textBlocks": len(original_texts), "counts": _aggregate_counts(original_texts), "validation": {"passed": True, "checked": len(original_texts), "issues": []}}


def translate_document(path: str | Path, source_lang: str, target_lang: str, translate_fn: TranslateFn) -> tuple[bytes, str, dict]:
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        data, info = translate_pdf_document(path, source_lang, target_lang, translate_fn)
        return data, "pdf", info
    if suffix == ".docx":
        data, info = translate_docx_document(path, source_lang, target_lang, translate_fn)
        return data, "docx", info
    raise ValueError(f"Reconstrucción no disponible para: {suffix or '(sin extensión)'}")
