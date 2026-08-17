"""Google Gemini translation provider for Sumire Translate."""

from __future__ import annotations

import os
from typing import Any


def _get_api_key() -> str | None:
    """Read the key from Streamlit Secrets first, then environment variables."""
    try:
        import streamlit as st

        key = st.secrets.get("GEMINI_API_KEY")
        if key:
            return str(key)
    except Exception:
        pass
    return os.getenv("GEMINI_API_KEY")


def translate_with_gemini(prompt: str) -> str:
    """Send a prepared Sumire translation prompt to Gemini."""
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError(
            "Sumire necesita una clave GEMINI_API_KEY. En Streamlit Cloud: "
            "Settings → Secrets y añade GEMINI_API_KEY=tu_clave."
        )

    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "Falta google-genai. La dependencia está declarada en requirements.txt; "
            "reinicia/redeploya la aplicación para instalarla."
        ) from exc

    client = genai.Client(api_key=api_key)
    response: Any = client.models.generate_content(
        model=os.getenv("SUMIRE_GEMINI_MODEL", "gemini-2.5-flash"),
        contents=prompt,
    )
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini no devolvió texto de traducción.")
    return str(text)
