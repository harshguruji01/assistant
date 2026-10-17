"""
Job Definitions and Recurrence Models for Falcon Scheduler.
Handles timers, reminders, alarms, and recurring scheduling models.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class JobType(str, Enum):
    """Types of scheduled background jobs."""
    REMINDER = "reminder"
    TIMER = "timer"
    ALARM = "alarm"
    RECURRING = "recurring"
    HOURLY_CHIME = "hourly_chime"


@dataclass
class ScheduledJob:
    """Represents a scheduled item in the Falcon engine."""
    id: str = field(default_factory=lambda: f"job_{uuid.uuid4().hex[:8]}")
    name: str = ""
    job_type: JobType = JobType.REMINDER
    scheduled_time: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    payload: Dict[str, Any] = field(default_factory=dict)
    is_recurring: bool = False
    recurrence_interval_seconds: Optional[int] = None
    status: str = "PENDING"  # PENDING, COMPLETED, CANCELLED

    def is_due(self, now: Optional[datetime.datetime] = None) -> bool:
        """Check if job scheduled time has arrived or passed."""
        current = now or datetime.datetime.now(datetime.timezone.utc)
        # Ensure timezone compatibility
        if self.scheduled_time.tzinfo is None:
            comp_sched = self.scheduled_time.replace(tzinfo=datetime.timezone.utc)
        else:
            comp_sched = self.scheduled_time
        return current >= comp_sched

    def advance_recurrence(self) -> None:
        """Calculate next execution time for recurring job."""
        if self.is_recurring and self.recurrence_interval_seconds:
            self.scheduled_time += datetime.timedelta(seconds=self.recurrence_interval_seconds)
            self.status = "PENDING"
        else:
            self.status = "COMPLETED"

    def to_db_row(self) -> tuple:
        return (
            self.id,
            self.name,
            self.job_type.value,
            self.scheduled_time.isoformat(),
            json.dumps(self.payload),
            1 if self.is_recurring else 0,
            self.recurrence_interval_seconds,
            self.status,
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> ScheduledJob:
        sched_time = datetime.datetime.fromisoformat(row["scheduled_time"])
        try:
            payload = json.loads(row["payload_json"])
        except Exception:
            payload = {}
        return cls(
            id=row["id"],
            name=row["name"],
            job_type=JobType(row["job_type"]),
            scheduled_time=sched_time,
            payload=payload,
            is_recurring=bool(row["is_recurring"]),
            recurrence_interval_seconds=row["recurrence_interval_seconds"],
            status=row["status"],
        )
