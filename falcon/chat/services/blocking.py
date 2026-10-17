"""
User Blocking & Policy Enforcement Service for HarshGuruJi Chat.
Enforces block lists, prevents message initiation/delivery, and manages relationships.
Developed by: HarshGuruJi (Website: https://www.webguruji.online)
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional
from falcon.chat.database import ChatDatabaseManager

logger = logging.getLogger("HarshGuruJi.Chat.Blocking")


class BlockingService:
    """Manages user blocks and verifies bidirectional communication permissions."""

    def __init__(self, db: ChatDatabaseManager):
        self.db = db

    def block_user(self, blocker_id: str, blocked_id: str) -> bool:
        """Block another user. Fails if trying to block self."""
        if blocker_id == blocked_id:
            raise ValueError("You cannot block yourself.")

        block_id = f"blk_{uuid.uuid4().hex[:12]}"
        with self.db.transaction() as cur:
            cur.execute("""
                INSERT OR IGNORE INTO user_blocks (id, blocker_id, blocked_id, created_at)
                VALUES (?, ?, ?, datetime('now'));
            """, (block_id, blocker_id, blocked_id))
        logger.info(f"User {blocker_id} blocked user {blocked_id}")
        return True

    def unblock_user(self, blocker_id: str, blocked_id: str) -> bool:
        """Remove a block."""
        with self.db.transaction() as cur:
            cur.execute("""
                DELETE FROM user_blocks WHERE blocker_id = ? AND blocked_id = ?;
            """, (blocker_id, blocked_id))
        logger.info(f"User {blocker_id} unblocked user {blocked_id}")
        return True

    def is_blocked(self, user_a: str, user_b: str) -> bool:
        """
        Check if any blocking relationship exists between user_a and user_b
        (i.e., user_a blocked user_b OR user_b blocked user_a).
        """
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 1 FROM user_blocks 
            WHERE (blocker_id = ? AND blocked_id = ?) 
               OR (blocker_id = ? AND blocked_id = ?)
            LIMIT 1;
        """, (user_a, user_b, user_b, user_a))
        return cur.fetchone() is not None

    def has_blocked(self, blocker_id: str, target_id: str) -> bool:
        """Check if blocker_id specifically initiated a block against target_id."""
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 1 FROM user_blocks WHERE blocker_id = ? AND blocked_id = ? LIMIT 1;
        """, (blocker_id, target_id))
        return cur.fetchone() is not None

    def get_blocked_users(self, user_id: str) -> List[dict]:
        """List all users blocked by the given user."""
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.username, u.hgj_id, u.display_name, u.avatar_url, b.created_at as blocked_at
            FROM user_blocks b
            JOIN users u ON b.blocked_id = u.id
            WHERE b.blocker_id = ?
            ORDER BY b.created_at DESC;
        """, (user_id,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
