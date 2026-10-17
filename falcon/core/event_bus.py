"""
Asynchronous Typed Event Bus for Falcon.
Provides decoupled, non-blocking communication between Core, Automation, Voice, and Desktop UI.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import asyncio
import datetime
import fnmatch
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union, Coroutine

logger = logging.getLogger("Falcon.EventBus")


class EventNames:
    """Standardized event topic names."""
    # Assistant Lifecycle & Responses
    ASSISTANT_READY = "assistant.ready"
    ASSISTANT_STATUS_CHANGED = "assistant.status_changed"
    ASSISTANT_MESSAGE_RECEIVED = "assistant.message_received"
    ASSISTANT_RESPONSE_STARTED = "assistant.response_started"
    ASSISTANT_RESPONSE_CHUNK = "assistant.response_chunk"
    ASSISTANT_RESPONSE_COMPLETED = "assistant.response_completed"
    ASSISTANT_ERROR = "assistant.error"

    # Tasks and Workflows
    TASK_CREATED = "task.created"
    TASK_PROGRESS = "task.progress"
    TASK_AWAITING_APPROVAL = "task.awaiting_approval"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"

    # Voice State
    VOICE_LISTENING_STARTED = "voice.listening_started"
    VOICE_LISTENING_STOPPED = "voice.listening_stopped"
    VOICE_SPEAKING_STARTED = "voice.speaking_started"
    VOICE_SPEAKING_STOPPED = "voice.speaking_stopped"

    # System Metrics
    SYSTEM_METRICS_UPDATED = "system.metrics_updated"


@dataclass
class Event:
    """Immutable data transfer object representing a system event."""
    topic: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    correlation_id: Optional[str] = None


EventHandler = Callable[[Event], Union[None, Coroutine[Any, Any, None]]]


class EventBus:
    """Thread-safe and asynchronous event bus supporting wildcard subscriptions."""

    def __init__(self):
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._lock = asyncio.Lock()
        self._sync_queue: List[Event] = []

    def subscribe(self, topic_pattern: str, handler: EventHandler) -> None:
        """Register a handler for a topic or wildcard pattern (e.g. 'task.*')."""
        if topic_pattern not in self._subscribers:
            self._subscribers[topic_pattern] = []
        if handler not in self._subscribers[topic_pattern]:
            self._subscribers[topic_pattern].append(handler)
            logger.debug(f"Subscribed handler {getattr(handler, '__name__', str(handler))} to '{topic_pattern}'")

    def unsubscribe(self, topic_pattern: str, handler: EventHandler) -> bool:
        """Unsubscribe an existing handler."""
        if topic_pattern in self._subscribers and handler in self._subscribers[topic_pattern]:
            self._subscribers[topic_pattern].remove(handler)
            if not self._subscribers[topic_pattern]:
                del self._subscribers[topic_pattern]
            return True
        return False

    async def publish(self, event: Event) -> None:
        """Publish an event to all matching subscribers asynchronously."""
        handlers_to_invoke: List[EventHandler] = []
        for pattern, handlers in list(self._subscribers.items()):
            if pattern == "*" or fnmatch.fnmatch(event.topic, pattern):
                handlers_to_invoke.extend(handlers)

        for handler in handlers_to_invoke:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    # Run sync handler
                    handler(event)
            except Exception as e:
                logger.error(
                    f"Error in event handler '{getattr(handler, '__name__', str(handler))}' "
                    f"handling topic '{event.topic}': {e}",
                    exc_info=True
                )

    def publish_sync(self, event: Event, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Safely publish an event from synchronous code or external worker threads."""
        try:
            target_loop = loop or asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(self.publish(event), target_loop)
        except RuntimeError:
            # No running loop in this thread, run in a temporary loop or dispatch directly to sync handlers
            self._dispatch_sync_only(event)

    def _dispatch_sync_only(self, event: Event) -> None:
        """Direct dispatch for synchronous handlers when event loop is unavailable."""
        for pattern, handlers in list(self._subscribers.items()):
            if pattern == "*" or fnmatch.fnmatch(event.topic, pattern):
                for handler in handlers:
                    if not inspect.iscoroutinefunction(handler):
                        try:
                            handler(event)
                        except Exception as e:
                            logger.error(f"Sync event dispatch error: {e}")
