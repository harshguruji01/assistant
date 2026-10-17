"""
Base AI Provider Interfaces and Data Models for Falcon.
Defines model abstractions, message structures, tool definitions, and capabilities.
Developed by: HarshGuruJi
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional


class MessageRole(str, Enum):
    """Roles in conversation history."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolCallRequest:
    """Represents a tool call proposed by the model."""
    id: str
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatMessage:
    """A single message within the conversation context."""
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[ToolCallRequest]] = None
    tool_call_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "role": self.role.value,
            "content": self.content or "",
        }
        if self.name:
            data["name"] = self.name
        if self.tool_calls:
            data["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.tool_name,
                        "arguments": tc.arguments,
                    },
                }
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        return data


@dataclass
class ToolDefinition:
    """Schema definition for tools exposed to AI models."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema format
    required_permissions: List[str] = field(default_factory=list)

    def to_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ProviderCapabilities:
    """Capabilities supported by a specific model or provider."""
    supports_tools: bool = True
    supports_streaming: bool = True
    supports_vision: bool = False
    context_window_size: int = 8192
    supports_system_prompt: bool = True


@dataclass
class AIResponse:
    """Standardized response from an AI provider."""
    content: str
    tool_calls: List[ToolCallRequest] = field(default_factory=list)
    provider_name: str = ""
    model_name: str = ""
    finish_reason: str = "stop"  # stop, tool_calls, length, error
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: Optional[str] = None


class BaseAIProvider(ABC):
    """Abstract base class for all Falcon AI provider implementations."""

    def __init__(self, name: str, model: str):
        self.name = name
        self.model = model

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider endpoint and credentials are operational."""
        pass

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """Return provider-specific capabilities."""
        pass

    @abstractmethod
    async def generate_response(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AIResponse:
        """Execute non-streaming inference with optional tool definitions."""
        pass

    @abstractmethod
    async def stream_response(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """Stream token chunks for real-time UI/Voice interaction."""
        pass
