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
st.markdown("""
<style>

/* Contenedor principal */
.main-container {
    max-width: 1000px;
    margin: 0 auto;
    padding: 20px;
    background-color: #f5faff; /* Azul muy claro */
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.08);
    color: #000; /* Texto negro */
}

/* Encabezado */
.header {
    text-align: center;
    margin-bottom: 30px;
}

.header h2 {
    font-size: 2.3rem;
    font-weight: bold;
    color: #000; /* Negro */
    text-shadow: 1px 1px #e6e6e6;
    border-bottom: 3px solid #ffd84d; /* Línea amarilla */
    display: inline-block;
    padding-bottom: 5px;
}

/* Barra de búsqueda */
.search-bar input {
    width: 100%;
    padding: 10px;
    margin-bottom: 20px;
    border: 2px solid #8ecaff;
    border-radius: 8px;
    font-size: 1.1rem;
    color: #000;
    background-color: #ffffff;
}

.search-bar input:focus {
    border-color: #ffd84d;
    outline: none;
}

/* Items del inventario */
.inventory-item {
    display: flex;
    justify-content: space-between;
    padding: 15px;
    margin-bottom: 15px;
    background-color: #e9f4ff;
    border-left: 6px solid #ffd84d;
    border-radius: 8px;
    color: #000;
}

/* Botón principal */
.btn-primary {
    background-color: #8ecaff;
    color: #000;
    padding: 10px 20px;
    border: 2px solid #ffd84d;
    border-radius: 8px;
    font-size: 1rem;
    cursor: pointer;
    font-weight: 600;
}

.btn-primary:hover {
    background-color: #d5ecff;
    border-color: #ffcc24;
}

</style>
""",
unsafe_allow_html=True
)

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




































