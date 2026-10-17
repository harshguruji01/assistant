"""
Unit tests for configuration loading and validation.
"""

import os
import unittest
from pathlib import Path
from falcon.config.settings import AISettings, FalconSettings, load_settings


class TestConfiguration(unittest.TestCase):

    def test_default_settings(self):
        settings = FalconSettings()
        self.assertEqual(settings.app_name, "Falcon AI Desktop Assistant")
        self.assertEqual(settings.developer, "HarshGuruJi")
        self.assertEqual(settings.platform, "Windows 11")
        self.assertTrue(settings.database_path.endswith("falcon.db"))
        self.assertEqual(settings.ai.default_provider, "ollama")

    def test_env_override(self):
        os.environ["FALCON_AI_PROVIDER"] = "mock"
        os.environ["FALCON_AI_MODEL"] = "test-model-1"
        try:
            settings = load_settings()
            self.assertEqual(settings.ai.default_provider, "mock")
            self.assertEqual(settings.ai.default_model, "test-model-1")
        finally:
            del os.environ["FALCON_AI_PROVIDER"]
            del os.environ["FALCON_AI_MODEL"]


if __name__ == "__main__":
    unittest.main()
