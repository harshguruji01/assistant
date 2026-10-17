"""
Central Application Controller for Falcon.
Coordinates all subsystems: AI providers, tool registry, conversation pipeline,
task executor, persistent memory, scheduler, and voice interfaces.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional
from falcon.ai.provider_manager import ProviderManager
from falcon.automation.executor import WorkflowExecutor
from falcon.automation.planner import TaskPlanner
from falcon.config.settings import FalconSettings, load_settings
from falcon.core.conversation import ConversationEngine, ConversationResult
from falcon.core.event_bus import Event, EventBus, EventNames
from falcon.core.intent_engine import IntentEngine
from falcon.core.lifecycle import AppState, LifecycleManager
from falcon.memory.conversation_store import ConversationStore
from falcon.memory.database import DatabaseManager
from falcon.memory.long_term_memory import LongTermMemory
from falcon.scheduler.scheduler import FalconScheduler
from falcon.security.policy import SecurityPolicy
from falcon.tools.application_tools import (
    LaunchApplicationTool,
    ListRunningProcessesTool,
    TerminateProcessTool,
)
from falcon.tools.browser_tools import OpenUrlTool, WebSearchTool
from falcon.tools.document_tools import ParseDocumentTool
from falcon.tools.file_tools import (
    ListDirectoryTool,
    MoveFileTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)
from falcon.tools.registry import ToolRegistry
from falcon.tools.system_tools import GetSystemInfoTool, ManageStartupTool, TakeScreenshotTool
from falcon.voice.audio_manager import AudioManager, VoiceState
from falcon.voice.speech_to_text import BaseSTT, DisabledSTT, SpeechRecognitionSTT, VachanaSTT
from falcon.voice.text_to_speech import BaseTTS, DisabledTTS, Pyttsx3TTS, SarvamTTS, VachanaTTS, WindowsSapiTTS

logger = logging.getLogger("Falcon.Core")


class FalconCore:
    """The central brain and orchestrator of Falcon AI Desktop Assistant."""

    def __init__(self, settings: Optional[FalconSettings] = None):
        self.settings = settings or load_settings()
        self.lifecycle = LifecycleManager()
        self.event_bus = EventBus()

        # Security & Policy
        self.security_policy = SecurityPolicy(
            require_approval_for_high_risk=self.settings.security.require_approval_for_high_risk
        )

        # Database & Memory
        self.db = DatabaseManager(self.settings.database_path)
        self.conversation_store = ConversationStore(self.db)
        self.long_term_memory = LongTermMemory(self.db)

        # Tools & Capabilities
        self.tool_registry = ToolRegistry(self.security_policy)
        self._register_default_tools()

        # AI & Conversation
        self.provider_manager = ProviderManager(self.settings.ai)
        self.intent_engine = IntentEngine()
        self.conversation = ConversationEngine(self.provider_manager, self.intent_engine)

        # Seed Permanent Creator Identity & Memory
        self._seed_creator_memories()

        # Connect tool execution callback to conversation engine
        self.conversation.set_tool_executor(
            executor_func=self.tool_registry.execute_tool,
            tool_definitions=self.tool_registry.list_tool_definitions(),
        )
        self.conversation.set_memory_retriever(self._get_active_memories)

        # Automation & Workflows
        self.planner = TaskPlanner(self.tool_registry)
        self.executor = WorkflowExecutor(self.tool_registry, self.event_bus)

        # Scheduler
        self.scheduler = FalconScheduler(
            self.db, self.event_bus, tick_interval=self.settings.scheduler_tick_seconds
        )

        # Voice
        self.audio_manager = AudioManager(self.event_bus)
        self.tts: BaseTTS = self._init_tts()
        self.stt: BaseSTT = self._init_stt()

        # Register services with lifecycle manager
        self._db_health = self.lifecycle.register_service("Database", is_optional=False)
        self._ai_health = self.lifecycle.register_service("AI_Provider", is_optional=False)
        self._scheduler_health = self.lifecycle.register_service("Scheduler", is_optional=False)
        self._voice_health = self.lifecycle.register_service("Voice", is_optional=True)
        self._chat_health = self.lifecycle.register_service("Chat_Server", is_optional=True)
        self._chat_server = None

    def _register_default_tools(self) -> None:
        """Register the built-in Windows automation tools."""
        allowed = self.settings.security.approved_directories

        # File tools
        self.tool_registry.register_tool(ListDirectoryTool(allowed))
        self.tool_registry.register_tool(ReadFileTool(allowed))
        self.tool_registry.register_tool(WriteFileTool(allowed))
        self.tool_registry.register_tool(SearchFilesTool(allowed))
        self.tool_registry.register_tool(MoveFileTool(allowed))

        # Application tools
        self.tool_registry.register_tool(LaunchApplicationTool(self.security_policy))
        self.tool_registry.register_tool(ListRunningProcessesTool())
        self.tool_registry.register_tool(TerminateProcessTool())

        # System tools
        self.tool_registry.register_tool(GetSystemInfoTool())
        self.tool_registry.register_tool(TakeScreenshotTool())
        self.tool_registry.register_tool(ManageStartupTool())

        # Browser tools
        self.tool_registry.register_tool(OpenUrlTool())
        self.tool_registry.register_tool(WebSearchTool())

        # Document tools
        self.tool_registry.register_tool(ParseDocumentTool(allowed))

    def _seed_creator_memories(self) -> None:
        """Seed permanent uneraseable knowledge about creator Harsh Patel (HarshGuruJi)."""
        core_memories = [
            ("creator_identity", "Developer & Creator: HarshGuruJi (Real Name: Harsh Patel)."),
            ("creator_website", "Official Website of Owner & HarshGuruJi: www.webguruji.online"),
            ("creator_vision", "Falcon AI is built specifically for HarshGuruJi as a real, production-ready Windows 11 AI desktop assistant."),
            ("memory_policy", "Unbreakable Memory Directive: Never forget Harsh Patel (HarshGuruJi), his website www.webguruji.online, his preferences, instructions, or photos."),
        ]
        for key, text in core_memories:
            try:
                self.long_term_memory.add_memory(
                    category="creator_profile",
                    content=text,
                    approved_by_user=True,
                    memory_id=f"core_{key}",
                )
            except Exception as e:
                logger.debug(f"Memory seed notice: {e}")

    def _get_active_memories(self) -> List[str]:
        """Fetch all stored memories from SQLite to inject into conversation context."""
        try:
            mems = self.long_term_memory.get_memories()
            return [m["content"] for m in mems]
        except Exception:
            return []

    def _init_tts(self) -> BaseTTS:
        """Initialize TTS provider with graceful fallback (Vachana AI / Sarvam AI -> pyttsx3 -> Windows SAPI)."""
        if not self.settings.voice.enabled:
            return DisabledTTS()

        # 1. Check if Vachana is preferred or key is present
        if self.settings.voice.tts_provider == "vachana" and self.settings.voice.vachana_api_key:
            vach = VachanaTTS(
                api_key=self.settings.voice.vachana_api_key,
                voice=self.settings.voice.vachana_tts_voice,
                model=self.settings.voice.vachana_tts_model,
            )
            if vach.is_available():
                logger.info("Initialized Gnani.ai / Vachana Voice AI TTS (timbre-v3.0).")
                return vach

        # 2. Check Sarvam AI Indian Voice API
        if self.settings.voice.sarvam_api_key:
            sarvam = SarvamTTS(
                api_key=self.settings.voice.sarvam_api_key,
                speaker=self.settings.voice.tts_voice_id or "aditya",
                model="bulbul:v3",
                language_code="hi-IN" if "hi" in self.settings.voice.stt_language else "en-IN",
            )
            if sarvam.is_available():
                logger.info("Initialized high-fidelity Indian Voice TTS (Sarvam AI Bulbul v3).")
                return sarvam

        # 3. Check Vachana fallback if Sarvam key was not set
        if self.settings.voice.vachana_api_key:
            vach = VachanaTTS(
                api_key=self.settings.voice.vachana_api_key,
                voice=self.settings.voice.vachana_tts_voice,
                model=self.settings.voice.vachana_tts_model,
            )
            if vach.is_available():
                logger.info("Initialized Gnani.ai / Vachana Voice AI TTS (timbre-v3.0).")
                return vach

        # 4. Try pyttsx3 next
        pyttsx = Pyttsx3TTS(rate=self.settings.voice.tts_rate, volume=self.settings.voice.tts_volume)
        if pyttsx.is_available():
            return pyttsx

        # 5. Fall back to native Windows SAPI
        sapi = WindowsSapiTTS()
        if sapi.is_available():
            return sapi

        return DisabledTTS()

    def _init_stt(self) -> BaseSTT:
        """Initialize STT provider with Vachana or SpeechRecognition."""
        if not self.settings.voice.enabled:
            return DisabledSTT()

        # Check Vachana STT first if configured
        if self.settings.voice.vachana_api_key:
            vach_stt = VachanaSTT(
                api_key=self.settings.voice.vachana_api_key,
                language_code=self.settings.voice.stt_language,
                model=self.settings.voice.vachana_stt_model,
                device_index=self.settings.voice.microphone_index,
            )
            if vach_stt.is_available():
                logger.info("Initialized Gnani.ai / Vachana Voice AI STT (gnani-prisma-v2.5).")
                return vach_stt

        stt = SpeechRecognitionSTT(device_index=self.settings.voice.microphone_index)
        if stt.is_available():
            return stt
        return DisabledSTT()

    async def start(self) -> bool:
        """Start all services in sequence and publish assistant.ready."""
        logger.info(f"Starting {self.settings.app_name} by {self.settings.developer}...")

        # 1. Database check
        try:
            self._db_health.mark_healthy()
        except Exception as e:
            self._db_health.mark_failed(str(e))
            return False

        # 2. AI Provider check
        active_provider = await self.provider_manager.get_active_provider()
        self._ai_health.mark_healthy(f"Using {active_provider.name} ({active_provider.model})")

        # 3. Start Scheduler
        try:
            await self.scheduler.start()
            self._scheduler_health.mark_healthy()
        except Exception as e:
            self._scheduler_health.mark_failed(str(e))
            return False

        # 4. Check Voice
        if self.settings.voice.enabled and (self.tts.is_available() or self.stt.is_available()):
            self._voice_health.mark_healthy("Voice services active")
        else:
            self._voice_health.mark_healthy("Voice services disabled or using fallback")

        # 5. Start HarshGuruJi 4K Chat Server
        if self.settings.chat_server_enabled:
            self._start_chat_server()

        # Set app lifecycle state
        self.lifecycle.set_state(AppState.READY)

        # Announce readiness
        await self.event_bus.publish(
            Event(
                topic=EventNames.ASSISTANT_READY,
                data={
                    "app_name": self.settings.app_name,
                    "version": self.settings.app_version,
                    "developer": self.settings.developer,
                    "services": self.lifecycle.get_all_services(),
                },
            )
        )
        logger.info("Falcon Core is fully initialized and READY.")
        return True

    def _start_chat_server(self) -> None:
        """Start the HarshGuruJi 4K Chat Server in a background daemon thread."""
        try:
            import threading
            import uvicorn
            from falcon.chat.server import create_chat_app
            chat_app = create_chat_app()
            
            config = uvicorn.Config(
                chat_app,
                host=self.settings.chat_server_host,
                port=self.settings.chat_server_port,
                log_level="warning",
            )
            server = uvicorn.Server(config)
            
            thread = threading.Thread(target=server.run, daemon=True, name="HarshGuruJiChatServer")
            thread.start()
            self._chat_server = server
            self._chat_health.mark_healthy(f"Serving at http://{self.settings.chat_server_host}:{self.settings.chat_server_port}/chat")
            logger.info(f"HarshGuruJi 4K Chat Server started on http://{self.settings.chat_server_host}:{self.settings.chat_server_port}/chat")
        except Exception as e:
            self._chat_health.mark_failed(str(e))
            logger.warning(f"Could not start HarshGuruJi Chat Server: {e}")

    async def process_message(
        self,
        message_text: str,
        session_id: Optional[str] = None,
        speak_response: bool = False,
    ) -> ConversationResult:
        """Public API to process user input (from UI, CLI, or speech)."""
        sid = session_id or f"sess_{uuid.uuid4().hex[:6]}"
        logger.info(f"Processing message in session '{sid}': {message_text}")

        # Publish message received event
        await self.event_bus.publish(
            Event(
                topic=EventNames.ASSISTANT_MESSAGE_RECEIVED,
                data={"text": message_text, "session_id": sid},
                correlation_id=sid,
            )
        )

        # Notify UI response started
        await self.event_bus.publish(
            Event(
                topic=EventNames.ASSISTANT_RESPONSE_STARTED,
                data={"session_id": sid},
                correlation_id=sid,
            )
        )

        # Save user message to durable storage
        self.conversation_store.save_message(
            session_id=sid,
            role="user",
            content=message_text,
        )

        # Execute conversation turn
        result = await self.conversation.process_user_turn(message_text, correlation_id=sid)

        # Save assistant response to durable storage
        self.conversation_store.save_message(
            session_id=sid,
            role="assistant",
            content=result.response_text,
            tool_calls=result.executed_tools,
            provider=result.provider_used,
        )

        # Publish response completed event
        await self.event_bus.publish(
            Event(
                topic=EventNames.ASSISTANT_RESPONSE_COMPLETED,
                data={
                    "session_id": sid,
                    "text": result.response_text,
                    "tools": result.executed_tools,
                    "latency": result.latency_seconds,
                },
                correlation_id=sid,
            )
        )

        # Optional audio playback
        if speak_response and self.settings.voice.enabled:
            asyncio.create_task(self.speak_text(result.response_text))

        return result

    async def speak_text(self, text: str) -> None:
        """Speak given text using configured TTS engine."""
        await self.audio_manager.set_state(VoiceState.SPEAKING)
        try:
            await self.tts.speak(text)
        finally:
            await self.audio_manager.set_state(VoiceState.IDLE)

    def stop_speaking(self) -> None:
        """Interrupt active speech synthesis."""
        self.tts.stop()

    def cancel_task(self, task_id: str) -> bool:
        """Cancel an ongoing automation workflow."""
        return self.executor.cancel_task(task_id)

    async def shutdown(self) -> None:
        """Gracefully terminate background services and scheduler."""
        logger.info("Initiating Falcon Core shutdown...")
        self.stop_speaking()
        await self.scheduler.stop()
        await self.lifecycle.shutdown()
        logger.info("Falcon Core shutdown complete.")

    def get_status(self) -> Dict[str, Any]:
        """Return real-time diagnostic and health information."""
        return {
            "app_name": self.settings.app_name,
            "version": self.settings.app_version,
            "developer": self.settings.developer,
            "state": self.lifecycle.state.value,
            "services": self.lifecycle.get_all_services(),
            "tools_count": len(self.tool_registry.list_tool_definitions()),
            "voice_state": self.audio_manager.state.value,
        }
