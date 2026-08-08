import streamlit as st

# Título de tu página
st.title("Traductor Sumitraslate 🌍")

# Mensaje de bienvenida
st.write("¡Hola! Sube tu documento aquí para traducirlo manteniendo el formato original.")

# Botón para subir archivos
archivo_subido = st.file_uploader("Elige un archivo (Word, PDF, etc.)")

# Acción cuando se sube un archivo
if archivo_subido is not None:
    st.success("¡Archivo subido con éxito! (La función de traducción estará lista pronto).")
