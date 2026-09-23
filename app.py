# -*- coding: utf-8 -*-
import os
import sys
import re
import json
import requests
from typing import Tuple, List, Dict, Any, Optional
from flask import Flask, request, jsonify, Response, send_from_directory
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Importamos nuestros módulos locales
from document_processor import DocumentProcessor
from vector_store import SimpleVectorStore
from whatsapp_handler import WhatsAppHandler
from meta_messenger_handler import MetaMessengerHandler
from database_manager import DatabaseManager
from tts_engine import TTSEngine

app = Flask(__name__)

# Configuración de carpetas y componentes
UPLOAD_FOLDER = os.path.abspath("./uploads")
AUDIO_FOLDER = os.path.abspath("./uploads/audio")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['AUDIO_FOLDER'] = AUDIO_FOLDER

VIDEO_FOLDER = os.path.abspath("./uploads/video")
os.makedirs(VIDEO_FOLDER, exist_ok=True)
app.config['VIDEO_FOLDER'] = VIDEO_FOLDER

from video_generator import WhiteboardVideoGenerator
video_gen = WhiteboardVideoGenerator(output_dir=VIDEO_FOLDER)


# Instancias principales
VECTOR_STORE_PATH = os.path.join(UPLOAD_FOLDER, "vector_index.pkl")
vector_store = SimpleVectorStore(storage_path=VECTOR_STORE_PATH)
processor = DocumentProcessor(min_chunk_size=300, max_chunk_size=1200, threshold=0.15)
whatsapp_handler = WhatsAppHandler()
meta_messenger_handler = MetaMessengerHandler()
db_manager = DatabaseManager(db_path=os.path.join(UPLOAD_FOLDER, "conversations.db"))
tts_engine = TTSEngine(output_folder=AUDIO_FOLDER)

# Control de duplicados de Webhooks
processed_message_ids = set()

# Caché en memoria para información de proveedor
cached_provider_info = None

BLACKLIST_MODELS = [
    "inclusionai/ling-3.0-flash-fin:free",
    "undaligned/llama-3-8b-instruct:free",
    "fargolabs/llama-3-8b-instruct-fp16:free"
]

STABLE_FREE_PRIORITY = [
    "google/gemini-2.5-flash:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-r1:free",
    "qwen/qwen-2.5-7b-instruct:free",
    "meta-llama/llama-3-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "microsoft/phi-3-medium-128k-instruct:free",
    "anyapi/free-gpt-4o-mini"
]


def discover_free_models_anyapi(api_key: str, base_url: str) -> list:
    models_url = f"{base_url.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    free_models = []
    
    try:
        response = requests.get(models_url, headers=headers, timeout=4)
        if response.status_code == 200:
            data = response.json().get("data", [])
            for item in data:
                model_id = item.get("id", "")
                if not model_id or model_id in BLACKLIST_MODELS:
                    continue
                
                pricing = item.get("pricing", {})
                try:
                    p_cost = float(pricing.get("prompt", 1))
                    c_cost = float(pricing.get("completion", 1))
                except (ValueError, TypeError):
                    p_cost = 1.0
                    c_cost = 1.0
                
                if (p_cost == 0.0 and c_cost == 0.0) or model_id.endswith(":free") or model_id.startswith("free-") or "free" in model_id.lower():
                    free_models.append(model_id)
    except Exception as e:
        print(f"[!] Advertencia al consultar AnyAPI AI models: {e}")
        
    return free_models


def discover_free_models_openrouter(api_key: str, base_url: str) -> list:
    models_url = f"{base_url.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    free_models = []
    
    try:
        response = requests.get(models_url, headers=headers, timeout=4)
        if response.status_code == 200:
            data = response.json().get("data", [])
            for item in data:
                model_id = item.get("id", "")
                if not model_id or model_id in BLACKLIST_MODELS:
                    continue
                
                pricing = item.get("pricing", {})
                try:
                    p_cost = float(pricing.get("prompt", 1))
                    c_cost = float(pricing.get("completion", 1))
                except (ValueError, TypeError):
                    p_cost = 1.0
                    c_cost = 1.0
                
                if (p_cost == 0.0 and c_cost == 0.0) or model_id.endswith(":free"):
                    free_models.append(model_id)
    except Exception as e:
        print(f"[!] Advertencia al consultar OpenRouter models: {e}")
        
    return free_models


