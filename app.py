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
MASTER_ADMIN_PASS = "3spejoVenenoso$2099" 

# Configuración Inicial Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_CONFIG["cloud_name"],
    api_key=CLOUDINARY_CONFIG["api_key"],
    api_secret=CLOUDINARY_CONFIG["api_secret"]
)

# --- SUCURSALES (Definición Oficial) ---
# Se agregó Tehuacan
SUCURSALES_OFICIALES = [
    "Cordoba", "Orizaba", "Xalapa", "Puebla", 
    "Oaxaca", "Tuxtepec", "Boca del Río", "Tehuacan"
]

FILES_DB = "usuarios.json"
HISTORIAL_FILE = "historial_modificaciones.csv"
YEAR_ACTUAL = 2025 # Año fijo

# ==============================================================================
# 2. FUNCIONES DE UTILIDAD
# ==============================================================================

def formatear_fecha_larga(fecha_str):
    """
    Convierte '2025-01-25' a 'Sábado 25 de Enero de 2025'.
    Hecho manualmente para no depender de la configuración regional del servidor.
    """
    if not fecha_str: return "Fecha pendiente"
    
    dias = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
    meses = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
        7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    
    try:
        dt = datetime.strptime(fecha_str, "%Y-%m-%d")
        dia_semana = dias[dt.weekday()]
        mes_nombre = meses[dt.month]
        return f"{dia_semana} {dt.day:02d} de {mes_nombre} de {dt.year}"
    except:
        return fecha_str

def get_imagen_plantilla(tipo_evento):
    """
    Devuelve la URL o ruta de la imagen según el tipo de evento.
    Puedes guardar tus imágenes en una carpeta local llamada 'assets'.
    """
    # Diccionario de imágenes por defecto (URLs públicas o rutas locales)
    # Si tienes archivos locales, usa: "assets/volanteo.jpg"
    imagenes = {
        "Volanteo": "https://cdn-icons-png.flaticon.com/512/2983/2983677.png", 
        "Actividad en Sucursal": "https://cdn-icons-png.flaticon.com/512/921/921347.png",
        "Cobranza": "https://cdn-icons-png.flaticon.com/512/2645/2645897.png",
        "Default": "https://www.provident.com.mx/content/dam/provident-mexico/logos/logo-provident.png"
    }
    
    # Intenta buscar coincidencia parcial, si no, devuelve default
    tipo = str(tipo_evento).lower()
    if "volanteo" in tipo: return imagenes["Volanteo"]
    if "sucursal" in tipo: return imagenes["Actividad en Sucursal"]
    
    return imagenes["Default"]

def normalizar_texto(texto):
    if not isinstance(texto, str): return str(texto).lower()
    texto = unicodedata.normalize('NFD', texto)
    return ''.join(c for c in texto if unicodedata.category(c) != 'Mn').lower()

def cargar_usuarios():
    if not os.path.exists(FILES_DB):
        default_db = {
            "admin": {
                "password": MASTER_ADMIN_PASS,
                "role": "admin",
                "plazas": SUCURSALES_OFICIALES
            }
        }
        with open(FILES_DB, 'w') as f:
            json.dump(default_db, f)
        return default_db
    
    with open(FILES_DB, 'r') as f:
        return json.load(f)

