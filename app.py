import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = json.loads(st.secrets["credentials"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)

#hoja de calculo google sheet
spreadsheet = client.open("INVENTARIO")
sheet_inventario = spreadsheet.worksheet("INVENTARIO")
sheet_historial = spreadsheet.worksheet("HISTORIAL")

# ==============================
# FUNCIONES AUXILIARES
# ==============================
def actualizar_estado_y_cantidad(id_componente):
    """Actualiza cantidad disponible y estado del componente según HISTORIAL (sumando cantidades)."""
    inventario = sheet_inventario.get_all_records()
    historial = sheet_historial.get_all_records()

    # Buscar el item en inventario
    for i, item in enumerate(inventario):
        if str(item["ID"]).strip().lower() == str(id_componente).strip().lower():
            total = int(item["Cantidad"])

            # Sumar todas las cantidades de PRÉSTAMO para ese ID
            total_prestamos = sum(
                int(h.get("Cantidad", 0) or 0)
                for h in historial
                if str(h["ID"]).strip().lower() == str(id_componente).strip().lower()
                and str(h["Acción"]).strip().lower() == "préstamo"
            )

            # Sumar todas las cantidades de DEVOLUCIÓN para ese ID
            total_devoluciones = sum(
                int(h.get("Cantidad", 0) or 0)
                for h in historial
                if str(h["ID"]).strip().lower() == str(id_componente).strip().lower()
                and str(h["Acción"]).strip().lower() == "devolución"
            )

            prestado_activo = max(total_prestamos - total_devoluciones, 0)
            cantidad_disponible = max(total - prestado_activo, 0)

            # Determinar nuevo estado
            if prestado_activo == 0:
                nuevo_estado = "Disponible"
            elif prestado_activo < total:
                nuevo_estado = "Parcialmente prestado"
            else:
                nuevo_estado = "No disponible"

            # Actualizar cantidad y estado en INVENTARIO
            sheet_inventario.update_cell(i + 2, 3, cantidad_disponible)  # columna 3 = Cantidad
            sheet_inventario.update_cell(i + 2, 4, nuevo_estado)         # columna 4 = Estado
            break

# ==============================
# CONFIGURACIÓN DE INTERFAZ
# ==============================
st.set_page_config(page_title="Gestión de Préstamos", layout="wide")
st.title("Sistema de Préstamos de Inventario")

inventario = pd.DataFrame(sheet_inventario.get_all_records())
st.subheader("Inventario actual")
st.dataframe(inventario)

# ==============================
# REGISTRAR PRÉSTAMO
# ==============================
st.subheader("Registrar préstamo")

with st.form("prestamo_form"):
    id_componente = st.text_input("ID del componente")
    persona = st.text_input("Persona responsable del préstamo")
    cantidad_prestamo = st.number_input("Cantidad a prestar", min_value=1, step=1)
    fecha_prestamo = st.date_input("Fecha del préstamo")
    observaciones = st.text_area("Observaciones (opcional)")
    submit_prestamo = st.form_submit_button("Registrar préstamo")

    if submit_prestamo:
        if not id_componente or not persona:
            st.error("Debes ingresar el ID y la persona responsable.")
        else:
            inventario = sheet_inventario.get_all_records()
            fila = next((i for i, item in enumerate(inventario)
                         if str(item["ID"]).strip().lower() == str(id_componente).strip().lower()), None)

            if fila is not None:
                disponible = int(inventario[fila]["Cantidad"])
                estado = inventario[fila]["Estado"]
                componente = inventario[fila]["Componente"]

                if disponible <= 0:
                    st.error("No hay unidades disponibles para préstamo.")
                elif cantidad_prestamo > disponible:
                    st.error(f"Solo hay {disponible} unidades disponibles.")
                else:
                    # Registrar préstamo en HISTORIAL
                    sheet_historial.append_row([
                        id_componente, componente, persona,
                        "Préstamo", str(fecha_prestamo), cantidad_prestamo, observaciones
                    ])
                    st.success(f"Préstamo registrado para {componente} ({cantidad_prestamo} unidad/es)")
                    actualizar_estado_y_cantidad(id_componente)
            else:
                st.error("No se encontró ese ID en el inventario.")

# ==============================
# REGISTRAR DEVOLUCIÓN
# ==============================
st.subheader("Registrar devolución")

with st.form("devolucion_form"):
    id_devolucion = st.text_input("ID del componente a devolver")
    persona_dev = st.text_input("Persona que devuelve el componente")
    cantidad_dev = st.number_input("Cantidad a devolver", min_value=1, step=1)
    fecha_devolucion = st.date_input("Fecha de devolución")
    observaciones_dev = st.text_area("Observaciones (opcional)")
    submit_devolucion = st.form_submit_button("Registrar devolución")

    if submit_devolucion:
        if not id_devolucion or not persona_dev:
            st.error("Debes ingresar el ID y el nombre de quien devuelve.")
        else:
            historial = sheet_historial.get_all_records()
            prestamos_activos = [
                h for h in historial
                if str(h["ID"]).strip().lower() == str(id_devolucion).strip().lower()
                and h["Acción"] == "Préstamo"
                and h["Persona"].strip().lower() == persona_dev.strip().lower()
                and not any(
                    d["Acción"] == "Devolución"
                    and d["Persona"] == h["Persona"]
                    and d["ID"] == h["ID"]
                    for d in historial
                )
            ]

            if not prestamos_activos:
                st.error("No se encontró un préstamo activo para esa persona e ID.")
            else:
                componente = prestamos_activos[0]["Componente"]
                # Registrar devolución
                sheet_historial.append_row([
                    id_devolucion, componente, persona_dev,
                    "Devolución", str(fecha_devolucion), cantidad_dev, observaciones_dev
                ])
                st.success(f"Devolución registrada para {componente} ({cantidad_dev} unidad/es)")
                actualizar_estado_y_cantidad(id_devolucion)

# ==============================
# MOSTRAR HISTORIAL
# ==============================
st.subheader("Historial de préstamos y devoluciones")
historial = pd.DataFrame(sheet_historial.get_all_records())
st.dataframe(historial)








