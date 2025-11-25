# app.py (reemplaza tu archivo con esto)
import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
from PIL import Image
import os
from streamlit_cookies_manager import EncryptedCookieManager
import re


# -----------------------------------------------
# CARGA DE GOOGLE SHEETS CON CACHE EXTENDIDO
# -----------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def cargar_inventario():
    try:
        datos = sheet_inventario.get_all_records()
        return pd.DataFrame(datos)
    except Exception as e:
        st.error("⚠ No se pudo cargar el inventario desde Google Sheets.")
        st.stop()

@st.cache_data(ttl=300, show_spinner=False)
def cargar_kits():
    try:
        datos = sheet_kits.get_all_records()
        return pd.DataFrame(datos)
    except Exception as e:
        st.error("⚠ No se pudo cargar la tabla de kits desde Google Sheets.")
        st.stop()

@st.cache_data(ttl=300, show_spinner=False)
def cargar_historial():
    try:
        datos = sheet_historial.get_all_records()
        return pd.DataFrame(datos)
    except Exception as e:
        st.error("⚠ No se pudo cargar el historial desde Google Sheets.")
        st.stop()


# ================================
#   BOTÓN PARA FORZAR REFRESCO
# ================================
st.sidebar.subheader("Recargar datos")
if st.sidebar.button("🔄 Actualizar datos ahora"):
    cargar_inventario.clear()
    cargar_kits.clear()
    cargar_historial.clear()
    st.sidebar.success("Datos actualizados correctamente.")

# --------------------------
# COOKIES CONFIG
# --------------------------
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
            cookies["logged"] = "yes"
            cookies.save()
            st.session_state["logged_in"] = True
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")

# LEER COOKIE
if cookies.get("logged") == "yes":
    st.session_state["logged_in"] = True

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login_screen()
    st.stop()