def guardar_usuarios(db):
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
    plaza_norm = normalizar_texto(plaza)

    for rec in data:
        fields = rec.get('fields', {})
        fecha_dato = fields.get('Fecha')
        match_year = False
        if fecha_dato and str(fecha_dato).startswith(str(year)):
            match_year = True
            
        suc_dato = fields.get('Sucursal')
        match_plaza = False
        if suc_dato:
            if isinstance(suc_dato, list): val_suc = str(suc_dato[0])
            else: val_suc = str(suc_dato)
            if normalizar_texto(val_suc) == plaza_norm: match_plaza = True
        
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
            btn_ingresar = st.form_submit_button("Ingresar", use_container_width=True)
            
            if btn_ingresar:
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
    # --- SIDEBAR ---
    with st.sidebar:
        st.header(f"Hola, {st.session_state.user_name}")
        st.caption(f"Rol: {st.session_state.user_role.upper()}")
        st.divider()
        st.subheader("📅 Configuración")
        
        # Selección Base/Mesa
        bases_map = get_bases()
        if not bases_map: st.stop()
        base_name = st.selectbox("Base:", list(bases_map.keys()))
        base_id = bases_map[base_name]

        tables_map = get_tables(base_id)
        table_id = None
        if tables_map:
            table_name = st.selectbox("Mes:", list(tables_map.keys()))
            table_id = tables_map[table_name]
        
        # Selector de Plaza (Filtrado por permisos)
        plazas_permitidas = st.session_state.allowed_plazas
        if not plazas_permitidas:
            st.error("Sin plazas asignadas.")
            sel_plaza = None
        else:
            sel_plaza = st.selectbox("📍 Plaza:", plazas_permitidas)
            st.session_state.sucursal_actual = sel_plaza

        # Año Fijo
        sel_year = YEAR_ACTUAL

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

    # --- PESTAÑAS ADMIN / USER ---
    if st.session_state.user_role == "admin":
        tab_main, tab_users, tab_hist = st.tabs(["📂 Gestión de Eventos", "👥 Usuarios", "📜 Historial"])
        
        # --- TAB USUARIOS ---
        with tab_users:
            st.subheader("Gestión de Accesos")
            users_db = cargar_usuarios()
            with st.expander("➕ Nuevo Usuario", expanded=False):
                with st.form("user_mngt"):
                    c1, c2 = st.columns(2)
                    new_user = c1.text_input("Usuario (ID):")
                    new_pass = c2.text_input("Contraseña:", type="password")
                    new_role = st.selectbox("Rol:", ["user", "admin"])
                    new_plazas = st.multiselect("Sucursales:", SUCURSALES_OFICIALES)
                    if st.form_submit_button("Guardar"):
                        users_db[new_user] = {"password": new_pass, "role": new_role, "plazas": new_plazas}
                        guardar_usuarios(users_db)
                        st.success(f"Usuario {new_user} guardado.")
                        st.rerun()
            st.dataframe(pd.DataFrame([{"User":u, "Rol":d['role'], "Plazas":d['plazas']} for u,d in users_db.items()]), use_container_width=True)

        # --- TAB HISTORIAL ---
        with tab_hist:
            if os.path.exists(HISTORIAL_FILE):
                st.dataframe(pd.read_csv(HISTORIAL_FILE).sort_values("Fecha", ascending=False), use_container_width=True)
            else: st.info("Vacío")
        
        main_area = tab_main
    else:
        main_area = st.container()

    # --- ÁREA PRINCIPAL ---
    with main_area:
        st.title(f"Gestión: {st.session_state.get('current_plaza_view', sel_plaza)}")

        # VISTA A: LISTADO DE EVENTOS (NUEVO DISEÑO 2 COLUMNAS)
        if st.session_state.selected_event is None:
            if 'search_results' in st.session_state:
                recs = st.session_state.search_results
                if recs:
                    for r in recs:
                        f = r['fields']
                        
                        # Contenedor estilo tarjeta para cada evento
                        with st.expander(f"{f.get('Fecha')} - {f.get('Tipo', 'Evento')}", expanded=True):
                            
                            col_img, col_data = st.columns([1, 2.5])
                            
                            # --- COLUMNA 1: IMAGEN PLANTILLA ---
                            with col_img:
                                img_url = get_imagen_plantilla(f.get('Tipo'))
                                st.image(img_url, use_container_width=True)
                                
                            # --- COLUMNA 2: DATOS DEL EVENTO ---
                            with col_data:
                                # Fecha formateada
                                fecha_larga = formatear_fecha_larga(f.get('Fecha'))
                                st.markdown(f"### 🗓️ {fecha_larga}")
                                
                                st.markdown(f"""
                                **Tipo:** {f.get('Tipo', '--')}  
                                **📍 Punto:** {f.get('Punto de reunion', 'N/A')}  
                                **🛣️ Ruta:** {f.get('Ruta a seguir', 'N/A')}  
                                **🏙️ Municipio:** {f.get('Municipio', 'N/A')}  
                                **⏰ Hora:** {f.get('Hora', '--')}
                                """)
                                
                                c_btn_1, c_btn_2 = st.columns(2)
                                with c_btn_1:
                                    if st.button("📸 SUBIR EVIDENCIA", key=f"btn_{r['id']}", type="primary", use_container_width=True):
                                        st.session_state.selected_event = r
                                        st.rerun()
                                with c_btn_2:
                                    # Botón Reagendado (Solo visual por ahora)
                                    if st.button("⚠️ EVENTO REAGENDADO", key=f"re_{r['id']}", use_container_width=True):
                                        st.warning("Funcionalidad de reagendar pendiente de conectar con Airtable.")
                                        registrar_historial("Click Reagendar", st.session_state.user_name, st.session_state.sucursal_actual, f"Evento {f.get('Fecha')}")

                else:
                    if st.session_state.get('sucursal_actual'):
                        st.info(f"No hay eventos programados en {st.session_state.sucursal_actual}.")
            else:
                st.info("👈 Presiona 'ACTUALIZAR EVENTOS' en la barra lateral.")

        # VISTA B: FORMULARIO DE CARGA (MODIFICADO)
        else:
            evt = st.session_state.selected_event
            fields = evt['fields']
            
            if st.button("⬅️ VOLVER", type="secondary"):
                st.session_state.selected_event = None
                st.rerun()

            st.markdown(f"### 📸 Cargar Evidencia: {fields.get('Tipo')}")
            st.caption(f"{formatear_fecha_larga(fields.get('Fecha'))}")
            
            with st.form("evidence_form"):
                uploads = {}

                # 1. FOTO EQUIPO
                st.markdown("#### 1. Foto de Equipo")
                c1, c2 = st.columns([3,1])
                uploads['Foto de equipo'] = c1.file_uploader("Subir imagen", type=['jpg','png','jpeg'], key="u_eq")
                if fields.get('Foto de equipo'): c2.image(fields['Foto de equipo'][0]['url'], width=100)
                
                # 2. ACTIVIDAD (GRID)
                st.markdown("#### 2. Fotos de Actividad")
                grid = [("Foto 01","Foto 02"), ("Foto 03","Foto 04"), ("Foto 05","Foto 06"), ("Foto 07",None)]
                for l_izq, l_der in grid:
                    col_a, col_b = st.columns(2)
                    with col_a:
                        uploads[l_izq] = st.file_uploader(l_izq, type=['jpg','png'], key=f"k_{l_izq}", label_visibility="collapsed")
                    if l_der:
                        with col_b:
                            uploads[l_der] = st.file_uploader(l_der, type=['jpg','png'], key=f"k_{l_der}", label_visibility="collapsed")
                
                st.markdown("---")
                
                # 3. REPORTE FIRMADO (AHORA SOLO IMAGEN)
                st.markdown("#### 3. Reporte Firmado")
                c3, c4 = st.columns([3,1])
                # Cambio: Solo acepta imagenes
                uploads['Reporte firmado'] = c3.file_uploader("Foto del Reporte", type=['jpg','png','jpeg'], key="u_rep")
                if fields.get('Reporte firmado'): c4.image(fields['Reporte firmado'][0]['url'], width=100)

                # 4. LISTA ASISTENCIA (CONDICIONAL - SOLO IMAGEN)
                if fields.get('Tipo') == "Actividad en Sucursal":
                    st.markdown("---")
                    st.markdown("#### 4. Lista de Asistencia")
                    c5, c6 = st.columns([3,1])
                    # Cambio: Solo acepta imagenes
                    uploads['Lista de asistencia'] = c5.file_uploader("Foto de Lista", type=['jpg','png','jpeg'], key="u_lst")
                    if fields.get('Lista de asistencia'): c6.image(fields['Lista de asistencia'][0]['url'], width=100)

                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("💾 GUARDAR CAMBIOS", type="primary", use_container_width=True):
                    # --- PROCESO DE SUBIDA ---
                    files_to = {k:v for k,v in uploads.items() if v}
                    if not files_to:
                        st.warning("Nada para subir.")
                    else:
                        prog = st.progress(0)
                        upd_dict = {}
                        tot = len(files_to)
                        try:
                            for i, (k, f_obj) in enumerate(files_to.items()):
                                res = cloudinary.uploader.upload(f_obj)
                                upd_dict[k] = [{"url": res['secure_url']}]
                                prog.progress((i+1)/(tot+1))
                            
                            if upload_evidence_to_airtable(st.session_state.current_base_id, st.session_state.current_table_id, evt['id'], upd_dict):
                                st.success("Guardado Exitosamente")
                                st.session_state.selected_event['fields'].update(upd_dict)
                                st.rerun()
                            else: st.error("Error Airtable")
                        except Exception as e: st.error(str(e))
