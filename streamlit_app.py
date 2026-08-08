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

/* =====================================================
   FONDO GENERAL
===================================================== */

.stApp {
    background: #ffffff !important;
}

body {
    background: #ffffff !important;
}

[data-testid="stAppViewContainer"] {
    background: #ffffff !important;
}

[data-testid="stHeader"] {
    background: #ffffff !important;
}

[data-testid="stToolbar"] {
    background: #ffffff !important;
}


/* =====================================================
   CONTENEDOR PRINCIPAL
===================================================== */

.block-container {
    max-width: 1350px !important;

    padding-top: 55px !important;
    padding-bottom: 50px !important;

    padding-left: 50px !important;
    padding-right: 50px !important;
}


/* Ocultar elementos de Streamlit */

#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}


/* =====================================================
   LOGO
===================================================== */

.logo {
    font-family: Georgia, serif;
    font-size: 28px;
    font-weight: 600;

    color: #252640;

    line-height: 1;
}

.logo-sub {
    font-family: Arial, sans-serif;

    font-size: 11px;

    letter-spacing: 4px;

    color: #6043bd;

    margin-top: 5px;
}


/* =====================================================
   MENÚ SUPERIOR
===================================================== */

.menu {
    text-align: center;

    padding-top: 8px;

    font-family: Arial, sans-serif;

    font-size: 15px;

    color: #4d4b58;
}

.menu .active {
    color: #4c35a5;
    font-weight: 500;
}


/* =====================================================
   BOTONES SUPERIORES
===================================================== */

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


/* =====================================================
   BOTÓN REGISTRARSE
===================================================== */

.register-button > button {

    background: linear-gradient(
        135deg,
        #6547c7,
        #4c2ca8
    ) !important;

    color: #ffffff !important;

    border: none !important;

    box-shadow:
        0 6px 15px rgba(79, 47, 170, 0.18) !important;
}

.register-button > button:hover {

    background: #5437b3 !important;

    color: #ffffff !important;
}


/* =====================================================
   HERO
===================================================== */

.hero-space {
    height: 35px;
}

.small-title {

    color: #6043bd;

    font-family: Arial, sans-serif;

    font-size: 14px;

    letter-spacing: 2px;

    margin-top: 45px;

    margin-bottom: 12px;
}

.main-title {

    font-family: Georgia, serif;

    font-size: 52px;

    line-height: 1.08;

    color: #20233d;

    margin-top: 0;

    margin-bottom: 18px;
}

.main-title span {

    color: #8c6bd2;

    font-style: italic;
}

.description {

    font-family: Georgia, serif;

    font-size: 19px;

    color: #55545c;

    line-height: 1.5;

    margin-bottom: 30px;
}


/* =====================================================
   TARJETA DEL TRADUCTOR
===================================================== */

.translator-container {

    background: #ffffff;

    border: 1px solid #e8e3eb;

    border-radius: 20px;

    padding: 25px;

    box-shadow:
        0 10px 35px rgba(60, 40, 90, 0.07);

    margin-top: 15px;

    margin-bottom: 25px;
}


/* =====================================================
   SELECTORES DE IDIOMA
===================================================== */

div[data-testid="stSelectbox"] label {

    color: #4d4960 !important;

    font-size: 13px !important;
}

div[data-baseweb="select"] > div {

    background-color: #ffffff !important;

    border-color: #ddd7e3 !important;

    border-radius: 12px !important;

    min-height: 50px !important;
}


/* =====================================================
   CAJAS DE TEXTO
===================================================== */

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

    box-shadow:
        0 0 0 1px #7558c5 !important;
}


/* Etiquetas */

div[data-testid="stTextArea"] label {

    color: #4d4960 !important;

    font-size: 13px !important;
}


/* =====================================================
   CONTADOR
===================================================== */

.character-count {

    color: #77727d;

    font-size: 13px;

    text-align: right;
}


/* =====================================================
   BOTÓN TRADUCIR
===================================================== */

.translate-button > button {

    background: linear-gradient(
        135deg,
        #6547c7,
        #4c2ca8
    ) !important;

    color: white !important;

    border: none !important;

    border-radius: 11px !important;

    min-height: 50px !important;

    font-family: Georgia, serif !important;

    font-size: 18px !important;

    box-shadow:
        0 7px 18px rgba(76, 43, 168, 0.20) !important;
}

.translate-button > button:hover {

    background: #5437b3 !important;

    color: white !important;
}


/* =====================================================
   SUBIDA DE ARCHIVOS
===================================================== */

[data-testid="stFileUploader"] {

    background: #ffffff;

    border: 1px dashed #c6b5e7;

    border-radius: 13px;

    padding: 8px;

}


/* =====================================================
   CARACTERÍSTICAS
===================================================== */

.feature-card {

    background: #ffffff;

    border: 1px solid #eeeaf0;

    border-radius: 18px;

    padding: 22px 18px;

    min-height: 135px;

    box-shadow:
        0 7px 25px rgba(60, 45, 90, 0.05);

    text-align: center;

    transition: transform 0.2s ease;
}

.feature-card:hover {

    transform: translateY(-3px);

    box-shadow:
        0 10px 30px rgba(60, 45, 90, 0.08);
}

.feature-icon {

    font-size: 28px;

    margin-bottom: 8px;
}

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


/* =====================================================
   RESPONSIVE
===================================================== */

