# -*- coding: utf-8 -*-
import os
import sys
import requests
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Cargar variables de entorno desde un archivo .env si está presente
load_dotenv()

# Importamos nuestros módulos locales
from document_processor import DocumentProcessor
from vector_store import SimpleVectorStore

app = Flask(__name__)

# Configuración de carpetas y carga de componentes
UPLOAD_FOLDER = os.path.abspath("./uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Guardamos el índice vectorial dentro de la carpeta uploads para mayor orden
VECTOR_STORE_PATH = os.path.join(UPLOAD_FOLDER, "vector_index.pkl")
vector_store = SimpleVectorStore(storage_path=VECTOR_STORE_PATH)
processor = DocumentProcessor(min_chunk_size=300, max_chunk_size=1200, threshold=0.15)

# Guardamos en caché el modelo seleccionado para evitar latencias en cada mensaje del chat
cached_free_model = None

# Lista de modelos inestables o problemáticos que queremos excluir del carrusel dinámico
BLACKLIST_MODELS = [
    "inclusionai/ling-3.0-flash-fin:free",
    "undaligned/llama-3-8b-instruct:free",
    "fargolabs/llama-3-8b-instruct-fp16:free"
]

def get_available_free_model():
    """
    Consulta la API de OpenRouter de manera rápida para detectar qué modelos
    gratuitos están activos, estables y disponibles.
    Implementa una lista negra y una caché en memoria para máxima velocidad.
    """
    global cached_free_model
    
    # Si ya lo consultamos previamente en esta sesión, retornamos el resultado cacheado
    if cached_free_model:
        return cached_free_model

    fallback_model = "google/gemini-2.5-flash:free"
    url = "https://openrouter.ai/api/v1/models"
    
    # Lista de modelos gratuitos estables de alta calidad (orden de prioridad)
    stable_free_priority = [
        "google/gemini-2.5-flash:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-r1:free",
        "qwen/qwen-2.5-7b-instruct:free",
        "meta-llama/llama-3-8b-instruct:free",
        "mistralai/mistral-7b-instruct:free",
        "microsoft/phi-3-medium-128k-instruct:free"
    ]
    
    try:
        # Hacemos una consulta rápida con un timeout estricto de 4 segundos para no bloquear la app
        response = requests.get(url, timeout=4)
        if response.status_code == 200:
            models_data = response.json().get("data", [])
            free_models = []
            
            for model in models_data:
                model_id = model.get("id", "")
                
                # Ignorar modelos en lista negra
                if model_id in BLACKLIST_MODELS:
                    continue
                    
                pricing = model.get("pricing", {})
                
                # Evaluamos los costos del modelo (tanto para prompt como para completion)
                try:
                    prompt_cost = float(pricing.get("prompt", 1))
                    completion_cost = float(pricing.get("completion", 1))
                except (ValueError, TypeError):
                    prompt_cost = 1.0
                    completion_cost = 1.0
                
                # Un modelo es considerado gratis si sus costos de API son cero o termina en ':free'
                if (prompt_cost == 0.0 and completion_cost == 0.0) or model_id.endswith(":free"):
                    free_models.append(model_id)
            
            if free_models:
                # 1. Buscamos el primer modelo disponible que coincida con nuestra lista de prioridad estable
                for preferred in stable_free_priority:
                    if preferred in free_models:
                        cached_free_model = preferred
                        print(f"[*] Modelo gratuito recomendado seleccionado: {cached_free_model}")
                        return cached_free_model
                
                # 2. Si ninguno de los preferidos está libre, tomamos el primero disponible de la lista general
                cached_free_model = free_models[0]
                print(f"[*] Modelo gratuito genérico seleccionado: {cached_free_model}")
                return cached_free_model
                
    except Exception as e:
        print(f"[!] Advertencia al consultar modelos en OpenRouter: {e}. Usando fallback por defecto.")
    
    # En caso de error o de no encontrar modelos libres, usamos el fallback
    cached_free_model = fallback_model
    return cached_free_model


# Manejo manual de CORS en Flask (flask_cors no está disponible)
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,DELETE,OPTIONS'
    return response

@app.route('/api/upload', methods=['OPTIONS'])
@app.route('/api/chat', methods=['OPTIONS'])
@app.route('/api/documents', methods=['OPTIONS'])
@app.route('/api/delete/<path:filename>', methods=['OPTIONS'])
def handle_options(*args, **kwargs):
    return '', 200

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy", 
        "database_chunks": len(vector_store.chunks),
        "active_free_model": get_available_free_model()
    }), 200

