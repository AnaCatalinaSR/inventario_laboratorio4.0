# Sistema de Préstamos de Inventario

Aplicación web desarrollada con **Streamlit** y conectada a **Google Sheets**, diseñada para gestionar el préstamo y devolución de equipos en el laboratorio.

---

## Características

- Visualización del inventario en tiempo real desde Google Sheets.
- Registro de préstamos con nombre del responsable y fecha.
- Registro de devoluciones con control de cantidades.
- Historial automático de movimientos.
- Control de disponibilidad de equipos.

---

## Tecnologías utilizadas

- Python
- Streamlit
- Pandas
- Google Sheets API (via `gspread` y `oauth2client`)

---

## Instalación

1. Clona este repositorio:
   ```bash
   git clone https://github.com/tuusuario/inventario-laboratorio.git
   cd inventario-laboratorio
