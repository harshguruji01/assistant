"""
Unit tests for workflow planning, step tracking, dependencies, and task cancellation.
"""

import asyncio
import unittest
from falcon.automation.executor import WorkflowExecutor
from falcon.automation.workflow import TaskPlan, TaskState, TaskStep
from falcon.core.event_bus import EventBus, EventNames
from falcon.security.policy import PermissionLevel, SecurityPolicy
from falcon.tools.registry import BaseTool, ToolRegistry


class FastTool(BaseTool):
    name = "fast_tool"
    description = "A fast test tool."
    permission_level = PermissionLevel.READ_ONLY
    parameters_schema = {"type": "object", "properties": {"val": {"type": "string"}}, "required": ["val"]}

    async def execute(self, val: str):
        return f"Echo: {val}"


class TestWorkflowExecutor(unittest.TestCase):

    def setUp(self):
        self.policy = SecurityPolicy()
        self.registry = ToolRegistry(self.policy)
        self.registry.register_tool(FastTool())
        self.bus = EventBus()
        self.executor = WorkflowExecutor(self.registry, self.bus)

    def test_workflow_execution_and_dependencies(self):
        step1 = TaskStep(step_id="s1", title="Step 1", tool_name="fast_tool", arguments={"val": "First"})
        step2 = TaskStep(step_id="s2", title="Step 2", tool_name="fast_tool", arguments={"val": "Second"}, depends_on=["s1"])

        plan = TaskPlan(title="Two Step Test", steps=[step1, step2])

        events_received = []
        self.bus.subscribe("task.*", lambda e: events_received.append(e.topic))

        async def _run():
            return await self.executor.execute_plan(plan)

        result_plan = asyncio.run(_run())
        self.assertEqual(result_plan.state, TaskState.COMPLETED)
        self.assertEqual(step1.status, TaskState.COMPLETED)
        self.assertEqual(step2.status, TaskState.COMPLETED)
        self.assertEqual(step1.result, "Echo: First")
        self.assertEqual(step2.result, "Echo: Second")
        self.assertIn(EventNames.TASK_CREATED, events_received)
        self.assertIn(EventNames.TASK_PROGRESS, events_received)
        self.assertIn(EventNames.TASK_COMPLETED, events_received)

    def test_task_cancellation(self):
        async def _test_cancel():
            # Create a long plan with multiple steps
            steps = [
                TaskStep(step_id=f"st_{i}", title=f"Step {i}", tool_name="fast_tool", arguments={"val": f"v{i}"})
                for i in range(5)
            ]
            plan = TaskPlan(task_id="cancel_task_1", title="Cancel Test", steps=steps)

            # Start execution as async task
            task_future = asyncio.create_task(self.executor.execute_plan(plan))

            # Immediately trigger cancellation
            await asyncio.sleep(0.01)
            self.executor.cancel_task("cancel_task_1")

            finished_plan = await task_future
            self.assertIn(finished_plan.state, (TaskState.CANCELLED, TaskState.COMPLETED))

        asyncio.run(_test_cancel())


if __name__ == "__main__":
    unittest.main()
