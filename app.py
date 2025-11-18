import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
from PIL import Image
import os

# ==============================
# CONFIGURACIÓN Y ESTILOS
# ==============================
st.markdown("""
<style>
.main-container {
    max-width: 1000px;
    margin: 0 auto;
    padding: 20px;
    background-color: #f5faff;
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.08);
    color: #000;
}
.header h2 {
    font-size: 2.3rem;
    font-weight: bold;
    color: #000;
    border-bottom: 3px solid #ffd84d;
    display: inline-block;
}
</style>
""", unsafe_allow_html=True)

# --- LOGO ---
logo_path = "logo-intep.png"
if os.path.exists(logo_path):
    logo = Image.open(logo_path)
    st.set_page_config(page_title="Gestión de Préstamos", layout="wide", page_icon=logo)
    with st.sidebar:
        st.image(logo, width=150)
else:
    st.set_page_config(page_title="Gestión de Préstamos", layout="wide", page_icon="🏫")

# ==============================
# GOOGLE SHEETS
# ==============================
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds_json = json.loads(st.secrets["credentials"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)

spreadsheet = client.open("INVENTARIO")

sheet_inventario = spreadsheet.worksheet("INVENTARIO")
sheet_historial = spreadsheet.worksheet("HISTORIAL")
sheet_kits = spreadsheet.worksheet("KITS")  # ← NUEVA HOJA

# ==============================
# FUNCIONES AUXILIARES
# ==============================
def actualizar_estado_y_cantidad(id_componente):
    inventario = sheet_inventario.get_all_records()
    historial = sheet_historial.get_all_records()

    for i, item in enumerate(inventario):
        if str(item["ID"]).strip().lower() == str(id_componente).strip().lower():

            total = int(item["Cantidad"])

            total_prestamos = sum(
                int(h["Cantidad"]) for h in historial
                if str(h["ID"]).lower() == str(id_componente).lower()
                and h["Acción"].lower() == "préstamo"
            )

            total_devoluciones = sum(
                int(h["Cantidad"]) for h in historial
                if str(h["ID"]).lower() == str(id_componente).lower()
                and h["Acción"].lower() == "devolución"
            )

            prestado_activo = max(total_prestamos - total_devoluciones, 0)
            disponible = total - prestado_activo

            if disponible == total:
                estado = "Disponible"
            elif disponible > 0:
                estado = "Parcialmente prestado"
            else:
                estado = "No disponible"

            sheet_inventario.update_cell(i + 2, 4, disponible)
            sheet_inventario.update_cell(i + 2, 5, estado)
            break

# ==============================
# MENÚ
# ==============================
st.sidebar.title("Menú")
menu = st.sidebar.radio("Selecciona una opción:", [
    "Inventario",
    "Registrar Préstamo",
    "Registrar Devolución",
    "Historial",
    "Kits"      # ← NUEVA OPCIÓN DE MENÚ
])

inventario = pd.DataFrame(sheet_inventario.get_all_records())

# ==============================
# 1. INVENTARIO
# ==============================
if menu == "Inventario":
    st.title("Inventario Actual")
    busqueda = st.text_input("Buscar componente por nombre o ID:")

    if busqueda:
        filtro = inventario[
            inventario["Componente"].str.contains(busqueda, case=False, na=False) |
            inventario["ID"].astype(str).str.contains(busqueda, case=False, na=False)
        ]
    else:
        filtro = inventario

    st.dataframe(filtro, use_container_width=True)

# ==============================
# 2. REGISTRAR PRÉSTAMO
# ==============================
elif menu == "Registrar Préstamo":
    st.title("Registrar Préstamo")

    busqueda = st.text_input("Buscar componente (por nombre o ID):")
    if busqueda:
        coincidencias = inventario[
            inventario["Componente"].str.contains(busqueda, case=False, na=False) |
            inventario["ID"].astype(str).str.contains(busqueda, case=False, na=False)
        ]
        st.dataframe(coincidencias)

    with st.form("prestamo_form"):
        id_componente = st.text_input("ID del componente")
        persona = st.text_input("Persona responsable del préstamo")
        cantidad_prestamo = st.number_input("Cantidad a prestar", min_value=1)
        fecha_prestamo = st.date_input("Fecha del préstamo")
        obs = st.text_area("Observaciones (opcional)")
        submit = st.form_submit_button("Registrar préstamo")

        if submit:
            inventario = sheet_inventario.get_all_records()

            fila = next(
                (i for i, item in enumerate(inventario)
                 if str(item["ID"]).lower() == id_componente.lower()), None)

            if fila is None:
                st.error("ID no encontrado en inventario.")
            else:
                disponible = int(inventario[fila]["Cantidad"])
                componente = inventario[fila]["Componente"]

                if cantidad_prestamo > disponible:
                    st.error(f"Solo hay {disponible} unidades.")
                else:
                    sheet_historial.append_row([
                        id_componente, componente, persona, "Préstamo",
                        str(fecha_prestamo), cantidad_prestamo, obs
                    ])
                    actualizar_estado_y_cantidad(id_componente)
                    st.success("Préstamo registrado correctamente.")

# ==============================
# 3. REGISTRAR DEVOLUCIÓN
# ==============================
elif menu == "Registrar Devolución":
    st.title("Registrar Devolución")

    busqueda = st.text_input("Buscar componente (por nombre o ID):")
    if busqueda:
        st.dataframe(
            inventario[
                inventario["Componente"].str.contains(busqueda, case=False, na=False) |
                inventario["ID"].astype(str).str.contains(busqueda, case=False, na=False)
            ]
        )

    with st.form("devolucion_form"):
        id_dev = st.text_input("ID del componente")
        persona = st.text_input("Persona que devuelve")
        cantidad = st.number_input("Cantidad devuelta", min_value=1)
        fecha = st.date_input("Fecha de devolución")
        obs = st.text_area("Observaciones (opcional)")
        submit = st.form_submit_button("Registrar devolución")

        if submit:
            historial = sheet_historial.get_all_records()

            total_prestado = sum(
                int(h["Cantidad"]) for h in historial
                if h["ID"] == id_dev and h["Acción"] == "Préstamo" and h["Persona"].lower() == persona.lower()
            )

            total_devuelto = sum(
                int(h["Cantidad"]) for h in historial
                if h["ID"] == id_dev and h["Acción"] == "Devolución" and h["Persona"].lower() == persona.lower()
            )

            pendiente = total_prestado - total_devuelto

            if pendiente <= 0:
                st.error("No hay préstamos pendientes para esta persona.")
            elif cantidad > pendiente:
                st.error(f"Solo puede devolver {pendiente}.")
            else:
                comp = next(
                    (h["Componente"] for h in historial
                     if h["ID"] == id_dev and h["Acción"] == "Préstamo"),
                    "Desconocido"
                )

                sheet_historial.append_row([
                    id_dev, comp, persona, "Devolución",
                    str(fecha), cantidad, obs
                ])

                actualizar_estado_y_cantidad(id_dev)
                st.success("Devolución registrada.")

# ==============================
# 4. HISTORIAL
# ==============================
elif menu == "Historial":
    st.title("Historial")
    st.dataframe(pd.DataFrame(sheet_historial.get_all_records()), use_container_width=True)

# ==============================
# 5. KITS  ← NUEVA SECCIÓN
# ==============================
elif menu == "Kits":
    st.title("Kits disponibles")

    kits_df = pd.DataFrame(sheet_kits.get_all_records())

    busqueda = st.text_input("Buscar kit por nombre o ID:")

    if busqueda:
        filtro = kits_df[
            kits_df["KIT"].str.contains(busqueda, case=False, na=False) |
            kits_df["ID"].astype(str).str.contains(busqueda, case=False, na=False)
        ]
    else:
        filtro = kits_df

    st.dataframe(filtro, use_container_width=True)





































