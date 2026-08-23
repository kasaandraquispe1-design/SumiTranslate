"""Google Gemini translation provider for Sumire Translate."""

from __future__ import annotations

import os
from typing import Any


# Models known to be exposed by the current Google AI Studio projects.
# Prefer the current Flash preview, then stable fallbacks. The provider also
# checks the models actually visible to the configured API key before calling.
_MODEL_CANDIDATES = (
    "gemini-3-flash-preview",
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
)


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


def _get_configured_model() -> str | None:
    return _get_secret("SUMIRE_GEMINI_MODEL")


def _normalise_model_name(name: str) -> str:
    return name.split("/", 1)[1] if name.startswith("models/") else name


def _available_generate_models(client: Any) -> list[str]:
    """Return generation-capable model IDs exposed by this API key."""
    try:
        models = client.models.list()
        available: list[str] = []
        for item in models:
            name = getattr(item, "name", None)
            if not name:
                continue
            actions = getattr(item, "supported_actions", None) or []
            actions_text = {str(action).lower() for action in actions}
            if actions_text and "generatecontent" not in actions_text and "generate_content" not in actions_text:
                continue
            available.append(_normalise_model_name(str(name)))
        return available
    except Exception:
        return []


def _select_model(client: Any) -> tuple[str, list[str]]:
    configured = _get_configured_model()
    available = _available_generate_models(client)

    if configured:
        configured = _normalise_model_name(configured)
        if not available or configured in available:
            return configured, available

    for candidate in _MODEL_CANDIDATES:
        if not available or candidate in available:
            return candidate, available

    if configured:
        return configured, available
    return _MODEL_CANDIDATES[0], available


def _generate(client: Any, model: str, prompt: str) -> str:
    response: Any = client.models.generate_content(model=model, contents=prompt)
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini no devolvió texto de traducción.")
    return str(text)


def translate_with_gemini(prompt: str) -> str:
    """Send a prepared Sumire translation prompt to Gemini."""
    api_key = _get_secret("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Sumire no tiene configurada GEMINI_API_KEY. "
            "En Streamlit Community Cloud abre Manage app → Settings → Secrets "
            "y añade GEMINI_API_KEY = \"tu_clave_de_Gemini\". "
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
        model, available = _select_model(client)

        try:
            return _generate(client, model, prompt)
        except Exception as first_exc:
            # Try only models that this exact project/key advertises when possible.
            candidates = [m for m in _MODEL_CANDIDATES if m != model]
            if available:
                candidates = [m for m in candidates if m in available]
            for fallback in candidates:
                try:
                    return _generate(client, fallback, prompt)
                except Exception:
                    continue

            available_text = ", ".join(available[:16]) if available else "no se pudo consultar la lista de modelos"
            raise RuntimeError(
                f"Gemini rechazó el modelo '{model}'. Modelos de generación visibles para "
                f"esta clave/proyecto: {available_text}. "
                "Revisa SUMIRE_GEMINI_MODEL en Streamlit Secrets o usa uno de los modelos "
                "que realmente aparecen para tu proyecto."
            ) from first_exc

    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            "No se pudo inicializar Gemini. Comprueba GEMINI_API_KEY, el proyecto de "
            "Google AI Studio y los límites/cuota de la API."
        ) from exc
