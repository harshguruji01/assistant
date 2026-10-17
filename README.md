# 🦅 Falcon AI Desktop Assistant
> **A Modular, Production-Grade Python Core Engine for Windows 11 Desktop Automation**  
> **Engineered by:** HarshGuruJi  
> **Platform:** Windows 11  
> **Language:** Python 3.12+ (Full Python 3.14 Compatibility)

---

## 📌 1. Project Overview

**Falcon** is a real, production-oriented Python core engine designed specifically for Windows 11. It provides an extensible, modular architecture that bridges natural language processing, intelligent intent analysis, tool selection, Windows system automation, voice interfaces, and persistent memory.

The core engine is strictly decoupled from any graphical user interface, exposing a clean, event-driven asynchronous API that connects seamlessly to:
- **PySide6** Windows desktop applications
- Speech-to-text / Text-to-speech voice pipelines
- Windows System Tray controllers
- Command-line interfaces & developer automation scripts

---

## 🏛️ 2. Architectural Blueprint

```
falcon/
├── main.py                     # CLI launcher, diagnostic runner, and eval entry point
├── __init__.py                 # Package metadata and version info
├── config/
│   └── settings.py             # Strongly-typed configuration loader (.env & JSON)
├── security/
│   ├── policy.py               # Risk tiers (READ_ONLY -> CRITICAL) & audit logging
│   ├── validation.py           # Path traversal protection & prompt injection heuristics
│   └── secrets.py              # Automatic credential redaction in logs/events
├── core/
│   ├── controller.py           # FalconCore central application orchestrator
│   ├── conversation.py         # Multi-turn conversation pipeline & tool loops
│   ├── intent_engine.py        # Hybrid rule/semantic intent classifier (EN, HI, Hinglish)
│   ├── event_bus.py            # Typed asynchronous event bus with wildcard matching
│   └── lifecycle.py            # Subsystem startup sequencing, health checks, shutdown
├── ai/
│   ├── base_provider.py        # Abstract AI provider interfaces & message models
│   ├── provider_manager.py     # Multi-provider manager with automatic fallback
│   ├── local_provider.py       # Local Ollama inference adapter
│   ├── cloud_provider.py       # OpenAI-compatible / Gemini / Anthropic cloud adapter
│   ├── mock_provider.py        # Offline deterministic testing provider
│   └── tool_calling.py         # JSON schema conversion & tool call deserialization
├── tools/
│   ├── registry.py             # Tool registration, schema validation, approval gates
│   ├── file_tools.py           # Safe listing, reading, writing, searching, moving files
│   ├── application_tools.py    # Launching approved apps, process listing, termination
│   ├── system_tools.py         # System metrics (CPU, RAM, Disk, Battery) & screenshots
│   ├── browser_tools.py        # Default browser URL opening & web search
│   └── document_tools.py       # Safe structured document parsing (.txt, .md, .csv, .json)
├── automation/
│   ├── workflow.py             # Finite-state workflow model (PENDING -> COMPLETED)
│   ├── planner.py              # Task decomposition & dependency graph generation
│   └── executor.py             # Bounded retries, cancellation tokens, step progress
├── memory/
│   ├── database.py             # SQLite WAL-mode transactional database manager
│   ├── conversation_store.py   # Multi-turn session history, search, and export
│   └── long_term_memory.py     # User-approved memory entries & key-value preferences
├── scheduler/
│   ├── jobs.py                 # Scheduled job models (reminders, timers, alarms, recurring)
│   └── scheduler.py            # Durable persistent task scheduler with timezone awareness
├── voice/
│   ├── audio_manager.py        # Audio device diagnostics & voice state machine
│   ├── speech_to_text.py       # Speech recognition adapter (English & Hindi)
│   ├── text_to_speech.py       # SAPI5 / pyttsx3 speech synthesis with interruption
│   └── wake_word.py            # Wake-word detection interface
├── chat/
│   ├── database.py             # SQLite WAL chat database manager & indexer
│   ├── server.py               # FastAPI REST & WebSocket server
│   ├── services/
│   │   ├── identity.py         # Collision-resistant HGJ-XXXXXX ID generator
│   │   ├── user_search.py      # Ranked search service (exact, prefix, ID, display)
│   │   ├── messaging.py        # Real-time messages, idempotency, delete for me/everyone
│   │   └── blocking.py         # Bidirectional block policy enforcement
│   ├── websocket/
│   │   └── manager.py          # WebSocket connection manager & real-time dispatcher
│   └── static/
│       ├── index.html          # 4K UHD (2160p) responsive private messaging interface
│       ├── style.css           # Glassmorphism, Instagram DM gradients, WhatsApp ticks
│       └── app.js              # Real-time WebSocket event reconciliation & startup toggle
├── system/
│   └── startup.py              # Native Windows 11 Startup Registry Manager (HKCU\Run)
└── ui/
    ├── ui_bridge.py            # Thread-safe Qt Signals adapter & Python event bridge
    └── desktop_app.py          # PySide6 desktop window interface
```

