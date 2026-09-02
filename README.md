# 🤖 AVFenix Agent (Fase 1 - Versión Estable)

¡Bienvenido al repositorio oficial de **AVFenix Agent**! Este es un motor de agentes de atención al cliente y asesoría de IA impulsado por la arquitectura **RAG (Retrieval-Augmented Generation)**. 

El principal objetivo de este proyecto es proveer un asistente inteligente e interactivo que **se ciña estrictamente a la base de conocimientos** (archivos PDF o Word) que el administrador le proporcione, asegurando **cero alucinaciones** y un comportamiento corporativo profesional.

---

## 🌟 Beneficios Clave

*   🛡️ **Zero-Hallucination (Cero Alucinaciones)**: Diseñado con prompts de sistema altamente restrictivos y temperatura mínima (`0.1`) para garantizar que el agente nunca invente hechos, enlaces o características. Si el tema no está en los documentos, el bot admitirá honestamente que no dispone de esa información.
*   💸 **100% Gratis & Libre de Costes**: Utiliza un motor de base vectorial local (offline y sin cargos de API) integrado con la capa gratuita oficial de **OpenRouter** para el procesamiento del modelo de lenguaje.
*   🎙️ **Experiencia de Voz Integrada**: Los usuarios pueden interactuar de manera fluida mediante voz (dictado por voz native en navegador STT) y recibir respuestas leídas en voz alta (TTS) de forma gratuita y local.
*   🔄 **Resiliencia Extrema (Zero Downtime)**: Equipado con un algoritmo de reintento secuencial automatizado. Si el modelo gratuito primario falla o se satura, el backend cambia de inmediato y de forma invisible al siguiente modelo gratuito de respaldo.

---

## ⚙️ Características Técnicas

1.  **Semantic Chunking (Segmentación Semántica)**: En lugar de cortar textos por caracteres fijos que rompen el contexto, el procesador divide los PDFs y archivos de Word a nivel de oraciones y agrupa bloques mediante similitud coseno local de embeddings TF-IDF.
2.  **Base Vectorial Local Ligera**: Indexación rápida y offline que persiste en disco (`vector_index.pkl`) utilizando Scikit-Learn y NumPy. No requiere bases de datos en la nube de pago.
3.  **Arquitectura Backend Flask**: Lógica desacoplada mediante una API REST en Flask que facilita la reutilización del "cerebro" del agente para conectar múltiples frontends (Web, Android, WhatsApp, Messenger o Instagram).
4.  **Consola de Administración Dual**: 
    *   **Dashboard Streamlit**: Una interfaz interactiva premium en Python para gestionar archivos e historial de chat.
    *   **Dashboard Web Standalone**: Interfaz en HTML5 y Tailwind CSS ligera, responsiva y portable que funciona directamente abriéndose en el navegador.

---

## 🛠️ Estructura del Proyecto

El código está estructurado en módulos desacoplados listos para producción:

```text
├── app.py                     # API central en Flask (Manejo de rutas, OpenRouter y CORS)
├── document_processor.py       # Extractor de PDF/DOCX y motor de Segmentación Semántica
├── vector_store.py            # Motor de Base de Datos Vectorial Local y similitud coseno
├── dashboard_streamlit.py     # Panel de Control Premium desarrollado en Streamlit
├── dashboard.html             # Consola Web Autónoma (Tailwind CSS, Drag & Drop y Voz STT/TTS)
├── widget.html                # Widget flotante interactivo listo para incrustar en sitios web
├── requirements.txt           # Dependencias necesarias para levantar el proyecto
└── .env                       # Archivo secreto de configuración de credenciales (API Keys)
```

---

## ⚡ Guía de Instalación y Puesta en Marcha

### 1. Clonar el repositorio e instalar dependencias
Asegúrate de contar con **Python 3** en tu sistema local o VPS:
```bash
git clone https://github.com/tu-usuario/avfenix-agent.git
cd avfenix-agent
pip install -r requirements.txt
```

### 2. Configurar las variables de entorno
Crea un archivo llamado `.env` en la raíz del proyecto y añade tu API Key de OpenRouter:
```env
OPENROUTER_API_KEY="tu_clave_secreta_de_openrouter"
```
*(Opcional: El backend detectará automáticamente los modelos gratuitos disponibles en OpenRouter, pero puedes forzar uno declarando `OPENROUTER_MODEL="google/gemini-2.5-flash:free"`).*

### 3. Ejecutar el Servidor Backend (Flask)
Inicia la API central de soporte:
```bash
python3 app.py
```
El servidor se levantará en `http://localhost:5000` con CORS habilitado de forma predeterminada para recibir peticiones de cualquier cliente web.

### 4. Lanzar los Dashboards de Control

*   **Para usar la Consola Web Ligera**: Simplemente abre el archivo `dashboard.html` haciendo doble clic desde tu ordenador.
*   **Para usar el Dashboard Streamlit**:
    ```bash
    streamlit run dashboard_streamlit.py
    ```

---

## 🛡️ Control y Corrección de Errores (Log de Estabilidad)

Durante la fase de auditoría técnica y pruebas de la Fase 1, se han resuelto de forma estable los siguientes fallos críticos reportados en entornos de producción:

*   **Solución al Error de Codificación ASCII (`SyntaxError: Non-ASCII character` - PEP-263)**: Se añadió la declaración explícita de codificación `# -*- coding: utf-8 -*-` al inicio de todos los scripts para asegurar total compatibilidad en sistemas que corren entornos híbridos de Python.
*   **Corrección de Sintaxis de Rutas**: Eliminación de caracteres de escape de salto de línea (`\n`) que colapsaban la carga de decoradores de endpoints `@app.route` de Flask.
*   **Corrección en el Flujo Lógico de Saludos**: Se modificó la regla de detección de base de conocimientos. Previamente, al enviar un simple saludo como *"Hola"*, el agente respondía que "No había base de conocimientos cargada" debido a que la similitud de similitud vectorial de la palabra "hola" con el PDF técnico daba `0.0`. Ahora, Flask valida si existen archivos físicos indexados antes de evaluar la similitud, permitiendo saludos naturales de cortesía.
*   **Inmunidad a Fallos de Modelos de OpenRouter (`'NoneType' object has no attribute 'strip'`)**: Algunos modelos gratuitos como `inclusionai/ling-3.0-flash-fin:free` sufren interrupciones y devuelven respuestas vacías (`None`). El backend fue blindado con:
    1.  **Lista Negra**: Se ignoran automáticamente los modelos inestables del catálogo de OpenRouter.
    2.  **Reintento de Emergencia**: Ante cualquier respuesta vacía o error del modelo seleccionado dinámicamente, Flask intercepta el fallo en milisegundos y hace una petición automática usando `google/gemini-2.5-flash:free` de respaldo de forma invisible al usuario.

---

## 🔮 Próximas Fases

*   **Fase 3 (WhatsApp)**: Creación del webhook `/api/whatsapp` para conectar el RAG con la API oficial de WhatsApp Cloud de Meta.
*   **Fase 4 (Facebook & Instagram)**: Webhook unificado de Meta Messenger para automatizar la atención en redes sociales con el mismo cerebro documental.
*   **Fase 5 (Voz con Kokoro Local)**: Sustitución de la síntesis del navegador por la síntesis neuronal local ultra-realista con **Kokoro TTS**.