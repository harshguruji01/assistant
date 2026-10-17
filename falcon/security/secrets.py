"""
Security and Secrets Management for Falcon.
Handles sensitive credential retrieval and automatic redaction of secrets in logs and events.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import logging
import os
import re
from typing import Dict, List, Optional, Pattern

# Common API Key and Secret Patterns
DEFAULT_SECRET_PATTERNS: List[Pattern[str]] = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),          # OpenAI / generic secret keys
    re.compile(r"sk_[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),         # Sarvam AI / underscore secret keys
    re.compile(r"vach_[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),       # Gnani / Vachana AI keys
    re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),      # Anthropic keys
    re.compile(r"AIzaSy[a-zA-Z0-9_-]{25,40}", re.IGNORECASE),     # Google Cloud / Gemini keys
    re.compile(r"nvapi-[a-zA-Z0-9_\-]{30,}", re.IGNORECASE),      # NVIDIA NIM API keys
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{15,}", re.IGNORECASE), # Bearer tokens
    re.compile(r"(api[_-]?key|secret[_-]?key|access[_-]?token|password)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?", re.IGNORECASE),
]


class SecretRedactor:
    """Utility class to sanitize strings and objects, stripping confidential keys."""

    def __init__(self, additional_patterns: Optional[List[Pattern[str]]] = None):
        self._patterns = list(DEFAULT_SECRET_PATTERNS)
        if additional_patterns:
            self._patterns.extend(additional_patterns)

    def redact(self, text: str) -> str:
        """Replace detected secrets with [REDACTED]."""
        if not text or not isinstance(text, str):
            return text
        sanitized = text
        for pattern in self._patterns:
            sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
        return sanitized


class RedactingLoggingFormatter(logging.Formatter):
    """Logging formatter that intercepts log messages and redacts sensitive credentials."""

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.redactor = SecretRedactor()

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return self.redactor.redact(original)


class SecretManager:
    """Manages credentials securely via environment variables and runtime settings."""

    @staticmethod
    def get_secret(key_name: str, default: Optional[str] = None) -> Optional[str]:
        """Fetch secret from environment variables."""
        return os.environ.get(key_name, default)

    @staticmethod
    def set_secret(key_name: str, value: str) -> None:
        """Set secret in the current process environment."""
        os.environ[key_name] = value

    @staticmethod
    def mask_secret(value: Optional[str]) -> str:
        """Provide a masked view of a secret (e.g. sk-proj...1234) for safe UI display."""
        if not value:
            return "<Not Set>"
        if len(value) <= 8:
            return "********"
        return f"{value[:4]}...{value[-4:]}"