def resolve_active_provider_and_models():
    global cached_provider_info
    if cached_provider_info:
        return cached_provider_info

    configured_provider = os.environ.get("AI_PROVIDER", "auto").lower().strip()
    anyapi_key = os.environ.get("ANYAPI_API_KEY", "").strip()
    anyapi_base = os.environ.get("ANYAPI_BASE_URL", "https://api.anyapi.ai/v1").strip()
    
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    openrouter_base = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()

    active_provider = "none"
    api_key = ""
    base_url = ""
    free_models = []

    if configured_provider == "anyapi" or (configured_provider == "auto" and anyapi_key):
        active_provider = "anyapi"
        api_key = anyapi_key
        base_url = anyapi_base
        if api_key:
            free_models = discover_free_models_anyapi(api_key, base_url)
    
    if not free_models and (configured_provider == "openrouter" or (configured_provider == "auto" and openrouter_key)):
        active_provider = "openrouter"
        api_key = openrouter_key
        base_url = openrouter_base
        if api_key:
            free_models = discover_free_models_openrouter(api_key, base_url)

    ordered_free_models = []
    if free_models:
        for pref in STABLE_FREE_PRIORITY:
            if pref in free_models:
                ordered_free_models.append(pref)
        for m in free_models:
            if m not in ordered_free_models:
                ordered_free_models.append(m)

    if not ordered_free_models:
        ordered_free_models = ["google/gemini-2.5-flash:free"]

    cached_provider_info = {
        "provider": active_provider if active_provider != "none" else ("anyapi" if anyapi_key else ("openrouter" if openrouter_key else "none")),
        "api_key": api_key or anyapi_key or openrouter_key,
        "base_url": base_url or (anyapi_base if anyapi_key else openrouter_base),
        "free_models": ordered_free_models,
        "active_model": ordered_free_models[0]
    }
    return cached_provider_info


def parse_suggestions_and_clean_text(response_text: str):
    if not response_text or not isinstance(response_text, str):
        return "Respuesta no disponible.", [
            "¿Deseas profundizar más en este tema?",
            "¿Qué requisitos o pasos adicionales necesitas?",
            "¿Quieres consultar otro documento de la base?"
        ]

    suggestions = []
    clean_text = response_text
    
    match = re.search(r'\[SUGERENCIAS\]:\s*(\[.*?\])', response_text, re.DOTALL | re.IGNORECASE)
    if match:
        raw_json = match.group(1).strip()
        try:
            suggestions = json.loads(raw_json)
        except Exception:
            suggestions = re.findall(r'\"([^\"]+)\"', raw_json)
        clean_text = response_text[:match.start()].strip()
    
    if not suggestions or not isinstance(suggestions, list):
        suggestions = [
            "¿Deseas profundizar más en este tema?",
            "¿Qué requisitos o pasos adicionales necesitas?",
            "¿Quieres consultar otro documento de la base?"
        ]
        
    cleaned_suggestions = []
    for s in suggestions:
        clean_s = str(s).replace('\\', '').strip().strip('\'"')
        if clean_s:
            cleaned_suggestions.append(clean_s)

    return clean_text, cleaned_suggestions[:3]


def detect_and_register_lead(user_id: str, channel: str, message: str):
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message)
    phone_match = re.search(r'\+?\d{8,15}', message)
    
    keywords = ["cotización", "precio", "contratar", "planes", "contacto", "demo", "asesoría"]
    is_interested = any(kw in message.lower() for kw in keywords)
    
    if email_match or phone_match or is_interested:
        db_manager.save_lead(
            user_id=user_id,
            channel=channel,
            name=user_id,
            email=email_match.group(0) if email_match else None,
            phone=phone_match.group(0) if phone_match else None,
            interest=message[:120]
        )


