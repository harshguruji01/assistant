"""
Application and Process Management Tools for Falcon.
Handles launching approved applications, window queries, and safe process inspection.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List, Optional
from falcon.security.policy import PermissionLevel, SecurityPolicy
from falcon.security.validation import SecurityValidationError
from falcon.tools.registry import BaseTool


class LaunchApplicationTool(BaseTool):
    name = "launch_application"
    description = "Launch a verified Windows desktop application (e.g. 'notepad', 'calc', 'explorer', 'chrome')."
    permission_level = PermissionLevel.LOW_RISK
    parameters_schema = {
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Name or executable of the application to open (e.g. 'notepad', 'calc', 'mspaint').",
            },
            "arguments": {
                "type": "array",
                "description": "Optional command-line arguments to pass to the application.",
                "items": {"type": "string"},
            },
        },
        "required": ["app_name"],
    }

    def __init__(self, security_policy: SecurityPolicy):
        self.security_policy = security_policy

    async def execute(self, app_name: str, arguments: Optional[List[str]] = None) -> Dict[str, Any]:
        clean_name = app_name.strip()

        # Check against approved list
        if not self.security_policy.is_action_allowed(clean_name):
            raise SecurityValidationError(
                f"Application '{clean_name}' is not in the approved applications list. Action blocked."
            )

        # Standard Windows shortcuts mapping
        app_aliases = {
            "notepad": "notepad.exe",
            "calc": "calc.exe",
            "calculator": "calc.exe",
            "paint": "mspaint.exe",
            "explorer": "explorer.exe",
            "file explorer": "explorer.exe",
            "taskmgr": "taskmgr.exe",
            "task manager": "taskmgr.exe",
            "edge": "msedge.exe",
        }

        exe_target = app_aliases.get(clean_name.lower(), clean_name)
        cmd = [exe_target]
        if arguments:
            cmd.extend(arguments)

        # Launch process detached
        try:
            # We do NOT use shell=True to prevent injection
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS if os.name == "nt" else 0,
            )
            return {
                "app_name": clean_name,
                "executable": exe_target,
                "pid": proc.pid,
                "status": "launched",
            }
        except Exception as e:
            raise RuntimeError(f"Failed to launch application '{clean_name}': {e}") from e


class ListRunningProcessesTool(BaseTool):
    name = "list_running_applications"
    description = "List currently running interactive desktop applications and their window titles."
    permission_level = PermissionLevel.READ_ONLY
    parameters_schema = {
        "type": "object",
        "properties": {
            "max_results": {
                "type": "integer",
                "description": "Max applications to return (default 25).",
            },
        },
        "required": [],
    }

    async def execute(self, max_results: int = 25) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []

        # Try psutil if available
        try:
            import psutil  # type: ignore
            for p in psutil.process_iter(["pid", "name"]):
                try:
                    results.append({"pid": p.info["pid"], "name": p.info["name"]})
                    if len(results) >= max_results:
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return {"count": len(results), "applications": results, "engine": "psutil"}
        except ImportError:
            pass

        # Windows PowerShell fallback (retrieving processes with Main Windows)
        if os.name == "nt":
            try:
                cmd = [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    f"Get-Process | Where-Object {{ $_.MainWindowTitle }} | Select-Object -First {max_results} -Property Id, ProcessName, MainWindowTitle | ConvertTo-Json -Compress",
                ]
                output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
                import json
                parsed = json.loads(output)
                if isinstance(parsed, dict):
                    parsed = [parsed]
                for item in parsed:
                    results.append({
                        "pid": item.get("Id"),
                        "name": item.get("ProcessName"),
                        "title": item.get("MainWindowTitle"),
                    })
                return {"count": len(results), "applications": results, "engine": "powershell"}
            except Exception as e:
                return {"count": 0, "applications": [], "error": str(e)}

        return {"count": 0, "applications": [], "message": "Process listing unavailable on this platform."}


class TerminateProcessTool(BaseTool):
    name = "terminate_process"
    description = "Safely terminate a running application process by PID or Name. (Requires user confirmation)."
    permission_level = PermissionLevel.HIGH_RISK
    requires_confirmation = True
    parameters_schema = {
        "type": "object",
        "properties": {
            "pid": {
                "type": "integer",
                "description": "Process ID to terminate.",
            },
        },
        "required": ["pid"],
    }

    async def execute(self, pid: int) -> Dict[str, Any]:
        # Protect system PIDs (0, 4, etc.)
        if pid <= 4:
            raise SecurityValidationError(f"Cannot terminate protected system process PID {pid}.")

        try:
            import psutil  # type: ignore
            p = psutil.Process(pid)
            p_name = p.name()
            p.terminate()
            p.wait(timeout=3)
            return {"pid": pid, "name": p_name, "status": "terminated"}
        except ImportError:
            if os.name == "nt":
                subprocess.check_call(["taskkill", "/PID", str(pid), "/F"])
                return {"pid": pid, "status": "terminated"}
            raise RuntimeError("psutil is required on non-Windows platforms for process termination.")
