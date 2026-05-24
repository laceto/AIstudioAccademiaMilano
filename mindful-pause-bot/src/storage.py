import sqlite3
import os
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "sessions.db")


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT NOT NULL,
                timestamp   TEXT NOT NULL,
                trigger     TEXT,
                choice      TEXT,
                reflection  TEXT
            )
        """)
        conn.commit()


def log_session(user_id: str, trigger: str, choice: str, reflection: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO sessions (user_id, timestamp, trigger, choice, reflection) VALUES (?, ?, ?, ?, ?)",
            (user_id, datetime.utcnow().isoformat(), trigger, choice, reflection),
        )
        conn.commit()


def get_user_sessions(user_id: str, limit: int = 10) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM sessions WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]
