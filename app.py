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

# ==============================================================================
# 1. CONFIGURACIÓN Y ESTILOS
# ==============================================================================
st.set_page_config(page_title="Gestor Provident", layout="wide")

# --- CSS: ESTILO MINIMALISTA PARA EL UPLOADER ---
st.markdown("""
<style>
    /* Ocultar sidebar y controles */
    [data-testid="stSidebar"] {display: none;}
    [data-testid="collapsedControl"] {display: none;}
    
    /* --- HACK PARA EL UPLOADER MINIMALISTA (CUADRO CON +) --- */
    
    /* 1. Ocultar el texto de "Limit 200MB" */
    [data-testid="stFileUploader"] small {
        display: none;
    }
    
    /* 2. Ocultar el botón original y el texto "Drag and drop" */
    [data-testid="stFileUploader"] button {
        display: none;
    }
    [data-testid="stFileUploader"] section > div {
        display: none; /* Oculta los textos internos */
    }
    
    /* 3. Estilizar la caja para que sea un cuadro simple */
    [data-testid="stFileUploader"] section {
        min-height: 0px !important;
        padding: 10px !important;
        background-color: #f0f2f6; /* Gris claro */
        border: 2px dashed #cccccc;
        border-radius: 10px;
        align-items: center;
        justify-content: center;
        display: flex;
    }
    
    /* 4. Agregar el signo de MÁS (+) */
    [data-testid="stFileUploader"] section::after {
        content: "➕";  /* Emoji o carácter de más */
        font-size: 30px;
        color: #888;
        visibility: visible;
        display: block;
    }

    /* Efecto al pasar el mouse */
    [data-testid="stFileUploader"] section:hover {
        background-color: #e0e2e6;
        border-color: #999;
    }

    /* Cuando ya hay archivo cargado (éxito) */
    .uploaded-success {
        border: 2px solid #28a745 !important;
    }
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
# 2. FUNCIONES DE UTILIDAD
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

def get_imagen_plantilla(tipo_evento):
    carpeta_assets = "assets" 
    url_default = "https://www.provident.com.mx/content/dam/provident-mexico/logos/logo-provident.png"
    if not tipo_evento: tipo_evento = "default"
    if not os.path.exists(carpeta_assets): return url_default
    clave_buscada = limpiar_clave(str(tipo_evento))
    try:
        archivos = os.listdir(carpeta_assets)
        for archivo in archivos:
            if limpiar_clave(os.path.splitext(archivo)[0]) == clave_buscada:
                return os.path.join(carpeta_assets, archivo)
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
# 5. LOGIN
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
            if st.form_submit_button("Ingresar", use_container_width=True):
                users_db = cargar_usuarios()
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
    # HEADER
    c_logo, c_user, c_logout = st.columns([1, 6, 1])
    with c_logo: st.image("https://www.provident.com.mx/content/dam/provident-mexico/logos/logo-provident.png", width=100)
    with c_user: st.markdown(f"#### 👤 {st.session_state.user_name} | {st.session_state.user_role.upper()}")
    with c_logout:
        if st.button("Salir", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()
    st.divider()

    # TOPBAR
    with st.container():
        col_base, col_mes, col_plaza, col_btn = st.columns([2, 2, 2, 2])
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
        with col_btn:
            st.write(""); st.write("")
            if sel_plaza and base_id and table_id and st.button("🔄 CARGAR EVENTOS", type="primary", use_container_width=True):
                st.session_state.selected_event = None; st.session_state.rescheduling_event = None
                st.session_state.search_results = get_records(base_id, table_id, YEAR_ACTUAL, sel_plaza)
                st.session_state.current_base_id = base_id; st.session_state.current_table_id = table_id; st.session_state.current_plaza_view = sel_plaza
    st.divider()

    # --- PESTAÑAS ADMIN ---
    if st.session_state.user_role == "admin":
        tab_main, tab_users, tab_config_db, tab_hist = st.tabs(["📂 Eventos", "👥 Usuarios", "⚙️ Configuración DB", "📜 Historial"])
        
        # --- TAB USUARIOS ---
        with tab_users:
            users_db = cargar_usuarios()
            st.subheader("Gestión de Accesos")
            opciones_usuarios = ["(Crear Nuevo)"] + list(users_db.keys())
            seleccion = st.selectbox("🔍 Seleccionar Usuario para Editar:", opciones_usuarios)
            if seleccion == "(Crear Nuevo)": val_user = ""; val_pass = ""; val_role = "user"; val_plazas = []; es_edicion = False
            else: data_u = users_db[seleccion]; val_user = seleccion; val_pass = data_u.get('password', ''); val_role = data_u.get('role', 'user'); val_plazas = data_u.get('plazas', []); es_edicion = True

            with st.form("form_usuarios_admin"):
                c1, c2 = st.columns(2)
                new_user = c1.text_input("Usuario (ID)", value=val_user)
                new_pass = c2.text_input("Contraseña", value=val_pass)
                c3, c4 = st.columns(2)
                new_role = c3.selectbox("Rol", ["user", "admin"], index=0 if val_role=="user" else 1)
                new_plazas = c4.multiselect("Plazas Permitidas", SUCURSALES_OFICIALES, default=[p for p in val_plazas if p in SUCURSALES_OFICIALES])
                st.markdown("<br>", unsafe_allow_html=True)
                cols_btns = st.columns([1, 1, 4])
                submitted = cols_btns[0].form_submit_button("💾 Guardar Datos", type="primary")
                if submitted:
                    if not new_user or not new_pass: st.error("Usuario y contraseña obligatorios.")
                    else:
                        if es_edicion and new_user != seleccion: del users_db[seleccion]
                        users_db[new_user] = {"password": new_pass, "role": new_role, "plazas": new_plazas}
                        guardar_usuarios(users_db); st.success(f"Usuario {new_user} guardado."); st.rerun()

            if es_edicion:
                st.markdown("---")
                if st.button("🗑️ Eliminar Usuario", type="secondary"):
                    if seleccion in users_db: del users_db[seleccion]; guardar_usuarios(users_db); st.warning(f"Usuario eliminado."); st.rerun()

            st.markdown("---")
            st.markdown("#### Lista de Usuarios Activos")
            df_users = pd.DataFrame([{"Usuario": k, "Rol": v['role'], "Plazas": ", ".join(v['plazas'])} for k,v in users_db.items()])
            st.dataframe(df_users, use_container_width=True)

        # --- TAB CONFIG DB ---
        with tab_config_db:
            st.subheader("Control de Visibilidad de Base de Datos")
            current_config = cargar_config_db(); current_bases = current_config.get("bases", {}); current_tables = current_config.get("tables", {})
            with st.spinner("Conectando Airtable..."): real_bases = api_get_all_bases()
            if real_bases:
                with st.form("db_config_form"):
                    bases_sel = st.multiselect("Bases Visibles:", list(real_bases.keys()), default=[n for n in real_bases if n in current_bases])
                    new_b = {}; new_t = {}
                    for b_name in bases_sel:
                        b_id = real_bases[b_name]; new_b[b_name] = b_id
                        real_tables = api_get_all_tables(b_id); prev_t = current_tables.get(b_id, {})
                        t_sel = st.multiselect(f"Tablas para {b_name}:", list(real_tables.keys()), default=[n for n in real_tables if n in prev_t])
                        new_t[b_id] = {n: real_tables[n] for n in t_sel}
                    if st.form_submit_button("💾 Guardar Configuración"):
                        guardar_config_db({"bases": new_b, "tables": new_t}); st.success("Guardado."); st.rerun()

        with tab_hist:
             if os.path.exists(HISTORIAL_FILE): st.dataframe(pd.read_csv(HISTORIAL_FILE).sort_values("Fecha", ascending=False), use_container_width=True)
        main_area = tab_main
    else: main_area = st.container()

    # VISTAS PRINCIPALES
    with main_area:
        if 'current_plaza_view' in st.session_state:
            st.markdown(f"### 📋 Eventos en {st.session_state.current_plaza_view} ({YEAR_ACTUAL})")

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
                                    if c2.button("⚠️ EVENTO REAGENDADO", key=f"r_{r['id']}", use_container_width=True): st.session_state.rescheduling_event=r; st.rerun()
                else: 
                    if st.session_state.get('sucursal_actual'): st.info("No hay eventos.")
                    else: st.warning("Carga eventos.")
            else: st.info("👆 Cargar eventos.")

        # 2. REAGENDAR
        elif st.session_state.rescheduling_event is not None:
            evt = st.session_state.rescheduling_event; f_orig = evt['fields']
            if st.button("⬅️ CANCELAR"): st.session_state.rescheduling_event = None; st.rerun()
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
            evt = st.session_state.selected_event; fields = evt['fields']
            if st.button("⬅️ REGRESAR"): st.session_state.selected_event = None; st.rerun()
            st.markdown(f"### 📸 Cargar Evidencia: {fields.get('Tipo')}")
            with st.form("upload_form"):
                uploads = {}
                st.caption("1. Foto Equipo"); c1,c2=st.columns([3,1]); uploads['Foto de equipo']=c1.file_uploader("Eq",key="ue",label_visibility="collapsed", type=['jpg','png','jpeg'])
                if fields.get('Foto de equipo'): c2.image(fields['Foto de equipo'][0]['url'],width=80)
                st.caption("2. Actividad"); g=[("Foto 01","Foto 02"),("Foto 03","Foto 04"),("Foto 05","Foto 06"),("Foto 07",None)]
                for l1,l2 in g:
                    ca,cb=st.columns(2); uploads[l1]=ca.file_uploader(l1,key=l1,label_visibility="collapsed", type=['jpg','png','jpeg'])
                    if fields.get(l1): ca.image(fields[l1][0]['url'],width=80)
                    if l2:
                        uploads[l2]=cb.file_uploader(l2,key=l2,label_visibility="collapsed", type=['jpg','png','jpeg'])
                        if fields.get(l2): cb.image(fields[l2][0]['url'],width=80)
                st.caption("3. Reporte"); c3,c4=st.columns([3,1]); uploads['Reporte firmado']=c3.file_uploader("Rep",key="ur",label_visibility="collapsed", type=['jpg','png','jpeg'])
                if fields.get('Reporte firmado'): c4.image(fields['Reporte firmado'][0]['url'],width=80)
                if fields.get('Tipo') == "Actividad en Sucursal":
                    st.caption("4. Lista"); c5,c6=st.columns([3,1]); uploads['Lista de asistencia']=c5.file_uploader("Lis",key="ul",label_visibility="collapsed", type=['jpg','png','jpeg'])
                    if fields.get('Lista de asistencia'): c6.image(fields['Lista de asistencia'][0]['url'],width=80)
                if st.form_submit_button("💾 GUARDAR", type="primary", use_container_width=True):
                    files={k:v for k,v in uploads.items() if v}; pr=st.progress(0); ud={}; tot=len(files)
                    if not files: st.warning("Nada para subir")
                    else:
                        try:
                            for i,(k,f) in enumerate(files.items()): r=cloudinary.uploader.upload(f); ud[k]=[{"url":r['secure_url']}]; pr.progress((i+1)/(tot+1))
                            if upload_evidence_to_airtable(st.session_state.current_base_id, st.session_state.current_table_id, evt['id'], ud): st.success("¡Listo!"); st.session_state.selected_event['fields'].update(ud); st.rerun()
                            else: st.error("Error Airtable")
                        except Exception as e: st.error(str(e))
