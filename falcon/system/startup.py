"""
Windows Startup Manager for Falcon AI Assistant.
Manages automatic startup on Windows boot via HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("Falcon.Startup")

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
DEFAULT_APP_NAME = "FalconAssistant"


def get_default_launch_command() -> str:
    """Generate the Windows command line to launch Falcon in the background on startup."""
    python_exe = sys.executable
    # Locate main.py or falcon launch module
    cwd = Path(__file__).resolve().parent.parent.parent
    main_py = cwd / "main.py"
    if main_py.exists():
        # Use pythonw if available for silent background execution, or python with window
        pythonw = Path(python_exe).parent / "pythonw.exe"
        exe_to_use = str(pythonw) if pythonw.exists() else python_exe
        return f'"{exe_to_use}" "{main_py}"'
    return f'"{python_exe}" -m falcon.main'


def is_startup_enabled(app_name: str = DEFAULT_APP_NAME) -> bool:
    """Check if Falcon is currently registered in Windows Startup registry."""
    if os.name != "nt":
        return False

    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            try:
                val, _ = winreg.QueryValueEx(key, app_name)
                return bool(val)
            except FileNotFoundError:
                return False
    except Exception as e:
        logger.debug(f"Failed to read startup registry: {e}")
        return False


def enable_startup(app_name: str = DEFAULT_APP_NAME, command: Optional[str] = None) -> bool:
    """Register Falcon in Windows Startup registry for the current user."""
    if os.name != "nt":
        logger.warning("Startup registration is only supported on Windows.")
        return False

    cmd = command or get_default_launch_command()
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
            logger.info(f"Registered '{app_name}' to Windows Startup: {cmd}")
            return True
    except Exception as e:
        logger.error(f"Failed to enable Windows Startup: {e}")
        return False


def disable_startup(app_name: str = DEFAULT_APP_NAME) -> bool:
    """Remove Falcon from Windows Startup registry."""
    if os.name != "nt":
        return False

    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, app_name)
                logger.info(f"Removed '{app_name}' from Windows Startup.")
                return True
            except FileNotFoundError:
                return True
    except Exception as e:
        logger.error(f"Failed to disable Windows Startup: {e}")
        return False


def get_startup_status(app_name: str = DEFAULT_APP_NAME) -> dict:
    """Return structured startup status information."""
    enabled = is_startup_enabled(app_name)
    current_cmd = ""
    if enabled and os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
                current_cmd, _ = winreg.QueryValueEx(key, app_name)
        except Exception:
            pass

    return {
        "app_name": app_name,
        "is_enabled": enabled,
        "registry_path": f"HKCU\\{RUN_KEY_PATH}\\{app_name}",
        "command": current_cmd or get_default_launch_command(),
        "platform": "Windows 11",
    }
