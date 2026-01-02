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
    .logo-light { display: none; }
    .logo-dark { display: block; }

    @media (prefers-color-scheme: dark) {
        .logo-light { display: block !important; }
        .logo-dark { display: none !important; }
    }
    [data-theme="dark"] .logo-light { display: block !important; }
    [data-theme="dark"] .logo-dark { display: none !important; }

    /* --- 2. ESTILOS GENERALES --- */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {}

    /* Expanders Negros */
    .streamlit-expanderHeader { background-color: #000000 !important; color: #ffffff !important; border: 1px solid #333333 !important; border-radius: 8px !important; }
    .streamlit-expanderContent { background-color: #1a1a1a !important; color: #ffffff !important; border: 1px solid #333333 !important; border-top: none !important; }
    .streamlit-expanderHeader p, .streamlit-expanderHeader span, .streamlit-expanderHeader svg,
    .streamlit-expanderContent p, .streamlit-expanderContent span, .streamlit-expanderContent h1, 
    .streamlit-expanderContent h2, .streamlit-expanderContent h3, .streamlit-expanderContent li, .streamlit-expanderContent label,
    .streamlit-expanderContent div { color: #ffffff !important; fill: #ffffff !important; }

    /* Botones */
    .stButton button[kind="primary"] { background-color: #00c853 !important; border: none !important; color: #ffffff !important; font-weight: 700 !important; }
    .stButton button[kind="primary"]:hover { background-color: #009624 !important; }
    .stButton button[kind="primary"] p { color: #ffffff !important; }
    .stButton button[kind="secondary"] { background-color: #dc2626 !important; border: none !important; color: #ffffff !important; font-weight: 600 !important; }
    .stButton button[kind="secondary"]:hover { background-color: #b91c1c !important; }
    .stButton button[kind="secondary"] p { color: #ffffff !important; }
    
    /* Botón Reagendar (Celeste) */
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

# --- CONFIGURACIÓN BASE MAESTRA ---
ADMIN_BASE_ID = "appRF7jHcmBJZA1px"
USERS_TABLE_ID = "tblzeDe2WTzmPKxv0"
CONFIG_TABLE_ID = "tblB9hhfMAS8HGEjZ"
BACKUP_TABLE_ID = "tbl..."  # <--- ⚠️ PON AQUÍ EL ID DE LA TABLA "MODIFICACION CON PERMISO"

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
        html = f"""<div style="text-align: center;"><img src="data:image/png;base64,{b64_light}" class="logo-light" style="{width_css}"><img src="data:image/png;base64,{b64_dark}" class="logo-dark" style="{width_css}"></div>"""
        st.markdown(html, unsafe_allow_html=True)
    else: st.markdown("## 🏦 **Provident**")

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
# 3. FUNCIONES AIRTABLE (CORE)
# ==============================================================================
def airtable_request(method, url, data=None):
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}
    try:
        if method == "GET": r = requests.get(url, headers=headers)
        elif method == "POST": r = requests.post(url, json=data, headers=headers)
        elif method == "PATCH": r = requests.patch(url, json=data, headers=headers)
        elif method == "DELETE": r = requests.delete(url, headers=headers)
        return r
    except: return None

def api_get_all_bases():
    r = airtable_request("GET", "https://api.airtable.com/v0/meta/bases")
    return {b['name']: b['id'] for b in r.json().get('bases', [])} if r and r.status_code==200 else {}

def api_get_all_tables(base_id):
    r = airtable_request("GET", f"https://api.airtable.com/v0/meta/bases/{base_id}/tables")
    return {t['name']: t['id'] for t in r.json().get('tables', [])} if r and r.status_code==200 else {}

def get_records(base_id, table_id, year, plaza):
    r = airtable_request("GET", f"https://api.airtable.com/v0/{base_id}/{table_id}")
    if not r or r.status_code != 200: return []
    filtered = []; plaza_norm = normalizar_texto_simple(plaza)
    for rec in r.json().get('records', []):
        f = rec.get('fields', {})
        if str(f.get('Fecha','')).startswith(str(year)):
            p_val = f.get('Sucursal')
            p_str = p_val[0] if isinstance(p_val, list) else str(p_val)
            if normalizar_texto_simple(p_str) == plaza_norm: filtered.append(rec)
    filtered.sort(key=lambda x: (x['fields'].get('Fecha',''), x['fields'].get('Hora','')))
    return filtered

# --- LÓGICA DE RESPALDO Y BLOQUEO ---
def crear_respaldo_evento(fields_original):
    """Copia todos los campos relevantes a la tabla de respaldo"""
    campos_copiar = ["Tipo", "Fecha", "Hora", "Sucursal", "Seccion", "Ruta a seguir", "Punto de reunion", "Municipio", "Cantidad", "AM Responsable", "DM Responsable", "Teléfono AM", "Teléfono DM", "Foto de equipo", "Foto 01", "Foto 02", "Foto 03", "Foto 04", "Foto 05", "Foto 06", "Foto 07", "Reporte firmado", "Lista de asistencia"]
    new_data = {}
    for k in campos_copiar:
        if k in fields_original:
            # Para imagenes, Airtable necesita una lista de dicts con url
            if isinstance(fields_original[k], list) and 'url' in fields_original[k][0]:
                new_data[k] = [{'url': img['url']} for img in fields_original[k]]
            else:
                new_data[k] = fields_original[k]
    
    # Agregar timestamp de respaldo si se desea (opcional)
    new_data["Notas"] = f"Respaldo automático: {datetime.now()}"
    
    url = f"https://api.airtable.com/v0/{ADMIN_BASE_ID}/{BACKUP_TABLE_ID}"
    return airtable_request("POST", url, {"fields": new_data})

def solicitar_desbloqueo(base_id, table_id, record_id):
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}/{record_id}"
    return airtable_request("PATCH", url, {"fields": {"Estado_Bloqueo": "Solicitado"}})

def aprobar_desbloqueo_admin(base_id, table_id, record_full_data):
    # 1. Crear Respaldo
    resp_backup = crear_respaldo_evento(record_full_data['fields'])
    if resp_backup and resp_backup.status_code == 200:
        # 2. Desbloquear Original
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}/{record_full_data['id']}"
        resp_update = airtable_request("PATCH", url, {"fields": {"Estado_Bloqueo": "Desbloqueado"}})
        return resp_update.status_code == 200
    return False

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
                    st.rerun()
                else: st.error("Datos incorrectos")

# ==============================================================================
# 6. APP PRINCIPAL
# ==============================================================================
else:
    render_logo_dinamico(True); st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([3,4,1])
    with c1: st.markdown(f"#### 👤 {st.session_state.user_name} | {st.session_state.user_role.upper()}")
    with c3: 
        if st.button("SALIR", use_container_width=True, type="secondary"): st.session_state.logged_in=False; st.rerun()
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
                st.session_state.search_results=get_records(bid, tid, YEAR_ACTUAL, spl)
                st.session_state.current_base_id=bid; st.session_state.current_table_id=tid; st.session_state.current_plaza_view=spl

    st.divider()

    # ADMIN PANEL
    if st.session_state.user_role == "admin":
        tm, tu, tc, ta = st.tabs(["📂 Eventos", "👥 Usuarios", "⚙️ Config", "🔐 Solicitudes"])
        
        # ... (Pestañas de usuarios y config iguales que antes) ...
        with tu:
            st.subheader("Gestión Usuarios"); udb = cargar_usuarios_airtable()
            sel = st.selectbox("Editar", ["(Nuevo)"]+list(udb.keys()))
            if sel=="(Nuevo)": d={"password":"", "role":"user", "plazas":[]}; rid=None
            else: d=udb[sel]; rid=d['id']
            with st.form("uf"):
                cu, cp = st.columns(2); nu=cu.text_input("User", sel if sel!="(Nuevo)" else ""); np=cp.text_input("Pass", d['password'])
                nr=st.selectbox("Rol",["user","admin"],0 if d['role']=="user" else 1); npl=st.multiselect("Plazas", SUCURSALES_OFICIALES, d['plazas'])
                if st.form_submit_button("Guardar", type="primary"):
                    crear_actualizar_usuario_airtable(nu,np,nr,npl,rid); st.success("OK"); st.rerun()
        
        with tc:
            st.subheader("Agregar Config"); 
            with st.form("cf"):
                c1,c2=st.columns(2); nb=c1.text_input("Nombre Base"); ib=c2.text_input("ID Base")
                nt=c1.text_input("Nombre Tabla"); it=c2.text_input("ID Tabla")
                if st.form_submit_button("Guardar", type="primary"):
                    url=f"https://api.airtable.com/v0/{ADMIN_BASE_ID}/{CONFIG_TABLE_ID}"
                    requests.post(url, json={"fields":{"Nombre_Base":nb,"ID_Base":ib,"Nombre_Tabla":nt,"ID_Tabla":it,"Activo":True}}, headers={"Authorization":f"Bearer {AIRTABLE_TOKEN}","Content-Type":"application/json"})
                    st.success("OK"); st.rerun()

        with ta:
            st.subheader("🔐 Solicitudes de Desbloqueo (Tabla Actual)")
            if 'search_results' in st.session_state:
                pending = [r for r in st.session_state.search_results if r['fields'].get('Estado_Bloqueo') == 'Solicitado']
                if not pending: st.info("No hay solicitudes pendientes en esta tabla.")
                else:
                    for p in pending:
                        pf = p['fields']
                        with st.expander(f"Solicitud: {pf.get('Tipo')} - {pf.get('Fecha')}", expanded=True):
                            st.write(f"**Sucursal:** {pf.get('Sucursal')} | **AM:** {pf.get('AM Responsable')}")
                            if st.button("✅ APROBAR Y RESPALDAR", key=f"ap_{p['id']}", type="primary"):
                                with st.spinner("Creando respaldo y desbloqueando..."):
                                    if aprobar_desbloqueo_admin(st.session_state.current_base_id, st.session_state.current_table_id, p):
                                        st.success("Procesado."); st.session_state.search_results=get_records(st.session_state.current_base_id, st.session_state.current_table_id, YEAR_ACTUAL, st.session_state.current_plaza_view); st.rerun()
                                    else: st.error("Error al procesar.")
            else: st.warning("Carga una tabla primero.")

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
                        f = r['fields']; ya_tiene = check_evidencia_completa(f)
                        # Estado Bloqueo Logic
                        estado_bloqueo = f.get('Estado_Bloqueo')
                        is_locked = ya_tiene and (estado_bloqueo != 'Desbloqueado')
                        
                        icon_lock = "🔒" if is_locked else ""
                        
                        with st.expander(f"{icon_lock} {f.get('Fecha')} | {f.get('Tipo')}", expanded=True):
                            c1, c2 = st.columns([1, 2.5]); c1.image(get_imagen_plantilla(f.get('Tipo')), use_container_width=True)
                            with c2:
                                st.markdown(f"### 🗓️ {formatear_fecha_larga(f.get('Fecha'))}")
                                st.markdown(f"**📌 Tipo:** {f.get('Tipo','--')}  \n**📍 Punto:** {f.get('Punto de reunion','--')}  \n**🛣️ Ruta:** {f.get('Ruta a seguir','--')}  \n**🏙️ Muni:** {f.get('Municipio','--')}  \n**⏰ Hora:** {f.get('Hora','--')}")
                                st.markdown("<br>",unsafe_allow_html=True); cb1, cb2 = st.columns(2)
                                
                                if cb1.button("📸 EVIDENCIA", key=f"b_{r['id']}", type="primary", use_container_width=True): st.session_state.selected_event=r; st.rerun()
                                if not ya_tiene:
                                    if cb2.button("⚠️ REAGENDAR", key=f"r_{r['id']}", use_container_width=True): st.session_state.rescheduling_event=r; st.rerun()
                else: st.info("No hay eventos.")
            else: st.info("Selecciona parámetros.")

        # 2. REAGENDAR (Igual que antes)
        elif st.session_state.rescheduling_event:
            evt = st.session_state.rescheduling_event; f=evt['fields']
            if st.button("⬅️ CANCELAR", type="secondary"): st.session_state.rescheduling_event=None; st.rerun()
            st.markdown("### ⚠️ Reagendar"); 
            with st.form("rgh"):
                c1,c2,c3=st.columns(3)
                nf=c1.date_input("Fecha"); nh=c2.text_input("Hora", f.get("Hora")); nm=c3.text_input("Muni", f.get("Municipio"))
                # ... (resto campos) ...
                if st.form_submit_button("Guardar", type="primary"):
                    # Logica crear nuevo...
                    st.success("Hecho"); st.session_state.rescheduling_event=None; st.rerun()

        # 3. CARGA EVIDENCIA (CON BLOQUEO)
        else:
            evt = st.session_state.selected_event; f=evt['fields']
            if st.button("⬅️ REGRESAR", type="secondary", use_container_width=True): st.session_state.selected_event=None; st.rerun()
            st.divider(); st.markdown(f"### 📸 {f.get('Tipo')}"); st.divider()
            
            # Lógica de Bloqueo Local
            ya_tiene = check_evidencia_completa(f)
            estado = f.get('Estado_Bloqueo')
            bloqueado = ya_tiene and (estado != 'Desbloqueado')

            if bloqueado:
                st.warning("🔒 Registro Bloqueado. Se requiere permiso para modificar.")
                if estado == 'Solicitado':
                    st.info("⏳ Solicitud enviada al administrador. Esperando aprobación.")
                else:
                    if st.button("🔓 SOLICITAR DESBLOQUEO", type="primary"):
                        with st.spinner("Enviando solicitud..."):
                            if solicitar_desbloqueo(st.session_state.current_base_id, st.session_state.current_table_id, evt['id']):
                                st.success("Solicitud enviada."); evt['fields']['Estado_Bloqueo']='Solicitado'; st.rerun()
                            else: st.error("Error al solicitar.")

            def render_cell(col, k, label):
                with col:
                    st.markdown(f'<p class="caption-text">{label}</p>', unsafe_allow_html=True)
                    if f.get(k):
                        st.image(f[k][0]['url'], use_container_width=True)
                        if not bloqueado: # SOLO MOSTRAR ELIMINAR SI NO ESTA BLOQUEADO
                            if st.button("🗑️ Eliminar", key=f"d_{k}", type="secondary", use_container_width=True):
                                url = f"https://api.airtable.com/v0/{st.session_state.current_base_id}/{st.session_state.current_table_id}/{evt['id']}"
                                airtable_request("PATCH", url, {"fields": {k: None}})
                                del st.session_state.selected_event['fields'][k]; st.rerun()
                    else:
                        if not bloqueado: # SOLO PERMITIR SUBIR SI NO ESTA BLOQUEADO
                            up = st.file_uploader(k, key=f"u_{k}", type=['jpg','png','jpeg'], label_visibility="collapsed")
                            if up:
                                img_ok = comprimir_imagen_webp(up)
                                with st.spinner("Subiendo..."):
                                    res = cloudinary.uploader.upload(img_ok, format="webp", resource_type="image")
                                    url = f"https://api.airtable.com/v0/{st.session_state.current_base_id}/{st.session_state.current_table_id}/{evt['id']}"
                                    airtable_request("PATCH", url, {"fields": {k:[{"url":res['secure_url']}]}})
                                    st.session_state.selected_event['fields'][k] = [{"url":res['secure_url']}]; st.rerun()
                        else:
                            st.caption("🔒 Bloqueado")

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
