import streamlit as st

# =========================================================
# CONFIGURACIÓN
# =========================================================
st.set_page_config(
    page_title="Sumire Translate",
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================================================
# ESTILOS
# =========================================================
st.markdown("""
<style>
/* FORZAR MODO CLARO Y FONDO GENERAL */
.stApp { background-color: #ffffff !important; }
[data-testid="stAppViewContainer"] { background-color: #ffffff !important; }
[data-testid="stHeader"] { background-color: #ffffff !important; }
body { background-color: #ffffff !important; color: #20233d !important; }

/* CONTENEDOR PRINCIPAL */
.block-container {
    max-width: 1350px !important;
    padding-top: 55px !important;
    padding-bottom: 60px !important;
    padding-left: 50px !important;
    padding-right: 50px !important;
}

/* Ocultar elementos de Streamlit */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

/* LOGO */
.logo {
    font-family: Georgia, serif;
    font-size: 29px;
    font-weight: 600;
    color: #252640;
    line-height: 1;
}
.logo-sub {
    font-family: Arial, sans-serif;
    font-size: 10px;
    letter-spacing: 4px;
    color: #6043bd;
    margin-top: 6px;
}

/* MENÚ */
.menu {
    text-align: center;
    padding-top: 10px;
    font-family: Arial, sans-serif;
    font-size: 15px;
    color: #4d4b58;
    white-space: nowrap;
}
.menu-active {
    color: #4c35a5;
    border-bottom: 2px solid #6043bd;
    padding-bottom: 8px;
}

/* BOTONES SUPERIORES Y DE NAVEGACIÓN */
.stButton > button {
    background-color: #ffffff !important;
    color: #4d3a99 !important;
    border: 1px solid #d8d0e6 !important;
    border-radius: 12px !important;
    min-height: 45px !important;
    font-size: 14px !important;
    box-shadow: none !important;
    transition: all 0.2s ease;
}
.stButton > button:hover {
    background-color: #faf7ff !important;
    border-color: #7254c5 !important;
    color: #4d35a5 !important;
}

/* Botones principales (Traducir / Registrarse) */
button[kind="primary"] {
    background: linear-gradient(135deg, #6547c7, #4c2ca8) !important;
    color: white !important;
    border: none !important;
    box-shadow: 0 6px 16px rgba(79, 47, 170, 0.18) !important;
}
button[kind="primary"]:hover {
    background: #5437b3 !important;
    color: white !important;
}

/* HERO */
.hero { margin-top: 85px; margin-bottom: 35px; }
.small-title {
    color: #6043bd;
    font-family: Arial, sans-serif;
    font-size: 14px;
    letter-spacing: 2px;
    margin-bottom: 12px;
}
.main-title {
    font-family: Georgia, serif;
    font-size: 52px;
    line-height: 1.08;
    color: #20233d;
    margin: 0;
    padding: 0;
}
.main-title span { color: #8c6bd2; font-style: italic; }
.description {
    font-family: Georgia, serif;
    font-size: 19px;
    color: #55545c;
    line-height: 1.5;
    margin-top: 18px;
}

/* SELECTORES DE IDIOMAS */
div[data-testid="stSelectbox"] label { color: #4d4960 !important; font-size: 13px !important; }
div[data-baseweb="select"] > div {
    background-color: #ffffff !important;
    border: 1px solid #ddd7e3 !important;
    border-radius: 12px !important;
    min-height: 48px !important;
    color: #20233d !important;
}

/* CAJAS DE TEXTO */
div[data-testid="stTextArea"] label { color: #4d4960 !important; font-size: 13px !important; }
div[data-testid="stTextArea"] textarea {
    background-color: #ffffff !important;
    color: #333342 !important;
    border: 1px solid #ddd8e1 !important;
    border-radius: 13px !important;
    font-family: Georgia, serif !important;
    font-size: 16px !important;
}
div[data-testid="stTextArea"] textarea:focus {
    border-color: #7558c5 !important;
    box-shadow: 0 0 0 1px #7558c5 !important;
}

/* CONTADOR DE CARACTERES */
.character-count {
    color: #77727d;
    font-size: 13px;
    text-align: right;
    margin-top: -10px;
    margin-bottom: 5px;
}

/* BOTÓN DE SUBIR ARCHIVOS */
[data-testid="stFileUploader"] {
    background-color: #fcfaff !important;
    border: 2px dashed #c5b4e5 !important;
    border-radius: 15px !important;
    padding: 15px !important;
    transition: all 0.3s ease;
}
[data-testid="stFileUploader"]:hover {
    border-color: #7558c5 !important;
    background-color: #f6f2fc !important;
}
[data-testid="stFileUploader"] section > button {
    background-color: #ffffff !important;
    color: #6547c7 !important;
    border: 1px solid #c5b4e5 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
[data-testid="stFileUploader"] section > button:hover {
    background-color: #6547c7 !important;
    color: #ffffff !important;
}
[data-testid="stFileUploadDropzone"] div {
    color: #4d4960 !important;
}
[data-testid="stFileUploadDropzone"] small {
    color: #8c6bd2 !important;
}

/* CARACTERÍSTICAS */
.features-title {
    font-family: Georgia, serif;
    font-size: 25px;
    color: #27273d;
    text-align: center;
    margin-top: 35px;
    margin-bottom: 20px;
}
.feature-card {
    background-color: #ffffff;
    border: 1px solid #eeeaf0;
    border-radius: 18px;
    padding: 22px 18px;
    min-height: 145px;
    box-shadow: 0 7px 25px rgba(60, 45, 90, 0.05);
    text-align: center;
}
.feature-icon { font-size: 28px; margin-bottom: 8px; }
.feature-title {
    font-family: Georgia, serif;
    font-size: 17px;
    font-weight: 600;
    color: #29283d;
    margin-bottom: 7px;
}
.feature-text {
    font-family: Arial, sans-serif;
    font-size: 13px;
    color: #66636b;
    line-height: 1.5;
}

/* RESPONSIVE (CELULARES) */
@media (max-width: 900px) {
    .block-container { padding-left: 25px !important; padding-right: 25px !important; }
    .hero { margin-top: 50px; }
    .main-title { font-size: 42px; }
    .menu { display: none; }
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# CABECERA
# =========================================================
col_logo, col_menu, col_buttons = st.columns([2.5, 4.3, 3.2])

with col_logo:
    st.markdown("""
    <div class="logo">🌸 Sumire</div>
    <div class="logo-sub">TRANSLATE</div>
    """, unsafe_allow_html=True)

with col_menu:
    st.markdown("""
    <div class="menu">
        <span class="menu-active">Inicio</span>
        &nbsp;&nbsp;&nbsp;&nbsp; Características
        &nbsp;&nbsp;&nbsp;&nbsp; Precios
        &nbsp;&nbsp;&nbsp;&nbsp; Blog
        &nbsp;&nbsp;&nbsp;&nbsp; Contacto
    </div>
    """, unsafe_allow_html=True)

with col_buttons:
    c1, c2, c3 = st.columns([0.8, 1.5, 1.5])
    with c1:
        st.button("☼", use_container_width=True)
    with c2:
        st.button("Iniciar sesión", use_container_width=True)
    with c3:
        st.button("Registrarse", use_container_width=True, type="primary")

# =========================================================
# HERO
# =========================================================
st.markdown("""
<div class="hero">
    <div class="small-title">TRADUCCIONES QUE CONECTAN</div>
    <div class="main-title">Traduce ideas.<br><span>Conecta mundos.</span> ✦</div>
    <div class="description">Traducciones precisas y naturales en segundos.<br>Más que palabras, significado.</div>
</div>
""", unsafe_allow_html=True)

# =========================================================
# LÓGICA DE INTERCAMBIO Y ESTADO DE SESIÓN
# =========================================================
if "idioma_origen" not in st.session_state:
    st.session_state.idioma_origen = "Español"
if "idioma_destino" not in st.session_state:
    st.session_state.idioma_destino = "Inglés"

def intercambiar_idiomas():
    st.session_state.idioma_origen, st.session_state.idioma_destino = (
        st.session_state.idioma_destino,
        st.session_state.idioma_origen
    )

# =========================================================
# TRADUCTOR
# =========================================================
lista_idiomas = ["Español", "Inglés", "Francés", "Portugués", "Alemán"]

col1, col2, col3 = st.columns([4, 1, 4])

with col1:
    idioma_origen = st.selectbox(
        "Idioma de origen", 
        lista_idiomas, 
        key="idioma_origen"
    )

with col2:
    st.write("")
    st.write("")
    st.button("⇄", on_click=intercambiar_idiomas, use_container_width=True)

with col3:
    idioma_destino = st.selectbox(
        "Idioma de destino", 
        lista_idiomas, 
        key="idioma_destino"
    )

st.write("")

col1, col2 = st.columns(2, gap="medium")
with col1:
    texto = st.text_area("Texto original", placeholder="Escribe o pega tu texto aquí...", height=220, max_chars=5000)
    st.markdown(f'<div class="character-count">{len(texto)} / 5000</div>', unsafe_allow_html=True)
with col2:
    traduccion = st.text_area("Traducción", placeholder="Tu traducción aparecerá aquí...", height=220, disabled=True)

st.write("")

col1, col2 = st.columns(2, gap="large")
with col1:
    archivo = st.file_uploader("📂 Subir documento (.pdf, .docx, .txt)", type=["pdf", "docx", "txt"])
with col2:
    st.write("")
    traducir = st.button("✨ Traducir", use_container_width=True, type="primary")

if traducir:
    if texto.strip():
        st.success(f"Texto listo para traducir: {idioma_origen} → {idioma_destino}")
    elif archivo is not None:
        st.success(f"Archivo recibido: {archivo.name}")
    else:
        st.warning("Escribe un texto o sube un documento primero.")

# =========================================================
# CARACTERÍSTICAS
# =========================================================
st.markdown('<div class="features-title">Todo lo que necesitas para traducir</div>', unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4, gap="medium")
with col2:
    st.markdown("""
    <div class="feature-card">
        <div class="feature-icon">🛡️</div>
        <div class="feature-title">Seguro y confidencial</div>
        <div class="feature-text">Tus documentos están protegidos.</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="feature-card">
        <div class="feature-icon">📄</div>
        <div class="feature-title">Mantiene el formato</div>
        <div class="feature-text">Conservamos el diseño original de tus archivos.</div>
    </div>
    """, unsafe_allow_html=True)
