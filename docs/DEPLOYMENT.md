# HarshGuruJi Chat Production Deployment Guide
**Target Domain:** [https://www.webguruji.online](https://www.webguruji.online) | `chat.webguruji.online`
**Developer:** HarshGuruJi (Harsh Patel)

---

### 1. Architecture Overview
- **Core Server:** FastAPI ASGI Application with WebSockets.
- **Database:** SQLite WAL mode (zero-config local desktop) with direct compatibility for PostgreSQL/Supabase.
- **Frontend:** 4K UHD High-DPI Responsive Single-Page Application (HTML5 / Vanilla CSS / Modern JS) with no third-party framework overhead.
- **Reverse Proxy:** Nginx / Caddy / Cloudflare Tunnel.

---

### 2. Production ASGI Server (Systemd / NSSM / Windows Service)

On Windows using NSSM (Non-Sucking Service Manager):
```powershell
nssm install HarshGuruJiChat "C:\Program Files\Python314\python.exe" "-m uvicorn falcon.chat.server:create_chat_app --factory --host 0.0.0.0 --port 8000 --workers 4"
nssm start HarshGuruJiChat
```

On Linux VPS / Cloud:
```bash
uvicorn falcon.chat.server:create_chat_app --factory --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers
```

---

### 3. Nginx Reverse Proxy & WebSocket Configuration

```nginx
server {
    server_name chat.webguruji.online;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket Upgrade
    location /ws/ {
        proxy_pass http://127.0.0.1:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

---

### 4. Supabase Migration Alignment
If deploying against Supabase PostgreSQL:
The schema in [`c:\Users\harsh\OneDrive\Desktop\site\supabase_chat_setup.sql`](file:///c:/Users/harsh/OneDrive/Desktop/site/supabase_chat_setup.sql) defines the identical tables (`profiles`, `conversations`, `messages`, `user_blocks`) and RLS security policies.
