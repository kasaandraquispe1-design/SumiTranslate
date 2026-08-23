"""Layout-preserving PDF/DOCX translation for Sumire Translate.

The source document is the visual source of truth. Translation happens per
visual text block/cell, while images, drawings and document containers are kept.
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
MARKER_RE = re.compile(r"\[\[[A-Z]+_\d{3}\]\]")
SEG_RE = re.compile(r"\[\[SUMIRE_SEG_(\d{6})_(START|END)\]\]")

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
        body += [f"[[SUMIRE_SEG_{sid}_START]]", text, f"[[SUMIRE_SEG_{sid}_END]]"]
    return f"""You are a professional academic and scientific document translator.
Translate from {language_name(source_lang)} to {language_name(target_lang)}.

Each segment represents one visual paragraph, table cell, caption, heading or
other text region. Translate only natural language.

STRICT RULES:
1. Preserve every SUMIRE_SEG START/END marker exactly and in the same order.
2. Preserve every protected marker such as [[MATH_001]], [[NUMBER_002]],
   [[TABLE_003]], [[CODE_004]], [[URL_005]] and [[CITE_006]] exactly.
3. Never translate or alter formulas, variables, numbers, symbols, code, URLs,
   citations or protected structural characters.
4. Do not merge segments or move text between segments.
5. Do not add explanations or commentary. Output only the translated segments.

SEGMENTS:
{chr(10).join(body)}

