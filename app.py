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
import re


# -------- COOKIES CONFIG --------
cookies = EncryptedCookieManager(
    prefix="inventario_login",
    password=st.secrets["cookies"]["password"]
)

if not cookies.ready():
    st.stop()

# -------- LOGIN SCREEN --------
def login_screen():
    st.title("Inicio de Sesión")
    st.write("Acceso restringido al sistema de inventario.")

    user = st.text_input("Usuario")
    pwd = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        if user == st.secrets["auth"]["username"] and pwd == st.secrets["auth"]["password"]:
            # Guardar cookie
            cookies["logged"] = "yes"
            cookies.save()

            # Actualizar session_state
            st.session_state["logged_in"] = True
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")


# -------- LEER COOKIE --------
if cookies.get("logged") == "yes":
    st.session_state["logged_in"] = True

# Inicializar estado
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# Mostrar login si no ha iniciado sesión
if not st.session_state["logged_in"]:
    login_screen()
    st.stop()
# ==============================
# COFIGUARACIÓN ESTILO KITS
st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Montserrat', sans-serif;
}

h1, h2, h3 {
    color: #1a3c6e;
    font-weight: 600;
}

.sidebar .css-1d391kg {
    background-color: #dce8ff !important;
}

.stButton>button {
    background-color: #1a3c6e;
    color: white;
    border-radius: 8px;
}

.stCheckbox {
    accent-color: #e0b100 !important;
}

