"""
Long Term User Memory and Preferences Store for Falcon.
Safely manages user-approved preferences, custom facts, and persistent memory entries.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import datetime
import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from falcon.memory.database import DatabaseManager

logger = logging.getLogger("Falcon.LongTermMemory")


class LongTermMemory:
    """Manages persistent facts and user-approved profile memories."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def add_memory(
        self,
        category: str,
        content: str,
        approved_by_user: bool = True,
        memory_id: Optional[str] = None,
    ) -> str:
        """Store a verified piece of user memory."""
        mid = memory_id or f"mem_{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.db.transaction() as cur:
            cur.execute(
                """
                INSERT OR REPLACE INTO long_term_memories (id, category, content, approved_by_user, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (mid, category, content, 1 if approved_by_user else 0, now),
            )
        logger.info(f"Added long term memory [{category}]: {content[:40]}...")
        return mid

    def get_memories(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve stored memories, optionally filtered by category."""
        if category:
            return self.db.execute_query(
                "SELECT id, category, content, created_at FROM long_term_memories WHERE category = ? ORDER BY created_at DESC",
                (category,),
            )
        return self.db.execute_query(
            "SELECT id, category, content, created_at FROM long_term_memories ORDER BY created_at DESC"
        )

    def delete_memory(self, memory_id: str) -> bool:
        """Remove a memory entry."""
        with self.db.transaction() as cur:
            cur.execute("DELETE FROM long_term_memories WHERE id = ?", (memory_id,))
            return cur.rowcount > 0

    # User Preferences (Key-Value)
    def set_preference(self, key: str, value: Any) -> None:
        """Store a user preference key-value pair."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        val_json = json.dumps(value)
        with self.db.transaction() as cur:
            cur.execute(
                """
                INSERT OR REPLACE INTO user_preferences (key, value_json, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, val_json, now),
            )

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Retrieve a stored preference."""
        rows = self.db.execute_query(
            "SELECT value_json FROM user_preferences WHERE key = ?",
            (key,),
        )
        if rows:
            try:
                return json.loads(rows[0]["value_json"])
            except Exception:
                return default
        return default

    def list_all_preferences(self) -> Dict[str, Any]:
        """Fetch all stored preferences as a dictionary."""
        rows = self.db.execute_query("SELECT key, value_json FROM user_preferences")
        result = {}
        for r in rows:
            try:
                result[r["key"]] = json.loads(r["value_json"])
            except Exception:
                result[r["key"]] = r["value_json"]
        return result
