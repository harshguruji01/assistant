"""
Unit tests for intent classification and multilingual understanding.
"""

import unittest
from falcon.core.intent_engine import IntentEngine, IntentType


class TestIntentEngine(unittest.TestCase):

    def setUp(self):
        self.engine = IntentEngine()

    def test_empty_input_clarification(self):
        intent = self.engine.classify_intent("   ")
        self.assertEqual(intent.intent_type, IntentType.CLARIFICATION_NEEDED)

    def test_app_launch_intent(self):
        intent = self.engine.classify_intent("open notepad")
        self.assertEqual(intent.intent_type, IntentType.SYSTEM_COMMAND)
        self.assertEqual(intent.action_type, "launch_app")
        self.assertEqual(intent.entities.get("app_name"), "notepad")
        self.assertFalse(intent.is_question)

    def test_hinglish_app_launch(self):
        intent = self.engine.classify_intent("calc kholo")
        self.assertEqual(intent.intent_type, IntentType.SYSTEM_COMMAND)
        self.assertEqual(intent.action_type, "launch_app")
        self.assertEqual(intent.entities.get("app_name"), "calc")
        self.assertEqual(intent.detected_language, "hi-en")

    def test_hindi_script_detection(self):
        lang = self.engine.detect_language("नमस्ते फाल्कन")
        self.assertEqual(lang, "hi")

    def test_question_detection(self):
        intent = self.engine.classify_intent("What is the capital of India?")
        self.assertTrue(intent.is_question)
        self.assertEqual(intent.intent_type, IntentType.CONVERSATION)

    def test_system_info_intent(self):
        intent = self.engine.classify_intent("Show me CPU and RAM stats")
        self.assertEqual(intent.intent_type, IntentType.SYSTEM_COMMAND)
        self.assertEqual(intent.action_type, "get_system_info")

    def test_multistep_workflow_intent(self):
        intent = self.engine.classify_intent("Find report.txt and then summarize its content")
        self.assertEqual(intent.intent_type, IntentType.AUTOMATION_WORKFLOW)
        self.assertEqual(intent.action_type, "composite_workflow")


if __name__ == "__main__":
    unittest.main()
