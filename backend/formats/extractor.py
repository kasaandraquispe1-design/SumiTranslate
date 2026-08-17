"""Text extraction for TXT, PDF and DOCX inputs.

This first adapter extracts readable text while keeping the source filename
and format explicit. Reconstruction is handled separately in a later stage.
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
