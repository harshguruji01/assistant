"""
Wake Word Detection Interface for Falcon.
Handles wake word activation with explicit operational state tracking.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

logger = logging.getLogger("Falcon.WakeWord")


class WakeWordDetector:
    """Manages wake word listening lifecycle."""

    def __init__(self, wake_word: str = "falcon", enabled: bool = False):
        self.wake_word = wake_word.lower()
        self.enabled = enabled
        self._is_listening = False
        self._has_engine = False
        self._on_wake_callback: Optional[Callable[[], None]] = None

        # Check if an actual wake word engine (like openWakeWord or pvporcupine) is installed
        try:
            import openwakeword  # type: ignore
            self._has_engine = True
        except ImportError:
            try:
                import pvporcupine  # type: ignore
                self._has_engine = True
            except ImportError:
                self._has_engine = False

    def is_supported(self) -> bool:
        """Return True only if a dedicated wake-word library is installed."""
        return self._has_engine

    def is_listening(self) -> bool:
        """True only if currently actively listening."""
        return self._is_listening

    def set_callback(self, callback: Callable[[], None]) -> None:
        self._on_wake_callback = callback

    def start_listening(self) -> bool:
        """Start listening for wake word if engine is present."""
        if not self.enabled:
            logger.info("Wake word is disabled in configuration.")
            return False

        if not self.is_supported():
            logger.warning("No wake-word engine (openWakeWord / Porcupine) installed. Wake word cannot run.")
            return False

        self._is_listening = True
        logger.info(f"Wake word detector started for keyword '{self.wake_word}'.")
        return True

    def stop_listening(self) -> None:
        """Stop listening."""
        self._is_listening = False
        logger.info("Wake word detector stopped.")
