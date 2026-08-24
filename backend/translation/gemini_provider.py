"""Google Gemini translation provider for Sumire Translate."""

from __future__ import annotations

import os
from typing import Any


# Prefer models that are actually exposed by the current Google AI project.
# The provider also queries the API at runtime, so Sumire does not depend on
# one hard-coded model name when Google changes availability.
_MODEL_CANDIDATES = (
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-2.5-pro",
    "gemini-pro-latest",
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
    """Read the optional model from Streamlit Secrets."""
    return _get_secret("SUMIRE_GEMINI_MODEL")


def _normalise_model_name(name: str) -> str:
    """Convert models/foo to foo for comparison and API calls."""
    return name.split("/", 1)[1] if name.startswith("models/") else name


def _available_generate_models(client: Any) -> list[str]:
    """Return model IDs exposed by this API key that support generation."""
    try:
        models = client.models.list()
        available: list[str] = []
        for item in models:
            name = getattr(item, "name", None)
            if not name:
                continue

            actions = getattr(item, "supported_actions", None) or []
            actions_text = {str(action).lower().replace("_", "") for action in actions}

            # Some google-genai SDK versions do not expose supported_actions.
            # In that case keep the model and let generate_content verify it.
            if actions_text and "generatecontent" not in actions_text:
                continue

            available.append(_normalise_model_name(str(name)))
        return available
    except Exception:
        return []


def _select_models(client: Any) -> tuple[list[str], list[str]]:
    """Build an ordered list of models that this project can actually use."""
    configured = _get_configured_model()
    configured = _normalise_model_name(configured) if configured else None
    available = _available_generate_models(client)

    ordered: list[str] = []

    # A configured model is only used when the current project exposes it.
    # This prevents an old Secret such as gemini-3.6-flash from breaking the app.
    if configured and (not available or configured in available):
        ordered.append(configured)

    for candidate in _MODEL_CANDIDATES:
        if candidate in ordered:
            continue
        if not available or candidate in available:
            ordered.append(candidate)

    # If Google exposes a new/renamed generation model that is not in our
    # preferred list, append it as a last-resort option.
    if available:
        for model in available:
            if model not in ordered and not model.startswith("gemma-"):
                ordered.append(model)

    return ordered, available


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
        candidates, available = _select_models(client)

        if not candidates:
            available_text = ", ".join(available[:20]) if available else "ninguno"
            raise RuntimeError(
                "Tu API key no expone ningún modelo de generación compatible. "
                f"Modelos visibles: {available_text}."
            )

        errors: list[str] = []
        for model in candidates:
            try:
                return _generate(client, model, prompt)
            except Exception as exc:
                errors.append(f"{model}: {exc}")
                continue

        available_text = ", ".join(available[:20]) if available else "no se pudo consultar la lista de modelos"
        raise RuntimeError(
            "No se pudo completar la traducción con ninguno de los modelos disponibles. "
            f"Modelos visibles para esta clave/proyecto: {available_text}. "
            "Comprueba GEMINI_API_KEY y la cuota de tu proyecto de Google AI Studio."
        )

    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            "No se pudo inicializar Gemini. Comprueba GEMINI_API_KEY, el proyecto de "
            "Google AI Studio y los límites/cuota de la API."
        ) from exc
