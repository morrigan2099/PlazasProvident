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

# ==============================================================================
# 1. CONFIGURACIÓN Y ESTILOS (TEMA CLARO FORZADO AGRESIVO)
# ==============================================================================
st.set_page_config(page_title="Gestor Provident", layout="wide")

st.markdown("""
<style>
    /* --- 1. RESET GLOBAL A TEMA CLARO (BLANCO/NEGRO) --- */
    
    /* Fondo principal y textos */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #ffffff !important;
        color: #000000 !important;
    }
    
    /* Forzar textos a negro (excepto botones que definiremos luego) */
    h1, h2, h3, h4, h5, h6, p, li, span, label, div.stMarkdown {
        color: #000000 !important;
    }

    /* --- 2. CORRECCIÓN DE ELEMENTOS DE INTERFAZ (EXPANDERS Y MENUS) --- */
    
    /* Expanders (Persianas) - Fondo Blanco y Borde */
    .streamlit-expanderHeader {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #e0e0e0 !important;
    }
    .streamlit-expanderContent {
        background-color: #ffffff !important;
        color: #000000 !important;
        border-top: none !important;
        border: 1px solid #e0e0e0 !important;
    }
    /* El texto dentro del expander header */
    .streamlit-expanderHeader p {
        color: #000000 !important;
        font-weight: 600;
    }

    /* Inputs y Selectboxes (Cajas de texto y menús) */
    .stTextInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #ffffff !important;
        color: #000000 !important;
        border-color: #cccccc !important;
    }
    
    /* MENÚS DESPLEGABLES (El dropdown que aparece al hacer click) */
    div[data-baseweb="popover"], div[data-baseweb="menu"], ul {
        background-color: #ffffff !important;
        color: #000000 !important;
    }
    li[role="option"] {
        background-color: #ffffff !important;
        color: #000000 !important;
    }
    /* Highlight del menú al pasar mouse */
    li[role="option"]:hover, li[role="option"][aria-selected="true"] {
        background-color: #e3f2fd !important; /* Azul muy claro */
    }

    /* --- 3. ESTILOS DE BOTONES (TEXTO BLANCO SIEMPRE) --- */
    
    /* Botón PRIMARIO (Verde Sólido #00c853) */
    .stButton button[kind="primary"] {
        background-color: #00c853 !important;
        border: none !important;
        color: #ffffff !important; /* TEXTO BLANCO */
        font-weight: 700 !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    .stButton button[kind="primary"] p {
        color: #ffffff !important; /* Forzar p interno a blanco */
    }
    .stButton button[kind="primary"]:hover {
        background-color: #009624 !important;
    }

    /* Botón SECUNDARIO (Rojo Sólido #dc2626 - Eliminar) */
    .stButton button[kind="secondary"] {
        background-color: #dc2626 !important;
        color: #ffffff !important; /* TEXTO BLANCO */
        border: none !important;
        font-weight: 600 !important;
    }
    .stButton button[kind="secondary"] p {
        color: #ffffff !important; /* Forzar p interno a blanco */
    }
    .stButton button[kind="secondary"]:hover {
        background-color: #b91c1c !important;
        border-color: #b91c1c !important;
        color: #ffffff !important;
    }

    /* --- 4. UPLOADER --- */
    [data-testid="stFileUploader"] small {display: none;}
    [data-testid="stFileUploader"] button {display: none;}
    [data-testid="stFileUploader"] section > div {display: none;}
    
    [data-testid="stFileUploader"] section {
        min-height: 0px !important;
        padding: 10px !important;
        background-color: #f8f9fa !important;
        border: 2px dashed #00b0ff !important; /* Borde Celeste */
        border-radius: 12px;
        align-items: center;
        justify-content: center;
        display: flex;
        cursor: pointer;
    }
    [data-testid="stFileUploader"] section::after {
        content: "➕";
        font-size: 32px;
        color: #00b0ff !important; /* Celeste */
        visibility: visible;
        display: block;
    }

    /* --- 5. OCULTAR SIDEBAR --- */
    [data-testid="stSidebar"] {display: none;}
    [data-testid="collapsedControl"] {display: none;}

    /* Ajuste de imágenes para que llenen contenedor */
    img { max-width: 100%; }
    
</style>
""", unsafe_allow_html=True)

