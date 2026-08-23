"""Layout-preserving PDF/DOCX translation for Sumire Translate."""
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


def _markers(text: str) -> list[str]:
    return MARKER_RE.findall(text)


def _prompt(source_lang: str, target_lang: str, segments: list[tuple[str, str]]) -> str:
    body = []
    for sid, text in segments:
        body.extend([f"[[SUMIRE_SEG_{sid}_START]]", text, f"[[SUMIRE_SEG_{sid}_END]]"])
    return f"""You are a professional academic and scientific document translator.
Translate from {language_name(source_lang)} to {language_name(target_lang)}.

Each segment is one visual paragraph, heading, caption or table cell.
Translate only natural language inside the segment.

STRICT RULES:
1. Preserve every SUMIRE_SEG START/END marker exactly and in the same order.
2. Preserve every protected marker exactly, including MATH, NUMBER, TABLE,
   CODE, URL and CITE markers.
3. Never translate or alter formulas, variables, numbers, symbols, code, URLs,
   citations or protected structural characters.
4. Never merge segments or move text between segments/cells.
5. Output only the translated segments. No explanations.

SEGMENTS:
{chr(10).join(body)}

OUTPUT ONLY THE TRANSLATION."""


def _translate_segments(segments: list[tuple[str, str]], source_lang: str, target_lang: str, translate_fn: TranslateFn) -> tuple[list[str], dict]:
    if not segments:
        return [], {"passed": True, "checked": 0, "issues": []}
    prepared: list[tuple[str, str, dict[str, ProtectedElement]]] = []
    originals: dict[str, str] = {}
    for sid, text in segments:
        protected, store, _ = protect_text(text)
        prepared.append((sid, protected, store))
        originals[sid] = text

    translated = translate_fn(_prompt(source_lang, target_lang, [(sid, p) for sid, p, _ in prepared]))
    expected = []
    for sid, protected, _ in prepared:
        expected.extend([f"[[SUMIRE_SEG_{sid}_START]]", *_markers(protected), f"[[SUMIRE_SEG_{sid}_END]]"])
    stream = re.findall(r"\[\[(?:SUMIRE_SEG_\d{6}_(?:START|END)|[A-Z]+_\d{3})\]\]", translated)
    if stream != expected:
        raise RuntimeError("La traducción fue bloqueada: Gemini alteró la estructura protegida del documento.")

    outputs = []
    issues = []
    cursor = 0
    for sid, protected, store in prepared:
        start_marker = f"[[SUMIRE_SEG_{sid}_START]]"
        end_marker = f"[[SUMIRE_SEG_{sid}_END]]"
        a = translated.find(start_marker, cursor)
        b = translated.find(end_marker, a + len(start_marker))
        if a < 0 or b < 0:
            issues.append({"segment": sid, "type": "missing_segment"})
            continue
        part = translated[a + len(start_marker):b].strip("\n")
        cursor = b + len(end_marker)
        if _markers(part) != _markers(protected):
            issues.append({"segment": sid, "type": "marker_sequence_changed"})
            continue
        restored = restore_markers(part, store)
        check = validate(originals[sid], restored, store, protected_source=protected, translated_protected=part)
        if not check["passed"]:
            issues.append({"segment": sid, "issues": check["issues"]})
            continue
        outputs.append(restored)
    if issues:
        raise RuntimeError("La traducción fue bloqueada por la validación estructural del documento.")
    return outputs, {"passed": True, "checked": len(outputs), "issues": []}


def _aggregate_counts(texts: list[str]) -> dict:
    total = translatable = protected = protected_words = 0
    by_type: dict[str, int] = {}
    for text in texts:
        c = count_words(text)
        total += int(c.get("total", 0))
        translatable += int(c.get("translatable", 0))
        protected += int(c.get("protected", 0))
        protected_words += int(c.get("protectedWords", 0))
        for kind, n in c.get("protectedByType", {}).items():
            by_type[kind] = by_type.get(kind, 0) + int(n)
    return {"total": total, "translatable": translatable, "protected": protected,
            "protectedWords": protected_words, "protectedRatio": protected_words / total if total else 0,
            "protectedByType": dict(sorted(by_type.items()))}


