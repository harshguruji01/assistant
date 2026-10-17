"""
Persistent Task Scheduler for Falcon.
Coordinates timers, reminders, alarms, and recurring jobs with durable SQLite persistence.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional
from falcon.core.event_bus import Event, EventBus
from falcon.memory.database import DatabaseManager
from falcon.scheduler.jobs import JobType, ScheduledJob

logger = logging.getLogger("Falcon.Scheduler")


class FalconScheduler:
    """Centralized, reliable background scheduler."""

    def __init__(self, db_manager: DatabaseManager, event_bus: EventBus, tick_interval: float = 1.0):
        self.db = db_manager
        self.event_bus = event_bus
        self.tick_interval = tick_interval
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        self._jobs: Dict[str, ScheduledJob] = {}
        self._custom_handlers: Dict[JobType, Callable[[ScheduledJob], Coroutine[Any, Any, None]]] = {}

    def register_handler(self, job_type: JobType, handler: Callable[[ScheduledJob], Coroutine[Any, Any, None]]) -> None:
        """Register custom execution logic for specific job types."""
        self._custom_handlers[job_type] = handler

    async def start(self) -> None:
        """Load pending jobs from database and start the scheduler tick loop."""
        self._load_pending_jobs()
        self._running = True
        self._loop_task = asyncio.create_task(self._run_loop(), name="FalconSchedulerLoop")
        logger.info(f"Falcon Scheduler started with {len(self._jobs)} restored job(s).")

    async def stop(self) -> None:
        """Stop scheduler loop cleanly."""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        logger.info("Falcon Scheduler stopped.")

    def _load_pending_jobs(self) -> None:
        """Restore all pending jobs from database."""
        rows = self.db.execute_query(
            "SELECT * FROM scheduled_jobs WHERE status = 'PENDING'"
        )
        for r in rows:
            try:
                job = ScheduledJob.from_db_row(r)
                self._jobs[job.id] = job
            except Exception as e:
                logger.error(f"Failed to restore scheduled job {r.get('id')}: {e}")

    def add_job(self, job: ScheduledJob) -> str:
        """Persist and queue a new scheduled job."""
        self._jobs[job.id] = job
        with self.db.transaction() as cur:
            cur.execute(
                """
                INSERT OR REPLACE INTO scheduled_jobs
                (id, name, job_type, scheduled_time, payload_json, is_recurring, recurrence_interval_seconds, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                job.to_db_row(),
            )
        logger.info(f"Scheduled job added: '{job.name}' ({job.job_type.value}) for {job.scheduled_time.isoformat()}")
        return job.id

    def schedule_reminder(self, text: str, delay_seconds: float, name: str = "Reminder") -> str:
        """Convenience method to set a reminder after a number of seconds."""
        run_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=delay_seconds)
        job = ScheduledJob(
            name=name,
            job_type=JobType.REMINDER,
            scheduled_time=run_at,
            payload={"message": text},
        )
        return self.add_job(job)

    def schedule_hourly_chime(self) -> str:
        """Schedule the next top-of-the-hour announcement."""
        now = datetime.datetime.now()
        next_hour = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        utc_target = next_hour.astimezone(datetime.timezone.utc)
        job = ScheduledJob(
            name="Hourly Chime",
            job_type=JobType.HOURLY_CHIME,
            scheduled_time=utc_target,
            payload={"hour": next_hour.hour},
            is_recurring=True,
            recurrence_interval_seconds=3600,
        )
        return self.add_job(job)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending job."""
        if job_id in self._jobs:
            self._jobs[job_id].status = "CANCELLED"
            del self._jobs[job_id]
            with self.db.transaction() as cur:
                cur.execute("UPDATE scheduled_jobs SET status = 'CANCELLED' WHERE id = ?", (job_id,))
            logger.info(f"Cancelled scheduled job: '{job_id}'")
            return True
        return False

    def list_jobs(self) -> List[Dict[str, Any]]:
        """Return list of all active jobs in memory."""
        return [
            {
                "id": j.id,
                "name": j.name,
                "type": j.job_type.value,
                "time": j.scheduled_time.isoformat(),
                "payload": j.payload,
                "recurring": j.is_recurring,
            }
            for j in self._jobs.values()
        ]

    async def _run_loop(self) -> None:
        """Periodic background evaluation of due jobs."""
        while self._running:
            try:
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                due_jobs = [j for j in list(self._jobs.values()) if j.is_due(now_utc)]

                for job in due_jobs:
                    await self._trigger_job(job)

                await asyncio.sleep(self.tick_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler tick loop: {e}", exc_info=True)
                await asyncio.sleep(self.tick_interval)

    async def _trigger_job(self, job: ScheduledJob) -> None:
        """Execute the job action, update database status, and publish event."""
        logger.info(f"Triggering scheduled job: '{job.name}' ({job.id})")

        # Publish notification event
        await self.event_bus.publish(
            Event(
                topic="scheduler.job_triggered",
                data={
                    "job_id": job.id,
                    "name": job.name,
                    "type": job.job_type.value,
                    "payload": job.payload,
                },
                correlation_id=job.id,
            )
        )

        # Call custom handler if registered
        if job.job_type in self._custom_handlers:
            try:
                await self._custom_handlers[job.job_type](job)
            except Exception as e:
                logger.error(f"Error executing custom handler for job '{job.id}': {e}")

        # Advance or complete job
        if job.is_recurring:
            job.advance_recurrence()
            with self.db.transaction() as cur:
                cur.execute(
                    "UPDATE scheduled_jobs SET scheduled_time = ?, status = 'PENDING' WHERE id = ?",
                    (job.scheduled_time.isoformat(), job.id),
                )
        else:
            job.status = "COMPLETED"
            self._jobs.pop(job.id, None)
            with self.db.transaction() as cur:
                cur.execute("UPDATE scheduled_jobs SET status = 'COMPLETED' WHERE id = ?", (job.id,))
