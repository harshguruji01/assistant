"""
Mock / Deterministic Offline AI Provider for Falcon.
Used for offline operation, automated testing, and development without external API costs.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, AsyncIterator, Dict, List, Optional
from falcon.ai.base_provider import (
    AIResponse,
    BaseAIProvider,
    ChatMessage,
    MessageRole,
    ProviderCapabilities,
    ToolCallRequest,
    ToolDefinition,
)


class MockAIProvider(BaseAIProvider):
    """
    Simulated intelligent provider for offline tests and development.
    Can trigger tool calls deterministically based on message content.
    """

    def __init__(self, name: str = "mock", model: str = "falcon-offline-v1"):
        super().__init__(name=name, model=model)

    async def is_available(self) -> bool:
        return True

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tools=True,
            supports_streaming=True,
            supports_vision=False,
            context_window_size=4096,
            supports_system_prompt=True,
        )

    async def generate_response(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AIResponse:
        # Check if the last message is a tool result from execution
        if messages and messages[-1].role == MessageRole.TOOL:
            last_tool = messages[-1]
            try:
                import json
                tool_data = json.loads(last_tool.content) if isinstance(last_tool.content, str) else last_tool.content
            except Exception:
                tool_data = {}

            if not isinstance(tool_data, dict):
                tool_data = {}

            # Unwrap nested 'result' dictionary from ToolRegistry
            res = tool_data.get("result", tool_data) if isinstance(tool_data.get("result"), dict) else tool_data

            if last_tool.name == "get_system_info":
                ram_info = res.get("ram", {}) if isinstance(res.get("ram"), dict) else {}
                ram_str = f"{ram_info.get('used_gb', 'N/A')} GB / {ram_info.get('total_gb', 'N/A')} GB ({ram_info.get('percent_used', 'N/A')}%)"
                cpu_str = f"{res.get('cpu_percent', 'N/A')}%"
                os_str = res.get("os", "Windows 11")
                reply = f"Here is your system status:\n- OS: {os_str}\n- RAM: {ram_str}\n- CPU: {cpu_str}\n- Status: Falcon System Monitor active."
            elif last_tool.name == "launch_application":
                app_name = res.get("app_name", "Application") if isinstance(res, dict) else "Application"
                reply = f"Successfully launched {app_name} on your Windows desktop."
            elif last_tool.name == "list_directory":
                items = res.get("items", []) if isinstance(res, dict) else []
                reply = f"Directory contents retrieved successfully ({len(items)} items found)."
            else:
                reply = f"Tool '{last_tool.name}' executed successfully."

            return AIResponse(
                content=reply,
                tool_calls=[],
                provider_name=self.name,
                model_name=self.model,
                finish_reason="stop",
            )

        last_user_msg = ""
        for m in reversed(messages):
            if m.role == MessageRole.USER:
                last_user_msg = m.content
                break

        lowered = last_user_msg.lower().strip()

        # Handle tool calling intentions if tools are available
        tool_calls: List[ToolCallRequest] = []
        if tools:
            tool_names = {t.name: t for t in tools}

            # Check if user asked to open an app
            app_match = re.search(r"open\s+([a-zA-Z0-9_\-\.]+)", lowered)
            if app_match and "launch_application" in tool_names:
                app_name = app_match.group(1)
                tool_calls.append(
                    ToolCallRequest(
                        id="call_mock_launch_app_1",
                        tool_name="launch_application",
                        arguments={"app_name": app_name},
                    )
                )

            # Check if user asked for system stats
            elif any(k in lowered for k in ("system info", "cpu", "ram", "specs", "battery", "performance")) and "get_system_info" in tool_names:
                tool_calls.append(
                    ToolCallRequest(
                        id="call_mock_sysinfo_1",
                        tool_name="get_system_info",
                        arguments={},
                    )
                )

            # Check if user asked to list files
            elif any(k in lowered for k in ("list files", "show files", "directory content")) and "list_directory" in tool_names:
                tool_calls.append(
                    ToolCallRequest(
                        id="call_mock_listfiles_1",
                        tool_name="list_directory",
                        arguments={"path": "."},
                    )
                )

        if tool_calls:
            return AIResponse(
                content="I will execute that operation for you now.",
                tool_calls=tool_calls,
                provider_name=self.name,
                model_name=self.model,
                finish_reason="tool_calls",
            )

        # Conversational responses (including multilingual / Hindi / Hinglish)
        if any(w in lowered for w in ("namaste", "pranam", "kya haal hai", "kaise ho")):
            reply = "Namaste HarshGuruJi! Main Falcon hoon, aapke (Harsh Patel) dwara banaya gaya desktop AI assistant. Main aapki kya seva kar sakta hoon?"
        elif any(w in lowered for w in ("hello", "hi", "hey")):
            reply = "Hello! I am Falcon, your Windows desktop assistant developed by HarshGuruJi (Harsh Patel), founder of www.webguruji.online."
        elif any(k in lowered for k in ("who made you", "who developed you", "kisme banaya", "creator", "owner")):
            reply = "I was created by HarshGuruJi (Real Name: Harsh Patel), owner and visionary founder of www.webguruji.online."
        elif any(k in lowered for k in ("website", "webguruji")):
            reply = "The official website of my creator HarshGuruJi (Harsh Patel) is www.webguruji.online."
        elif any(k in lowered for k in ("harsh patel", "harshguruji")):
            reply = "HarshGuruJi (Harsh Patel) is my creator, developer, and master. His official platform is www.webguruji.online, and I have permanent memory of him."
        elif any(k in lowered for k in ("memory", "yaad", "forget", "bhul")):
            reply = "Mujhe sab kuch yaad hai aur rahega! Mere paas SQLite permanent memory storage hai, main Harsh Patel (HarshGuruJi) aur unke www.webguruji.online ko kabhi nahi bhool sakta."
        elif "time" in lowered or "samay" in lowered:
            import datetime
            now_str = datetime.datetime.now().strftime("%I:%M %p")
            reply = f"The current system time is {now_str}."
        elif "date" in lowered or "tarikh" in lowered:
            import datetime
            date_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
            reply = f"Today's date is {date_str}."
        else:
            reply = f"I understand your message: '{last_user_msg}'. Falcon core is ready for commands and workflow automation."

        return AIResponse(
            content=reply,
            tool_calls=[],
            provider_name=self.name,
            model_name=self.model,
            finish_reason="stop",
            prompt_tokens=len(last_user_msg.split()),
            completion_tokens=len(reply.split()),
        )

    async def stream_response(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        full_resp = await self.generate_response(messages, tools, temperature, max_tokens)
        words = full_resp.content.split(" ")
        for word in words:
            yield word + " "
            await asyncio.sleep(0.01)
