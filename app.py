import streamlit as st
import requests
import cloudinary
import cloudinary.uploader
import pandas as pd
from datetime import datetime
import os
import json
import unicodedata

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
# La contraseña maestra ahora sirve para crear el primer admin si se borra la DB
MASTER_ADMIN_PASS = "3spejoVenenoso$2099" 

# Configuración Inicial Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_CONFIG["cloud_name"],
    api_key=CLOUDINARY_CONFIG["api_key"],
    api_secret=CLOUDINARY_CONFIG["api_secret"]
)

# --- SUCURSALES (Definición Oficial) ---
SUCURSALES_OFICIALES = [
    "Cordoba", "Orizaba", "Xalapa", "Tehuacan", 
    "Oaxaca", "Tuxtepec", "Boca del Río"
]

FILES_DB = "usuarios.json"
HISTORIAL_FILE = "historial_modificaciones.csv"

# ==============================================================================
# 2. FUNCIONES DE UTILIDAD (TEXTO Y DB)
# ==============================================================================

def normalizar_texto(texto):
    """
    Elimina acentos y convierte a minúsculas para comparaciones robustas.
    Ej: 'Córdoba' -> 'cordoba'
    """
    if not isinstance(texto, str): return str(texto).lower()
    texto = unicodedata.normalize('NFD', texto)
    return ''.join(c for c in texto if unicodedata.category(c) != 'Mn').lower()

def cargar_usuarios():
    """Carga la base de datos de usuarios, o crea el admin por defecto."""
    if not os.path.exists(FILES_DB):
        # Usuario Admin por defecto si no existe el archivo
        default_db = {
            "admin": {
                "password": MASTER_ADMIN_PASS,
                "role": "admin",
                "plazas": SUCURSALES_OFICIALES # Admin tiene todas
            }
        }
        with open(FILES_DB, 'w') as f:
            json.dump(default_db, f)
        return default_db
    
    with open(FILES_DB, 'r') as f:
        return json.load(f)

def guardar_usuarios(db):
    """Guarda los cambios en usuarios.json"""
    with open(FILES_DB, 'w') as f:
        json.dump(db, f)

def registrar_historial(accion, usuario, sucursal, detalles):
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

# ==============================================================================
# 3. FUNCIONES AIRTABLE
# ==============================================================================

@st.cache_data(ttl=600)
def get_bases():
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
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            return {t['name']: t['id'] for t in r.json().get('tables', [])}
    except: pass
    return {}

def get_records(base_id, table_id, year, plaza):
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    
    try:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            st.error(f"Error conectando a Airtable: {r.status_code}")
            return []
        data = r.json().get('records', [])
    except Exception as e:
        st.error(f"Error de conexión: {str(e)}")
        return []

    filtered = []
    # Normalizamos la plaza buscada
    plaza_norm = normalizar_texto(plaza)

    for rec in data:
        fields = rec.get('fields', {})
        
        # FILTRO 1: FECHA
        fecha_dato = fields.get('Fecha')
        match_year = False
        if fecha_dato and str(fecha_dato).startswith(str(year)):
            match_year = True
            
        # FILTRO 2: SUCURSAL (INSENSIBLE A MAYUS/ACENTOS)
        suc_dato = fields.get('Sucursal')
        match_plaza = False
        
        if suc_dato:
            if isinstance(suc_dato, list):
                val_suc = str(suc_dato[0])
            else:
                val_suc = str(suc_dato)
            
            # Comparamos normalizado vs normalizado
            if normalizar_texto(val_suc) == plaza_norm:
                match_plaza = True
        
        if match_year and match_plaza:
            filtered.append(rec)
            
    try:
        filtered.sort(key=lambda x: (x['fields'].get('Fecha',''), x['fields'].get('Hora','')))
    except: pass

    return filtered

def upload_evidence_to_airtable(base_id, table_id, record_id, updates_dict):
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}/{record_id}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}
    data = {"fields": updates_dict}
    r = requests.patch(url, json=data, headers=headers)
    return r.status_code == 200