def generate_rag_response(message: str, user_id: str = "default_user", channel: str = "web") -> Tuple[str, List[str], List[Dict[str, Any]], str, str]:
    db_manager.save_message(user_id, channel, "user", message)
    detect_and_register_lead(user_id, channel, message)

    if not vector_store.chunks:
        fallback_msg = "Hola. Actualmente no tengo cargada ninguna base de conocimientos para responder a tus preguntas de manera precisa. Por favor, sube un documento PDF/DOCX o añade una URL desde el panel de administración."
        sugs = ["¿Cómo subo un documento?", "¿Cómo agrego un sitio web?", "¿Qué tipo de archivos soportas?"]
        db_manager.save_message(user_id, channel, "assistant", fallback_msg, suggestions=sugs, model_used="none")
        return (fallback_msg, sugs, [], "none", "none")

    recent_history = db_manager.get_recent_history(user_id, limit=4)
    history_text = ""
    if len(recent_history) > 1:
        history_text = "\n\nHISTORIAL CONVERSACIONAL PREVIO DEL USUARIO:\n"
        for h in recent_history[:-1]:
            role_label = "Usuario" if h["role"] == "user" else "Asistente"
            history_text += f"- {role_label}: {h['content']}\n"

    top_chunks_data = vector_store.query(message, top_k=4)

    context_parts = []
    sources = []
    for chunk, score in top_chunks_data:
        meta = chunk["metadata"]
        context_parts.append(f"[Fuente: {meta['filename']} - Pág/Sec: {meta['page_number']}]\n{chunk['text']}")
        sources.append({
            "filename": meta["filename"],
            "page_number": meta["page_number"],
            "score": round(score, 3),
            "text": chunk["text"]
        })
        
    context_text = "\n\n---\n\n".join(context_parts)
    
    system_prompt = (
        "Eres un Agente de Inteligencia Artificial experto en atención al cliente y soporte para AVFenix.\n"
        "Tu misión principal es asesorar al usuario basándote ÚNICAMENTE en la base de conocimientos proporcionada abajo.\n\n"
        "REGLAS CRÍTICAS DE COMPORTAMIENTO:\n"
        "1. Ciñete estrictamente al contexto proporcionado. NO inventes hechos, cifras, enlaces, características ni respuestas.\n"
        "2. Si la respuesta a la pregunta del usuario no está contenida explícitamente en el contexto ni es un saludo/cortesía básico, debes responder textualmente:\n"
        "   \"Lo siento, no encuentro información sobre ese tema en mi base de conocimientos actual.\"\n"
        "   No intentes rellenar huecos ni dar respuestas parciales basadas en tu entrenamiento previo.\n"
        "3. Si el mensaje es un saludo común (ej. 'hola', 'buenos días', '¿qué tal?'), saluda de manera cortés, profesional y diles que estás listo para responder preguntas sobre los documentos y webs cargadas.\n"
        "4. Mantén un tono profesional, cortés, empático y claro en español.\n"
        "5. Al final de tus respuestas informativas, menciona brevemente las fuentes utilizadas citando el archivo o enlace de forma natural.\n"
        "6. OBLIGATORIO AL FINAL: Incluye siempre un bloque de 3 sugerencias cortas y clickeables para que el usuario pueda avanzar. Escribe estrictamente la siguiente sintaxis al final del mensaje:\n"
        "[SUGERENCIAS]: [\"Pregunta o acción 1\", \"Pregunta o acción 2\", \"Pregunta o acción 3\"]\n"
        f"{history_text}\n"
        f"CONTEXTO AUTORIZADO:\n{context_text}"
    )

    info = resolve_active_provider_and_models()
    provider_name = info["provider"]
    api_key = info["api_key"]
    base_url = info["base_url"]
    free_models = info["free_models"]

    if not api_key:
        err_msg = "Error: No se encontró clave de API configurada en .env."
        db_manager.save_message(user_id, channel, "assistant", err_msg, model_used="none")
        return (err_msg, [], [], "none", "none")

    try:
        max_tokens = int(os.environ.get("MAX_TOKENS", os.environ.get("OPENROUTER_MAX_TOKENS", 2000)))
    except (ValueError, TypeError):
        max_tokens = 2000

    chat_endpoint = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": "AVFenix RAG Customer Agent"
    }

    ai_response = None
    last_error = ""

    for model_name in free_models:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens
        }

        try:
            response = requests.post(chat_endpoint, json=payload, headers=headers, timeout=30)
            if response.status_code != 200:
                raise ValueError(f"HTTP {response.status_code}")

            res_json = response.json()
            if not isinstance(res_json, dict):
                raise ValueError("Formato de respuesta inválido")

            choices = res_json.get('choices', [])
            if not choices or not isinstance(choices, list):
                err_msg = res_json.get('error', {}).get('message', 'Sin choices')
                raise ValueError(err_msg)

            message_data = choices[0].get('message', {})
            ai_response_raw = message_data.get('content')

            if ai_response_raw is None:
                raise ValueError("Respuesta nula del modelo")

            ai_response = str(ai_response_raw).strip()
            if not ai_response:
                raise ValueError("Respuesta vacía del modelo")

            info["active_model"] = model_name
            break

        except Exception as e:
            last_error = str(e)
            continue

    if not ai_response:
        err_fallback = f"Lo siento, ocurrió un problema temporal con el motor de IA: {last_error}"
        db_manager.save_message(user_id, channel, "assistant", err_fallback, model_used="error")
        return (err_fallback, [], [], provider_name, "error")

    clean_response, suggestions = parse_suggestions_and_clean_text(ai_response)
    db_manager.save_message(user_id, channel, "assistant", clean_response, suggestions=suggestions, sources=sources, model_used=info["active_model"])

    return clean_response, suggestions, sources, provider_name, info["active_model"]


