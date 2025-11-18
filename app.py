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
elif menu == "Registrar Devolución":
    st.title("Registrar Devolución")

    busqueda = st.text_input("Buscar componente (por nombre o ID):")

    if busqueda:
        # Buscar coincidencias en el inventario
        coincidencias = inventario[
            inventario["Componente"].str.contains(busqueda, case=False, na=False)
            | inventario["ID"].astype(str).str.contains(busqueda, na=False)
        ]

        if coincidencias.empty:
            st.warning("No se encontraron componentes.")
        else:
            componente = coincidencias.iloc[0]

            st.subheader(f"Componente seleccionado: **{componente['Componente']}**")

            # 🔍 Verificar si es un KIT en la hoja KITS
            kits_de_este = kits[kits["ID Inventario"] == componente["ID"]]

            if not kits_de_este.empty:
                st.info("Este componente es un **KIT**. Selecciona cuál quieres devolver.")

                # Kits actualmente prestados
                kits_prestados = kits_de_este[kits_de_este["Estado"] == "Prestado"]

                if kits_prestados.empty:
                    st.warning("Ningún kit de este componente está prestado actualmente.")
                else:
                    # Selección de número de kit para devolver
                    kit_elegido = st.selectbox(
                        "Selecciona el número de kit a devolver:",
                        kits_prestados["Número Kit"].tolist()
                    )

                    observacion = st.text_area("Observación (opcional):")

                    if st.button("Registrar Devolución del KIT"):
                        idx = kits_prestados[kits_prestados["Número Kit"] == kit_elegido].index[0]

                        # Actualizar estado en la hoja KITS
                        sheets.update_cell("KITS", idx + 2, kits.columns.get_loc("Estado") + 1, "Disponible")
                        sheets.update_cell("KITS", idx + 2, kits.columns.get_loc("Observación") + 1, observacion)

                        # Registrar la devolución en historial
                        nuevo_registro = pd.DataFrame([{
                            "Tipo": "Devolución KIT",
                            "Componente": componente["Componente"],
                            "Número Kit": kit_elegido,
                            "Fecha": str(date.today()),
                            "Observación": observacion
                        }])
                        historial = pd.concat([historial, nuevo_registro], ignore_index=True)
                        save_to_sheet("HISTORIAL", historial)

                        st.success(f"Kit #{kit_elegido} devuelto correctamente.")
            else:
                # ⚙️ Devolución normal (no es un kit)
                st.info("Este componente NO es un kit. Procesando devolución normal.")

                cantidad = st.number_input("Cantidad a devolver:", min_value=1, step=1)
                observacion = st.text_area("Observación (opcional):")

                if st.button("Registrar Devolución"):
                    nuevo_total = componente["Cantidad"] + cantidad

                    inventario.loc[componente.name, "Cantidad"] = nuevo_total
                    save_to_sheet("INVENTARIO", inventario)

                    nuevo_registro = pd.DataFrame([{
                        "Tipo": "Devolución",
                        "Componente": componente["Componente"],
                        "Cantidad": cantidad,
                        "Fecha": str(date.today()),
                        "Observación": observacion
                    }])
                    historial = pd.concat([historial, nuevo_registro], ignore_index=True)
                    save_to_sheet("HISTORIAL", historial)

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







































