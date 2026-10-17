"""
Integration tests for central FalconCore controller and UI Bridge.
"""

import asyncio
import tempfile
import unittest
from pathlib import Path
from falcon.config.settings import AISettings, FalconSettings, VoiceSettings
from falcon.core.controller import FalconCore
from falcon.core.lifecycle import AppState
from falcon.ui.ui_bridge import PythonUIBridge


class TestControllerLifecycle(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = str(Path(self.temp_dir.name) / "test_core.db")

        # Configure deterministic mock AI and disabled voice for tests
        settings = FalconSettings(
            database_path=db_path,
            log_dir=self.temp_dir.name,
            ai=AISettings(default_provider="mock", fallback_provider="mock"),
            voice=VoiceSettings(enabled=False),
        )
        self.core = FalconCore(settings)
        self.ui_bridge = PythonUIBridge(self.core)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_startup_and_message_processing(self):
        ui_received_events = []
        self.ui_bridge.on("*", lambda data: ui_received_events.append(data))

        async def _test():
            # 1. Start core
            started = await self.core.start()
            self.assertTrue(started)
            self.assertEqual(self.core.lifecycle.state, AppState.READY)

            # 2. Process greeting message
            res1 = await self.core.process_message("Hello Falcon")
            self.assertIn("HarshGuruJi", res1.response_text)
            self.assertEqual(res1.provider_used, "mock")

            # 3. Process tool invocation request (get system info)
            res2 = await self.core.process_message("Show system info and RAM")
            self.assertTrue(len(res2.executed_tools) >= 1)
            self.assertEqual(res2.executed_tools[0]["tool"], "get_system_info")

            # 4. Graceful shutdown
            await self.core.shutdown()
            self.assertEqual(self.core.lifecycle.state, AppState.STOPPED)

        asyncio.run(_test())
        self.assertTrue(len(ui_received_events) > 0)


if __name__ == "__main__":
    unittest.main()
