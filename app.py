import streamlit as st
import requests
import cloudinary
import cloudinary.uploader
import pandas as pd
from datetime import datetime
import os

# ==============================================================================
# 1. CONFIGURACIÓN Y CREDENCIALES
# ==============================================================================
st.set_page_config(page_title="Gestor Provident", layout="wide", initial_sidebar_state="expanded")

# --- CREDENCIALES FIJAS ---
CLOUDINARY_CONFIG = {
    "cloud_name": "dlj0pdv6i",
    "api_key": "847419449273122",
    "api_secret": "i0cJCELeYVAosiBL_ltjHkM_FV0"
}

AIRTABLE_TOKEN = "patyclv7hDjtGHB0F.19829008c5dee053cba18720d38c62ed86fa76ff0c87ad1f2d71bfe853ce9783"
ADMIN_PASS = "3spejoVenenoso$2099"

# Configuración Inicial
cloudinary.config(
    cloud_name=CLOUDINARY_CONFIG["cloud_name"],
    api_key=CLOUDINARY_CONFIG["api_key"],
    api_secret=CLOUDINARY_CONFIG["api_secret"]
)

SUCURSALES = ["Puebla", "Veracruz", "Xalapa", "Oaxaca", "León", "Querétaro", "CDMX", "Mérida"]
HISTORIAL_FILE = "historial_modificaciones.csv"

# ==============================================================================
# 2. FUNCIONES
# ==============================================================================

def registrar_historial(accion, usuario, sucursal, detalles):
    """Guarda registro de actividad en CSV"""
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

@st.cache_data(ttl=600)
def get_bases():
    """Obtiene bases de Airtable"""
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
    """Obtiene tablas (Meses)"""
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            return {t['name']: t['id'] for t in r.json().get('tables', [])}
    except: pass
    return {}

def get_records(base_id, table_id, year, plaza):
    """
    Obtiene TODOS los registros y filtra manualmente en Python 
    para evitar errores de fórmulas de Airtable.
    """
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    
    # 1. Traemos TODO sin filtrar por fórmula (más seguro)
    try:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            st.error(f"Error Airtable ({r.status_code}): {r.text}")
            return []
            
        all_records = r.json().get('records', [])
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return []

    # 2. Filtramos en Python (Más flexible)
    filtered_records = []
    
    for rec in all_records:
        f = rec.get('fields', {})
        
        # --- A. VERIFICACIÓN DE FECHA ---
        # Buscamos campos comunes de fecha si 'Fecha' no existe
        fecha_str = f.get('Fecha') or f.get('Date') or f.get('Dia')
        
        match_year = False
        if fecha_str:
            try:
                # Si es '2025-01-20', tomamos los primeros 4 chars
                if str(fecha_str)[:4] == str(year):
                    match_year = True
            except: pass
        
        # --- B. VERIFICACIÓN DE SUCURSAL ---
        # Buscamos campos comunes de lugar
        suc_dato = f.get('Sucursal') or f.get('Plaza') or f.get('Lugar')
        
        match_plaza = False
        if suc_dato:
            # A veces Airtable devuelve listas si es un campo de enlace
            val_suc = suc_dato[0] if isinstance(suc_dato, list) else suc_dato
            
            # Comparamos ignorando mayúsculas/minúsculas
            if str(val_suc).strip().lower() == str(plaza).strip().lower():
                match_plaza = True
        
        # Si cumple AMBOS (o si no hay fecha estricta, solo plaza), lo agregamos
        if match_plaza and match_year:
            filtered_records.append(rec)
            
    # Ordenar por fecha (opcional)
    try:
        filtered_records.sort(key=lambda x: x['fields'].get('Fecha', ''))
    except: pass

    return filtered_records

# ==============================================================================
# 3. GESTIÓN DE SESIÓN
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
    col_izq, col_centro, col_der = st.columns([1, 2, 1])
    
    with col_centro:
        st.image("https://www.provident.com.mx/content/dam/provident-mexico/logos/logo-provident.png", width=200)
        st.markdown("### 🔐 Acceso al Sistema")
        
        with st.form("login_form"):
            # Selección de Plaza (Solo aquí se elige la plaza del usuario)
            sucursal_sel = st.selectbox("📍 Selecciona tu Plaza (Sucursal):", SUCURSALES)
            usuario_input = st.text_input("👤 Usuario:")
            
            st.markdown("---")
            es_admin = st.checkbox("Soy Administrador")
            pass_input = st.text_input("Contraseña Admin:", type="password")
            
            btn_ingresar = st.form_submit_button("Ingresar", use_container_width=True)
            
            if btn_ingresar:
                if not usuario_input:
                    st.error("Ingresa un usuario.")
                elif es_admin:
                    if pass_input == ADMIN_PASS:
                        st.session_state.logged_in = True
                        st.session_state.user_role = "admin"
                        st.session_state.user_name = usuario_input
                        st.session_state.sucursal_actual = sucursal_sel # El admin inicia en una plaza pero puede cambiar
                        registrar_historial("Login Admin", usuario_input, "Global", "Acceso OK")
                        st.rerun()
                    else:
                        st.error("Contraseña incorrecta.")
                else:
                    # Usuario normal
                    st.session_state.logged_in = True
                    st.session_state.user_role = "user"
                    st.session_state.user_name = usuario_input
                    st.session_state.sucursal_actual = sucursal_sel
                    registrar_historial("Login User", usuario_input, sucursal_sel, "Acceso OK")
                    st.rerun()

