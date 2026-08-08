import streamlit as st

# ---------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------

st.set_page_config(
    page_title="Sumire Translate",
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------------------------------------------------------
# CSS
# ---------------------------------------------------------

st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:ital,wght@0,400;0,500;0,600;1,500&display=swap');

/* ======================================================
   GENERAL
====================================================== */

.stApp {
    background: #ffffff;
    color: #20233c;
    font-family: 'DM Sans', sans-serif;
}

.main {
    padding: 0 !important;
}

.block-container {
    max-width: 1380px;
    padding-top: 20px !important;
    padding-bottom: 50px !important;
}

/* Ocultar elementos propios de Streamlit */

#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

header {
    visibility: hidden;
}

/* ======================================================
   NAVBAR
====================================================== */

.navbar {
    width: 100%;
    height: 72px;

    display: flex;
    align-items: center;
    justify-content: space-between;

    padding: 0 5px;
    margin-bottom: 35px;
}

/* Logo */

.logo-container {
    display: flex;
    align-items: center;
    gap: 13px;
}

.logo-flower {
    font-size: 43px;
    line-height: 1;
}

.logo-text {
    display: flex;
    flex-direction: column;
}

.logo-name {
    font-family: 'Playfair Display', serif;
    font-size: 25px;
    font-weight: 600;
    color: #20233c;
    line-height: 1;
}

.logo-subtitle {
    font-size: 12px;
    letter-spacing: 5px;
    color: #5740b8;
    margin-top: 5px;
}

/* Menú */

.nav-menu {
    display: flex;
    align-items: center;
    gap: 38px;
    margin-left: 80px;
}

.nav-item {
    font-size: 15px;
    color: #444455;
    text-decoration: none;
    padding: 12px 4px;
}

.nav-item:hover {
    color: #4d35b5;
}

.nav-item.active {
    color: #3f2aa5;
    border-bottom: 2px solid #4b32bb;
}

/* Botones derecha */

.nav-actions {
    display: flex;
    align-items: center;
    gap: 14px;
}

.theme-button {
    width: 62px;
    height: 47px;

    border: 1px solid #ddd9df;
    border-radius: 25px;

    display: flex;
    align-items: center;
    justify-content: center;

    font-size: 23px;
}

.login-button {
    height: 47px;
    padding: 0 23px;

    border: 1px solid #ddd9df;
    border-radius: 13px;

    display: flex;
    align-items: center;
    justify-content: center;

    color: #27263b;
    font-size: 15px;
}

.register-button {
    height: 47px;
    padding: 0 25px;

    border-radius: 13px;

    background: linear-gradient(
        135deg,
        #6547c7,
        #4a2ca7
    );

    color: white;
    font-size: 15px;

    display: flex;
    align-items: center;
    justify-content: center;

    box-shadow: 0 5px 15px rgba(83, 52, 174, 0.18);
}

/* ======================================================
   HERO
====================================================== */

.hero {
    position: relative;
    min-height: 300px;

    padding: 35px 5px 25px 5px;

    overflow: hidden;
}

.hero-content {
    position: relative;
    z-index: 2;
    max-width: 650px;
}

.eyebrow {
    color: #5a43bb;
    font-size: 14px;
    letter-spacing: 2px;
    font-weight: 500;
    margin-bottom: 15px;
}

.hero-title {
    font-family: 'Playfair Display', serif;

    font-size: 52px;
    line-height: 1.12;

    font-weight: 500;

    color: #1d223d;

    margin: 0;
}

.hero-title span {
    color: #8a6bd2;
    font-style: italic;
}

.hero-description {
    margin-top: 18px;

    color: #55545c;

    font-family: 'Playfair Display', serif;

    font-size: 19px;
    line-height: 1.55;
}

/* Flores */

.flowers {
    position: absolute;

    right: -25px;
    top: -25px;

    width: 560px;

    opacity: 0.7;

    z-index: 1;
}

.flower-line {
    font-size: 150px;
    color: #cdb7ec;
    transform: rotate(-18deg);
}

/* ======================================================
   TRANSLATOR CARD
====================================================== */

.translator-card {

    background: rgba(255,255,255,0.92);

    border: 1px solid #eeeaf0;

    border-radius: 19px;

    padding: 24px 25px 25px 25px;

    box-shadow:
        0 10px 35px rgba(60, 45, 90, 0.07);

    margin-top: 8px;
}

/* Language row */

.language-row {
    display: flex;
    align-items: center;
    gap: 20px;

    margin-bottom: 20px;
}

.language-box {
    height: 54px;

    border: 1px solid #e5e1e7;

    border-radius: 13px;

    display: flex;
    align-items: center;

    padding: 0 18px;

    flex: 1;

    background: white;

    font-family: 'Playfair Display', serif;

    font-size: 17px;
}

.flag {
    font-size: 27px;
    margin-right: 14px;
}

.language-arrow {

    width: 54px;
    height: 54px;

    border: 1px solid #ebe6f0;

    border-radius: 50%;

    display: flex;
    align-items: center;
    justify-content: center;

    color: #5435ba;

    font-size: 23px;

    background: white;

    flex-shrink: 0;
}

.detect-button {

    height: 54px;

    padding: 0 20px;

    border: 1px solid #e3dfe7;

    border-radius: 13px;

    display: flex;
    align-items: center;
    justify-content: center;

    color: #4930a8;

    font-size: 14px;

    background: white;

    white-space: nowrap;
}

/* ======================================================
   TEXT BOXES
====================================================== */

.text-area {

    height: 225px;

    border: 1px solid #ddd9df;

    border-radius: 14px;

    background: white;

    padding: 18px;

    color: #66646b;

    font-family: 'Playfair Display', serif;

    font-size: 17px;
}

.text-placeholder {
    color: #77757b;
}

.text-bottom {
    display: flex;
    justify-content: space-between;
    align-items: center;

    margin-top: 145px;
}

.text-tools {
    display: flex;
    gap: 22px;

    font-family: 'DM Sans', sans-serif;

    font-size: 20px;

    color: #55545d;
}

.character-count {
    font-size: 14px;
    color: #55545d;
}

.output-tools {
    display: flex;
    justify-content: space-between;

    margin-top: 145px;

    color: #55545d;

    font-size: 20px;
}

/* ======================================================
   BOTTOM ACTIONS
====================================================== */

.action-row {

    display: flex;

    align-items: center;

    gap: 35px;

    margin-top: 30px;
}

.upload-box {

    height: 66px;

    border: 1px dashed #bba7e6;

    border-radius: 13px;

    display: flex;

    align-items: center;
    justify-content: center;

    flex: 1;

    color: #5235b4;

    background: #fefcff;

    font-size: 15px;
}

.upload-icon {
    font-size: 28px;
    margin-right: 15px;
}

.upload-title {
    font-weight: 600;
    font-size: 16px;
}

.upload-description {
    color: #66606d;
    font-size: 13px;
    margin-top: 2px;
}

.translate-button {

    height: 64px;

    width: 285px;

    border: none;

    border-radius: 10px;

    background: linear-gradient(
        135deg,
        #6545c6,
        #4c2ba9
    );

    color: white;

    font-family: 'Playfair Display', serif;

    font-size: 20px;

    display: flex;

    align-items: center;

    justify-content: center;

    box-shadow: 0 8px 20px rgba(76,43,169,0.2);
}

/* ======================================================
   FEATURES
====================================================== */

.features {

    margin-top: 20px;

    border: 1px solid #eeeaf0;

    border-radius: 19px;

    background: white;

    box-shadow:
        0 8px 30px rgba(60,45,90,0.05);

    padding: 25px 30px;

    display: grid;

    grid-template-columns:
        repeat(4, 1fr);

    gap: 25px;
}

.feature {

    display: flex;

    align-items: center;

    gap: 17px;

    padding-right: 25px;

    border-right: 1px solid #eeeaf0;
}

.feature:last-child {
    border-right: none;
}

.feature-icon {

    width: 66px;
    height: 66px;

    border-radius: 50%;

    background: #f5f0fa;

    display: flex;

    align-items: center;
    justify-content: center;

    font-size: 27px;

    color: #5735b9;

    flex-shrink: 0;
}

.feature-title {

    font-family: 'Playfair Display', serif;

    font-size: 17px;

    font-weight: 600;

    color: #24243a;

    margin-bottom: 5px;
}

.feature-description {

    color: #66636b;

    font-size: 14px;

    line-height: 1.5;
}

/* ======================================================
   RESPONSIVE
====================================================== */

@media (max-width: 1000px) {

    .nav-menu {
        display: none;
    }

    .hero-title {
        font-size: 43px;
    }

    .flowers {
        opacity: 0.3;
        width: 450px;
    }

    .features {
        grid-template-columns: repeat(2, 1fr);
    }

    .feature:nth-child(2) {
        border-right: none;
    }
}

@media (max-width: 700px) {

    .block-container {
        padding-left: 15px !important;
        padding-right: 15px !important;
    }

    .navbar {
        margin-bottom: 10px;
    }

    .login-button {
        display: none;
    }

    .hero-title {
        font-size: 38px;
    }

    .hero-description {
        font-size: 17px;
    }

    .language-row {
        flex-wrap: wrap;
    }

    .language-box {
        min-width: 40%;
    }

    .detect-button {
        width: 100%;
    }

    .features {
        grid-template-columns: 1fr;
    }

    .feature {
        border-right: none;
        border-bottom: 1px solid #eeeaf0;
        padding-bottom: 18px;
    }

    .feature:last-child {
        border-bottom: none;
    }

    .action-row {
        flex-direction: column;
    }

    .upload-box,
    .translate-button {
        width: 100%;
    }
}

</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# NAVBAR
# ---------------------------------------------------------

st.markdown("""
<div class="navbar">

    <div class="logo-container">

        <div class="logo-flower">✿</div>

        <div class="logo-text">
            <div class="logo-name">Sumire</div>
            <div class="logo-subtitle">TRANSLATE</div>
        </div>

    </div>


    <div class="nav-menu">

        <div class="nav-item active">Inicio</div>

        <div class="nav-item">Características</div>

        <div class="nav-item">Precios</div>

        <div class="nav-item">Blog</div>

        <div class="nav-item">Contacto</div>

    </div>


    <div class="nav-actions">

        <div class="theme-button">
            ☼
        </div>

        <div class="login-button">
            Iniciar sesión
        </div>

        <div class="register-button">
            Registrarse
        </div>

    </div>

</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# HERO
# ---------------------------------------------------------

st.markdown("""
<div class="hero">

    <div class="hero-content">

        <div class="eyebrow">
            TRADUCCIONES QUE CONECTAN
        </div>

        <h1 class="hero-title">
            Traduce ideas.<br>
            <span>Conecta mundos.</span> ✦
        </h1>

        <div class="hero-description">
            Traducciones precisas y naturales en segundos.<br>
            Más que palabras, significado.
        </div>

    </div>

    <div class="flowers">
        🌸
    </div>

</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# TRANSLATOR
# ---------------------------------------------------------

st.markdown('<div class="translator-card">', unsafe_allow_html=True)


# Idiomas

col1, col2, col3, col4 = st.columns([3.3, 0.45, 3.3, 1.0])

with col1:

    st.markdown("""
    <div class="language-box">
        <span class="flag">🇪🇸</span>
        Español
        <span style="margin-left:auto;">⌄</span>
    </div>
    """, unsafe_allow_html=True)


with col2:

    st.markdown("""
    <div class="language-arrow">
        ⇄
    </div>
    """, unsafe_allow_html=True)


with col3:

    st.markdown("""
    <div class="language-box">
        <span class="flag">🇬🇧</span>
        Inglés
        <span style="margin-left:auto;">⌄</span>
    </div>
    """, unsafe_allow_html=True)


with col4:

    st.markdown("""
    <div class="detect-button">
        Detectar idioma ✦
    </div>
    """, unsafe_allow_html=True)


st.markdown("<br>", unsafe_allow_html=True)


# ---------------------------------------------------------
# CAJAS DE TEXTO
# ---------------------------------------------------------

col1, col2 = st.columns(2, gap="medium")


with col1:

    st.markdown("""
    <div class="text-area">

        <div class="text-placeholder">
            Escribe o pega tu texto aquí...
        </div>

        <div class="text-bottom">

            <div class="text-tools">
                🎙
                <span class="character-count">
                    0 / 5000
                </span>
            </div>

            <div>
                ×
            </div>

        </div>

    </div>
    """, unsafe_allow_html=True)


with col2:

    st.markdown("""
    <div class="text-area">

        <div class="text-placeholder">
            Tu traducción aparecerá aquí...
        </div>

        <div class="output-tools">

            <div>
                🔊 &nbsp;&nbsp; ⧉ &nbsp;&nbsp; ↗
            </div>

            <div>
                ☆
            </div>

        </div>

    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------
# BOTONES
# ---------------------------------------------------------

st.markdown("""
<div class="action-row">

    <div class="upload-box">

        <div class="upload-icon">
            ☁
        </div>

        <div>
            <div class="upload-title">
                Subir documento
            </div>

            <div class="upload-description">
                .pdf, .docx, .txt (Máx. 50MB)
            </div>
        </div>

    </div>


    <div class="translate-button">
        Traducir &nbsp; ✦
    </div>

</div>
""", unsafe_allow_html=True)


st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------------
# CARACTERÍSTICAS
# ---------------------------------------------------------

st.markdown("""
<div class="features">

    <div class="feature">

        <div class="feature-icon">
            ♢
        </div>

        <div>
            <div class="feature-title">
                Seguro y confidencial
            </div>

            <div class="feature-description">
                Tus documentos están<br>
                protegidos con encriptación.
            </div>
        </div>

    </div>


    <div class="feature">

        <div class="feature-icon">
            ⚡
        </div>

        <div>
            <div class="feature-title">
                Traducciones rápidas
            </div>

            <div class="feature-description">
                Resultados precisos en<br>
                segundos.
            </div>
        </div>

    </div>


    <div class="feature">

        <div class="feature-icon">
            ▣
        </div>

        <div>
            <div class="feature-title">
                Mantiene el formato
            </div>

            <div class="feature-description">
                Conservamos el diseño<br>
                original de tus archivos.
            </div>
        </div>

    </div>


    <div class="feature">

        <div class="feature-icon">
            ◎
        </div>

        <div>
            <div class="feature-title">
                Múltiples idiomas
            </div>

            <div class="feature-description">
                Más de 100 idiomas<br>
                disponibles.
            </div>
        </div>

    </div>

</div>
""", unsafe_allow_html=True)
