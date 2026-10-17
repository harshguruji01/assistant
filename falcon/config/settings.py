"""
Configuration and Settings Management for Falcon.
Supports loading from environment variables, .env files, and JSON settings.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def _get_default_data_dir() -> Path:
    """Return default user data directory for Falcon."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data) / "FalconAI"
    else:
        base = Path.home() / ".falcon"
    return base


@dataclass
class AISettings:
    """Settings for AI model providers."""
    default_provider: str = "ollama"  # ollama, openai, gemini, anthropic, mock
    fallback_provider: Optional[str] = "mock"
    default_model: str = "llama3.2"
    temperature: float = 0.7
    max_tokens: int = 2048
    request_timeout_seconds: float = 30.0
    max_retries: int = 2
    
    # Provider endpoints & credentials
    ollama_base_url: str = "http://localhost:11434"
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    nvidia_api_key: Optional[str] = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    gemini_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None


@dataclass
class VoiceSettings:
    """Settings for Speech-To-Text and Text-To-Speech."""
    enabled: bool = True
    # Providers: vachana, sarvam, pyttsx3, windows_sapi, disabled
    tts_provider: str = "vachana"              
    sarvam_api_key: Optional[str] = None
    # Providers: vachana, speech_recognition, whisper, vosk, disabled
    stt_provider: str = "vachana"              
    vachana_api_key: Optional[str] = None
    vachana_tts_voice: str = "Devansh"
    vachana_tts_model: str = "timbre-v3.0"
    vachana_stt_model: str = "gnani-prisma-v2.5"
    stt_language: str = "hi-IN"              # en-US, hi-IN
    tts_voice_id: Optional[str] = "Devansh"
    tts_rate: int = 190
    tts_volume: float = 0.95
    wake_word_enabled: bool = False
    wake_word: str = "falcon"
    microphone_index: Optional[int] = None


@dataclass
class SecuritySettings:
    """Settings for system automation permissions and boundaries."""
    require_approval_for_high_risk: bool = True
    approved_directories: List[str] = field(default_factory=lambda: [
        str(Path.home() / "Desktop"),
        str(Path.home() / "Documents"),
        str(Path.home() / "Downloads"),
        str(Path.home() / "Pictures"),
        str(Path.home() / "Videos"),
        str(Path.home() / "Music"),
        str(Path.cwd()),
    ])
    max_execution_time_seconds: float = 60.0
    allow_shell_commands: bool = False


@dataclass
class FalconSettings:
    """Global configuration settings for Falcon AI Desktop Assistant."""
    app_name: str = "Falcon AI Desktop Assistant"
    app_version: str = "1.0.0"
    developer: str = "HarshGuruJi"
    platform: str = "Windows 11"
    
    # Paths
    base_data_dir: str = field(default_factory=lambda: str(_get_default_data_dir()))
    database_path: Optional[str] = None
    log_dir: Optional[str] = None
    log_level: str = "INFO"
    
    # Sub-configurations
    ai: AISettings = field(default_factory=AISettings)
    voice: VoiceSettings = field(default_factory=VoiceSettings)
    security: SecuritySettings = field(default_factory=SecuritySettings)
    
    # Scheduler
    scheduler_tick_seconds: float = 1.0

    # HarshGuruJi Real-time 4K Chat Server
    chat_server_enabled: bool = True
    chat_server_host: str = "127.0.0.1"
    chat_server_port: int = 8000

    def __post_init__(self):
        # Resolve derived directory paths
        base_path = Path(self.base_data_dir)
        if not self.database_path:
            self.database_path = str(base_path / "falcon.db")
        if not self.log_dir:
            self.log_dir = str(base_path / "logs")


def load_env_file(filepath: str | Path) -> None:
    """Manually parse .env file and set environment variables without requiring external dependencies."""
    p = Path(filepath)
    if not p.is_file():
        return
    try:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


