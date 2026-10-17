"""
WebSocket Connection & Event Manager for HarshGuruJi Chat.
Handles real-time message routing, delivery receipts, read receipts, and presence updates.
Developed by: HarshGuruJi (Website: https://www.webguruji.online)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Set
from fastapi import WebSocket

logger = logging.getLogger("HarshGuruJi.Chat.WebSocket")


class ChatWebSocketManager:
    """Manages active WebSocket connections per authenticated user."""

    def __init__(self):
        # Maps user_id -> set of active WebSockets (supports multi-tab / multi-device)
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        """Accept WebSocket connection and register user."""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        logger.info(f"User {user_id} connected (total sockets: {len(self.active_connections[user_id])})")

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        """Unregister closed socket connection."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"User {user_id} disconnected.")

    def is_user_online(self, user_id: str) -> bool:
        """Check if user has at least one active connection."""
        return bool(self.active_connections.get(user_id))

    async def send_to_user(self, user_id: str, event_type: str, data: Dict[str, Any]) -> None:
        """Dispatch a JSON event to all active sockets of a user."""
        sockets = self.active_connections.get(user_id, set()).copy()
        if not sockets:
            return

        payload = json.dumps({"event": event_type, "data": data})
        stale_sockets = []
        for ws in sockets:
            try:
                await ws.send_text(payload)
            except Exception as e:
                logger.debug(f"Failed to send to socket for {user_id}: {e}")
                stale_sockets.append(ws)

        for stale in stale_sockets:
            self.disconnect(user_id, stale)

    async def broadcast_presence(self, user_id: str, is_online: bool) -> None:
        """Notify active connections of user status."""
        payload = json.dumps({
            "event": "user:presence",
            "data": {"user_id": user_id, "is_online": is_online}
        })
        for uid, sockets in list(self.active_connections.items()):
            if uid == user_id:
                continue
            for ws in list(sockets):
                try:
                    await ws.send_text(payload)
                except Exception:
                    pass
