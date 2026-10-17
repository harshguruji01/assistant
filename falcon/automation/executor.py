"""
Task and Workflow Execution Engine for Falcon.
Handles dependency resolution, cancellation, timeouts, bounded retries, and event streaming.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any, Dict, List, Optional
from falcon.automation.workflow import TaskPlan, TaskState, TaskStep
from falcon.core.event_bus import Event, EventBus, EventNames
from falcon.tools.registry import ToolRegistry

logger = logging.getLogger("Falcon.Executor")


class WorkflowExecutor:
    """Orchestrates safe execution of multi-step plans with state machines and cancellation."""

    def __init__(self, tool_registry: ToolRegistry, event_bus: EventBus):
        self.tool_registry = tool_registry
        self.event_bus = event_bus
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._cancellation_events: Dict[str, asyncio.Event] = {}
        self._task_history: List[TaskPlan] = []

    def get_task_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return serialized list of past executed plans."""
        return [t.to_dict() for t in self._task_history[-limit:]]

    def cancel_task(self, task_id: str) -> bool:
        """Signal cancellation for an active workflow."""
        if task_id in self._cancellation_events:
            logger.info(f"Cancellation requested for task '{task_id}'")
            self._cancellation_events[task_id].set()
            if task_id in self._active_tasks:
                self._active_tasks[task_id].cancel()
            return True
        return False

    async def execute_plan(self, plan: TaskPlan, timeout_seconds: float = 60.0) -> TaskPlan:
        """Run a task plan through completion or cancellation."""
        plan.state = TaskState.RUNNING
        cancel_event = asyncio.Event()
        self._cancellation_events[plan.task_id] = cancel_event

        # Emit task created event
        await self.event_bus.publish(
            Event(
                topic=EventNames.TASK_CREATED,
                data={"task_id": plan.task_id, "title": plan.title, "total_steps": len(plan.steps)},
                correlation_id=plan.task_id,
            )
        )

        completed_step_ids: set[str] = set()

        try:
            for index, step in enumerate(plan.steps):
                # Check for cancellation
                if cancel_event.is_set():
                    plan.state = TaskState.CANCELLED
                    break

                # Verify dependencies
                missing_deps = [dep for dep in step.depends_on if dep not in completed_step_ids]
                if missing_deps:
                    step.status = TaskState.FAILED
                    step.error = f"Step dependency failed: missing {missing_deps}"
                    plan.state = TaskState.FAILED
                    plan.error_message = step.error
                    break

                # Execute step with retries
                step.status = TaskState.RUNNING
                step.started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

                await self.event_bus.publish(
                    Event(
                        topic=EventNames.TASK_PROGRESS,
                        data={
                            "task_id": plan.task_id,
                            "step_id": step.step_id,
                            "step_title": step.title,
                            "step_index": index + 1,
                            "total_steps": len(plan.steps),
                            "progress_percent": plan.get_progress_percentage(),
                        },
                        correlation_id=plan.task_id,
                    )
                )

                step_succeeded = False
                for attempt in range(step.max_retries + 1):
                    if cancel_event.is_set():
                        break
                    try:
                        logger.info(f"Executing step '{step.title}' (attempt {attempt + 1}/{step.max_retries + 1})")
                        exec_result = await asyncio.wait_for(
                            self.tool_registry.execute_tool(step.tool_name, step.arguments),
                            timeout=timeout_seconds,
                        )

                        if exec_result.get("status") == "success":
                            step.status = TaskState.COMPLETED
                            step.result = exec_result.get("result")
                            step.completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
                            completed_step_ids.add(step.step_id)
                            step_succeeded = True
                            break
                        elif exec_result.get("status") == "blocked":
                            step.status = TaskState.WAITING_FOR_APPROVAL
                            step.error = exec_result.get("message")
                            plan.state = TaskState.WAITING_FOR_APPROVAL
                            return plan
                        else:
                            step.error = exec_result.get("error", "Execution failed")
                            step.retry_count = attempt + 1
                    except asyncio.TimeoutError:
                        step.error = f"Step execution timed out after {timeout_seconds}s"
                        step.retry_count = attempt + 1
                    except Exception as e:
                        step.error = str(e)
                        step.retry_count = attempt + 1

                if not step_succeeded:
                    step.status = TaskState.FAILED
                    plan.state = TaskState.FAILED
                    plan.error_message = step.error
                    break

            if plan.state == TaskState.RUNNING:
                plan.state = TaskState.COMPLETED
                plan.completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
                await self.event_bus.publish(
                    Event(
                        topic=EventNames.TASK_COMPLETED,
                        data={"task_id": plan.task_id, "title": plan.title, "results": plan.to_dict()},
                        correlation_id=plan.task_id,
                    )
                )

        except asyncio.CancelledError:
            plan.state = TaskState.CANCELLED
            await self.event_bus.publish(
                Event(
                    topic=EventNames.TASK_CANCELLED,
                    data={"task_id": plan.task_id},
                    correlation_id=plan.task_id,
                )
            )
        finally:
            self._cancellation_events.pop(plan.task_id, None)
            self._active_tasks.pop(plan.task_id, None)
            self._task_history.append(plan)

        if plan.state == TaskState.FAILED:
            await self.event_bus.publish(
                Event(
                    topic=EventNames.TASK_FAILED,
                    data={"task_id": plan.task_id, "error": plan.error_message},
                    correlation_id=plan.task_id,
                )
            )

        return plan
