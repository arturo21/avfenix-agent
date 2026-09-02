# 🤖 AVFenix Agent: Sistema RAG Multicanal Inmune a Alucinaciones

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org)
[![Flask](https://img.shields.io/badge/backend-Flask-orange.svg)](https://flask.palletsprojects.com/)
[![OpenRouter](https://img.shields.io/badge/LLM-OpenRouter%20Free-green.svg)](https://openrouter.ai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AVFenix Agent** es un ecosistema inteligente de atención al cliente e IA conversacional diseñado para proporcionar asesoramiento ultra-preciso basado estrictamente en documentos de texto cargados por el usuario (en formatos **PDF** y **DOCX**). Al operar bajo una arquitectura **RAG (Retrieval-Augmented Generation)** altamente restrictiva, este agente actúa de forma autónoma garantizando **cero alucinaciones** y un comportamiento 100% fiel a tu base de conocimientos corporativa.

La lógica centralizada en un backend flexible (Flask) te permite desplegar la IA en múltiples interfaces: desde un elegante **Widget Web flotante**, un **Dashboard de administración en Streamlit**, hasta integraciones de mensajería como **WhatsApp, Instagram y Facebook**.

---

## 🌟 Beneficios Clave

*   **🔒 Cero Alucinaciones (Zero-Hallucination)**: Configuraciones optimizadas con un prompt del sistema ultra-estricto y una **temperatura baja (0.1)**. Si la consulta del cliente no se encuentra explícitamente en tus documentos, el agente responderá de forma honesta y cortés: *"Lo siento, no encuentro información sobre ese tema en mi base de conocimientos actual."*
*   **💸 100% Costo Cero en Modelos**: Integración con el catálogo de modelos gratuitos de **OpenRouter** de manera dinámica (Gemini, Llama, Qwen, Mistral).
*   **📦 Base Vectorial Local e Instantánea**: Búsqueda semántica implementada localmente en memoria y disco (`vector_index.pkl`) mediante TF-IDF y similitud coseno de Scikit-Learn y NumPy. **Sin suscripciones ni bases de datos vectoriales en la nube de pago.**
*   **🎙️ Experiencia Conversacional de Voz Completa**:
    *   *Entrada (STT)*: El usuario puede dictar sus preguntas por voz desde el navegador de manera gratuita y nativa gracias a la **Web Speech API**.
    *   *Salida (TTS)*: Respuestas habladas generadas de forma gratuita con la síntesis nativa del navegador, con compatibilidad integrada para conectarse con la avanzada tubería local de **Kokoro TTS**.
*   **🛠️ Gestión Autónoma de Archivos**: Sube, elimina e indexa múltiples PDFs y archivos de Word en tiempo real directamente desde la interfaz web o consola.

---

## 🛠️ Características de la Arquitectura

### 1. Chunking Semántico (Semantic Chunking)
A diferencia de los cortadores tradicionales que dividen el texto de manera rígida por número de caracteres (rompiendo ideas y contextos a la mitad), nuestro **`DocumentProcessor`** inteligente:
*   Extrae el texto de archivos Word (`docx`) y PDFs (`pypdf`).
*   Divide el contenido en oraciones y calcula la similitud coseno de los vectores locales TF-IDF de oraciones contiguas.
*   Divide los fragmentos únicamente en los puntos de transición de temas (cuando la similitud cae por debajo de un umbral adaptable), protegiendo la cohesión de la información antes de la indexación.

### 2. Algoritmo de Selección y Reintento de Emergencia (Zero-Downtime)
Los entornos de API gratuitos de OpenRouter son susceptibles a congestión. Para blindar al agente, hemos implementado una **tubería de recuperación en cascada**:
*   **Lista Negra Activa**: Excluye automáticamente modelos inestables del tier gratis que devuelven respuestas vacías (como `inclusionai/ling-3.0-flash-fin:free`).
*   **Orden de Prioridad Estructurado**: Evalúa dinámicamente el catálogo gratis y prefiere modelos de alto rendimiento como `google/gemini-2.5-flash:free` y `meta-llama/llama-3.3-70b-instruct:free`.
*   **Reintento de Emergencia Automático**: Si el modelo primario seleccionado falla o devuelve una respuesta nula, el backend intercepta el fallo en milisegundos y relanza la petición de forma transparente utilizando el ultra-estable modelo de respaldo de Google.

---

## 📂 Mapa de Archivos del Proyecto

```text
avfenix-agent/
│
├── app.py                      # API Backend en Flask con RAG, OpenRouter y manejo de CORS
├── document_processor.py       # Extractor de PDF/Word y algoritmo de Chunking Semántico
├── vector_store.py             # Base vectorial offline local (TF-IDF + Coseno + persistencia Pickle)
├── requirements.txt            # Dependencias del proyecto Python
├── .env                        # Archivo de variables de entorno seguras (API Key, Límites)
│
├── dashboard_streamlit.py      # Dashboard premium para administración de base de conocimientos y chats
├── dashboard_web.html          # Panel Web HTML/Tailwind alternativo y standalone
└── widget_code.txt             # Código HTML/JS listo para insertar como burbuja flotante en cualquier web
```

---

## 💎 Versión Estable y Solución de Errores (Log de Producción)

Durante la optimización y pruebas de estabilidad del agente para producción se aplicaron las siguientes soluciones definitivas:

*   **Error de Sintaxis Non-ASCII en app.py (Línea 7)**:
    *   *Causa*: Intérpretes configurados en Python 2 fallaban al encontrarse con comentarios en español con caracteres como acentos u 'ñ'.
    *   *Solución*: Se declaró explícitamente la codificación UTF-8 en la cabecera de todos los scripts (`# -*- coding: utf-8 -*-`) y se migró todo el soporte para una ejecución nativa en **Python 3**.
*   **Error de CORS en Rutas OPTIONS del Navegador**:
    *   *Causa*: Peticiones pre-flight bloqueadas por navegadores web al consumir la API Flask desde dominios externos.
    *   *Solución*: Implementación manual y robusta de decoradores `@app.after_request` para inyectar cabeceras CORS libres (`*`), eliminando cualquier dependencia de librerías terceras inestables.
*   **Falsas Alertas de Base de Conocimientos Vacía**:
    *   *Causa*: Al saludar con un *"Hola"*, la similitud de caracteres con los PDFs indexados daba `0.0`. El backend asumía erróneamente que no había base de conocimientos cargada en absoluto.
    *   *Solución*: Se separaron las validaciones. Ahora Flask verifica el tamaño físico del almacén vectorial (`vector_store.chunks`). Si está cargado, procesa los saludos de cortesía de forma profesional y empática, manteniendo el filtro restrictivo de RAG activo para las preguntas.
*   **Excepción `'NoneType' object has no attribute 'strip'`**:
    *   *Causa*: Fallos de servicio y respuestas vacías devueltas por modelos gratuitos inestables de OpenRouter.
    *   *Solución*: Incorporación del sistema de lista negra y del **mecanismo de reintento secuencial en cascada**. Si un modelo devuelve nulo, se conmuta al instante con un fallback de emergencia a `google/gemini-2.5-flash:free`.
*   **Corte Abrupto de Respuestas**:
    *   *Causa*: El parámetro de OpenRouter `max_tokens` estaba topado en un valor muy bajo (800 tokens).
    *   *Solución*: Se incrementó el límite predeterminado a **2000 tokens** para dar soporte a explicaciones extensas y ricas basadas en los documentos, volviéndose además completamente configurable de forma externa a través del archivo de entorno `.env`.

---

## 🚀 Instalación y Puesta en Marcha

### 1. Clonar el repositorio e Instalar dependencias
```bash
git clone https://github.com/tu-usuario/avfenix-agent.git
cd avfenix-agent
pip install -r requirements.txt
```

### 2. Configurar Variables de Entorno (`.env`)
Crea un archivo llamado `.env` en la raíz del proyecto y define tus configuraciones de OpenRouter de forma segura:
```env
OPENROUTER_API_KEY="tu_api_key_secreta_de_openrouter_aqui"
# Define el límite de tokens de respuesta (ej. 2000 tokens para respuestas largas sin cortes)
OPENROUTER_MAX_TOKENS=2000
```

### 3. Levantar el Cerebro Backend (API Flask)
```bash
python3 app.py
```
*El backend se levantará escuchando en `http://localhost:5000` listo para procesar documentos, vectorizar y responder consultas.*

### 4. Lanzar la Consola de Administración (Dashboard Streamlit)
```bash
streamlit run dashboard_streamlit.py
```
*Se abrirá automáticamente una pestaña interactiva en tu navegador. Sube tus PDFs o DOCXs de asesoría y haz tus primeras preguntas al agente.*

---

## 📝 Licencia

Este proyecto está bajo la licencia MIT. Siéntete libre de clonarlo, mejorarlo y adaptarlo a tus necesidades comerciales o proyectos personales de atención al cliente con IA.