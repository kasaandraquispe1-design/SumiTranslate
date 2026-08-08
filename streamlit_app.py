import streamlit as st

# Configuración de la página
st.set_page_config(
    page_title="SumiTranslate",
    page_icon="🌎",
    layout="centered"
)

# Título principal
st.title("🌎 SumiTranslate")
st.subheader("Traduce tus documentos de forma sencilla")

st.write(
    "Sube un documento y podrás traducirlo conservando, "
    "en lo posible, su estructura y contenido."
)

st.divider()

# Selección de idiomas
col1, col2 = st.columns(2)

with col1:
    idioma_origen = st.selectbox(
        "Idioma del documento",
        [
            "Detectar automáticamente",
            "Español",
            "Inglés",
            "Francés",
            "Portugués",
            "Alemán",
            "Italiano"
        ]
    )

with col2:
    idioma_destino = st.selectbox(
        "Traducir a",
        [
            "Español",
            "Inglés",
            "Francés",
            "Portugués",
            "Alemán",
            "Italiano"
        ]
    )

st.divider()

# Subida de archivos
st.subheader("📄 Sube tu documento")

archivo = st.file_uploader(
    "Selecciona un archivo",
    type=["pdf", "docx", "txt"],
    help="Puedes subir PDF, Word o archivos de texto."
)

if archivo is not None:

    st.success(f"Archivo seleccionado: {archivo.name}")

    st.write(
        f"**Tamaño:** {archivo.size / 1024:.1f} KB"
    )

    st.info(
        "🆓 Versión gratuita: podrás traducir documentos "
        "hasta un límite determinado de caracteres."
    )

    if st.button("🌎 Traducir documento", type="primary"):

        st.warning(
            "La traducción todavía está en desarrollo. "
            "Primero estamos preparando el sistema para "
            "leer correctamente tu documento."
        )

st.divider()

# Información del servicio
st.caption(
    "SumiTranslate — Traducción de documentos"
)

st.caption(
    "Versión inicial en desarrollo"
)
