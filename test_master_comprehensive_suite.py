# -*- coding: utf-8 -*-
import unittest
import json
import os
import sys
import tempfile
import io
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath('/workspace/scratch'))

os.environ["ANYAPI_API_KEY"] = "test_anyapi_key_master"
os.environ["OPENROUTER_API_KEY"] = "test_openrouter_key_master"
os.environ["WHATSAPP_PHONE_ID"] = "100000000000"
os.environ["WHATSAPP_TOKEN"] = "EAATestTokenWhatsApp"
os.environ["META_PAGE_ACCESS_TOKEN"] = "EAATestTokenMetaPage"

import app as app_module

class TestAVFenixMasterComprehensiveSuite(unittest.TestCase):
    def setUp(self):
        app_module.app.config['TESTING'] = True
        self.client = app_module.app.test_client()
        self.temp_dir = tempfile.mkdtemp()
        app_module.app.config['UPLOAD_FOLDER'] = self.temp_dir
        app_module.app.config['AUDIO_FOLDER'] = os.path.join(self.temp_dir, "audio")
        os.makedirs(app_module.app.config['AUDIO_FOLDER'], exist_ok=True)

        db_path = os.path.join(self.temp_dir, "test_conversations.db")
        app_module.db_manager.db_path = db_path
        app_module.db_manager._init_db()

        app_module.vector_store.storage_path = os.path.join(self.temp_dir, "test_index.pkl")
        app_module.vector_store.chunks = [{
            "text": "AVFenix ofrece planes de asesoría y agentes inteligentes multicanal RAG con cero alucinaciones.",
            "metadata": {"filename": "manual_avfenix.pdf", "page_number": 1, "chunk_id": "manual_1"}
        }]
        app_module.vector_store._rebuild_index()

    def test_01_health_and_analytics(self):
        res = self.client.get('/api/health')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('analytics', data)
        self.assertIn('tts_engine_type', data)

    def test_02_export_leads_csv(self):
        app_module.db_manager.save_lead("usr_101", "web", "Juan Pérez", "juan@ejemplo.com", "+5215511223344", "Cotización de servicios RAG")
        
        res = self.client.get('/api/export_leads')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'text/csv')
        csv_str = res.data.decode('utf-8')
        self.assertIn("Usuario ID", csv_str)
        self.assertIn("juan@ejemplo.com", csv_str)
        self.assertIn("Cotización de servicios RAG", csv_str)

    @patch('requests.post')
    def test_03_chat_and_lead_registration(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Ofrecemos soporte personalizado.\n[SUGERENCIAS]: [\"¿Cómo contratar?\", \"¿Qué requisitos hay?\", \"¿Precios?\"]"
                }
            }]
        }
        mock_post.return_value = mock_resp

        payload = {
            "message": "Hola, me interesa una cotización mi correo es cliente@empresa.com",
            "user_id": "usr_web_001",
            "channel": "web"
        }
        res = self.client.post('/api/chat', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("soporte personalizado", data['response'])
        self.assertEqual(len(data['suggestions']), 3)

        summary = app_module.db_manager.get_analytics_summary()
        self.assertGreaterEqual(summary['total_leads'], 1)

    def test_04_document_lifecycle(self):
        with patch.object(app_module.processor, 'process_file') as mock_process:
            mock_process.return_value = [{"text": "Fragmento de prueba PDF extenso con palabras claves para RAG", "metadata": {"filename": "documento_prueba.pdf", "page_number": 1, "chunk_id": "doc_1"}}]

            # Intentar subir archivo inválido
            res_exe = self.client.post('/api/upload', data={'file': (io.BytesIO(b"binary"), "script.exe")})
            self.assertEqual(res_exe.status_code, 400)

            # Subir PDF válido
            pdf_bytes = b"%PDF-1.4 mock pdf content"
            res_pdf = self.client.post('/api/upload', data={'file': (io.BytesIO(pdf_bytes), "documento_prueba.pdf")})
            self.assertEqual(res_pdf.status_code, 200)

            # Borrar documento
            res_del = self.client.delete('/api/delete/documento_prueba.pdf')
            self.assertEqual(res_del.status_code, 200)

    def test_05_scrape_url(self):
        with patch.object(app_module.processor, 'process_url') as mock_process_url:
            mock_process_url.return_value = [{"text": "Página oficial de soporte de AVFenix", "metadata": {"filename": "WEB_avfenix_com", "page_number": 1, "chunk_id": "web_1"}}]
            res = self.client.post('/api/scrape_url', json={"url": "https://avfenix.com/soporte"})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertIn("indexada con éxito", data['message'])

    def test_06_history_and_analytics_breakdown(self):
        app_module.db_manager.save_message("usr_002", "whatsapp", "user", "Hola desde WhatsApp")
        app_module.db_manager.save_message("usr_002", "whatsapp", "assistant", "Hola, ¿en qué te ayudo?")

        res_hist = self.client.get('/api/history/usr_002')
        self.assertEqual(res_hist.status_code, 200)
        hist_data = res_hist.get_json()
        self.assertEqual(len(hist_data['messages']), 2)

        res_analytics = self.client.get('/api/analytics')
        self.assertEqual(res_analytics.status_code, 200)
        analytics_data = res_analytics.get_json()
        self.assertIn('messages_by_channel', analytics_data)
        self.assertIn('whatsapp', analytics_data['messages_by_channel'])

    def test_07_tts_and_audio_serving(self):
        res_tts = self.client.get('/api/tts?text=Prueba_de_audio_sintetizado')
        self.assertEqual(res_tts.status_code, 200)
        data = res_tts.get_json()
        self.assertIn('audio_url', data)
        audio_filename = data['filename']

        res_audio = self.client.get(f'/api/audio/{audio_filename}')
        self.assertEqual(res_audio.status_code, 200)

    def test_08_whatsapp_webhook_flow(self):
        res_get = self.client.get('/api/whatsapp?hub.mode=subscribe&hub.verify_token=avfenix_secret_token_2026&hub.challenge=code_123')
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.data.decode('utf-8'), 'code_123')

        with patch.object(app_module.whatsapp_handler, 'send_message') as mock_send:
            mock_send.return_value = True
            payload = {
                "object": "whatsapp_business_account",
                "entry": [{
                    "id": "123456",
                    "changes": [{
                        "value": {
                            "messages": [{
                                "from": "5215599887766",
                                "id": "msg_wa_99",
                                "text": {"body": "Atención al cliente"},
                                "type": "text"
                            }]
                        }
                    }]
                }]
            }
            res_post = self.client.post('/api/whatsapp', json=payload)
            self.assertEqual(res_post.status_code, 200)
            mock_send.assert_called_once()

    def test_09_meta_messenger_webhook_flow(self):
        res_get = self.client.get('/api/meta_messenger?hub.mode=subscribe&hub.verify_token=avfenix_meta_secret_2026&hub.challenge=meta_123')
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.data.decode('utf-8'), 'meta_123')

        with patch.object(app_module.meta_messenger_handler, 'send_message') as mock_send_meta:
            mock_send_meta.return_value = True
            payload = {
                "object": "instagram",
                "entry": [{
                    "id": "ig_acc_001",
                    "messaging": [{
                        "sender": {"id": "112233445566"},
                        "message": {"id": "msg_ig_88", "text": "¿Tienen soporte para Instagram?"}
                    }]
                }]
            }
            res_post = self.client.post('/api/meta_messenger', json=payload)
            self.assertEqual(res_post.status_code, 200)
            mock_send_meta.assert_called_once()

if __name__ == '__main__':
    unittest.main()
