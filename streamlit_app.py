from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st

from backend.core.languages import LANGUAGES
from backend.formats.extractor import extract_text
from backend.processing.pipeline import run_pipeline
from backend.translation.gemini_provider import translate_with_gemini

st.set_page_config(
    page_title="Sumire Translate",
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .stApp { background: #ffffff; }
    .block-container { max-width: 1350px; padding-top: 45px; padding-bottom: 60px; }
    .logo { font-family: Georgia, serif; font-size: 30px; font-weight: 600; color: #252640; }
    .logo-sub { font-family: Arial, sans-serif; font-size: 10px; letter-spacing: 4px; color: #6043bd; }
    .hero { margin: 65px 0 30px; }
    .small-title { color: #6043bd; font-size: 13px; letter-spacing: 2px; }
    .main-title { font-family: Georgia, serif; font-size: 50px; line-height: 1.08; color: #20233d; }
    .main-title span { color: #8c6bd2; font-style: italic; }
    .description { font-family: Georgia, serif; font-size: 18px; color: #55545c; line-height: 1.5; }
    .status-card { padding: 14px 18px; border: 1px solid #eeeaf0; border-radius: 14px; background: #fcfaff; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="logo">🌸 Sumire</div><div class="logo-sub">TRANSLATE</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero"><div class="small-title">TRADUCCIONES QUE CONECTAN</div>'
    '<div class="main-title">Traduce ideas.<br><span>Conecta mundos.</span> ✦</div>'
    '<div class="description">Traducciones precisas y naturales, protegiendo matemáticas, símbolos y estructura.</div></div>',
    unsafe_allow_html=True,
)

language_names = [item["name"] for item in LANGUAGES]
language_codes = {item["name"]: item["code"] for item in LANGUAGES}

if "source_language" not in st.session_state:
    st.session_state.source_language = "Español"
if "target_language" not in st.session_state:
    st.session_state.target_language = "Inglés"
if "translated_text" not in st.session_state:
    st.session_state.translated_text = ""
if "validation" not in st.session_state:
    st.session_state.validation = None

col1, col2, col3 = st.columns([4, 1, 4])
with col1:
    source_name = st.selectbox("Idioma de origen", language_names, key="source_language")
with col2:
    st.write("")
    st.write("")
    if st.button("⇄", use_container_width=True):
        st.session_state.source_language, st.session_state.target_language = (
            st.session_state.target_language,
            st.session_state.source_language,
        )
        st.rerun()
with col3:
    target_name = st.selectbox("Idioma de destino", language_names, key="target_language")

col1, col2 = st.columns(2, gap="medium")
with col1:
    text = st.text_area(
        "Texto original",
        placeholder="Escribe o pega tu texto aquí...",
        height=260,
        max_chars=20000,
    )
    st.caption(f"{len(text)} caracteres")

with col2:
    st.text_area(
        "Traducción",
        value=st.session_state.translated_text,
        placeholder="Tu traducción aparecerá aquí...",
        height=260,
        disabled=True,
    )

uploaded = st.file_uploader(
    "📂 Subir documento (.pdf, .docx, .txt)",
    type=["pdf", "docx", "txt"],
)

col1, col2 = st.columns([1, 1])
with col1:
    translate_clicked = st.button("✨ Traducir", use_container_width=True, type="primary")
with col2:
    clear_clicked = st.button("Limpiar", use_container_width=True)

if clear_clicked:
    st.session_state.translated_text = ""
    st.session_state.validation = None
    st.rerun()

if translate_clicked:
    source_text = text.strip()
    source_filename = "texto.txt"

    if uploaded is not None:
        suffix = Path(uploaded.name).suffix.lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded.getbuffer())
            temp_path = tmp.name
        try:
            source_text = extract_text(temp_path).strip()
            source_filename = uploaded.name
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    if not source_text:
        st.warning("Escribe un texto o sube un documento primero.")
    elif source_name == target_name:
        st.warning("El idioma de origen y el idioma de destino deben ser diferentes.")
    else:
        with st.status("Procesando Sumire Translate...", expanded=True) as status:
            try:
                st.write("Protegiendo matemáticas, símbolos, código y elementos estructurales...")
                result = run_pipeline(
                    text=source_text,
                    source_lang=language_codes[source_name],
                    target_lang=language_codes[target_name],
                    translate_fn=translate_with_gemini,
                )
                st.session_state.translated_text = result["translated"]
                st.session_state.validation = result["validation"]
                status.update(label="Traducción completada", state="complete")
            except Exception as exc:
                status.update(label="No se pudo completar la traducción", state="error")
                st.error(str(exc))

if st.session_state.validation is not None:
    validation = st.session_state.validation
    if validation.get("passed"):
        st.success("✓ Validación estructural superada: los elementos protegidos fueron restaurados.")
    else:
        st.warning("⚠ La validación detectó posibles cambios. Revisa el resultado antes de usarlo.")
        if validation.get("issues"):
            st.write(validation["issues"])

if st.session_state.translated_text:
    st.download_button(
        "⬇️ Descargar traducción como TXT",
        data=st.session_state.translated_text,
        file_name="sumire_traduccion.txt",
        mime="text/plain",
        use_container_width=True,
    )

st.markdown("---")
st.markdown("### 🛡️ Protección de contenido")
st.write(
    "Sumire protege elementos no lingüísticos antes de enviarlos al modelo y los restaura después. "
    "La reconstrucción fiel de PDF/DOCX y la preservación avanzada de tablas e imágenes son las siguientes fases del proyecto."
)