def load_settings(config_file: Optional[str | Path] = None) -> FalconSettings:
    """
    Load settings with precedence:
    1. Environment variables
    2. Local .env file
    3. config.json (if present)
    4. Default values
    """
    # Try loading .env from current directory or parent directory
    load_env_file(Path.cwd() / ".env")

    settings = FalconSettings()

    # Load from JSON file if provided or if default exists
    cfg_path = Path(config_file) if config_file else Path.cwd() / "config.json"
    if cfg_path.is_file():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "app_name" in data:
                    settings.app_name = data["app_name"]
                if "log_level" in data:
                    settings.log_level = data["log_level"]
                if "base_data_dir" in data:
                    settings.base_data_dir = data["base_data_dir"]
                if "ai" in data and isinstance(data["ai"], dict):
                    for k, v in data["ai"].items():
                        if hasattr(settings.ai, k):
                            setattr(settings.ai, k, v)
                if "voice" in data and isinstance(data["voice"], dict):
                    for k, v in data["voice"].items():
                        if hasattr(settings.voice, k):
                            setattr(settings.voice, k, v)
                if "security" in data and isinstance(data["security"], dict):
                    for k, v in data["security"].items():
                        if hasattr(settings.security, k):
                            setattr(settings.security, k, v)
        except Exception:
            pass

    # Override with Environment Variables
    if os.getenv("FALCON_AI_PROVIDER"):
        settings.ai.default_provider = os.getenv("FALCON_AI_PROVIDER", settings.ai.default_provider)
    if os.getenv("FALCON_AI_MODEL"):
        settings.ai.default_model = os.getenv("FALCON_AI_MODEL", settings.ai.default_model)
    if os.getenv("OLLAMA_BASE_URL"):
        settings.ai.ollama_base_url = os.getenv("OLLAMA_BASE_URL", settings.ai.ollama_base_url)
    if os.getenv("OPENAI_API_KEY"):
        settings.ai.openai_api_key = os.getenv("OPENAI_API_KEY")
    if os.getenv("OPENAI_BASE_URL"):
        settings.ai.openai_base_url = os.getenv("OPENAI_BASE_URL")
    if os.getenv("NVIDIA_API_KEY"):
        settings.ai.nvidia_api_key = os.getenv("NVIDIA_API_KEY")
    if os.getenv("NVIDIA_BASE_URL"):
        settings.ai.nvidia_base_url = os.getenv("NVIDIA_BASE_URL", settings.ai.nvidia_base_url)
    if os.getenv("GEMINI_API_KEY"):
        settings.ai.gemini_api_key = os.getenv("GEMINI_API_KEY")
    if os.getenv("ANTHROPIC_API_KEY"):
        settings.ai.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    if os.getenv("SARVAM_API_KEY"):
        settings.voice.sarvam_api_key = os.getenv("SARVAM_API_KEY")
    if os.getenv("VACHANA_API_KEY"):
        settings.voice.vachana_api_key = os.getenv("VACHANA_API_KEY")
    if os.getenv("VACHANA_TTS_VOICE"):
        settings.voice.vachana_tts_voice = os.getenv("VACHANA_TTS_VOICE")
    if os.getenv("VACHANA_TTS_MODEL"):
        settings.voice.vachana_tts_model = os.getenv("VACHANA_TTS_MODEL")
    if os.getenv("FALCON_TTS_PROVIDER"):
        settings.voice.tts_provider = os.getenv("FALCON_TTS_PROVIDER")
    if os.getenv("FALCON_STT_PROVIDER"):
        settings.voice.stt_provider = os.getenv("FALCON_STT_PROVIDER")
    if os.getenv("FALCON_VOICE_LANG"):
        settings.voice.stt_language = os.getenv("FALCON_VOICE_LANG")
    if os.getenv("FALCON_LOG_LEVEL"):
        settings.log_level = os.getenv("FALCON_LOG_LEVEL", settings.log_level)
    if os.getenv("FALCON_VOICE_ENABLED"):
        settings.voice.enabled = os.getenv("FALCON_VOICE_ENABLED", "true").lower() in ("1", "true", "yes")

    # Create data and log directories if needed
    try:
        Path(settings.base_data_dir).mkdir(parents=True, exist_ok=True)
        if settings.log_dir:
            Path(settings.log_dir).mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    return settings