def _block_text(block: dict) -> str:
    return "\n".join("".join(str(s.get("text", "")) for s in line.get("spans", [])).rstrip() for line in block.get("lines", [])).strip()


def _inside(rect, region) -> bool:
    cx = (rect[0] + rect[2]) / 2
    cy = (rect[1] + rect[3]) / 2
    return region.x0 <= cx <= region.x1 and region.y0 <= cy <= region.y1


def _grid_edges(cells, axis: int) -> list[float]:
    values = []
    for cell in cells:
        if cell is not None:
            values.extend([float(cell[axis]), float(cell[axis + 2])])
    return sorted(set(round(v, 3) for v in values))


def _table_cell_rect(table, row_index: int, col_index: int, row_count: int, col_count: int):
    """Return the geometry of exactly one table cell.

    Priority:
    1. Use PyMuPDF's own cell geometry for the exact row/column.
    2. If that position is a merged/None cell, reconstruct the grid from the
       table bounding box and the calculated number of rows/columns.

    This deliberately avoids assigning cells from a flat sequence of text.
    Every non-empty cell is therefore translated and rendered back into its
    own row/column position.
    """
    import pymupdf

    cells = list(getattr(table, "cells", []) or [])
    direct_index = row_index * col_count + col_index
    if 0 <= direct_index < len(cells):
        cell = cells[direct_index]
        if cell is not None:
            rect = pymupdf.Rect(cell)
            if rect.width > 0 and rect.height > 0:
                return rect

    # Merged cells or unusual table geometries: use the table dimensions as a
    # deterministic grid. This is safer than letting a missing cell shift all
    # following columns.
    bbox = pymupdf.Rect(table.bbox)
    width = bbox.width / max(col_count, 1)
    height = bbox.height / max(row_count, 1)
    return pymupdf.Rect(
        bbox.x0 + col_index * width,
        bbox.y0 + row_index * height,
        bbox.x0 + (col_index + 1) * width,
        bbox.y0 + (row_index + 1) * height,
    )


def _extract_pdf_blocks(doc) -> list[PDFTextBlock]:
    import pymupdf
    blocks: list[PDFTextBlock] = []
    table_regions: dict[int, list] = {}

    for pi, page in enumerate(doc):
        regions = []
        try:
            finder = page.find_tables()
            tables = list(getattr(finder, "tables", []) or [])
        except Exception:
            tables = []
        for table in tables:
            extracted = table.extract() or []
            if not extracted:
                continue
            row_count = len(extracted)
            col_count = max((len(row) for row in extracted), default=0)
            if not col_count:
                continue

            # IMPORTANT: each non-empty cell becomes an independent translation
            # segment. The table dimensions are calculated first, then every
            # row/column is inspected separately.
            for ri in range(row_count):
                row = extracted[ri]
                for ci in range(col_count):
                    value = row[ci] if ci < len(row) else None
                    if value is None or not str(value).strip():
                        continue
                    rect = _table_cell_rect(table, ri, ci, row_count, col_count)
                    clip = page.get_text("dict", clip=rect, sort=True)
                    spans = [
                        s for b in clip.get("blocks", [])
                        for l in b.get("lines", [])
                        for s in l.get("spans", [])
                        if s.get("text")
                    ]
                    first = spans[0] if spans else {}
                    blocks.append(
                        PDFTextBlock(
                            pi,
                            (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)),
                            str(value).strip(),
                            float(first.get("size", 9) or 9),
                            int(first.get("flags", 0) or 0),
                            int(first.get("color", 0) or 0),
                            "table_cell",
                        )
                    )
            try:
                regions.append(pymupdf.Rect(table.bbox))
            except Exception:
                pass
        table_regions[pi] = regions

    for pi, page in enumerate(doc):
        for block in page.get_text("dict", sort=True).get("blocks", []):
            if block.get("type") != 0 or not block.get("lines"):
                continue
            text = _block_text(block)
            if not text:
                continue
            bbox = tuple(float(x) for x in block["bbox"])
            if any(_inside(bbox, r) for r in table_regions.get(pi, [])):
                continue
            spans = [s for l in block.get("lines", []) for s in l.get("spans", []) if s.get("text")]
            if not spans:
                continue
            first = spans[0]
            blocks.append(PDFTextBlock(pi, bbox, text, float(first.get("size", 10) or 10), int(first.get("flags", 0) or 0), int(first.get("color", 0) or 0)))
    blocks.sort(key=lambda b: (b.page, b.bbox[1], b.bbox[0]))
    return blocks


