# -*- coding: utf-8 -*-
import os
import requests
from typing import Dict, Any, Tuple, Optional, List

class WhatsAppHandler:
    def __init__(self):
        """
        Mapeador e integrador oficial para WhatsApp Cloud API de Meta.
        Lee las credenciales del entorno (.env).
        """
        self.phone_id = os.environ.get("WHATSAPP_PHONE_ID", "")
        self.access_token = os.environ.get("WHATSAPP_TOKEN", "")
        self.verify_token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "avfenix_secret_token_2026")
        self.api_version = os.environ.get("WHATSAPP_API_VERSION", "v20.0")

    def verify_token_match(self, mode: str, token: str) -> bool:
        """
        Verifica que el hub.mode sea 'subscribe' y que el token coincida con WHATSAPP_VERIFY_TOKEN.
        """
        return mode == 'subscribe' and token == self.verify_token

    def parse_incoming_payload(self, payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Analiza el payload JSON enviado por los webhooks de Meta WhatsApp Cloud API.
        Devuelve (phone_number, message_text, message_id).
        """
        try:
            entries = payload.get('entry', [])
            if not entries:
                return None, None, None
                
            for entry in entries:
                changes = entry.get('changes', [])
                for change in changes:
                    value = change.get('value', {})
                    messages = value.get('messages', [])
                    if messages:
                        msg = messages[0]
                        sender_phone = msg.get('from')
                        msg_id = msg.get('id')
                        msg_type = msg.get('type')
                        
                        # Manejar mensajes de texto simples
                        if msg_type == 'text':
                            text_body = msg.get('text', {}).get('body', '').strip()
                            return sender_phone, text_body, msg_id
                            
                        # Manejar respuestas a botones/listas interactivas
                        elif msg_type == 'interactive':
                            interactive = msg.get('interactive', {})
                            itype = interactive.get('type')
                            if itype == 'button_reply':
                                button_text = interactive.get('button_reply', {}).get('title', '')
                                return sender_phone, button_text, msg_id
                            elif itype == 'list_reply':
                                list_title = interactive.get('list_reply', {}).get('title', '')
                                return sender_phone, list_title, msg_id
                                
                        # Si es nota de voz o documento
                        elif msg_type in ['audio', 'voice']:
                            return sender_phone, "[NOTA DE VOZ RECIBIDA] ¿Puedes darme un resumen o información general?", msg_id
                        elif msg_type in ['document', 'image']:
                            return sender_phone, "[ARCHIVO O IMAGEN ADJUNTA] Hola, ¿en qué me puedes ayudar?", msg_id

            return None, None, None
        except Exception as e:
            print(f"[!] Error al parsear payload de WhatsApp: {e}")
            return None, None, None

    def send_message(self, recipient_phone: str, text_content: str, suggestions: Optional[List[str]] = None) -> bool:
        """
        Envía un mensaje de texto de respuesta a WhatsApp utilizando Meta Graph API.
        Formatea las sugerencias como lista o botones interactivos de acceso rápido.
        """
        if not self.phone_id or not self.access_token:
            print("[!] ERROR: WHATSAPP_PHONE_ID o WHATSAPP_TOKEN no están configurados en el .env.")
            return False

        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        formatted_text = text_content
        
        # Añadir sugerencias al pie del mensaje
        if suggestions and len(suggestions) > 0:
            formatted_text += "\n\n💡 *Sugerencias para continuar:*\n"
            for sug in suggestions[:3]:
                # Saneamiento de sugerencias
                clean_sug = str(sug).replace('\\', '').strip().strip('\'"')
                formatted_text += f"🔹 {clean_sug}\n"

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": formatted_text
            }
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code in [200, 201]:
                print(f"[*] Mensaje enviado con éxito a WhatsApp (+{recipient_phone})")
                return True
            else:
                print(f"[!] Error enviando mensaje a WhatsApp ({response.status_code}): {response.text}")
                return False
        except Exception as e:
            print(f"[!] Excepción al conectar con WhatsApp API Graph: {e}")
            return False

    def send_audio_message(self, recipient_phone: str, audio_url: str) -> bool:
        """
        Envía una nota de voz / audio como mensaje multimedia en WhatsApp.
        """
        if not self.phone_id or not self.access_token or not audio_url:
            return False

        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "audio",
            "audio": {
                "link": audio_url
            }
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            return response.status_code in [200, 201]
        except Exception as e:
            print(f"[!] Excepción enviando audio a WhatsApp: {e}")
            return False
