import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
from PIL import Image
import streamlit as st
import os
#color pagina

# === ESTILO INSTITUCIONAL CLARO (texto visible) ===
st.markdown("""
<style>

:root {
    --azul-principal: #004080;
    --azul-secundario: #0066cc;
    --azul-claro: #e9f1fb;
    --blanco: #ffffff;
    --gris-suave: #f7f9fc;
    --texto-oscuro: #1a1a1a;
}

/* ===== FONDO GENERAL ===== */
[data-testid="stAppViewContainer"] {
    background-color: var(--gris-suave);
    color: var(--texto-oscuro);
}

/* ======= BARRA SUPERIOR (header) ======= */
header[data-testid="stHeader"] {
    background-color: var(--azul-claro) !important;
    color: var(--azul-principal) !important;
    border-bottom: 2px solid #d0e2ff;
}

/* Iconos del header */
header[data-testid="stHeader"] svg {
    fill: var(--azul-principal) !important;
}

/* Texto del header */
header[data-testid="stHeader"] * {
    color: var(--azul-principal) !important;
}

/* ===== SIDEBAR ===== */
[data-testid="stSidebar"] {
    background-color: var(--blanco);
    border-right: 2px solid var(--azul-claro);
}
[data-testid="stSidebar"] * {
    color: var(--azul-principal) !important;
    font-weight: 500;
}
[data-testid="stSidebarNav"] a {
    color: var(--azul-principal) !important;
}
[data-testid="stSidebarNav"] a:hover {
    color: var(--azul-secundario) !important;
}

/* ===== TITULOS ===== */
h1, h2, h3, h4, h5 {
    color: var(--azul-principal) !important;
    font-family: "Segoe UI", Roboto, sans-serif;
}

/* ===== BOTONES ===== */
div.stButton > button {
    background-color: var(--azul-principal);
    color: var(--blanco);
    border: none;
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.2s ease;
}
div.stButton > button:hover {
    background-color: var(--azul-secundario);
    transform: translateY(-2px);
}

/* ===== TABLAS ===== */
.stDataFrame {
    background: var(--blanco);
    border-radius: 10px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    padding: 8px;
    color: var(--texto-oscuro);
}

/* ===== FORMULARIOS ===== */
.stForm {
    background: var(--blanco);
    border-radius: 10px;
    padding: 20px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    color: var(--texto-oscuro);
}

/* ===== INPUTS ===== */
.stTextInput > div > div > input,
.stNumberInput > div > input,
.stTextArea > div > textarea,
.stDateInput > div > input {
    border: 1px solid #d3e3f7;
    border-radius: 6px;
    background: var(--blanco);
    color: var(--texto-oscuro);
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > input:focus,
.stTextArea > div > textarea:focus,
.stDateInput > div > input:focus {
    outline: none;
    border: 1.5px solid var(--azul-secundario);
    box-shadow: 0 0 4px rgba(0,64,128,0.2);
}

/* ===== MENSAJES ===== */
.stAlert {
    border-radius: 8px;
}
[data-testid="stSuccess"] {
    background-color: #e6f4ea;
    color: #1a6333;
}
[data-testid="stError"] {
    background-color: #fdecea;
    color: #a30d0d;
}
[data-testid="stWarning"] {
    background-color: #fff4e5;
    color: #8a6d1d;
}

/* ===== ENLACES Y TEXTOS ===== */
a, p, label, span {
    color: var(--texto-oscuro) !important;
}

</style>
""", unsafe_allow_html=True)


#color tablas
st.markdown("""
<style>

/* === FORZAR MODO CLARO EN DATAFRAME === */
.ag-theme-streamlit-dark {
    --ag-background-color: #e9f1fb !important;
    --ag-odd-row-background-color: #f3f7ff !important;
    --ag-header-background-color: #004080 !important;
    --ag-header-foreground-color: #ffffff !important;
    --ag-foreground-color: #1a1a1a !important;
    --ag-border-color: #c5d9f2 !important;
    --ag-font-size: 14px;
}

/* Para la versión clara */
.ag-theme-streamlit-light {
    --ag-background-color: #e9f1fb !important;
    --ag-odd-row-background-color: #f3f7ff !important;
    --ag-header-background-color: #004080 !important;
    --ag-header-foreground-color: #ffffff !important;
    --ag-foreground-color: #1a1a1a !important;
    --ag-border-color: #c5d9f2 !important;
    --ag-font-size: 14px;
}

/* Forzar texto negro */
.ag-root-wrapper, .ag-cell, .ag-header-cell {
    color: #1a1a1a !important;
}

</style>
""", unsafe_allow_html=True)
# --- Configurar logo ---
logo_path = "logo-intep.png"

