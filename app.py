import streamlit as st
import requests
import cloudinary
import cloudinary.uploader
import pandas as pd
from datetime import datetime
import os

# ==============================================================================
# 1. CONFIGURACIÓN Y CREDENCIALES (YA INTEGRADAS)
# ==============================================================================
st.set_page_config(page_title="Gestor Provident", layout="wide", initial_sidebar_state="expanded")

# --- CREDENCIALES FIJAS (NO MODIFICAR) ---
CLOUDINARY_CONFIG = {
    "cloud_name": "dlj0pdv6i",
    "api_key": "847419449273122",
    "api_secret": "i0cJCELeYVAosiBL_ltjHkM_FV0"
}

AIRTABLE_TOKEN = "patyclv7hDjtGHB0F.19829008c5dee053cba18720d38c62ed86fa76ff0c87ad1f2d71bfe853ce9783"
ADMIN_PASS = "3spejoVenenoso$2099"

# Configuración Inicial de Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_CONFIG["cloud_name"],
    api_key=CLOUDINARY_CONFIG["api_key"],
    api_secret=CLOUDINARY_CONFIG["api_secret"]
)

# Listas de configuración
SUCURSALES = ["Puebla", "Veracruz", "Xalapa", "Oaxaca", "León", "Querétaro", "CDMX", "Mérida"]
HISTORIAL_FILE = "historial_modificaciones.csv"

# ==============================================================================
# 2. FUNCIONES DE CONEXIÓN Y UTILIDAD
# ==============================================================================

def registrar_historial(accion, usuario, sucursal, detalles):
    """Guarda un log de las acciones realizadas"""
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nuevo_registro = {
        "Fecha": fecha, "Usuario": usuario, "Sucursal": sucursal,
        "Acción": accion, "Detalles": detalles
    }
    df_new = pd.DataFrame([nuevo_registro])
    if not os.path.exists(HISTORIAL_FILE):
        df_new.to_csv(HISTORIAL_FILE, index=False)
    else:
        df_new.to_csv(HISTORIAL_FILE, mode='a', header=False, index=False)

@st.cache_data(ttl=600) # Caché para no llamar a Airtable a cada rato
def get_bases():
    """Obtiene bases disponibles (Airtable)"""
    url = "https://api.airtable.com/v0/meta/bases"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            return {b['name']: b['id'] for b in r.json().get('bases', [])}
    except: pass
    return {}

@st.cache_data(ttl=60)
def get_tables(base_id):
    """Obtiene tablas (Meses) de la base"""
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            return {t['name']: t['id'] for t in r.json().get('tables', [])}
    except: pass
    return {}

def get_records(base_id, table_id, year, plaza):
    """Busca eventos filtrando por Año y Plaza"""
    # Fórmula Airtable: AND(YEAR({Fecha})=2025, {Sucursal}='Puebla')
    formula = f"AND(YEAR({{Fecha}})={year}, {{Sucursal}}='{plaza}')"
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    params = {"filterByFormula": formula, "sort[0][field]": "Fecha"}
    try:
        r = requests.get(url, headers=headers, params=params)
        if r.status_code == 200:
            return r.json().get('records', [])
    except: pass
    return []

def upload_evidence_to_airtable(base_id, table_id, record_id, updates_dict):
    """Envía URL de imágenes a Airtable"""
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}/{record_id}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}
    data = {"fields": updates_dict}
    r = requests.patch(url, json=data, headers=headers)
    return r.status_code == 200

# ==============================================================================
# 3. GESTIÓN DE ESTADO (SESSION STATE)
# ==============================================================================
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_role' not in st.session_state: st.session_state.user_role = "user"
if 'user_name' not in st.session_state: st.session_state.user_name = ""
if 'sucursal_actual' not in st.session_state: st.session_state.sucursal_actual = ""
if 'selected_event' not in st.session_state: st.session_state.selected_event = None

# ==============================================================================
# 4. PANTALLA DE LOGIN
# ==============================================================================
if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_main, col_form, col_pad = st.columns([1, 2, 1])
    
    with col_form:
        st.image("https://www.provident.com.mx/content/dam/provident-mexico/logos/logo-provident.png", width=200)
        st.markdown("### 🔐 Iniciar Sesión")
        
        with st.form("login_form"):
            # Selección desplegable AL INICIO como solicitaste
            sucursal_sel = st.selectbox("📍 Selecciona Plaza (Sucursal):", SUCURSALES)
            usuario_input = st.text_input("👤 Usuario:")
            
            st.markdown("---")
            es_admin = st.checkbox("Soy Administrador")
            pass_input = st.text_input("Contraseña Admin:", type="password")
            
            btn_ingresar = st.form_submit_button("Ingresar", use_container_width=True)
            
            if btn_ingresar:
                if not usuario_input:
                    st.error("Debes ingresar un usuario.")
                elif es_admin:
                    if pass_input == ADMIN_PASS:
                        st.session_state.logged_in = True
                        st.session_state.user_role = "admin"
                        st.session_state.user_name = f"{usuario_input}"
                        st.session_state.sucursal_actual = "Global (Admin)"
                        registrar_historial("Login Admin", usuario_input, "Global", "Acceso concedido")
                        st.rerun()
                    else:
                        st.error("Contraseña incorrecta.")
                else:
                    st.session_state.logged_in = True
                    st.session_state.user_role = "user"
                    st.session_state.user_name = usuario_input
                    st.session_state.sucursal_actual = sucursal_sel
                    registrar_historial("Login User", usuario_input, sucursal_sel, "Acceso concedido")
                    st.rerun()

