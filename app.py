# -*- coding: utf-8 -*-
import os
import sys
import requests
from flask import Flask, request, jsonify
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

# Lista negra de modelos gratuitos que sabemos que fallan, están rotos o devuelven None
BLACKLIST_MODELS = [
    "inclusionai/ling-3.0-flash-fin:free",
    "inclusionai/ling-3.0-flash:free",
    "undaligned/llama-3-8b-instruct:free"
]

# Cacheamos la lista ordenada de modelos gratuitos para no consultar la API en cada mensaje
cached_ranked_models = []

def get_ranked_free_models():
    """
    Consulta la API de OpenRouter de manera rápida para obtener la lista de modelos
    gratuitos activos, los filtra quitando la lista negra y los ordena priorizando
    los más estables y de mayor rendimiento para español.
    """
    global cached_ranked_models
    
    # Si ya lo consultamos y logramos armar la caché, la reutilizamos
    if cached_ranked_models:
        return cached_ranked_models

    # Lista preferente de modelos gratuitos estables de alta calidad (ordenados por prioridad)
    stable_free_priority = [
        "google/gemini-2.5-flash:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-r1:free",
        "qwen/qwen-2.5-7b-instruct:free",
        "meta-llama/llama-3-8b-instruct:free",
        "mistralai/mistral-7b-instruct:free",
        "microsoft/phi-3-medium-128k-instruct:free"
    ]
    
    url = "https://openrouter.ai/api/v1/models"
    try:
        # Petición rápida con un timeout de 4 segundos
        response = requests.get(url, timeout=4)
        if response.status_code == 200:
            models_data = response.json().get("data", [])
            detected_free_models = []
            
            for model in models_data:
                model_id = model.get("id", "")
                pricing = model.get("pricing", {})
                
                # Omitir modelos que están explícitamente en la lista negra
                if model_id in BLACKLIST_MODELS:
                    continue
                
                # Evaluar costos de prompt y completion
                try:
                    prompt_cost = float(pricing.get("prompt", 1))
                    completion_cost = float(pricing.get("completion", 1))
                except (ValueError, TypeError):
                    prompt_cost = 1.0
                    completion_cost = 1.0
                
                # Es gratis si el costo es 0 o si termina con ':free'
                if (prompt_cost == 0.0 and completion_cost == 0.0) or model_id.endswith(":free"):
                    detected_free_models.append(model_id)
            
            if detected_free_models:
                # Ordenar los modelos detectados basándose en nuestra prioridad estable
                ranked_list = []
                # 1. Agregamos los que están en nuestra lista de estabilidad (siempre que OpenRouter diga que están gratis y activos)
                for preferred in stable_free_priority:
                    if preferred in detected_free_models:
                        ranked_list.append(preferred)
                
                # 2. Agregamos el resto de modelos gratis que no estaban en nuestra lista de prioridad
                for detected in detected_free_models:
                    if detected not in ranked_list:
                        ranked_list.append(detected)
                
                cached_ranked_models = ranked_list
                print(f"[*] Modelos gratuitos detectados y ordenados por prioridad: {cached_ranked_models}")
                return cached_ranked_models
                
    except Exception as e:
        print(f"[!] Advertencia al consultar modelos de OpenRouter: {e}. Usando lista por defecto.")
    
    # Si hay un fallo de red o la API no responde, usamos nuestra lista estática confiable
    cached_ranked_models = stable_free_priority
    return cached_ranked_models


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
    models = get_ranked_free_models()
    return jsonify({
        "status": "healthy", 
        "database_chunks": len(vector_store.chunks),
        "primary_free_model": models[0] if models else "None",
        "available_free_models_count": len(models)
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
        print(f"Error procesando el archivo {filename}: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({"error": f"Error interno al procesar el documento: {str(e)}"}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Endpoint principal del chat RAG. Realiza búsqueda vectorial y consulta a OpenRouter.
    Prueba dinámicamente múltiples modelos gratuitos disponibles en orden de estabilidad
    para recuperarse de forma invisible de caídas, bloqueos o respuestas vacías (None).
    """
    data = request.json or {}
    message = data.get("message", "").strip()
    output_mode = data.get("output_mode", "text")
    
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

    # 4. Obtener la lista ordenada y filtrada de modelos gratuitos disponibles
    models_to_try = get_ranked_free_models()

    # 5. Llamar a la API de OpenRouter con reintento secuencial
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
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        "temperature": 0.1,  # Baja creatividad para evitar alucinaciones
        "max_tokens": 800
    }
    
    ai_response = None
    last_error = "No se encontraron modelos gratuitos de OpenRouter activos o disponibles."
    used_model = None

    # Algoritmo de reintento secuencial invisible al usuario
    for model_name in models_to_try:
        print(f"[*] Probando consulta con el modelo gratuito: {model_name}")
        payload["model"] = model_name
        
        try:
            response = requests.post(openrouter_url, json=payload, headers=headers, timeout=25)
            response.raise_for_status()
            res_json = response.json()
            
            choices = res_json.get('choices', [])
            if not choices:
                err_msg = res_json.get('error', {}).get('message', 'OpenRouter no devolvió opciones.')
                raise ValueError(f"Fallo de generación: {err_msg}")
                
            message_data = choices[0].get('message', {})
            ai_response_raw = message_data.get('content')
            
            if ai_response_raw is None:
                raise ValueError("El modelo devolvió una respuesta nula (None).")
                
            ai_response_cleaned = ai_response_raw.strip()
            if not ai_response_cleaned:
                raise ValueError("El modelo devolvió un texto vacío.")
            
            # Si tiene éxito y devuelve contenido válido, guardamos la respuesta y detenemos el ciclo
            ai_response = ai_response_cleaned
            used_model = model_name
            print(f"[+] Éxito total en la consulta usando: {used_model}")
            break
            
        except Exception as e:
            print(f"[!] El modelo gratuito '{model_name}' falló debido a: {e}. Probando el siguiente modelo en la cola...")
            last_error = str(e)
            continue

    # Si se recorrieron todos los modelos y ninguno pudo responder con éxito
    if ai_response is None:
        print(f"[CRÍTICO] Todos los modelos gratuitos de OpenRouter fallaron. Último error registrado: {last_error}")
        return jsonify({
            "error": f"Todos los modelos gratuitos fallaron. Último error: {last_error}. Por favor, verifica el estado de tu cuenta de OpenRouter o tus límites diarios."
        }), 502

    # 6. Pipeline de Voz (Kokoro / TTS alternativo)
    audio_url = None
    if output_mode in ["audio", "both"]:
        audio_url = f"/api/tts?text={requests.utils.quote(ai_response[:200])}"

    return jsonify({
        "response": ai_response,
        "sources": sources,
        "audio_url": audio_url,
        "model_used": used_model
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