# ==============================================================================
# 4. GESTIÓN DE SESIÓN
# ==============================================================================
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_role' not in st.session_state: st.session_state.user_role = "user"
if 'user_name' not in st.session_state: st.session_state.user_name = ""
if 'allowed_plazas' not in st.session_state: st.session_state.allowed_plazas = []
if 'sucursal_actual' not in st.session_state: st.session_state.sucursal_actual = ""
if 'selected_event' not in st.session_state: st.session_state.selected_event = None

# ==============================================================================
# 5. PANTALLA DE LOGIN
# ==============================================================================
if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_izq, col_centro, col_der = st.columns([1, 2, 1])
    
    with col_centro:
        st.image("https://www.provident.com.mx/content/dam/provident-mexico/logos/logo-provident.png", width=200)
        st.markdown("### 🔐 Acceso al Sistema")
        
        with st.form("login_form"):
            usuario_input = st.text_input("👤 Usuario:")
            pass_input = st.text_input("🔑 Contraseña:", type="password")
            
            btn_ingresar = st.form_submit_button("Ingresar", use_container_width=True)
            
            if btn_ingresar:
                users_db = cargar_usuarios()
                user_data = users_db.get(usuario_input)

                if user_data and user_data['password'] == pass_input:
                    # Login Exitoso
                    st.session_state.logged_in = True
                    st.session_state.user_role = user_data.get('role', 'user')
                    st.session_state.user_name = usuario_input
                    # Guardamos las plazas permitidas para este usuario
                    st.session_state.allowed_plazas = user_data.get('plazas', [])
                    
                    registrar_historial("Login", usuario_input, "Sistema", "Inicio de sesión exitoso")
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")