# Manejo manual de CORS en Flask
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,DELETE,OPTIONS'
    return response

@app.route('/api/summarize', methods=['OPTIONS'])
@app.route('/api/generate_whiteboard_video', methods=['OPTIONS'])
@app.route('/api/upload', methods=['OPTIONS'])
@app.route('/api/scrape_url', methods=['OPTIONS'])
@app.route('/api/chat', methods=['OPTIONS'])
@app.route('/api/export_leads', methods=['OPTIONS'])
@app.route('/api/whatsapp', methods=['OPTIONS'])
@app.route('/api/meta_messenger', methods=['OPTIONS'])
@app.route('/api/instagram', methods=['OPTIONS'])
@app.route('/api/facebook', methods=['OPTIONS'])
@app.route('/api/documents', methods=['OPTIONS'])
@app.route('/api/delete/<path:filename>', methods=['OPTIONS'])
def handle_options(*args, **kwargs):
    return '', 200


@app.route('/', methods=['GET'])
@app.route('/dashboard', methods=['GET'])
def serve_dashboard():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for fn in ['index.html', 'dashboard_web.txt', 'dashboard_web.html']:
        for search_dir in [base_dir, '.']:
            p = os.path.join(search_dir, fn)
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f_in:
                    content = f_in.read()
                return Response(content, mimetype='text/html; charset=utf-8')
    return jsonify({"status": "healthy", "info": "AVFenix Agent API"}), 200

@app.route('/api/summarize', methods=['POST'])
def summarize_document():
    data = request.json or {}
    filename = data.get("filename", "").strip()
    
    if filename:
        prompt = f"Haz un resumen ejecutivo detallado y completo del documento {filename}."
    else:
        prompt = "Haz un resumen ejecutivo detallado y completo de la base de conocimientos."
        
    clean_response, suggestions, sources, provider_name, active_model = generate_rag_response(
        prompt, user_id="summary_user", channel="web"
    )
    
    audio_url = None
    if clean_response:
        audio_filename = tts_engine.generate_audio(clean_response, output_dir=app.config['AUDIO_FOLDER'])
        if audio_filename:
            audio_url = f"/api/audio/{audio_filename}"
            
    return jsonify({
        "summary": clean_response,
        "response": clean_response,
        "audio_url": audio_url,
        "suggestions": suggestions,
        "sources": sources
    }), 200

@app.route('/api/generate_whiteboard_video', methods=['POST'])
def generate_whiteboard_video_endpoint():
    data = request.json or {}
    filename = data.get("filename", "").strip()
    
    if filename:
        prompt = f"Genera los puntos clave del documento {filename} para un resumen en video."
    else:
        prompt = "Genera los puntos clave de la base de conocimientos para un resumen en video."
        
    clean_response, suggestions, sources, provider_name, active_model = generate_rag_response(
        prompt, user_id="video_user", channel="web"
    )
    
    video_filename = video_gen.generate_video(clean_response, title=filename or "Resumen AVFenix")
    if video_filename:
        return jsonify({
            "status": "success",
            "video_filename": video_filename,
            "video_url": f"/api/video/{video_filename}",
            "summary_text": clean_response
        }), 200
    return jsonify({"error": "No se pudo generar el video pizarra"}), 500

@app.route('/api/video/<path:filename>', methods=['GET'])
def serve_video(filename):
    return send_from_directory(app.config['VIDEO_FOLDER'], filename)

@app.route('/api/health', methods=['GET'])
def health():
    info = resolve_active_provider_and_models()
    analytics = db_manager.get_analytics_summary()
    return jsonify({
        "status": "healthy", 
        "database_chunks": len(vector_store.chunks),
        "active_provider": info["provider"],
        "active_free_model": info["active_model"],
        "available_free_models": info["free_models"],
        "whatsapp_configured": bool(os.environ.get("WHATSAPP_TOKEN") and os.environ.get("WHATSAPP_PHONE_ID")),
        "meta_messenger_configured": bool(os.environ.get("META_PAGE_ACCESS_TOKEN")),
        "tts_engine_type": tts_engine.engine_type,
        "analytics": analytics
    }), 200

