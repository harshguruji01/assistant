"""
Messaging & Conversation Service for HarshGuruJi Chat.
Handles real-time persistence, duplicate prevention via idempotency keys,
chronological ordering, delete for me/everyone, edits, and delivery/read receipts.
Developed by: HarshGuruJi (Website: https://www.webguruji.online)
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from falcon.chat.database import ChatDatabaseManager
from falcon.chat.services.blocking import BlockingService

logger = logging.getLogger("HarshGuruJi.Chat.Messaging")


class MessagingService:
    """Core messaging pipeline managing conversations and messages."""

    def __init__(self, db: ChatDatabaseManager, blocking: BlockingService):
        self.db = db
        self.blocking = blocking

    def get_or_create_conversation(self, user_a: str, user_b: str) -> Dict[str, Any]:
        """
        Get existing conversation between user_a and user_b or create a new one.
        Enforces one-to-one uniqueness (never duplicates conversations).
        """
        if user_a == user_b:
            raise ValueError("Cannot start a conversation with yourself.")

        if self.blocking.is_blocked(user_a, user_b):
            raise PermissionError("Cannot start or access conversation: communication is blocked.")

        # Canonical ordering to match unique index
        p1, p2 = (user_a, user_b) if user_a < user_b else (user_b, user_a)

        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, participant_one, participant_two, last_message, last_message_at, last_sender_id, created_at, updated_at
            FROM conversations
            WHERE participant_one = ? AND participant_two = ?;
        """, (p1, p2))
        row = cur.fetchone()
        if row:
            return dict(row)

        # Create new conversation
        conv_id = f"conv_{uuid.uuid4().hex[:12]}"
        with self.db.transaction() as cur:
            cur.execute("""
                INSERT INTO conversations (id, participant_one, participant_two, created_at, updated_at)
                VALUES (?, ?, ?, datetime('now'), datetime('now'));
            """, (conv_id, p1, p2))

        logger.info(f"Created conversation {conv_id} between {user_a} and {user_b}")
        return {
            "id": conv_id,
            "participant_one": p1,
            "participant_two": p2,
            "last_message": None,
            "last_message_at": None,
            "last_sender_id": None,
        }

    def list_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        """List all active conversations for user with partner details and unread counts."""
        conn = self.db.get_connection()
        cur = conn.cursor()

        sql = """
            SELECT 
                c.id, c.participant_one, c.participant_two, c.last_message, c.last_message_at, c.last_sender_id,
                CASE WHEN c.participant_one = ? THEN c.participant_two ELSE c.participant_one END AS partner_id,
                u.username AS partner_username,
                u.hgj_id AS partner_hgj_id,
                u.display_name AS partner_display_name,
                u.avatar_url AS partner_avatar_url,
                u.is_online AS partner_is_online,
                u.last_seen_at AS partner_last_seen_at,
                (
                    SELECT COUNT(*) FROM messages m 
                    WHERE m.conversation_id = c.id 
                      AND m.receiver_id = ? 
                      AND m.status != 'seen'
                      AND m.deleted_for_receiver = 0
                      AND m.deleted_for_everyone = 0
                ) AS unread_count
            FROM conversations c
            JOIN users u ON (CASE WHEN c.participant_one = ? THEN c.participant_two ELSE c.participant_one END) = u.id
            WHERE c.participant_one = ? OR c.participant_two = ?
            ORDER BY coalesce(c.last_message_at, c.created_at) DESC;
        """
        cur.execute(sql, (user_id, user_id, user_id, user_id, user_id))
        rows = cur.fetchall()
        return [dict(r) for r in rows]

    def send_message(
        self,
        conversation_id: str,
        sender_id: str,
        content: str,
        idempotency_key: Optional[str] = None,
        reply_to_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a real-time message with duplicate protection and block checks.
        """
        clean_content = content.strip()
        if not clean_content:
            raise ValueError("Message content cannot be empty.")

        # Check idempotency
        if idempotency_key:
            conn = self.db.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM messages WHERE idempotency_key = ?;", (idempotency_key,))
            existing = cur.fetchone()
            if existing:
                logger.info(f"Idempotent message hit: returning existing message {existing['id']}")
                return dict(existing)

        # Verify conversation and participants
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT participant_one, participant_two FROM conversations WHERE id = ?;", (conversation_id,))
        conv = cur.fetchone()
        if not conv:
            raise ValueError("Conversation does not exist.")

        p1, p2 = conv["participant_one"], conv["participant_two"]
        if sender_id not in (p1, p2):
            raise PermissionError("User is not an authorized participant in this conversation.")

        receiver_id = p2 if sender_id == p1 else p1

        # Check block status
        if self.blocking.is_blocked(sender_id, receiver_id):
            raise PermissionError("Cannot send message: conversation is blocked.")

        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        with self.db.transaction() as cur:
            cur.execute("""
                INSERT INTO messages (
                    id, conversation_id, sender_id, receiver_id, content, 
                    status, idempotency_key, reply_to_id, created_at
                ) VALUES (?, ?, ?, ?, ?, 'sent', ?, ?, datetime('now'));
            """, (msg_id, conversation_id, sender_id, receiver_id, clean_content, idempotency_key, reply_to_id))

            # Update conversation summary
            cur.execute("""
                UPDATE conversations
                SET last_message = ?, last_message_at = datetime('now'), last_sender_id = ?, updated_at = datetime('now')
                WHERE id = ?;
            """, (clean_content[:150], sender_id, conversation_id))

        return {
            "id": msg_id,
            "conversation_id": conversation_id,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "content": clean_content,
            "status": "sent",
            "reply_to_id": reply_to_id,
            "is_edited": False,
            "deleted_for_everyone": False,
        }

    def get_messages(
        self,
        conversation_id: str,
        user_id: str,
        limit: int = 50,
        before_timestamp: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve paginated chronological messages for a conversation, respecting deletion rules."""
        conn = self.db.get_connection()
        cur = conn.cursor()

        # Verify participant
        cur.execute("SELECT participant_one, participant_two FROM conversations WHERE id = ?;", (conversation_id,))
        conv = cur.fetchone()
        if not conv or user_id not in (conv["participant_one"], conv["participant_two"]):
            raise PermissionError("Access denied: Not a participant in this conversation.")

        sql = """
            SELECT 
                id, conversation_id, sender_id, receiver_id, content, status, 
                reply_to_id, is_edited, edited_at, delivered_at, seen_at,
                deleted_for_sender, deleted_for_receiver, deleted_for_everyone,
                created_at
            FROM messages
            WHERE conversation_id = ?
              AND (
                -- sender view
                (sender_id = ? AND deleted_for_sender = 0)
                OR
                -- receiver view
                (receiver_id = ? AND deleted_for_receiver = 0)
              )
              AND (? IS NULL OR created_at < ?)
            ORDER BY created_at ASC
            LIMIT ?;
        """
        cur.execute(sql, (conversation_id, user_id, user_id, before_timestamp, before_timestamp, limit))
        rows = cur.fetchall()

        messages = []
        for r in rows:
            is_del_everyone = bool(r["deleted_for_everyone"])
            msg_content = "[This message was deleted]" if is_del_everyone else r["content"]
            messages.append({
                "id": r["id"],
                "conversation_id": r["conversation_id"],
                "sender_id": r["sender_id"],
                "receiver_id": r["receiver_id"],
                "content": msg_content,
                "status": r["status"],
                "reply_to_id": r["reply_to_id"],
                "is_edited": bool(r["is_edited"]),
                "edited_at": r["edited_at"],
                "delivered_at": r["delivered_at"],
                "seen_at": r["seen_at"],
                "deleted_for_everyone": is_del_everyone,
                "created_at": r["created_at"],
            })
        return messages

    def update_status(self, message_ids: List[str], new_status: str, receiver_id: str) -> int:
        """Mark messages as 'delivered' or 'seen' for incoming receiver."""
        if not message_ids or new_status not in ("delivered", "seen"):
            return 0

        placeholders = ",".join("?" for _ in message_ids)
        time_col = "delivered_at" if new_status == "delivered" else "seen_at"

        sql = f"""
            UPDATE messages
            SET status = ?, {time_col} = datetime('now')
            WHERE id IN ({placeholders}) AND receiver_id = ? AND status != 'seen';
        """
        with self.db.transaction() as cur:
            cur.execute(sql, [new_status] + list(message_ids) + [receiver_id])
            count = cur.rowcount
        return count

    def delete_message(self, message_id: str, user_id: str, delete_for_everyone: bool = False) -> bool:
        """
        Delete a message.
        - delete_for_everyone: Only allowed if user is the sender.
        - delete_for_me: Marks deleted_for_sender or deleted_for_receiver.
        """
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT sender_id, receiver_id FROM messages WHERE id = ?;", (message_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("Message not found.")

        sender_id, receiver_id = row["sender_id"], row["receiver_id"]
        if user_id not in (sender_id, receiver_id):
            raise PermissionError("You cannot delete this message.")

        with self.db.transaction() as cur:
            if delete_for_everyone:
                if user_id != sender_id:
                    raise PermissionError("Only the sender can delete a message for everyone.")
                cur.execute("""
                    UPDATE messages
                    SET deleted_for_everyone = 1, content = '[This message was deleted]'
                    WHERE id = ?;
                """, (message_id,))
            else:
                if user_id == sender_id:
                    cur.execute("UPDATE messages SET deleted_for_sender = 1 WHERE id = ?;", (message_id,))
                else:
                    cur.execute("UPDATE messages SET deleted_for_receiver = 1 WHERE id = ?;", (message_id,))
        return True

    def edit_message(self, message_id: str, user_id: str, new_content: str) -> Dict[str, Any]:
        """Edit an authorized sent message."""
        clean = new_content.strip()
        if not clean:
            raise ValueError("Edited content cannot be empty.")

        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT sender_id, deleted_for_everyone FROM messages WHERE id = ?;", (message_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("Message not found.")
        if row["sender_id"] != user_id:
            raise PermissionError("Only the sender can edit this message.")
        if row["deleted_for_everyone"]:
            raise ValueError("Cannot edit a deleted message.")

        with self.db.transaction() as cur:
            cur.execute("""
                UPDATE messages
                SET content = ?, is_edited = 1, edited_at = datetime('now')
                WHERE id = ?;
            """, (clean, message_id))

        return {
            "id": message_id,
            "content": clean,
            "is_edited": True,
        }
