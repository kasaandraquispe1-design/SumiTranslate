"""Image text extraction for Sumire Translate.

Images are treated as visual documents. Gemini is used only to recover the
readable text; the normal Sumire translation pipeline still performs the
translation and structural validation afterward.
"""

from __future__ import annotations

import os
from pathlib import Path


def _get_api_key() -> str | None:
    try:
        import streamlit as st

        key = st.secrets.get("GEMINI_API_KEY")
        if key:
            return str(key)
    except Exception:
        pass
    return os.getenv("GEMINI_API_KEY")


MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def extract_text_from_image(path: str | Path) -> str:
    """Extract visible text from a PNG/JPEG/WEBP image using Gemini vision."""
    file_path = Path(path)
    mime_type = MIME_TYPES.get(file_path.suffix.lower())
    if not mime_type:
        raise ValueError(f"Formato de imagen no soportado: {file_path.suffix or '(sin extensión)'}")

    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError(
            "Para leer texto de imágenes, Sumire necesita GEMINI_API_KEY."
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Falta google-genai. Ejecuta/redeploya la aplicación para instalar las dependencias.") from exc

    client = genai.Client(api_key=api_key)
    image_bytes = file_path.read_bytes()

    prompt = (
        "Extract all readable text from this image. Preserve the reading order, "
        "paragraph breaks, mathematical expressions, symbols, numbers, and table "
        "content as faithfully as possible. Do not translate, summarize, or explain. "
        "Return only the recovered text."
    )

    response = client.models.generate_content(
        model=os.getenv("SUMIRE_GEMINI_VISION_MODEL", os.getenv("SUMIRE_GEMINI_MODEL", "gemini-2.5-flash")),
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            prompt,
        ],
    )
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini no pudo recuperar texto legible de la imagen.")
    return str(text)
