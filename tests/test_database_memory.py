"""
Unit tests for SQLite database persistence, conversation history, and long-term memory.
"""

import tempfile
import unittest
from pathlib import Path
from falcon.memory.conversation_store import ConversationStore
from falcon.memory.database import DatabaseManager
from falcon.memory.long_term_memory import LongTermMemory


class TestDatabaseAndMemory(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_falcon.db"
        self.db_manager = DatabaseManager(self.db_path)
        self.conv_store = ConversationStore(self.db_manager)
        self.ltm = LongTermMemory(self.db_manager)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_conversation_persistence_and_search(self):
        # Save messages
        self.conv_store.save_message("session_1", "user", "Hello Falcon, find project notes.")
        self.conv_store.save_message("session_1", "assistant", "I found 3 notes for your project.")

        # Retrieve session history
        history = self.conv_store.get_session_history("session_1")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[1]["role"], "assistant")

        # Search
        results = self.conv_store.search_conversations("project")
        self.assertEqual(len(results), 2)

        # Delete session
        deleted_count = self.conv_store.delete_session("session_1")
        self.assertEqual(deleted_count, 2)
        self.assertEqual(len(self.conv_store.get_session_history("session_1")), 0)

    def test_long_term_memory(self):
        mid = self.ltm.add_memory("preference", "User prefers Hindi greeting in mornings.", approved_by_user=True)
        self.assertTrue(mid.startswith("mem_"))

        memories = self.ltm.get_memories("preference")
        self.assertEqual(len(memories), 1)
        self.assertIn("Hindi greeting", memories[0]["content"])

        deleted = self.ltm.delete_memory(mid)
        self.assertTrue(deleted)
        self.assertEqual(len(self.ltm.get_memories("preference")), 0)

    def test_user_preferences(self):
        self.ltm.set_preference("theme", "dark")
        self.ltm.set_preference("tts_volume", 0.8)

        self.assertEqual(self.ltm.get_preference("theme"), "dark")
        self.assertEqual(self.ltm.get_preference("tts_volume"), 0.8)
        self.assertIsNone(self.ltm.get_preference("non_existent"))


if __name__ == "__main__":
    unittest.main()
