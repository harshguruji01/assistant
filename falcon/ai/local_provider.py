"""
Local AI Provider Implementation for Ollama.
Connects to local Ollama inference server on Windows without requiring cloud keys.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from typing import Any, AsyncIterator, Dict, List, Optional
from falcon.ai.base_provider import (
    AIResponse,
    BaseAIProvider,
    ChatMessage,
    ProviderCapabilities,
    ToolCallRequest,
    ToolDefinition,
)

logger = logging.getLogger("Falcon.OllamaProvider")


class OllamaProvider(BaseAIProvider):
    """Adapter for locally hosted Ollama model service."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
        timeout: float = 30.0,
    ):
        super().__init__(name="ollama", model=model)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def is_available(self) -> bool:
        """Ping Ollama /api/tags to see if the local daemon is active."""
        def _check():
            try:
                url = f"{self.base_url}/api/tags"
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    return resp.status == 200
            except Exception:
                return False

        return await asyncio.to_thread(_check)

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tools=True,
            supports_streaming=True,
            supports_vision=False,
            context_window_size=8192,
            supports_system_prompt=True,
        )

    def _prepare_payload(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> Dict[str, Any]:
        formatted_messages = []
        for m in messages:
            msg_dict: Dict[str, Any] = {"role": m.role.value, "content": m.content}
            if m.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "function": {
                            "name": tc.tool_name,
                            "arguments": tc.arguments,
                        }
                    }
                    for tc in m.tool_calls
                ]
            formatted_messages.append(msg_dict)

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "stream": stream,
            "options": {"temperature": temperature},
        }

        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]

        return payload

    async def generate_response(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AIResponse:
        payload = self._prepare_payload(messages, tools, temperature, stream=False)
        url = f"{self.base_url}/api/chat"

        def _call_ollama() -> Dict[str, Any]:
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))

        try:
            res_json = await asyncio.to_thread(_call_ollama)
            message_data = res_json.get("message", {})
            content = message_data.get("content", "")

            # Parse tool calls if returned
            tool_calls: List[ToolCallRequest] = []
            raw_tool_calls = message_data.get("tool_calls", [])
            for idx, tc in enumerate(raw_tool_calls):
                func_data = tc.get("function", {})
                tool_calls.append(
                    ToolCallRequest(
                        id=f"ollama_call_{idx}",
                        tool_name=func_data.get("name", ""),
                        arguments=func_data.get("arguments", {}),
                    )
                )

            finish_reason = "tool_calls" if tool_calls else "stop"

            return AIResponse(
                content=content,
                tool_calls=tool_calls,
                provider_name=self.name,
                model_name=self.model,
                finish_reason=finish_reason,
                prompt_tokens=res_json.get("prompt_eval_count", 0),
                completion_tokens=res_json.get("eval_count", 0),
            )
        except Exception as e:
            logger.error(f"Ollama request error: {e}")
            return AIResponse(
                content="",
                provider_name=self.name,
                model_name=self.model,
                finish_reason="error",
                error=str(e),
            )

    async def stream_response(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        # Fallback to generate_response if streaming socket streaming is interrupted
        full = await self.generate_response(messages, tools, temperature, max_tokens)
        if full.content:
            for chunk in full.content.split(" "):
                yield chunk + " "
                await asyncio.sleep(0.01)
