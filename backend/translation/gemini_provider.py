"""Google Gemini translation provider for Sumire Translate."""

from __future__ import annotations

import os
from typing import Any


# Ordered fallbacks. The provider first asks Google which generation models are
# actually exposed to the configured API key/project and then chooses from that
# list. This is important because a model written in Streamlit Secrets can be
# valid globally but unavailable to a particular project.
_MODEL_CANDIDATES = (
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
)


def _get_secret(name: str) -> str | None:
    try:
        import streamlit as st
        value = st.secrets.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    except Exception:
        pass
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


def _normalise_model_name(name: str) -> str:
    name = str(name).strip()
    return name.split("/", 1)[1] if name.startswith("models/") else name


def _available_generate_models(client: Any) -> list[str]:
    """Return model IDs exposed by this exact API key/project.

    Some SDK versions expose supported_actions and others do not. If that
    metadata is absent, keep the model rather than incorrectly filtering it
    out; generate_content itself remains the final capability check.
    """
    try:
        models = client.models.list()
        available: list[str] = []
        for item in models:
            name = getattr(item, "name", None)
            if not name:
                continue
            actions = getattr(item, "supported_actions", None)
            if actions:
                actions_text = {str(action).lower().replace("_", "") for action in actions}
                if "generatecontent" not in actions_text:
                    continue
            available.append(_normalise_model_name(str(name)))
        return available
    except Exception:
        return []


def _select_model(client: Any) -> tuple[str, list[str]]:
    configured = _get_secret("SUMIRE_GEMINI_MODEL")
    configured = _normalise_model_name(configured) if configured else None
    available = _available_generate_models(client)
    available_set = set(available)

    # A configured model is honored only when Google explicitly exposes it.
    # If Secrets still contains an obsolete value such as gemini-3.6-flash,
    # silently fall back instead of stopping the whole translation.
    if configured and (not available or configured in available_set):
        return configured, available

    if available:
        for candidate in _MODEL_CANDIDATES:
            if candidate in available_set:
                return candidate, available
        # Last resort: choose a generation-capable Flash model advertised by
        # this project, without guessing a model that is not in the list.
        for model in available:
            if "flash" in model.lower() and "tts" not in model.lower():
                return model, available
        return available[0], available

    # Listing models can occasionally fail transiently. Use a stable fallback
    # and let generate_content/fallback logic perform the capability check.
    return (configured or _MODEL_CANDIDATES[0]), available


def _generate(client: Any, model: str, prompt: str) -> str:
    response: Any = client.models.generate_content(model=model, contents=prompt)
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini no devolvió texto de traducción.")
    return str(text)


def translate_with_gemini(prompt: str) -> str:
    api_key = _get_secret("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Sumire no tiene configurada GEMINI_API_KEY. "
            "En Streamlit Community Cloud abre Manage app → Settings → Secrets "
            "y añade GEMINI_API_KEY = \"tu_clave_de_Gemini\". No pongas la clave en GitHub."
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

        candidates = [model]
        if available:
            for candidate in _MODEL_CANDIDATES:
                if candidate in available and candidate not in candidates:
                    candidates.append(candidate)
            for candidate in available:
                if "flash" in candidate.lower() and "tts" not in candidate.lower() and candidate not in candidates:
                    candidates.append(candidate)
        else:
            for candidate in _MODEL_CANDIDATES:
                if candidate not in candidates:
                    candidates.append(candidate)

        first_exc: Exception | None = None
        for candidate in candidates:
            try:
                return _generate(client, candidate, prompt)
            except Exception as exc:
                if first_exc is None:
                    first_exc = exc
                continue

        available_text = ", ".join(available[:30]) if available else "no se pudo consultar la lista de modelos"
        raise RuntimeError(
            f"Gemini no pudo generar la traducción con los modelos disponibles. "
            f"Modelos visibles para esta clave/proyecto: {available_text}. "
            "Si SUMIRE_GEMINI_MODEL apunta a un modelo antiguo, puedes eliminar esa "
            "variable de Streamlit Secrets; Sumire elegirá automáticamente uno compatible."
        ) from first_exc
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            "No se pudo inicializar Gemini. Comprueba GEMINI_API_KEY, el proyecto de "
            "Google AI Studio y los límites/cuota de la API."
        ) from exc
