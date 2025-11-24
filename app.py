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

# ====================================
# Pantalla para marcar/verificar contenido del kit (con fallback manual)
# ====================================

def mostrar_verificacion_kit(nombre_kit, url_qr, creds):
    st.subheader(f"Verificación de contenido – {nombre_kit}")

    tabla = cargar_tabla_kit(url_qr, creds)

    if tabla is None:
        st.error("No se pudo cargar la lista del kit desde el QR.")
        return None

    # Convertir a DataFrame (esto elimina llaves feas)
    df_tabla = pd.DataFrame(tabla)

    # Mostrar tabla normal del kit
    st.write("### Contenido del Kit")
    st.dataframe(df_tabla, use_container_width=True)

    st.write("### Verificación")

    estados = []
    for i, item in df_tabla.iterrows():
        elemento = item.get("Elemento", f"Elemento {i}")

        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"📦 {elemento}")
        with col2:
            ok = st.checkbox("OK", key=f"verif_{nombre_kit}_{i}")

        estados.append({
            "Elemento": elemento,
            "OK": ok
        })

    return estados


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
    # recargar para datos actualizados
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
    else:
        seleccionado = st.selectbox(
            "Seleccione un componente:",
            coincidencias["Componente"] + " (ID: " + coincidencias["ID"].astype(str) + ")"
        )
        id_real = seleccionado.split("ID: ")[1].replace(")", "")
        comp_row = coincidencias[coincidencias["ID"].astype(str) == id_real].iloc[0]
        st.write(client.open("INVENTARIO").worksheets())
        st.write(f"**Componente:** {comp_row['Componente']}  —  **ID:** {id_real}")

        # comprobar si hay kits relacionados
        kits_relacionados = kits_df[kits_df["ID Inventario"].astype(str) == str(id_real)]
        es_kit = not kits_relacionados.empty

        numero_kit = None
        verificacion = []
        url_qr = None

        if es_kit:
            st.subheader("Este componente tiene KITS disponibles")
            kits_disponibles = kits_relacionados[kits_relacionados["Estado"].astype(str).str.lower() == "disponible"]
            if kits_disponibles.empty:
                st.warning("No hay kits marcados como 'Disponible' en KITS.")
            else:
                numero_kit = st.selectbox("Seleccione el número de kit disponible:", kits_disponibles["Número Kit"].astype(str))
                kit_row = kits_disponibles[kits_disponibles["Número Kit"].astype(str) == numero_kit].iloc[0]
                st.write("Observación:", kit_row.get("Observación", ""))
                url_qr = kit_row.get("QR", "")

                # mostrar verificación (fallback)
                verificacion = mostrar_verificacion_con_fallback(f"{comp_row['Componente']} - Kit #{numero_kit}", url_qr, key_prefix=f"pre_{id_real}_{numero_kit}")

        # Datos del préstamo
        nombre = st.text_input("Nombre de quien realiza el préstamo")
        fecha_prestamo = st.date_input("Fecha del préstamo", value=datetime.now().date())
        cantidad = st.number_input("Cantidad (para componentes indiv.)", min_value=1, step=1, value=1)

        if st.button("Registrar Préstamo"):
            if not nombre:
                st.error("Ingresa el nombre de quien realiza el préstamo.")
            else:
                # preparar fila para historial (se añade al final la verificación JSON si existe)
                accion = "Préstamo"
                cantidad_grabar = 1 if es_kit else int(cantidad)
                obs_col = ""
                # si es kit, poner detalle Kit # en Observaciones (o en columna 7 según tu hoja)
                if es_kit:
                    obs_col = f"Kit #{numero_kit}"
                    # actualizar estado en hoja KITS a Prestado
                    fila_kit_idx = kits_df[
                    (kits_df["ID Inventario"].astype(str) == str(id_real)) &
                    (kits_df["Número Kit"].astype(str) == str(numero_kit))
                     ].index

                    # better: find the matching row in kits_df (use loc)
                    try:
                        fila_rel = kits_df[
                            (kits_df["ID Inventario"].astype(str) == str(id_real)) &
                            (kits_df["Número Kit"].astype(str) == numero_kit)
                        ].index[0]
                        row_number = fila_rel + 2
                        col_estado = kits_df.columns.get_loc("Estado") + 1
                        sheet_kits.update_cell(row_number, col_estado, "Prestado")
                    except Exception:
                        # fallback: try to use kits_relacionados earlier
                        try:
                            fila_rel2 = kits_relacionados[
                                kits_relacionados["Número Kit"].astype(str) == numero_kit
                            ].index[0]
                            sheet_kits.update_cell(fila_rel2 + 2, kits_df.columns.get_loc("Estado") + 1, "Prestado")
                        except Exception:
                            st.warning("No pude actualizar el estado del kit (verifica permisos).")

                # verificación -> JSON
                ver_json = json.dumps(verificacion, ensure_ascii=False)

                # construir fila para append (ajusta orden según tu hoja HISTORIAL)
                # tu esquema anterior era: [ID, Componente, Persona, Acción, Fecha, Cantidad, Observaciones]
                fila_hist = [
                    id_real,
                    comp_row["Componente"],
                    nombre,
                    accion,
                    str(fecha_prestamo),
                    cantidad_grabar,
                    obs_col,
                    ver_json  # columna extra para la verificación
                ]
                try:
                    sheet_historial.append_row(fila_hist)
                    actualizar_estado_y_cantidad(id_real)
                    st.success("Préstamo registrado y verificación guardada en HISTORIAL.")
                except Exception as e:
                    st.error(f"No pude guardar el préstamo en HISTORIAL: {e}")

