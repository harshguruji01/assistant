"""
Comprehensive Test Suite for HarshGuruJi Chat Engine & Windows Startup Manager.
Tests identity, ranked search, messaging, idempotency, deletion, blocking, and startup integration.
Developed by: HarshGuruJi (Website: https://www.webguruji.online)
"""

import tempfile
import unittest
from pathlib import Path

from falcon.chat.database import ChatDatabaseManager
from falcon.chat.services.blocking import BlockingService
from falcon.chat.services.identity import generate_hgj_id, is_valid_hgj_id, sanitize_username
from falcon.chat.services.messaging import MessagingService
from falcon.chat.services.user_search import UserSearchService
from falcon.system.startup import get_startup_status, is_startup_enabled


class TestHarshGuruJiChatPlatform(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_chat.db")
        self.db = ChatDatabaseManager(self.db_path)
        self.blocking = BlockingService(self.db)
        self.messaging = MessagingService(self.db, self.blocking)
        self.search = UserSearchService(self.db)

        # Seed test users
        with self.db.transaction() as cur:
            cur.execute("""
                INSERT INTO users (id, username, hgj_id, display_name, avatar_url, is_online)
                VALUES 
                    ('u1', 'harshguruji', 'HGJ-7F42K9', 'Harsh Patel', 'https://example.com/h.png', 1),
                    ('u2', 'rahulkumar', 'HGJ-9K12L3', 'Rahul Kumar', 'https://example.com/r.png', 1),
                    ('u3', 'priyasharma', 'HGJ-4P88Z1', 'Priya Sharma', 'https://example.com/p.png', 0);
            """)

    def tearDown(self):
        self.db.close()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # ==================== IDENTITY TESTS ====================

    def test_hgj_id_generation_and_format(self):
        hgj_id = generate_hgj_id()
        self.assertTrue(hgj_id.startswith("HGJ-"))
        self.assertEqual(len(hgj_id), 10)
        self.assertTrue(is_valid_hgj_id(hgj_id))

    def test_hgj_id_uniqueness(self):
        generated = {generate_hgj_id() for _ in range(200)}
        self.assertEqual(len(generated), 200, "Collision detected in HGJ-ID generation!")

    def test_username_sanitization(self):
        self.assertEqual(sanitize_username("@RahulKumar"), "rahulkumar")
        self.assertEqual(sanitize_username("  harsh_patel  "), "harsh_patel")
        with self.assertRaises(ValueError):
            sanitize_username("ab")  # Too short (< 3)

    # ==================== SEARCH TESTS ====================

    def test_exact_username_search(self):
        results = self.search.search_users("rahulkumar", current_user_id="u1")
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]["username"], "rahulkumar")
        self.assertEqual(results[0]["rank_score"], 1)

    def test_search_with_at_prefix(self):
        results = self.search.search_users("@rahulkumar", current_user_id="u1")
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]["username"], "rahulkumar")

    def test_prefix_search_ranking(self):
        results = self.search.search_users("rah", current_user_id="u1")
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]["username"], "rahulkumar")
        self.assertEqual(results[0]["rank_score"], 2)

    def test_hgj_id_search(self):
        results = self.search.search_users("HGJ-9K12L3", current_user_id="u1")
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]["hgj_id"], "HGJ-9K12L3")

    # ==================== MESSAGING & IDEMPOTENCY TESTS ====================

    def test_conversation_creation_and_no_duplicates(self):
        c1 = self.messaging.get_or_create_conversation("u1", "u2")
        c2 = self.messaging.get_or_create_conversation("u2", "u1")
        self.assertEqual(c1["id"], c2["id"], "Conversations between same users must not duplicate!")

    def test_send_and_retrieve_messages(self):
        conv = self.messaging.get_or_create_conversation("u1", "u2")
        msg = self.messaging.send_message(
            conversation_id=conv["id"],
            sender_id="u1",
            content="Hello Rahul! This is Harsh Patel.",
        )
        self.assertEqual(msg["content"], "Hello Rahul! This is Harsh Patel.")
        self.assertEqual(msg["status"], "sent")

        history = self.messaging.get_messages(conv["id"], user_id="u1")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["content"], "Hello Rahul! This is Harsh Patel.")

    def test_idempotency_duplicate_protection(self):
        conv = self.messaging.get_or_create_conversation("u1", "u2")
        idemp_key = "idemp_test_unique_key_123"

        msg1 = self.messaging.send_message(conv["id"], "u1", "Payment confirmation", idempotency_key=idemp_key)
        msg2 = self.messaging.send_message(conv["id"], "u1", "Payment confirmation", idempotency_key=idemp_key)

        self.assertEqual(msg1["id"], msg2["id"], "Idempotency key must prevent duplicate message creation!")

    def test_status_update_delivered_and_seen(self):
        conv = self.messaging.get_or_create_conversation("u1", "u2")
        msg = self.messaging.send_message(conv["id"], "u1", "Are you available?")

        count_delivered = self.messaging.update_status([msg["id"]], "delivered", receiver_id="u2")
        self.assertEqual(count_delivered, 1)

        count_seen = self.messaging.update_status([msg["id"]], "seen", receiver_id="u2")
        self.assertEqual(count_seen, 1)

        history = self.messaging.get_messages(conv["id"], user_id="u1")
        self.assertEqual(history[0]["status"], "seen")

    def test_delete_for_me_vs_delete_for_everyone(self):
        conv = self.messaging.get_or_create_conversation("u1", "u2")
        msg = self.messaging.send_message(conv["id"], "u1", "Sensitive confidential note")

        # Receiver cannot delete for everyone
        with self.assertRaises(PermissionError):
            self.messaging.delete_message(msg["id"], user_id="u2", delete_for_everyone=True)

        # Sender deletes for everyone
        self.messaging.delete_message(msg["id"], user_id="u1", delete_for_everyone=True)

        history_u1 = self.messaging.get_messages(conv["id"], user_id="u1")
        history_u2 = self.messaging.get_messages(conv["id"], user_id="u2")

        self.assertEqual(history_u1[0]["content"], "[This message was deleted]")
        self.assertEqual(history_u2[0]["content"], "[This message was deleted]")

    # ==================== BLOCKING TESTS ====================

    def test_blocking_enforcement(self):
        self.blocking.block_user("u1", "u2")
        self.assertTrue(self.blocking.is_blocked("u1", "u2"))
        self.assertTrue(self.blocking.is_blocked("u2", "u1"))

        # Blocked users cannot start conversation or send messages
        with self.assertRaises(PermissionError):
            self.messaging.get_or_create_conversation("u1", "u2")

        # Unblock allows communication again
        self.blocking.unblock_user("u1", "u2")
        self.assertFalse(self.blocking.is_blocked("u1", "u2"))
        conv = self.messaging.get_or_create_conversation("u1", "u2")
        self.assertIsNotNone(conv["id"])

    # ==================== WINDOWS STARTUP TEST ====================

    def test_startup_status(self):
        status_info = get_startup_status()
        self.assertIn("app_name", status_info)
        self.assertIn("is_enabled", status_info)
        self.assertIn("command", status_info)


if __name__ == "__main__":
    unittest.main()
