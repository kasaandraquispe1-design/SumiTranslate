"""Google Gemini translation provider.

The API key is read only from the GEMINI_API_KEY environment variable.
"""

from __future__ import annotations

import os


def translate_with_gemini(prompt: str) -> str:
    """Send a prepared Sumire translation prompt to Gemini."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Falta GEMINI_API_KEY. Configúrala como variable de entorno/Secret antes de traducir."
        )

    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "Falta la dependencia google-genai. Instálala con 'pip install google-genai'."
        ) from exc

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=os.getenv("SUMIRE_GEMINI_MODEL", "gemini-2.5-flash"),
        contents=prompt,
    )
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini no devolvió texto de traducción.")
    return text