if os.path.exists(logo_path):
    logo = Image.open(logo_path)
    st.set_page_config(page_title="Gestión de Préstamos", layout="wide", page_icon=logo)
    with st.sidebar:
        st.image(logo, width=150)
        st.markdown("<h3 style='color:#004080;'>Laboratorio de Industria 4.0</h3>", unsafe_allow_html=True)
else:
    st.set_page_config(page_title="Gestión de Préstamos", layout="wide", page_icon="🏫")
    with st.sidebar:
        st.markdown("<h3 style='color:#004080;'>Laboratorio Industrial 4.0</h3>", unsafe_allow_html=True)
# ==============================
# CONFIGURACIÓN GOOGLE SHEETS
# ==============================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = json.loads(st.secrets["credentials"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)

# Abrir archivo principal
spreadsheet = client.open("INVENTARIO")
sheet_inventario = spreadsheet.worksheet("INVENTARIO")
sheet_historial = spreadsheet.worksheet("HISTORIAL")

# ==============================
# FUNCIONES AUXILIARES
# ==============================
def actualizar_estado_y_cantidad(id_componente):
    """Actualiza la columna 'Disponible' y 'Estado' sin tocar la cantidad total."""
    inventario = sheet_inventario.get_all_records()
    historial = sheet_historial.get_all_records()

    for i, item in enumerate(inventario):
        if str(item["ID"]).strip().lower() == str(id_componente).strip().lower():

            # CANTIDAD TOTAL (NO SE MODIFICA)
            total = int(item["Cantidad"])

            # SUMA PRESTAMOS
            total_prestamos = sum(
                int(h["Cantidad"])
                for h in historial
                if str(h["ID"]).lower() == str(id_componente).lower()
                and h["Acción"].lower() == "préstamo"
            )

            # SUMA DEVOLUCIONES
            total_devoluciones = sum(
                int(h["Cantidad"])
                for h in historial
                if str(h["ID"]).lower() == str(id_componente).lower()
                and h["Acción"].lower() == "devolución"
            )

            # PRESTADO ACTIVO
            prestado_activo = max(total_prestamos - total_devoluciones, 0)

            # DISPONIBLE
            disponible = total - prestado_activo

            # ESTADO
            if disponible == total:
                estado = "Disponible"
            elif disponible > 0:
                estado = "Parcialmente prestado"
            else:
                estado = "No disponible"

            # ACTUALIZAR HOJA
            # Col 4 = Disponible
            sheet_inventario.update_cell(i + 2, 4, disponible)

            # Col 5 = Estado
            sheet_inventario.update_cell(i + 2, 5, estado)

            break


# ==============================
# INTERFAZ PRINCIPAL
# ==============================
st.set_page_config(page_title="Gestión de Préstamos", layout="wide")

st.sidebar.title("Menú")
menu = st.sidebar.radio("Selecciona una opción:", [
    "Inventario",
    "Registrar Préstamo",
    "Registrar Devolución",
    "Historial"
])

inventario = pd.DataFrame(sheet_inventario.get_all_records())

# ==============================
# OPCIÓN 1: INVENTARIO
# ==============================
if menu == "Inventario":
    st.title("Inventario Actual")

    # Campo de búsqueda
    busqueda = st.text_input("Buscar componente por nombre o ID:")

    # Filtrar por nombre o ID si hay búsqueda
    if busqueda:
        filtro = inventario[
            inventario["Componente"].str.contains(busqueda, case=False, na=False) |
            inventario["ID"].astype(str).str.contains(busqueda, case=False, na=False)
        ]
    else:
        filtro = inventario

    # Función para aplicar colores según el estado
    def resaltar_estado(val):
        if val == "Disponible":
            color = "background-color: #d4edda; color: #155724;"   # Verde suave
        elif val == "Parcialmente prestado":
            color = "background-color: #fff3cd; color: #856404;"   # Amarillo suave
        elif val == "No disponible":
            color = "background-color: #f8d7da; color: #721c24;"   # Rojo suave
        else:
            color = ""
        return color

    # Aplicar estilo
    if "Estado" in filtro.columns:
        styled_df = filtro.style.applymap(resaltar_estado, subset=["Estado"])
        st.dataframe(styled_df, use_container_width=True)
    else:
        st.dataframe(filtro, use_container_width=True)