def _font(flags: int) -> str:
    bold = bool(flags & 16)
    italic = bool(flags & 2)
    return "figbi" if bold and italic else "figbo" if bold else "figit" if italic else "figo"


def _insert_pdf(page, rect, text, block: PDFTextBlock):
    color = (((block.color >> 16) & 255) / 255, ((block.color >> 8) & 255) / 255, (block.color & 255) / 255)
    size = max(5.0, min(block.fontsize, 24.0))
    while size >= 4:
        rc = page.insert_textbox(rect, text, fontname=_font(block.flags), fontsize=size, color=color, overlay=True)
        if rc >= 0:
            return
        size -= 0.5
    raise RuntimeError("La reconstrucción PDF fue bloqueada: el texto traducido no cabe en su región original.")


def _validate_final_pdf(output: bytes, rendered_blocks: list[tuple[PDFTextBlock, str]]) -> dict:
    import pymupdf
    result = pymupdf.open(stream=output, filetype="pdf")
    extracted = [page.get_text("text") for page in result]
    checked = 0
    warnings = []
    for block, _ in rendered_blocks:
        _, store, _ = protect_text(block.text)
        page_text = extracted[block.page] if block.page < len(extracted) else ""
        for item in store.values():
            checked += 1
            original = re.sub(r"\s+", "", item.original)
            if original and original not in re.sub(r"\s+", "", page_text):
                warnings.append({"type": "protected_content_not_extractable", "page": block.page + 1, "kind": item.type})
    pages = len(extracted)
    result.close()
    return {"passed": True, "checked": checked, "issues": warnings[:20], "renderedPages": pages}


def translate_pdf_document(path: str | Path, source_lang: str, target_lang: str, translate_fn: TranslateFn, *, batch_size: int = 18):
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("Falta PyMuPDF. Declara pymupdf en requirements.txt.") from exc
    source = pymupdf.open(str(path))
    try:
        blocks = _extract_pdf_blocks(source)
        if not blocks:
            raise RuntimeError("Este PDF no contiene texto seleccionable. Para PDF escaneados necesitamos OCR.")
        originals = [b.text for b in blocks]
        translated_texts: list[str] = []
        for start in range(0, len(blocks), batch_size):
            batch = blocks[start:start + batch_size]
            outs, _ = _translate_segments([(f"{i:06d}", b.text) for i, b in enumerate(batch, start=start + 1)], source_lang, target_lang, translate_fn)
            translated_texts.extend(outs)
        if len(translated_texts) != len(blocks):
            raise RuntimeError("La traducción no produjo todos los bloques del PDF.")

        for b in blocks:
            source[b.page].add_redact_annot(pymupdf.Rect(b.bbox), fill=False, cross_out=False)
        for page in source:
            page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                                  graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                                  text=pymupdf.PDF_REDACT_TEXT_REMOVE)

        rendered = []
        for b, translated in zip(blocks, translated_texts):
            page = source[b.page]
            r = pymupdf.Rect(b.bbox)
            if b.kind == "table_cell":
                r = pymupdf.Rect(r.x0 + 1, r.y0 + .5, r.x1 - 1, r.y1 + .5)
            else:
                r = pymupdf.Rect(r.x0, r.y0 - .5, r.x1, r.y1 + max(1, b.fontsize * .18))
            _insert_pdf(page, r, translated, b)
            rendered.append((b, translated))
        output = source.tobytes(garbage=4, deflate=True, clean=True)
        validation = _validate_final_pdf(output, rendered)
        return output, {"format": "pdf", "pages": len(set(b.page for b in blocks)), "textBlocks": len(blocks), "counts": _aggregate_counts(originals), "validation": validation}
    finally:
        source.close()


