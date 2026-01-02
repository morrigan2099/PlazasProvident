import streamlit as st
import requests
import cloudinary
import cloudinary.uploader
import pandas as pd
from datetime import datetime
import os
import json
import unicodedata
import re
from PIL import Image
import io
import base64

# ==============================================================================
# 1. CONFIGURACIÓN Y ESTILOS
# ==============================================================================
st.set_page_config(page_title="Gestor Provident", layout="wide")

st.markdown("""
<style>
    /* --- 1. LOGOTIPO DINÁMICO (LÓGICA INVERTIDA) --- */
    
    /* ESTADO POR DEFECTO (Theme Light / Fondo Blanco) */
    /* Aquí mostramos el lightlogo.png y ocultamos el darklogo.png */
    .logo-light { display: block; }
    .logo-dark { display: none; }

    /* ESTADO MODO OSCURO (Theme Dark / Fondo Negro) */
    /* Aquí invertimos: Ocultamos light, Mostramos dark */
    
    /* Caso 1: Detectado por Sistema Operativo (Móvil) */
    @media (prefers-color-scheme: dark) {
        .logo-light { display: none !important; }
        .logo-dark { display: block !important; }
    }

    /* Caso 2: Detectado por Configuración de Streamlit */
    [data-theme="dark"] .logo-light { display: none !important; }
    [data-theme="dark"] .logo-dark { display: block !important; }


    /* --- 2. RESTO DE ESTILOS (BOTONES, EXPANDERS, ETC) --- */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {}

    /* Expanders Negros */
    .streamlit-expanderHeader { background-color: #000000 !important; color: #ffffff !important; border: 1px solid #333333 !important; border-radius: 8px !important; }
    .streamlit-expanderContent { background-color: #1a1a1a !important; color: #ffffff !important; border: 1px solid #333333 !important; border-top: none !important; }
    .streamlit-expanderHeader p, .streamlit-expanderHeader span, .streamlit-expanderHeader svg,
    .streamlit-expanderContent p, .streamlit-expanderContent span, .streamlit-expanderContent h1, 
    .streamlit-expanderContent h2, .streamlit-expanderContent h3, .streamlit-expanderContent li, .streamlit-expanderContent label { color: #ffffff !important; fill: #ffffff !important; }

    /* Botones */
    .stButton button[kind="primary"] { background-color: #00c853 !important; border: none !important; color: #ffffff !important; font-weight: 700 !important; }
    .stButton button[kind="primary"]:hover { background-color: #009624 !important; }
    .stButton button[kind="primary"] p { color: #ffffff !important; }
    .stButton button[kind="secondary"] { background-color: #dc2626 !important; border: none !important; color: #ffffff !important; font-weight: 600 !important; }
    .stButton button[kind="secondary"]:hover { background-color: #b91c1c !important; }
    .stButton button[kind="secondary"] p { color: #ffffff !important; }
    [data-testid="stExpanderDetails"] [data-testid="column"]:nth-child(2) button { background-color: #00b0ff !important; color: white !important; border: none !important; }
    [data-testid="stExpanderDetails"] [data-testid="column"]:nth-child(2) button:hover { background-color: #0091ea !important; }
    [data-testid="stExpanderDetails"] [data-testid="column"]:nth-child(2) button p { color: white !important; }

    /* Uploader */
    [data-testid="stFileUploader"] small, [data-testid="stFileUploader"] button, [data-testid="stFileUploader"] section > div {display: none;}
    [data-testid="stFileUploader"] section { min-height: 0px !important; padding: 10px !important; background-color: transparent !important; border: 2px dashed #00b0ff !important; border-radius: 12px; display: flex; align-items: center; justify-content: center; cursor: pointer; }
    [data-testid="stFileUploader"] section::after { content: "➕"; font-size: 32px; color: #00b0ff !important; display: block; }

    [data-testid="stSidebar"], [data-testid="collapsedControl"] {display: none;}
    img { max-width: 100%; }
    .caption-text { font-size: 1.1rem !important; font-weight: 700 !important; margin-bottom: 0.5rem; }
</style>
""", unsafe_allow_html=True)