</style>
""", unsafe_allow_html=True)


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
#_______________________________________________
# Utilidades para cargar tabla desde el link QR
#_______________________________________________
def extraer_id_y_gid(url):
    doc_id = re.search(r"/d/([a-zA-Z0-9-_]+)", url).group(1)
    gid = re.search(r"gid=([0-9]+)", url).group(1)
    return doc_id, gid

def cargar_tabla_kit(url, creds):
    try:
        doc_id, gid = extraer_id_y_gid(url)
        gc = gspread.authorize(creds)
        doc = gc.open_by_key(doc_id)

        hoja = None
        for ws in doc.worksheets():
            if str(ws.id) == gid:
                hoja = ws
                break

        if hoja is None:
            return None

        return hoja.get_all_records()

    except Exception as e:
        print("ERROR leyendo QR:", e)
        return None


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
# Pantalla para marcar contenido del kit
# ==============================

def mostrar_verificacion_kit(nombre_kit, url_qr, creds):
    st.subheader(f"Verificación de contenido – {nombre_kit}")

    tabla = cargar_tabla_kit(url_qr, creds)

    if tabla is None:
        st.error("No se pudo cargar la lista del kit desde el QR.")
        return None

    st.write("### Contenido del kit")

    estados = []
    for item in tabla:
        elemento = item.get("Elemento", "Elemento sin nombre")

        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"📦 {elemento}")
        with col2:
            ok = st.checkbox("OK", key=f"kit_{nombre_kit}_{elemento}")
        
        estados.append({
            "Elemento": elemento,
            "OK": ok
        })

    return estados


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

    # Cargar datos en variables consistentes y actualizadas
    inventario_df = pd.DataFrame(sheet_inventario.get_all_records())
    kits_df = pd.DataFrame(sheet_kits.get_all_records())

    busqueda = st.text_input("Buscar componente por nombre o ID:")
    if busqueda:
        coincidencias = inventario_df[
            inventario_df["ID"].astype(str).str.contains(busqueda, case=False, na=False) |
            inventario_df["Componente"].astype(str).str.contains(busqueda, case=False, na=False)
        ]
    else:
        coincidencias = pd.DataFrame()

    if not coincidencias.empty:
        seleccionado = st.selectbox(
            "Seleccione un componente:",
            coincidencias["Componente"] + " (ID: " + coincidencias["ID"].astype(str) + ")"
        )

        id_real = seleccionado.split("ID: ")[1].replace(")", "")
        # Verificar si es un kit
        kits_relacionados = kits_df[kits_df["ID Inventario"].astype(str) == str(id_real)]
        es_kit = len(kits_relacionados) > 0

        if es_kit:
            st.subheader("Este componente es un KIT")
            kits_disponibles = kits_relacionados[kits_relacionados["Estado"].astype(str).str.lower() == "disponible"]
            if kits_disponibles.empty:
                st.error("No hay kits disponibles.")
            else:
                numero_kit = st.selectbox(
                    "Seleccione el número de kit disponible:",
                    kits_disponibles["Número Kit"].astype(str)
                )
                info_kit = kits_disponibles[kits_disponibles["Número Kit"].astype(str) == numero_kit].iloc[0]
                st.write("Observación:", info_kit.get("Observación", ""))
                st.write("QR:", info_kit.get("QR", ""))

        else:
            st.info("Este componente NO es un Kit.")

        nombre = st.text_input("Nombre de quien realiza el préstamo")
        cantidad = st.number_input("Cantidad", min_value=1, step=1)

        if st.button("Registrar Préstamo"):
            # Prepara registro (consistente con HISTORIAL)
            registro_row = [
                id_real,
                coincidencias[coincidencias["ID"].astype(str) == id_real].iloc[0]["Componente"],
                nombre,
                "Préstamo",
                str(datetime.now().date()),
                cantidad,
                ""
            ]

            # Si es kit, registramos el número de kit y cambiamos estado en KITS
            if es_kit:
                registro_row[6] = f"Kit #{numero_kit}"
                fila_kit = kits_relacionados[
                    kits_relacionados["Número Kit"].astype(str) == numero_kit
                ].index[0] + 2  # +2 por encabezado
                sheet_kits.update_cell(fila_kit, kits_df.columns.get_loc("Estado") + 1, "Prestado")

            sheet_historial.append_row(registro_row)
            actualizar_estado_y_cantidad(id_real)
            st.success("Préstamo registrado correctamente.")

# ==============================
# REGISTRO DEVOLUCIÓN     

elif menu == "Registrar Devolución":
    st.title("Registrar Devolución")

    # Cargar datos actualizados
    inventario_df = pd.DataFrame(sheet_inventario.get_all_records())
    kits_df = pd.DataFrame(sheet_kits.get_all_records())

    busqueda = st.text_input("Buscar componente (por nombre o ID):")
    if busqueda:
        coincidencias = inventario_df[
            inventario_df["Componente"].str.contains(busqueda, case=False, na=False) |
            inventario_df["ID"].astype(str).str.contains(busqueda, case=False, na=False)
        ]
        if coincidencias.empty:
            st.warning("No se encontraron componentes para esa búsqueda.")
        else:
            st.dataframe(coincidencias, use_container_width=True)

    id_dev = st.text_input("ID del componente (para devolución)")
    persona = st.text_input("Persona que devuelve")
    fecha_dev = st.date_input("Fecha de devolución")
    observaciones_dev = st.text_area("Observaciones (opcional)")

    es_kit = False
    kits_relacionados = pd.DataFrame()
    kits_prestados = pd.DataFrame()
    seleccion_kit = None

    if id_dev:
        kits_relacionados = kits_df[kits_df["ID Inventario"].astype(str) == str(id_dev)]
        es_kit = not kits_relacionados.empty

        if es_kit:
            kits_prestados = kits_relacionados[
                kits_relacionados["Estado"].astype(str).str.lower() == "prestado"
            ]
            if kits_prestados.empty:
                st.info("No hay kits prestados actualmente para este ID.")
            else:
                opciones = (kits_prestados["Kit ID"].astype(str) + " - Kit #" +
                            kits_prestados["Número Kit"].astype(str))
                seleccion_kit = st.selectbox("Selecciona el kit a devolver:", opciones)

    if st.button("Registrar devolución"):
        if not id_dev:
            st.error("Ingresa el ID del componente.")
        elif not persona:
            st.error("Ingresa la persona que devuelve.")
        else:
            if es_kit:
                if kits_prestados.empty:
                    st.error("No hay kits prestados para devolver.")
                else:
                    if not seleccion_kit:
                        st.error("Selecciona primero el kit a devolver.")
                    else:
                        kit_id = seleccion_kit.split(" - ")[0].strip()
                        try:
                            fila_rel = kits_df[kits_df["Kit ID"].astype(str) == kit_id].index[0]
                        except IndexError:
                            st.error("No pude encontrar la fila del kit en la hoja KITS.")
                            fila_rel = None

                        if fila_rel is not None:
                            row_number = fila_rel + 2
                            col_estado = kits_df.columns.get_loc("Estado") + 1
                            col_obs = kits_df.columns.get_loc("Observación") + 1

                            sheet_kits.update_cell(row_number, col_estado, "Disponible")
                            sheet_kits.update_cell(row_number, col_obs, observaciones_dev if observaciones_dev else "")

                            inv_match = inventario_df[inventario_df["ID"].astype(str) == str(id_dev)]
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

                            actualizar_estado_y_cantidad(id_dev)
                            st.success(f"Kit {kit_id} devuelto y marcado como Disponible.")
            else:
                historial = sheet_historial.get_all_records()
                total_prestado = sum(
                    int(h["Cantidad"]) for h in historial
                    if str(h["ID"]).strip().lower() == str(id_dev).strip().lower()
                    and str(h["Acción"]).strip().lower() == "préstamo"
                    and h["Persona"].strip().lower() == persona.strip().lower()
                )
                total_devuelto = sum(
                    int(h["Cantidad"]) for h in historial
                    if str(h["ID"]).strip().lower() == str(id_dev).strip().lower()
                    and str(h["Acción"]).strip().lower() == "devolución"
                    and h["Persona"].strip().lower() == persona.strip().lower()
                )
                pendiente = total_prestado - total_devuelto

                if pendiente <= 0:
                    st.error("No hay préstamos pendientes para esta persona y componente.")
                else:
                    # pedir cantidad y confirmar
                    cantidad_dev = st.number_input("Cantidad a devolver ahora:", min_value=1, max_value=pendiente, value=1)
                    if st.button("Confirmar devolución de componente"):
                        inv_match = inventario_df[inventario_df["ID"].astype(str) == str(id_dev)]
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


# ----------- APP PRINCIPAL ----------
st.sidebar.markdown("### Sesión")
if st.sidebar.button("Cerrar sesión"):
    cookies["logged"] = "no"
    cookies.save()
    st.session_state["logged_in"] = False
    st.rerun()















































