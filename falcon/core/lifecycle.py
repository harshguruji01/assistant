"""
Application Lifecycle Management for Falcon.
Coordinates service startup sequencing, health tracking, and graceful shutdown.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import asyncio
import logging
import signal
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger("Falcon.Lifecycle")


class AppState(str, Enum):
    """Lifecycle states of the Falcon Core Engine."""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class ServiceHealth:
    """Tracks health and readiness of individual sub-services."""
    def __init__(self, name: str):
        self.name = name
        self.is_healthy: bool = False
        self.is_optional: bool = False
        self.message: str = "Not initialized"
        self.error: Optional[str] = None

    def mark_healthy(self, message: str = "Operational") -> None:
        self.is_healthy = True
        self.message = message
        self.error = None

    def mark_failed(self, error: str, is_optional: bool = False) -> None:
        self.is_healthy = False
        self.error = error
        self.message = f"Failed: {error}"
        self.is_optional = is_optional

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "healthy": self.is_healthy,
            "optional": self.is_optional,
            "status": self.message,
            "error": self.error,
        }


class LifecycleManager:
    """Coordinates lifecycle transitions, shutdown hooks, and service registry."""

    def __init__(self):
        self._state: AppState = AppState.UNINITIALIZED
        self._services: Dict[str, ServiceHealth] = {}
        self._startup_hooks: List[Callable[[], Coroutine[Any, Any, None]]] = []
        self._shutdown_hooks: List[Callable[[], Coroutine[Any, Any, None]]] = []
        self._shutdown_event = asyncio.Event()

    @property
    def state(self) -> AppState:
        return self._state

    def set_state(self, new_state: AppState) -> None:
        logger.info(f"Falcon lifecycle state changed: {self._state.value} -> {new_state.value}")
        self._state = new_state

    def register_service(self, name: str, is_optional: bool = False) -> ServiceHealth:
        """Register a subsystem for health monitoring."""
        health = ServiceHealth(name)
        health.is_optional = is_optional
        self._services[name] = health
        return health

    def get_service_health(self, name: str) -> Optional[ServiceHealth]:
        return self._services.get(name)

    def get_all_services(self) -> Dict[str, Dict[str, Any]]:
        return {name: svc.to_dict() for name, svc in self._services.items()}

    def add_startup_hook(self, hook: Callable[[], Coroutine[Any, Any, None]]) -> None:
        self._startup_hooks.append(hook)

    def add_shutdown_hook(self, hook: Callable[[], Coroutine[Any, Any, None]]) -> None:
        self._shutdown_hooks.append(hook)

    async def startup(self) -> bool:
        """Run all startup hooks and verify non-optional services are operational."""
        self.set_state(AppState.INITIALIZING)
        for hook in self._startup_hooks:
            try:
                await hook()
            except Exception as e:
                logger.error(f"Error during startup hook {getattr(hook, '__name__', str(hook))}: {e}", exc_info=True)

        # Verify critical services
        failed_critical = [
            name for name, svc in self._services.items()
            if not svc.is_healthy and not svc.is_optional
        ]

        if failed_critical:
            self.set_state(AppState.ERROR)
            logger.error(f"Critical services failed to start: {failed_critical}")
            return False

        self.set_state(AppState.READY)
        return True

    async def shutdown(self) -> None:
        """Gracefully execute shutdown hooks in reverse registration order."""
        if self._state in (AppState.STOPPING, AppState.STOPPED):
            return
        self.set_state(AppState.STOPPING)
        logger.info("Executing graceful shutdown...")

        for hook in reversed(self._shutdown_hooks):
            try:
                await hook()
            except Exception as e:
                logger.error(f"Error executing shutdown hook {getattr(hook, '__name__', str(hook))}: {e}", exc_info=True)

        self._shutdown_event.set()
        self.set_state(AppState.STOPPED)
        logger.info("Falcon shutdown complete.")

    def wait_until_stopped(self) -> asyncio.Event:
        return self._shutdown_event
