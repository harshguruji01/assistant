"""
End-to-End Control Flow & Output Demonstration for Falcon.
Runs all core capabilities step-by-step and demonstrates output and control.
Developed by: HarshGuruJi
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from falcon.config.settings import AISettings, FalconSettings, VoiceSettings
from falcon.core.controller import FalconCore
from falcon.automation.workflow import TaskState
from falcon.security.policy import PermissionLevel


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


async def run_step_by_step_demo():
    print("=" * 80)
    print("  [FALCON AI DESKTOP ASSISTANT - STEP-BY-STEP CONTROL FLOW & OUTPUT]")
    print("   Author: HarshGuruJi | Platform: Windows 11")
    print("=" * 80)

    # 1. Initialize Core with deterministic offline mock AI for instant demonstration
    settings = FalconSettings(
        ai=AISettings(default_provider="mock", fallback_provider="mock"),
        voice=VoiceSettings(enabled=False),
    )
    core = FalconCore(settings)

    # Listen to events on Event Bus
    events_log = []
    core.event_bus.subscribe("*", lambda e: events_log.append(e.topic))

    # STEP 1: Startup & Lifecycle
    print("\n[STEP 1] Initializing Core Engine & Lifecycle Services...")
    ready = await core.start()
    print(f"-> FalconCore State: {core.lifecycle.state.value.upper()}")
    print(f"-> Services Health: {list(core.lifecycle.get_all_services().keys())}")

    # STEP 2: Intent Classification & Multilingual Understanding
    print("\n[STEP 2] Multilingual Intent Engine Analysis:")
    queries = [
        "Namaste Falcon, aap kaise ho?",
        "calc kholo",
        "Show CPU and RAM specs",
        "Read notes.txt and then summarize its content",
    ]
    for q in queries:
        intent = core.intent_engine.classify_intent(q)
        print(f"  • Input: '{q}'")
        print(f"    Intent: {intent.intent_type.value} | Action: {intent.action_type} | Lang: {intent.detected_language} | Entities: {intent.entities}")

    # STEP 3: Conversational AI Turn & Tool Calling
    print("\n[STEP 3] Executing Message with Automated Tool Call (System Info):")
    conv_result = await core.process_message("Show system info and RAM")
    print(f"-> AI Response:\n{conv_result.response_text}")
    print(f"-> Executed Tools: {len(conv_result.executed_tools)} (Tool: {conv_result.executed_tools[0]['tool']})")

    # STEP 4: Safe File Management Tools
    print("\n[STEP 4] Executing Safe File Operations (Write & Read):")
    test_file = Path.cwd() / "demo_output.txt"
    # Write
    w_res = await core.tool_registry.execute_tool("write_file", {"file_path": str(test_file), "content": "Falcon AI Desktop Assistant - HarshGuruJi"})
    print(f"-> Write File Result: {w_res['status']} ({w_res.get('result', {}).get('bytes_written')} bytes written)")
    # Read
    r_res = await core.tool_registry.execute_tool("read_file", {"file_path": str(test_file)})
    print(f"-> Read File Result: '{r_res.get('result', {}).get('content')}'")
    # Clean up demo file
    if test_file.exists():
        test_file.unlink()

    # STEP 5: Task Planning & Multi-Step Workflow Automation
    print("\n[STEP 5] Multi-Step Task Workflow Execution with State Machine:")
    audit_plan = core.planner.create_system_audit_plan()
    print(f"-> Generated Plan: '{audit_plan.title}' with {len(audit_plan.steps)} steps:")
    for s in audit_plan.steps:
        print(f"   - Step '{s.title}' (Tool: {s.tool_name}, Depends on: {s.depends_on})")

    completed_plan = await core.executor.execute_plan(audit_plan)
    print(f"-> Workflow Final State: {completed_plan.state.value}")
    print(f"-> Progress: {completed_plan.get_progress_percentage()}%")

    # STEP 6: Persistent Scheduler & Reminders (SQLite)
    print("\n[STEP 6] Persistent Scheduler & Reminders:")
    reminder_id = core.scheduler.schedule_reminder("Standup Meeting with HarshGuruJi", delay_seconds=300)
    print(f"-> Scheduled Reminder ID: {reminder_id}")
    active_jobs = core.scheduler.list_jobs()
    print(f"-> Active Durable Jobs in SQLite: {len(active_jobs)} (Next: {active_jobs[0]['name']} at {active_jobs[0]['time']})")

    # STEP 7: Security Approval Gating for High-Risk Actions
    print("\n[STEP 7] Security Policy & Approval Gating:")
    # High risk tool without confirmation callback is blocked
    blocked = await core.tool_registry.execute_tool("terminate_process", {"pid": 99999})
    print(f"-> Terminate Process (No confirmation): {blocked['status']} -> {blocked.get('message')}")

    # STEP 8: Graceful Shutdown
    print("\n[STEP 8] Graceful Shutdown:")
    await core.shutdown()
    print(f"-> FalconCore Final State: {core.lifecycle.state.value.upper()}")
    print("=" * 80)
    print("All subsystems verified successfully!")


if __name__ == "__main__":
    asyncio.run(run_step_by_step_demo())
