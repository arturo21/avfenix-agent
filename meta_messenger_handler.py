# -*- coding: utf-8 -*-
import os
import requests
from typing import Dict, Any, Tuple, Optional, List

class MetaMessengerHandler:
    def __init__(self):
        """
        Mapeador e integrador oficial para Instagram Direct & Facebook Messenger
        a través de la API Graph de Meta.
        """
        self.page_access_token = os.environ.get("META_PAGE_ACCESS_TOKEN", "")
        self.instagram_access_token = os.environ.get("META_INSTAGRAM_ACCESS_TOKEN", self.page_access_token)
        self.verify_token = os.environ.get("META_VERIFY_TOKEN", "avfenix_meta_secret_2026")
        self.api_version = os.environ.get("META_API_VERSION", "v20.0")

    def verify_token_match(self, mode: str, token: str) -> bool:
        """Verifica la validez del token en la verificación de Webhooks de Meta."""
        return mode == 'subscribe' and token == self.verify_token

    def parse_incoming_payload(self, payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str], str]:
        """
        Analiza el payload JSON del Webhook de Meta para Instagram o Messenger.
        Devuelve (sender_id, message_text, message_id, platform).
        """
        try:
            object_type = payload.get('object', '')
            platform = "instagram" if object_type == "instagram" else "page"

            entries = payload.get('entry', [])
            if not entries:
                return None, None, None, platform

            for entry in entries:
                messaging = entry.get('messaging', [])
                if not messaging:
                    messaging = entry.get('changes', [])

                for item in messaging:
                    message_obj = item.get('message', {})
                    sender = item.get('sender', {})
                    sender_id = sender.get('id')
                    msg_id = message_obj.get('mid') or item.get('id')

                    if message_obj:
                        text = message_obj.get('text', '').strip()
                        if text:
                            return sender_id, text, msg_id, platform

                        quick_reply = message_obj.get('quick_reply', {})
                        if quick_reply and quick_reply.get('payload'):
                            return sender_id, quick_reply.get('payload'), msg_id, platform

                        attachments = message_obj.get('attachments', [])
                        if attachments:
                            att_type = attachments[0].get('type')
                            if att_type in ['audio', 'voice']:
                                return sender_id, "[NOTA DE VOZ RECIBIDA] ¿Puedes responder mi consulta?", msg_id, platform
                            return sender_id, "[CONTENIDO MULTIMEDIA ADJUNTO] Hola", msg_id, platform

                    postback = item.get('postback', {})
                    if postback:
                        title = postback.get('title') or postback.get('payload')
                        if title:
                            return sender_id, title, msg_id, platform

            return None, None, None, platform
        except Exception as e:
            print(f"[!] Error parseando payload de Instagram/Messenger: {e}")
            return None, None, None, "unknown"

    def send_message(self, recipient_id: str, text_content: str, suggestions: Optional[List[str]] = None, platform: str = "page") -> bool:
        """
        Envía un mensaje directo a un usuario en Instagram o Facebook Messenger.
        """
        token = self.instagram_access_token if platform == "instagram" else self.page_access_token
        if not token:
            token = self.page_access_token or os.environ.get("WHATSAPP_TOKEN", "")

        if not token:
            print(f"[!] ERROR: Token de acceso no configurado para Meta Messenger ({platform}).")
            return False

        url = f"https://graph.facebook.com/{self.api_version}/me/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        formatted_text = text_content
        if suggestions and len(suggestions) > 0:
            formatted_text += "\n\n💡 Sugerencias:\n"
            for sug in suggestions[:3]:
                clean_sug = str(sug).replace('\\', '').strip().strip('\'"')
                formatted_text += f"• {clean_sug}\n"

        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": formatted_text}
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code in [200, 201]:
                print(f"[*] Mensaje enviado con éxito a {platform.upper()} (User: {recipient_id})")
                return True
            else:
                print(f"[!] Error enviando a Meta Messenger ({response.status_code}): {response.text}")
                return False
        except Exception as e:
            print(f"[!] Excepción al conectar con Meta Graph API: {e}")
            return False
