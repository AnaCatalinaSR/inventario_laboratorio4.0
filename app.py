import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
from PIL import Image
import os
import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager

# CONFIGURAR COOKIES
cookies = EncryptedCookieManager(prefix="inventario_login")
if not cookies.ready():
    st.stop()

def login_screen():
    st.title("Inicio de Sesión")
    st.write("Acceso restringido al sistema de inventario.")

    user = st.text_input("Usuario")
    pwd = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        if user == st.secrets["auth"]["username"] and pwd == st.secrets["auth"]["password"]:
            # Guardar login en cookie
            cookies["logged"] = "yes"
            cookies.save()

            st.session_state["logged_in"] = True
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")

# Leer cookie al iniciar
if cookies.get("logged") == "yes":
    st.session_state["logged_in"] = True

# Inicializar variable
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# Si no ha iniciado sesión → mostrar login
if not st.session_state["logged_in"]:
    login_screen()
    st.stop()


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
sheet_kits = spreadsheet.worksheet("KITS")

# ==============================
# FUNCIÓN AUXILIAR
# ==============================
def actualizar_estado_y_cantidad(id_componente):
    inventario = sheet_inventario.get_all_records()
    historial = sheet_historial.get_all_records()

    for i, item in enumerate(inventario):
        if str(item["ID"]).lower() == str(id_componente).lower():

            total = int(item["Cantidad"])

            total_prestamos = sum(
                int(h["Cantidad"]) for h in historial
                if h["ID"] == id_componente and h["Acción"] == "Préstamo"
            )

            total_devoluciones = sum(
                int(h["Cantidad"]) for h in historial
                if h["ID"] == id_componente and h["Acción"] == "Devolución"
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
    "Kits"
])

inventario_df = pd.DataFrame(sheet_inventario.get_all_records())
kits_df = pd.DataFrame(sheet_kits.get_all_records())

# ==============================
# 1. INVENTARIO
# ==============================
if menu == "Inventario":
    st.title("Inventario Actual")

    busqueda = st.text_input("Buscar componente por nombre o ID:")

    if busqueda:
        filtro = inventario_df[
            inventario_df["Componente"].str.contains(busqueda, case=False, na=False) |
            inventario_df["ID"].astype(str).str.contains(busqueda, case=False, na=False)
        ]
    else:
        filtro = inventario_df

    st.dataframe(filtro, use_container_width=True)

# ==============================
# 2. REGISTRAR PRÉSTAMO
# ==============================
elif menu == "Registrar Préstamo":

    st.title("Registrar Préstamo")

    inventario = pd.DataFrame(sheet_inventario.get_all_records())
    kits = pd.DataFrame(sheet_kits.get_all_records())

    busqueda = st.text_input("Buscar componente por nombre o ID:")

    if busqueda:
        coincidencias = inventario[
            inventario["ID"].astype(str).str.contains(busqueda, case=False) |
            inventario["Componente"].astype(str).str.contains(busqueda, case=False)
        ]
    else:
        coincidencias = pd.DataFrame()

    if len(coincidencias) > 0:

        seleccionado = st.selectbox(
            "Seleccione un componente:",
            coincidencias["Componente"] + " (ID: " + coincidencias["ID"].astype(str) + ")"
        )

        id_real = seleccionado.split("ID: ")[1].replace(")", "")

        # Verificar si es un kit
        kits_relacionados = kits[kits["ID Inventario"].astype(str) == str(id_real)]
        es_kit = len(kits_relacionados) > 0

        if es_kit:
            st.subheader("Este componente es un KIT")

            kits_disponibles = kits_relacionados[kits_relacionados["Estado"] == "Disponible"]

            if len(kits_disponibles) == 0:
                st.error("No hay kits disponibles.")
            else:
                numero_kit = st.selectbox(
                    "Seleccione el número de kit disponible:",
                    kits_disponibles["Número Kit"].astype(str)
                )

                info_kit = kits_disponibles[kits_disponibles["Número Kit"].astype(str) == numero_kit].iloc[0]
                st.write("Observación:", info_kit["Observación"])
                st.write("QR:", info_kit["QR"])

        else:
            st.info("Este componente NO es un Kit.")

        nombre = st.text_input("Nombre de quien realiza el préstamo")
        cantidad = st.number_input("Cantidad", min_value=1, step=1)

        if st.button("Registrar Préstamo"):

            registro = {
                "ID": id_real,
                "Componente": seleccionado,
                "Persona": nombre,
                "Acción": "Préstamo",
                "Fecha": str(datetime.now().date()),
                "Cantidad": cantidad,
                "Obs": "",
            }

            if es_kit:
                registro["Número Kit"] = numero_kit
                fila_kit = kits_relacionados[
                    kits_relacionados["Número Kit"].astype(str) == numero_kit
                ].index[0] + 2
                sheet_kits.update_cell(fila_kit, kits.columns.get_loc("Estado") + 1, "Prestado")

            sheet_historial.append_row(list(registro.values()))
            actualizar_estado_y_cantidad(id_real)
            st.success("Préstamo registrado correctamente.")