OUTPUT ONLY THE TRANSLATION."""


def _translate_segments(segments: list[tuple[str, str]], source_lang: str, target_lang: str, translate_fn: TranslateFn) -> tuple[list[str], dict]:
    if not segments:
        return [], {"passed": True, "checked": 0, "issues": []}
    prepared: list[tuple[str, str, dict[str, ProtectedElement]]] = []
    original_by_id: dict[str, str] = {}
    for sid, text in segments:
        protected, store, _ = protect_text(text)
        prepared.append((sid, protected, store))
        original_by_id[sid] = text

    translated = translate_fn(_prompt(source_lang, target_lang, [(sid, p) for sid, p, _ in prepared]))
    expected: list[str] = []
    for sid, protected, _ in prepared:
        expected += [f"[[SUMIRE_SEG_{sid}_START]]"] + _markers(protected) + [f"[[SUMIRE_SEG_{sid}_END]]"]
    stream = re.findall(r"\[\[(?:SUMIRE_SEG_\d{6}_(?:START|END)|[A-Z]+_\d{3})\]\]", translated)
    if stream != expected:
        raise RuntimeError("La traducción fue bloqueada: el modelo alteró la estructura protegida del documento.")

    outputs: list[str] = []
    issues: list[dict] = []
    cursor = 0
    for sid, protected, store in prepared:
        start = f"[[SUMIRE_SEG_{sid}_START]]"
        end = f"[[SUMIRE_SEG_{sid}_END]]"
        a = translated.find(start, cursor)
        b = translated.find(end, a + len(start))
        if a < 0 or b < 0:
            issues.append({"segment": sid, "type": "missing_segment"})
            continue
        part = translated[a + len(start):b].strip("\n")
        cursor = b + len(end)
        if _markers(part) != _markers(protected):
            issues.append({"segment": sid, "type": "marker_sequence_changed"})
            continue
        restored = restore_markers(part, store)
        check = validate(original_by_id[sid], restored, store, protected_source=protected, translated_protected=part)
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
        total += int(c.get("total", 0)); translatable += int(c.get("translatable", 0))
        protected += int(c.get("protected", 0)); protected_words += int(c.get("protectedWords", 0))
        for kind, n in c.get("protectedByType", {}).items(): by_type[kind] = by_type.get(kind, 0) + int(n)
    return {"total": total, "translatable": translatable, "protected": protected,
            "protectedWords": protected_words, "protectedRatio": protected_words / total if total else 0,
            "protectedByType": dict(sorted(by_type.items()))}


def _block_text(block: dict) -> str:
    return "\n".join("".join(str(s.get("text", "")) for s in line.get("spans", [])).rstrip() for line in block.get("lines", [])).strip()


def _inside(rect, region) -> bool:
    cx = (rect[0] + rect[2]) / 2; cy = (rect[1] + rect[3]) / 2
    return region.x0 <= cx <= region.x1 and region.y0 <= cy <= region.y1


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
            cells = list(getattr(table, "cells", []) or [])
            if not extracted or not cells:
                continue
            # Keep the exact row/column cell rectangle. Merged/empty cells are
            # represented by None and must not shift the following columns.
            cell_i = 0
            for row in extracted:
                for value in row:
                    if cell_i >= len(cells):
                        break
                    rect_data = cells[cell_i]
                    cell_i += 1
                    if rect_data is None or value is None or not str(value).strip():
                        continue
                    rect = tuple(float(x) for x in rect_data)
                    clip = page.get_text("dict", clip=pymupdf.Rect(rect), sort=True)
                    spans = [s for b in clip.get("blocks", []) for l in b.get("lines", []) for s in l.get("spans", []) if s.get("text")]
                    first = spans[0] if spans else {}
                    blocks.append(PDFTextBlock(pi, rect, str(value).strip(), float(first.get("size", 9) or 9), int(first.get("flags", 0) or 0), int(first.get("color", 0) or 0), "table_cell"))
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
    bold = bool(flags & 16); italic = bool(flags & 2)
    return "figbi" if bold and italic else "figbo" if bold else "figit" if italic else "figo"


def _insert_pdf(page, rect, text, block: PDFTextBlock):
    color = ((block.color >> 16 & 255) / 255, (block.color >> 8 & 255) / 255, (block.color & 255) / 255)
    size = max(5.0, min(block.fontsize, 24.0))
    while size >= 4:
        rc = page.insert_textbox(rect, text, fontname=_font(block.flags), fontsize=size, color=color, overlay=True)
        if rc >= 0:
            return
        size -= 0.5
    raise RuntimeError("La reconstrucción fue bloqueada: el texto traducido no cabe en su región original.")


def _validate_final_pdf(output: bytes, rendered_blocks: list[tuple[PDFTextBlock, str]]) -> dict:
    import pymupdf
    result = pymupdf.open(stream=output, filetype="pdf")
    extracted = [page.get_text("text") for page in result]
    checked = 0; warnings = []
    for block, _ in rendered_blocks:
        _, store, _ = protect_text(block.text)
        page_text = extracted[block.page] if block.page < len(extracted) else ""
        for item in store.values():
            checked += 1
            # Keep this as a warning: PDF font extraction can differ from the
            # visual glyphs even when the content was correctly restored before rendering.
            if re.sub(r"\s+", "", item.original) not in re.sub(r"\s+", "", page_text):
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
    blocks = _extract_pdf_blocks(source)
    if not blocks:
        source.close(); raise RuntimeError("Este PDF no contiene texto seleccionable. Para PDF escaneados necesitamos OCR.")
    originals = [b.text for b in blocks]
    translated_texts: list[str] = []
    for start in range(0, len(blocks), batch_size):
        batch = blocks[start:start + batch_size]
        outs, _ = _translate_segments([(f"{i:06d}", b.text) for i, b in enumerate(batch, start=start + 1)], source_lang, target_lang, translate_fn)
        translated_texts.extend(outs)
    if len(translated_texts) != len(blocks):
        source.close(); raise RuntimeError("La traducción no produjo todos los bloques del documento.")

    for b in blocks:
        source[b.page].add_redact_annot(pymupdf.Rect(b.bbox), fill=False, cross_out=False)
    for page in source:
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE, text=pymupdf.PDF_REDACT_TEXT_REMOVE)
    rendered = []
    for b, translated in zip(blocks, translated_texts):
        page = source[b.page]; r = pymupdf.Rect(b.bbox)
        if b.kind == "table_cell":
            r = pymupdf.Rect(r.x0 + 1, r.y0 + .5, r.x1 - 1, r.y1 + .5)
        else:
            r = pymupdf.Rect(r.x0, r.y0 - .5, r.x1, r.y1 + max(1, b.fontsize * .18))
        _insert_pdf(page, r, translated, b); rendered.append((b, translated))
    output = source.tobytes(garbage=4, deflate=True, clean=True)
    source.close()
    validation = _validate_final_pdf(output, rendered)
    return output, {"format": "pdf", "pages": len(set(b.page for b in blocks)), "textBlocks": len(blocks), "counts": _aggregate_counts(originals), "validation": validation}


def _run_has_drawing(run) -> bool:
    return bool(run._r.xpath(".//*[local-name()='drawing' or local-name()='pict' or local-name()='object']"))


def _paragraphs_in_document(document):
    seen = set()
    def emit(p):
        key = id(p._p)
        if key not in seen:
            seen.add(key); yield p
    for p in document.paragraphs:
        yield from emit(p)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    yield from emit(p)
    for section in document.sections:
        for part in (section.header, section.first_page_header, section.even_page_header, section.footer, section.first_page_footer, section.even_page_footer):
            for p in part.paragraphs:
                yield from emit(p)


def translate_docx_document(path: str | Path, source_lang: str, target_lang: str, translate_fn: TranslateFn):
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("Falta python-docx. Declara python-docx en requirements.txt.") from exc
    document = Document(str(path))
    locations = []; originals = []
    for p in _paragraphs_in_document(document):
        text = p.text.strip()
        if text:
            locations.append(p); originals.append(text)
    translated: list[str] = []
    for start in range(0, len(originals), 18):
        batch = originals[start:start + 18]
        outs, _ = _translate_segments([(f"{i:06d}", t) for i, t in enumerate(batch, start=start + 1)], source_lang, target_lang, translate_fn)
        translated.extend(outs)

    for p, value in zip(locations, translated):
        # Only text runs are edited. Drawing/image XML is left untouched.
        text_runs = [r for r in p.runs if not _run_has_drawing(r)]
        if not text_runs:
            continue
        text_runs[0].text = value
        for r in text_runs[1:]:
            r.text = ""

    # python-docx Document intentionally has no close() method.
    output_path = Path(path).with_name(f"{Path(path).stem}_sumire_temp.docx")
    try:
        document.save(str(output_path))
        output = output_path.read_bytes()
    finally:
        try: output_path.unlink()
        except OSError: pass
    return output, {"format": "docx", "textBlocks": len(originals), "counts": _aggregate_counts(originals), "validation": {"passed": True, "checked": len(originals), "issues": []}, "translatedText": "\n\n".join(translated)}


def translate_document(path: str | Path, source_lang: str, target_lang: str, translate_fn: TranslateFn):
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        data, info = translate_pdf_document(path, source_lang, target_lang, translate_fn)
        return data, "pdf", info
    if suffix == ".docx":
        data, info = translate_docx_document(path, source_lang, target_lang, translate_fn)
        return data, "docx", info
    raise ValueError(f"Reconstrucción no disponible para: {suffix or '(sin extensión)'}")
