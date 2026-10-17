"""
Security Policy and Permission Definitions for Falcon.
Controls authorization levels, user confirmation gates, and audit trails.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field


class PermissionLevel(str, Enum):
    """Execution risk categories for tools and tasks."""
    READ_ONLY = "read_only"       # Safe to read (system info, listing files, time)
    LOW_RISK = "low_risk"         # Minimal impact (open app, open browser url, create temp file)
    MEDIUM_RISK = "medium_risk"   # Notable impact (edit file, move file, create scheduled task)
    HIGH_RISK = "high_risk"       # Destructive / sensitive (delete file, terminate process, kill task)
    CRITICAL = "critical"         # System-level (shutdown computer, edit registry) - requires explicit confirmation


@dataclass
class AuditRecord:
    """Audit log entry capturing privileged actions."""
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    action_name: str = ""
    actor: str = "assistant"
    parameters: Dict[str, Any] = field(default_factory=dict)
    permission_level: PermissionLevel = PermissionLevel.READ_ONLY
    approved_by_user: bool = False
    status: str = "PENDING"  # PENDING, EXECUTED, BLOCKED, FAILED
    error_message: Optional[str] = None


class SecurityPolicy:
    """Manages permissions, approval policies, and action allowlists."""

    def __init__(
        self,
        require_approval_for_high_risk: bool = True,
        approved_apps: Optional[Set[str]] = None,
        blocked_commands: Optional[Set[str]] = None,
    ):
        self.require_approval_for_high_risk = require_approval_for_high_risk
        # Pre-approved standard Windows executables
        self.approved_apps: Set[str] = approved_apps or {
            "notepad.exe",
            "calc.exe",
            "explorer.exe",
            "mspaint.exe",
            "msedge.exe",
            "chrome.exe",
            "firefox.exe",
            "code.exe",
            "cmd.exe",
            "powershell.exe",
            "taskmgr.exe",
        }
        # Explicitly forbidden executables or destructive utilities
        self.blocked_commands: Set[str] = blocked_commands or {
            "format",
            "del /f /s /q c:\\",
            "rmdir /s /q c:\\",
            "diskpart",
            "vssadmin delete shadows",
        }
        self._audit_trail: List[AuditRecord] = []

    def is_action_allowed(self, app_name: str) -> bool:
        """Check if an application is in the pre-approved list or allowed executable."""
        clean = app_name.lower().strip()
        if not clean.endswith(".exe"):
            clean_exe = clean + ".exe"
        else:
            clean_exe = clean
        return clean_exe in self.approved_apps or clean in self.approved_apps

    def requires_user_confirmation(self, level: PermissionLevel) -> bool:
        """Determines if the permission tier requires interactive user confirmation."""
        if not self.require_approval_for_high_risk:
            return level == PermissionLevel.CRITICAL
        return level in (PermissionLevel.HIGH_RISK, PermissionLevel.CRITICAL)

    def log_audit(self, record: AuditRecord) -> None:
        """Append an action to the in-memory audit log."""
        self._audit_trail.append(record)

    def get_audit_trail(self, limit: int = 100) -> List[AuditRecord]:
        """Retrieve recent audit logs."""
        return self._audit_trail[-limit:]
