"""
SQLite Database Storage and Connection Management for Falcon.
Handles schema initialization, WAL mode, migrations, and atomic transactions.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

logger = logging.getLogger("Falcon.Database")

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Conversation history
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_calls_json TEXT,
    timestamp TEXT NOT NULL,
    provider TEXT,
    tokens INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);

-- User-controlled long term memory
CREATE TABLE IF NOT EXISTS long_term_memories (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    approved_by_user BOOLEAN DEFAULT 1,
    created_at TEXT NOT NULL
);

-- User preferences and settings
CREATE TABLE IF NOT EXISTS user_preferences (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Persistent scheduled jobs (reminders, timers, alarms)
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    job_type TEXT NOT NULL, -- reminder, timer, recurring, hourly
    scheduled_time TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    is_recurring BOOLEAN DEFAULT 0,
    recurrence_interval_seconds INTEGER,
    status TEXT DEFAULT 'PENDING', -- PENDING, COMPLETED, CANCELLED
    created_at TEXT NOT NULL
);

-- Security and Tool execution audit logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    action_name TEXT NOT NULL,
    actor TEXT NOT NULL,
    parameters_json TEXT,
    permission_level TEXT NOT NULL,
    approved_by_user BOOLEAN DEFAULT 0,
    status TEXT NOT NULL,
    error_message TEXT
);
"""


class DatabaseManager:
    """Manages SQLite database lifecycle, schema initialization, and transactional access."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a new SQLite connection with dict-like row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_schema(self) -> None:
        """Apply core tables and indexes."""
        with self.transaction() as cur:
            cur.executescript(SCHEMA_SQL)
        logger.info(f"Initialized SQLite database schema at: '{self.db_path}'")

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        """Provide a transactional cursor with automatic rollback on error and commit on success."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database transaction error: {e}")
            raise
        finally:
            conn.close()

    def execute_query(self, query: str, params: tuple = ()) -> list[dict]:
        """Helper to run a SELECT query and return rows as dictionaries."""
        with self.transaction() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            return [dict(row) for row in rows]
