"""
HarshGuruJi Chat Database Layer.
SQLite with WAL mode, foreign keys, transaction boundaries, and full migration capabilities.
Developed by: HarshGuruJi (Website: https://www.webguruji.online)
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

logger = logging.getLogger("HarshGuruJi.Chat.DB")


class ChatDatabaseManager:
    """Thread-safe SQLite database manager for HarshGuruJi Chat."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            app_data = Path.home() / ".falcon" / "chat"
            app_data.mkdir(parents=True, exist_ok=True)
            self.db_path = app_data / "chat.db"

        self._local = threading.local()
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Get or create thread-local database connection with WAL mode."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            self._local.conn = conn
        return self._local.conn

    def close(self) -> None:
        """Close thread-local SQLite connection if open."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager providing an atomic transaction cursor."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Chat DB transaction rollback due to error: {e}")
            raise
        finally:
            cursor.close()

    def _init_db(self) -> None:
        """Initialize all schema tables, constraints, and indexes."""
        with self.transaction() as cur:
            # 1. Users Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    hgj_id TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    avatar_url TEXT,
                    is_online INTEGER DEFAULT 0,
                    last_seen_at TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
            """)

            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_hgj_id ON users(hgj_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_display ON users(display_name);")

            # 2. Conversations Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    participant_one TEXT NOT NULL,
                    participant_two TEXT NOT NULL,
                    last_message TEXT,
                    last_message_at TEXT DEFAULT (datetime('now')),
                    last_sender_id TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY(participant_one) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(participant_two) REFERENCES users(id) ON DELETE CASCADE,
                    CHECK (participant_one <> participant_two)
                );
            """)

            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_pair 
                ON conversations (
                    CASE WHEN participant_one < participant_two THEN participant_one ELSE participant_two END,
                    CASE WHEN participant_one < participant_two THEN participant_two ELSE participant_one END
                );
            """)

            # 3. Messages Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    receiver_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT DEFAULT 'sent',
                    idempotency_key TEXT,
                    reply_to_id TEXT,
                    is_edited INTEGER DEFAULT 0,
                    edited_at TEXT,
                    delivered_at TEXT,
                    seen_at TEXT,
                    deleted_for_sender INTEGER DEFAULT 0,
                    deleted_for_receiver INTEGER DEFAULT 0,
                    deleted_for_everyone INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                    FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(receiver_id) REFERENCES users(id) ON DELETE CASCADE
                );
            """)

            cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv_order ON messages(conversation_id, created_at ASC);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_idempotency ON messages(idempotency_key);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_receiver_status ON messages(receiver_id, status);")

            # 4. User Blocks Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_blocks (
                    id TEXT PRIMARY KEY,
                    blocker_id TEXT NOT NULL,
                    blocked_id TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY(blocker_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(blocked_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(blocker_id, blocked_id)
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_blocks_lookup ON user_blocks(blocker_id, blocked_id);")
            logger.info("HarshGuruJi Chat database schema verified.")
