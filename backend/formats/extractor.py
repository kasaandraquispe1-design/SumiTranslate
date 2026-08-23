"""Text extraction adapters for TXT, PDF and DOCX inputs.

The simple extractor remains useful for plain-text workflows. Layout-aware PDF
and DOCX translation is implemented separately in ``document_pipeline.py`` so
that the original document can be reconstructed instead of being flattened to
plain text.
"""

from __future__ import annotations

from pathlib import Path


def extract_text(path: str | Path) -> str:
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix == ".txt":
        return file_path.read_text(encoding="utf-8", errors="replace")

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("Instala pypdf para procesar PDF.") from exc
        reader = PdfReader(str(file_path))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)

    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("Instala python-docx para procesar DOCX.") from exc
        document = Document(str(file_path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)

    raise ValueError(f"Formato no soportado: {suffix or '(sin extensión)'}")
