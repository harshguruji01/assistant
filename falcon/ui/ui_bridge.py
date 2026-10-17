"""
UI Bridge and Qt Signal Adapter for Falcon.
Decouples Falcon Core from PySide6 or other UI frameworks using thread-safe event bridges.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional
from falcon.core.controller import FalconCore
from falcon.core.event_bus import Event, EventNames

logger = logging.getLogger("Falcon.UIBridge")


class PythonUIBridge:
    """Thread-safe pure Python callback bridge for non-Qt UIs, web sockets, or CLI clients."""

    def __init__(self, core: FalconCore):
        self.core = core
        self._listeners: Dict[str, list[Callable[[Dict[str, Any]], None]]] = {}
        # Subscribe to all events
        self.core.event_bus.subscribe("*", self._on_core_event)

    def on(self, event_name: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a UI callback for an event topic."""
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)

    def _on_core_event(self, event: Event) -> None:
        """Forward event to listeners."""
        handlers = self._listeners.get(event.topic, []) + self._listeners.get("*", [])
        for handler in handlers:
            try:
                handler(event.data)
            except Exception as e:
                logger.error(f"UI listener error: {e}")


def get_qt_signals_adapter(core: FalconCore):
    """
    Returns a PySide6 QObject with strongly typed Qt Signals mapped to Falcon events.
    Returns None if PySide6 is not installed.
    """
    try:
        from PySide6.QtCore import QObject, Signal  # type: ignore

        class FalconQtSignals(QObject):
            # Lifecycle and Messages
            assistant_ready = Signal(dict)
            status_changed = Signal(str)
            message_received = Signal(dict)
            response_started = Signal(dict)
            response_completed = Signal(dict)
            error_occurred = Signal(str)

            # Task Progress
            task_created = Signal(dict)
            task_progress = Signal(dict)
            task_completed = Signal(dict)
            task_failed = Signal(dict)

            # Voice
            voice_listening = Signal(bool)
            voice_speaking = Signal(bool)

            def __init__(self, core_ref: FalconCore):
                super().__init__()
                self.core = core_ref
                self._bind_events()

            def _bind_events(self):
                self.core.event_bus.subscribe(EventNames.ASSISTANT_READY, lambda e: self.assistant_ready.emit(e.data))
                self.core.event_bus.subscribe(EventNames.ASSISTANT_MESSAGE_RECEIVED, lambda e: self.message_received.emit(e.data))
                self.core.event_bus.subscribe(EventNames.ASSISTANT_RESPONSE_STARTED, lambda e: self.response_started.emit(e.data))
                self.core.event_bus.subscribe(EventNames.ASSISTANT_RESPONSE_COMPLETED, lambda e: self.response_completed.emit(e.data))
                self.core.event_bus.subscribe(EventNames.TASK_CREATED, lambda e: self.task_created.emit(e.data))
                self.core.event_bus.subscribe(EventNames.TASK_PROGRESS, lambda e: self.task_progress.emit(e.data))
                self.core.event_bus.subscribe(EventNames.TASK_COMPLETED, lambda e: self.task_completed.emit(e.data))
                self.core.event_bus.subscribe(EventNames.TASK_FAILED, lambda e: self.task_failed.emit(e.data))
                self.core.event_bus.subscribe(EventNames.VOICE_LISTENING_STARTED, lambda e: self.voice_listening.emit(True))
                self.core.event_bus.subscribe(EventNames.VOICE_LISTENING_STOPPED, lambda e: self.voice_listening.emit(False))
                self.core.event_bus.subscribe(EventNames.VOICE_SPEAKING_STARTED, lambda e: self.voice_speaking.emit(True))
                self.core.event_bus.subscribe(EventNames.VOICE_SPEAKING_STOPPED, lambda e: self.voice_speaking.emit(False))

        return FalconQtSignals(core)
    except ImportError:
        logger.info("PySide6 is not installed. Pure-Python UI bridge is active.")
        return None
