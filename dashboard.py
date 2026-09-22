# -*- coding: utf-8 -*-
import streamlit as st
import requests
import os

# Configuración de página de Streamlit
st.set_page_config(
    page_title="AVFenix Agent - Panel de Administración",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos personalizados para mejorar el diseño
st.markdown("""
    <style>
    .main-title {
        font-size: 38px;
        font-weight: bold;
        color: #1E3A8A;
        margin-bottom: 5px;
    }
    .sub-title {
        font-size: 16px;
        color: #4B5563;
        margin-bottom: 25px;
    }
    .metric-card {
        background-color: #F3F4F6;
        border-radius: 8px;
        padding: 15px;
        border-left: 5px solid #3B82F6;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONFIGURACIÓN EN LA BARRA LATERAL ---
st.sidebar.image("https://img.icons8.com/fluency/96/artificial-intelligence.png", width=80)
st.sidebar.markdown("### 🤖 AVFenix Agent")
st.sidebar.markdown("Panel de control unificado para cargar documentos, scrapear sitios web y probar el comportamiento del agente RAG.")

st.sidebar.markdown("---")
st.sidebar.markdown("#### ⚙️ Configuración de API")
api_base_url = st.sidebar.text_input(
    "URL del Servidor Flask",
    value="http://localhost:5000",
    help="La URL donde se está ejecutando tu API backend en Flask."
)

# Comprobar la salud del backend
backend_healthy = False
db_chunks = 0
try:
    health_resp = requests.get(f"{api_base_url}/api/health", timeout=3)
    if health_resp.status_code == 200:
        backend_healthy = True
        db_chunks = health_resp.json().get("database_chunks", 0)
except Exception:
    backend_healthy = False

# Indicador de estado en la barra lateral
if backend_healthy:
    st.sidebar.success("🟢 Conectado al Backend")
else:
    st.sidebar.error("🔴 Servidor Desconectado")
    st.sidebar.warning("Asegúrate de que 'app.py' se esté ejecutando localmente en el puerto configurado.")

st.sidebar.markdown("---")
st.sidebar.markdown("#### 💬 Parámetros del Chat")
output_mode_label = st.sidebar.selectbox(
    "Modo de Respuesta del Agente",
    options=["Solo Texto", "Solo Audio", "Ambos (Texto + Audio)"],
    index=0
)

mode_mapping = {
    "Solo Texto": "text",
    "Solo Audio": "audio",
    "Ambos (Texto + Audio)": "both"
}
output_mode = mode_mapping[output_mode_label]

st.sidebar.markdown("---")
st.sidebar.info("💡 **RAG Integrado**: Sube documentos o añade URLs para dotar de memoria y contexto exclusivo a tu agente de IA.")

# --- CUERPO PRINCIPAL ---
st.markdown('<div class="main-title">Panel de Control AVFenix</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Carga documentos, scrapea enlaces web y prueba sugerencias clickeables de avance.</div>', unsafe_allow_html=True)

# Crear pestañas principales
tab1, tab2 = st.tabs(["📂 Gestión de Conocimientos", "💬 Consola de Chat"])

# --- TAB 1: GESTIÓN DE CONOCIMIENTOS ---
with tab1:
    st.markdown("### 📄 Base de Conocimientos")
    st.markdown("Agrega archivos en formato **PDF / DOCX** o **scrapea URLs web** para que el agente aprenda sobre tu tema. El sistema aplicará *Semantic Chunking* de manera automática para fragmentar y entender las ideas del texto.")
    
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.markdown(
            f'<div class="metric-card">'
            f'<span style="font-size:14px;color:#6B7280;">Estado de API Backend</span><br>'
            f'<span style="font-size:24px;font-weight:bold;color:{"#10B981" if backend_healthy else "#EF4444"};">{"ACTIVO" if backend_healthy else "INACTIVO"}</span>'
            f'</div>',
            unsafe_allow_html=True
        )
    with col_m2:
        st.markdown(
            f'<div class="metric-card">'
            f'<span style="font-size:14px;color:#6B7280;">Total de Fragmentos en Base Vectorial</span><br>'
            f'<span style="font-size:24px;font-weight:bold;color:#3B82F6;">{db_chunks} fragmentos</span>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown("---")
    
    col_upload, col_list = st.columns([1, 1])
    
    with col_upload:
        st.markdown("#### 📤 Cargar Nuevo Documento (PDF / DOCX)")
        uploaded_file = st.file_uploader(
            "Arrastra o selecciona un archivo para indexar",
            type=["pdf", "docx"],
            help="Límite recomendado de 20MB. Formatos soportados: PDF y DOCX"
        )
        
        if uploaded_file is not None:
            if not backend_healthy:
                st.error("No se puede cargar el archivo porque el servidor Flask está desconectado.")
            else:
                if st.button("🚀 Indexar Documento en el Agente", use_container_width=True):
                    with st.spinner("Procesando documento... Extrayendo texto y dividiendo semánticamente."):
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        try:
                            upload_url = f"{api_base_url}/api/upload"
                            resp = requests.post(upload_url, files=files, timeout=60)
                            if resp.status_code == 200:
                                res_json = resp.json()
                                st.success(f"¡Excelente! '{res_json['filename']}' ha sido indexado con éxito.")
                                st.info(f"Se crearon **{res_json['chunks_count']} fragmentos semánticos**.")
                                st.rerun()
                            else:
                                error_msg = resp.json().get("error", "Error desconocido en el backend.")
                                st.error(f"Error del servidor ({resp.status_code}): {error_msg}")
                        except Exception as e:
                            st.error(f"Error de conexión al subir: {str(e)}")

        st.markdown("---")
        st.markdown("#### 🌐 Anexar Sitio Web (Scraping)")
        url_to_scrape = st.text_input("Ingresa la URL del sitio web a scrapear", placeholder="https://ejemplo.com/pagina")
        if st.button("🌐 Scrapear e Indexar URL", use_container_width=True):
            if not url_to_scrape.strip():
                st.warning("Por favor ingresa una URL válida.")
            elif not backend_healthy:
                st.error("Servidor Flask desconectado.")
            else:
                with st.spinner("Scrapeando página web e indexando en la base vectorial..."):
                    try:
                        scrape_url_endpoint = f"{api_base_url}/api/scrape_url"
                        resp = requests.post(scrape_url_endpoint, json={"url": url_to_scrape.strip()}, timeout=30)
                        if resp.status_code == 200:
                            res_json = resp.json()
                            st.success(f"¡Éxito! Sitio web '{url_to_scrape}' indexado correctamente.")
                            st.info(f"Se crearon **{res_json['chunks_count']} fragmentos semánticos**.")
                            st.rerun()
                        else:
                            error_msg = resp.json().get("error", "Error desconocido.")
                            st.error(f"Error ({resp.status_code}): {error_msg}")
                    except Exception as e:
                        st.error(f"Error de conexión: {str(e)}")
                            
    with col_list:
        st.markdown("#### 📚 Fuentes Cargadas (Archivos y Webs)")
        if not backend_healthy:
            st.warning("Conecta el servidor para listar las fuentes activas.")
        else:
            try:
                docs_url = f"{api_base_url}/api/documents"
                resp = requests.get(docs_url, timeout=5)
                if resp.status_code == 200:
                    documents = resp.json().get("documents", [])
                    if not documents:
                        st.info("Aún no hay fuentes en la base de conocimientos. ¡Sube un archivo o scrapea una URL!")
                    else:
                        for doc in documents:
                            col_doc_name, col_btn = st.columns([4, 1])
                            with col_doc_name:
                                icon = "🌐" if doc.startswith("WEB_") else "📄"
                                st.markdown(f"{icon} **{doc}**")
                            with col_btn:
                                if st.button("🗑️ Borrar", key=f"del_{doc}", use_container_width=True):
                                    with st.spinner("Borrando del índice..."):
                                        del_url = f"{api_base_url}/api/delete/{doc}"
                                        del_resp = requests.delete(del_url, timeout=5)
                                        if del_resp.status_code == 200:
                                            st.toast(f"Fuente '{doc}' eliminada correctamente.", icon="🗑️")
                                            st.rerun()
                                        else:
                                            st.error("No se pudo eliminar la fuente.")
                else:
                    st.error("Error al recuperar la lista de fuentes.")
            except Exception as e:
                st.error(f"Error de conexión: {str(e)}")

# --- TAB 2: CONSOLA DE CHAT ---
with tab2:
    st.markdown("### 💬 Interacción en Tiempo Real")
    st.markdown("Escribe tu pregunta o haz clic en las **sugerencias dinámicas de avance** para explorar el conocimiento extraído.")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "pending_query" not in st.session_state:
        st.session_state.pending_query = None

    # Mostrar mensajes previos
    for msg_idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
            if "sources" in msg and msg["sources"]:
                with st.expander("🔍 Ver fuentes de esta respuesta"):
                    for src in msg["sources"]:
                        st.markdown(f"📍 **{src['filename']}** (Sección/Pág. {src['page_number']}) — *Relevancia: {src['score']}*")
                        st.caption(f"\"{src['text']}\"")
                        
            if "suggestions" in msg and msg["suggestions"]:
                st.markdown("**💡 Sugerencias para avanzar:**")
                cols = st.columns(len(msg["suggestions"]))
                for s_idx, sug in enumerate(msg["suggestions"]):
                    with cols[s_idx]:
                        if st.button(sug, key=f"sug_{msg_idx}_{s_idx}"):
                            st.session_state.pending_query = sug
                            st.rerun()

            if "audio_url" in msg and msg["audio_url"]:
                full_audio_url = f"{api_base_url}{msg['audio_url']}"
                st.audio(full_audio_url)

    # Determinar si hay un query pendiente por clic de sugerencia o por chat_input
    active_query = None
    if st.session_state.pending_query:
        active_query = st.session_state.pending_query
        st.session_state.pending_query = None
    else:
        input_query = st.chat_input("Pregúntale al agente sobre tus documentos o webs...")
        if input_query:
            active_query = input_query

    if active_query:
        st.session_state.messages.append({"role": "user", "content": active_query})
        with st.chat_message("user"):
            st.markdown(active_query)

        with st.chat_message("assistant"):
            if not backend_healthy:
                err_text = "Lo siento, no puedo responder porque el servidor Flask no está en línea."
                st.markdown(err_text)
                st.session_state.messages.append({"role": "assistant", "content": err_text})
            else:
                with st.spinner("Buscando en la base vectorial y generando respuesta con sugerencias..."):
                    try:
                        chat_url = f"{api_base_url}/api/chat"
                        payload = {
                            "message": active_query,
                            "output_mode": output_mode
                        }
                        chat_resp = requests.post(chat_url, json=payload, timeout=40)
                        
                        if chat_resp.status_code == 200:
                            data = chat_resp.json()
                            ai_text = data.get("response", "")
                            sources_used = data.get("sources", [])
                            sug_list = data.get("suggestions", [])
                            aud_url = data.get("audio_url", None)
                            
                            st.markdown(ai_text)
                            
                            if sources_used:
                                with st.expander("🔍 Ver fuentes de esta respuesta"):
                                    for src in sources_used:
                                        st.markdown(f"📍 **{src['filename']}** (Sección/Pág. {src['page_number']}) — *Relevancia: {src['score']}*")
                                        st.caption(f"\"{src['text']}\"")
                                        
                            if sug_list:
                                st.markdown("**💡 Sugerencias para avanzar:**")
                                cols = st.columns(len(sug_list))
                                for s_idx, sug in enumerate(sug_list):
                                    with cols[s_idx]:
                                        if st.button(sug, key=f"sug_new_{s_idx}"):
                                            st.session_state.pending_query = sug
                                            st.rerun()

                            if aud_url:
                                full_audio_url = f"{api_base_url}{aud_url}"
                                st.audio(full_audio_url)
                                
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": ai_text,
                                "sources": sources_used,
                                "suggestions": sug_list,
                                "audio_url": aud_url
                            })
                            st.rerun()
                        else:
                            err_text = f"Error de comunicación con el agente ({chat_resp.status_code})."
                            st.error(err_text)
                            st.session_state.messages.append({"role": "assistant", "content": err_text})
                    except Exception as e:
                        err_text = f"Error al enviar la consulta al backend: {str(e)}"
                        st.error(err_text)
                        st.session_state.messages.append({"role": "assistant", "content": err_text})
