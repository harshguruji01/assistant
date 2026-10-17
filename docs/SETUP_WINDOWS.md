# HarshGuruJi Chat & Falcon Windows 11 Setup Guide
**Platform:** Windows 11 | **Developer:** HarshGuruJi (Harsh Patel) | **Website:** [www.webguruji.online](https://www.webguruji.online)

---

### 1. Prerequisites
- **Operating System:** Windows 11 64-bit
- **Python:** 3.12+ (Fully verified on Python 3.14 64-bit)
- **PowerShell:** 5.1+ or PowerShell 7

---

### 2. Quick Setup & Virtual Environment (PowerShell)

```powershell
# 1. Navigate to Falcon root
cd "C:\Users\harsh\OneDrive\Desktop\AI\Desktop assistant"

# 2. Install application dependencies
python -m pip install -r requirements.txt

# 3. Configure local environment variables
Copy-Item .env.example .env
```

---

### 3. Activating Windows Startup Auto-Launch

Falcon now has built-in native Windows Startup activation via registry (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`).

To activate directly from PowerShell:
```powershell
python -c "from falcon.system.startup import enable_startup; enable_startup(); print('Falcon registered on Windows Startup!')"
```

To verify status:
```powershell
python -c "from falcon.system.startup import get_startup_status; print(get_startup_status())"
```

You can also toggle Windows Startup with one click directly inside the 4K Chat Web Interface (`⚡ Windows Startup: ON / OFF`).

---

### 4. Running the 4K UHD Chat & AI Engine

```powershell
# Launch Falcon Core + 4K Real-time Chat Engine
python main.py
```

The system will start:
1. **HarshGuruJi 4K Chat Platform:** [http://127.0.0.1:8000/chat](http://127.0.0.1:8000/chat)
2. **WebSocket Realtime Gateway:** `ws://127.0.0.1:8000/ws/chat`
3. **NVIDIA NIM AI Brain:** Active with thinking reasoning
4. **Vachana AI Voice Engine:** Active for STT & TTS
5. **Windows 11 Automation Tools:** 13 tools active (including `manage_startup`)

---

### 5. Running Automated Verification Tests

```powershell
python -m unittest discover tests
```
*All 41 unit and integration tests will execute and verify identity, search, messaging, blocking, status, and startup.*