@app.route('/api/documents', methods=['GET'])
def list_documents():
    docs = vector_store.list_documents()
    return jsonify({"documents": docs}), 200

@app.route('/api/delete/<path:filename>', methods=['DELETE'])
def delete_document(filename):
    if not filename:
        return jsonify({"error": "Nombre de archivo no proporcionado"}), 400
        
    deleted_chunks = vector_store.delete_by_filename(filename)
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
    file_deleted = False
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            file_deleted = True
        except Exception as e:
            print(f"Error borrando archivo físico {filename}: {e}")
            
    return jsonify({
        "message": f"Documento '{filename}' procesado para borrado.",
        "chunks_removed": deleted_chunks,
        "physical_file_deleted": file_deleted
    }), 200

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No se envió ninguna parte de archivo"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No se seleccionó ningún archivo"}), 400
        
    filename = secure_filename(file.filename)
    ext = filename.lower().split('.')[-1]
    if ext not in ['pdf', 'docx', 'doc']:
        return jsonify({"error": "Solo se permiten formatos PDF y DOCX (.docx/.doc)"}), 400
        
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    
    try:
        chunks = processor.process_file(file_path)
        if not chunks:
            return jsonify({"error": f"No se pudo extraer texto legible del archivo '{filename}'."}), 422
            
        vector_store.add_chunks(chunks)
        return jsonify({
            "message": f"Archivo '{filename}' procesado e indexado con éxito.",
            "chunks_count": len(chunks),
            "filename": filename
        }), 200
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({"error": f"Error interno al procesar el documento: {str(e)}"}), 500

@app.route('/api/scrape_url', methods=['POST'])
def scrape_url():
    data = request.json or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "Debe proporcionar una URL válida"}), 400
        
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url
        
    try:
        chunks = processor.process_url(url)
        if not chunks:
            return jsonify({"error": f"No se pudo extraer texto legible de la URL '{url}'."}), 422
            
        vector_store.add_chunks(chunks)
        filename = chunks[0]["metadata"]["filename"]
        return jsonify({
            "message": f"URL '{url}' scrapeada e indexada con éxito.",
            "chunks_count": len(chunks),
            "filename": filename
        }), 200
    except Exception as e:
        return jsonify({"error": f"Error al procesar la URL: {str(e)}"}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json or {}
    message = data.get("message", "").strip()
    output_mode = data.get("output_mode", "text")
    user_id = data.get("user_id", "web_user")
    channel = data.get("channel", "web")
    
    if not message:
        return jsonify({"error": "El mensaje no puede estar vacío"}), 400
        
    clean_response, suggestions, sources, provider_name, active_model = generate_rag_response(
        message, user_id=user_id, channel=channel
    )

    audio_url = None
    if output_mode in ["audio", "both"] and clean_response:
        audio_filename = tts_engine.generate_audio(clean_response, output_dir=app.config['AUDIO_FOLDER'])
        if audio_filename:
            audio_url = f"/api/audio/{audio_filename}"

    return jsonify({
        "response": clean_response,
        "suggestions": suggestions,
        "sources": sources,
        "audio_url": audio_url,
        "provider": provider_name,
        "model": active_model,
        "user_id": user_id
    }), 200


@app.route('/api/audio/<path:filename>', methods=['GET'])
def serve_audio(filename):
    """Sirve los archivos de audio sintetizados (.wav o .mp3)."""
    return send_from_directory(app.config['AUDIO_FOLDER'], filename)

@app.route('/api/history/<user_id>', methods=['GET'])
def get_user_history(user_id):
    """Retorna el historial conversacional completo guardado en SQLite para un usuario."""
    history = db_manager.get_full_history(user_id)
    return jsonify({"user_id": user_id, "messages": history}), 200

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    """Retorna las métricas y analíticas globales de uso del agente multicanal."""
    summary = db_manager.get_analytics_summary()
    return jsonify(summary), 200

@app.route('/api/export_leads', methods=['GET', 'OPTIONS'])
def export_leads():
    """Genera y descarga un archivo CSV con la lista completa de leads capturados."""
    if request.method == 'OPTIONS':
        return '', 200
    csv_content = db_manager.export_leads_csv()
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads_avfenix.csv"}
    )

