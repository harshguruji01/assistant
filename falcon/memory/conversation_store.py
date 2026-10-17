"""
Conversation History Store for Falcon.
Persists chat transcripts, supports full text retrieval, session management, and export.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import datetime
import json
import logging
from typing import Any, Dict, List, Optional
from falcon.memory.database import DatabaseManager

logger = logging.getLogger("Falcon.ConversationStore")


class ConversationStore:
    """Persistent storage repository for multi-turn conversations."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        provider: Optional[str] = None,
        tokens: int = 0,
    ) -> int:
        """Persist a single message entry into the database."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        tool_json = json.dumps(tool_calls) if tool_calls else None

        with self.db.transaction() as cur:
            cur.execute(
                """
                INSERT INTO conversations (session_id, role, content, tool_calls_json, timestamp, provider, tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, role, content, tool_json, now, provider, tokens),
            )
            return cur.lastrowid

    def get_session_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent messages for a session."""
        rows = self.db.execute_query(
            """
            SELECT id, session_id, role, content, tool_calls_json, timestamp, provider, tokens
            FROM conversations
            WHERE session_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (session_id, limit),
        )
        for r in rows:
            if r.get("tool_calls_json"):
                try:
                    r["tool_calls"] = json.loads(r["tool_calls_json"])
                except Exception:
                    r["tool_calls"] = None
        return rows

    def search_conversations(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search previous conversation history across all sessions."""
        term = f"%{keyword}%"
        return self.db.execute_query(
            """
            SELECT id, session_id, role, content, timestamp, provider
            FROM conversations
            WHERE content LIKE ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (term, limit),
        )

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List distinct conversation sessions with their message count and last updated time."""
        return self.db.execute_query(
            """
            SELECT session_id, COUNT(*) as message_count, MAX(timestamp) as last_activity
            FROM conversations
            GROUP BY session_id
            ORDER BY last_activity DESC
            LIMIT ?
            """,
            (limit,),
        )

    def delete_session(self, session_id: str) -> int:
        """Delete all messages associated with a session ID."""
        with self.db.transaction() as cur:
            cur.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
            return cur.rowcount
