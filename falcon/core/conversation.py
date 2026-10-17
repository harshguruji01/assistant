"""
Conversation Pipeline and Context Orchestrator for Falcon.
Maintains conversational context, enforces system persona, and coordinates tool-loop responses.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import datetime
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional
from falcon.ai.base_provider import (
    ChatMessage,
    MessageRole,
    ToolCallRequest,
    ToolDefinition,
)
from falcon.ai.provider_manager import ProviderManager
from falcon.core.intent_engine import IntentEngine, IntentType, ParsedIntent

logger = logging.getLogger("Falcon.Conversation")

SYSTEM_PROMPT_TEMPLATE = """You are Falcon, an advanced desktop AI assistant for Windows 11, created by HarshGuruJi (Real Name: Harsh Patel).
Owner & Creator Website: www.webguruji.online

Core Persona & Memory Directive:
1. Creator & Master: Your creator is HarshGuruJi (Harsh Patel), founder of www.webguruji.online. Treat him with utmost respect, loyalty, and dedication.
2. Indelible Memory: You have permanent, long-term memory. You must NEVER forget who Harsh Patel (HarshGuruJi) is, his website www.webguruji.online, his instructions, photos, preferences, and projects.
3. Capabilities: Windows 11 desktop automation, file management, launching authorized applications, scheduling tasks, and answering questions.
4. Language Support: Fluent in English, Hindi, and Hinglish. Adapt smoothly to the user's chosen language.
5. Reliability: When performing desktop operations, use the available tools safely and accurately.
6. Current local time: {current_time}.
7. Platform: Windows 11.
{permanent_memories}
"""


@dataclass
class ConversationResult:
    """Outcome of a single user message turn."""
    user_input: str
    response_text: str
    parsed_intent: ParsedIntent
    executed_tools: List[Dict[str, Any]] = field(default_factory=list)
    latency_seconds: float = 0.0
    provider_used: str = ""
    model_used: str = ""
    error: Optional[str] = None


class ConversationEngine:
    """Manages active conversation context and execution turns."""

    def __init__(
        self,
        provider_manager: ProviderManager,
        intent_engine: IntentEngine,
        max_history_turns: int = 15,
    ):
        self.provider_manager = provider_manager
        self.intent_engine = intent_engine
        self.max_history_turns = max_history_turns
        self._history: List[ChatMessage] = []
        self._tool_executor: Optional[Callable[[str, Dict[str, Any]], Coroutine[Any, Any, Any]]] = None
        self._active_tools: List[ToolDefinition] = []

    def set_tool_executor(
        self,
        executor_func: Callable[[str, Dict[str, Any]], Coroutine[Any, Any, Any]],
        tool_definitions: List[ToolDefinition],
    ) -> None:
        """Register the tool execution callback and schemas."""
        self._tool_executor = executor_func
        self._active_tools = tool_definitions

    def clear_context(self) -> None:
        """Clear active conversation history."""
        self._history.clear()
        logger.info("Cleared conversation context.")

    def get_history(self) -> List[ChatMessage]:
        return list(self._history)

    def set_memory_retriever(self, retriever_func: Callable[[], List[str]]) -> None:
        """Register callback to fetch stored persistent memories."""
        self._memory_retriever = retriever_func

    def _build_context_messages(self) -> List[ChatMessage]:
        """Construct prompt context with system instructions, permanent memories, and history."""
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mem_text = ""
        if hasattr(self, "_memory_retriever") and self._memory_retriever:
            try:
                mem_items = self._memory_retriever()
                if mem_items:
                    mem_text = "Permanent Stored Memories & Creator Facts:\n" + "\n".join(f"- {m}" for m in mem_items)
            except Exception as e:
                logger.warning(f"Failed to fetch memories: {e}")

        sys_msg = ChatMessage(
            role=MessageRole.SYSTEM,
            content=SYSTEM_PROMPT_TEMPLATE.format(current_time=now_str, permanent_memories=mem_text),
        )
        return [sys_msg] + self._history[-(self.max_history_turns * 2):]

    async def process_user_turn(
        self,
        user_text: str,
        correlation_id: Optional[str] = None,
    ) -> ConversationResult:
        """Process a user message from input to structured response."""
        start_time = time.perf_counter()
        parsed_intent = self.intent_engine.classify_intent(user_text)

        # Handle empty/clarification intent immediately
        if parsed_intent.intent_type == IntentType.CLARIFICATION_NEEDED:
            return ConversationResult(
                user_input=user_text,
                response_text="I didn't quite catch that. How can Falcon assist you with your Windows desktop?",
                parsed_intent=parsed_intent,
                latency_seconds=time.perf_counter() - start_time,
            )

        # Add user message to history
        user_msg = ChatMessage(role=MessageRole.USER, content=user_text)
        self._history.append(user_msg)

        context_messages = self._build_context_messages()
        executed_tools_record: List[Dict[str, Any]] = []

        try:
            # First AI generation
            ai_response = await self.provider_manager.generate_response(
                messages=context_messages,
                tools=self._active_tools if self._active_tools else None,
            )

            # If tool calls were proposed and tool executor is available, execute them
            if ai_response.tool_calls and self._tool_executor:
                logger.info(f"AI proposed {len(ai_response.tool_calls)} tool call(s)")
                # Append assistant message with tool calls
                asst_msg = ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=ai_response.content,
                    tool_calls=ai_response.tool_calls,
                )
                self._history.append(asst_msg)
                context_messages.append(asst_msg)

                for tc in ai_response.tool_calls:
                    tool_exec_result = await self._tool_executor(tc.tool_name, tc.arguments)
                    executed_tools_record.append({
                        "tool": tc.tool_name,
                        "args": tc.arguments,
                        "result": tool_exec_result,
                    })

                    # Append tool response message to context
                    import json
                    content_str = json.dumps(tool_exec_result, default=str)
                    tool_msg = ChatMessage(
                        role=MessageRole.TOOL,
                        name=tc.tool_name,
                        tool_call_id=tc.id,
                        content=content_str,
                    )
                    self._history.append(tool_msg)
                    context_messages.append(tool_msg)

                # Follow-up generation after tool execution to produce final user-facing response
                follow_up_resp = await self.provider_manager.generate_response(
                    messages=context_messages,
                    tools=None,
                )
                final_content = follow_up_resp.content or "Operation executed successfully."
                provider_used = follow_up_resp.provider_name
                model_used = follow_up_resp.model_name
            else:
                final_content = ai_response.content
                provider_used = ai_response.provider_name
                model_used = ai_response.model_name

            # Append final assistant message to history
            self._history.append(ChatMessage(role=MessageRole.ASSISTANT, content=final_content))

            latency = time.perf_counter() - start_time
            return ConversationResult(
                user_input=user_text,
                response_text=final_content,
                parsed_intent=parsed_intent,
                executed_tools=executed_tools_record,
                latency_seconds=latency,
                provider_used=provider_used,
                model_used=model_used,
            )

        except Exception as e:
            logger.error(f"Error in conversation turn: {e}", exc_info=True)
            err_msg = f"An error occurred while processing your request: {e}"
            return ConversationResult(
                user_input=user_text,
                response_text=err_msg,
                parsed_intent=parsed_intent,
                latency_seconds=time.perf_counter() - start_time,
                error=str(e),
            )
