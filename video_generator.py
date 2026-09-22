# -*- coding: utf-8 -*-
import os
import re
import time
import uuid
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

from tts_engine import TTSEngine

class WhiteboardVideoGenerator:
    def __init__(self, output_dir: str = "./uploads/video"):
        """
        Generador de videos animados tipo Pizarra (Whiteboard Video Summaries)
        con renders en estilo borrador/pizarra y narración por voz sintetizada.
        """
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        self.tts_engine = TTSEngine(output_folder=os.path.join(self.output_dir, "audio_tmp"))

    def _parse_summary_into_slides(self, text: str, title: str) -> List[Dict[str, Any]]:
        """
        Divide un texto de resumen en 3 a 5 tarjetas/diapositivas tipo pizarra.
        """
        cleaned = re.sub(r'\[SUGERENCIAS\]:.*', '', text, flags=re.DOTALL).strip()
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        
        slides = []
        
        # Diapositiva 1: Portada
        slides.append({
            "type": "cover",
            "title": title[:50] if title else "Resumen en Video - AVFenix",
            "bullets": ["📌 Resumen Ejecutivo Generado por IA", "🎙️ Narración por Voz Sintetizada"],
            "narration": f"Bienvenido al resumen en video del agente AVFenix. A continuación presentaremos los puntos clave de {title}."
        })
        
        # Extraer puntos o párrafos principales
        paragraphs = []
        current_p = []
        for line in lines:
            if line.startswith(('-', '*', '•', '1.', '2.', '3.', '4.', '5.')):
                paragraphs.append(re.sub(r'^[-*•\d\.\s]+', '', line))
            else:
                current_p.append(line)
                if len(' '.join(current_p)) > 150:
                    paragraphs.append(' '.join(current_p))
                    current_p = []
        if current_p:
            paragraphs.append(' '.join(current_p))
            
        if not paragraphs:
            paragraphs = ["Información procesada e indexada correctamente en la base de conocimientos."]
            
        # Agrupar en máximo 3 diapositivas de contenido
        chunk_size = max(1, len(paragraphs) // 3 + (1 if len(paragraphs) % 3 != 0 else 0))
        for i in range(0, len(paragraphs), chunk_size):
            group = paragraphs[i:i+chunk_size]
            slides.append({
                "type": "content",
                "title": f"Punto Clave {len(slides)}",
                "bullets": [p[:90] + ("..." if len(p) > 90 else "") for p in group],
                "narration": ". ".join(group[:2])
            })
            if len(slides) >= 4:
                break
                
        # Diapositiva Final: Conclusión
        slides.append({
            "type": "conclusion",
            "title": "Conclusión & Siguientes Pasos",
            "bullets": ["💡 Consulta el agente RAG para detalles específicos", "📄 Documento disponible en la base de conocimientos"],
            "narration": "Este ha sido el resumen en video. Puedes consultar más detalles interactuando con el agente RAG."
        })
        
        return slides

    def _render_whiteboard_frame(self, slide: Dict[str, Any], width: int = 1280, height: int = 720) -> Image.Image:
        """
        Dibuja un fotograma estilo pizarra con fondo blanco, bordes dibujados a mano,
        marcado azul/gris y encabezados destacados.
        """
        img = Image.new("RGB", (width, height), color="#F8FAFC")
        draw = ImageDraw.Draw(img)
        
        # Borde exterior simulación pizarra (Grid / Marco)
        draw.rectangle([20, 20, width - 20, height - 20], outline="#0284C7", width=4)
        draw.rectangle([26, 26, width - 26, height - 26], outline="#E2E8F0", width=2)
        
        # Intentar cargar fuentes estándar de Pillow
        try:
            title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 38)
            body_font = ImageFont.truetype("DejaVuSans.ttf", 26)
            subtitle_font = ImageFont.truetype("DejaVuSans-Oblique.ttf", 22)
        except Exception:
            title_font = ImageFont.load_default()
            body_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            
        # Encabezado Superior / Título
        draw.rectangle([40, 40, width - 40, 110], fill="#0284C7")
        draw.text((60, 52), slide["title"].upper(), fill="#FFFFFF", font=title_font)
        
        # Tipo de diapositiva
        draw.text((60, 125), f"AVFenix Whiteboard AI Summary | Modo: {slide['type'].upper()}", fill="#64748B", font=subtitle_font)
        
        # Cuerpo de viñetas / Bullet Points
        y_offset = 180
        for i, bullet in enumerate(slide["bullets"]):
            # Dibujar caja / tarjeta estilo pizarra
            box_top = y_offset
            box_bottom = y_offset + 80
            draw.rectangle([60, box_top, width - 60, box_bottom], fill="#FFFFFF", outline="#CBD5E1", width=2)
            draw.rectangle([60, box_top, 75, box_bottom], fill="#0369A1") # Acento lateral
            
            draw.text((95, box_top + 24), f"•  {bullet}", fill="#1E293B", font=body_font)
            y_offset += 105
            if y_offset > height - 100:
                break
                
        # Pie de página estilo marca de agua pizarra
        draw.line([40, height - 50, width - 40, height - 50], fill="#E2E8F0", width=2)
        draw.text((60, height - 40), "🤖 Generado por AVFenix Whiteboard Video Engine", fill="#94A3B8", font=subtitle_font)
        
        return img

    def generate_video(self, text_summary: str, title: str = "Resumen de Documento") -> Optional[str]:
        """
        Procesa el resumen, genera fotogramas estilo pizarra, sintetiza la voz
        y compila el archivo final .mp4.
        """
        try:
            slides = self._parse_summary_into_slides(text_summary, title)
            clips = []
            
            unique_id = f"whiteboard_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            
            for idx, slide in enumerate(slides):
                # 1. Renderizar fotograma PIL
                frame_img = self._render_whiteboard_frame(slide)
                frame_path = os.path.join(self.output_dir, f"{unique_id}_slide_{idx}.png")
                frame_img.save(frame_path)
                
                # 2. Sintetizar narración
                audio_filename = self.tts_engine.generate_audio(slide["narration"], output_dir=os.path.join(self.output_dir, "audio_tmp"))
                
                audio_path = None
                if audio_filename:
                    full_audio_p = os.path.abspath(os.path.join(self.output_dir, "audio_tmp", audio_filename))
                    if os.path.exists(full_audio_p) and os.path.getsize(full_audio_p) > 0:
                        audio_path = full_audio_p
                        
                # 3. Crear Clip de Imagen con MoviePy
                if audio_path:
                    audio_clip = AudioFileClip(audio_path)
                    duration = max(3.5, audio_clip.duration + 0.8)
                    img_clip = ImageClip(frame_path).with_duration(duration).with_audio(audio_clip)
                else:
                    duration = 5.0
                    img_clip = ImageClip(frame_path).with_duration(duration)
                    
                clips.append(img_clip)
                
            # 4. Concatenar y Renderizar Video
            final_clip = concatenate_videoclips(clips, method="compose")
            out_video_filename = f"{unique_id}.mp4"
            out_video_path = os.path.join(self.output_dir, out_video_filename)
            
            final_clip.write_videofile(
                out_video_path,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                logger=None
            )
            
            # Limpieza de temporales
            for clip in clips:
                clip.close()
            final_clip.close()
            
            return out_video_filename
            
        except Exception as e:
            print(f"[!] Error generando video tipo pizarra: {e}")
            return None
