# 🤖 AVFenix Customer Agent — RAG Multicanal, Resúmenes de Audio/Video, Analíticas & Leads

Bienvenido a **AVFenix Customer Agent**, un ecosistema inteligente de atención al cliente e IA conversacional impulsado por **RAG (Retrieval-Augmented Generation)**, **Chunking Semántico**, **Scraping Web**, **Memoria Persistente en SQLite**, **Síntesis de Voz (TTS)**, **Resúmenes en Video Animado estilo Pizarra (*Whiteboard Video Summaries*)** e **Integración Multicanal Unificada** para WhatsApp Cloud API, Instagram Direct, Facebook Messenger y Web Widgets.

---

## 🌟 Beneficios & Características Principales

* **Cero Alucinaciones (Zero-Hallucination RAG)**: Respuestas estrictamente fundamentadas en tu base de conocimientos (PDFs, Word DOCX, grabaciones de Audio/Video y URLs web) con temperatura `0.1`.
* **Resúmenes en Audio Completo e Ilimitado (TTS)**: Síntesis de voz continua sin límite de caracteres mediante Kokoro TTS (modelo ultra ligero Kokoro-82M), gTTS o pyttsx3, con subprocesos aislados para evitar colapsos.
* **Resúmenes en Video Animado estilo Pizarra (Whiteboard Video Summaries)**: Generación automática de videos `.mp4` con diapositivas estilo borrador de pizarra, marcadores visuales y narración sintetizada integrada.
* **Soporte Multimodal Ampliado**: Procesamiento y transcripción de archivos de video y audio (`.mp4`, `.mov`, `.avi`, `.mkv`) mediante `ffmpeg` para indexación semántica en RAG.
* **Visualización de Estadísticas & Leads en Dashboard HTML/JS**: Panel de control interactivo para revisar el rendimiento, volumen de usuarios, desglose por canal (Web, WhatsApp, Instagram, Facebook) y la lista de prospectos (*leads*) capturados.
* **Exportación de Leads a CSV**: Descarga en tiempo real de prospectos capturados con correo, teléfono, consulta y canal de origen.
* **Modelos 100% Gratuitos (AnyAPI AI & OpenRouter)**: Algoritmo de selección dinámica que conmuta automáticamente entre los modelos libres más estables (Gemini 2.5 Flash, LLaMA 3.3 70B, DeepSeek R1, Qwen 2.5).
* **Sugerencias Clickeables e Interactivas**: Cada respuesta del bot genera automáticamente 3 sugerencias para guiar al usuario.
* **Memoria Conversacional Persistente**: Contexto histórico por usuario almacenado en SQLite (`conversations.db`).
* **Arranque Ultra Rápido (< 1s)**: Servidor optimizado con deshabilitación de reloader doble y carga perezosa de dependencias pesadas.

---

## 📊 Módulos y Estructura del Proyecto

```
/
├── app.py                     # Servidor backend Flask (RAG, Webhooks, Analytics, Resúmenes)
├── database_manager.py        # Gestor de base de datos SQLite (Historial, Leads y Exportación CSV)
├── document_processor.py      # Extractor de PDF, DOCX, Video/Audio y Web Scraper con Chunking Semántico
├── vector_store.py            # Almacén vectorial TF-IDF con similitud coseno local
├── tts_engine.py              # Motor de síntesis de voz (Kokoro-82M, gTTS, pyttsx3) ilimitado con subprocesos
├── video_generator.py         # Generador de resúmenes en video animado tipo pizarra (.mp4)
├── whatsapp_handler.py        # Integración oficial Meta Cloud API para WhatsApp
├── meta_messenger_handler.py  # Integración oficial para Instagram Direct & Facebook Messenger
├── dashboard_web.txt          # Consola web HTML/JS/Tailwind con Chat, Analíticas y Resúmenes Audio/Video
├── test_master_suite.py       # Suite de pruebas máster automatizadas (12/12 pruebas 100% OK)
└── requirements.txt           # Dependencias de Python
```

---

## ⚡ Instalación y Puesta en Marcha

1. **Instalar dependencias de Python:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Instalar dependencias de sistema (para procesamiento fonético y multimedia):**
   ```bash
   # En Debian/Ubuntu:
   sudo apt-get update && sudo apt-get install -y espeak-ng ffmpeg
   ```

3. **Ejecutar el servidor backend:**
   ```bash
   python3 app.py
   ```
   *El servidor iniciará en menos de 1 segundo en `http://localhost:5000/`.*

4. **Acceder a la consola web:**
   Navega a `http://localhost:5000/` en tu explorador. Podrás cargar archivos, solicitar resúmenes en audio (`⚡ Audio`) o video (`🎥 Pizarra`), y chatear con el agente RAG.

---

## 📈 Visualización de Estadísticas y Leads

1. Abre la consola web y dirígete a la pestaña **"Estadísticas & Leads"**.
2. Revisa en tiempo real:
   - **Métricas Clave**: Total de Usuarios, Total de Mensajes, Total de Leads y Modelo Activo.
   - **Volumen por Canal**: Gráficos de barras con la distribución porcentual de Web, WhatsApp, Instagram y Facebook.
   - **Tabla de Leads y Exportación CSV**: Descarga inmediata de contactos detectados con el botón **"Exportar Leads (CSV)"**.

---

## 🧪 Ejecución de la Suite de Pruebas Automatizadas

Para verificar la integridad de todos los módulos y endpoints de la aplicación:
```bash
python3 test_master_suite.py
```

---

AVFenix Zero-Hallucination Agent Console &copy; 2026.
