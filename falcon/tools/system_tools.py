"""
System Inspection and Diagnostics Tools for Falcon.
Retrieves CPU, RAM, disk, battery status, and handles screenshots on Windows 11.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import datetime
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional
from falcon.security.policy import PermissionLevel
from falcon.tools.registry import BaseTool


class GetSystemInfoTool(BaseTool):
    name = "get_system_info"
    description = "Retrieve current Windows 11 system performance metrics, CPU usage, RAM, and disk space."
    permission_level = PermissionLevel.READ_ONLY
    parameters_schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    async def execute(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "os": f"{platform.system()} {platform.release()} ({platform.version()})",
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "timestamp": datetime.datetime.now().isoformat(),
        }

        # Disk usage of system drive
        try:
            total, used, free = shutil.disk_usage("C:\\" if os.name == "nt" else "/")
            info["disk_c"] = {
                "total_gb": round(total / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "percent_used": round((used / total) * 100, 1),
            }
        except Exception:
            pass

        # Use psutil if available
        try:
            import psutil  # type: ignore
            info["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            info["cpu_count"] = psutil.cpu_count(logical=True)
            mem = psutil.virtual_memory()
            info["ram"] = {
                "total_gb": round(mem.total / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "percent_used": mem.percent,
            }
            battery = psutil.sensors_battery()
            if battery:
                info["battery"] = {
                    "percent": battery.percent,
                    "power_plugged": battery.power_plugged,
                }
            return info
        except ImportError:
            pass

        # Windows PowerShell fallback for RAM & CPU if psutil is not yet installed
        if os.name == "nt":
            try:
                ps_script = (
                    "$os = Get-CimInstance Win32_OperatingSystem; "
                    "$totalRam = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2); "
                    "$freeRam = [math]::Round($os.FreePhysicalMemory / 1MB, 2); "
                    "$cpu = (Get-CimInstance Win32_Processor).LoadPercentage; "
                    "Write-Output \"$totalRam,$freeRam,$cpu\""
                )
                output = subprocess.check_output(
                    ["powershell", "-NoProfile", "-Command", ps_script],
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).strip()
                parts = output.split(",")
                if len(parts) >= 3:
                    t_ram = float(parts[0])
                    f_ram = float(parts[1])
                    u_ram = round(t_ram - f_ram, 2)
                    info["ram"] = {
                        "total_gb": t_ram,
                        "used_gb": u_ram,
                        "free_gb": f_ram,
                        "percent_used": round((u_ram / t_ram) * 100, 1) if t_ram else 0,
                    }
                    if parts[2]:
                        info["cpu_percent"] = float(parts[2])
            except Exception:
                pass

        return info


class TakeScreenshotTool(BaseTool):
    name = "take_screenshot"
    description = "Capture a desktop screenshot and save it to the user's pictures or screenshots folder."
    permission_level = PermissionLevel.LOW_RISK
    parameters_schema = {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Optional custom filename for the screenshot (e.g. 'falcon_screen.png').",
            },
        },
        "required": [],
    }

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir) if output_dir else Path.home() / "Pictures" / "FalconScreenshots"

    async def execute(self, filename: Optional[str] = None) -> Dict[str, Any]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        target_name = filename or f"screenshot_{timestamp}.png"
        if not target_name.endswith(".png"):
            target_name += ".png"
        target_file = self.output_dir / target_name

        # Try PIL / Pillow if available
        try:
            from PIL import ImageGrab  # type: ignore
            im = ImageGrab.grab()
            im.save(str(target_file))
            return {
                "file_path": str(target_file),
                "resolution": f"{im.width}x{im.height}",
                "status": "captured",
            }
        except ImportError:
            pass

        # Windows PowerShell / .NET fallback
        if os.name == "nt":
            try:
                ps_cmd = (
                    "Add-Type -AssemblyName System.Windows.Forms; "
                    "Add-Type -AssemblyName System.Drawing; "
                    "$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
                    "$bitmap = New-Object System.Drawing.Bitmap $screen.Width, $screen.Height; "
                    "$graphics = [System.Drawing.Graphics]::FromImage($bitmap); "
                    "$graphics.CopyFromScreen($screen.X, $screen.Y, 0, 0, $screen.Size); "
                    f"$bitmap.Save('{str(target_file)}', [System.Drawing.Imaging.ImageFormat]::Png); "
                    "$graphics.Dispose(); $bitmap.Dispose();"
                )
                subprocess.check_call(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    stderr=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                )
                return {
                    "file_path": str(target_file),
                    "status": "captured",
                }
            except Exception as e:
                raise RuntimeError(f"Screenshot capture failed: {e}") from e

        raise RuntimeError("Pillow is required for screenshot capture on non-Windows environments.")


class ManageStartupTool(BaseTool):
    """Enable, disable, or inspect Windows Startup activation for Falcon."""

    name = "manage_startup"
    description = "Enable, disable, or query Windows 11 Startup auto-run for Falcon Assistant."
    permission_level = PermissionLevel.LOW_RISK
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["enable", "disable", "status"],
                "description": "Action to perform on Windows Startup ('enable', 'disable', 'status').",
            },
        },
        "required": ["action"],
    }

    async def execute(self, action: str) -> Dict[str, Any]:
        from falcon.system.startup import (
            disable_startup,
            enable_startup,
            get_startup_status,
            is_startup_enabled,
        )

        act = action.strip().lower()
        if act in ("enable", "activate", "on"):
            success = enable_startup()
            return {
                "success": success,
                "action": "enable",
                "is_enabled": is_startup_enabled(),
                "message": "Falcon has been configured to launch automatically on Windows Startup." if success else "Failed to enable Windows Startup."
            }
        elif act in ("disable", "deactivate", "off"):
            success = disable_startup()
            return {
                "success": success,
                "action": "disable",
                "is_enabled": is_startup_enabled(),
                "message": "Falcon has been removed from Windows Startup." if success else "Failed to disable Windows Startup."
            }
        elif act in ("status", "check", "query"):
            return get_startup_status()
        else:
            raise ValueError(f"Unknown action '{action}'. Supported actions are: 'enable', 'disable', 'status'.")
