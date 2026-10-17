"""
FastAPI Server & REST / WebSocket Endpoints for HarshGuruJi Chat.
Production-ready private messaging platform with 4K UHD UI and Windows 11 integration.
Developed by: HarshGuruJi (Website: https://www.webguruji.online)
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    Cookie,
    FastAPI,
    HTTPException,
    Header,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from falcon.chat.database import ChatDatabaseManager
from falcon.chat.services.blocking import BlockingService
from falcon.chat.services.identity import generate_hgj_id, sanitize_username
from falcon.chat.services.messaging import MessagingService
from falcon.chat.services.user_search import UserSearchService
from falcon.chat.websocket.manager import ChatWebSocketManager
from falcon.system.startup import (
    disable_startup,
    enable_startup,
    get_startup_status,
    is_startup_enabled,
)

logger = logging.getLogger("HarshGuruJi.Chat.Server")


# ==================== PYDANTIC SCHEMAS ====================

class RegisterRequest(BaseModel):
    username: str
    display_name: str
    avatar_url: Optional[str] = None


class LoginRequest(BaseModel):
    username: str


class SendMessageRequest(BaseModel):
    content: str
    idempotency_key: Optional[str] = None
    reply_to_id: Optional[str] = None


class StatusUpdateRequest(BaseModel):
    message_ids: List[str]
    status: str  # 'delivered' or 'seen'


class BlockRequest(BaseModel):
    target_id: str


class StartupToggleRequest(BaseModel):
    action: str  # 'enable' or 'disable'


# ==================== APP FACTORY ====================

def create_chat_app(db_path: Optional[str] = None) -> FastAPI:
    """Create and configure the HarshGuruJi Chat FastAPI application."""
    app = FastAPI(
        title="HarshGuruJi Private Chat Platform",
        version="1.0.0",
        description="Secure real-time private messaging engine developed by HarshGuruJi",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    db = ChatDatabaseManager(db_path)
    blocking = BlockingService(db)
    messaging = MessagingService(db, blocking)
    search_service = UserSearchService(db)
    ws_manager = ChatWebSocketManager()

    # Seed creator profile
    _seed_creator_profile(db)

    # Resolve static assets folder
    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Auth helper
    def get_current_user_id(
        authorization: Optional[str] = Header(None),
        user_id: Optional[str] = Query(None),
        chat_user: Optional[str] = Cookie(None),
    ) -> str:
        """Extract user ID from query param, bearer token, or cookie."""
        if user_id:
            return user_id
        if chat_user:
            return chat_user
        if authorization and authorization.startswith("Bearer "):
            return authorization[7:].strip()
        # Default fallback for local single-user testing: HarshGuruJi
        return "user_harsh_patel"

    # ==================== REST ROUTES ====================

    @app.get("/", response_class=HTMLResponse)
    @app.get("/chat", response_class=HTMLResponse)
    async def get_chat_page():
        """Serve the 2160p 4K UHD messaging interface."""
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return HTMLResponse("<h1>HarshGuruJi Chat 4K UI Loading...</h1>")

    @app.get("/api/health")
    async def health_check():
        return {
            "status": "healthy",
            "platform": "HarshGuruJi Chat Engine v1.0",
            "website": "https://www.webguruji.online",
            "developer": "HarshGuruJi (Harsh Patel)",
            "windows_startup": is_startup_enabled(),
        }

    @app.post("/api/auth/register")
    async def register_user(req: RegisterRequest):
        try:
            clean_username = sanitize_username(req.username)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?;", (clean_username,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail=f"Username '@{clean_username}' is already taken.")

        uid = f"usr_{uuid.uuid4().hex[:12]}"
        hgj_id = generate_hgj_id()

        with db.transaction() as cur:
            cur.execute("""
                INSERT INTO users (id, username, hgj_id, display_name, avatar_url, is_online, last_seen_at)
                VALUES (?, ?, ?, ?, ?, 1, datetime('now'));
            """, (uid, clean_username, hgj_id, req.display_name.strip(), req.avatar_url))

        return {
            "id": uid,
            "username": clean_username,
            "hgj_id": hgj_id,
            "display_name": req.display_name.strip(),
            "avatar_url": req.avatar_url,
        }

    @app.post("/api/auth/login")
    async def login_user(req: LoginRequest):
        clean = req.username.strip().lstrip("@").lower()
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, hgj_id, display_name, avatar_url, is_online, last_seen_at
            FROM users 
            WHERE lower(username) = ? OR upper(hgj_id) = ?;
        """, (clean, clean.upper()))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User account not found.")

        user_data = dict(row)
        # Update online status
        with db.transaction() as cur:
            cur.execute("UPDATE users SET is_online = 1, last_seen_at = datetime('now') WHERE id = ?;", (user_data["id"],))

        return user_data

    @app.get("/api/users/me")
    async def get_me(user_id: str = Query(...)):
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username, hgj_id, display_name, avatar_url, is_online, last_seen_at FROM users WHERE id = ?;", (user_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found.")
        return dict(row)

    @app.get("/api/search")
    async def search_users(q: str = Query(""), user_id: Optional[str] = Query(None)):
        return search_service.search_users(query=q, current_user_id=user_id, limit=15)

    @app.get("/api/conversations")
    async def get_conversations(user_id: str = Query(...)):
        return messaging.list_conversations(user_id=user_id)

    @app.post("/api/conversations")
    async def create_conversation(partner_id: str = Query(...), user_id: str = Query(...)):
        try:
            return messaging.get_or_create_conversation(user_id, partner_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/conversations/{conv_id}/messages")
    async def get_messages(
        conv_id: str,
        user_id: str = Query(...),
        limit: int = Query(50),
        before: Optional[str] = Query(None),
    ):
        try:
            return messaging.get_messages(
                conversation_id=conv_id,
                user_id=user_id,
                limit=limit,
                before_timestamp=before,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/conversations/{conv_id}/messages")
    async def send_message(
        conv_id: str,
        req: SendMessageRequest,
        user_id: str = Query(...),
    ):
        try:
            msg = messaging.send_message(
                conversation_id=conv_id,
                sender_id=user_id,
                content=req.content,
                idempotency_key=req.idempotency_key,
                reply_to_id=req.reply_to_id,
            )
            # Real-time WebSocket dispatch to receiver and sender
            receiver_id = msg["receiver_id"]
            await ws_manager.send_to_user(receiver_id, "message:new", msg)
            await ws_manager.send_to_user(user_id, "message:new", msg)
            return msg
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/messages/status")
    async def update_status(req: StatusUpdateRequest, user_id: str = Query(...)):
        updated_count = messaging.update_status(req.message_ids, req.status, user_id)
        # Notify senders of the status update
        for mid in req.message_ids:
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT sender_id, conversation_id FROM messages WHERE id = ?;", (mid,))
            row = cur.fetchone()
            if row:
                await ws_manager.send_to_user(row["sender_id"], f"message:{req.status}", {
                    "message_id": mid,
                    "conversation_id": row["conversation_id"],
                    "status": req.status,
                })
        return {"updated_count": updated_count, "status": req.status}

    @app.delete("/api/messages/{msg_id}")
    async def delete_message(
        msg_id: str,
        user_id: str = Query(...),
        everyone: bool = Query(False),
    ):
        try:
            messaging.delete_message(msg_id, user_id, delete_for_everyone=everyone)
            return {"success": True, "message_id": msg_id, "deleted_for_everyone": everyone}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/blocks")
    async def block_user(req: BlockRequest, user_id: str = Query(...)):
        try:
            blocking.block_user(user_id, req.target_id)
            return {"success": True, "blocked_id": req.target_id}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.delete("/api/blocks/{target_id}")
    async def unblock_user(target_id: str, user_id: str = Query(...)):
        blocking.unblock_user(user_id, target_id)
        return {"success": True, "unblocked_id": target_id}

    @app.get("/api/blocks")
    async def get_blocks(user_id: str = Query(...)):
        return blocking.get_blocked_users(user_id)

    @app.get("/api/system/startup")
    async def check_startup():
        return get_startup_status()

    @app.post("/api/system/startup")
    async def toggle_startup(req: StartupToggleRequest):
        act = req.action.lower().strip()
        if act == "enable":
            enable_startup()
        elif act == "disable":
            disable_startup()
        return get_startup_status()

    # ==================== WEBSOCKET ROUTE ====================

    @app.websocket("/ws/chat")
    async def websocket_endpoint(websocket: WebSocket, user_id: str = Query(...)):
        await ws_manager.connect(user_id, websocket)
        await ws_manager.broadcast_presence(user_id, True)

        try:
            while True:
                data = await websocket.receive_json()
                event = data.get("event")
                payload = data.get("data", {})

                if event == "typing":
                    # Forward typing to conversation partner
                    partner_id = payload.get("partner_id")
                    if partner_id:
                        await ws_manager.send_to_user(partner_id, "user:typing", {
                            "user_id": user_id,
                            "conversation_id": payload.get("conversation_id"),
                            "is_typing": payload.get("is_typing", True),
                        })

                elif event == "message:send":
                    conv_id = payload.get("conversation_id")
                    content = payload.get("content", "")
                    if conv_id and content:
                        msg = messaging.send_message(
                            conversation_id=conv_id,
                            sender_id=user_id,
                            content=content,
                            idempotency_key=payload.get("idempotency_key"),
                            reply_to_id=payload.get("reply_to_id"),
                        )
                        receiver_id = msg["receiver_id"]
                        await ws_manager.send_to_user(receiver_id, "message:new", msg)
                        await ws_manager.send_to_user(user_id, "message:new", msg)

                elif event == "message:ack":
                    # Acknowledge delivery or seen
                    msg_ids = payload.get("message_ids", [])
                    ack_status = payload.get("status", "delivered")
                    messaging.update_status(msg_ids, ack_status, user_id)
        except WebSocketDisconnect:
            ws_manager.disconnect(user_id, websocket)
            if not ws_manager.is_user_online(user_id):
                await ws_manager.broadcast_presence(user_id, False)
        except Exception as e:
            logger.debug(f"WebSocket error for {user_id}: {e}")
            ws_manager.disconnect(user_id, websocket)

    return app


def _seed_creator_profile(db: ChatDatabaseManager) -> None:
    """Ensure HarshGuruJi (Harsh Patel) profile is permanently created in Chat DB."""
    try:
        with db.transaction() as cur:
            cur.execute("""
                INSERT OR IGNORE INTO users (id, username, hgj_id, display_name, avatar_url, is_online, last_seen_at)
                VALUES (
                    'user_harsh_patel',
                    'harshguruji',
                    'HGJ-7F42K9',
                    'Harsh Patel (HarshGuruJi)',
                    'https://www.webguruji.online/logo-512.png',
                    1,
                    datetime('now')
                );
            """)
            # Also seed an assistant test companion account
            cur.execute("""
                INSERT OR IGNORE INTO users (id, username, hgj_id, display_name, avatar_url, is_online, last_seen_at)
                VALUES (
                    'user_falcon_assistant',
                    'falcon_assistant',
                    'HGJ-A11001',
                    'Falcon AI Core',
                    'https://www.webguruji.online/harshlogo.png',
                    1,
                    datetime('now')
                );
            """)
    except Exception as e:
        logger.debug(f"Creator profile seed note: {e}")