# --- CREDENCIALES ---
CLOUDINARY_CONFIG = {
    "cloud_name": "dlj0pdv6i",
    "api_key": "847419449273122",
    "api_secret": "i0cJCELeYVAosiBL_ltjHkM_FV0"
}
AIRTABLE_TOKEN = "patyclv7hDjtGHB0F.19829008c5dee053cba18720d38c62ed86fa76ff0c87ad1f2d71bfe853ce9783"
MASTER_ADMIN_PASS = "3spejoVenenoso$2099" 
SUCURSALES_OFICIALES = ["Cordoba", "Orizaba", "Xalapa", "Puebla", "Oaxaca", "Tuxtepec", "Boca del Río", "Tehuacan"]

FILES_DB = "usuarios.json"
CONFIG_DB = "config_airtable.json"
HISTORIAL_FILE = "historial_modificaciones.csv"
YEAR_ACTUAL = 2025 

cloudinary.config(
    cloud_name=CLOUDINARY_CONFIG["cloud_name"],
    api_key=CLOUDINARY_CONFIG["api_key"],
    api_secret=CLOUDINARY_CONFIG["api_secret"]
)

# ==============================================================================
# 2. FUNCIONES
# ==============================================================================
def limpiar_clave(texto):
    if not isinstance(texto, str): return str(texto).lower()
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]', '', texto.lower())

def formatear_fecha_larga(fecha_str):
    if not fecha_str: return "Fecha pendiente"
    dias = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
    meses = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
    try:
        dt = datetime.strptime(fecha_str, "%Y-%m-%d")
        return f"{dias[dt.weekday()]} {dt.day:02d} de {meses[dt.month]} de {dt.year}"
    except: return fecha_str

def obtener_ubicacion_corta(fields):
    opciones = [str(fields.get('Punto de reunion', '')), str(fields.get('Ruta a seguir', '')), str(fields.get('Municipio', ''))]
    validas = [op for op in opciones if op and op.lower() != 'none' and len(op) > 2]
    if not validas: return "Ubicación N/A"
    return min(validas, key=len)

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

def render_logo(is_banner=False):
    """
    is_banner=False -> Logo pequeño (Login)
    is_banner=True -> Logo ancho completo (App Principal)
    """
    path_logo = os.path.join("assets", "logo.png")
    if os.path.exists(path_logo):
        if is_banner:
            # Banner ancho completo
            st.image(path_logo, use_container_width=True) 
        else:
            # Logo contenido (Login)
            st.image(path_logo, use_container_width=True)
    else:
        st.markdown(f"## 🏦 **Provident**") 

def get_imagen_plantilla(tipo_evento):
    carpeta_assets = "assets" 
    url_default = "https://via.placeholder.com/400x300.png?text=Provident+Evento" 
    if not tipo_evento: tipo_evento = "default"
    if not os.path.exists(carpeta_assets): return url_default
    clave_buscada = limpiar_clave(str(tipo_evento))
    try:
        archivos = os.listdir(carpeta_assets)
        for archivo in archivos:
            if limpiar_clave(os.path.splitext(archivo)[0]) == clave_buscada: return os.path.join(carpeta_assets, archivo)
        for archivo in archivos:
            if "default" in limpiar_clave(archivo): return os.path.join(carpeta_assets, archivo)
    except: pass
    return url_default

def normalizar_texto_simple(texto):
    if not isinstance(texto, str): return str(texto).lower()
    texto = unicodedata.normalize('NFD', texto)
    return ''.join(c for c in texto if unicodedata.category(c) != 'Mn').lower()

