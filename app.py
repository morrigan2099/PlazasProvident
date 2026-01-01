import streamlit as st
import requests
import cloudinary
import cloudinary.uploader
from datetime import datetime
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestor de Evidencia Provident", layout="wide")

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .header-zone { background-color: #002060; color: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
    .stExpander { border: 1px solid #ddd; border-radius: 5px; }
    h1, h2, h3 { color: #002060; }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES DE SOPORTE ---

def init_cloudinary(cloud_name, api_key, api_secret):
    """Configura Cloudinary solo si hay credenciales válidas"""
    if cloud_name and api_key and api_secret:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret
        )
        return True
    return False

def get_tables(base_id, token):
    """Obtiene la lista de tablas (Meses) de la base"""
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            return r.json().get('tables', [])
    except Exception as e:
        st.error(f"Error de conexión: {e}")
    return []

def get_records(base_id, table_id, token, year, plaza):
    """Filtra registros por Año y Plaza usando fórmulas de Airtable"""
    # IMPORTANTE: Asegúrate de que en Airtable las columnas se llamen 'Fecha' y 'Sucursal'
    # Si 'Sucursal' es un campo de selección simple, esto funciona.
    formula = f"AND(YEAR({{Fecha}})={year}, {{Sucursal}}='{plaza}')"
    
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"filterByFormula": formula}
    
    try:
        r = requests.get(url, headers=headers, params=params)
        if r.status_code == 200:
            return r.json().get('records', [])
    except: pass
    return []

def upload_evidence(base_id, table_id, token, record_id, updates_dict):
    """Envía los links de las imágenes a Airtable"""
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}/{record_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {"fields": updates_dict}
    r = requests.patch(url, json=data, headers=headers)
    return r.status_code == 200

# --- INTERFAZ SIDEBAR ---
with st.sidebar:
    st.image("https://www.provident.com.mx/content/dam/provident-mexico/logos/logo-provident.png", width=150)
    st.header("⚙️ Configuración")
    
    # Intenta leer secretos de Streamlit, si no, usa inputs manuales
    # Esto permite que funcione tanto en local como en producción segura
    secrets = st.secrets if "AIRTABLE_TOKEN" in st.secrets else {}
    
    with st.expander("Credenciales API", expanded=not bool(secrets)):
        token = st.text_input("Airtable Token", value=secrets.get("AIRTABLE_TOKEN", ""), type="password")
        base_id = st.text_input("Base ID", value=secrets.get("AIRTABLE_BASE_ID", ""))
        
        st.caption("Cloudinary")
        c_name = st.text_input("Cloud Name", value=secrets.get("CLOUD_NAME", ""))
        c_key = st.text_input("API Key", value=secrets.get("CLOUD_KEY", ""))
        c_secret = st.text_input("API Secret", value=secrets.get("CLOUD_SECRET", ""), type="password")

    st.divider()
    
    st.header("📍 Navegación")
    sel_year = st.number_input("Año", min_value=2024, max_value=2030, value=2025)
    sel_plaza = st.text_input("Plaza (Sucursal)", value="Puebla")
    
    if st.button("🔎 BUSCAR EVENTOS", use_container_width=True):
        st.session_state['search_trigger'] = True
        st.session_state['selected_event'] = None # Reset
        st.rerun()

# --- LOGICA PRINCIPAL ---
st.title(f"Gestión de Evidencia: {sel_plaza} {sel_year}")

# Inicializar Cloudinary
cloudinary_ready = init_cloudinary(c_name, c_key, c_secret)

if 'selected_event' not in st.session_state:
    st.session_state['selected_event'] = None

# VISTA A: LISTADO (BUSQUEDA)
if st.session_state.get('selected_event') is None:
    if token and base_id and st.session_state.get('search_trigger'):
        with st.spinner("Conectando con Airtable..."):
            tables = get_tables(base_id, token)
            
            if not tables:
                st.warning("No se encontraron tablas. Verifica el Base ID y el Token.")
            
            tables_found = False
            for table in tables:
                # Buscamos registros en cada mes
                records = get_records(base_id, table['id'], token, sel_year, sel_plaza)
                
                if records:
                    tables_found = True
                    with st.expander(f"📂 {table['name']} ({len(records)} eventos)", expanded=False):
                        for rec in records:
                            f = rec['fields']
                            col1, col2, col3, col4 = st.columns([2, 3, 2, 2])
                            col1.write(f"📅 **{f.get('Fecha', 'S/F')}**")
                            col2.write(f"{f.get('Tipo', 'Evento')}")
                            col3.write(f"⏰ {f.get('Hora', '--')}")
                            
                            if col4.button("📂 Abrir", key=rec['id']):
                                st.session_state['selected_event'] = rec
                                st.session_state['current_table_id'] = table['id']
                                st.rerun()
                            st.markdown("---")
            
            if not tables_found and tables:
                st.info(f"No se encontraron eventos para {sel_plaza} en el año {sel_year}.")
    else:
        st.info("👈 Ingresa tus credenciales y haz clic en 'Buscar Eventos'.")

# VISTA B: FORMULARIO DE CARGA
else:
    evt = st.session_state['selected_event']
    fields = evt['fields']
    table_id = st.session_state['current_table_id']
    
    if st.button("⬅️ Volver al listado"):
        st.session_state['selected_event'] = None
        st.rerun()

    # Header del evento
    st.markdown(f"""
    <div class="header-zone">
        <h3>{fields.get('Tipo', 'Evento')}</h3>
        <p><b>Fecha:</b> {fields.get('Fecha')} &nbsp; | &nbsp; <b>Sucursal:</b> {fields.get('Sucursal')} &nbsp; | &nbsp; <b>Hora:</b> {fields.get('Hora')}</p>
        <p><i>Punto de reunión: {fields.get('Punto de reunion', 'N/A')}</i></p>
    </div>
    """, unsafe_allow_html=True)

    if not cloudinary_ready:
        st.error("⚠️ Configura Cloudinary en el menú lateral para subir fotos.")
    
    with st.form("evidence_form", clear_on_submit=False):
        
        uploads = {} # Almacén temporal de archivos

        # 1. FOTO DE EQUIPO
        st.markdown("### 1. Foto de Equipo")
        col_eq, col_prev = st.columns([3, 1])
        uploads['Foto de equipo'] = col_eq.file_uploader("Subir Foto Grupal", type=['jpg', 'png', 'jpeg'], key="u_eq")
        if fields.get('Foto de equipo'):
            col_prev.image(fields['Foto de equipo'][0]['url'], caption="Actual", use_container_width=True)

        st.markdown("---")

        # 2. FOTOS DE ACTIVIDAD (GRID)
        st.markdown("### 2. Fotos de Actividad")
        
        # Matriz de campos solicitada
        grid_layout = [
            ("Foto 01", "Foto 02"),
            ("Foto 03", "Foto 04"),
            ("Foto 05", "Foto 06"),
            ("Foto 07", None)
        ]
        
        for f_left, f_right in grid_layout:
            c1, c2 = st.columns(2)
            # Izquierda
            with c1:
                st.caption(f"📸 {f_left}")
                uploads[f_left] = st.file_uploader(f"Cargar", type=['jpg','png'], key=f"u_{f_left}", label_visibility="collapsed")
                if fields.get(f_left): st.image(fields[f_left][0]['url'], width=120)
            
            # Derecha
            if f_right:
                with c2:
                    st.caption(f"📸 {f_right}")
                    uploads[f_right] = st.file_uploader(f"Cargar", type=['jpg','png'], key=f"u_{f_right}", label_visibility="collapsed")
                    if fields.get(f_right): st.image(fields[f_right][0]['url'], width=120)
            st.write("") # Espaciador

        st.markdown("---")

        # 3. REPORTE FIRMADO
        st.markdown("### 3. Reporte Firmado")
        uploads['Reporte firmado'] = st.file_uploader("PDF o Foto del Reporte", type=['pdf', 'jpg', 'png'], key="u_rep")
        if fields.get('Reporte firmado'): st.success(f"✅ Documento cargado: {fields['Reporte firmado'][0]['filename']}")

        st.markdown("---")

        # 4. LISTA DE ASISTENCIA (CONDICIONAL)
        if fields.get('Tipo') == "Actividad en Sucursal":
            st.markdown("### 4. Lista de Asistencia")
            uploads['Lista de asistencia'] = st.file_uploader("PDF o Foto de Lista", type=['pdf', 'jpg', 'png'], key="u_list")
            if fields.get('Lista de asistencia'): st.success("✅ Lista cargada")
        
        st.write("")
        submitted = st.form_submit_button("💾 GUARDAR EVIDENCIAS", type="primary", use_container_width=True)

        if submitted:
            if not cloudinary_ready:
                st.error("No se puede subir: Faltan credenciales de Cloudinary.")
            else:
                updates = {}
                progress_text = st.empty()
                
                try:
                    files_to_process = {k: v for k, v in uploads.items() if v is not None}
                    
                    if not files_to_process:
                        st.warning("No has seleccionado archivos nuevos para subir.")
                    else:
                        with st.spinner("Subiendo archivos a la nube..."):
                            for key, file_obj in files_to_process.items():
                                # 1. Subir a Cloudinary
                                resp = cloudinary.uploader.upload(file_obj)
                                img_url = resp['secure_url']
                                # 2. Preparar para Airtable
                                updates[key] = [{"url": img_url}]
                            
                            # 3. Guardar en Airtable
                            if upload_evidence(base_id, table_id, token, evt['id'], updates):
                                st.success("✅ ¡Guardado exitosamente!")
                                st.balloons()
                                # Actualizar vista local (hack simple)
                                st.session_state['selected_event']['fields'].update(updates)
                                st.rerun()
                            else:
                                st.error("❌ Error al guardar en Airtable. Verifica permisos.")
                except Exception as e:
                    st.error(f"Error técnico: {e}")