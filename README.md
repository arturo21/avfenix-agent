# AVFenix Agent - Agente IA de Atención al Cliente con RAG (Fase 1 & Fase 2)

Este proyecto implementa el backend y el widget web de un **Agente IA de Soporte Técnico y Atención al Cliente** ultra seguro y libre de alucinaciones. El sistema lee documentos en formato **PDF** y **Word (.docx)** proporcionados por ti, extrae su información utilizando **Chunking Semántico**, y responde a los usuarios exclusivamente con base en esa información.

---

## 🏗️ Arquitectura y Stack Tecnológico

1. **Backend API (Flask - Python)**:
   - **Procesador de Documentos (`document_processor.py`)**: Extrae texto usando `pypdf` para PDFs y `python-docx` para archivos Word. Aplica un algoritmo de **Semantic Chunking** local que agrupa oraciones adyacentes utilizando similitud coseno de sus vectores TF-IDF. Esto mantiene la cohesión de los temas sin dividir ideas en partes.
   - **Base de Datos Vectorial Local (`vector_store.py`)**: Motor de búsqueda local que vectoriza consultas en tiempo real y realiza una búsqueda de similitud coseno ultrarrápida. Almacena el índice de conocimiento en disco como un archivo persistente binario (`vector_index.pkl`) de forma gratuita.
   - **Orquestador API (`app.py`)**: Servidor Flask que expone las rutas REST para subida, listado, eliminación y consultas del chat. Utiliza **OpenRouter** conectado a **Gemini 2.5 Flash** con una temperatura muy baja (`0.1`) y un prompt del sistema restrictivo que prohíbe explícitamente inventar información (Zero-Hallucination).

2. **Frontend Widget Web (`widget.html`)**:
   - Interfaz en formato de **widget flotante** tipo botón de soporte técnico.
   - **Reconocimiento de voz integrado**: Usa la API gratuita del navegador (**Web Speech API**) para transcribir voz a texto directamente al hacer clic en el botón de micrófono.
   - **Lector por voz integrado**: Utiliza el sintetizador nativo de voz de tu navegador de manera gratuita como un fallback rápido si la opción de voz está activada.
   - **Panel de Administración Secreto**: Permite arrastrar y soltar archivos PDF y Word directamente, ver qué archivos están en la base del agente y borrarlos en tiempo real.

---

## 🛠️ Instalación y Configuración Paso a Paso

### 1. Requisitos Previos
Asegúrate de tener instalado Python 3.10 o superior.

### 2. Instalación de Dependencias
Descomprime o copia los archivos y ejecuta el siguiente comando en tu consola para instalar los paquetes necesarios:

```bash
pip install -r requirements.txt
```

### 3. Configuración de Credenciales
Debes configurar tu clave de API de **OpenRouter** para permitir que el agente consulte el modelo Gemini. Ejecuta en tu terminal:

*   **Linux/macOS**:
    ```bash
    export OPENROUTER_API_KEY="tu_clave_de_openrouter"
    ```
*   **Windows (Command Prompt - CMD)**:
    ```cmd
    set OPENROUTER_API_KEY="tu_clave_de_openrouter"
    ```
*   **Windows (PowerShell)**:
    ```powershell
    $env:OPENROUTER_API_KEY="tu_clave_de_openrouter"
    ```

### 4. Lanzar el Servidor Backend
Inicia la API ejecutando:

```bash
python app.py
```

El servidor se ejecutará en `http://localhost:5000` y creará automáticamente una carpeta llamada `uploads` donde guardará los documentos físicos y el índice vectorial persistente `vector_index.pkl`.

### 5. Probar el Widget Web
Simplemente haz doble clic en el archivo `widget.html` para abrirlo en tu navegador. 
- Abre el widget flotante en la esquina inferior derecha.
- Haz clic en el icono de **engrane/herramientas** de la cabecera para abrir el **Panel de Administración**.
- Arrastra o selecciona tus archivos PDF o DOCX de prueba. ¡Verás que se procesan y se añaden dinámicamente a la lista!
- Vuelve a la pestaña de chat y haz cualquier consulta. ¡El agente responderá de forma inteligente basándose únicamente en lo que subiste y te mostrará las fuentes empleadas con su relevancia exacta!

---

## 🔮 Roadmap: Conexión con Canales de Mensajería (Fases 3 y 4)

El backend en Flask expone un endpoint unificado `/api/chat` que está listo para ser consumido por cualquier otro canal. Aquí tienes el mapa técnico de cómo conectarlo en las siguientes fases:

1. **WhatsApp (API Cloud de Meta)**:
   - Crear una ruta `POST /api/whatsapp` en `app.py`.
   - Meta enviará un mensaje entrante (Webhook) con formato JSON que contiene el texto del usuario y su número telefónico.
   - Tu backend consulta a `vector_store.query(mensaje_usuario)` y procesa la respuesta mediante OpenRouter.
   - Envías de vuelta la respuesta llamando al endpoint de WhatsApp de Meta usando `requests.post("https://graph.facebook.com/v17.0/YOUR_PHONE_NUMBER_ID/messages", ...)` con tu Token de Acceso Permanente.

2. **Facebook Messenger / Instagram Direct**:
   - Crear una ruta unificada `POST /api/meta-messenger` en `app.py`.
   - Meta requiere verificar el webhook mediante un token de verificación (método `GET`).
   - Una vez verificado, Meta enviará cada mensaje como un evento `messaging` de webhook.
   - Llamas al motor RAG local y envías la respuesta usando la API de Meta Send (`https://graph.facebook.com/v17.0/me/messages`).
