"""Layout-aware document translation for Sumire Translate.

Phase 2 keeps the original document as the visual source of truth. PDF text is
translated block-by-block and written back into the original page coordinates;
images, vector drawings, page size and page count are retained. DOCX paragraphs
and table cells are translated in place so styles, numbering and embedded
images remain part of the document.
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
            # type 0 = text. Image blocks are deliberately ignored: they remain
            # untouched in the original PDF and are copied to the output.
            if block.get("type") != 0 or not block.get("lines"):
                continue
            text = _block_text(block)
            if not text:
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
                    bbox=tuple(float(x) for x in block["bbox"]),
                    text=text,
                    fontsize=float(first.get("size", 10.0) or 10.0),
                    flags=int(first.get("flags", 0) or 0),
                    color=int(first.get("color", 0) or 0),
                )
            )
    return blocks


def _marker_sequence(text: str) -> list[str]:
    return MARKER_RE.findall(text)


def _build_document_prompt(
    source_lang: str,
    target_lang: str,
    segments: list[tuple[str, str]],
) -> str:
    body: list[str] = []
    for marker, protected in segments:
        body.append(f"[[SUMIRE_SEG_{marker}_START]]")
        body.append(protected)
        body.append(f"[[SUMIRE_SEG_{marker}_END]]")
    return f"""You are a professional academic and scientific document translator.
Translate from {language_name(source_lang)} to {language_name(target_lang)}.

This is a layout-preserving document job. Each SEGMENT corresponds to one
visual text block in the original PDF/DOCX. Translate only the natural language
inside each segment.

ABSOLUTE RULES:
1. Every [[SUMIRE_SEG_XXXXXX_START]] and [[SUMIRE_SEG_XXXXXX_END]] marker must
   be reproduced exactly, in exactly the same order. Never add, remove, rename,
   merge or reorder segment markers.
2. Every protected marker such as [[MATH_001]], [[NUMBER_002]], [[TABLE_003]],
   [[CODE_004]], [[URL_005]] or [[CITE_006]] must be reproduced exactly and in
   the same order inside its segment.
3. Never translate or modify formulas, variables, mathematical symbols,
   numbers, code, URLs, citations or table delimiters represented by markers.
4. Preserve line breaks inside a segment whenever practical. Do not create a
   new paragraph or join two segments.
5. Do not add explanations, notes, headings or commentary.
6. Output only the segmented translated document.

DOCUMENT SEGMENTS:
{chr(10).join(body)}