# ------------------------------
# 3) REGISTRAR DEVOLUCIÓN (con verificación)
# ------------------------------
elif menu == "Registrar Devolución":
    st.title("Registrar Devolución")
    inventario_df = pd.DataFrame(sheet_inventario.get_all_records())
    kits_df = pd.DataFrame(sheet_kits.get_all_records())

    busqueda = st.text_input("Buscar componente (por nombre o ID):")
    coincidencias = pd.DataFrame()
    if busqueda:
        coincidencias = inventario_df[
            inventario_df["Componente"].str.contains(busqueda, case=False, na=False) |
            inventario_df["ID"].astype(str).str.contains(busqueda, case=False, na=False)
        ]
    if coincidencias.empty:
        st.info("Busca un componente para comenzar la devolución.")
    else:
        seleccionado = st.selectbox(
            "Seleccione un componente:",
            coincidencias["Componente"] + " (ID: " + coincidencias["ID"].astype(str) + ")"
        )
        id_real = seleccionado.split("ID: ")[1].replace(")", "")
        comp_row = coincidencias[coincidencias["ID"].astype(str) == id_real].iloc[0]
        st.write(f"**Componente:** {comp_row['Componente']}  —  **ID:** {id_real}")

        # comprobar kits relacionados
        kits_relacionados = kits_df[kits_df["ID Inventario"].astype(str) == str(id_real)]
        es_kit = not kits_relacionados.empty

        numero_kit = None
        verificacion = []
        url_qr = None

        if es_kit:
            st.subheader("Este componente tiene KITS registrados")
            kits_prestados = kits_relacionados[kits_relacionados["Estado"].astype(str).str.lower() == "prestado"]
            if kits_prestados.empty:
                st.warning("No hay kits marcados como 'Prestado' para este componente.")
            else:
                opciones = (kits_prestados["Kit ID"].astype(str) + " - Kit #" + kits_prestados["Número Kit"].astype(str))
                seleccion_kit = st.selectbox("Selecciona el kit a devolver:", opciones)
                if seleccion_kit:
                    kit_id = seleccion_kit.split(" - ")[0].strip()
                    row_kit = kits_prestados[kits_prestados["Kit ID"].astype(str) == kit_id].iloc[0]
                    numero_kit = str(row_kit["Número Kit"])
                    url_qr = row_kit.get("QR", "")
                    # mostrar verificación
                    verificacion = mostrar_verificacion_con_fallback(f"{comp_row['Componente']} - Kit #{numero_kit}", url_qr, key_prefix=f"dev_{id_real}_{numero_kit}")

        # datos devolución
        persona = st.text_input("Persona que devuelve")
        fecha_dev = st.date_input("Fecha de devolución", value=datetime.now().date())
        observaciones_dev = st.text_area("Observaciones (opcional)")

        if st.button("Registrar Devolución"):
            if not persona:
                st.error("Ingresa la persona que devuelve.")
            else:
                if es_kit and numero_kit:
                    # actualizar estado en KITS a Disponible
                    try:
                        fila_rel = kits_df[
                            (kits_df["ID Inventario"].astype(str) == str(id_real)) &
                            (kits_df["Número Kit"].astype(str) == numero_kit)
                        ].index[0]
                        row_number = fila_rel + 2
                        col_estado = kits_df.columns.get_loc("Estado") + 1
                        col_obs = kits_df.columns.get_loc("Observación") + 1
                        sheet_kits.update_cell(row_number, col_estado, "Disponible")
                        sheet_kits.update_cell(row_number, col_obs, observaciones_dev if observaciones_dev else "")
                    except Exception:
                        st.warning("No pude actualizar el estado del kit (verifica permisos).")

                    ver_json = json.dumps(verificacion, ensure_ascii=False)
                    # Historial row
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
                        st.success("Devolución y verificación guardadas en HISTORIAL. Kit marcado como Disponible.")
                    except Exception as e:
                        st.error(f"No pude guardar la devolución en HISTORIAL: {e}")

                else:
                    # devolución normal de componente
                    historial = sheet_historial.get_all_records()
                    total_prestado = sum(
                        int(h["Cantidad"]) for h in historial
                        if str(h["ID"]).strip().lower() == str(id_real).strip().lower()
                        and str(h["Acción"]).strip().lower() == "préstamo"
                        and h["Persona"].strip().lower() == persona.strip().lower()
                    )
                    total_devuelto = sum(
                        int(h["Cantidad"]) for h in historial
                        if str(h["ID"]).strip().lower() == str(id_real).strip().lower()
                        and str(h["Acción"]).strip().lower() == "devolución"
                        and h["Persona"].strip().lower() == persona.strip().lower()
                    )
                    pendiente = total_prestado - total_devuelto
                    if pendiente <= 0:
                        st.error("No hay préstamos pendientes para esta persona y componente.")
                    else:
                        cantidad_dev = st.number_input("Cantidad a devolver ahora:", min_value=1, max_value=pendiente, value=1)
                        if st.button("Confirmar devolución de componente"):
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
                                st.error(f"No pude guardar la devolución en HISTORIAL: {e}")

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





















































