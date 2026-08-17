from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st

from backend.core.languages import LANGUAGES
from backend.formats.extractor import extract_text
from backend.formats.image_extractor import extract_text_from_image
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
    :root { --sumire-ink:#252640; --sumire-muted:#6f6d78; --sumire-primary:#6043bd; --sumire-border:#e9e5ef; --sumire-bg:#fbfafc; }
    .stApp { background:linear-gradient(180deg,#fff 0%,var(--sumire-bg) 100%); color:var(--sumire-ink); }
    .block-container { max-width:1320px; padding-top:32px; padding-bottom:64px; }
    [data-testid="stHeader"] { background:transparent; } [data-testid="stDecoration"] { display:none; }
    .sumire-brand { display:inline-flex; align-items:center; gap:10px; margin-bottom:8px; }
    .sumire-mark { width:38px; height:38px; display:grid; place-items:center; border:1px solid #e4dff0; border-radius:12px; background:#f8f5ff; font-size:20px; box-shadow:0 4px 16px rgba(96,67,189,.08); }
    .sumire-logo { font-family:Georgia,serif; font-size:26px; line-height:1; font-weight:600; color:var(--sumire-ink); }
    .sumire-sub { margin-left:48px; margin-top:-3px; font-size:9px; letter-spacing:4px; color:var(--sumire-primary); font-weight:700; }
    .hero { padding:42px 0 26px; }
    .eyebrow { color:var(--sumire-primary); font-size:12px; letter-spacing:2px; font-weight:700; margin-bottom:10px; }
    .main-title { font-family:Georgia,serif; font-size:clamp(38px,5vw,58px); line-height:1.04; letter-spacing:-1.5px; color:#20233d; margin:0; }
    .main-title span { color:#8c6bd2; font-style:italic; }
    .description { max-width:720px; margin-top:15px; font-family:Georgia,serif; font-size:18px; color:#64616c; line-height:1.55; }
    .feature-row { display:flex; flex-wrap:wrap; gap:8px; margin-top:18px; }
    .feature-badge { display:inline-flex; align-items:center; gap:6px; padding:6px 10px; border:1px solid var(--sumire-border); border-radius:999px; background:#fff; color:#5e5b67; font-size:12px; }
    .section-title { font-size:14px; font-weight:700; color:var(--sumire-ink); margin-bottom:4px; }
    .section-caption { color:var(--sumire-muted); font-size:12px; margin-bottom:12px; }
    .protection-card { margin-top:22px; padding:17px 19px; border:1px solid #e5dff0; border-radius:16px; background:linear-gradient(135deg,#fcfaff,#fff); }
    .protection-title { font-weight:700; color:var(--sumire-ink); margin-bottom:4px; }
    .protection-text { color:var(--sumire-muted); font-size:13px; line-height:1.5; }
    div[data-testid="stTextArea"] textarea, div[data-testid="stFileUploader"] section { border-radius:14px !important; border-color:var(--sumire-border) !important; }
    div[data-testid="stSelectbox"] > div > div { border-radius:12px !important; border-color:var(--sumire-border) !important; }
    .stButton > button, .stDownloadButton > button { border-radius:11px; min-height:42px; font-weight:650; border-color:var(--sumire-border); }
    .stButton > button[kind="primary"] { background:var(--sumire-primary); border-color:var(--sumire-primary); }
    .stButton > button[kind="primary"]:hover { background:#5136a7; border-color:#5136a7; }
    hr { border-color:var(--sumire-border) !important; }
    @media (max-width:800px) { .block-container{padding-left:18px;padding-right:18px;} .hero{padding-top:28px;} .main-title{font-size:42px;} }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="sumire-brand"><div class="sumire-mark">🌸</div><div class="sumire-logo">Sumire</div></div><div class="sumire-sub">TRANSLATE</div>', unsafe_allow_html=True)
st.markdown('<div class="hero"><div class="eyebrow">TRADUCCIONES QUE CONECTAN</div><div class="main-title">Traduce ideas.<br><span>Conecta mundos.</span> ✦</div><div class="description">Traducciones precisas y naturales, protegiendo matemáticas, símbolos y estructura.</div><div class="feature-row"><span class="feature-badge">🛡️ Matemáticas protegidas</span><span class="feature-badge">📄 PDF / DOCX / TXT</span><span class="feature-badge">🖼️ Texto desde imágenes</span><span class="feature-badge">✓ Validación estructural</span></div></div>', unsafe_allow_html=True)

language_names = [item["name"] for item in LANGUAGES]
language_codes = {item["name"]: item["code"] for item in LANGUAGES}
language_flags = {item["name"]: item.get("flag", "") for item in LANGUAGES}

if "source_language" not in st.session_state:
    st.session_state.source_language = "Español"
if "target_language" not in st.session_state:
    st.session_state.target_language = "Inglés"
if "translated_text" not in st.session_state:
    st.session_state.translated_text = ""
if "validation" not in st.session_state:
    st.session_state.validation = None

# The selectboxes own these two keys. The swap callback runs before Streamlit
# reruns the script, so changing the widget values here is safe and avoids
# StreamlitAPIException caused by changing widget state after widget creation.
if "source_language_widget" not in st.session_state:
    st.session_state.source_language_widget = st.session_state.source_language
if "target_language_widget" not in st.session_state:
    st.session_state.target_language_widget = st.session_state.target_language


def swap_languages() -> None:
    """Swap the two selectbox values inside the widget callback."""
    source = st.session_state.get("source_language_widget", "Español")
    target = st.session_state.get("target_language_widget", "Inglés")
    st.session_state.source_language_widget = target
    st.session_state.target_language_widget = source


st.markdown('<div class="section-title">Idioma</div><div class="section-caption">Elige el idioma de origen y el idioma al que quieres traducir.</div>', unsafe_allow_html=True)
col1, col2, col3 = st.columns([4, 1, 4], vertical_alignment="bottom")
with col1:
    source_name = st.selectbox(
        "Idioma de origen",
        language_names,
        key="source_language_widget",
        format_func=lambda name: f"{language_flags.get(name, '')} {name}".strip(),
    )
with col2:
    st.button(
        "⇄",
        use_container_width=True,
        help="Intercambiar idiomas",
        on_click=swap_languages,
    )
with col3:
    target_name = st.selectbox(
        "Idioma de destino",
        language_names,
        key="target_language_widget",
        format_func=lambda name: f"{language_flags.get(name, '')} {name}".strip(),
    )

# Keep the application-level language state synchronized with the widgets.
st.session_state.source_language = source_name
st.session_state.target_language = target_name

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
col1, col2 = st.columns(2, gap="large")
with col1:
    st.markdown('<div class="section-title">Texto original</div><div class="section-caption">Escribe, pega o carga un documento.</div>', unsafe_allow_html=True)
    text = st.text_area("Texto original", placeholder="Escribe o pega tu texto aquí...", height=300, max_chars=20000, label_visibility="collapsed")
    st.caption(f"{len(text):,} caracteres")
with col2:
    st.markdown('<div class="section-title">Traducción</div><div class="section-caption">Sumire mostrará aquí el resultado validado.</div>', unsafe_allow_html=True)
    st.text_area("Traducción", value=st.session_state.translated_text, placeholder="Tu traducción aparecerá aquí...", height=300, disabled=True, label_visibility="collapsed")

uploaded = st.file_uploader(
    "📂 Subir documento o imagen",
    type=["pdf", "docx", "txt", "png", "jpg", "jpeg", "webp"],
    help="PDF, DOCX y TXT se extraen con los adaptadores actuales. PNG/JPG/JPEG/WEBP usan Gemini Vision para recuperar texto antes de traducirlo.",
)

col1, col2 = st.columns([1, 1], gap="medium")
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
    if uploaded is not None:
        suffix = Path(uploaded.name).suffix.lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded.getbuffer())
            temp_path = tmp.name
        try:
            if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
                with st.status("Leyendo el texto de la imagen...", expanded=False) as image_status:
                    source_text = extract_text_from_image(temp_path).strip()
                    image_status.update(label="Texto de la imagen recuperado", state="complete")
            else:
                source_text = extract_text(temp_path).strip()
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
            with st.expander("Ver detalles de validación"):
                st.write(validation["issues"])

if st.session_state.translated_text:
    st.download_button(
        "⬇️ Descargar traducción como TXT",
        data=st.session_state.translated_text,
        file_name="sumire_traduccion.txt",
        mime="text/plain",
        use_container_width=True,
    )

st.markdown('<div class="protection-card"><div class="protection-title">🛡️ Protección de contenido</div><div class="protection-text">Sumire protege elementos no lingüísticos antes de enviarlos al modelo y los restaura después. La lectura de imágenes ya puede recuperar texto visual mediante Gemini; la siguiente etapa será conservar/reconstruir el formato visual completo, tablas e imágenes en los archivos de salida.</div></div>', unsafe_allow_html=True)