@app.route('/api/documents', methods=['GET'])
def list_documents():
    """
    Retorna la lista de documentos únicos indexados en el agente.
    """
    docs = vector_store.list_documents()
    return jsonify({"documents": docs}), 200

@app.route('/api/delete/<path:filename>', methods=['DELETE'])
def delete_document(filename):
    """
    Elimina un documento del índice vectorial y del almacenamiento físico.
    """
    if not filename:
        return jsonify({"error": "Nombre de archivo no proporcionado"}), 400
        
    # Eliminar de la base vectorial
    deleted_chunks = vector_store.delete_by_filename(filename)
    
    # Intentar eliminar el archivo físico de uploads
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
    """
    Sube un archivo PDF o DOCX, extrae su texto mediante chunking semántico y lo indexa.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No se envió ninguna parte de archivo"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No se seleccionó ningún archivo"}), 400
        
    filename = secure_filename(file.filename)
    ext = filename.lower().split('.')[-1]
    if ext not in ['pdf', 'docx', 'doc']:
        return jsonify({"error": "Solo se permiten formatos PDF y DOCX (.docx/.doc)"}), 400
        
    # Guardar archivo temporalmente
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    
    try:
        # Procesar y fragmentar semánticamente el documento
        chunks = processor.process_file(file_path)
        
        if not chunks:
            return jsonify({"error": f"No se pudo extraer texto legible del archivo '{filename}'."}), 422
            
        # Indexar chunks en la base vectorial
        vector_store.add_chunks(chunks)
        
        return jsonify({
            "message": f"Archivo '{filename}' procesado e indexado con éxito.",
            "chunks_count": len(chunks),
            "filename": filename
        }), 200
        
    except Exception as e:
        print(f"Error procesando el archivo {filename}: {e}")
        # Limpieza si falla
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({"error": f"Error interno al procesar el documento: {str(e)}"}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Endpoint principal del chat RAG. Realiza búsqueda vectorial y consulta a OpenRouter.
    Soporta opcionalmente output_mode = text / audio / both.
    """
    data = request.json or {}
    message = data.get("message", "").strip()
    output_mode = data.get("output_mode", "text") # text, audio, both
    
    if not message:
        return jsonify({"error": "El mensaje no puede estar vacío"}), 400
        
    # 1. Comprobar si hay alguna base de conocimiento cargada en general
    if not vector_store.chunks:
        return jsonify({
            "response": "Hola. Actualmente no tengo cargada ninguna base de conocimientos para responder a tus preguntas de manera precisa. Por favor, sube un documento PDF o DOCX desde el panel de administración.",
            "sources": [],
            "audio_url": None
        }), 200

    # 2. Recuperar los fragmentos de conocimiento más relevantes (RAG)
    top_chunks_data = vector_store.query(message, top_k=4)

    # Construir el contexto y recopilar metadatos de fuentes
    context_parts = []
    sources = []
    for chunk, score in top_chunks_data:
        meta = chunk["metadata"]
        context_parts.append(f"[Archivo: {meta['filename']} - Pág/Sec: {meta['page_number']}]\n{chunk['text']}")
        sources.append({
            "filename": meta["filename"],
            "page_number": meta["page_number"],
            "score": round(score, 3),
            "text": chunk["text"]
        })
        
    context_text = "\n\n---\n\n".join(context_parts)
    
    # 3. Formular el prompt para OpenRouter con restricciones estrictas (Zero-Hallucination)
    system_prompt = (
        "Eres un Agente de Inteligencia Artificial experto en atención al cliente y soporte para AVFenix.\n"
        "Tu misión principal es asesorar al usuario basándote ÚNICAMENTE en la base de conocimientos proporcionada abajo.\n\n"
        "REGLAS CRÍTICAS DE COMPORTAMIENTO:\n"
        "1. Ciñete estrictamente al contexto proporcionado. NO inventes hechos, cifras, enlaces, características ni respuestas.\n"
        "2. Si la respuesta a la pregunta del usuario no está contenida explícitamente en el contexto ni es un saludo/cortesía básico, debes responder textualmente:\n"
        "   \"Lo siento, no encuentro información sobre ese tema en mi base de conocimientos actual.\"\n"
        "   No intentes rellenar huecos ni dar respuestas parciales basadas en tu entrenamiento previo.\n"
        "3. Si el mensaje es un saludo común (ej. 'hola', 'buenos días', '¿qué tal?'), saluda de manera cortés, profesional y diles que estás listo para responder preguntas sobre los documentos cargados.\n"
        "4. Mantén un tono profesional, cortés, empático y claro en español.\n"
        "5. Al final de tus respuestas informativas, menciona brevemente las fuentes utilizadas citando el archivo y la página de forma natural.\n\n"
        f"CONTEXTO AUTORIZADO:\n{context_text}"
    )

    # 4. Obtener dinámicamente el modelo gratuito disponible en OpenRouter
    model_name = get_available_free_model()

    # 5. Configurar el tamaño máximo de respuesta dinámica (Evitar recortes)
    # Buscamos en el .env la variable OPENROUTER_MAX_TOKENS. Si no está configurada,
    # ampliamos de 800 a 2000 tokens por defecto para permitir respuestas ricas y detalladas.
    try:
        max_tokens = int(os.environ.get("OPENROUTER_MAX_TOKENS", 2000))
    except (ValueError, TypeError):
        max_tokens = 2000

    # 6. Llamar a la API de OpenRouter
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return jsonify({
            "error": "La variable de entorno OPENROUTER_API_KEY no está configurada en el servidor. No se puede consultar el LLM."
        }), 500

    openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "AVFenix RAG Customer Agent"
    }
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        "temperature": 0.1,  # Temperatura baja para evitar alucinaciones y respuestas creativas
        "max_tokens": max_tokens
    }
    
    ai_response = None
    try:
        response = requests.post(openrouter_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        res_json = response.json()
        
        choices = res_json.get('choices', [])
        if not choices:
            err_msg = res_json.get('error', {}).get('message', 'No se recibieron opciones válidas del modelo.')
            raise ValueError(f"OpenRouter devolvió un error: {err_msg}")
            
        message_data = choices[0].get('message', {})
        ai_response_raw = message_data.get('content')
        
        if ai_response_raw is None:
            raise ValueError("El modelo devolvió una respuesta nula (None), posiblemente por bloqueo de seguridad o fallo interno.")
            
        ai_response = ai_response_raw.strip()
        if not ai_response:
            raise ValueError("El modelo devolvió un texto vacío.")
            
    except Exception as e:
        print(f"Error al llamar a OpenRouter usando el modelo primario {model_name}: {e}")
        
        # MECANISMO DE RESPALDO DE EMERGENCIA: Si el modelo dinámico falló o devolvió None,
        # reintentamos de forma automática e inmediata con el modelo ultra-estable de Gemini 2.5 Flash Free.
        if model_name != "google/gemini-2.5-flash:free":
            print("[*] Reintentando llamada de emergencia inmediata con google/gemini-2.5-flash:free...")
            try:
                payload["model"] = "google/gemini-2.5-flash:free"
                payload["max_tokens"] = max_tokens
                fallback_response = requests.post(openrouter_url, json=payload, headers=headers, timeout=30)
                fallback_response.raise_for_status()
                fallback_json = fallback_response.json()
                
                fallback_choices = fallback_json.get('choices', [])
                if fallback_choices:
                    fallback_content = fallback_choices[0].get('message', {}).get('content')
                    if fallback_content is not None:
                        ai_response = fallback_content.strip()
                        print("[*] Reintento de emergencia exitoso usando google/gemini-2.5-flash:free")
                        return jsonify({
                            "response": ai_response,
                            "sources": sources,
                            "audio_url": None,
                            "note": "Nota: Se utilizó un modelo de respaldo debido a un fallo en el modelo dinámico primario."
                        }), 200
            except Exception as inner_e:
                print(f"[!] Falló también el reintento de emergencia: {inner_e}")
        
        # Si fallaron todas las opciones, devolvemos un mensaje de error estructurado
        return jsonify({"error": f"Error de comunicación con el motor de IA ({model_name}): {str(e)}"}), 502

    # 7. Pipeline de Voz (Kokoro / TTS alternativo)
    audio_url = None
    if output_mode in ["audio", "both"] and ai_response:
        audio_url = f"/api/tts?text={requests.utils.quote(ai_response[:200])}"

    return jsonify({
        "response": ai_response,
        "sources": sources,
        "audio_url": audio_url
    }), 200

@app.route('/api/tts', methods=['GET'])
def tts_placeholder():
    """
    Ruta para la generación de audio. En un entorno de producción con Kokoro TTS,
    aquí se cargaría el pipeline local para generar el archivo .wav y retornarlo.
    """
    text = request.args.get("text", "")
    return jsonify({
        "info": "Servicio de Voz Kokoro TTS.",
        "text_to_speak": text,
        "note": "Para producción, sustituir este handler por la llamada a kokoro.generate() y devolver un send_file de audio/wav"
    }), 200

if __name__ == '__main__':
    print("Iniciando Servidor AVFenix Agent Backend en http://localhost:5000")
    # Escuchamos en todas las interfaces para permitir llamadas externas de widgets o WhatsApp
    app.run(host='0.0.0.0', port=5000, debug=True)