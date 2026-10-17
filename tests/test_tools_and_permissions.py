"""
Unit tests for tool registry, parameter schema validation, permissions, and audit trails.
"""

import asyncio
import tempfile
import unittest
from pathlib import Path
from falcon.security.policy import PermissionLevel, SecurityPolicy
from falcon.tools.file_tools import ListDirectoryTool, ReadFileTool, WriteFileTool
from falcon.tools.registry import BaseTool, ToolRegistry


class DummyHighRiskTool(BaseTool):
    name = "dummy_high_risk"
    description = "A simulated high risk operation."
    permission_level = PermissionLevel.HIGH_RISK
    parameters_schema = {
        "type": "object",
        "properties": {
            "target": {"type": "string"},
        },
        "required": ["target"],
    }

    async def execute(self, target: str):
        return f"Executed on {target}"


class TestToolsAndPermissions(unittest.TestCase):

    def setUp(self):
        self.policy = SecurityPolicy(require_approval_for_high_risk=True)
        self.registry = ToolRegistry(self.policy)
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_schema_validation(self):
        self.registry.register_tool(DummyHighRiskTool())

        async def _test():
            # Missing required argument
            res1 = await self.registry.execute_tool("dummy_high_risk", {})
            self.assertEqual(res1["status"], "error")
            self.assertIn("Missing required parameter", res1["error"])

            # Wrong argument type
            res2 = await self.registry.execute_tool("dummy_high_risk", {"target": 12345})
            self.assertEqual(res2["status"], "error")
            self.assertIn("expected string", res2["error"])

        asyncio.run(_test())

    def test_permission_approval_gating(self):
        self.registry.register_tool(DummyHighRiskTool())

        async def _test():
            # Without approval callback, high risk tool is blocked
            blocked_res = await self.registry.execute_tool("dummy_high_risk", {"target": "node_1"})
            self.assertEqual(blocked_res["status"], "blocked")

            # With approval callback granting permission
            async def _mock_approve(prompt, tool, args):
                return True

            self.registry.set_confirmation_callback(_mock_approve)
            approved_res = await self.registry.execute_tool("dummy_high_risk", {"target": "node_1"})
            self.assertEqual(approved_res["status"], "success")

            # Verify audit trail
            audits = self.policy.get_audit_trail()
            self.assertTrue(len(audits) >= 2)
            self.assertEqual(audits[-1].status, "EXECUTED")

        asyncio.run(_test())

    def test_safe_file_tools(self):
        allowed_root = Path(self.temp_dir.name)
        write_tool = WriteFileTool(allowed_roots=[str(allowed_root)])
        read_tool = ReadFileTool(allowed_roots=[str(allowed_root)])
        list_tool = ListDirectoryTool(allowed_roots=[str(allowed_root)])

        self.registry.register_tool(write_tool)
        self.registry.register_tool(read_tool)
        self.registry.register_tool(list_tool)

        async def _test():
            test_file = allowed_root / "sample.txt"
            
            # Write file
            w_res = await self.registry.execute_tool("write_file", {"file_path": str(test_file), "content": "Falcon AI Test"})
            self.assertEqual(w_res["status"], "success")

            # Read file
            r_res = await self.registry.execute_tool("read_file", {"file_path": str(test_file)})
            self.assertEqual(r_res["status"], "success")
            self.assertEqual(r_res["result"]["content"], "Falcon AI Test")

            # List directory
            l_res = await self.registry.execute_tool("list_directory", {"path": str(allowed_root)})
            self.assertEqual(l_res["status"], "success")
            self.assertEqual(l_res["result"]["total_listed"], 1)

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
