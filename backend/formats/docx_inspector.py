"""Safe DOCX inspection helpers.

This module only inspects the OOXML package. It never modifies the document.
Images are detected directly from word/media/, so inline and floating images
are both counted without touching the document's layout or text.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile


def inspect_docx_images(path_or_bytes) -> dict:
    """Return image inventory for a DOCX before translation.

    The result is intentionally small and stable so the UI can report whether
    the document contains images before the translation pipeline starts.
    """
    if hasattr(path_or_bytes, "read"):
        raw = path_or_bytes.read()
        try:
            path_or_bytes.seek(0)
        except Exception:
            pass
        archive = zipfile.ZipFile(BytesIO(raw))
    elif isinstance(path_or_bytes, (bytes, bytearray)):
        archive = zipfile.ZipFile(BytesIO(path_or_bytes))
    else:
        archive = zipfile.ZipFile(str(Path(path_or_bytes)))

    try:
        media = sorted(
            name for name in archive.namelist()
            if name.startswith("word/media/") and not name.endswith("/")
        )
        by_extension: dict[str, int] = {}
        for name in media:
            ext = Path(name).suffix.lower().lstrip(".") or "desconocido"
            by_extension[ext] = by_extension.get(ext, 0) + 1
        return {
            "hasImages": bool(media),
            "count": len(media),
            "files": media,
            "byExtension": dict(sorted(by_extension.items())),
        }
    finally:
        archive.close()