# ==============================================================================
# 5. APLICACIÓN PRINCIPAL
# ==============================================================================
else:
    # --- BARRA LATERAL (SIDEBAR) ---
    with st.sidebar:
        st.header("📅 Configuración")
        
        # 1. Base de Datos
        bases_map = get_bases()
        if not bases_map:
            st.error("Error de conexión con Airtable.")
            st.stop()
        base_name = st.selectbox("Base de Datos:", list(bases_map.keys()))
        base_id = bases_map[base_name]

        # 2. Tabla (Mes)
        tables_map = get_tables(base_id)
        table_id = None
        if tables_map:
            table_name = st.selectbox("Mes de Trabajo:", list(tables_map.keys()))
            table_id = tables_map[table_name]
        else:
            st.warning("Sin tablas.")

        # 3. Año
        sel_year = st.number_input("Año:", min_value=2024, max_value=2030, value=2025)
        
        st.divider()

        # 4. LÓGICA DE PLAZA (Clave del requerimiento)
        if st.session_state.user_role == "admin":
            # El administrador PUEDE ver el filtro y cambiarlo
            st.subheader("🛠 Opciones de Admin")
            sel_plaza = st.selectbox("Cambiar Plaza:", SUCURSALES, index=SUCURSALES.index(st.session_state.sucursal_actual) if st.session_state.sucursal_actual in SUCURSALES else 0)
        else:
            # El usuario NO ve el filtro, se usa su variable de sesión automática
            sel_plaza = st.session_state.sucursal_actual
            st.info(f"📍 Plaza Fija: **{sel_plaza}**")

        # Botón para cargar eventos
        if st.button("🔄 ACTUALIZAR EVENTOS", type="primary", use_container_width=True):
            st.session_state.selected_event = None
            st.session_state.search_results = get_records(base_id, table_id, sel_year, sel_plaza)
            st.session_state.current_base_id = base_id
            st.session_state.current_table_id = table_id
            st.session_state.current_plaza_view = sel_plaza

        st.divider()
        st.caption(f"👤 {st.session_state.user_name}")
        if st.button("Cerrar Sesión"):
            st.session_state.logged_in = False
            st.rerun()

    # --- ÁREA PRINCIPAL ---
    
    # Manejo de pestañas solo para Admin
    if st.session_state.user_role == "admin":
        tab_main, tab_hist = st.tabs(["📂 Gestión de Eventos", "📜 Historial de Cambios"])
        with tab_hist:
            if os.path.exists(HISTORIAL_FILE):
                df_hist = pd.read_csv(HISTORIAL_FILE)
                st.dataframe(df_hist.sort_values(by="Fecha", ascending=False), use_container_width=True)
            else:
                st.info("Sin historial.")
        main_area = tab_main
    else:
        main_area = st.container()

    with main_area:
        st.title(f"Gestión: {st.session_state.get('current_plaza_view', sel_plaza)}")

        # VISTA A: TARJETAS DE EVENTOS (NO TABLAS)
        if st.session_state.selected_event is None:
            if 'search_results' in st.session_state:
                recs = st.session_state.search_results
                if recs:
                    for r in recs:
                        f = r['fields']
                        # Usamos Expander para que parezca una tarjeta limpia
                        with st.expander(f"📅 {f.get('Fecha')} | {f.get('Tipo', 'Evento')}"):
                            c1, c2, c3 = st.columns([2, 2, 1])
                            c1.markdown(f"**Hora:** {f.get('Hora', '--')}")
                            c2.markdown(f"**Punto:** {f.get('Punto de reunion', 'N/A')}")
                            if c3.button("📸 SUBIR FOTOS", key=r['id'], use_container_width=True):
                                st.session_state.selected_event = r
                                st.rerun()
                else:
                    st.info(f"No hay eventos programados en {sel_plaza} para esta fecha.")
            else:
                st.info("👈 Selecciona el Mes y pulsa 'ACTUALIZAR EVENTOS'.")

        # VISTA B: FORMULARIO DE CARGA
        else:
            evt = st.session_state.selected_event
            fields = evt['fields']
            
            if st.button("⬅️ VOLVER AL LISTADO"):
                st.session_state.selected_event = None
                st.rerun()

            st.markdown(f"""
            <div style="background-color:#002060; color:white; padding:15px; border-radius:8px; margin-bottom:20px;">
                <h3 style="margin:0;">{fields.get('Tipo')}</h3>
                <p style="margin:0;">📅 {fields.get('Fecha')} &nbsp; | &nbsp; ⏰ {fields.get('Hora')}</p>
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("evidence_form"):
                
                uploads = {}

                # 1. FOTO DE EQUIPO
                st.markdown("#### 1. Foto de Equipo")
                c_eq, c_prev = st.columns([3, 1])
                uploads['Foto de equipo'] = c_eq.file_uploader("Cargar foto", type=['jpg','png','jpeg'], key="u_eq")
                if fields.get('Foto de equipo'):
                    c_prev.image(fields['Foto de equipo'][0]['url'], caption="Actual", width=120)
                
                st.markdown("---")

                # 2. GRID DE ACTIVIDAD
                st.markdown("#### 2. Fotos de Actividad")
                grid_layout = [
                    ("Foto 01", "Foto 02"),
                    ("Foto 03", "Foto 04"),
                    ("Foto 05", "Foto 06"),
                    ("Foto 07", None)
                ]
                
                for l_izq, l_der in grid_layout:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.caption(f"📌 {l_izq}")
                        uploads[l_izq] = st.file_uploader(f"u_{l_izq}", type=['jpg','png'], key=f"k_{l_izq}", label_visibility="collapsed")
                        if fields.get(l_izq): st.image(fields[l_izq][0]['url'], width=100)
                    if l_der:
                        with c2:
                            st.caption(f"📌 {l_der}")
                            uploads[l_der] = st.file_uploader(f"u_{l_der}", type=['jpg','png'], key=f"k_{l_der}", label_visibility="collapsed")
                            if fields.get(l_der): st.image(fields[l_der][0]['url'], width=100)
                    st.write("")

                st.markdown("---")

                # 3. REPORTE
                st.markdown("#### 3. Reporte Firmado")
                uploads['Reporte firmado'] = st.file_uploader("Cargar PDF/Img", type=['pdf','jpg','png'], key="u_rep")
                if fields.get('Reporte firmado'): 
                    st.success(f"✅ Cargado: {fields['Reporte firmado'][0]['filename']}")

                # 4. LISTA
                if fields.get('Tipo') == "Actividad en Sucursal":
                    st.markdown("---")
                    st.markdown("#### 4. Lista de Asistencia")
                    uploads['Lista de asistencia'] = st.file_uploader("Cargar Lista", type=['pdf','jpg','png'], key="u_lst")
                    if fields.get('Lista de asistencia'):
                        st.success("✅ Cargada.")

                st.markdown("<br>", unsafe_allow_html=True)
                submitted = st.form_submit_button("💾 GUARDAR CAMBIOS", type="primary", use_container_width=True)

                if submitted:
                    files_to_upload = {k: v for k, v in uploads.items() if v is not None}
                    
                    if not files_to_upload:
                        st.warning("⚠️ Selecciona al menos un archivo.")
                    else:
                        progress = st.progress(0)
                        status = st.empty()
                        try:
                            updates_airtable = {}
                            total = len(files_to_upload)
                            for i, (key, file_obj) in enumerate(files_to_upload.items()):
                                status.text(f"Subiendo {key}...")
                                resp = cloudinary.uploader.upload(file_obj)
                                updates_airtable[key] = [{"url": resp['secure_url']}]
                                progress.progress((i + 1) / (total + 1))
                            
                            status.text("Actualizando Airtable...")
                            success = upload_evidence_to_airtable(
                                st.session_state.current_base_id,
                                st.session_state.current_table_id,
                                evt['id'],
                                updates_airtable
                            )
                            progress.progress(1.0)
                            
                            if success:
                                st.success("✅ ¡Guardado!")
                                st.balloons()
                                log_det = f"Archivos: {list(files_to_upload.keys())} - ID: {evt['id']}"
                                registrar_historial("Carga Fotos", st.session_state.user_name, st.session_state.sucursal_actual, log_det)
                                st.session_state.selected_event['fields'].update(updates_airtable)
                                st.rerun()
                            else:
                                st.error("❌ Error al guardar.")
                        except Exception as e:
                            st.error(f"Error técnico: {str(e)}")
