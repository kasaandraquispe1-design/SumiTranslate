"""Layout-aware document translation for Sumire Translate.

Phase 2 keeps the original document as the visual source of truth. PDF text is
translated block-by-block and written back into the original page coordinates;
images, vector drawings, page size and page count are retained. DOCX paragraphs
and table cells are translated in place so styles, numbering and embedded
images remain part of the document.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from backend.core.languages import language_name
from backend.protection.math_protector import (
    ProtectedElement,
    protect_text,
    restore_markers,
)
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
    rotation: int = 0


def _block_text(block: dict) -> str:
    lines: list[str] = []
    for line in block.get("lines", []):
        spans = line.get("spans", [])
        line_text = "".join(str(span.get("text", "")) for span in spans)
        lines.append(line_text.rstrip())
    return "\n".join(lines).strip()


def _extract_pdf_blocks(doc) -> list[PDFTextBlock]:
    blocks: list[PDFTextBlock] = []
    for page_index, page in enumerate(doc):
        data = page.get_text("dict", sort=True)
        for block in data.get("blocks", []):
            # type 0 = text. Image blocks are deliberately ignored here: they
            # remain untouched in the original PDF and are copied to output.
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


def _segment_tokens(text: str) -> list[str]:
    return [match.group(0) for match in SEGMENT_RE.finditer(text)]


def _build_document_prompt(
    source_lang: str,
    target_lang: str,
    segments: list[tuple[str, str]],
) -> str:
    body = []
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
    for segment_id, text in segments:
        protected, store, _ = protect_text(text)
        prepared.append((segment_id, protected, store))

    prompt_segments = [(segment_id, protected) for segment_id, protected, _ in prepared]
    prompt = _build_document_prompt(source_lang, target_lang, prompt_segments)
    translated = translate_fn(prompt)

    expected_tokens: list[str] = []
    for segment_id, protected, _ in prepared:
        expected_tokens.append(f"[[SUMIRE_SEG_{segment_id}_START]]")
        expected_tokens.extend(_marker_sequence(protected))
        expected_tokens.append(f"[[SUMIRE_SEG_{segment_id}_END]]")

    actual_tokens = _segment_tokens(translated)
    # Protected markers are not segment tokens, so compare them separately.
    actual_all_markers = re.findall(r"\[\[[A-Z_]+_\d{3,6}(?:_(?:START|END))?\]\]", translated)
    expected_all_markers = expected_tokens
    if actual_all_markers != expected_all_markers:
        raise RuntimeError(
            "La traducción fue bloqueada: el modelo alteró la estructura protegida "
            "del documento."
        )

    outputs: list[str] = []
    validation_issues: list[dict] = []
    for segment_id, _, store in prepared:
        start = f"[[SUMIRE_SEG_{segment_id}_START]]"
        end = f"[[SUMIRE_SEG_{segment_id}_END]]"
        start_pos = translated.find(start)
        end_pos = translated.find(end, start_pos + len(start))
        if start_pos < 0 or end_pos < 0:
            raise RuntimeError("La traducción fue bloqueada: falta un delimitador de segmento.")
        segment_output = translated[start_pos + len(start):end_pos].strip("\n")
        # The protected marker sequence inside this segment must be exact.
        original_protected = next(p for sid, p, _ in prepared if sid == segment_id)
        if _marker_sequence(segment_output) != _marker_sequence(original_protected):
            validation_issues.append({"segment": segment_id, "type": "marker_sequence_changed"})
            continue
        restored = restore_markers(segment_output, store)
        validation = validate(
            next(text for sid, text in segments if sid == segment_id),
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
    bold = bool(flags & 16)
    italic = bool(flags & 2)
    if bold and italic:
        return "hebi"
    if bold:
        return "hebo"
    if italic:
        return "heit"
    return "helv"


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
    blocks = _extract_pdf_blocks(source)
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

    # Replace text only. Images and vector graphics are explicitly left alone.
    # This is the key preservation step: the original PDF page remains the
    # background, including figures, captions' geometry, tables and numbering.
    for block, translated in zip(blocks, translated_texts):
        page = source[block.page]
        rect = pymupdf.Rect(block.bbox)
        page.add_redact_annot(rect, fill=False, cross_out=False)

    for page in source:
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
            text=pymupdf.PDF_REDACT_TEXT_REMOVE,
        )

    for block, translated in zip(blocks, translated_texts):
        page = source[block.page]
        rect = pymupdf.Rect(block.bbox)
        fontsize = max(5.5, min(block.fontsize, 24.0))
        # Give translated text a little more room without moving it to another
        # region. PyMuPDF automatically reduces the font if the text is longer.
        rect = pymupdf.Rect(rect.x0, rect.y0 - 0.5, rect.x1, rect.y1 + max(1.0, block.fontsize * 0.18))
        page.insert_textbox(
            rect,
            translated,
            fontname=_pdf_font_name(block.flags),
            fontsize=fontsize,
            color=_pdf_color(block.color),
            overlay=True,
        )

    output = io.BytesIO()
    source.save(output, garbage=4, deflate=True, clean=True)
    source.close()
    return output.getvalue(), {
        "format": "pdf",
        "pages": len(set(block.page for block in blocks)) if blocks else 0,
        "textBlocks": len(blocks),
        "counts": _aggregate_counts(original_texts),
        "validation": {"passed": True, "checked": len(blocks), "issues": []},
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
    original_texts, translated_texts = _translate_docx_paragraphs(
        document, source_lang, target_lang, translate_fn
    )
    output = io.BytesIO()
    document.save(output)
    return output.getvalue(), {
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
