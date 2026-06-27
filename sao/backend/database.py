import aiosqlite
import uuid
from datetime import datetime
import json

class Database:
    def __init__(self, db_path="sao_history.db"):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    metadata_id TEXT PRIMARY KEY,
                    message_id TEXT,
                    model_used TEXT,
                    tool_calls TEXT,
                    FOREIGN KEY(message_id) REFERENCES messages(message_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS provider_models (
                    provider TEXT PRIMARY KEY,
                    models_json TEXT NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """)
            await db.commit()

    async def create_session(self, title="New Session"):
        session_id = str(uuid.uuid4())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO sessions (session_id, title, created_at) VALUES (?, ?, ?)",
                (session_id, title, datetime.now())
            )
            await db.commit()
        return session_id

    async def add_message(self, session_id, role, content, model_used=None, tool_calls=None):
        message_id = str(uuid.uuid4())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO messages (message_id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                (message_id, session_id, role, content, datetime.now())
            )
            if model_used or tool_calls:
                metadata_id = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO metadata (metadata_id, message_id, model_used, tool_calls) VALUES (?, ?, ?, ?)",
                    (metadata_id, message_id, model_used, json.dumps(tool_calls) if tool_calls else None)
                )
            await db.commit()
        return message_id

    async def get_history(self, session_id, limit=100):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                # Return in chronological order
                return [{"role": row[0], "content": row[1]} for row in reversed(rows)]

    async def save_provider_models(self, provider, models):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO provider_models (provider, models_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(provider) DO UPDATE SET
                    models_json = excluded.models_json,
                    updated_at = excluded.updated_at
                """,
                (provider, json.dumps(models), datetime.now())
            )
            await db.commit()

    async def get_provider_models(self, provider):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT models_json FROM provider_models WHERE provider = ?",
                (provider,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return []
                try:
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return []