# ==============================
# 3. REGISTRAR DEVOLUCIÓN
# ==============================

# ==============================
# 3. REGISTRAR DEVOLUCIÓN (CORREGIDO, con soporte para KITS)
# ==============================
elif menu == "Registrar Devolución":
    st.title("Registrar Devolución")

    # Cargar datos frescos
    inventario = pd.DataFrame(sheet_inventario.get_all_records())
    kits = pd.DataFrame(sheet_kits.get_all_records())

    # Búsqueda / vista previa
    busqueda = st.text_input("Buscar componente (por nombre o ID):")
    if busqueda:
        coincidencias = inventario[
            inventario["Componente"].str.contains(busqueda, case=False, na=False) |
            inventario["ID"].astype(str).str.contains(busqueda, case=False, na=False)
        ]
        if coincidencias.empty:
            st.warning("No se encontraron componentes para esa búsqueda.")
        else:
            st.dataframe(coincidencias, use_container_width=True)

    # Datos para devolución
    id_dev = st.text_input("ID del componente (para devolución)")
    persona = st.text_input("Persona que devuelve")
    fecha_dev = st.date_input("Fecha de devolución")
    observaciones_dev = st.text_area("Observaciones (opcional)")

    # Si se ingresó ID, detectamos si es kit y listamos kits prestados
    es_kit = False
    kits_relacionados = pd.DataFrame()
    kits_prestados = pd.DataFrame()
    seleccion_kit = None

    if id_dev:
        kits_relacionados = kits[kits["ID Inventario"].astype(str) == str(id_dev)]
        es_kit = not kits_relacionados.empty

        if es_kit:
            # Filtrar kits actualmente prestados
            kits_prestados = kits_relacionados[
                kits_relacionados["Estado"].astype(str).str.lower() == "prestado"
            ]

            if kits_prestados.empty:
                st.info("No hay kits prestados actualmente para este ID.")
            else:
                # Mostrar selectbox con 'Kit ID - #Número'
                opciones = (kits_prestados["Kit ID"].astype(str) + " - Kit #" +
                            kits_prestados["Número Kit"].astype(str))
                seleccion_kit = st.selectbox("Selecciona el kit a devolver:", opciones)

    # Botón para confirmar devolución
    if st.button("Registrar devolución"):
        # Validaciones básicas
        if not id_dev:
            st.error("Ingresa el ID del componente.")
        elif not persona:
            st.error("Ingresa la persona que devuelve.")
        else:
            # --- Devolución de KIT ---
            if es_kit:
                if kits_prestados.empty:
                    st.error("No hay kits prestados para devolver (o el kit ya está disponible).")
                else:
                    # Extraer Kit ID desde la opción seleccionada
                    if not seleccion_kit:
                        st.error("Selecciona primero el kit a devolver.")
                    else:
                        kit_id = seleccion_kit.split(" - ")[0].strip()

                        # Buscar fila del kit en kits dataframe para actualizar hoja
                        try:
                            fila_rel = kits[kits["Kit ID"].astype(str) == kit_id].index[0]  # 0-based
                        except IndexError:
                            st.error("No pude encontrar la fila del kit en la hoja KITS.")
                            fila_rel = None

                        if fila_rel is not None:
                            row_number = fila_rel + 2  # +2 por encabezado en Sheets

                            # Actualizar Estado y Observación en la hoja KITS
                            # Obtener índices de columna (1-based) usando el df 'kits' (asegúrate que columnas coinciden)
                            col_estado = kits.columns.get_loc("Estado") + 1
                            col_obs = kits.columns.get_loc("Observación") + 1

                            sheet_kits.update_cell(row_number, col_estado, "Disponible")
                            sheet_kits.update_cell(row_number, col_obs, observaciones_dev if observaciones_dev else "")

                            # Registrar en HISTORIAL: [ID, Componente, Persona, Acción, Fecha, Cantidad, Observaciones]
                            # Obtener nombre del componente desde inventario (si existe)
                            inv_match = inventario[inventario["ID"].astype(str) == str(id_dev)]
                            nombre_comp = inv_match.iloc[0]["Componente"] if not inv_match.empty else id_dev

                            sheet_historial.append_row([
                                id_dev,
                                f"{nombre_comp} (Kit {kit_id})",
                                persona,
                                "Devolución",
                                str(fecha_dev),
                                1,
                                observaciones_dev if observaciones_dev else ""
                            ])

                            # Actualizar contadores en INVENTARIO
                            actualizar_estado_y_cantidad(id_dev)

                            st.success(f"Kit {kit_id} devuelto y marcado como Disponible.")

            # --- Devolución normal (no es kit) ---
            else:
                # Validar que existan préstamos pendientes
                historial = sheet_historial.get_all_records()

                total_prestado = sum(
                    int(h["Cantidad"])
                    for h in historial
                    if str(h["ID"]).strip().lower() == str(id_dev).strip().lower()
                    and str(h["Acción"]).strip().lower() == "préstamo"
                    and h["Persona"].strip().lower() == persona.strip().lower()
                )

                total_devuelto = sum(
                    int(h["Cantidad"])
                    for h in historial
                    if str(h["ID"]).strip().lower() == str(id_dev).strip().lower()
                    and str(h["Acción"]).strip().lower() == "devolución"
                    and h["Persona"].strip().lower() == persona.strip().lower()
                )

                pendiente = total_prestado - total_devuelto

                if pendiente <= 0:
                    st.error("No hay préstamos pendientes para esta persona y componente.")
                else:
                    cantidad_dev = st.number_input("Cantidad a devolver ahora:", min_value=1, max_value=pendiente, value=1)
                    # Confirmación adicional (evita duplicar al usar botón)
                    if st.button("Confirmar devolución de componente"):
                        # Obtener nombre del componente para historial
                        inv_match = inventario[inventario["ID"].astype(str) == str(id_dev)]
                        nombre_comp = inv_match.iloc[0]["Componente"] if not inv_match.empty else id_dev

                        sheet_historial.append_row([
                            id_dev,
                            nombre_comp,
                            persona,
                            "Devolución",
                            str(fecha_dev),
                            int(cantidad_dev),
                            observaciones_dev if observaciones_dev else ""
                        ])

                        actualizar_estado_y_cantidad(id_dev)
                        st.success("Devolución registrada correctamente.")


# ==============================
# 4. HISTORIAL
# ==============================
elif menu == "Historial":
    st.title("Historial Completo")
    st.dataframe(pd.DataFrame(sheet_historial.get_all_records()), use_container_width=True)

# ==============================
# 5. KITS
# ==============================
elif menu == "Kits":
    st.title("Listado de KITS")
    st.dataframe(kits_df, use_container_width=True)

# BOTÓN DE CIERRE DE SESIÓN
with st.sidebar:
    st.markdown("### Sesión")
    if st.button("Cerrar sesión"):
        st.session_state["logged_in"] = False
        st.success("Sesión cerrada correctamente.")
        st.rerun()


# ------------- APP PRINCIPAL ------------------

with st.sidebar:
    st.markdown("### Sesión")
    if st.button("Cerrar sesión"):
        cookies["logged"] = "no"
        cookies.save()
        st.session_state["logged_in"] = False
        st.rerun()








