# --- CREDENCIALES ---
CLOUDINARY_CONFIG = {
    "cloud_name": "dlj0pdv6i",
    "api_key": "847419449273122",
    "api_secret": "i0cJCELeYVAosiBL_ltjHkM_FV0"
}
AIRTABLE_TOKEN = "patyclv7hDjtGHB0F.19829008c5dee053cba18720d38c62ed86fa76ff0c87ad1f2d71bfe853ce9783"

# --- ⚠️ CONFIGURACIÓN DE LA BASE MAESTRA ---
ADMIN_BASE_ID = "appRF7jHcmBJZA1px"       # ID Base: Provident Event Photo Uploader
USERS_TABLE_ID = "tblzeDe2WTzmPKxv0"      # ID Tabla: Usuarios
CONFIG_TABLE_ID = "tblB9hhfMAS8HGEjZ"     # ID Tabla: Configuracion

SUCURSALES_OFICIALES = ["Cordoba", "Orizaba", "Xalapa", "Puebla", "Oaxaca", "Tuxtepec", "Boca del Río", "Tehuacan"]
YEAR_ACTUAL = 2025 

cloudinary.config(
    cloud_name=CLOUDINARY_CONFIG["cloud_name"],
    api_key=CLOUDINARY_CONFIG["api_key"],
    api_secret=CLOUDINARY_CONFIG["api_secret"]
)

# ==============================================================================
# 2. FUNCIONES DE UTILIDAD
# ==============================================================================
def limpiar_clave(texto):
    if not isinstance(texto, str): return str(texto).lower()
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]', '', texto.lower())

def formatear_fecha_larga(fecha_str):
    if not fecha_str: return "Fecha pendiente"
    try:
        dt = datetime.strptime(fecha_str, "%Y-%m-%d")
        meses = {1:"Enero", 2:"Febrero", 3:"Marzo", 4:"Abril", 5:"Mayo", 6:"Junio", 7:"Julio", 8:"Agosto", 9:"Septiembre", 10:"Octubre", 11:"Noviembre", 12:"Diciembre"}
        dias = {0:"Lunes", 1:"Martes", 2:"Miércoles", 3:"Jueves", 4:"Viernes", 5:"Sábado", 6:"Domingo"}
        return f"{dias[dt.weekday()]} {dt.day:02d} de {meses[dt.month]} de {dt.year}"
    except: return fecha_str

def obtener_ubicacion_corta(fields):
    opciones = [str(fields.get('Punto de reunion', '')), str(fields.get('Ruta a seguir', '')), str(fields.get('Municipio', ''))]
    validas = [op for op in opciones if op and op.lower() != 'none' and len(op) > 2]
    return min(validas, key=len) if validas else "Ubicación N/A"

def comprimir_imagen_webp(archivo_upload):
    try:
        image = Image.open(archivo_upload)
        if image.mode in ("RGBA", "P"): image = image.convert("RGB")
        max_width = 1920
        if image.width > max_width:
            ratio = max_width / image.width
            image = image.resize((max_width, int(image.height * ratio)), Image.Resampling.LANCZOS)
        buffer_salida = io.BytesIO()
        image.save(buffer_salida, format="WEBP", quality=80, optimize=True)
        buffer_salida.seek(0)
        return buffer_salida
    except: return archivo_upload

# --- LOGO DINÁMICO (BASE64) ---
def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

