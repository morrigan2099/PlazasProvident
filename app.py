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

# --- CSS PARA OCULTAR SIDEBAR Y DAR ESTILO A TOPBAR ---
st.markdown("""
<style>
    /* Ocultar la sidebar nativa de Streamlit */
    [data-testid="stSidebar"] {display: none;}
    [data-testid="collapsedControl"] {display: none;}
    
    /* Estilo para la tarjeta del evento */
    .event-card {
        padding: 10px;
        border-radius: 10px;
        background-color: #f9f9f9;
        margin-bottom: 10px;
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
    texto = texto.lower()
    return re.sub(r'[^a-z0-9]', '', texto)

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

def registrar_historial(accion, usuario, sucursal, detalles):
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nuevo_registro = {"Fecha": fecha, "Usuario": usuario, "Sucursal": sucursal, "Acción": accion, "Detalles": detalles}
    df_new = pd.DataFrame([nuevo_registro])
    if not os.path.exists(HISTORIAL_FILE): df_new.to_csv(HISTORIAL_FILE, index=False)
    else: df_new.to_csv(HISTORIAL_FILE, mode='a', header=False, index=False)

# ==============================================================================
# 3. FUNCIONES AIRTABLE
# ==============================================================================
@st.cache_data(ttl=600)
def get_bases():
    url = "https://api.airtable.com/v0/meta/bases"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200: return {b['name']: b['id'] for b in r.json().get('bases', [])}
    except: pass
    return {}

@st.cache_data(ttl=60)
def get_tables(base_id):
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200: return {t['name']: t['id'] for t in r.json().get('tables', [])}
    except: pass
    return {}

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
# 6. APP PRINCIPAL (TOPBAR + CONTENIDO)
# ==============================================================================
else:
    # --- HEADER / BARRA SUPERIOR DE USUARIO ---
    c_logo, c_user, c_logout = st.columns([1, 6, 1])
    with c_logo:
        st.image("https://www.provident.com.mx/content/dam/provident-mexico/logos/logo-provident.png", width=100)
    with c_user:
        st.markdown(f"#### 👤 {st.session_state.user_name} | {st.session_state.user_role.upper()}")
    with c_logout:
        if st.button("Salir", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()
    
    st.divider()

    # --- TOPBAR (BARRA DE FILTROS) ---
    # Usamos container para agrupar los filtros horizontalmente
    with st.container():
        col_base, col_mes, col_plaza, col_btn = st.columns([2, 2, 2, 2])
        
        # Filtro 1: Base
        with col_base:
            bases_map = get_bases()
            if not bases_map: st.stop()
            base_name = st.selectbox("📂 Base de Datos", list(bases_map.keys()))
            base_id = bases_map[base_name]

        # Filtro 2: Mes
        with col_mes:
            tables_map = get_tables(base_id)
            table_id = None
            if tables_map:
                table_name = st.selectbox("📅 Mes", list(tables_map.keys()))
                table_id = tables_map[table_name]
            else: st.selectbox("Mes", ["Sin datos"], disabled=True)

        # Filtro 3: Plaza
        with col_plaza:
            plazas_permitidas = st.session_state.allowed_plazas
            if not plazas_permitidas:
                st.error("Sin permisos")
                sel_plaza = None
            else:
                sel_plaza = st.selectbox("📍 Plaza", plazas_permitidas)
                st.session_state.sucursal_actual = sel_plaza

        # Botón Actualizar
        with col_btn:
            st.write("") # Espacio para alinear verticalmente con los inputs
            st.write("") 
            if sel_plaza and st.button("🔄 CARGAR EVENTOS", type="primary", use_container_width=True):
                st.session_state.selected_event = None
                st.session_state.search_results = get_records(base_id, table_id, YEAR_ACTUAL, sel_plaza)
                st.session_state.current_base_id = base_id
                st.session_state.current_table_id = table_id
                st.session_state.current_plaza_view = sel_plaza

    st.divider()

    # --- ÁREA DE CONTENIDO (ADMIN TABS O USER LIST) ---
    if st.session_state.user_role == "admin":
        tab_main, tab_users, tab_hist, tab_debug = st.tabs(["📂 Eventos", "👥 Usuarios", "📜 Historial", "🔧 Debug"])
        
        # ... (Código de pestañas Admin igual que antes) ...
        with tab_users:
            users_db = cargar_usuarios()
            with st.expander("➕ Crear/Editar Usuario"):
                with st.form("user_mngt"):
                    c1, c2 = st.columns(2)
                    nu = c1.text_input("Usuario")
                    np = c2.text_input("Pass", type="password")
                    nr = st.selectbox("Rol", ["user", "admin"])
                    npl = st.multiselect("Plazas", SUCURSALES_OFICIALES)
                    if st.form_submit_button("Guardar"):
                        users_db[nu] = {"password": np, "role": nr, "plazas": npl}
                        guardar_usuarios(users_db)
                        st.success("Guardado")
                        st.rerun()
            st.dataframe(pd.DataFrame([{"U":k, "R":v['role'], "P":v['plazas']} for k,v in users_db.items()]), use_container_width=True)
        
        with tab_hist:
             if os.path.exists(HISTORIAL_FILE): st.dataframe(pd.read_csv(HISTORIAL_FILE).sort_values("Fecha", ascending=False), use_container_width=True)

        with tab_debug:
            st.write(f"Assets en: {os.path.join(os.getcwd(), 'assets')}")
            if os.path.exists("assets"): st.write(os.listdir("assets"))
            
        main_area = tab_main
    else:
        main_area = st.container()

    # --- VISTA PRINCIPAL DE EVENTOS ---
    with main_area:
        if 'current_plaza_view' in st.session_state:
            st.markdown(f"### 📋 Eventos en {st.session_state.current_plaza_view} ({YEAR_ACTUAL})")
        
        # VISTA A: LISTADO
        if st.session_state.selected_event is None:
            if 'search_results' in st.session_state:
                recs = st.session_state.search_results
                if recs:
                    for r in recs:
                        f = r['fields']
                        
                        # --- INICIO TARJETA DE EVENTO ---
                        with st.expander(f"{f.get('Fecha')} | {f.get('Tipo', 'Evento')}", expanded=True):
                            
                            # Layout: Imagen (1/3) - Info (2/3)
                            col_img, col_data = st.columns([1, 2.5])
                            
                            with col_img:
                                img_path = get_imagen_plantilla(f.get('Tipo'))
                                st.image(img_path, use_container_width=True)
                            
                            # --- AQUÍ ESTÁ EL CAMBIO DE FORMATO (1 POR LÍNEA) ---
                            with col_data:
                                fecha_fmt = formatear_fecha_larga(f.get('Fecha'))
                                
                                # 1. Fecha como título grande
                                st.markdown(f"### 🗓️ {fecha_fmt}")
                                
                                # 2. Lista de datos (Uno por línea)
                                st.markdown(f"**Tipo:** {f.get('Tipo', '--')}")
                                st.markdown(f"**📍 Punto:** {f.get('Punto de reunion', 'N/A')}")
                                st.markdown(f"**🛣️ Ruta:** {f.get('Ruta a seguir', 'N/A')}") # Emoji de carretera/ruta
                                st.markdown(f"**🏙️ Municipio:** {f.get('Municipio', 'N/A')}")
                                st.markdown(f"**⏰ Hora:** {f.get('Hora', '--')}")

                                st.markdown("<br>", unsafe_allow_html=True)
                                
                                # Botones de acción
                                cb1, cb2 = st.columns(2)
                                with cb1:
                                    if st.button("📸 SUBIR EVIDENCIA", key=f"b_{r['id']}", type="primary", use_container_width=True):
                                        st.session_state.selected_event = r
                                        st.rerun()
                                with cb2:
                                    if st.button("⚠️ EVENTO REAGENDADO", key=f"r_{r['id']}", use_container_width=True):
                                        st.toast("Funcionalidad pendiente")
                        # --- FIN TARJETA ---
                        
                else:
                    if st.session_state.get('sucursal_actual'): st.info("No hay eventos programados.")
                    else: st.warning("Por favor carga eventos usando el botón superior.")
            else:
                st.info("👆 Selecciona filtros y presiona 'CARGAR EVENTOS'.")

        # VISTA B: CARGA (Sin cambios mayores, solo mantener funcionalidad)
        else:
            evt = st.session_state.selected_event
            fields = evt['fields']
            
            if st.button("⬅️ REGRESAR A LISTADO"):
                st.session_state.selected_event = None
                st.rerun()
            
            st.markdown(f"### 📸 Cargando para: {fields.get('Tipo')}")
            st.caption(formatear_fecha_larga(fields.get('Fecha')))
            
            with st.form("upload_form"):
                uploads = {}
                c1, c2 = st.columns([3,1])
                st.caption("1. Foto Equipo")
                uploads['Foto de equipo'] = c1.file_uploader("Equipo", key="ue", label_visibility="collapsed")
                if fields.get('Foto de equipo'): c2.image(fields['Foto de equipo'][0]['url'], width=80)
                
                st.caption("2. Actividad")
                g = [("Foto 01","Foto 02"), ("Foto 03","Foto 04"), ("Foto 05","Foto 06"), ("Foto 07",None)]
                for l1, l2 in g:
                    ca, cb = st.columns(2)
                    uploads[l1] = ca.file_uploader(l1, key=l1, label_visibility="collapsed")
                    if fields.get(l1): ca.image(fields[l1][0]['url'], width=80)
                    if l2:
                        uploads[l2] = cb.file_uploader(l2, key=l2, label_visibility="collapsed")
                        if fields.get(l2): cb.image(fields[l2][0]['url'], width=80)
                
                st.caption("3. Reporte")
                c3, c4 = st.columns([3,1])
                uploads['Reporte firmado'] = c3.file_uploader("Reporte", key="ur", label_visibility="collapsed")
                if fields.get('Reporte firmado'): c4.image(fields['Reporte firmado'][0]['url'], width=80)

                if fields.get('Tipo') == "Actividad en Sucursal":
                    st.caption("4. Lista")
                    c5, c6 = st.columns([3,1])
                    uploads['Lista de asistencia'] = c5.file_uploader("Lista", key="ul", label_visibility="collapsed")
                    if fields.get('Lista de asistencia'): c6.image(fields['Lista de asistencia'][0]['url'], width=80)

                if st.form_submit_button("💾 GUARDAR", type="primary", use_container_width=True):
                    # Lógica de subida (igual que antes)
                    files = {k:v for k,v in uploads.items() if v}
                    if not files: st.warning("Selecciona archivos")
                    else:
                        pr = st.progress(0)
                        ud = {}
                        try:
                            for i, (k, f) in enumerate(files.items()):
                                r = cloudinary.uploader.upload(f)
                                ud[k] = [{"url": r['secure_url']}]
                                pr.progress((i+1)/(len(files)+1))
                            if upload_evidence_to_airtable(st.session_state.current_base_id, st.session_state.current_table_id, evt['id'], ud):
                                st.success("¡Listo!")
                                st.session_state.selected_event['fields'].update(ud)
                                st.rerun()
                            else: st.error("Error Airtable")
                        except Exception as e: st.error(str(e))