# ==============================
# OPCIÓN 2: REGISTRAR PRÉSTAMO
# ==============================
elif menu == "Registrar Préstamo":
    st.title("Registrar Préstamo")
    busqueda = st.text_input("Buscar componente (por nombre o ID):")
    if busqueda:
        coincidencias = inventario[inventario["Componente"].str.contains(busqueda, case=False, na=False) |
                                   inventario["ID"].astype(str).str.contains(busqueda, case=False, na=False)]
        st.dataframe(coincidencias)

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
                    componente = inventario[fila]["Componente"]

                    if disponible <= 0:
                        st.error("No hay unidades disponibles para préstamo.")
                    elif cantidad_prestamo > disponible:
                        st.error(f"Solo hay {disponible} unidades disponibles.")
                    else:
                        sheet_historial.append_row([
                            id_componente, componente, persona,
                            "Préstamo", str(fecha_prestamo), cantidad_prestamo, observaciones
                        ])
                        st.success(f"Préstamo registrado para {componente} ({cantidad_prestamo} unidad/es)")
                        actualizar_estado_y_cantidad(id_componente)
                else:
                    st.error("No se encontró ese ID en el inventario.")

# ==============================
# OPCIÓN 3: REGISTRAR DEVOLUCIÓN
# ==============================
elif menu == "Registrar Devolución":
    st.title("Registrar Devolución")
    busqueda = st.text_input("Buscar componente (por nombre o ID):")
    if busqueda:
        coincidencias = inventario[
            inventario["Componente"].str.contains(busqueda, case=False, na=False) |
            inventario["ID"].astype(str).str.contains(busqueda, case=False, na=False)
        ]
        st.dataframe(coincidencias)

    with st.form("devolucion_form"):
        id_devolucion = st.text_input("ID del componente a devolver")
        persona_dev = st.text_input("Persona que devuelve el componente")
        cantidad_dev = st.number_input("Cantidad a devolver", min_value=1, step=1)
        fecha_devolucion = st.date_input("Fecha de devolución")
        observaciones_dev = st.text_area("Observaciones (opcional)")
        submit_devolucion = st.form_submit_button("Registrar devolución")

        if submit_devolucion:
            if not id_devolucion or not persona_dev:
                st.error("Debes ingresar el ID y la persona.")
                st.stop()

            historial = sheet_historial.get_all_records()

            # Cantidad prestada por esa persona
            total_prestado = sum(
                int(h["Cantidad"])
                for h in historial
                if str(h["ID"]).lower() == str(id_devolucion).lower()
                and h["Acción"].lower() == "préstamo"
                and h["Persona"].strip().lower() == persona_dev.strip().lower()
            )

            # Cantidad devuelta por esa persona
            total_devuelto = sum(
                int(h["Cantidad"])
                for h in historial
                if str(h["ID"]).lower() == str(id_devolucion).lower()
                and h["Acción"].lower() == "devolución"
                and h["Persona"].strip().lower() == persona_dev.strip().lower()
            )

            pendiente = total_prestado - total_devuelto

            if pendiente <= 0:
                st.error("Esta persona no tiene préstamos pendientes para este ID.")
                st.stop()

            if cantidad_dev > pendiente:
                st.error(f"Solo puede devolver {pendiente} unidades.")
                st.stop()

            
           
            # Obtener nombre del componente desde el PRÉSTAMO original
            comp = next(
                (
                    h["Componente"]
                    for h in historial
                    if str(h["ID"]).strip().lower() == str(id_devolucion).strip().lower()
                    and h["Acción"].lower() == "préstamo"
                    and h.get("Componente")
                ),
                "Desconocido"
            )

            # Registrar devolución
            sheet_historial.append_row([
                id_devolucion, comp, persona_dev,
                "Devolución", str(fecha_devolucion), cantidad_dev, observaciones_dev
            ])

            st.success(f"Devolución registrada ({cantidad_dev} unidad/es).")
            actualizar_estado_y_cantidad(id_devolucion)


# ==============================
# OPCIÓN 4: HISTORIAL
# ==============================
elif menu == "Historial":
    st.title("Historial de préstamos y devoluciones")
    historial = pd.DataFrame(sheet_historial.get_all_records())
    st.dataframe(historial)






























