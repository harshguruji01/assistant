"""
Unit tests for persistent scheduler and reminders.
"""

import asyncio
import tempfile
import unittest
from pathlib import Path
from falcon.core.event_bus import EventBus
from falcon.memory.database import DatabaseManager
from falcon.scheduler.jobs import JobType, ScheduledJob
from falcon.scheduler.scheduler import FalconScheduler


class TestScheduler(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_sched.db"
        self.db_manager = DatabaseManager(self.db_path)
        self.event_bus = EventBus()
        self.scheduler = FalconScheduler(self.db_manager, self.event_bus, tick_interval=0.1)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_schedule_and_trigger_reminder(self):
        triggered_events = []

        async def _test():
            self.event_bus.subscribe("scheduler.job_triggered", lambda e: triggered_events.append(e.data))
            await self.scheduler.start()

            # Schedule a reminder due in 0.1s
            job_id = self.scheduler.schedule_reminder("Take a break", delay_seconds=0.1, name="BreakAlert")
            self.assertTrue(job_id.startswith("job_"))

            # Wait for execution tick
            await asyncio.sleep(0.4)
            await self.scheduler.stop()

        asyncio.run(_test())
        self.assertEqual(len(triggered_events), 1)
        self.assertEqual(triggered_events[0]["name"], "BreakAlert")

    def test_job_persistence_recovery(self):
        # Add a job directly
        import datetime
        future_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
        job = ScheduledJob(
            id="job_persist_1",
            name="Meeting",
            job_type=JobType.REMINDER,
            scheduled_time=future_time,
            payload={"msg": "Daily standup"},
        )
        self.scheduler.add_job(job)

        # Create a new scheduler instance on the same database
        new_scheduler = FalconScheduler(self.db_manager, self.event_bus, tick_interval=1.0)
        async def _check():
            await new_scheduler.start()
            jobs = new_scheduler.list_jobs()
            await new_scheduler.stop()
            return jobs

        restored_jobs = asyncio.run(_check())
        self.assertEqual(len(restored_jobs), 1)
        self.assertEqual(restored_jobs[0]["id"], "job_persist_1")
        self.assertEqual(restored_jobs[0]["name"], "Meeting")


if __name__ == "__main__":
    unittest.main()
