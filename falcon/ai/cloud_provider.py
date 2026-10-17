"""
Cloud AI Provider Implementation for Falcon.
Supports OpenAI-compatible APIs, Google Gemini, and Anthropic Claude.
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
    MessageRole,
    ProviderCapabilities,
    ToolCallRequest,
    ToolDefinition,
)

logger = logging.getLogger("Falcon.CloudProvider")


class OpenAICompatibleProvider(BaseAIProvider):
    """Adapter for OpenAI and OpenAI-compatible API services (OpenAI, Groq, OpenRouter, DeepSeek, etc.)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
        provider_name: str = "openai",
    ):
        super().__init__(name=provider_name, model=model)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tools=True,
            supports_streaming=True,
            supports_vision=True,
            context_window_size=128000,
            supports_system_prompt=True,
        )

    async def generate_response(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AIResponse:
        if not self.api_key:
            return AIResponse(
                content="",
                provider_name=self.name,
                model_name=self.model,
                finish_reason="error",
                error=f"API key missing for provider '{self.name}'. Set environment variable or configure settings.",
            )

        endpoint = f"{self.base_url}/chat/completions"
        msgs_payload = [m.to_dict() for m in messages]

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": msgs_payload,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = [t.to_openai_schema() for t in tools]
            payload["tool_choice"] = "auto"

        def _do_request() -> Dict[str, Any]:
            body = json.dumps(payload).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))

        try:
            data = await asyncio.to_thread(_do_request)
            choice = data.get("choices", [{}])[0]
            msg = choice.get("message", {})
            finish_reason = choice.get("finish_reason", "stop")
            content = msg.get("content") or ""

            tool_calls: List[ToolCallRequest] = []
            for tc in msg.get("tool_calls", []):
                func = tc.get("function", {})
                args_str = func.get("arguments", "{}")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except Exception:
                    args = {"raw": args_str}

                tool_calls.append(
                    ToolCallRequest(
                        id=tc.get("id", "call_id"),
                        tool_name=func.get("name", ""),
                        arguments=args,
                    )
                )

            usage = data.get("usage", {})
            return AIResponse(
                content=content,
                tool_calls=tool_calls,
                provider_name=self.name,
                model_name=self.model,
                finish_reason=finish_reason,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            logger.error(f"Cloud API HTTP Error {e.code}: {err_body}")
            return AIResponse(
                content="",
                provider_name=self.name,
                model_name=self.model,
                finish_reason="error",
                error=f"HTTP {e.code}: {err_body}",
            )
        except Exception as e:
            logger.error(f"Cloud API Request failed: {e}")
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
        # Generate and chunk response
        resp = await self.generate_response(messages, tools, temperature, max_tokens)
        if resp.content:
            for word in resp.content.split(" "):
                yield word + " "
                await asyncio.sleep(0.01)