@media (max-width: 900px) {

    .block-container {

        padding-left: 25px !important;

        padding-right: 25px !important;
    }

    .main-title {

        font-size: 42px;
    }

    .menu {

        display: none;
    }
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# CABECERA
# =========================================================

col_logo, col_menu, col_buttons = st.columns(
    [2.5, 4.2, 3.3]
)


# -------------------------
# LOGO
# -------------------------

with col_logo:

    st.markdown("""
    <div class="logo">
        🌸 Sumire
    </div>

    <div class="logo-sub">
        TRANSLATE
    </div>
    """, unsafe_allow_html=True)


# -------------------------
# MENÚ
# -------------------------

with col_menu:

    st.markdown("""
    <div class="menu">

        <span class="active">Inicio</span>
        &nbsp;&nbsp;&nbsp;&nbsp;
        Características
        &nbsp;&nbsp;&nbsp;&nbsp;
        Precios
        &nbsp;&nbsp;&nbsp;&nbsp;
        Blog
        &nbsp;&nbsp;&nbsp;&nbsp;
        Contacto

    </div>
    """, unsafe_allow_html=True)


# -------------------------
# BOTONES
# -------------------------

with col_buttons:

    c1, c2, c3 = st.columns([0.8, 1.5, 1.5])

    with c1:

        st.button(
            "☼",
            use_container_width=True
        )

    with c2:

        st.button(
            "Iniciar sesión",
            use_container_width=True
        )

    with c3:

        st.markdown(
            '<div class="register-button">',
            unsafe_allow_html=True
        )

        st.button(
            "Registrarse",
            use_container_width=True
        )

        st.markdown(
            '</div>',
            unsafe_allow_html=True
        )


# =========================================================
# ESPACIO ANTES DEL HERO
# =========================================================

st.markdown(
    '<div class="hero-space"></div>',
    unsafe_allow_html=True
)


# =========================================================
# HERO
# =========================================================

st.markdown("""
<div class="small-title">
    TRADUCCIONES QUE CONECTAN
</div>

<div class="main-title">
    Traduce ideas.<br>
    <span>Conecta mundos.</span> ✦
</div>

<div class="description">
    Traducciones precisas y naturales en segundos.<br>
    Más que palabras, significado.
</div>
""", unsafe_allow_html=True)


# =========================================================
# TARJETA DEL TRADUCTOR
# =========================================================

st.markdown(
    '<div class="translator-container">',
    unsafe_allow_html=True
)


# =========================================================
# IDIOMAS
# =========================================================

col1, col2, col3 = st.columns(
    [4, 0.7, 4]
)


with col1:

    idioma_origen = st.selectbox(
        "Idioma de origen",
        [
            "Español",
            "Inglés",
            "Francés",
            "Portugués",
            "Alemán"
        ]
    )


with col2:

    st.write("")
    st.write("")
    st.markdown(
        """
        <div style="
            text-align:center;
            font-size:26px;
            color:#6043bd;
            padding-top:5px;
        ">
            ⇄
        </div>
        """,
        unsafe_allow_html=True
    )


with col3:

    idioma_destino = st.selectbox(
        "Idioma de destino",
        [
            "Inglés",
            "Español",
            "Francés",
            "Portugués",
            "Alemán"
        ]
    )


st.write("")


# =========================================================
# CAJAS DE TEXTO
# =========================================================

col1, col2 = st.columns(
    2,
    gap="medium"
)


# -------------------------
# TEXTO ORIGINAL
# -------------------------

with col1:

    texto = st.text_area(
        "Texto original",
        placeholder="Escribe o pega tu texto aquí...",
        height=220,
        max_chars=5000
    )

    st.markdown(
        f"""
        <div class="character-count">
            {len(texto)} / 5000
        </div>
        """,
        unsafe_allow_html=True
    )


# -------------------------
# TRADUCCIÓN
# -------------------------

with col2:

    traduccion = st.text_area(
        "Traducción",
        placeholder="Tu traducción aparecerá aquí...",
        height=220,
        disabled=True
    )


st.write("")


# =========================================================
# ARCHIVO + TRADUCIR
# =========================================================

col1, col2 = st.columns(
    [1, 1],
    gap="large"
)


# -------------------------
# ARCHIVO
# -------------------------

with col1:

    archivo = st.file_uploader(
        "Subir documento",
        type=[
            "pdf",
            "docx",
            "txt"
        ]
    )


# -------------------------
# TRADUCIR
# -------------------------

with col2:

    st.markdown(
        '<div class="translate-button">',
        unsafe_allow_html=True
    )

    traducir = st.button(
        "✨  Traducir",
        use_container_width=True
    )

    st.markdown(
        '</div>',
        unsafe_allow_html=True
    )


# =========================================================
# ACCIÓN DEL BOTÓN
# =========================================================

if traducir:

    if texto.strip():

        st.success(
            f"Texto listo para traducir: "
            f"{idioma_origen} → {idioma_destino}"
        )

    elif archivo is not None:

        st.success(
            f"Archivo recibido: {archivo.name}"
        )

    else:

        st.warning(
            "Escribe un texto o sube un documento primero."
        )


# =========================================================
# CERRAR TARJETA
# =========================================================

st.markdown(
    '</div>',
    unsafe_allow_html=True
)


# =========================================================
# CARACTERÍSTICAS
# =========================================================

st.write("")
st.write("")

col1, col2, col3, col4 = st.columns(4)

with col2:
    st.markdown("""
    <div class="feature-card">
        <div class="feature-icon">🛡️</div>
        <div class="feature-title">
            Seguro y confidencial
        </div>
        <div class="feature-text">
            Tus documentos están protegidos.
        </div>
    </div>
    """, unsafe_allow_html=True)


with col3:
    st.markdown("""
    <div class="feature-card">
        <div class="feature-icon">📄</div>
        <div class="feature-title">
            Mantiene el formato
        </div>
        <div class="feature-text">
            Conservamos el diseño original.
        </div>
    </div>
    """, unsafe_allow_html=True)

