from __future__ import annotations

import streamlit as st

from backend.billing import FREE_WORDS, MAX_PAYMENT_PEN, PACKAGES, money, new_order_id

st.set_page_config(page_title="Planes y pago · Sumire Translate", page_icon="💳", layout="wide")

st.markdown(
    """
    <style>
    :root { --ink:#252640; --muted:#6f6d78; --primary:#6043bd; --soft:#8c6bd2; --border:#d9cff0; --bg:#fbfafc; }
    .stApp { background:linear-gradient(180deg,#fff 0%,var(--bg) 100%); color:var(--ink); }
    .block-container { max-width:1100px; padding-top:42px; padding-bottom:70px; }
    .brand { font-family:Georgia,serif; font-size:28px; font-weight:600; color:var(--ink); }
    .eyebrow { color:var(--primary); font-size:12px; letter-spacing:2px; font-weight:700; margin-top:26px; }
    h1 { font-family:Georgia,serif !important; color:#20233d !important; }
    .intro { max-width:720px; color:var(--muted); font-size:17px; line-height:1.55; }
    .card { border:1px solid var(--border); border-radius:18px; padding:20px; background:#fff; height:100%; box-shadow:0 4px 18px rgba(96,67,189,.05); }
    .price { font-family:Georgia,serif; font-size:30px; color:var(--primary); font-weight:700; margin:8px 0; }
    .small { color:var(--muted); font-size:13px; }
    .tag { display:inline-block; padding:5px 9px; border-radius:999px; background:#f5f1ff; color:var(--primary); font-size:11px; font-weight:700; }
    .notice { border:1px solid var(--border); border-radius:16px; padding:17px 19px; background:#fcfaff; margin:20px 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="brand">🌸 Sumire Translate</div>', unsafe_allow_html=True)
st.markdown('<div class="eyebrow">MODELO BETA</div>', unsafe_allow_html=True)
st.title("Traduce más cuando lo necesites")
st.markdown(
    f'<div class="intro">Empieza con <strong>{FREE_WORDS:,} palabras gratis</strong>. Si necesitas más, compra un paquete puntual. Durante la beta mantenemos precios muy bajos mientras seguimos mejorando la velocidad, los PDF, la reconstrucción y la cobertura de idiomas.</div>',
    unsafe_allow_html=True,
)

st.markdown("### Gratis")
st.markdown(
    f'<div class="card"><span class="tag">PARA PROBAR SUMIRE</span><div class="price">S/ 0</div><strong>{FREE_WORDS:,} palabras traducibles</strong><p class="small">Cuota inicial para probar traducciones técnicas, protección matemática y validación.</p></div>',
    unsafe_allow_html=True,
)

st.markdown("### 🌸 Precios beta")
cols = st.columns(4)
for column, package in zip(cols, PACKAGES):
    with column:
        st.markdown(
            f'<div class="card"><span class="tag">BETA</span><h3>{package.name}</h3><div class="price">{money(package.price)}</div><p class="small">{package.description}</p></div>',
            unsafe_allow_html=True,
        )

st.caption(f"Límite temporal de compra durante la beta: {money(MAX_PAYMENT_PEN)} por pedido.")

st.markdown("---")
st.markdown("### 💳 Solicitar una compra")
package_labels = {f"{p.name} — {money(p.price)}": p for p in PACKAGES}
selected_label = st.selectbox("Elige el paquete", list(package_labels))
selected = package_labels[selected_label]

if selected.price > MAX_PAYMENT_PEN:
    st.error("Este paquete supera el límite temporal de la beta.")
elif st.button("Generar solicitud de pago", type="primary", use_container_width=True):
    order_id = new_order_id()
    st.session_state["sumire_order_id"] = order_id
    st.session_state["sumire_order_package"] = selected.key

order_id = st.session_state.get("sumire_order_id")
if order_id:
    st.markdown(
        f'<div class="notice"><strong>Solicitud {order_id}</strong><br>Paquete: {selected.name}<br>Total: <strong>{money(selected.price)}</strong><br><br>Conserva este código y úsalo al enviar tu comprobante. La traducción de pago se habilita después de la verificación.</div>',
        unsafe_allow_html=True,
    )

st.markdown("### Yape / Plin")
yape = st.secrets.get("SUMIRE_YAPE", "")
plin = st.secrets.get("SUMIRE_PLIN", "")
owner = st.secrets.get("SUMIRE_PAYMENT_NAME", "Sumire Translate")

if yape or plin:
    st.info(f"Titular: {owner}")
    if yape:
        st.write(f"**Yape:** {yape}")
    if plin:
        st.write(f"**Plin:** {plin}")
    st.caption("Realiza el pago por el método configurado y conserva el comprobante.")
else:
    st.warning("Aún no se han configurado los datos de Yape/Plin. En Streamlit Secrets define SUMIRE_YAPE y/o SUMIRE_PLIN antes de publicar esta página.")

st.markdown("### Enviar comprobante")
if order_id:
    st.text_input("Código de operación / referencia", key="sumire_payment_reference", placeholder="Ej. código que aparece en tu comprobante")
    st.file_uploader("Comprobante (opcional)", type=["png", "jpg", "jpeg", "pdf"], key="sumire_receipt")
    st.caption("En esta beta, el comprobante se revisa manualmente. No se solicitan datos de tarjetas ni credenciales.")
else:
    st.caption("Primero genera una solicitud para obtener tu código de pedido.")

st.markdown("---")
st.markdown("### 🔐 Verificación del propietario")
st.caption("Zona interna temporal para confirmar un pago recibido. La pasarela automática con Izipay se conectará en el siguiente paso.")
admin_pin = st.text_input("PIN de administración", type="password", key="sumire_admin_pin")
if st.button("Confirmar pago manualmente"):
    configured_pin = st.secrets.get("SUMIRE_ADMIN_PIN", "")
    if not configured_pin:
        st.error("Configura SUMIRE_ADMIN_PIN en Streamlit Secrets antes de usar la verificación.")
    elif admin_pin != configured_pin:
        st.error("PIN incorrecto.")
    elif not order_id:
        st.error("No hay una solicitud de pago activa.")
    elif selected.price > MAX_PAYMENT_PEN:
        st.error(f"El pedido supera el límite temporal de {money(MAX_PAYMENT_PEN)}.")
    else:
        st.session_state["sumire_paid_order"] = order_id
        st.session_state["sumire_paid_words"] = selected.words
        st.session_state["sumire_payment_status"] = "PAID"
        st.success(f"Pago confirmado para {order_id}: {selected.words:,} palabras disponibles.")

if st.session_state.get("sumire_paid_order") == order_id and order_id:
    paid_words = st.session_state.get("sumire_paid_words", 0)
    st.success(f"✓ Pedido PAID · saldo beta: {paid_words:,} palabras.")

st.info("Beta de lanzamiento: 1,000 palabras gratis + paquetes desde S/0.50. El precio máximo temporal es S/3 por pedido. Más adelante ajustaremos los precios según los costos reales y la calidad/velocidad del servicio.")
