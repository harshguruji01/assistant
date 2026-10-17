"""
Main Application Entry Point for Falcon AI Desktop Assistant.
Developed by: HarshGuruJi
Platform: Windows 11
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from falcon import __app_name__, __author__, __version__
from falcon.config.settings import load_settings
from falcon.core.controller import FalconCore
from falcon.security.secrets import RedactingLoggingFormatter
from falcon.system.diagnostics import SystemDiagnostics

# Ensure Windows terminal outputs UTF-8 characters and emojis safely
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def configure_logging(level: str = "INFO", log_dir: Optional[str] = None) -> None:
    """Setup structured console and file logging with automatic secret redaction."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    formatter = RedactingLoggingFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler if directory exists
    if log_dir:
        try:
            log_path = Path(log_dir) / "falcon.log"
            file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception:
            pass


async def run_interactive_cli(core: FalconCore) -> None:
    """Interactive command-line interface for testing and interacting with Falcon."""
    print("=" * 70)
    print(f"  {__app_name__} (v{__version__})")
    print(f"  Engineered by: {__author__} | Platform: Windows 11")
    print("=" * 70)
    print("Type your message or command (or 'exit' / 'quit' to close):")
    print("-" * 70)

    # Subscribe to status changes or tool executions for live CLI updates
    core.event_bus.subscribe("task.*", lambda e: print(f"  [Workflow Event] {e.topic}: {e.data}"))

    session_id = "cli_session"
    while True:
        try:
            user_input = await asyncio.to_thread(input, "\nYou > ")
            cleaned = user_input.strip()
            if not cleaned:
                continue
            if cleaned.lower() in ("exit", "quit", "q"):
                print("\nShutting down Falcon...")
                break

            print("\nFalcon is thinking...")
            result = await core.process_message(cleaned, session_id=session_id)
            print(f"\nFalcon > {result.response_text}")

            if result.executed_tools:
                print(f"  (Tools executed: {len(result.executed_tools)}, Latency: {result.latency_seconds:.2f}s)")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting Falcon...")
            break
        except Exception as e:
            print(f"\n[Error] {e}")


async def async_main() -> None:
    parser = argparse.ArgumentParser(description=f"{__app_name__} by {__author__}")
    parser.add_argument("--diagnostics", "-d", action="store_true", help="Run system diagnostics and exit")
    parser.add_argument("--status", "-s", action="store_true", help="Display assistant health status and exit")
    parser.add_argument("--eval", "-e", type=str, help="Evaluate a single command or question and exit")
    parser.add_argument("--config", "-c", type=str, help="Path to custom configuration file")
    args = parser.parse_args()

    settings = load_settings(args.config)
    configure_logging(level=settings.log_level, log_dir=settings.log_dir)

    # 1. Run diagnostics if requested
    if args.diagnostics:
        diag = SystemDiagnostics(settings)
        report = diag.generate_support_report()
        print(json.dumps(report, indent=2))
        return

    # Initialize Core
    core = FalconCore(settings)
    started = await core.start()
    if not started:
        print("[CRITICAL] Failed to start Falcon Core services.", file=sys.stderr)
        sys.exit(1)

    try:
        if args.status:
            print(json.dumps(core.get_status(), indent=2))
        elif args.eval:
            result = await core.process_message(args.eval)
            print(result.response_text)
        else:
            await run_interactive_cli(core)
    finally:
        await core.shutdown()


def main() -> None:
    """Synchronous entry point."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
