# -*- coding: utf-8 -*-
import sqlite3
import json
import os
import time
import csv
import io
from typing import List, Dict, Any, Optional

class DatabaseManager:
    def __init__(self, db_path: str = "conversations.db"):
        """
        Gestor de base de datos relacional SQLite para la memoria conversacional
        a largo plazo, usuarios multicanal, registro de leads y analíticas.
        """
        self.db_path = os.path.abspath(db_path)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Crea las tablas necesarias en la base de datos si no existen."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Tabla de Usuarios Multicanal
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    channel TEXT NOT NULL,
                    name TEXT,
                    first_seen REAL,
                    last_seen REAL
                )
            """)
            
            # Tabla de Historial de Mensajes / Conversaciones
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    suggestions_json TEXT,
                    sources_json TEXT,
                    model_used TEXT,
                    timestamp REAL NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Tabla de Registro de Leads / Transacciones
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    name TEXT,
                    email TEXT,
                    phone TEXT,
                    interest TEXT,
                    timestamp REAL NOT NULL
                )
            """)
            
            conn.commit()

    def register_or_update_user(self, user_id: str, channel: str, name: Optional[str] = None):
        """Registra un nuevo usuario o actualiza la fecha de su última interacción."""
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                if name:
                    cursor.execute(
                        "UPDATE users SET last_seen = ?, name = ? WHERE user_id = ?",
                        (now, name, user_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE users SET last_seen = ? WHERE user_id = ?",
                        (now, user_id)
                    )
            else:
                cursor.execute(
                    "INSERT INTO users (user_id, channel, name, first_seen, last_seen) VALUES (?, ?, ?, ?, ?)",
                    (user_id, channel, name or user_id, now, now)
                )
            conn.commit()

    def save_message(
        self, 
        user_id: str, 
        channel: str, 
        role: str, 
        content: str, 
        suggestions: Optional[List[str]] = None, 
        sources: Optional[List[Dict[str, Any]]] = None, 
        model_used: Optional[str] = None
    ) -> int:
        """Guarda un mensaje en la base de datos y actualiza el estado del usuario."""
        self.register_or_update_user(user_id, channel)
        now = time.time()
        sug_json = json.dumps(suggestions or [], ensure_ascii=False)
        src_json = json.dumps(sources or [], ensure_ascii=False)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversations (user_id, channel, role, content, suggestions_json, sources_json, model_used, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, channel, role, content, sug_json, src_json, model_used or "unknown", now))
            conn.commit()
            return cursor.lastrowid

    def get_recent_history(self, user_id: str, limit: int = 6) -> List[Dict[str, str]]:
        """
        Retorna los últimos 'limit' mensajes formateados como lista de dicts
        [{"role": "user", "content": "..."}, ...] para inyectar contexto conversacional en RAG.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content FROM conversations 
                WHERE user_id = ? 
                ORDER BY id DESC LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()
            
            history = []
            for r in reversed(rows):
                history.append({"role": r["role"], "content": r["content"]})
            return history

    def get_full_history(self, user_id: str) -> List[Dict[str, Any]]:
        """Retorna el historial completo de conversación de un usuario específico."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, channel, role, content, suggestions_json, sources_json, model_used, timestamp
                FROM conversations
                WHERE user_id = ?
                ORDER BY id ASC
            """, (user_id,))
            rows = cursor.fetchall()
            
            result = []
            for r in rows:
                result.append({
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "channel": r["channel"],
                    "role": r["role"],
                    "content": r["content"],
                    "suggestions": json.loads(r["suggestions_json"] or "[]"),
                    "sources": json.loads(r["sources_json"] or "[]"),
                    "model_used": r["model_used"],
                    "timestamp": r["timestamp"]
                })
            return result

    def save_lead(self, user_id: str, channel: str, name: Optional[str] = None, email: Optional[str] = None, phone: Optional[str] = None, interest: Optional[str] = None) -> int:
        """Registra la intención o contacto de un lead detectado."""
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO leads (user_id, channel, name, email, phone, interest, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, channel, name, email, phone or user_id, interest, now))
            conn.commit()
            return cursor.lastrowid

    def export_leads_csv(self) -> str:
        """Genera un archivo CSV en formato string con la lista de leads capturados."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Canal", "Nombre", "Email", "Telefono_Usuario", "Interes", "Fecha"])
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, channel, name, email, phone, interest, timestamp FROM leads ORDER BY id ASC")
            rows = cursor.fetchall()
            for r in rows:
                formatted_date = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(r["timestamp"])) if r["timestamp"] else "-"
                writer.writerow([r["id"], r["channel"], r["name"] or "", r["email"] or "", r["phone"] or "", r["interest"] or "", formatted_date])
                
        return output.getvalue()

    def get_analytics_summary(self) -> Dict[str, Any]:
        """Obtiene resumen de métricas del agente (usuarios, mensajes por canal, leads y lista reciente)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM conversations")
            total_messages = cursor.fetchone()[0]
            
            cursor.execute("SELECT channel, COUNT(*) as count FROM conversations GROUP BY channel")
            messages_by_channel = {row["channel"]: row["count"] for row in cursor.fetchall()}
            
            cursor.execute("SELECT COUNT(*) FROM leads")
            total_leads = cursor.fetchone()[0]

            cursor.execute("""
                SELECT id, user_id, channel, name, email, phone, interest, timestamp 
                FROM leads ORDER BY id DESC LIMIT 50
            """)
            leads_rows = cursor.fetchall()
            recent_leads = [
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "channel": r["channel"],
                    "name": r["name"],
                    "email": r["email"],
                    "phone": r["phone"],
                    "interest": r["interest"],
                    "date": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(r["timestamp"])) if r["timestamp"] else "-",
                    "timestamp": r["timestamp"]
                }
                for r in leads_rows
            ]
            
            return {
                "total_users": total_users,
                "total_messages": total_messages,
                "messages_by_channel": messages_by_channel,
                "total_leads": total_leads,
                "recent_leads": recent_leads
            }