@app.route('/api/tts', methods=['GET'])
def tts_handler():
    text = request.args.get("text", "")
    audio_filename = tts_engine.generate_audio(text, output_dir=app.config['AUDIO_FOLDER'])
    if audio_filename:
        audio_url = f"/api/audio/{audio_filename}"
        return jsonify({
            "info": f"Servicio TTS con motor {tts_engine.engine_type}.",
            "audio_url": audio_url,
            "filename": audio_filename
        }), 200
    return jsonify({"error": "No se pudo generar el archivo de audio"}), 500


# --- ENDPOINTS DE WHATSAPP CLOUD API ---

@app.route('/api/whatsapp', methods=['GET'])
def verify_whatsapp_webhook():
    mode = request.args.get('hub.mode', '')
    token = request.args.get('hub.verify_token', '')
    challenge = request.args.get('hub.challenge', '')

    if whatsapp_handler.verify_token_match(mode, token):
        print("[*] Webhook de WhatsApp verificado exitosamente con Meta.")
        return challenge, 200
    else:
        print("[!] Falló la verificación del Webhook de WhatsApp: Token incorrecto.")
        return "Error de verificación: Token no válido", 403

@app.route('/api/whatsapp', methods=['POST'])
def receive_whatsapp_message():
    payload = request.json or {}
    sender_phone, message_text, msg_id = whatsapp_handler.parse_incoming_payload(payload)

    if not sender_phone or not message_text:
        return jsonify({"status": "ignored"}), 200

    if msg_id and msg_id in processed_message_ids:
        return jsonify({"status": "already_processed"}), 200

    if msg_id:
        processed_message_ids.add(msg_id)
        if len(processed_message_ids) > 1000:
            processed_message_ids.clear()

    print(f"[*] Mensaje entrante de WhatsApp (+{sender_phone}): {message_text}")

    clean_response, suggestions, sources, provider, model = generate_rag_response(
        message_text, user_id=f"wa_{sender_phone}", channel="whatsapp"
    )

    sent_success = whatsapp_handler.send_message(sender_phone, clean_response, suggestions)

    return jsonify({
        "status": "success" if sent_success else "error_sending",
        "recipient": sender_phone,
        "provider_used": provider,
        "model_used": model
    }), 200


# --- ENDPOINTS DE INSTAGRAM DIRECT & FACEBOOK MESSENGER ---

@app.route('/api/meta_messenger', methods=['GET'])
@app.route('/api/instagram', methods=['GET'])
@app.route('/api/facebook', methods=['GET'])
def verify_meta_messenger_webhook():
    mode = request.args.get('hub.mode', '')
    token = request.args.get('hub.verify_token', '')
    challenge = request.args.get('hub.challenge', '')

    if meta_messenger_handler.verify_token_match(mode, token):
        print("[*] Webhook de Meta Messenger/Instagram verificado exitosamente con Meta.")
        return challenge, 200
    else:
        print("[!] Falló la verificación del Webhook de Meta Messenger/Instagram: Token incorrecto.")
        return "Error de verificación: Token no válido", 403

@app.route('/api/meta_messenger', methods=['POST'])
@app.route('/api/instagram', methods=['POST'])
@app.route('/api/facebook', methods=['POST'])
def receive_meta_messenger_message():
    payload = request.json or {}
    sender_id, message_text, msg_id, platform = meta_messenger_handler.parse_incoming_payload(payload)

    if not sender_id or not message_text:
        return jsonify({"status": "ignored"}), 200

    if msg_id and msg_id in processed_message_ids:
        return jsonify({"status": "already_processed"}), 200

    if msg_id:
        processed_message_ids.add(msg_id)
        if len(processed_message_ids) > 1000:
            processed_message_ids.clear()

    print(f"[*] Mensaje entrante de {platform.upper()} (User ID: {sender_id}): {message_text}")

    user_channel_id = f"ig_{sender_id}" if platform == "instagram" else f"fb_{sender_id}"
    clean_response, suggestions, sources, provider, model = generate_rag_response(
        message_text, user_id=user_channel_id, channel=platform
    )

    sent_success = meta_messenger_handler.send_message(sender_id, clean_response, suggestions, platform=platform)

    return jsonify({
        "status": "success" if sent_success else "error_sending",
        "recipient": sender_id,
        "platform": platform,
        "provider_used": provider,
        "model_used": model
    }), 200


if __name__ == '__main__':
    print("Iniciando Servidor AVFenix Agent Backend Fase 6 en http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