OUTPUT ONLY THE TRANSLATION."""


def _translate_segments(
    segments: list[tuple[str, str]],
    source_lang: str,
    target_lang: str,
    translate_fn: TranslateFn,
) -> tuple[list[str], dict]:
    """Protect each segment, translate a batch, and fail closed on marker drift."""
    if not segments:
        return [], {"passed": True, "issues": []}

    prepared: list[tuple[str, str, dict[str, ProtectedElement]]] = []
    source_by_id: dict[str, str] = {}
    for segment_id, text in segments:
        protected, store, _ = protect_text(text)
        prepared.append((segment_id, protected, store))
        source_by_id[segment_id] = text

    prompt = _build_document_prompt(
        source_lang,
        target_lang,
        [(segment_id, protected) for segment_id, protected, _ in prepared],
    )
    translated = translate_fn(prompt)

    expected_tokens: list[str] = []
    for segment_id, protected, _ in prepared:
        expected_tokens.append(f"[[SUMIRE_SEG_{segment_id}_START]]")
        expected_tokens.extend(_marker_sequence(protected))
        expected_tokens.append(f"[[SUMIRE_SEG_{segment_id}_END]]")

    actual_all_markers = re.findall(
        r"\[\[[A-Z_]+_\d{3,6}(?:_(?:START|END))?\]\]", translated
    )
    if actual_all_markers != expected_tokens:
        raise RuntimeError(
            "La traducción fue bloqueada: el modelo alteró la estructura protegida "
            "del documento."
        )

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
        validation = validate(
            source_by_id[segment_id],
            restored,
            store,
            protected_source=original_protected,
            translated_protected=segment_output,
        )
        if not validation["passed"]:
            validation_issues.append({"segment": segment_id, "issues": validation["issues"]})
            continue
        outputs.append(restored)

    if validation_issues:
        raise RuntimeError(
            "La traducción fue bloqueada por la validación estructural del documento."
        )

    return outputs, {"passed": True, "issues": []}


def _aggregate_counts(texts: list[str]) -> dict:
    total = 0
    translatable = 0
    protected = 0
    protected_words = 0
    by_type: dict[str, int] = {}
    for text in texts:
        counts = count_words(text)
        total += int(counts["total"])
        translatable += int(counts["translatable"])
        protected += int(counts["protected"])
        protected_words += int(counts.get("protectedWords", 0))
        for kind, amount in counts.get("protectedByType", {}).items():
            by_type[kind] = by_type.get(kind, 0) + int(amount)
    return {
        "total": total,
        "translatable": translatable,
        "protected": protected,
        "protectedWords": protected_words,
        "protectedRatio": protected_words / total if total else 0.0,
        "protectedByType": dict(sorted(by_type.items())),
    }


def _pdf_color(value: int) -> tuple[float, float, float]:
    return ((value >> 16 & 255) / 255.0, (value >> 8 & 255) / 255.0, (value & 255) / 255.0)


def _pdf_font_name(flags: int) -> str:
    """Use FiraGO when available: it covers Latin and Greek better than Base-14."""
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
    """Insert translated text, shrinking until it fits or fail closed."""
    fontsize = max(5.5, min(block.fontsize, 24.0))
    fontname = _pdf_font_name(block.flags)
    while fontsize >= 4.0:
        rc = page.insert_textbox(
            rect,
            text,
            fontname=fontname,
            fontsize=fontsize,
            color=_pdf_color(block.color),
            overlay=True,
        )
        if rc >= 0:
            return fontsize
        # A failed insertion writes nothing according to PyMuPDF's contract,
        # so retrying with a smaller font is safe.
        fontsize -= 0.5
    raise RuntimeError(
        "La reconstrucción fue bloqueada: un bloque traducido no cabe en su región original."
    )


def _validate_final_pdf(output: bytes, blocks: list[PDFTextBlock]) -> dict:
    """Re-open the generated PDF and verify protected source spans survived."""
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
                issues.append({
                    "type": "protected_content_missing_in_pdf",
                    "page": block.page + 1,
                    "kind": item.type,
                    "original": item.original,
                })
                if len(issues) >= 20:
                    break
        if len(issues) >= 20:
            break

    return {"passed": not issues, "checked": checked, "issues": issues}


def translate_pdf_document(
    path: str | Path,
    source_lang: str,
    target_lang: str,
    translate_fn: TranslateFn,
    *,
    batch_size: int = 18,
) -> tuple[bytes, dict]:
    """Translate a PDF while retaining its original pages, images and graphics."""
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("Falta PyMuPDF. La dependencia está declarada en requirements.txt.") from exc

    source = pymupdf.open(str(path))
    page_count = source.page_count
    blocks = _extract_pdf_blocks(source)
    if not blocks:
        source.close()
        raise RuntimeError(
            "Este PDF no contiene texto seleccionable. Para PDF escaneados con texto "
            "solo como imagen necesitamos activar OCR en una siguiente etapa."
        )

    original_texts = [block.text for block in blocks]
    translated_texts: list[str] = []

    for start in range(0, len(blocks), batch_size):
        batch = blocks[start:start + batch_size]
        segment_inputs = [
            (f"{index:06d}", block.text)
            for index, block in enumerate(batch, start=start + 1)
        ]
        batch_outputs, _ = _translate_segments(
            segment_inputs, source_lang, target_lang, translate_fn
        )
        translated_texts.extend(batch_outputs)

    if len(translated_texts) != len(blocks):
        source.close()
        raise RuntimeError("La traducción no produjo todos los bloques del documento.")

    # Remove only the original text layer. Images and vector graphics remain.
    for block in blocks:
        source[block.page].add_redact_annot(
            pymupdf.Rect(block.bbox), fill=False, cross_out=False
        )

    for page in source:
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
            text=pymupdf.PDF_REDACT_TEXT_REMOVE,
        )

    for block, translated in zip(blocks, translated_texts):
        page = source[block.page]
        rect = pymupdf.Rect(block.bbox)
        rect = pymupdf.Rect(
            rect.x0,
            rect.y0 - 0.5,
            rect.x1,
            rect.y1 + max(1.0, block.fontsize * 0.18),
        )
        _insert_pdf_text_fitted(page, rect, translated, block)

    output = source.tobytes(garbage=4, deflate=True, clean=True)
    source.close()

    final_validation = _validate_final_pdf(output, blocks)
    if not final_validation["passed"]:
        raise RuntimeError(
            "La reconstrucción PDF fue bloqueada: la validación final detectó contenido "
            "protegido que no sobrevivió al renderizado."
        )

    return output, {
        "format": "pdf",
        "pages": page_count,
        "textBlocks": len(blocks),
        "counts": _aggregate_counts(original_texts),
        "validation": final_validation,
    }


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
        if paragraph.runs:
            paragraph.runs[0].text = value
            for run in paragraph.runs[1:]:
                run.text = ""
        else:
            paragraph.add_run(value)
    return texts, translated


def translate_docx_document(
    path: str | Path,
    source_lang: str,
    target_lang: str,
    translate_fn: TranslateFn,
) -> tuple[bytes, dict]:
    """Translate DOCX paragraphs and tables while keeping the document object."""
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("Falta python-docx. La dependencia está declarada en requirements.txt.") from exc

    document = Document(str(path))
    original_texts, _ = _translate_docx_paragraphs(
        document, source_lang, target_lang, translate_fn
    )
    output_path = Path(path).with_name(f"{Path(path).stem}_sumire_temp.docx")
    try:
        document.save(str(output_path))
        output = output_path.read_bytes()
    finally:
        try:
            output_path.unlink()
        except OSError:
            pass
    return output, {
        "format": "docx",
        "textBlocks": len(original_texts),
        "counts": _aggregate_counts(original_texts),
        "validation": {"passed": True, "checked": len(original_texts), "issues": []},
    }


def translate_document(
    path: str | Path,
    source_lang: str,
    target_lang: str,
    translate_fn: TranslateFn,
) -> tuple[bytes, str, dict]:
    """Dispatch a document to its layout-aware reconstruction adapter."""
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        data, info = translate_pdf_document(path, source_lang, target_lang, translate_fn)
        return data, "pdf", info
    if suffix == ".docx":
        data, info = translate_docx_document(path, source_lang, target_lang, translate_fn)
        return data, "docx", info
    raise ValueError(f"Reconstrucción no disponible para: {suffix or '(sin extensión)'}")
