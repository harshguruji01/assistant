"""
Validation and Sanitization Utilities for Falcon.
Guards against path traversal, command injection, and malicious input.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional, Sequence


class SecurityValidationError(Exception):
    """Raised when an operation violates security constraints."""
    pass


# System directories that must NEVER be modified or deleted by Falcon
CRITICAL_SYSTEM_DIRS: List[Path] = [
    Path(os.environ.get("SystemRoot", r"C:\Windows")).resolve(),
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")).resolve(),
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")).resolve(),
]

# Patterns suspicious of prompt injection in untrusted text
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?(above|system\s+prompt)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
    re.compile(r"jailbreak|dan\s+mode|bypass\s+safety", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+must", re.IGNORECASE),
]


class InputValidator:
    """Validates paths, inputs, and commands."""

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize a filename to prevent invalid characters and directory traversal."""
        # Strip path separators
        cleaned = re.sub(r'[\\/*?:"<>|]', "", filename)
        cleaned = cleaned.strip(". ")
        if not cleaned:
            return "unnamed_file"
        return cleaned

    @staticmethod
    def validate_path_safety(
        target_path: str | Path,
        allowed_roots: Optional[Sequence[str | Path]] = None,
        allow_read_only_system: bool = True,
        is_write_operation: bool = False,
    ) -> Path:
        """
        Validate that the target path does not escape permitted boundaries or touch critical system files.
        Raises SecurityValidationError if validation fails.
        """
        try:
            resolved = Path(target_path).expanduser().resolve()
        except Exception as e:
            raise SecurityValidationError(f"Invalid path syntax '{target_path}': {e}") from e

        # Check critical system directories for write operations
        if is_write_operation:
            for sys_dir in CRITICAL_SYSTEM_DIRS:
                if resolved == sys_dir or sys_dir in resolved.parents:
                    raise SecurityValidationError(
                        f"Write access to system directory '{resolved}' is strictly prohibited."
                    )

        # If explicit allowed roots are provided, path must be inside one of them
        if allowed_roots:
            resolved_roots = [Path(root).expanduser().resolve() for root in allowed_roots]
            is_inside = any(resolved == root or root in resolved.parents for root in resolved_roots)
            if not is_inside:
                raise SecurityValidationError(
                    f"Path '{resolved}' is outside allowed directories: {[str(r) for r in resolved_roots]}"
                )

        return resolved

    @staticmethod
    def detect_prompt_injection(content: str) -> tuple[bool, Optional[str]]:
        """
        Scans external untrusted documents or web content for prompt injection cues.
        Returns (is_suspicious, matched_reason).
        """
        if not content:
            return False, None
        for pattern in PROMPT_INJECTION_PATTERNS:
            match = pattern.search(content)
            if match:
                return True, f"Matched injection pattern: '{match.group(0)}'"
        return False, None

    @staticmethod
    def sanitize_command_args(args: Sequence[str]) -> List[str]:
        """Ensure command arguments do not contain null bytes or control exploits."""
        sanitized = []
        for arg in args:
            if "\x00" in arg:
                raise SecurityValidationError("Null byte detected in command argument.")
            sanitized.append(str(arg))
        return sanitized
