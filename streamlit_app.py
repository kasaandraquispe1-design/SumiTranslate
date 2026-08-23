from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st

from backend.core.languages import LANGUAGES
from backend.formats.document_pipeline import translate_document
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
    :root { --sumire-ink:#252640; --sumire-muted:#6f6d78; --sumire-primary:#6043bd; --sumire-primary-soft:#8c6bd2; --sumire-border:#d9cff0; --sumire-bg:#fbfafc; }
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
    .main-title span { color:var(--sumire-primary-soft); font-style:italic; }
    .description { max-width:720px; margin-top:15px; font-family:Georgia,serif; font-size:18px; color:#64616c; line-height:1.55; }
    .feature-row { display:flex; flex-wrap:wrap; gap:8px; margin-top:18px; }
    .feature-badge { display:inline-flex; align-items:center; gap:6px; padding:6px 10px; border:1px solid var(--sumire-border); border-radius:999px; background:#fff; color:#5e5b67; font-size:12px; }
    .section-title { font-size:14px; font-weight:700; color:var(--sumire-ink); margin-bottom:4px; }
    .section-caption { color:var(--sumire-muted); font-size:12px; margin-bottom:12px; }
    .protection-card { margin-top:22px; padding:17px 19px; border:1px solid #e5dff0; border-radius:16px; background:linear-gradient(135deg,#fcfaff,#fff); }
    .protection-title { font-weight:700; color:var(--sumire-ink); margin-bottom:4px; }
    .protection-text { color:var(--sumire-muted); font-size:13px; line-height:1.5; }
    div[data-testid="stTextArea"] textarea, div[data-testid="stFileUploader"] section, div[data-testid="stSelectbox"] [data-baseweb="select"] > div { background:#fff !important; background-color:#fff !important; color:var(--sumire-ink) !important; border:1.5px solid var(--sumire-border) !important; border-radius:14px !important; box-shadow:0 2px 10px rgba(96,67,189,.035) !important; }
    div[data-testid="stSelectbox"] [data-baseweb="select"] span, div[data-testid="stSelectbox"] [data-baseweb="select"] input, div[data-testid="stSelectbox"] [data-baseweb="select"] div { color:var(--sumire-ink) !important; }
    div[data-testid="stSelectbox"] [data-baseweb="select"] svg { fill:var(--sumire-primary) !important; }
    div[data-testid="stTextArea"] textarea:focus, div[data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within, div[data-testid="stFileUploader"] section:hover { border-color:var(--sumire-primary) !important; box-shadow:0 0 0 2px rgba(96,67,189,.10) !important; }
    div[data-testid="stTextArea"] textarea:disabled { background:#fff !important; color:#39364a !important; -webkit-text-fill-color:#39364a !important; opacity:1 !important; }
    div[data-testid="stFileUploader"] section { padding:12px !important; } div[data-testid="stFileUploader"] section > div { background:#fff !important; }
    div[data-testid="stFileUploader"] button { border-color:var(--sumire-border) !important; color:var(--sumire-primary) !important; background:#fff !important; }
    div[data-testid="stButton"] > button, div[data-testid="stDownloadButton"] > button, .stButton > button, .stDownloadButton > button { border-radius:11px !important; min-height:42px !important; font-weight:650 !important; border:1.5px solid var(--sumire-border) !important; background:#fff !important; color:var(--sumire-ink) !important; box-shadow:0 2px 8px rgba(96,67,189,.04) !important; }
    div[data-testid="stButton"] > button:hover, div[data-testid="stDownloadButton"] > button:hover { border-color:var(--sumire-primary) !important; color:var(--sumire-primary) !important; background:#fff !important; }
    div[data-testid="stButton"] > button[kind="primary"], .stButton > button[kind="primary"] { background:var(--sumire-primary) !important; background-color:var(--sumire-primary) !important; color:#fff !important; border-color:var(--sumire-primary) !important; box-shadow:0 5px 16px rgba(96,67,189,.18) !important; }
    div[data-testid="stButton"] > button[kind="primary"] p, .stButton > button[kind="primary"] p { color:#fff !important; }
    div[data-testid="stButton"] > button[kind="primary"]:hover, .stButton > button[kind="primary"]:hover { background:#5136a7 !important; background-color:#5136a7 !important; border-color:#5136a7 !important; color:#fff !important; }
    hr { border-color:var(--sumire-border) !important; }
    .sumire-stats { display:flex; flex-wrap:wrap; gap:8px; margin:12px 0 2px; }
    .sumire-stat { padding:8px 12px; border:1px solid var(--sumire-border); border-radius:12px; background:#fff; color:#514d5d; font-size:12px; }
    .sumire-stat strong { color:var(--sumire-primary); }
    .language-direction { display:flex; align-items:center; justify-content:center; gap:10px; margin:2px 0 18px; padding:9px 14px; border:1px solid var(--sumire-border); border-radius:999px; background:#fff; color:var(--sumire-ink); font-size:13px; font-weight:650; box-shadow:0 3px 12px rgba(96,67,189,.05); }
    .language-direction .arrow { color:var(--sumire-primary); font-size:18px; }
    .document-result { margin-top:12px; padding:14px 16px; border:1px solid var(--sumire-border); border-radius:14px; background:#fff; color:var(--sumire-ink); }
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

for key, default in {"source_language":"Español","target_language":"Inglés","translated_text":"","validation":None,"counts":None,"translated_document":None,"translated_document_format":None,"translated_document_name":None,"document_info":None,"original_text":""}.items():
    if key not in st.session_state:
        st.session_state[key] = default

if "uploader_version" not in st.session_state: st.session_state.uploader_version = 0

if "source_language_widget" not in st.session_state: st.session_state.source_language_widget = st.session_state.source_language
if "target_language_widget" not in st.session_state: st.session_state.target_language_widget = st.session_state.target_language

def swap_languages() -> None:
    source = st.session_state.get("source_language_widget", "Español")
    target = st.session_state.get("target_language_widget", "Inglés")
    st.session_state.source_language_widget = target
    st.session_state.target_language_widget = source

def clear_app() -> None:
    """Reset only the UI/input state; it does not affect the translation engine or configuration."""
    for key, value in {
        "original_text":"",
        "translated_text":"",
        "validation":None,
        "counts":None,
        "translated_document":None,
        "translated_document_format":None,
        "translated_document_name":None,
        "document_info":None,
    }.items():
        st.session_state[key] = value
    st.session_state.uploader_version += 1
    st.session_state.uploader_version += 1
    st.session_state.uploader_version += 1
    st.session_state.uploader_version += 1
    st.session_state.uploader_version += 1
    st.session_state.uploader_version += 1
    st.session_state.uploader_version += 1
    st.session_state.uploader_version += 1
    st.session_state.uploader_version += 1
    st.session_state.uploader_version += 1
    st.session_state.uploader_version += 1
    st.session_state.uploader_version += 1
    st.session_state.uploader_version += 1

st.markdown('<div class="section-title">Idioma</div><div class="section-caption">Elige el idioma de origen y el idioma al que quieres traducir.</div>', unsafe_allow_html=True)
col1, col2, col3 = st.columns([4, 1, 4], vertical_alignment="bottom")
with col1:
    source_name = st.selectbox("Idioma de origen", language_names, key="source_language_widget", format_func=lambda name: f"{language_flags.get(name, '')} {name}".strip())
with col2:
    st.button("⇄", use_container_width=True, help="Intercambiar idiomas", on_click=swap_languages)
with col3:
    target_name = st.selectbox("Idioma de destino", language_names, key="target_language_widget", format_func=lambda name: f"{language_flags.get(name, '')} {name}".strip())

st.session_state.source_language = source_name
st.session_state.target_language = target_name
st.markdown(f'<div class="language-direction"><span>{language_flags.get(source_name, "")} {source_name}</span><span class="arrow">→</span><span>{language_flags.get(target_name, "")} {target_name}</span></div>', unsafe_allow_html=True)

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
col1, col2 = st.columns(2, gap="large")
with col1:
    st.markdown('<div class="section-title">Texto original</div><div class="section-caption">Escribe, pega o carga un documento.</div>', unsafe_allow_html=True)
    text = st.text_area("Texto original", key="original_text", placeholder="Escribe o pega tu texto aquí...", height=300, max_chars=20000, label_visibility="collapsed")
    st.caption(f"{len(text):,} caracteres")
with col2:
    st.markdown('<div class="section-title">Traducción</div><div class="section-caption">Sumire mostrará aquí el resultado validado.</div>', unsafe_allow_html=True)
    st.text_area("Traducción", value=st.session_state.translated_text or "", placeholder="Tu traducción aparecerá aquí...", height=300, disabled=True, label_visibility="collapsed")

uploaded = st.file_uploader("📂 Subir documento o imagen", type=["pdf", "docx", "txt", "png", "jpg", "jpeg", "webp"], key=f"uploaded_file_{st.session_state.uploader_version}", help="PDF y DOCX se reconstruyen conservando su estructura visual. TXT se traduce como texto. Las imágenes usan Gemini Vision para recuperar texto.")

col1, col2 = st.columns([1, 1], gap="medium")
with col1:
    translate_clicked = st.button("✨ Traducir", use_container_width=True, type="primary")
with col2:
    clear_clicked = st.button("Limpiar", use_container_width=True, on_click=clear_app)

if clear_clicked:
    st.rerun()

if translate_clicked:
    suffix = Path(uploaded.name).suffix.lower() if uploaded is not None else ""
    is_layout_document = suffix in {".pdf", ".docx"}
    has_input = uploaded is not None or bool(text.strip())
    if not has_input:
        st.warning("Escribe un texto o sube un documento primero.")
    elif source_name == target_name:
        st.warning("El idioma de origen y el idioma de destino deben ser diferentes.")
    else:
        with st.status("Procesando Sumire Translate...", expanded=True) as status:
            temp_path = None
            try:
                if is_layout_document:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(uploaded.getbuffer())
                        temp_path = tmp.name
                    st.write(f"Analizando estructura del {suffix.upper()[1:]}...")
                    st.write("Protegiendo matemáticas, números, código, URLs, citas y estructura...")
                    document_bytes, document_format, info = translate_document(temp_path, language_codes[source_name], language_codes[target_name], translate_with_gemini)
                    st.session_state.translated_document = document_bytes
                    st.session_state.translated_document_format = document_format
                    stem = Path(uploaded.name).stem
                    st.session_state.translated_document_name = f"{stem}_sumire_{target_name.lower().replace(' ', '_')}.{document_format}"
                    st.session_state.document_info = info
                    st.session_state.counts = info.get("counts")
                    st.session_state.validation = info.get("validation")
                    st.session_state.translated_text = info.get("translatedText", "") or ""
                    status.update(label="Documento reconstruido y validado", state="complete")
                else:
                    source_text = text.strip()
                    if uploaded is not None:
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
                            try: os.unlink(temp_path)
                            except OSError: pass
                            temp_path = None
                    if not source_text:
                        st.warning("El documento no contiene texto reconocible.")
                    else:
                        st.write(f"Protegiendo contenido antes de traducir: {source_name} → {target_name}...")
                        result = run_pipeline(text=source_text, source_lang=language_codes[source_name], target_lang=language_codes[target_name], translate_fn=translate_with_gemini)
                        st.session_state.translated_text = result.get("translated") or ""
                        st.session_state.validation = result["validation"]
                        st.session_state.counts = result.get("counts")
                        st.session_state.translated_document = None
                        st.session_state.document_info = None
                        status.update(label="Traducción completada y validada" if result.get("translated") is not None else "Traducción bloqueada por validación", state="complete" if result.get("translated") is not None else "error")
                if st.session_state.translated_text or st.session_state.translated_document:
                    st.rerun()
            except Exception as exc:
                status.update(label="No se pudo completar la traducción", state="error")
                st.error(str(exc))
            finally:
                if temp_path:
                    try: os.unlink(temp_path)
                    except OSError: pass

if st.session_state.counts is not None:
    counts = st.session_state.counts
    protected_types = counts.get("protectedByType", {})
    type_summary = " · ".join(f"{kind}: {amount}" for kind, amount in protected_types.items()) or "ninguno"
    st.markdown(f'<div class="sumire-stats"><span class="sumire-stat">Palabras totales: <strong>{counts.get("total", 0):,}</strong></span><span class="sumire-stat">Traducibles: <strong>{counts.get("translatable", 0):,}</strong></span><span class="sumire-stat">Elementos protegidos: <strong>{counts.get("protected", 0):,}</strong></span><span class="sumire-stat">Protección: <strong>{counts.get("protectedRatio", 0) * 100:.1f}%</strong></span></div>', unsafe_allow_html=True)
    st.caption(f"Protección por tipo: {type_summary}")

if st.session_state.document_info is not None:
    info = st.session_state.document_info
    pages = info.get("pages")
    blocks = info.get("textBlocks", 0)
    label = f"{pages} páginas · " if pages is not None else ""
    st.markdown(f'<div class="document-result">📄 <strong>Documento reconstruido:</strong> {label}{blocks} bloques de texto procesados. Las imágenes y los elementos gráficos originales se conservaron.</div>', unsafe_allow_html=True)

if st.session_state.validation is not None:
    validation = st.session_state.validation
    if validation.get("passed"):
        st.success("✓ Validación estructural superada: los elementos protegidos fueron restaurados exactamente.")
    else:
        st.warning("⚠ La validación detectó posibles cambios. El resultado no se entrega como traducción válida.")
        if validation.get("issues"):
            with st.expander("Ver detalles de validación"): st.write(validation["issues"])

if st.session_state.translated_document:
    document_format = st.session_state.translated_document_format
    mime = "application/pdf" if document_format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    st.download_button("⬇️ Descargar documento traducido", data=st.session_state.translated_document, file_name=st.session_state.translated_document_name or f"sumire_traduccion.{document_format}", mime=mime, use_container_width=True)
elif st.session_state.translated_text:
    st.download_button("⬇️ Descargar traducción como TXT", data=st.session_state.translated_text, file_name="sumire_traduccion.txt", mime="text/plain", use_container_width=True)

st.markdown('<div class="protection-card"><div class="protection-title">🛡️ Protección de contenido</div><div class="protection-text">Sumire protege matemáticas, números, tablas, código, URLs y citas antes de enviarlos al modelo. En documentos, cada bloque conserva su posición y la reconstrucción reutiliza la página original para mantener imágenes, gráficos, tablas, numeración y pies de figura.</div></div>', unsafe_allow_html=True)