---

## ⚡ 3. Quick Start & Installation

### Requirements
- **Windows 11** (or Windows 10)
- **Python 3.12+** (Python 3.14 verified)

### 1. Setup Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
```powershell
pip install -r requirements.txt
```
*(Falcon is designed with standard-library resilience. If optional packages are omitted, it gracefully activates native Windows fallbacks for PowerShell SAPI audio, system queries, and offline mock inference!)*

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```powershell
cp .env.example .env
```
Configure your desired AI backend and keys (e.g. `OLLAMA_BASE_URL` or `OPENAI_API_KEY`).

---

## 🚀 4. Running Falcon

### Run Interactive CLI
```powershell
python main.py
```

### Run Diagnostics Self-Test
Checks Python version, package availability, SQLite read/write capability, Windows version, and AI provider status:
```powershell
python main.py --diagnostics
```

### Evaluate Single Command / Prompt
```powershell
python main.py --eval "Namaste Falcon, who created you?"
python main.py --eval "Show CPU and RAM specs"
python main.py --eval "Open notepad"
```

---

## 🔌 5. FalconCore Public API Reference

The core engine is encapsulated in `FalconCore`:

```python
import asyncio
from falcon.core.controller import FalconCore
from falcon.config.settings import load_settings

async def main():
    settings = load_settings()
    core = FalconCore(settings)

    # 1. Start application services
    await core.start()

    # 2. Process message (natural language query or automation instruction)
    result = await core.process_message("Show current CPU usage and free disk space")
    print(f"Response: {result.response_text}")
    print(f"Executed Tools: {result.executed_tools}")

    # 3. Schedule a reminder
    core.scheduler.schedule_reminder("Team Meeting", delay_seconds=60)

    # 4. Graceful shutdown
    await core.shutdown()

asyncio.run(main())
```

---

## 🤖 6. AI Providers & Model Connection

