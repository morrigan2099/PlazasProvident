import streamlit as st
import requests
import cloudinary
import cloudinary.uploader
import pandas as pd
from datetime import datetime
import os
import json
import time
import unicodedata
import re
from PIL import Image
import io
import base64
import pytz

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

    /* ESTILOS GENERALES */
    .streamlit-expanderHeader { background-color: #000000 !important; color: #ffffff !important; border: 1px solid #333333 !important; border-radius: 8px !important; }
    .streamlit-expanderContent { background-color: #1a1a1a !important; color: #ffffff !important; border: 1px solid #333333 !important; border-top: none !important; }
    .streamlit-expanderHeader p, .streamlit-expanderHeader span, .streamlit-expanderContent p, .streamlit-expanderContent span, .streamlit-expanderContent div { color: #ffffff !important; }
    
    .stButton button[kind="primary"] { background-color: #00c853 !important; border: none !important; color: #ffffff !important; font-weight: 700 !important; }
    .stButton button[kind="primary"]:hover { background-color: #009624 !important; }
    .stButton button[kind="primary"] p { color: #ffffff !important; }
    .stButton button[kind="secondary"] { background-color: #dc2626 !important; border: none !important; color: #ffffff !important; font-weight: 600 !important; }
    
    /* --- ESTILO UPLOADER MINIMALISTA (SOLO + CELESTE) --- */
    [data-testid="stFileUploader"] section { 
        min-height: 0px !important; 
        padding: 15px !important; 
        border: 2px dashed #40E0D0 !important; /* Borde Celeste */
        background-color: rgba(64, 224, 208, 0.05) !important; 
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    /* Ocultar TODO el contenido interno por defecto (Botón Browse, textos, limites) */
    [data-testid="stFileUploader"] section > div {
        display: none !important;
    }
    [data-testid="stFileUploader"] section button {
        display: none !important;
    }
    [data-testid="stFileUploader"] section span, 
    [data-testid="stFileUploader"] section small, 
    [data-testid="stFileUploader"] section p {
        display: none !important;
    }

    /* Agregar ÚNICAMENTE el emoji (+) */
    [data-testid="stFileUploader"] section::after { 
        content: "➕"; 
        font-size: 28px; 
        color: #40E0D0 !important; /* Celeste */
        display: block; 
        visibility: visible !important;
    }

    [data-testid="stSidebar"], [data-testid="collapsedControl"] {display: none;}
    .compact-md p { margin-bottom: 0px !important; line-height: 1.4 !important; }
</style>
""", unsafe_allow_html=True)

# --- CREDENCIALES ---
CLOUDINARY_CONFIG = {
    "cloud_name": "dlj0pdv6i",
    "api_key": "847419449273122",
    "api_secret": "i0cJCELeYVAosiBL_ltjHkM_FV0"
}
AIRTABLE_TOKEN = "patyclv7hDjtGHB0F.19829008c5dee053cba18720d38c62ed86fa76ff0c87ad1f2d71bfe853ce9783"

# --- 🔔 TELEGRAM CONFIG ---
TELEGRAM_TOKEN = "8282197056:AAGMNd3kSJThY2_RN-Umk9fAlJ3a2NECpcE"
TELEGRAM_CHAT_ID = "1858285363"

# --- CONFIGURACIÓN BASE MAESTRA ---
ADMIN_BASE_ID = "appRF7jHcmBJZA1px"
USERS_TABLE_ID = "tblzeDe2WTzmPKxv0"
CONFIG_TABLE_ID = "tblB9hhfMAS8HGEjZ"
BACKUP_TABLE_ID = "tbl50k9wNeMvr4Vbd" 
HISTORY_TABLE_ID = "tblmy6hL3VXQM5883"

SUCURSALES_OFICIALES = ["Cordoba", "Orizaba", "Xalapa", "Puebla", "Oaxaca", "Tuxtepec", "Boca del Río", "Tehuacan"]

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
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in texto if unicodedata.category(c) != 'Mn').lower())

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

def get_base64_image(image_path):
    with open(image_path, "rb") as img_file: return base64.b64encode(img_file.read()).decode()

def render_logo_dinamico(is_banner=False):
    light_path, dark_path = os.path.join("assets", "lightlogo.png"), os.path.join("assets", "darklogo.png")
    width_css = "width: 100%;" if is_banner else "width: 150px; max-width: 100%;"
    if os.path.exists(light_path) and os.path.exists(dark_path):
        b64_light, b64_dark = get_base64_image(light_path), get_base64_image(dark_path)
        st.markdown(f"""<div style="text-align: center;"><img src="data:image/png;base64,{b64_light}" class="logo-light" style="{width_css}"><img src="data:image/png;base64,{b64_dark}" class="logo-dark" style="{width_css}"></div>""", unsafe_allow_html=True)
    else: st.markdown("## 🏦 **Provident**")

def get_imagen_plantilla(tipo_evento):
    carpeta_assets, url_default, clave = "assets", "https://via.placeholder.com/400x300.png?text=Provident", limpiar_clave(str(tipo_evento))
    if not os.path.exists(carpeta_assets): return url_default
    try:
        for f in os.listdir(carpeta_assets):
            if limpiar_clave(os.path.splitext(f)[0]) == clave: return os.path.join(carpeta_assets, f)
        for f in os.listdir(carpeta_assets):
            if "default" in limpiar_clave(f): return os.path.join(carpeta_assets, f)
    except: pass
    return url_default

def normalizar_texto_simple(texto):
    if not isinstance(texto, str): return str(texto).lower()
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def check_evidencia_completa(fields):
    for k in ["Foto de equipo", "Foto 01", "Foto 02", "Foto 03", "Foto 04", "Foto 05", "Foto 06", "Foto 07", "Reporte firmado", "Lista de asistencia"]:
        if fields.get(k): return True
    return False

# ==============================================================================
# 3. FUNCIONES AIRTABLE
# ==============================================================================
def airtable_request(method, url, data=None, params=None):
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}
    try:
        if method == "GET": r = requests.get(url, headers=headers, params=params)
        elif method == "POST": r = requests.post(url, json=data, headers=headers)
        elif method == "PATCH": r = requests.patch(url, json=data, headers=headers)
        elif method == "DELETE": r = requests.delete(url, headers=headers)
        
        if r.status_code not in [200, 201, 202]:
            st.error(f"⚠️ ERROR AIRTABLE ({r.status_code}): {r.text}")
        return r
    except Exception as e:
        st.error(f"❌ Error de Conexión Python: {str(e)}")
        return None

# --- TELEGRAM ALERT ---
def enviar_alerta_telegram(mensaje):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
        requests.post(url, json=payload)
    except: pass

# --- AUDITORÍA / LOGS (CON ZONA HORARIA MX) ---
def registrar_historial(accion, detalles):
    if "tbl" not in HISTORY_TABLE_ID: return 
    url = f"https://api.airtable.com/v0/{ADMIN_BASE_ID}/{HISTORY_TABLE_ID}"
    usuario = st.session_state.get('user_name', 'Sistema')
    rol = st.session_state.get('user_role', '--')
    sucursal = st.session_state.get('sucursal_actual', 'N/A')
    
    try:
        mx_zone = pytz.timezone('America/Mexico_City')
        fecha = datetime.now(mx_zone).strftime("%Y-%m-%d %H:%M:%S")
    except:
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    data = {"fields": {"Fecha": fecha, "Usuario": usuario, "Rol": rol, "Sucursal": sucursal, "Accion": accion, "Detalles": detalles}}
    res = requests.post(url, json=data, headers={"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"})

def get_full_history():
    r = airtable_request("GET", f"https://api.airtable.com/v0/{ADMIN_BASE_ID}/{HISTORY_TABLE_ID}?sort%5B0%5D%5Bfield%5D=Fecha&sort%5B0%5D%5Bdirection%5D=desc")
    return [rec['fields'] for rec in r.json().get('records', [])] if r and r.status_code==200 else []

# --- FUNCIONES DE DATOS ---
def api_get_all_bases():
    r = airtable_request("GET", "https://api.airtable.com/v0/meta/bases")
    return {b['name']: b['id'] for b in r.json().get('bases', [])} if r and r.status_code==200 else {}

def api_get_all_tables(base_id):
    r = airtable_request("GET", f"https://api.airtable.com/v0/meta/bases/{base_id}/tables")
    return {t['name']: t['id'] for t in r.json().get('tables', [])} if r and r.status_code==200 else {}

def get_records(base_id, table_id, plaza):
    r = airtable_request("GET", f"https://api.airtable.com/v0/{base_id}/{table_id}")
    if not r or r.status_code != 200: return []
    filtered = []; plaza_norm = normalizar_texto_simple(plaza)
    for rec in r.json().get('records', []):
        f = rec.get('fields', {})
        p_val = f.get('Sucursal')
        p_str = p_val[0] if isinstance(p_val, list) else str(p_val)
        if normalizar_texto_simple(p_str) == plaza_norm: filtered.append(rec)
    filtered.sort(key=lambda x: (x['fields'].get('Fecha',''), x['fields'].get('Hora','')))
    return filtered

def get_all_pending_requests():
    config = cargar_config_airtable()
    pending_list = []
    for base_name, base_id in config['bases'].items():
        tables = config['tables'].get(base_id, {})
        for table_name, table_id in tables.items():
            params = {"filterByFormula": "{Estado_Bloqueo}='Solicitado'"}
            r = airtable_request("GET", f"https://api.airtable.com/v0/{base_id}/{table_id}", params=params)
            if r and r.status_code == 200:
                for rec in r.json().get('records', []):
                    rec['metadata'] = {"base_id": base_id, "table_id": table_id, "base_name": base_name, "table_name": table_name}
                    pending_list.append(rec)
    return pending_list

# --- LÓGICA DE RESPALDO BLINDADA ---
def crear_respaldo_evento(fields_original):
    campos_copiar = ["Tipo", "Fecha", "Hora", "Sucursal", "Seccion", "Ruta a seguir", "Punto de reunion", "Municipio", "Cantidad", "AM Responsable", "DM Responsable", "Teléfono AM", "Teléfono DM", "Foto de equipo", "Foto 01", "Foto 02", "Foto 03", "Foto 04", "Foto 05", "Foto 06", "Foto 07", "Reporte firmado", "Lista de asistencia"]
    new_data = {}
    for k in campos_copiar:
        val = fields_original.get(k)
        if val not in [None, "", []]:
            is_attachment = False
            if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict) and 'url' in val[0]: is_attachment = True
            if is_attachment: new_data[k] = [{'url': img['url']} for img in val]
            else:
                if isinstance(val, list): new_data[k] = ", ".join(str(x) for x in val)
                else: new_data[k] = str(val)
    url = f"https://api.airtable.com/v0/{ADMIN_BASE_ID}/{BACKUP_TABLE_ID}"
    return airtable_request("POST", url, {"fields": new_data})

def solicitar_desbloqueo(base_id, table_id, record_id, campos):
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}/{record_id}"
    resp = airtable_request("PATCH", url, {"fields": {"Estado_Bloqueo": "Solicitado"}})
    if resp and resp.status_code == 200: 
        registrar_historial("Solicitud Permiso", f"Record ID: {record_id} ({campos.get('Tipo')})")
        msg = f"🔔 *SOLICITUD DE DESBLOQUEO*\n\n👤 *Usuario:* {st.session_state.user_name}\n📍 *Sucursal:* {campos.get('Sucursal')}\n📅 *Fecha:* {campos.get('Fecha')}\n📌 *Evento:* {campos.get('Tipo')}"
        enviar_alerta_telegram(msg)
    return resp

def aprobar_desbloqueo_admin(base_id, table_id, record_full_data):
    resp_backup = crear_respaldo_evento(record_full_data['fields'])
    if resp_backup and resp_backup.status_code == 200:
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}/{record_full_data['id']}"
        resp_update = airtable_request("PATCH", url, {"fields": {"Estado_Bloqueo": "Desbloqueado"}})
        if resp_update and resp_update.status_code == 200:
            registrar_historial("Aprobación Permiso", f"Admin aprobó desbloqueo para ID: {record_full_data['id']}")
            return True, "Éxito"
        else: return False, f"Respaldo OK, fallo desbloqueo."
    else: return False, "Fallo al crear respaldo."

# --- GESTIÓN USUARIOS Y CONFIG ---
def cargar_usuarios_airtable():
    r = airtable_request("GET", f"https://api.airtable.com/v0/{ADMIN_BASE_ID}/{USERS_TABLE_ID}")
    users = {}
    if r and r.status_code==200:
        for rec in r.json().get('records', []):
            f = rec['fields']; u = f.get('Usuario')
            if u: 
                pl = f.get('Plazas',[])
                if isinstance(pl,str): pl = [x.strip() for x in pl.split(',')]
                users[u] = {"id": rec['id'], "password": f.get('Password'), "role": f.get('Role','user'), "plazas": pl}
    return users

def crear_actualizar_usuario_airtable(u, p, r, pl, rid=None):
    data = {"fields": {"Usuario": u, "Password": p, "Role": r, "Plazas": pl}}
    if rid: 
        res = airtable_request("PATCH", f"https://api.airtable.com/v0/{ADMIN_BASE_ID}/{USERS_TABLE_ID}/{rid}", data)
        if res.status_code==200: registrar_historial("Modificar Usuario", f"Usuario: {u}"); return True
    else: 
        res = airtable_request("POST", f"https://api.airtable.com/v0/{ADMIN_BASE_ID}/{USERS_TABLE_ID}", data)
        if res.status_code==200: registrar_historial("Crear Usuario", f"Usuario: {u}"); return True
    return False

def eliminar_usuario_airtable(rid):
    res = airtable_request("DELETE", f"https://api.airtable.com/v0/{ADMIN_BASE_ID}/{USERS_TABLE_ID}/{rid}")
    if res.status_code==200: registrar_historial("Eliminar Usuario", f"ID: {rid}")
    return res.status_code==200

def cargar_config_airtable():
    r = airtable_request("GET", f"https://api.airtable.com/v0/{ADMIN_BASE_ID}/{CONFIG_TABLE_ID}")
    conf = {"bases":{}, "tables":{}}
    if r and r.status_code==200:
        for rec in r.json().get('records', []):
            f=rec['fields']
            if f.get('Activo'):
                bid=f.get('ID_Base'); tid=f.get('ID_Tabla')
                if bid and tid:
                    conf['bases'][f.get('Nombre_Base')]=bid
                    if bid not in conf['tables']: conf['tables'][bid]={}
                    conf['tables'][bid][f.get('Nombre_Tabla')]=tid
    return conf

def guardar_config_airtable(bn, bid, tn, tid):
    data = {"fields": {"Nombre_Base":bn, "ID_Base":bid, "Nombre_Tabla":tn, "ID_Tabla":tid, "Activo":True}}
    res = airtable_request("POST", f"https://api.airtable.com/v0/{ADMIN_BASE_ID}/{CONFIG_TABLE_ID}", data)
    if res.status_code==200: registrar_historial("Configuración", f"Agregada tabla: {tn}")

def create_new_event(base_id, table_id, data):
    r = airtable_request("POST", f"https://api.airtable.com/v0/{base_id}/{table_id}", {"fields": data})
    if r.status_code == 200: registrar_historial("Reagendar Evento", f"Nuevo evento en {data.get('Municipio')}")
    return r.status_code == 200, r.text if r else "Error"

def upload_evidence_to_airtable(base_id, table_id, record_id, updates):
    r = airtable_request("PATCH", f"https://api.airtable.com/v0/{base_id}/{table_id}/{record_id}", {"fields": updates})
    if r.status_code == 200: registrar_historial("Subir/Editar Evidencia", f"Campos: {list(updates.keys())} en ID {record_id}")
    return r.status_code == 200 if r else False

def delete_field_from_airtable(base_id, table_id, record_id, field):
    r = airtable_request("PATCH", f"https://api.airtable.com/v0/{base_id}/{table_id}/{record_id}", {"fields": {field: None}})
    if r.status_code == 200: 
        registrar_historial("Eliminación Evidencia", f"Se eliminó el archivo del campo: {field}")
    return r.status_code == 200 if r else False

# ==============================================================================
# 4. SESIÓN
# ==============================================================================
if 'logged_in' not in st.session_state: st.session_state.logged_in=False
if 'user_role' not in st.session_state: st.session_state.user_role="user"
if 'user_name' not in st.session_state: st.session_state.user_name=""
if 'allowed_plazas' not in st.session_state: st.session_state.allowed_plazas=[]
if 'sucursal_actual' not in st.session_state: st.session_state.sucursal_actual=""
if 'selected_event' not in st.session_state: st.session_state.selected_event=None
if 'rescheduling_event' not in st.session_state: st.session_state.rescheduling_event=None
if 'history_data_view' not in st.session_state: st.session_state.history_data_view = []

# ==============================================================================
# 5. LOGIN
# ==============================================================================
if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        render_logo_dinamico(True)
        st.markdown("<h3 style='text-align:center'>🔐 Acceso al Sistema</h3>", unsafe_allow_html=True)
        with st.form("log"):
            u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INGRESAR", use_container_width=True, type="primary"):
                udb = cargar_usuarios_airtable(); user = udb.get(u)
                if user and user['password'] == p:
                    st.session_state.logged_in=True; st.session_state.user_role=user['role']
                    st.session_state.user_name=u; st.session_state.allowed_plazas=user['plazas']
                    registrar_historial("Login", "Inicio de sesión exitoso")
                    st.rerun()
                else: 
                    registrar_historial("Login Fallido", f"Intento fallido usuario: {u}")
                    st.error("Datos incorrectos")

# ==============================================================================
# 6. APP PRINCIPAL
# ==============================================================================
else:
    render_logo_dinamico(True); st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([3,4,1])
    with c1: st.markdown(f"#### 👤 {st.session_state.user_name} | {st.session_state.user_role.upper()}")
    with c3: 
        if st.button("SALIR", use_container_width=True, type="secondary"): 
            registrar_historial("Logout", "Cierre de sesión")
            st.session_state.logged_in=False; st.rerun()
    st.divider()

    # TOPBAR
    with st.container():
        c1, c2, c3 = st.columns(3); conf = cargar_config_airtable()
        with c1:
            bn = st.selectbox("📂 Base", list(conf['bases'].keys())) if conf['bases'] else None
            bid = conf['bases'][bn] if bn else None
        with c2:
            tn = st.selectbox("📅 Mes", list(conf['tables'].get(bid, {}).keys())) if bid else None
            tid = conf['tables'][bid][tn] if tn else None
        with c3:
            spl = st.selectbox("📍 Plaza", st.session_state.allowed_plazas) if st.session_state.allowed_plazas else None
            if spl: st.session_state.sucursal_actual = spl

    if bid and tid and spl:
        if (bid!=st.session_state.get('current_base_id') or tid!=st.session_state.get('current_table_id') or spl!=st.session_state.get('current_plaza_view') or 'search_results' not in st.session_state):
            with st.spinner("🔄 Cargando..."):
                st.session_state.selected_event=None; st.session_state.rescheduling_event=None
                st.session_state.search_results=get_records(bid, tid, spl)
                st.session_state.current_base_id=bid; st.session_state.current_table_id=tid; st.session_state.current_plaza_view=spl

    st.divider()

    # ADMIN PANEL
    if st.session_state.user_role == "admin":
        all_pending = get_all_pending_requests()
        count_pending = len(all_pending)
        label_solicitudes = f"🔐 Solicitudes ({count_pending}) 🔴" if count_pending > 0 else "🔐 Solicitudes"
        if count_pending > 0:
            st.toast(f"🔔 ¡ATENCIÓN! HAY {count_pending} SOLICITUDES DE PERMISO", icon="🚨")
            st.markdown("""<audio autoplay><source src="https://upload.wikimedia.org/wikipedia/commons/0/05/Beep-09.ogg" type="audio/ogg"></audio>""", unsafe_allow_html=True)

        tm, tu, tc, ta, th = st.tabs(["📂 Eventos", "👥 Usuarios", "⚙️ Config", label_solicitudes, "📜 Historial"])
        
        with tu:
            st.subheader("Gestión Usuarios"); udb = cargar_usuarios_airtable()
            sel = st.selectbox("Editar", ["(Nuevo)"]+list(udb.keys()))
            if sel=="(Nuevo)": d={"password":"", "role":"user", "plazas":[]}; rid=None
            else: d=udb[sel]; rid=d['id']
            with st.form("uf"):
                cu, cp = st.columns(2); nu=cu.text_input("User", sel if sel!="(Nuevo)" else ""); np=cp.text_input("Pass", d['password'])
                nr=st.selectbox("Rol",["user","admin"],0 if d['role']=="user" else 1)
                
                defaults_validos = [x for x in d['plazas'] if x in SUCURSALES_OFICIALES]
                npl=st.multiselect("Plazas", SUCURSALES_OFICIALES, defaults_validos)
                
                if st.form_submit_button("Guardar", type="primary"):
                    crear_actualizar_usuario_airtable(nu,np,nr,npl,rid); st.success("OK"); st.rerun()
            if rid and st.button("Eliminar", type="secondary"): eliminar_usuario_airtable(rid); st.rerun()
        
        with tc:
            st.subheader("Agregar Config"); 
            with st.spinner("Buscando Bases..."): real_bases = api_get_all_bases()
            if not real_bases: st.error("Error al buscar bases.")
            else:
                sb_n = st.selectbox("Base Real", list(real_bases.keys())); sb_id = real_bases[sb_n]
                with st.spinner("Tablas..."): real_tables = api_get_all_tables(sb_id)
                sts = st.multiselect("Tablas a habilitar", list(real_tables.keys()))
                if st.button("Guardar Config", type="primary"):
                    if sts:
                        for t in sts: guardar_config_airtable(sb_n, sb_id, t, real_tables[t])
                        st.success("OK"); st.rerun()
            st.json(conf)

        with ta:
            st.subheader("🔐 Todas las Solicitudes Pendientes (Global)")
            
            monitor_activo = st.checkbox("🔄 Activar Monitor en Vivo (Sonido activado)", value=False)
            if monitor_activo:
                time.sleep(5); st.rerun()
            
            if not all_pending: st.info("✅ No hay solicitudes pendientes.")
            else:
                for p in all_pending:
                    pf = p['fields']; meta = p['metadata']
                    label = f"[{meta['base_name']} / {meta['table_name']}] - {pf.get('Sucursal')} - {pf.get('Fecha')} ({pf.get('Tipo')})"
                    with st.expander(label, expanded=True):
                        c1, c2 = st.columns([3, 1])
                        c1.markdown(f"**AM:** {pf.get('AM Responsable')} | **Municipio:** {pf.get('Municipio')}"); c1.caption(f"ID Registro: {p['id']}")
                        if c2.button("✅ APROBAR", key=f"ga_{p['id']}", type="primary", use_container_width=True):
                            with st.spinner("Creando respaldo y desbloqueando..."):
                                ok, msg = aprobar_desbloqueo_admin(meta['base_id'], meta['table_id'], p)
                                if ok: st.success("¡Aprobado con éxito!"); st.rerun()
                                else: st.error(f"Fallo final: {msg}")
        
        with th:
            st.subheader("📜 Auditoría del Sistema")
            c_refresh, c_delete = st.columns([1, 4])
            if c_refresh.button("🔄 Actualizar", type="primary"):
                with st.spinner("Actualizando historial..."):
                    st.session_state.history_data_view = get_full_history() 
            
            if c_delete.button("🗑️ Eliminar Historial Completo (Limpiar Vista)", type="secondary"):
                st.session_state.history_data_view = [] 
                st.success("Vista limpiada.")
                st.rerun()

            logs = st.session_state.history_data_view
            
            if not logs and 'history_loaded' not in st.session_state:
                logs = get_full_history()
                st.session_state.history_data_view = logs
                st.session_state.history_loaded = True

            if logs:
                df = pd.DataFrame(logs)
                col_u, col_s = st.columns(2)
                if 'Usuario' in df.columns:
                    sel_users = col_u.multiselect("Filtrar por Usuario", df['Usuario'].unique())
                    if sel_users: df = df[df['Usuario'].isin(sel_users)]
                if 'Sucursal' in df.columns:
                    sel_sucs = col_s.multiselect("Filtrar por Sucursal", df['Sucursal'].unique())
                    if sel_sucs: df = df[df['Sucursal'].isin(sel_sucs)]

                if 'Fecha' in df.columns:
                    df['Fecha_DT'] = pd.to_datetime(df['Fecha'], errors='coerce')
                    meses_es = {1:"Enero", 2:"Febrero", 3:"Marzo", 4:"Abril", 5:"Mayo", 6:"Junio", 7:"Julio", 8:"Agosto", 9:"Septiembre", 10:"Octubre", 11:"Noviembre", 12:"Diciembre"}
                    df['YearMonth'] = df['Fecha_DT'].dt.strftime('%Y-%m')
                    
                    for ym in sorted(df['YearMonth'].unique(), reverse=True):
                        df_month = df[df['YearMonth'] == ym]
                        if not df_month.empty:
                            dt_obj = df_month.iloc[0]['Fecha_DT']
                            nombre_mes = f"{meses_es[dt_obj.month]} {dt_obj.year}"
                            with st.expander(f"📅 {nombre_mes} ({len(df_month)} registros)", expanded=(ym == sorted(df['YearMonth'].unique(), reverse=True)[0])): 
                                display_cols = ["Fecha", "Usuario", "Accion", "Sucursal", "Detalles"]
                                st.dataframe(df_month[[c for c in display_cols if c in df_month.columns]], use_container_width=True, hide_index=True)
                else:
                    st.dataframe(df, use_container_width=True)
            else:
                st.info("No hay datos para mostrar en esta vista.")

        main_area = tm
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
                        f = r['fields']; esta_completo = check_evidencia_completa(f)
                        estado_bloqueo = f.get('Estado_Bloqueo')
                        bloqueado = False
                        icon_lock = ""
                        if esta_completo:
                            if estado_bloqueo != 'Desbloqueado':
                                bloqueado = True
                                icon_lock = "🔒"
                                if estado_bloqueo == 'Solicitado': icon_lock = "⏳"
                        
                        with st.expander(f"{icon_lock} {f.get('Fecha')} | {f.get('Tipo')}", expanded=True):
                            c1, c2 = st.columns([1, 2.5]); c1.image(get_imagen_plantilla(f.get('Tipo')), use_container_width=True)
                            with c2:
                                st.markdown(f"### 🗓️ {formatear_fecha_larga(f.get('Fecha'))}")
                                st.markdown(f"**📌 Tipo:** {f.get('Tipo','--')}  \n**📍 Punto:** {f.get('Punto de reunion','--')}  \n**🛣️ Ruta:** {f.get('Ruta a seguir','--')}  \n**🏙️ Muni:** {f.get('Municipio','--')}  \n**⏰ Hora:** {f.get('Hora','--')}")
                                st.markdown("<br>",unsafe_allow_html=True); cb1, cb2 = st.columns(2)
                                if cb1.button("📸 EVIDENCIA", key=f"b_{r['id']}", type="primary", use_container_width=True): st.session_state.selected_event=r; st.rerun()
                                if not esta_completo:
                                    if cb2.button("⚠️ REAGENDAR", key=f"r_{r['id']}", use_container_width=True): st.session_state.rescheduling_event=r; st.rerun()
                else: st.info("No hay eventos.")
            else: st.info("Selecciona parámetros.")

        # 2. REAGENDAR
        elif st.session_state.rescheduling_event:
            evt = st.session_state.rescheduling_event; f=evt['fields']
            if st.button("⬅️ CANCELAR", type="secondary"): st.session_state.rescheduling_event=None; st.rerun()
            st.markdown("### ⚠️ Reagendar"); 
            with st.form("rgh"):
                c1,c2,c3=st.columns(3)
                try: fd=datetime.strptime(f.get('Fecha'),"%Y-%m-%d")
                except: fd=datetime.now()
                nf=c1.date_input("Fecha", value=fd); nh=c2.text_input("Hora", f.get("Hora")); nm=c3.text_input("Muni", f.get("Municipio"))
                nt=c1.text_input("Tipo", f.get('Tipo')); ns=c2.text_input("Sección", f.get('Seccion')); np=c3.text_input("Punto", f.get('Punto de reunion'))
                nr=c1.text_input("Ruta", f.get('Ruta a seguir')); nam=c2.text_input("AM", f.get('AM Responsable')); ndm=c3.text_input("DM", f.get('DM Responsable'))
                ntam=c1.text_input("Tel AM", f.get('Teléfono AM')); ntdm=c2.text_input("Tel DM", f.get('Teléfono DM')); nc=c3.text_input("Cantidad", f.get('Cantidad'))
                
                if st.form_submit_button("Guardar", type="primary"):
                    new_reg = {"Fecha":nf.strftime("%Y-%m-%d"),"Hora":nh,"Tipo":nt,"Sucursal":f.get('Sucursal'),"Seccion":ns,"Ruta a seguir":nr,"Punto de reunion":np,"Municipio":f"{nm} (Evento Reagendado)","Cantidad":nc,"AM Responsable":nam,"Teléfono AM":ntam,"DM Responsable":ndm,"Teléfono DM":ntdm}
                    if create_new_event(st.session_state.current_base_id, st.session_state.current_table_id, new_reg)[0]: st.success("Hecho"); st.session_state.rescheduling_event=None; st.session_state.search_results=get_records(st.session_state.current_base_id, st.session_state.current_table_id, st.session_state.current_plaza_view); st.rerun()
                    else: st.error("Error")

        # 3. CARGA EVIDENCIA
        else:
            evt = st.session_state.selected_event; f=evt['fields']
            current_record_fresh = next((r for r in get_records(st.session_state.current_base_id, st.session_state.current_table_id, st.session_state.current_plaza_view) if r['id'] == evt['id']), None)
            if current_record_fresh: f = current_record_fresh['fields']; evt = current_record_fresh
            
            if st.button("⬅️ REGRESAR", type="secondary", use_container_width=True): st.session_state.selected_event=None; st.rerun()
            st.divider(); st.markdown(f"### 📸 {f.get('Tipo')} - {obtener_ubicacion_corta(f)}"); st.divider()
            
            esta_completo = check_evidencia_completa(f)
            estado = f.get('Estado_Bloqueo')
            bloqueado = False
            if esta_completo and estado != 'Desbloqueado': bloqueado = True

            if bloqueado:
                st.warning("🔒 Registro Completo y Bloqueado.")
                if estado == 'Solicitado': 
                    st.info("⏳ Solicitud enviada. Esperando autorización... (La pantalla se actualizará automáticamente)")
                    time.sleep(4); st.rerun() # POLLING
                else:
                    if st.button("🔓 SOLICITAR DESBLOQUEO", type="primary"):
                        with st.spinner("Enviando..."):
                            resp = solicitar_desbloqueo(st.session_state.current_base_id, st.session_state.current_table_id, evt['id'], f)
                            if resp and resp.status_code==200: st.success("Enviado."); st.rerun()
                            else: pass 
            else:
                if esta_completo and estado == 'Desbloqueado':
                      st.toast("🔓 ¡PERMISO CONCEDIDO!", icon="✅")
                      st.markdown("""<audio autoplay><source src="https://upload.wikimedia.org/wikipedia/commons/0/05/Beep-09.ogg" type="audio/ogg"></audio>""", unsafe_allow_html=True)

            def render_cell(col, k, label):
                with col:
                    st.markdown(f'<p class="caption-text">{label}</p>', unsafe_allow_html=True)
                    if f.get(k):
                        st.image(f[k][0]['url'], use_container_width=True)
                        if not bloqueado:
                            if st.button("🗑️ Eliminar", key=f"d_{k}", type="secondary", use_container_width=True):
                                delete_field_from_airtable(st.session_state.current_base_id, st.session_state.current_table_id, evt['id'], k)
                                st.rerun()
                    else:
                        if not bloqueado:
                            up = st.file_uploader(k, key=f"u_{k}", type=['jpg','png','jpeg'], label_visibility="collapsed")
                            if up:
                                img_ok = comprimir_imagen_webp(up)
                                with st.spinner("Subiendo..."):
                                    res = cloudinary.uploader.upload(img_ok, format="webp", resource_type="image")
                                    upload_evidence_to_airtable(st.session_state.current_base_id, st.session_state.current_table_id, evt['id'], {k:[{"url":res['secure_url']}]})
                                    st.rerun()
                        else: st.caption("🔒")

            st.markdown("#### 1. Foto Inicio"); c1,c2 = st.columns(2); render_cell(c1, "Foto de equipo", "Foto Equipo")
            
            # --- CAMBIO SOLICITADO: TÍTULO "Fotos de Actividad" ---
            st.markdown("#### Fotos de Actividad"); keys=["Foto 01","Foto 02","Foto 03","Foto 04","Foto 05","Foto 06","Foto 07"]
            for i in range(0,len(keys),2):
                cr=st.columns(2); render_cell(cr[0], keys[i], keys[i])
                if i+1<len(keys): render_cell(cr[1], keys[i+1], keys[i+1])
            
            t3 = "3. Reporte y Lista" if f.get('Tipo') == "Actividad en Sucursal" else "3. Reporte Firmado"
            st.markdown(f"#### {t3}"); cr3=st.columns(2); render_cell(cr3[0], "Reporte firmado", "Reporte")
            if f.get('Tipo') == "Actividad en Sucursal": render_cell(cr3[1], "Lista de asistencia", "Lista")
            
            if not bloqueado and esta_completo:
                st.divider(); st.info("⚠️ Tienes permiso temporal.")
                if st.button("💾 FINALIZAR Y GUARDAR CAMBIOS", type="primary", use_container_width=True):
                    with st.spinner("Finalizando y bloqueando..."):
                        airtable_request("PATCH", f"https://api.airtable.com/v0/{st.session_state.current_base_id}/{st.session_state.current_table_id}/{evt['id']}", {"fields": {"Estado_Bloqueo": None}})
                        registrar_historial("Fin Edición Permiso", f"Usuario finalizó edición ID {evt['id']}")
                        st.session_state.selected_event = None
                        st.success("Guardado."); st.rerun()