# --------------------------
# ESTILOS (Montserrat + colores)
# --------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family: 'Montserrat', sans-serif; color: #000; }
h1,h2,h3 { color:#1a3c6e; font-weight:600; }
.sidebar .css-1d391kg { background-color: #dce8ff !important; }
.stButton>button { background-color: #1a3c6e !important; color: white !important; border-radius:8px !important; }
.stCheckbox input { accent-color: #e0b100 !important; }
.main-container { max-width:1000px; margin:0 auto; padding:20px; background-color:#f5faff; border-radius:10px; }
.header h2 { font-size:2.3rem; color:#000; border-bottom:3px solid #ffd84d; display:inline-block; }
</style>
""", unsafe_allow_html=True)

# --- LOGO / PAGE CONFIG ---
logo_path = "logo-intep.png"
if os.path.exists(logo_path):
    logo = Image.open(logo_path)
    st.set_page_config(page_title="Gestión de Préstamos", layout="wide", page_icon=logo)
    with st.sidebar:
        st.image(logo, width=150)
else:
    st.set_page_config(page_title="Gestión de Préstamos", layout="wide", page_icon="🏫")

# ==============================
# GOOGLE SHEETS (inicialización robusta)
# ==============================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

try:
    creds_secret = st.secrets.get("credentials")
    if creds_secret is None:
        raise ValueError("No se encontró 'credentials' en st.secrets.")
    # creds_secret puede ser dict o string JSON
    if isinstance(creds_secret, str):
        creds_dict = json.loads(creds_secret)
    else:
        creds_dict = creds_secret

    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    spreadsheet = client.open("INVENTARIO")
    sheet_inventario = spreadsheet.worksheet("INVENTARIO")
    sheet_historial = spreadsheet.worksheet("HISTORIAL")
    sheet_kits = spreadsheet.worksheet("KITS")

except Exception as e:
    st.error("Error conectando a Google Sheets: " + str(e))
    st.stop()

# util: correo service account para instrucciones de compartir
service_account_email = None
try:
    if isinstance(creds_secret, str):
        parsed = json.loads(creds_secret)
    else:
        parsed = creds_secret
    service_account_email = parsed.get("client_email")
except:
    service_account_email = None

# ====================================
# Utilidades para cargar tabla desde el link QR (documento externo)
# ====================================
def extraer_id_y_gid(url):
    """Extrae doc_id y gid de un URL tipo Google Sheets."""
    if not url or not isinstance(url, str):
        return None, None
    m_id = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    m_gid = re.search(r"gid=([0-9]+)", url)
    doc_id = m_id.group(1) if m_id else None
    gid = m_gid.group(1) if m_gid else None
    return doc_id, gid

def intentar_cargar_tabla_desde_qr(url):
    """Intenta abrir el documento apuntado por url y devolver lista de dicts o None."""
    try:
        doc_id, gid = extraer_id_y_gid(url)
        if not doc_id:
            return None
        doc = client.open_by_key(doc_id)
        # si hay gid, buscar worksheet por id; sino usar primera
        if gid:
            hoja = None
            for ws in doc.worksheets():
                if str(ws.id) == str(gid):
                    hoja = ws
                    break
            if hoja is None:
                return None
        else:
            hoja = doc.get_worksheet(0)
        return hoja.get_all_records()
    except Exception as e:
        # no romper; devolver None para fallback manual
        # opcional: mostrar debug en la app (comente en producción)
        st.info(f"(No pude leer el documento del QR: {e})")
        return None

# ====================================
# FUNCIONES AUXILIARES EXISTENTES
# ====================================
def actualizar_estado_y_cantidad(id_componente):
    inventario = sheet_inventario.get_all_records()
    historial = sheet_historial.get_all_records()
    for i, item in enumerate(inventario):
        if str(item["ID"]).strip().lower() == str(id_componente).strip().lower():
            total = int(item["Cantidad"])
            total_prestamos = sum(
                int(h["Cantidad"]) for h in historial
                if str(h["ID"]).strip().lower() == str(id_componente).strip().lower() and str(h["Acción"]).strip().lower() == "préstamo"
            )
            total_devoluciones = sum(
                int(h["Cantidad"]) for h in historial
                if str(h["ID"]).strip().lower() == str(id_componente).strip().lower() and str(h["Acción"]).strip().lower() == "devolución"
            )
            prestado_activo = max(total_prestamos - total_devoluciones, 0)
            disponible = total - prestado_activo
            if disponible == total:
                estado = "Disponible"
            elif disponible > 0:
                estado = "Parcialmente prestado"
            else:
                estado = "No disponible"
            # actualizar (col 4 = Disponible, col 5 = Estado)
            sheet_inventario.update_cell(i + 2, 4, disponible)
            sheet_inventario.update_cell(i + 2, 5, estado)
            break
#-----------------------------------------------
#VER LA TABLA CON CHECKBOXES
#-----------------------------------------------

def mostrar_tabla_verificacion(df_componentes, key_prefix="verif"):
    df = df_componentes.copy()

    # Detectar el nombre correcto de la columna
    col_nombre = None
    for posible in ["INVENTARIO", "Elemento", "Nombre", "Item"]:
        if posible in df.columns:
            col_nombre = posible
            break

    if col_nombre is None:
        st.error("❌ No se encontró una columna válida ('INVENTARIO' o 'Elemento') en el kit.")
        return df_componentes

    checks = []
    for i, row in df.iterrows():
        check_val = st.checkbox(
            f"✔ {row[col_nombre]}",
            key=f"{key_prefix}_{i}"
        )
        checks.append(check_val)

    df["Presente"] = checks
    return df


# ====================================
# MENÚ PRINCIPAL
# ====================================
st.sidebar.title("Menú")
menu = st.sidebar.radio("Selecciona una opción:", [
    "Inventario",
    "Registrar Préstamo",
    "Registrar Devolución",
    "Historial",
    "Kits"
])

# Cargar DF actuales para mostrar
inventario_df = pd.DataFrame(sheet_inventario.get_all_records())
kits_df = pd.DataFrame(sheet_kits.get_all_records())

# ------------------------------
# 1) INVENTARIO
# ------------------------------
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


# ------------------------------
# 2) REGISTRAR PRÉSTAMO  (con verificación de kit)
# ------------------------------

elif menu == "Registrar Préstamo":
    st.title("Registrar Préstamo")
    
    inventario_df = pd.DataFrame(sheet_inventario.get_all_records())
    kits_df = pd.DataFrame(sheet_kits.get_all_records())

    busqueda = st.text_input("Buscar componente por nombre o ID:")
    coincidencias = pd.DataFrame()
    
    if busqueda:
        coincidencias = inventario_df[
            inventario_df["ID"].astype(str).str.contains(busqueda, case=False, na=False) |
            inventario_df["Componente"].astype(str).str.contains(busqueda, case=False, na=False)
        ]

    if coincidencias.empty:
        st.info("Busca un componente para comenzar.")
        st.stop()

    # Selección de componente
    seleccionado = st.selectbox(
        "Seleccione un componente:",
        coincidencias["Componente"] + " (ID: " + coincidencias["ID"].astype(str) + ")"
    )

    id_real = seleccionado.split("ID: ")[1].replace(")", "")
    comp_row = coincidencias[coincidencias["ID"].astype(str) == id_real].iloc[0]

    st.write(f"**Componente:** {comp_row['Componente']}  —  **ID:** {id_real}")

    # verificar kits relacionados
    kits_relacionados = kits_df[kits_df["ID Inventario"].astype(str) == str(id_real)]
    es_kit = not kits_relacionados.empty

    numero_kit = None
    url_qr = None
    verificacion = []

    # ──────────────────────────────────────────────
    # SI ES KIT → SOLO PRESTAR EL KIT SELECCIONADO
    # ──────────────────────────────────────────────
    if es_kit:
        st.subheader("Este componente tiene KITS disponibles")

        kits_disponibles = kits_relacionados[
            kits_relacionados["Estado"].astype(str).str.lower() == "disponible"
        ]

        if kits_disponibles.empty:
            st.warning("No hay kits disponibles para préstamo.")
            st.stop()

        numero_kit = st.selectbox(
            "Seleccione el número de kit disponible:",
            kits_disponibles["Número Kit"].astype(str)
        )

        kit_row = kits_disponibles[
            kits_disponibles["Número Kit"].astype(str) == numero_kit
        ].iloc[0]

        st.write("Observación:", kit_row.get("Observación", ""))

        url_qr = kit_row.get("QR", "")

        # Cargar y mostrar verificación
        data_kit = intentar_cargar_tabla_desde_qr(url_qr)

        st.subheader("Verificación del kit")
        verificacion = mostrar_tabla_verificacion(
            pd.DataFrame(data_kit),
            key_prefix=f"pre_{id_real}_{numero_kit}"
        )

    # ----------------------------------------------
    # DATOS DEL PRÉSTAMO
    # ----------------------------------------------
    nombre = st.text_input("Nombre de quien realiza el préstamo")
    fecha_prestamo = st.date_input("Fecha del préstamo", value=datetime.now().date())
    cantidad = st.number_input("Cantidad (solo si NO es kit)", min_value=1, step=1, value=1)

    # ----------------------------------------------
    # BOTÓN: REGISTRAR PRÉSTAMO
    # ----------------------------------------------
    if st.button("Registrar Préstamo"):

        if not nombre:
            st.error("Ingresa el nombre de quien realiza el préstamo.")
            st.stop()

        accion = "Préstamo"
        cantidad_grabar = 1 if es_kit else int(cantidad)
        obs_col = ""

        # ----------------------------------------------
        # ACTUALIZAR SOLO EL KIT SELECCIONADO
        # ----------------------------------------------
        if es_kit:
            obs_col = f"Kit #{numero_kit}"

            try:
                fila_rel = kits_df[
                    (kits_df["ID Inventario"].astype(str) == str(id_real)) &
                    (kits_df["Número Kit"].astype(str) == str(numero_kit))
                ].index[0]

                row_number = fila_rel + 2  # compensar encabezado
                col_estado = kits_df.columns.get_loc("Estado") + 1

                sheet_kits.update_cell(row_number, col_estado, "Prestado")

            except Exception as e:
                st.error(f"No pude actualizar el estado del kit: {e}")
                st.stop()

        # ----------------------------------------------
        # GUARDAR VERIFICACIÓN EN HISTORIAL
        # ----------------------------------------------
        try:
            ver_json = json.dumps(verificacion.to_dict(orient="records"), ensure_ascii=False)
        except:
            ver_json = "[]"

        fila_hist = [
            id_real,
            comp_row["Componente"],
            nombre,
            accion,
            str(fecha_prestamo),
            cantidad_grabar,
            obs_col,
            ver_json
        ]

        try:
            sheet_historial.append_row(fila_hist)
            actualizar_estado_y_cantidad(id_real)
            st.success("Préstamo registrado correctamente. Solo se prestó el kit seleccionado.")
        except Exception as e:
            st.error(f"No pude guardar en HISTORIAL: {e}")

# ------------------------------
# 3) REGISTRAR DEVOLUCIÓN (con verificación)
# ------------------------------
elif menu == "Registrar Devolución":
    st.title("Registrar Devolución")

    inventario_df = cargar_inventario()
    kits_df = cargar_kits()

    busqueda = st.text_input("Buscar componente (por nombre o ID):")
    coincidencias = pd.DataFrame()

    if busqueda:
        coincidencias = inventario_df[
            inventario_df["Componente"].str.contains(busqueda, case=False, na=False) |
            inventario_df["ID"].astype(str).str.contains(busqueda, case=False, na=False)
        ]

    if coincidencias.empty:
        st.info("Busca un componente para comenzar la devolución.")
        st.stop()

    # Selección del componente
    seleccionado = st.selectbox(
        "Seleccione un componente:",
        coincidencias["Componente"] + " (ID: " + coincidencias["ID"].astype(str) + ")"
    )

    id_real = seleccionado.split("ID: ")[1].replace(")", "").strip()
    comp_row = coincidencias[coincidencias["ID"].astype(str) == id_real].iloc[0]

    st.write(f"**Componente:** {comp_row['Componente']}  —  **ID:** {id_real}")

    # Comprobar si es kit
    kits_relacionados = kits_df[kits_df["ID Inventario"].astype(str) == id_real]
    es_kit = not kits_relacionados.empty

    numero_kit = None
    verificacion = []
    df_kit = pd.DataFrame()

    # =========================================================
    #      DEVOLUCIÓN DE KITS
    # =========================================================
    if es_kit:
        st.subheader("Este componente tiene KITS registrados")

        kits_prestados = kits_relacionados[
            kits_relacionados["Estado"].str.lower() == "prestado"
        ]

        if kits_prestados.empty:
            st.warning("No hay kits marcados como 'Prestado'.")
            st.stop()

        opciones = (
            kits_prestados["Kit ID"].astype(str) +
            " - Kit #" + kits_prestados["Número Kit"].astype(str)
        )

        seleccion_kit = st.selectbox("Selecciona el kit a devolver:", opciones)

        if seleccion_kit:
            kit_id = seleccion_kit.split(" - ")[0].strip()
            row_kit = kits_prestados[kits_prestados["Kit ID"].astype(str) == kit_id].iloc[0]

            numero_kit = str(row_kit["Número Kit"])
            url_qr = row_kit.get("QR", "")

            # Cargar tabla desde el QR (ya usa la función correcta)
            data_kit = intentar_cargar_tabla_desde_qr(url_qr)
            if not data_kit:
                df_kit = pd.DataFrame()
            else:
                df_kit = pd.DataFrame(data_kit)

            st.subheader("Verificación del kit")

            tabla_verif = mostrar_tabla_verificacion(
                df_kit,
                key_prefix=f"dev_{id_real}_{numero_kit}"
            )

            # Serializar verificación
            col_nombre = None
            for posible in ["INVENTARIO", "Elemento", "Nombre", "Item"]:
                if posible in tabla_verif.columns:
                    col_nombre = posible
                    break

            if col_nombre:
                verificacion = [
                    {
                        "Elemento": str(tabla_verif.iloc[i][col_nombre]),
                        "Presente": bool(tabla_verif.iloc[i]["Presente"])
                    }
                    for i in range(len(tabla_verif))
                ]
            else:
                verificacion = []

    # Datos generales
    persona = st.text_input("Persona que devuelve")
    fecha_dev = st.date_input("Fecha de devolución", value=datetime.now().date())
    observaciones_dev = st.text_area("Observaciones (opcional)")

    # =========================================================
    #      BOTÓN DE REGISTRO
    # =========================================================
    if st.button("Registrar Devolución"):

        if not persona:
            st.error("Ingresa la persona que devuelve.")
            st.stop()

        # =====================================================
        #      DEVOLUCIÓN DE UN KIT
        # =====================================================
        if es_kit and numero_kit:

            try:
                fila_rel = kits_df[
                    (kits_df["ID Inventario"].astype(str) == id_real) &
                    (kits_df["Número Kit"].astype(str) == numero_kit)
                ].index[0]

                row_number = fila_rel + 2
                col_estado = kits_df.columns.get_loc("Estado") + 1
                col_obs = kits_df.columns.get_loc("Observación") + 1

                # Volver a disponible
                sheet_kits.update_cell(row_number, col_estado, "Disponible")
                sheet_kits.update_cell(row_number, col_obs, observaciones_dev or "")

            except Exception as e:
                st.error(f"No pude actualizar el estado del kit: {e}")
                st.stop()

            # Guardar verificación
            ver_json = json.dumps(verificacion, ensure_ascii=False)

            fila_hist = [
                id_real,
                f"{comp_row['Componente']} (Kit {numero_kit})",
                persona,
                "Devolución",
                str(fecha_dev),
                1,
                observaciones_dev if observaciones_dev else "",
                ver_json
            ]

            try:
                sheet_historial.append_row(fila_hist)
                actualizar_estado_y_cantidad(id_real)
                st.success("Devolución registrada correctamente. Kit marcado como Disponible.")
            except Exception as e:
                st.error(f"No pude guardar en HISTORIAL: {e}")

            st.stop()

        # =====================================================
        #    DEVOLUCIÓN NORMAL (sin kit)
        # =====================================================
        historial = cargar_historial()

        total_prestado = sum(
            int(h["Cantidad"]) for h in historial
            if str(h["ID"]) == id_real
            and h["Acción"].lower() == "préstamo"
            and h["Persona"].lower() == persona.lower()
        )

        total_devuelto = sum(
            int(h["Cantidad"]) for h in historial
            if str(h["ID"]) == id_real
            and h["Acción"].lower() == "devolución"
            and h["Persona"].lower() == persona.lower()
        )

        pendiente = total_prestado - total_devuelto

        if pendiente <= 0:
            st.error("No hay préstamos pendientes para esta persona.")
            st.stop()

        cantidad_dev = st.number_input(
            "Cantidad a devolver:",
            min_value=1,
            max_value=pendiente,
            value=pendiente
        )

        fila_hist = [
            id_real,
            comp_row["Componente"],
            persona,
            "Devolución",
            str(fecha_dev),
            int(cantidad_dev),
            observaciones_dev if observaciones_dev else "",
            "[]"
        ]

        try:
            sheet_historial.append_row(fila_hist)
            actualizar_estado_y_cantidad(id_real)
            st.success("Devolución registrada correctamente.")
        except Exception as e:
            st.error(f"No pude guardar en HISTORIAL: {e}")




# ------------------------------
# 4) HISTORIAL
# ------------------------------
elif menu == "Historial":
    st.title("Historial Completo")
    st.dataframe(pd.DataFrame(sheet_historial.get_all_records()), use_container_width=True)

# ------------------------------
# 5) KITS
# ------------------------------
elif menu == "Kits":
    st.title("Listado de KITS")
    st.dataframe(kits_df, use_container_width=True)

# ------------------------------
# Logout en sidebar
# ------------------------------
st.sidebar.markdown("### Sesión")
if st.sidebar.button("Cerrar sesión"):
    cookies["logged"] = "no"
    cookies.save()
    st.session_state["logged_in"] = False
    st.rerun()







































































