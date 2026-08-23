"""Google Gemini translation provider for Sumire Translate."""

from __future__ import annotations

import os
from typing import Any


def _get_secret(name: str) -> str | None:
    """Read a Streamlit secret first, then an environment variable."""
    try:
        import streamlit as st

        value = st.secrets.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    except Exception:
        pass

    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


def _get_api_key() -> str | None:
    """Read the Gemini key from Streamlit Secrets or the environment."""
    return _get_secret("GEMINI_API_KEY")


def _get_model() -> str:
    """Read the configured Gemini model, with a safe default."""
    return _get_secret("SUMIRE_GEMINI_MODEL") or "gemini-2.5-flash"


def translate_with_gemini(prompt: str) -> str:
    """Send a prepared Sumire translation prompt to Gemini."""
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError(
            "Sumire no tiene configurada GEMINI_API_KEY. "
            "En Streamlit Community Cloud abre Manage app → Settings → Secrets "
            "y añade: GEMINI_API_KEY = \"tu_clave_de_Gemini\". "
            "No pongas la clave en GitHub."
        )

    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "Falta google-genai. La dependencia está declarada en requirements.txt; "
            "reinicia/redeploya la aplicación para instalarla."
        ) from exc

    try:
        client = genai.Client(api_key=api_key)
        response: Any = client.models.generate_content(
            model=_get_model(),
            contents=prompt,
        )
    except Exception as exc:
        raise RuntimeError(
            "No se pudo conectar con Gemini. Comprueba GEMINI_API_KEY, "
            "el modelo configurado y los límites/cuota de tu proyecto de Google AI."
        ) from exc

    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini no devolvió texto de traducción.")
    return str(text)
