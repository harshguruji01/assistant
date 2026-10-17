"""
Task and Workflow State Definitions for Falcon.
Defines execution states, task steps, dependency graphs, and plan models.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskState(str, Enum):
    """Finite-state workflow model."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class TaskStep:
    """A discrete executable unit within a task plan."""
    step_id: str = field(default_factory=lambda: f"step_{uuid.uuid4().hex[:6]}")
    title: str = ""
    tool_name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)  # list of step_ids that must finish before this
    status: TaskState = TaskState.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class TaskPlan:
    """An orchestrated multi-step workflow."""
    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    title: str = ""
    description: str = ""
    steps: List[TaskStep] = field(default_factory=list)
    state: TaskState = TaskState.PENDING
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

    def get_progress_percentage(self) -> float:
        """Calculate completion percentage."""
        if not self.steps:
            return 100.0 if self.state == TaskState.COMPLETED else 0.0
        finished = sum(1 for s in self.steps if s.status in (TaskState.COMPLETED, TaskState.CANCELLED))
        return round((finished / len(self.steps)) * 100, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "state": self.state.value,
            "progress_percent": self.get_progress_percentage(),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
            "steps": [s.to_dict() for s in self.steps],
        }