# ==============================================================================
# 5. APLICACIÓN PRINCIPAL
# ==============================================================================
else:
    # --- BARRA LATERAL (SIDEBAR) ---
    with st.sidebar:
        st.image("https://www.provident.com.mx/content/dam/provident-mexico/logos/logo-provident.png", width=120)
        
        # Info Usuario
        st.info(f"👤 **{st.session_state.user_name}**\n\n📍 {st.session_state.sucursal_actual}")
        
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.selected_event = None
            st.rerun()
        
        st.divider()
        st.header("⚙️ Configuración")
        
        # 1. SELECCIÓN DE BASE (Airtable)
        bases_map = get_bases()
        if not bases_map:
            st.error("Error conectando a Airtable. Verifica token.")
            st.stop()
            
        base_name = st.selectbox("Base de Datos:", list(bases_map.keys()))
        base_id = bases_map[base_name]

        # 2. SELECCIÓN DE TABLA (Mes)
        tables_map = get_tables(base_id)
        table_id = None
        if tables_map:
            table_name = st.selectbox("Tabla (Mes):", list(tables_map.keys()))
            table_id = tables_map[table_name]
        else:
            st.warning("La base no tiene tablas.")

        # 3. SELECCIÓN DE AÑO
        sel_year = st.number_input("Año:", min_value=2024, max_value=2030, value=2025)

        # 4. SELECCIÓN DE PLAZA (Solo si es Admin, si no, usa la del login)
        if st.session_state.user_role == "admin":
            st.divider()
            sel_plaza = st.selectbox("Filtrar Plaza (Admin):", SUCURSALES)
        else:
            sel_plaza = st.session_state.sucursal_actual

        st.divider()
        # Botón principal de búsqueda
        if st.button("🔎 ACTUALIZAR EVENTOS", type="primary", use_container_width=True):
            st.session_state.selected_event = None
            st.session_state.search_results = get_records(base_id, table_id, sel_year, sel_plaza)
            st.session_state.current_base_id = base_id
            st.session_state.current_table_id = table_id
            st.session_state.current_plaza_view = sel_plaza

    # --- ÁREA PRINCIPAL DE TRABAJO ---
    
    # MODO ADMIN: Pestaña extra para historial
    if st.session_state.user_role == "admin":
        tab_main, tab_hist = st.tabs(["📂 Gestión de Eventos", "📜 Historial de Cambios"])
        
        with tab_hist:
            st.subheader("Registro de Auditoría")
            if os.path.exists(HISTORIAL_FILE):
                df_hist = pd.read_csv(HISTORIAL_FILE)
                st.dataframe(df_hist.sort_values(by="Fecha", ascending=False), use_container_width=True)
            else:
                st.info("No hay historial disponible aún.")
        
        main_area = tab_main
    else:
        main_area = st.container()

    # CONTENIDO PRINCIPAL
    with main_area:
        st.title(f"Gestión: {st.session_state.get('current_plaza_view', sel_plaza)}")

        # A) LISTADO DE EVENTOS
        if st.session_state.selected_event is None:
            if 'search_results' in st.session_state:
                recs = st.session_state.search_results
                if recs:
                    st.success(f"Se encontraron {len(recs)} eventos.")
                    for r in recs:
                        f = r['fields']
                        with st.expander(f"📅 {f.get('Fecha')} | {f.get('Tipo', 'Evento')}"):
                            c1, c2, c3 = st.columns([2, 2, 1])
                            c1.write(f"**Hora:** {f.get('Hora', '--')}")
                            c2.write(f"**Lugar:** {f.get('Punto de reunion', 'N/A')}")
                            if c3.button("📸 SUBIR FOTOS", key=r['id'], use_container_width=True):
                                st.session_state.selected_event = r
                                st.rerun()
                else:
                    st.info("No hay eventos programados con estos filtros.")
            else:
                st.info("👈 Configura la Base y haz clic en 'ACTUALIZAR EVENTOS' en la barra lateral.")

        # B) CUADRÍCULA DE CARGA (GRID)
        else:
            evt = st.session_state.selected_event
            fields = evt['fields']
            
            if st.button("⬅️ VOLVER A LA LISTA"):
                st.session_state.selected_event = None
                st.rerun()

            # Encabezado del Evento
            st.markdown(f"""
            <div style="background-color:#002060; color:white; padding:15px; border-radius:8px;">
                <h3 style="margin:0;">{fields.get('Tipo')}</h3>
                <p style="margin:0;">📅 {fields.get('Fecha')} &nbsp; | &nbsp; ⏰ {fields.get('Hora')} &nbsp; | &nbsp; 📍 {fields.get('Sucursal')}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.write("") # Espacio

            with st.form("evidence_form"):
                
                uploads = {}

                # 1. FOTO DE EQUIPO
                st.markdown("#### 1. Foto de Equipo")
                c_eq, c_prev = st.columns([3, 1])
                uploads['Foto de equipo'] = c_eq.file_uploader("Cargar foto grupal", type=['jpg','png','jpeg'], key="u_eq")
                if fields.get('Foto de equipo'):
                    c_prev.image(fields['Foto de equipo'][0]['url'], caption="Actual", width=120)
                
                st.markdown("---")

                # 2. FOTOS DE ACTIVIDAD (GRID 2 COLUMNAS)
                st.markdown("#### 2. Fotos de Actividad")
                
                # Definición exacta de tu cuadrícula
                grid_layout = [
                    ("Foto 01", "Foto 02"),
                    ("Foto 03", "Foto 04"),
                    ("Foto 05", "Foto 06"),
                    ("Foto 07", None)
                ]
                
                for label_izq, label_der in grid_layout:
                    c1, c2 = st.columns(2)
                    
                    # Columna Izquierda
                    with c1:
                        st.caption(f"📌 {label_izq}")
                        uploads[label_izq] = st.file_uploader(f"u_{label_izq}", type=['jpg','png'], key=f"key_{label_izq}", label_visibility="collapsed")
                        if fields.get(label_izq): st.image(fields[label_izq][0]['url'], width=100)
                    
                    # Columna Derecha
                    if label_der:
                        with c2:
                            st.caption(f"📌 {label_der}")
                            uploads[label_der] = st.file_uploader(f"u_{label_der}", type=['jpg','png'], key=f"key_{label_der}", label_visibility="collapsed")
                            if fields.get(label_der): st.image(fields[label_der][0]['url'], width=100)
                    
                    st.write("") # Separador visual

                st.markdown("---")

                # 3. REPORTE FIRMADO
                st.markdown("#### 3. Reporte Firmado")
                uploads['Reporte firmado'] = st.file_uploader("Cargar PDF o Imagen", type=['pdf','jpg','png'], key="u_rep")
                if fields.get('Reporte firmado'): 
                    st.success(f"✅ Documento cargado: {fields['Reporte firmado'][0]['filename']}")

                # 4. LISTA DE ASISTENCIA (CONDICIONAL)
                if fields.get('Tipo') == "Actividad en Sucursal":
                    st.markdown("---")
                    st.markdown("#### 4. Lista de Asistencia")
                    uploads['Lista de asistencia'] = st.file_uploader("Cargar Lista", type=['pdf','jpg','png'], key="u_lst")
                    if fields.get('Lista de asistencia'):
                        st.success("✅ Lista cargada.")

                st.markdown("<br>", unsafe_allow_html=True)
                
                # BOTÓN FINAL
                submitted = st.form_submit_button("💾 GUARDAR CAMBIOS", type="primary", use_container_width=True)

                if submitted:
                    # Filtrar solo archivos nuevos seleccionados
                    files_to_upload = {k: v for k, v in uploads.items() if v is not None}
                    
                    if not files_to_upload:
                        st.warning("⚠️ No has seleccionado archivos nuevos para subir.")
                    else:
                        progress = st.progress(0)
                        status = st.empty()
                        
                        try:
                            # 1. Subir a Cloudinary
                            updates_airtable = {}
                            total = len(files_to_upload)
                            
                            for i, (key, file_obj) in enumerate(files_to_upload.items()):
                                status.text(f"Subiendo {key}...")
                                resp = cloudinary.uploader.upload(file_obj)
                                updates_airtable[key] = [{"url": resp['secure_url']}]
                                progress.progress((i + 1) / (total + 1))
                            
                            # 2. Actualizar Airtable
                            status.text("Actualizando base de datos...")
                            success = upload_evidence_to_airtable(
                                st.session_state.current_base_id,
                                st.session_state.current_table_id,
                                evt['id'],
                                updates_airtable
                            )
                            progress.progress(1.0)
                            
                            if success:
                                st.success("✅ ¡Información guardada correctamente!")
                                st.balloons()
                                
                                # Log en Historial
                                log_det = f"Archivos subidos: {list(files_to_upload.keys())} - ID: {evt['id']}"
                                registrar_historial("Carga Fotos", st.session_state.user_name, st.session_state.sucursal_actual, log_det)
                                
                                # Actualizar vista local
                                st.session_state.selected_event['fields'].update(updates_airtable)
                                st.rerun()
                            else:
                                st.error("❌ Error al conectar con Airtable.")
                                
                        except Exception as e:
                            st.error(f"Error técnico: {str(e)}")