def render_logo_dinamico(is_banner=False):
    light_path = os.path.join("assets", "lightlogo.png")
    dark_path = os.path.join("assets", "darklogo.png")
    width_css = "width: 100%;" if is_banner else "width: 150px; max-width: 100%;"
    
    if os.path.exists(light_path) and os.path.exists(dark_path):
        b64_light = get_base64_image(light_path)
        b64_dark = get_base64_image(dark_path)
        
        # Inyectamos AMBOS logos, el CSS se encarga de mostrar uno y ocultar el otro
        html = f"""
        <div style="text-align: center;">
            <img src="data:image/png;base64,{b64_light}" class="logo-light" style="{width_css}">
            <img src="data:image/png;base64,{b64_dark}" class="logo-dark" style="{width_css}">
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.markdown("## 🏦 **Provident**")

def get_imagen_plantilla(tipo_evento):
    carpeta_assets = "assets"
    url_default = "https://via.placeholder.com/400x300.png?text=Provident"
    if not tipo_evento: tipo_evento = "default"
    if not os.path.exists(carpeta_assets): return url_default
    clave = limpiar_clave(str(tipo_evento))
    try:
        for f in os.listdir(carpeta_assets):
            if limpiar_clave(os.path.splitext(f)[0]) == clave: return os.path.join(carpeta_assets, f)
        for f in os.listdir(carpeta_assets):
            if "default" in limpiar_clave(f): return os.path.join(carpeta_assets, f)
    except: pass
    return url_default

def normalizar_texto_simple(texto):
    if not isinstance(texto, str): return str(texto).lower()
    texto = unicodedata.normalize('NFD', texto)
    return ''.join(c for c in texto if unicodedata.category(c) != 'Mn').lower()

def check_evidencia_completa(fields):
    claves = ["Foto de equipo", "Foto 01", "Foto 02", "Foto 03", "Foto 04", "Foto 05", "Foto 06", "Foto 07", "Reporte firmado", "Lista de asistencia"]
    for k in claves: 
        if fields.get(k): return True
    return False

# ==============================================================================
# 3. FUNCIONES DE API AIRTABLE (METADATA + DATOS)
# ==============================================================================

def api_get_all_bases():
    url = "https://api.airtable.com/v0/meta/bases"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            return {b['name']: b['id'] for b in r.json().get('bases', [])}
    except: pass
    return {}

def api_get_all_tables(base_id):
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            return {t['name']: t['id'] for t in r.json().get('tables', [])}
    except: pass
    return {}

def cargar_usuarios_airtable():
    url = f"https://api.airtable.com/v0/{ADMIN_BASE_ID}/{USERS_TABLE_ID}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    users_dict = {}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            for rec in r.json().get('records', []):
                f = rec['fields']
                usuario = f.get('Usuario')
                if usuario:
                    plazas_raw = f.get('Plazas', [])
                    plazas = [p.strip() for p in plazas_raw.split(',')] if isinstance(plazas_raw, str) else plazas_raw
                    users_dict[usuario] = {
                        "id_record": rec['id'],
                        "password": f.get('Password', ''),
                        "role": f.get('Role', 'user'),
                        "plazas": plazas
                    }
    except: pass
    return users_dict

def crear_actualizar_usuario_airtable(usuario, password, role, plazas, record_id=None):
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}
    fields = {"Usuario": usuario, "Password": password, "Role": role, "Plazas": plazas}
    if record_id:
        r = requests.patch(f"https://api.airtable.com/v0/{ADMIN_BASE_ID}/{USERS_TABLE_ID}/{record_id}", json={"fields": fields}, headers=headers)
    else:
        r = requests.post(f"https://api.airtable.com/v0/{ADMIN_BASE_ID}/{USERS_TABLE_ID}", json={"fields": fields}, headers=headers)
    return r.status_code == 200

def eliminar_usuario_airtable(record_id):
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    r = requests.delete(f"https://api.airtable.com/v0/{ADMIN_BASE_ID}/{USERS_TABLE_ID}/{record_id}", headers=headers)
    return r.status_code == 200

def cargar_config_airtable():
    url = f"https://api.airtable.com/v0/{ADMIN_BASE_ID}/{CONFIG_TABLE_ID}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    config = {"bases": {}, "tables": {}}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            for rec in r.json().get('records', []):
                f = rec['fields']
                if f.get('Activo'):
                    b_name = f.get('Nombre_Base'); b_id = f.get('ID_Base')
                    t_name = f.get('Nombre_Tabla'); t_id = f.get('ID_Tabla')
                    if b_name and b_id:
                        config["bases"][b_name] = b_id
                        if t_name and t_id:
                            if b_id not in config["tables"]: config["tables"][b_id] = {}
                            config["tables"][b_id][t_name] = t_id
    except: pass
    return config

def guardar_config_airtable(base_name, base_id, table_name, table_id):
    url = f"https://api.airtable.com/v0/{ADMIN_BASE_ID}/{CONFIG_TABLE_ID}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}
    fields = {"Nombre_Base": base_name, "ID_Base": base_id, "Nombre_Tabla": table_name, "ID_Tabla": table_id, "Activo": True}
    requests.post(url, json={"fields": fields}, headers=headers)

def get_records(base_id, table_id, year, plaza):
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code != 200: return []
        data = r.json().get('records', [])
    except: return []
    filtered = []
    plaza_norm = normalizar_texto_simple(plaza)
    for rec in data:
        f = rec.get('fields', {})
        if str(f.get('Fecha','')).startswith(str(year)):
            p_val = f.get('Sucursal')
            p_str = p_val[0] if isinstance(p_val, list) else str(p_val)
            if normalizar_texto_simple(p_str) == plaza_norm: filtered.append(rec)
    filtered.sort(key=lambda x: (x['fields'].get('Fecha',''), x['fields'].get('Hora','')))
    return filtered

def upload_evidence_to_airtable(base_id, table_id, record_id, updates):
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}/{record_id}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}
    r = requests.patch(url, json={"fields": updates}, headers=headers)
    return r.status_code == 200

def create_new_event(base_id, table_id, data):
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}
    r = requests.post(url, json={"fields": data}, headers=headers)
    return r.status_code == 200, r.text

def delete_field_from_airtable(base_id, table_id, record_id, field):
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}/{record_id}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}
    r = requests.patch(url, json={"fields": {field: None}}, headers=headers)
    return r.status_code == 200

def registrar_historial(accion, usuario, sucursal, detalles):
    pass 

# ==============================================================================
# 4. GESTIÓN DE SESIÓN
# ==============================================================================
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_role' not in st.session_state: st.session_state.user_role = "user"
if 'user_name' not in st.session_state: st.session_state.user_name = ""
if 'allowed_plazas' not in st.session_state: st.session_state.allowed_plazas = []
if 'sucursal_actual' not in st.session_state: st.session_state.sucursal_actual = ""
if 'selected_event' not in st.session_state: st.session_state.selected_event = None
if 'rescheduling_event' not in st.session_state: st.session_state.rescheduling_event = None

# ==============================================================================
# 5. PANTALLA DE LOGIN
# ==============================================================================
if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c_izq, c_centro, c_der = st.columns([1, 2, 1])
    with c_centro:
        render_logo_dinamico(is_banner=True)
        st.markdown("<h3 style='text-align: center;'>🔐 Acceso al Sistema</h3>", unsafe_allow_html=True)
        with st.form("login_form"):
            usuario_input = st.text_input("👤 Usuario:")
            pass_input = st.text_input("🔑 Contraseña:", type="password")
            if st.form_submit_button("INGRESAR", use_container_width=True, type="primary"):
                users_db = cargar_usuarios_airtable()
                user_data = users_db.get(usuario_input)
                if user_data and user_data['password'] == pass_input:
                    st.session_state.logged_in = True
                    st.session_state.user_role = user_data.get('role', 'user')
                    st.session_state.user_name = usuario_input
                    st.session_state.allowed_plazas = user_data.get('plazas', [])
                    registrar_historial("Login", usuario_input, "Sistema", "Inicio de sesión exitoso")
                    st.rerun()
                else: st.error("Credenciales incorrectas.")

# ==============================================================================
# 6. APP PRINCIPAL
# ==============================================================================
else:
    # Header
    render_logo_dinamico(is_banner=True)
    st.markdown("<br>", unsafe_allow_html=True)
    c_user, c_fill, c_logout = st.columns([3, 4, 1])
    with c_user: st.markdown(f"#### 👤 {st.session_state.user_name} | {st.session_state.user_role.upper()}")
    with c_logout: 
        if st.button("SALIR", use_container_width=True, type="secondary"): st.session_state.logged_in=False; st.rerun()
    st.divider()

    # Topbar
    with st.container():
        col_base, col_mes, col_plaza = st.columns(3)
        config_db = cargar_config_airtable()
        bases_map = config_db.get("bases", {})
        with col_base:
            if not bases_map: st.warning("⚠️ Sin bases configuradas"); base_id = None
            else: base_name = st.selectbox("📂 Base de Datos", list(bases_map.keys())); base_id = bases_map[base_name]
        with col_mes:
            if base_id:
                tables_map = config_db.get("tables", {}).get(base_id, {})
                if tables_map: table_name = st.selectbox("📅 Mes", list(tables_map.keys())); table_id = tables_map[table_name]
                else: table_id = None
            else: st.selectbox("📅 Mes", [], disabled=True); table_id = None
        with col_plaza:
            plazas_permitidas = st.session_state.allowed_plazas
            sel_plaza = st.selectbox("📍 Plaza", plazas_permitidas) if plazas_permitidas else None
            if sel_plaza: st.session_state.sucursal_actual = sel_plaza

    # Auto-Carga
    if base_id and table_id and sel_plaza:
        if (base_id != st.session_state.get('current_base_id') or 
            table_id != st.session_state.get('current_table_id') or 
            sel_plaza != st.session_state.get('current_plaza_view') or 'search_results' not in st.session_state):
            with st.spinner("🔄 Cargando..."):
                st.session_state.selected_event = None; st.session_state.rescheduling_event = None
                st.session_state.search_results = get_records(base_id, table_id, YEAR_ACTUAL, sel_plaza)
                st.session_state.current_base_id = base_id; st.session_state.current_table_id = table_id; st.session_state.current_plaza_view = sel_plaza

    st.divider()

    # ADMIN
    if st.session_state.user_role == "admin":
        tab_main, tab_users, tab_config_db = st.tabs(["📂 Eventos", "👥 Usuarios (DB)", "⚙️ Config DB"])
        
        with tab_users:
            st.subheader("Gestión de Usuarios (En Base Maestra)")
            users_db = cargar_usuarios_airtable()
            opciones = ["(Crear Nuevo)"] + list(users_db.keys()); seleccion = st.selectbox("Editar:", opciones)
            if seleccion == "(Crear Nuevo)": u_val=""; p_val=""; r_val="user"; pl_val=[]; rec_id=None
            else: d = users_db[seleccion]; u_val=seleccion; p_val=d['password']; r_val=d['role']; pl_val=d['plazas']; rec_id=d['id_record']
            with st.form("user_form"):
                c1, c2 = st.columns(2); nu = c1.text_input("Usuario", value=u_val); np = c2.text_input("Password", value=p_val)
                nr = st.selectbox("Rol", ["user", "admin"], index=0 if r_val=="user" else 1); npl = st.multiselect("Plazas", SUCURSALES_OFICIALES, default=[x for x in pl_val if x in SUCURSALES_OFICIALES])
                if st.form_submit_button("💾 Guardar en DB", type="primary"):
                    if crear_actualizar_usuario_airtable(nu, np, nr, npl, rec_id): st.success("✅ Guardado"); st.rerun()
                    else: st.error("Error al guardar")
            if rec_id and st.button("🗑️ Eliminar Usuario", type="secondary"): eliminar_usuario_airtable(rec_id); st.warning("Eliminado"); st.rerun()

        with tab_config_db:
            st.subheader("Agregar Configuración de Visibilidad")
            st.info("El sistema consultará tus Bases reales en Airtable.")
            with st.spinner("Obteniendo Bases de Airtable..."):
                real_bases = api_get_all_bases()
            if not real_bases: st.error("No se pudieron obtener bases. Revisa tu Token.")
            else:
                selected_base_name = st.selectbox("Selecciona la Base:", list(real_bases.keys()))
                selected_base_id = real_bases[selected_base_name]
                with st.spinner(f"Obteniendo tablas de {selected_base_name}..."):
                    real_tables = api_get_all_tables(selected_base_id)
                if not real_tables: st.warning("Esta base no tiene tablas o no se pudieron leer.")
                else:
                    st.markdown(f"**Tablas disponibles en {selected_base_name}:**")
                    selected_tables_names = st.multiselect("Selecciona las tablas (Meses) a habilitar:", list(real_tables.keys()))
                    if st.button("💾 GUARDAR CONFIGURACIÓN", type="primary"):
                        if selected_tables_names:
                            count = 0; progress_text = st.empty()
                            for t_name in selected_tables_names:
                                t_id = real_tables[t_name]
                                guardar_config_airtable(selected_base_name, selected_base_id, t_name, t_id)
                                count += 1
                                progress_text.text(f"Guardando {t_name}...")
                            st.success(f"✅ Se agregaron {count} tablas a la configuración exitosamente."); st.rerun()
                        else: st.warning("Selecciona al menos una tabla.")
            st.divider(); st.markdown("#### Configuración Actual Guardada:"); st.json(cargar_config_airtable())

        main_area = tab_main
    else: main_area = st.container()

    # VISTAS PRINCIPALES
    with main_area:
        if 'current_plaza_view' in st.session_state: st.markdown(f"### 📋 Eventos en {st.session_state.current_plaza_view}")

        # 1. LISTADO
        if st.session_state.selected_event is None and st.session_state.rescheduling_event is None:
            if 'search_results' in st.session_state:
                recs = st.session_state.search_results
                if recs:
                    for r in recs:
                        f = r['fields']; ya_tiene = check_evidencia_completa(f)
                        with st.expander(f"{f.get('Fecha')} | {f.get('Tipo')}", expanded=True):
                            c1, c2 = st.columns([1, 2.5]); c1.image(get_imagen_plantilla(f.get('Tipo')), use_container_width=True)
                            c2.markdown(f"**📍 {obtener_ubicacion_corta(f)}**\n\n{formatear_fecha_larga(f.get('Fecha'))} | {f.get('Hora')}")
                            cb1, cb2 = st.columns(2)
                            if cb1.button("📸 SUBIR EVIDENCIA", key=f"b_{r['id']}", type="primary", use_container_width=True): st.session_state.selected_event=r; st.rerun()
                            if not ya_tiene:
                                if cb2.button("⚠️ EVENTO REAGENDADO", key=f"r_{r['id']}", use_container_width=True): st.session_state.rescheduling_event=r; st.rerun()
                else: st.info("No hay eventos.")
            else: st.info("Selecciona base y mes.")

        # 2. REAGENDAR
        elif st.session_state.rescheduling_event:
            evt = st.session_state.rescheduling_event; f=evt['fields']
            if st.button("⬅️ CANCELAR", type="secondary", use_container_width=True): st.session_state.rescheduling_event=None; st.rerun()
            st.markdown("### ⚠️ Reagendar Evento")
            with st.form("reschedule"):
                c1,c2,c3 = st.columns(3)
                try: fd=datetime.strptime(f.get('Fecha'),"%Y-%m-%d")
                except: fd=datetime.now()
                nf=c1.date_input("Nueva Fecha", value=fd); nh=c2.text_input("Hora", f.get('Hora')); nm=c3.text_input("Municipio", f.get('Municipio'))
                nt=c1.text_input("Tipo", f.get('Tipo')); ns=c2.text_input("Sección", f.get('Seccion')); np=c3.text_input("Punto", f.get('Punto de reunion'))
                nr=c1.text_input("Ruta", f.get('Ruta a seguir')); nam=c2.text_input("AM", f.get('AM Responsable')); ndm=c3.text_input("DM", f.get('DM Responsable'))
                ntam=c1.text_input("Tel AM", f.get('Teléfono AM')); ntdm=c2.text_input("Tel DM", f.get('Teléfono DM')); nc=c3.text_input("Cantidad", f.get('Cantidad'))
                if st.form_submit_button("💾 GUARDAR CAMBIOS", type="primary", use_container_width=True):
                    new_reg = {"Fecha":nf.strftime("%Y-%m-%d"),"Hora":nh,"Tipo":nt,"Sucursal":f.get('Sucursal'),"Seccion":ns,"Ruta a seguir":nr,"Punto de reunion":np,"Municipio":f"{nm} (Evento Reagendado)","Cantidad":nc,"AM Responsable":nam,"Teléfono AM":ntam,"DM Responsable":ndm,"Teléfono DM":ntdm}
                    if create_new_event(st.session_state.current_base_id, st.session_state.current_table_id, new_reg)[0]: st.success("Reagendado."); st.session_state.rescheduling_event=None; st.session_state.search_results=get_records(st.session_state.current_base_id, st.session_state.current_table_id, YEAR_ACTUAL, st.session_state.current_plaza_view); st.rerun()
                    else: st.error("Error al crear")

        # 3. CARGA (AUTO-UPLOAD)
        else:
            evt = st.session_state.selected_event; f=evt['fields']
            if st.button("⬅️ REGRESAR", type="secondary", use_container_width=True): st.session_state.selected_event=None; st.rerun()
            st.divider(); st.markdown(f"### 📸 {f.get('Tipo')} - {obtener_ubicacion_corta(f)}"); st.divider()
            
            def render_cell(col, k, label):
                with col:
                    st.markdown(f'<p class="caption-text">{label}</p>', unsafe_allow_html=True)
                    if f.get(k):
                        st.image(f[k][0]['url'], use_container_width=True)
                        if st.button("🗑️ Eliminar", key=f"d_{k}", type="secondary", use_container_width=True):
                            delete_field_from_airtable(st.session_state.current_base_id, st.session_state.current_table_id, evt['id'], k)
                            del st.session_state.selected_event['fields'][k]; st.rerun()
                    else:
                        up = st.file_uploader(k, key=f"u_{k}", type=['jpg','png','jpeg'], label_visibility="collapsed")
                        if up:
                            img_ok = comprimir_imagen_webp(up)
                            with st.spinner("Subiendo..."):
                                res = cloudinary.uploader.upload(img_ok, format="webp", resource_type="image")
                                upload_evidence_to_airtable(st.session_state.current_base_id, st.session_state.current_table_id, evt['id'], {k:[{"url":res['secure_url']}]})
                                st.session_state.selected_event['fields'][k] = [{"url":res['secure_url']}]; st.rerun()

            st.markdown("#### 1. Foto Inicio"); c1,c2 = st.columns(2); render_cell(c1, "Foto de equipo", "Foto Equipo")
            st.markdown("#### 2. Actividad"); keys=["Foto 01","Foto 02","Foto 03","Foto 04","Foto 05","Foto 06","Foto 07"]
            for i in range(0,len(keys),2):
                cr=st.columns(2); render_cell(cr[0], keys[i], keys[i])
                if i+1<len(keys): render_cell(cr[1], keys[i+1], keys[i+1])
            
            t3 = "3. Reporte y Lista" if f.get('Tipo') == "Actividad en Sucursal" else "3. Reporte Firmado"
            st.markdown(f"#### {t3}"); cr3=st.columns(2); render_cell(cr3[0], "Reporte firmado", "Reporte")
            if f.get('Tipo') == "Actividad en Sucursal": render_cell(cr3[1], "Lista de asistencia", "Lista")
            
            st.divider(); 
            if st.button("⬅️ REGRESAR (FINAL)", type="secondary", use_container_width=True): st.session_state.selected_event=None; st.rerun()