def cargar_usuarios():
    if not os.path.exists(FILES_DB):
        default_db = {"admin": {"password": MASTER_ADMIN_PASS, "role": "admin", "plazas": SUCURSALES_OFICIALES}}
        with open(FILES_DB, 'w') as f: json.dump(default_db, f)
        return default_db
    with open(FILES_DB, 'r') as f: return json.load(f)

def guardar_usuarios(db):
    with open(FILES_DB, 'w') as f: json.dump(db, f)

def cargar_config_db():
    if not os.path.exists(CONFIG_DB): return {} 
    with open(CONFIG_DB, 'r') as f: return json.load(f)

def guardar_config_db(config_data):
    with open(CONFIG_DB, 'w') as f: json.dump(config_data, f)

def registrar_historial(accion, usuario, sucursal, detalles):
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nuevo_registro = {"Fecha": fecha, "Usuario": usuario, "Sucursal": sucursal, "Acción": accion, "Detalles": detalles}
    df_new = pd.DataFrame([nuevo_registro])
    if not os.path.exists(HISTORIAL_FILE): df_new.to_csv(HISTORIAL_FILE, index=False)
    else: df_new.to_csv(HISTORIAL_FILE, mode='a', header=False, index=False)

def check_evidencia_completa(fields):
    claves_evidencia = ["Foto de equipo", "Foto 01", "Foto 02", "Foto 03", "Foto 04", "Foto 05", "Foto 06", "Foto 07", "Reporte firmado", "Lista de asistencia"]
    for k in claves_evidencia:
        if fields.get(k): return True
    return False

# ==============================================================================
# 3. FUNCIONES AIRTABLE
# ==============================================================================
def api_get_all_bases():
    url = "https://api.airtable.com/v0/meta/bases"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200: return {b['name']: b['id'] for b in r.json().get('bases', [])}
    except: pass
    return {}

def api_get_all_tables(base_id):
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200: return {t['name']: t['id'] for t in r.json().get('tables', [])}
    except: pass
    return {}

def get_authorized_bases():
    config = cargar_config_db()
    return config.get("bases", {})

def get_authorized_tables(base_id):
    config = cargar_config_db()
    all_tables_config = config.get("tables", {})
    return all_tables_config.get(base_id, {})

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
        fields = rec.get('fields', {})
        fecha_dato = fields.get('Fecha')
        match_year = False
        if fecha_dato and str(fecha_dato).startswith(str(year)): match_year = True
        suc_dato = fields.get('Sucursal')
        match_plaza = False
        if suc_dato:
            val_suc = str(suc_dato[0]) if isinstance(suc_dato, list) else str(suc_dato)
            if normalizar_texto_simple(val_suc) == plaza_norm: match_plaza = True
        if match_year and match_plaza: filtered.append(rec)
    try: filtered.sort(key=lambda x: (x['fields'].get('Fecha',''), x['fields'].get('Hora','')))
    except: pass
    return filtered

def upload_evidence_to_airtable(base_id, table_id, record_id, updates_dict):
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}/{record_id}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}
    data = {"fields": updates_dict}
    r = requests.patch(url, json=data, headers=headers)
    return r.status_code == 200

def delete_field_from_airtable(base_id, table_id, record_id, field_name):
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}/{record_id}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}
    data = {"fields": {field_name: None}} 
    r = requests.patch(url, json=data, headers=headers)
    return r.status_code == 200

