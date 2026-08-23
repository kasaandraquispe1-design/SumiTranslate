"""Google Gemini translation provider for Sumire Translate."""

from __future__ import annotations

import os
from typing import Any


# Stable production models currently intended for text/document translation.
# The first entry is preferred, but the provider can fall back when a project
# does not expose the configured model.
_MODEL_CANDIDATES = (
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
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
    """Return the optional model selected by the user in Streamlit Secrets."""
    return _get_secret("SUMIRE_GEMINI_MODEL")


def _normalise_model_name(name: str) -> str:
    """Convert models/foo to foo for comparison and API calls."""
    return name.split("/", 1)[1] if name.startswith("models/") else name


def _available_generate_models(client: Any) -> list[str]:
    """Return model IDs exposed by the current API key that support generation."""
    try:
        models = client.models.list()
        available: list[str] = []
        for item in models:
            name = getattr(item, "name", None)
            if not name:
                continue
            actions = getattr(item, "supported_actions", None) or []
            actions_text = {str(action).lower() for action in actions}
            # Some SDK versions expose supported_actions; if absent, keep the
            # model because generate_content is the operation we will test.
            if actions_text and "generatecontent" not in actions_text and "generate_content" not in actions_text:
                continue
            available.append(_normalise_model_name(str(name)))
        return available
    except Exception:
        return []


def _select_model(client: Any) -> tuple[str, list[str]]:
    """Choose a model, preferring the configured model and then known stable models."""
    configured = _configured = _get_configured_model()
    available = _available_generate_models(client)

    if configured:
        configured = _normalise_model_name(configured)
        if not available or configured in available:
            return configured, available

    for candidate in _MODEL_CANDIDATES:
        if not available or candidate in available:
            return candidate, available

    # No known candidate is exposed. Return the configured model if one was
    # supplied so the final error can explain exactly what the project exposes.
    if _configured:
        return _configured, available
    return _MODEL_CANDIDATES[0], available


def _generate(client: Any, model: str, prompt: str) -> str:
    """Call Gemini and return only the generated text."""
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
        model, available = _select_model(client)

        try:
            return _generate(client, model, prompt)
        except Exception as first_exc:
            # If the configured model is not accessible to this API key/project,
            # retry once with another stable model that the project advertises.
            candidates = [m for m in _MODEL_CANDIDATES if m != model]
            if available:
                candidates = [m for m in candidates if m in available]
            for fallback in candidates:
                try:
                    return _generate(client, fallback, prompt)
                except Exception:
                    continue

            available_text = ", ".join(available[:12]) if available else "no se pudo consultar la lista de modelos"
            raise RuntimeError(
                f"Gemini rechazó el modelo '{model}'. Modelos de generación visibles para "
                f"esta clave/proyecto: {available_text}. "
                "Si gemini-3.6-flash aparece en la lista pero sigue dando 404, "
                "crea una API key nueva en Google AI Studio dentro del mismo proyecto "
                "que estás usando y reemplaza GEMINI_API_KEY en Streamlit Secrets."
            ) from first_exc

    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            "No se pudo inicializar Gemini. Comprueba GEMINI_API_KEY, el proyecto de "
            "Google AI Studio y los límites/cuota de la API."
        ) from exc
