import streamlit as st

st.set_page_config(
    page_title="Sumire Translate",
    page_icon="🌸",
    layout="wide"
)

# =========================
# ESTILOS
# =========================

st.markdown("""
<style>

.stApp {
    background-color: #ffffff;
}

.block-container {
    max-width: 1350px;
    padding-top: 25px;
}

/* Ocultar menú y footer de Streamlit */
#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

/* Logo */
.logo {
    font-family: Georgia, serif;
    font-size: 28px;
    font-weight: bold;
    color: #252640;
}

.logo-sub {
    font-family: Arial, sans-serif;
    font-size: 11px;
    letter-spacing: 4px;
    color: #6043bd;
}

/* Título */
.small-title {
    color: #6043bd;
    font-size: 14px;
    letter-spacing: 2px;
    margin-top: 70px;
}

.main-title {
    font-family: Georgia, serif;
    font-size: 52px;
    line-height: 1.1;
    color: #20233d;
    margin-top: 10px;
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
}

/* Tarjeta */
.translator-card {
    background: #ffffff;
    border: 1px solid #e8e4ea;
    border-radius: 18px;
    padding: 25px;
    box-shadow: 0px 8px 30px rgba(60, 40, 90, 0.07);
}

/* Características */
.feature-card {
    background: #ffffff;
    border: 1px solid #eeeaf0;
    border-radius: 18px;
    padding: 22px;
    text-align: center;
    box-shadow: 0px 5px 20px rgba(60, 40, 90, 0.05);
}

.feature-icon {
    font-size: 30px;
}

.feature-title {
    font-family: Georgia, serif;
    font-size: 17px;
    font-weight: bold;
    color: #29283d;
}

.feature-text {
    font-size: 14px;
    color: #66636b;
}

</style>
""", unsafe_allow_html=True)


# =========================
# CABECERA
# =========================

col_logo, col_menu, col_buttons = st.columns([2.2, 4, 2.8])

with col_logo:
    st.markdown("""
    <div class="logo">
        🌸 Sumire
    </div>

    <div class="logo-sub">
        TRANSLATE
    </div>
    """, unsafe_allow_html=True)


with col_menu:
    st.write("")
    st.write("Inicio    Características    Precios    Blog    Contacto")


with col_buttons:
    c1, c2, c3 = st.columns(3)

    with c1:
        st.button("☼")

    with c2:
        st.button("Iniciar sesión")

    with c3:
        st.button("Registrarse")


# =========================
# HERO
# =========================

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


st.write("")


# =========================
# TRADUCTOR
# =========================

st.markdown('<div class="translator-card">', unsafe_allow_html=True)

# Idiomas

col1, col2, col3 = st.columns([4, 1, 4])

with col1:
    idioma_origen = st.selectbox(
        "Idioma de origen",
        ["Español", "Inglés", "Francés", "Portugués", "Alemán"]
    )

with col2:
    st.write("")
    st.write("")
    st.markdown(
        "<div style='text-align:center;font-size:25px;color:#6043bd;'>⇄</div>",
        unsafe_allow_html=True
    )

with col3:
    idioma_destino = st.selectbox(
        "Idioma de destino",
        ["Inglés", "Español", "Francés", "Portugués", "Alemán"]
    )


# Cajas de texto

col1, col2 = st.columns(2)

with col1:

    texto = st.text_area(
        "Texto original",
        placeholder="Escribe o pega tu texto aquí...",
        height=220,
        max_chars=5000
    )

    st.caption(f"{len(texto)} / 5000")


with col2:

    traduccion = st.text_area(
        "Traducción",
        placeholder="Tu traducción aparecerá aquí...",
        height=220,
        disabled=True
    )


# Botones

col1, col2 = st.columns([1, 1])

with col1:

    archivo = st.file_uploader(
        "Subir documento",
        type=["pdf", "docx", "txt"]
    )

with col2:

    st.write("")

    if st.button(
        "✨ Traducir",
        use_container_width=True,
        type="primary"
    ):

        if texto.strip():
            st.success(
                f"Texto listo para traducir de {idioma_origen} → {idioma_destino}"
            )
        else:
            st.warning("Escribe primero un texto.")


st.markdown('</div>', unsafe_allow_html=True)


# =========================
# CARACTERÍSTICAS
# =========================

st.write("")
st.write("")

col1, col2, col3, col4 = st.columns(4)

with col1:
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


with col2:
    st.markdown("""
    <div class="feature-card">
        <div class="feature-icon">⚡</div>
        <div class="feature-title">
            Traducciones rápidas
        </div>
        <div class="feature-text">
            Resultados precisos en segundos.
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


with col4:
    st.markdown("""
    <div class="feature-card">
        <div class="feature-icon">🌐</div>
        <div class="feature-title">
            Múltiples idiomas
        </div>
        <div class="feature-text">
            Más de 100 idiomas disponibles.
        </div>
    </div>
    """, unsafe_allow_html=True)
