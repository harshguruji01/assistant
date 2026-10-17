"""
Tool Registry and Execution Pipeline for Falcon.
Manages tool definitions, parameter validation, permission checks, and audit logging.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import inspect
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine, Dict, List, Optional
from falcon.ai.base_provider import ToolDefinition
from falcon.security.policy import AuditRecord, PermissionLevel, SecurityPolicy

logger = logging.getLogger("Falcon.ToolRegistry")


class BaseTool(ABC):
    """Abstract base class for all callable tools."""

    name: str = ""
    description: str = ""
    parameters_schema: Dict[str, Any] = {}
    permission_level: PermissionLevel = PermissionLevel.READ_ONLY
    requires_confirmation: bool = False

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """Perform the actual tool logic and return structured result."""
        pass

    def get_tool_definition(self) -> ToolDefinition:
        """Export tool metadata for AI provider consumption."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters_schema,
            required_permissions=[self.permission_level.value],
        )


class ToolRegistry:
    """Central registry and executor for all Falcon capabilities."""

    def __init__(self, security_policy: SecurityPolicy):
        self.security_policy = security_policy
        self._tools: Dict[str, BaseTool] = {}
        self._confirmation_callback: Optional[Callable[[str, BaseTool, Dict[str, Any]], Coroutine[Any, Any, bool]]] = None

    def register_tool(self, tool: BaseTool) -> None:
        """Register a new tool instance."""
        if not tool.name:
            raise ValueError(f"Tool {tool} must have a non-empty name.")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: '{tool.name}' [{tool.permission_level.value}]")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tool_definitions(self) -> List[ToolDefinition]:
        """Return all tool definitions formatted for AI providers."""
        return [tool.get_tool_definition() for tool in self._tools.values()]

    def set_confirmation_callback(
        self,
        callback: Callable[[str, BaseTool, Dict[str, Any]], Coroutine[Any, Any, bool]]
    ) -> None:
        """Set callback to request interactive user confirmation for high-risk actions."""
        self._confirmation_callback = callback

    def _validate_arguments(self, tool: BaseTool, kwargs: Dict[str, Any]) -> None:
        """Validate input arguments against tool schema."""
        properties = tool.parameters_schema.get("properties", {})
        required = tool.parameters_schema.get("required", [])

        # Check required fields
        for req in required:
            if req not in kwargs or kwargs[req] is None:
                raise ValueError(f"Missing required parameter '{req}' for tool '{tool.name}'.")

        # Type checking for primitives
        type_map = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict}
        for k, v in kwargs.items():
            if k in properties and v is not None:
                expected_type_name = properties[k].get("type")
                if expected_type_name in type_map:
                    expected_type = type_map[expected_type_name]
                    if not isinstance(v, expected_type):
                        raise TypeError(
                            f"Parameter '{k}' in tool '{tool.name}' expected {expected_type_name}, got {type(v).__name__}."
                        )

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Validate, authorize, audit, and execute a tool call."""
        tool = self.get_tool(tool_name)
        if not tool:
            err = f"Tool '{tool_name}' is not registered."
            logger.error(err)
            return {"status": "error", "error": err}

        # Validate arguments
        try:
            self._validate_arguments(tool, arguments)
        except Exception as e:
            logger.warning(f"Argument validation failed for '{tool_name}': {e}")
            return {"status": "error", "error": f"Invalid arguments: {e}"}

        # Check confirmation requirement
        needs_approval = (
            tool.requires_confirmation
            or self.security_policy.requires_user_confirmation(tool.permission_level)
        )

        user_approved = True
        if needs_approval:
            logger.info(f"Tool '{tool_name}' requires approval [{tool.permission_level.value}]")
            if self._confirmation_callback:
                prompt_msg = f"Falcon is requesting permission to execute: '{tool_name}' with parameters: {arguments}"
                user_approved = await self._confirmation_callback(prompt_msg, tool, arguments)
            else:
                # Without interactive callback, block high-risk actions safely
                logger.warning(f"High risk tool '{tool_name}' blocked: no confirmation callback configured.")
                user_approved = False

            if not user_approved:
                record = AuditRecord(
                    action_name=tool_name,
                    parameters=arguments,
                    permission_level=tool.permission_level,
                    approved_by_user=False,
                    status="BLOCKED",
                    error_message="User declined or approval unavailable.",
                )
                self.security_policy.log_audit(record)
                return {
                    "status": "blocked",
                    "message": "Action was blocked because it requires user approval.",
                }

        # Execute tool
        try:
            logger.info(f"Executing tool '{tool_name}' with arguments: {arguments}")
            if inspect.iscoroutinefunction(tool.execute):
                result = await tool.execute(**arguments)
            else:
                result = tool.execute(**arguments)

            # Record success audit
            record = AuditRecord(
                action_name=tool_name,
                parameters=arguments,
                permission_level=tool.permission_level,
                approved_by_user=user_approved,
                status="EXECUTED",
            )
            self.security_policy.log_audit(record)
            return {"status": "success", "result": result}

        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            record = AuditRecord(
                action_name=tool_name,
                parameters=arguments,
                permission_level=tool.permission_level,
                approved_by_user=user_approved,
                status="FAILED",
                error_message=str(e),
            )
            self.security_policy.log_audit(record)
            return {"status": "error", "error": str(e)}