def _run_has_drawing(run) -> bool:
    try:
        return bool(run._r.xpath(".//*[local-name()='drawing' or local-name()='pict' or local-name()='object']"))
    except Exception:
        return False


def _iter_table_paragraphs(table):
    for row in table.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                yield p
            for nested in cell.tables:
                yield from _iter_table_paragraphs(nested)


def _paragraphs_in_document(document):
    seen = set()
    def emit(p):
        key = id(p._p)
        if key not in seen:
            seen.add(key)
            yield p
    for p in document.paragraphs:
        yield from emit(p)
    for table in document.tables:
        for p in _iter_table_paragraphs(table):
            yield from emit(p)
    for section in document.sections:
        for part in (section.header, section.first_page_header, section.even_page_header,
                     section.footer, section.first_page_footer, section.even_page_footer):
            for p in part.paragraphs:
                yield from emit(p)
            for table in part.tables:
                for p in _iter_table_paragraphs(table):
                    yield from emit(p)


def _replace_paragraph_text_preserving_drawings(paragraph, value: str):
    """Replace text only; never remove image/drawing XML from the DOCX."""
    text_runs = [r for r in paragraph.runs if not _run_has_drawing(r)]
    if not text_runs:
        return
    text_runs[0].text = value
    for r in text_runs[1:]:
        r.text = ""


def translate_docx_document(path: str | Path, source_lang: str, target_lang: str, translate_fn: TranslateFn):
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("Falta python-docx. Declara python-docx en requirements.txt.") from exc

    # IMPORTANT: python-docx Document has no close() method. It is an OOXML
    # package loaded in memory; save() is sufficient and avoids the crash that
    # was appearing as: 'Document' object has no attribute 'close'.
    document = Document(str(path))
    locations = []
    originals = []
    for p in _paragraphs_in_document(document):
        text = p.text.strip()
        if text:
            locations.append(p)
            originals.append(text)

    translated: list[str] = []
    for start in range(0, len(originals), 18):
        batch = originals[start:start + 18]
        outs, _ = _translate_segments([(f"{i:06d}", t) for i, t in enumerate(batch, start=start + 1)], source_lang, target_lang, translate_fn)
        translated.extend(outs)

    for p, value in zip(locations, translated):
        _replace_paragraph_text_preserving_drawings(p, value)

    output_path = Path(path).with_name(f"{Path(path).stem}_sumire_temp.docx")
    try:
        document.save(str(output_path))
        output = output_path.read_bytes()
    finally:
        try:
            output_path.unlink()
        except OSError:
            pass

    return output, {"format": "docx", "textBlocks": len(originals), "counts": _aggregate_counts(originals),
                    "validation": {"passed": True, "checked": len(originals), "issues": []},
                    "translatedText": "\n\n".join(translated)}


def translate_document(path: str | Path, source_lang: str, target_lang: str, translate_fn: TranslateFn):
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return translate_pdf_document(path, source_lang, target_lang, translate_fn)
    if suffix == ".docx":
        return translate_docx_document(path, source_lang, target_lang, translate_fn)
    raise ValueError(f"Formato de documento no soportado: {suffix or '(sin extensión)'}")