def create_new_event(base_id, table_id, new_data):
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}
    payload = {"fields": new_data}
    try:
        r = requests.post(url, json=payload, headers=headers)
        if r.status_code == 200: return True, r.json()
        else: return False, r.text
    except Exception as e: return False, str(e)

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
    # Espaciado superior
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # Columna central para el formulario
    c_izq, c_centro, c_der = st.columns([1, 2, 1])
    
    with c_centro:
        # LOGO CENTRADO Y CONTENIDO EN LA CAJA DE LOGIN
        # Al usar st.columns([1,2,1]), el logo quedará centrado y de buen tamaño
        render_logo(is_banner=False) # Usa logo normal, ajustado al ancho de columna
        
        st.markdown("<h3 style='text-align: center;'>🔐 Acceso al Sistema</h3>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            usuario_input = st.text_input("👤 Usuario:")
            pass_input = st.text_input("🔑 Contraseña:", type="password")
            
            # Botón verde sólido con texto blanco
            btn = st.form_submit_button("INGRESAR", use_container_width=True, type="primary")
            
            if btn:
                users_db = cargar_usuarios()
                user_data = users_db.get(usuario_input)
                if user_data and user_data['password'] == pass_input:
                    st.session_state.logged_in = True
                    st.session_state.user_role = user_data.get('role', 'user')
                    st.session_state.user_name = usuario_input
                    st.session_state.allowed_plazas = user_data.get('plazas', [])
                    registrar_historial("Login", usuario_input, "Sistema", "Inicio de sesión exitoso")
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas.")

# ==============================================================================
# 6. APP PRINCIPAL
# ==============================================================================
else:
    # --- HEADER PRINCIPAL ---
    # Logo Full Width (Banner) arriba del todo
    render_logo(is_banner=True)
    
    st.markdown("<br>", unsafe_allow_html=True)

    # Info Usuario (Izquierda) y Logout (Derecha)
    c_user, c_fill, c_logout = st.columns([3, 4, 1])
    with c_user:
        # Texto negro forzado por CSS
        st.markdown(f"#### 👤 {st.session_state.user_name} | {st.session_state.user_role.upper()}")
    with c_logout:
        # Botón rojo sólido (secondary)
        if st.button("SALIR", use_container_width=True, type="secondary"):
            st.session_state.logged_in = False
            st.rerun()
            
    st.divider()

    # TOPBAR FILTROS
    with st.container():
        col_base, col_mes, col_plaza = st.columns(3)
        with col_base:
            bases_map = get_authorized_bases()
            if not bases_map: st.warning("⚠️ Sin bases"); base_id = None
            else: base_name = st.selectbox("📂 Base de Datos", list(bases_map.keys())); base_id = bases_map[base_name]
        with col_mes:
            if base_id:
                tables_map = get_authorized_tables(base_id)
                if tables_map: table_name = st.selectbox("📅 Mes", list(tables_map.keys())); table_id = tables_map[table_name]
                else: table_id = None
            else: st.selectbox("📅 Mes", [], disabled=True); table_id = None
        with col_plaza:
            plazas_permitidas = st.session_state.allowed_plazas
            sel_plaza = st.selectbox("📍 Plaza", plazas_permitidas) if plazas_permitidas else None
            if sel_plaza: st.session_state.sucursal_actual = sel_plaza

    # AUTO-CARGA
    if base_id and table_id and sel_plaza:
        has_changed = (base_id != st.session_state.get('current_base_id') or table_id != st.session_state.get('current_table_id') or sel_plaza != st.session_state.get('current_plaza_view') or 'search_results' not in st.session_state)
        if has_changed:
            with st.spinner("🔄 Actualizando lista..."):
                st.session_state.selected_event = None; st.session_state.rescheduling_event = None
                st.session_state.search_results = get_records(base_id, table_id, YEAR_ACTUAL, sel_plaza)
                st.session_state.current_base_id = base_id; st.session_state.current_table_id = table_id; st.session_state.current_plaza_view = sel_plaza

    st.divider()

    # PESTAÑAS ADMIN
    if st.session_state.user_role == "admin":
        tab_main, tab_users, tab_config_db, tab_hist = st.tabs(["📂 Eventos", "👥 Usuarios", "⚙️ Configuración DB", "📜 Historial"])
        with tab_users:
            users_db = cargar_usuarios(); st.subheader("Gestión de Accesos"); opciones_usuarios = ["(Crear Nuevo)"] + list(users_db.keys()); seleccion = st.selectbox("🔍 Seleccionar Usuario:", opciones_usuarios)
            if seleccion == "(Crear Nuevo)": val_user = ""; val_pass = ""; val_role = "user"; val_plazas = []; es_edicion = False
            else: data_u = users_db[seleccion]; val_user = seleccion; val_pass = data_u.get('password', ''); val_role = data_u.get('role', 'user'); val_plazas = data_u.get('plazas', []); es_edicion = True
            with st.form("form_usuarios_admin"):
                c1, c2 = st.columns(2); new_user = c1.text_input("Usuario (ID)", value=val_user); new_pass = c2.text_input("Contraseña", value=val_pass)
                c3, c4 = st.columns(2); new_role = c3.selectbox("Rol", ["user", "admin"], index=0 if val_role=="user" else 1); new_plazas = c4.multiselect("Plazas", SUCURSALES_OFICIALES, default=[p for p in val_plazas if p in SUCURSALES_OFICIALES])
                if st.form_submit_button("💾 Guardar Datos", type="primary"):
                    if not new_user or not new_pass: st.error("Faltan datos.")
                    else:
                        if es_edicion and new_user != seleccion: del users_db[seleccion]
                        users_db[new_user] = {"password": new_pass, "role": new_role, "plazas": new_plazas}; guardar_usuarios(users_db); st.success("Guardado."); st.rerun()
            if es_edicion:
                if st.button("🗑️ Eliminar Usuario", type="secondary"): del users_db[seleccion]; guardar_usuarios(users_db); st.warning("Eliminado."); st.rerun()
        with tab_config_db:
             current_config = cargar_config_db(); current_bases = current_config.get("bases", {}); current_tables = current_config.get("tables", {})
             with st.spinner("Conectando..."): real_bases = api_get_all_bases()
             if real_bases:
                 with st.form("db_c"):
                     bs = st.multiselect("Bases:", list(real_bases.keys()), default=[n for n in real_bases if n in current_bases])
                     nb={}; nt={}
                     for b in bs:
                         bid=real_bases[b]; nb[b]=bid; rt=api_get_all_tables(bid); pt=current_tables.get(bid,{})
                         ts=st.multiselect(f"Tablas {b}:", list(rt.keys()), default=[n for n in rt if n in pt]); nt[bid]={n:rt[n] for n in ts}
                     if st.form_submit_button("💾 Guardar Configuración", type="primary"): guardar_config_db({"bases":nb,"tables":nt}); st.success("Ok"); st.rerun()
        with tab_hist:
             if os.path.exists(HISTORIAL_FILE): st.dataframe(pd.read_csv(HISTORIAL_FILE).sort_values("Fecha", ascending=False), use_container_width=True)
        main_area = tab_main
    else: main_area = st.container()

    # VISTAS PRINCIPALES
    with main_area:
        if 'current_plaza_view' in st.session_state: st.markdown(f"### 📋 Eventos en {st.session_state.current_plaza_view} ({YEAR_ACTUAL})")

        # 1. LISTADO
        if st.session_state.selected_event is None and st.session_state.rescheduling_event is None:
            if 'search_results' in st.session_state:
                recs = st.session_state.search_results
                if recs:
                    for r in recs:
                        f = r['fields']; ya_tiene = check_evidencia_completa(f)
                        with st.expander(f"{f.get('Fecha')} | {f.get('Tipo', 'Evento')}", expanded=True):
                            col_img, col_data = st.columns([1, 2.5])
                            with col_img: st.image(get_imagen_plantilla(f.get('Tipo')), use_container_width=True)
                            with col_data:
                                st.markdown(f"### 🗓️ {formatear_fecha_larga(f.get('Fecha'))}")
                                st.markdown(f"**📌 Tipo:** {f.get('Tipo','--')}\n**📍 Punto:** {f.get('Punto de reunion','--')}\n**🛣️ Ruta:** {f.get('Ruta a seguir','--')}\n**🏙️ Muni:** {f.get('Municipio','--')}\n**⏰ Hora:** {f.get('Hora','--')}")
                                st.markdown("<br>",unsafe_allow_html=True)
                                c1,c2=st.columns(2)
                                if c1.button("📸 SUBIR EVIDENCIA", key=f"b_{r['id']}", type="primary", use_container_width=True): st.session_state.selected_event=r; st.rerun()
                                if not ya_tiene:
                                    if c2.button("⚠️ EVENTO REAGENDADO", key=f"r_{r['id']}", use_container_width=True, type="secondary"): st.session_state.rescheduling_event=r; st.rerun()
                else: 
                    if st.session_state.get('sucursal_actual'): st.info("No hay eventos.")
                    else: st.warning("Carga eventos.")
            else: st.info("👆 Cargar eventos.")

        # 2. REAGENDAR
        elif st.session_state.rescheduling_event is not None:
            evt = st.session_state.rescheduling_event; f_orig = evt['fields']
            if st.button("⬅️ CANCELAR REAGENDADO", use_container_width=True, type="secondary"): st.session_state.rescheduling_event = None; st.rerun()
            st.markdown("### ⚠️ Reagendar Evento")
            with st.form("reschedule_form"):
                c1, c2, c3 = st.columns(3)
                try: fd = datetime.strptime(f_orig.get('Fecha', datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d")
                except: fd = datetime.now()
                with c1: nf=st.date_input("Fecha",value=fd); nt=st.text_input("Tipo",value=f_orig.get('Tipo','')); ns=st.text_input("Sección",value=f_orig.get('Seccion','')); nam=st.text_input("AM",value=f_orig.get('AM Responsable','')); ndm=st.text_input("DM",value=f_orig.get('DM Responsable',''))
                with c2: nh=st.text_input("Hora",value=f_orig.get('Hora','09:00')); nsu=st.text_input("Sucursal",value=f_orig.get('Sucursal',st.session_state.sucursal_actual)); nr=st.text_input("Ruta",value=f_orig.get('Ruta a seguir','')); ntam=st.text_input("Tel AM",value=f_orig.get('Teléfono AM','')); ntdm=st.text_input("Tel DM",value=f_orig.get('Teléfono DM',''))
                with c3: nm=st.text_input("Municipio",value=f_orig.get('Municipio','')); np=st.text_input("Punto",value=f_orig.get('Punto de reunion','')); nc=st.text_input("Cantidad",value=f_orig.get('Cantidad',''))
                st.markdown("<br>",unsafe_allow_html=True)
                if st.form_submit_button("💾 GUARDAR NUEVA FECHA", type="primary", use_container_width=True):
                    new_reg = {"Fecha":nf.strftime("%Y-%m-%d"),"Hora":nh,"Tipo":nt,"Sucursal":nsu,"Seccion":ns,"Ruta a seguir":nr,"Punto de reunion":np,"Municipio":f"{nm} (Evento Reagendado)","Cantidad":nc,"AM Responsable":nam,"Teléfono AM":ntam,"DM Responsable":ndm,"Teléfono DM":ntdm}
                    ex, rs = create_new_event(st.session_state.current_base_id, st.session_state.current_table_id, new_reg)
                    if ex: st.success("✅ Creado."); registrar_historial("Reagendar",st.session_state.user_name,nsu,f"Orig:{f_orig.get('Fecha')}->New:{nf}"); st.session_state.rescheduling_event=None; st.session_state.search_results=get_records(st.session_state.current_base_id,st.session_state.current_table_id,YEAR_ACTUAL,st.session_state.current_plaza_view); st.rerun()
                    else: st.error(f"Error: {rs}")

        # 3. CARGA EVIDENCIA
        else:
            evt = st.session_state.selected_event
            fields = evt['fields']

            # FUNCION CORE AUTO-UPLOAD
            def render_celda_auto(columna, key, label, fields_dict):
                with columna:
                    st.markdown(f'<p class="caption-text">{label}</p>', unsafe_allow_html=True)
                    if fields_dict.get(key):
                        url_img = fields_dict[key][0]['url']
                        st.image(url_img, use_container_width=True)
                        if st.button("🗑️ Eliminar", key=f"del_{evt['id']}_{key}", type="secondary", use_container_width=True):
                            with st.spinner("Borrando..."):
                                if delete_field_from_airtable(st.session_state.current_base_id, st.session_state.current_table_id, evt['id'], key):
                                    del st.session_state.selected_event['fields'][key]
                                    st.rerun()
                                else: st.error("Error al borrar")
                    else:
                        file = st.file_uploader(key, key=f"up_{evt['id']}_{key}", label_visibility="collapsed", type=['jpg','png','jpeg','webp'])
                        if file is not None:
                            file_optimizado = comprimir_imagen_webp(file)
                            with st.spinner(f"Subiendo {label}..."):
                                try:
                                    resp = cloudinary.uploader.upload(file_optimizado, resource_type="image", format="webp")
                                    payload = {key: [{"url": resp['secure_url']}]}
                                    if upload_evidence_to_airtable(st.session_state.current_base_id, st.session_state.current_table_id, evt['id'], payload):
                                        st.session_state.selected_event['fields'].update(payload)
                                        st.rerun()
                                    else: st.error("Error Airtable")
                                except Exception as e: st.error(f"Error: {str(e)}")

            if st.button("⬅️ REGRESAR A LISTADO DE EVENTOS", use_container_width=True, type="secondary"):
                st.session_state.selected_event = None; st.rerun()

            st.divider()
            
            loc_corta = obtener_ubicacion_corta(fields)
            fecha_fmt = formatear_fecha_larga(fields.get('Fecha'))
            hora = fields.get('Hora', '--')
            
            st.markdown(f"### 📸 {fields.get('Tipo')} - {loc_corta}")
            st.markdown(f"**{fecha_fmt} | {hora}**")
            st.divider()

            # SECCIÓN 1: INICIO
            st.markdown("#### 1. Foto de Inicio")
            c1, c2 = st.columns(2)
            render_celda_auto(c1, "Foto de equipo", "Foto de Equipo", fields)

            # SECCIÓN 2: ACTIVIDAD
            st.markdown("#### 2. Fotos de Actividad")
            keys_act = ["Foto 01", "Foto 02", "Foto 03", "Foto 04", "Foto 05", "Foto 06", "Foto 07"]
            for i in range(0, len(keys_act), 2):
                col_row = st.columns(2)
                render_celda_auto(col_row[0], keys_act[i], keys_act[i], fields)
                if i + 1 < len(keys_act):
                    render_celda_auto(col_row[1], keys_act[i+1], keys_act[i+1], fields)

            # SECCIÓN 3: REPORTE
            is_sucursal = fields.get('Tipo') == "Actividad en Sucursal"
            t_sec3 = "3. Reporte y Lista" if is_sucursal else "3. Reporte Firmado"
            st.markdown(f"#### {t_sec3}")
            c_rep, c_list = st.columns(2)
            render_celda_auto(c_rep, "Reporte firmado", "Reporte Firmado", fields)
            if is_sucursal:
                render_celda_auto(c_list, "Lista de asistencia", "Lista de Asistencia", fields)
            
            st.divider()
            if st.button("⬅️ REGRESAR A LISTADO DE EVENTOS (FINAL)", use_container_width=True, type="secondary"):
                st.session_state.selected_event = None; st.rerun()
