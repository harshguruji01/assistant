"""
NVIDIA NIM Cloud AI Provider for Falcon.
Supports ultra-scale models such as nvidia/nemotron-3-ultra-550b-a55b,
deep reasoning (enable_thinking), streaming, and standard tool calling.
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

logger = logging.getLogger("Falcon.NvidiaProvider")


class NvidiaNimProvider(BaseAIProvider):
    """Adapter for NVIDIA NIM API (integrate.api.nvidia.com) with reasoning support."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "nvidia/nemotron-3-ultra-550b-a55b",
        base_url: str = "https://integrate.api.nvidia.com/v1",
        timeout: float = 60.0,
        enable_thinking: bool = True,
    ):
        super().__init__(name="nvidia", model=model)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.enable_thinking = enable_thinking

    async def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.startswith("nvapi-"))

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tools=True,
            supports_streaming=True,
            supports_vision=False,
            context_window_size=16384,
            supports_system_prompt=True,
        )

    def _prepare_request_payload(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> Dict[str, Any]:
        msgs_payload = [m.to_dict() for m in messages]
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": msgs_payload,
            "temperature": temperature,
            "top_p": 0.95,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        # Add thinking template kwargs if requested
        if self.enable_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": True}

        if tools:
            payload["tools"] = [t.to_openai_schema() for t in tools]
            payload["tool_choice"] = "auto"

        return payload

    async def generate_response(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AIResponse:
        if not self.api_key:
            return AIResponse(
                content="",
                provider_name=self.name,
                model_name=self.model,
                finish_reason="error",
                error="NVIDIA API key (nvapi-...) is missing or not configured.",
            )

        endpoint = f"{self.base_url}/chat/completions"
        payload = self._prepare_request_payload(messages, tools, temperature, max_tokens, stream=False)

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
            reasoning = msg.get("reasoning_content") or ""

            # If reasoning exists, prefix or log it
            if reasoning:
                logger.info(f"NVIDIA Nemotron Reasoning: {reasoning[:120]}...")

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
                        id=tc.get("id", "call_nvidia"),
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
                finish_reason="tool_calls" if tool_calls else finish_reason,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            # If 503 overloaded and currently on 550b, failover to 30b reasoning model on NVIDIA NIM
            if e.code in (500, 503) and self.model != "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning":
                logger.warning(
                    f"NVIDIA model '{self.model}' returned HTTP {e.code} (Overloaded). "
                    f"Automatically failing over to 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning'..."
                )
                original_model = self.model
                self.model = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
                try:
                    resp = await self.generate_response(messages, tools, temperature, max_tokens)
                    return resp
                finally:
                    self.model = original_model

            logger.error(f"NVIDIA NIM API HTTP Error {e.code}: {err_body}")
            return AIResponse(
                content="",
                provider_name=self.name,
                model_name=self.model,
                finish_reason="error",
                error=f"NVIDIA API HTTP {e.code}: {err_body}",
            )
        except Exception as e:
            logger.error(f"NVIDIA NIM API Request failed: {e}")
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
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        # Try using OpenAI client if installed for seamless SSE streaming
        try:
            from openai import OpenAI  # type: ignore

            client = OpenAI(base_url=self.base_url, api_key=self.api_key)
            msgs_payload = [m.to_dict() for m in messages]

            def _get_stream():
                return client.chat.completions.create(
                    model=self.model,
                    messages=msgs_payload,
                    temperature=temperature,
                    top_p=0.95,
                    max_tokens=max_tokens,
                    extra_body={"chat_template_kwargs": {"enable_thinking": self.enable_thinking}},
                    stream=True,
                )

            stream_obj = await asyncio.to_thread(_get_stream)
            for chunk in stream_obj:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    yield reasoning
                if delta.content:
                    yield delta.content
            return
        except ImportError:
            pass

        # Fallback to generate_response tokens
        resp = await self.generate_response(messages, tools, temperature, max_tokens)
        if resp.content:
            for word in resp.content.split(" "):
                yield word + " "
                await asyncio.sleep(0.01)
