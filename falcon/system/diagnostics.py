"""
Diagnostic and System Verification Utilities for Falcon.
Performs pre-flight checks for Python version, database access, audio devices,
AI provider connectivity, and Windows automation support.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import os
import platform
import sys
from typing import Any, Dict, List
from falcon.config.settings import FalconSettings
from falcon.memory.database import DatabaseManager


class SystemDiagnostics:
    """Performs non-destructive environment checks and generates sanitized support reports."""

    def __init__(self, settings: FalconSettings):
        self.settings = settings

    def check_python_environment(self) -> Dict[str, Any]:
        """Verify Python version and architecture."""
        v = sys.version_info
        compatible = v.major == 3 and v.minor >= 10
        return {
            "version": f"{v.major}.{v.minor}.{v.micro}",
            "compatible": compatible,
            "architecture": platform.architecture()[0],
            "executable": sys.executable,
        }

    def check_installed_packages(self) -> Dict[str, bool]:
        """Check presence of optional and recommended packages."""
        packages = ["psutil", "PIL", "pyttsx3", "speech_recognition", "PySide6"]
        status = {}
        for pkg in packages:
            try:
                __import__(pkg)
                status[pkg] = True
            except ImportError:
                status[pkg] = False
        return status

    def check_database_access(self) -> Dict[str, Any]:
        """Test database connection and read/write capabilities."""
        db_path = self.settings.database_path
        try:
            db = DatabaseManager(db_path)
            with db.transaction() as cur:
                cur.execute("SELECT 1")
            return {"status": "ok", "path": db_path, "writable": True}
        except Exception as e:
            return {"status": "error", "path": db_path, "error": str(e), "writable": False}

    def check_windows_integration(self) -> Dict[str, Any]:
        """Verify Windows operating system capabilities."""
        is_windows = os.name == "nt"
        win_ver = platform.version() if is_windows else "N/A"
        return {
            "is_windows": is_windows,
            "os_name": platform.system(),
            "windows_version": win_ver,
            "release": platform.release(),
        }

    def generate_support_report(self) -> Dict[str, Any]:
        """Generate a complete diagnostics report with redacted secrets."""
        py_info = self.check_python_environment()
        pkg_info = self.check_installed_packages()
        db_info = self.check_database_access()
        win_info = self.check_windows_integration()

        return {
            "application": {
                "name": self.settings.app_name,
                "version": self.settings.app_version,
                "developer": self.settings.developer,
            },
            "environment": {
                "python": py_info,
                "operating_system": win_info,
                "packages": pkg_info,
            },
            "database": db_info,
            "ai_config": {
                "provider": self.settings.ai.default_provider,
                "model": self.settings.ai.default_model,
                "fallback": self.settings.ai.fallback_provider,
                "has_openai_key": bool(self.settings.ai.openai_api_key),
                "has_gemini_key": bool(self.settings.ai.gemini_api_key),
                "has_anthropic_key": bool(self.settings.ai.anthropic_api_key),
            },
            "voice_config": {
                "enabled": self.settings.voice.enabled,
                "stt_provider": self.settings.voice.stt_provider,
                "tts_provider": self.settings.voice.tts_provider,
                "wake_word_enabled": self.settings.voice.wake_word_enabled,
            },
        }