# ==============================================================================
# 6. APLICACIÓN PRINCIPAL
# ==============================================================================
else:
    # --- BARRA LATERAL (SIDEBAR) ---
    with st.sidebar:
        st.header(f"Hola, {st.session_state.user_name}")
        st.caption(f"Rol: {st.session_state.user_role.upper()}")
        
        st.divider()
        st.subheader("📅 Configuración de Trabajo")
        
        # 1. Base de Datos
        bases_map = get_bases()
        if not bases_map:
            st.error("Error Airtable.")
            st.stop()
        base_name = st.selectbox("Base de Datos:", list(bases_map.keys()))
        base_id = bases_map[base_name]

        # 2. Tabla (Mes)
        tables_map = get_tables(base_id)
        table_id = None
        if tables_map:
            table_name = st.selectbox("Mes de Trabajo:", list(tables_map.keys()))
            table_id = tables_map[table_name]
        
        # 3. Año
        sel_year = st.number_input("Año:", min_value=2024, max_value=2030, value=2025)

        st.divider()

        # 4. SELECCIÓN DE SUCURSAL (Limitada por permisos)
        # Si el usuario no tiene plazas asignadas, mostrar error
        plazas_permitidas = st.session_state.allowed_plazas
        
        if not plazas_permitidas:
            st.error("No tienes sucursales asignadas. Contacta al Admin.")
            sel_plaza = None
        else:
            sel_plaza = st.selectbox("📍 Selecciona Plaza a gestionar:", plazas_permitidas)
            st.session_state.sucursal_actual = sel_plaza

        # Botón para cargar eventos
        if sel_plaza and st.button("🔄 ACTUALIZAR EVENTOS", type="primary", use_container_width=True):
            st.session_state.selected_event = None
            st.session_state.search_results = get_records(base_id, table_id, sel_year, sel_plaza)
            st.session_state.current_base_id = base_id
            st.session_state.current_table_id = table_id
            st.session_state.current_plaza_view = sel_plaza

        st.divider()
        if st.button("Cerrar Sesión"):
            st.session_state.logged_in = False
            st.rerun()

    # --- ÁREA PRINCIPAL ---
    
    # Definición de pestañas según ROL
    if st.session_state.user_role == "admin":
        tab_main, tab_users, tab_hist = st.tabs(["📂 Gestión de Eventos", "👥 Administrar Usuarios", "📜 Historial Global"])
        
        # Pestaña 2: ADMINISTRAR USUARIOS
        with tab_users:
            st.subheader("Gestión de Accesos")
            users_db = cargar_usuarios()
            
            # Formulario Alta/Edición
            with st.expander("➕ Crear / Editar Usuario", expanded=True):
                with st.form("user_mngt"):
                    c1, c2 = st.columns(2)
                    new_user = c1.text_input("Nombre de Usuario (ID):")
                    new_pass = c2.text_input("Contraseña:", type="password")
                    
                    new_role = st.selectbox("Rol:", ["user", "admin"])
                    
                    # Multiselect con las sucursales oficiales
                    new_plazas = st.multiselect(
                        "Sucursales Permitidas:", 
                        SUCURSALES_OFICIALES,
                        help="Selecciona las plazas que este usuario puede ver y editar."
                    )
                    
                    btn_save_user = st.form_submit_button("Guardar Usuario")
                    
                    if btn_save_user:
                        if new_user and new_pass and new_plazas:
                            users_db[new_user] = {
                                "password": new_pass,
                                "role": new_role,
                                "plazas": new_plazas
                            }
                            guardar_usuarios(users_db)
                            st.success(f"Usuario {new_user} actualizado correctamente.")
                            registrar_historial("Admin User", st.session_state.user_name, "Admin Panel", f"Creó/Editó usuario {new_user}")
                            st.rerun()
                        else:
                            st.error("Todos los campos son obligatorios.")

            # Tabla de Usuarios Existentes
            st.markdown("#### Usuarios Activos")
            user_list = []
            for u, data in users_db.items():
                user_list.append({
                    "Usuario": u,
                    "Rol": data.get('role'),
                    "Plazas": ", ".join(data.get('plazas', []))
                })
            st.dataframe(pd.DataFrame(user_list), use_container_width=True)


        # Pestaña 3: HISTORIAL
        with tab_hist:
            if os.path.exists(HISTORIAL_FILE):
                df_hist = pd.read_csv(HISTORIAL_FILE)
                st.dataframe(df_hist.sort_values(by="Fecha", ascending=False), use_container_width=True)
            else:
                st.info("Sin historial.")
                
        main_area = tab_main

    else:
        # Si es usuario normal, solo ve el área principal
        main_area = st.container()

    # --- LÓGICA DE GESTIÓN DE EVENTOS (Común para todos) ---
    with main_area:
        if 'current_plaza_view' in st.session_state:
            st.title(f"Gestión: {st.session_state.current_plaza_view}")
        else:
            st.title("Gestor de Evidencias")

        # VISTA A: LISTADO
        if st.session_state.selected_event is None:
            if 'search_results' in st.session_state:
                recs = st.session_state.search_results
                if recs:
                    for r in recs:
                        f = r['fields']
                        with st.expander(f"📅 {f.get('Fecha')} | {f.get('Tipo', 'Evento')}"):
                            c1, c2, c3 = st.columns([2, 2, 1])
                            c1.markdown(f"**Hora:** {f.get('Hora', '--')}")
                            c2.markdown(f"**Punto:** {f.get('Punto de reunion', 'N/A')}")
                            if c3.button("📸 SUBIR FOTOS", key=r['id'], use_container_width=True):
                                st.session_state.selected_event = r
                                st.rerun()
                else:
                    if st.session_state.get('sucursal_actual'):
                        st.info(f"No hay eventos encontrados en {st.session_state.sucursal_actual} con los filtros actuales.")
            else:
                st.info("👈 Selecciona Plaza, Mes y pulsa 'ACTUALIZAR EVENTOS'.")

        # VISTA B: CARGA DE EVIDENCIA
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
