"""
AI Provider Manager for Falcon.
Coordinates multiple AI backends, dynamic fallback, capability queries, and health checks.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import logging
from typing import AsyncIterator, Dict, List, Optional
from falcon.ai.base_provider import (
    AIResponse,
    BaseAIProvider,
    ChatMessage,
    ProviderCapabilities,
    ToolDefinition,
)
from falcon.ai.cloud_provider import OpenAICompatibleProvider
from falcon.ai.local_provider import OllamaProvider
from falcon.ai.mock_provider import MockAIProvider
from falcon.ai.nvidia_provider import NvidiaNimProvider
from falcon.config.settings import AISettings

logger = logging.getLogger("Falcon.ProviderManager")


class ProviderManager:
    """Manages provider registry, active provider selection, and fallback execution."""

    def __init__(self, settings: AISettings):
        self.settings = settings
        self._providers: Dict[str, BaseAIProvider] = {}
        self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Register built-in providers according to configuration."""
        # Mock provider (always available for testing & fallback)
        self.register_provider(MockAIProvider())

        # NVIDIA NIM Provider (Nemotron, Ultra models, deep reasoning)
        if self.settings.nvidia_api_key:
            self.register_provider(
                NvidiaNimProvider(
                    api_key=self.settings.nvidia_api_key,
                    model=self.settings.default_model if "nvidia" in self.settings.default_model or "nemotron" in self.settings.default_model else "nvidia/nemotron-3-ultra-550b-a55b",
                    base_url=self.settings.nvidia_base_url,
                    timeout=self.settings.request_timeout_seconds,
                    enable_thinking=True,
                )
            )

        # Local Ollama provider
        self.register_provider(
            OllamaProvider(
                base_url=self.settings.ollama_base_url,
                model=self.settings.default_model,
                timeout=self.settings.request_timeout_seconds,
            )
        )

        # Cloud OpenAI-compatible provider
        if self.settings.openai_api_key or self.settings.openai_base_url:
            self.register_provider(
                OpenAICompatibleProvider(
                    api_key=self.settings.openai_api_key,
                    model=self.settings.default_model or "gpt-4o-mini",
                    base_url=self.settings.openai_base_url or "https://api.openai.com/v1",
                    timeout=self.settings.request_timeout_seconds,
                    provider_name="openai",
                )
            )

    def register_provider(self, provider: BaseAIProvider) -> None:
        """Register or override a provider."""
        self._providers[provider.name.lower()] = provider
        logger.info(f"Registered AI provider: '{provider.name}' (model: {provider.model})")

    def get_provider(self, name: Optional[str] = None) -> Optional[BaseAIProvider]:
        """Fetch provider by name, or return configured default."""
        target = (name or self.settings.default_provider).lower()
        return self._providers.get(target)

    async def get_active_provider(self) -> BaseAIProvider:
        """
        Return the primary configured provider if available;
        otherwise fail over to fallback provider.
        """
        primary = self.get_provider(self.settings.default_provider)
        if primary and await primary.is_available():
            return primary

        # If primary is not available, try fallback
        fallback_name = self.settings.fallback_provider or "mock"
        logger.warning(
            f"Primary AI provider '{self.settings.default_provider}' is unavailable. "
            f"Failing over to fallback provider '{fallback_name}'."
        )
        fallback = self.get_provider(fallback_name)
        if fallback and await fallback.is_available():
            return fallback

        # If all else fails, use mock
        return self._providers.get("mock", MockAIProvider())

    async def generate_response(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        provider_name: Optional[str] = None,
    ) -> AIResponse:
        """Execute chat completion with automatic retry and fallback."""
        provider = self.get_provider(provider_name) if provider_name else await self.get_active_provider()
        if not provider:
            provider = await self.get_active_provider()

        logger.debug(f"Generating AI response using provider: '{provider.name}'")
        response = await provider.generate_response(
            messages=messages,
            tools=tools,
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
        )

        # If error occurred and provider was not mock, attempt fallback
        if response.finish_reason == "error" and provider.name != "mock":
            logger.warning(f"Provider '{provider.name}' failed: {response.error}. Attempting fallback...")
            fallback = self.get_provider(self.settings.fallback_provider or "mock")
            if fallback and fallback.name != provider.name:
                fallback_resp = await fallback.generate_response(
                    messages=messages,
                    tools=tools,
                    temperature=self.settings.temperature,
                    max_tokens=self.settings.max_tokens,
                )
                if fallback_resp.finish_reason != "error":
                    return fallback_resp

        return response

    async def stream_response(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        provider_name: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream chat tokens with active provider."""
        provider = self.get_provider(provider_name) if provider_name else await self.get_active_provider()
        if not provider:
            provider = await self.get_active_provider()

        async for chunk in provider.stream_response(
            messages=messages,
            tools=tools,
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
        ):
            yield chunk

    def list_providers(self) -> List[str]:
        """Return names of all registered providers."""
        return list(self._providers.keys())
