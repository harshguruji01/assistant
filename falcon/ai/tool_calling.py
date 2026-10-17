"""
Tool Calling and Schema Parsing Utilities for Falcon.
Handles serialization and deserialization of tool calls across model providers.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from falcon.ai.base_provider import ToolCallRequest, ToolDefinition

logger = logging.getLogger("Falcon.ToolCalling")


class ToolCallingHelper:
    """Helper utilities for tool arguments and schema conversion."""

    @staticmethod
    def parse_arguments(raw_args: Any) -> Dict[str, Any]:
        """Safely parse raw tool arguments into a dictionary."""
        if isinstance(raw_args, dict):
            return raw_args
        if isinstance(raw_args, str):
            clean = raw_args.strip()
            if not clean:
                return {}
            try:
                return json.loads(clean)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to decode tool arguments string '{raw_args}': {e}")
                return {"_raw_text": raw_args}
        return {}

    @staticmethod
    def format_tool_result_message(tool_call_id: str, tool_name: str, result: Any) -> Dict[str, Any]:
        """Format a tool result as a standard message payload."""
        content = json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
        return {
            "role": "tool",
            "name": tool_name,
            "tool_call_id": tool_call_id,
            "content": content,
        }