### A. Local Offline Inference with Ollama (Recommended for Privacy)
1. Install [Ollama for Windows](https://ollama.com).
2. Pull your model:
   ```powershell
   ollama pull llama3.2
   ```
3. Set `.env`:
   ```ini
   FALCON_AI_PROVIDER=ollama
   FALCON_AI_MODEL=llama3.2
   OLLAMA_BASE_URL=http://localhost:11434
   ```

### B. Cloud Models (OpenAI, Gemini, Anthropic, Groq)
In `.env`:
```ini
FALCON_AI_PROVIDER=openai
FALCON_AI_MODEL=gpt-4o-mini
OPENAI_API_KEY=your_key_here
```

### C. Offline Fallback
Falcon includes an intelligent, deterministic `MockAIProvider` that runs completely offline with zero API keys or external downloads. If your primary provider is unreachable, Falcon automatically fails over to the fallback provider without crashing.

---

## 🎙️ 7. Voice Engine Integration

Falcon provides independent Speech-to-Text and Text-to-Speech:
- **Speech Recognition:** Uses `SpeechRecognition` library supporting English (`en-US`) and Hindi (`hi-IN`).
- **Text-to-Speech:** Uses `pyttsx3` (Windows SAPI5) or native PowerShell `.NET System.Speech` fallback when `pyttsx3` is not installed.
- **Interruption Support:** Call `core.stop_speaking()` to instantly interrupt spoken responses.
- **Microphone Diagnostics:** Call `core.audio_manager.check_audio_health()` to inspect connected microphones.

---

## 🛡️ 8. Security & Permissions

Falcon implements security by design:
1. **Tool Permission Tiers:**
   - `READ_ONLY`: Safe read-only operations (listing files, checking CPU).
   - `LOW_RISK`: Benign actions (opening notepad, browser search).
   - `MEDIUM_RISK`: Write actions (writing files, moving folders).
   - `HIGH_RISK`: Destructive operations (killing processes, deleting files) — requires user approval callback!
2. **Directory Containment:** All file operations are checked against `approved_directories` to prevent path traversal (`../`) attacks.
3. **Critical System Protection:** Write/delete operations to `C:\Windows`, `C:\Program Files`, etc. are strictly blocked.
4. **Credential Redaction:** API keys, Bearer tokens, and secrets are automatically scrubbed from all logs.
5. **Prompt Injection Heuristics:** Untrusted external files and web pages are scanned for injection patterns before processing.

---

## 🧪 9. Automated Testing Suite

Falcon includes a comprehensive unit and integration test suite using Python's standard `unittest`:

```powershell
python -m unittest discover tests
```

### Test Coverage Areas:
- ✅ Configuration loading and environment variable precedence
- ✅ Secret redaction (OpenAI, Anthropic, Google keys, Bearer tokens)
- ✅ Path traversal prevention and system folder write protection
- ✅ Prompt injection detection
- ✅ Typed asynchronous event bus with wildcard dispatch
- ✅ Multilingual intent classification (English, Hindi, Hinglish)
- ✅ SQLite WAL database persistence, conversation store, and search
- ✅ User-approved long term memory and preferences
- ✅ Scheduler persistence, timers, and recovery after restart
- ✅ Tool schema validation and interactive approval gating
- ✅ Workflow step execution, dependency resolution, and task cancellation
- ✅ Complete FalconCore lifecycle (startup, message turn, shutdown)

---

## 📋 10. Completed Features & Setup Matrix

| Feature | Implementation Status | Additional Setup Required |
|---|---|---|
| **Core Architecture & Lifecycle** | ✅ Fully Implemented | None (Built-in standard library) |
| **Typed Event Bus** | ✅ Fully Implemented | None |
| **Multilingual Intent Engine** | ✅ Fully Implemented | None (English, Hindi, Hinglish supported) |
| **Tool Registry & Execution** | ✅ Fully Implemented | None |
| **Safe File Operations** | ✅ Fully Implemented | None |
| **Windows App Launching** | ✅ Fully Implemented | None |
| **System Info & Metrics** | ✅ Fully Implemented | Optional: `pip install psutil` |
| **Desktop Screenshots** | ✅ Fully Implemented | Optional: `pip install Pillow` (has native PowerShell fallback) |
| **Browser Web Search** | ✅ Fully Implemented | None |
| **Workflow State Machine** | ✅ Fully Implemented | None |
| **SQLite Persistent Memory** | ✅ Fully Implemented | None (Automatic `%LOCALAPPDATA%\FalconAI\falcon.db`) |
| **Persistent Task Scheduler** | ✅ Fully Implemented | None |
| **Security & Redaction** | ✅ Fully Implemented | None |
| **Diagnostic Self-Test Utility** | ✅ Fully Implemented | Run `python main.py --diagnostics` |
| **Ollama Local Provider** | ✅ Fully Implemented | Install [Ollama](https://ollama.com) |
| **Cloud AI Provider** | ✅ Fully Implemented | Add API key to `.env` |
| **Speech-To-Text (STT)** | ✅ Fully Implemented | Optional: `pip install SpeechRecognition` |
| **Text-To-Speech (TTS)** | ✅ Fully Implemented | Optional: `pip install pyttsx3` (has Windows SAPI fallback) |
| **Desktop GUI Window** | ✅ Fully Implemented | Optional: `pip install PySide6` |

---

## 👨‍💻 Developer & Attribution
- **Assistant Name:** Falcon AI Desktop Assistant
- **Developer:** HarshGuruJi
- **Platform:** Windows 11
