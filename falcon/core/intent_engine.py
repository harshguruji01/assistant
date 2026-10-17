"""
Intent Recognition and Entity Extraction Engine for Falcon.
Distinguishes between conversational questions, single-tool commands, and multi-step workflows.
Supports English, Hindi, and Hinglish inputs.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class IntentType(str, Enum):
    """Primary intent categories."""
    CONVERSATION = "conversation"             # Chit-chat, general questions, explanations
    SYSTEM_COMMAND = "system_command"         # Single-step action (open app, check CPU, etc.)
    AUTOMATION_WORKFLOW = "workflow"          # Multi-step complex task
    CLARIFICATION_NEEDED = "clarification"   # Ambiguous instruction requiring follow-up
    UNKNOWN = "unknown"


@dataclass
class ParsedIntent:
    """Structured representation of interpreted user intent."""
    intent_type: IntentType
    action_type: str                          # e.g. "open_app", "read_file", "system_info", "set_reminder"
    confidence: float                         # 0.0 to 1.0
    entities: Dict[str, Any] = field(default_factory=dict)
    is_question: bool = False
    requires_confirmation: bool = False
    detected_language: str = "en"             # "en", "hi", "hi-en"
    raw_query: str = ""
    normalized_query: str = ""


class IntentEngine:
    """Hybrid deterministic & semantic intent analyzer."""

    def __init__(self):
        # Rule definitions for high-speed deterministic resolution
        self._app_launch_patterns = [
            re.compile(r"^(?:please\s+)?(?:open|launch|start|run|kholo|chalao)\s+([a-zA-Z0-9_\-\.\s]+)$", re.IGNORECASE),
            re.compile(r"^([a-zA-Z0-9_\-\.\s]+)\s+(?:kholo|chalao|open\s+karo|start\s+karo)$", re.IGNORECASE),
        ]
        self._sysinfo_patterns = [
            re.compile(r"(system|specs|cpu|ram|memory|battery|disk|usage|performance|stats|hardware)", re.IGNORECASE),
        ]
        self._file_patterns = [
            re.compile(r"(?:list|show|find|search|dikhaye|khojo)\s+(?:files|folders|documents|directory)", re.IGNORECASE),
            re.compile(r"(?:create|make|banao)\s+(?:file|folder|document)\s+(.+)", re.IGNORECASE),
            re.compile(r"(?:read|open|padho)\s+(?:file|document)\s+(.+)", re.IGNORECASE),
        ]
        self._reminder_patterns = [
            re.compile(r"(?:remind\s+me|set\s+a\s+reminder|yaad\s+dilana|alarm|timer)\s+(?:to|at|in|ke\s+liye)?\s*(.+)", re.IGNORECASE),
        ]
        self._browser_patterns = [
            re.compile(r"(?:browse|search\s+for|google|open\s+website)\s+(.+)", re.IGNORECASE),
        ]

    def normalize_text(self, text: str) -> str:
        """Clean Unicode, strip extraneous whitespace, and normalize case."""
        if not text:
            return ""
        # Normalize Unicode characters (e.g. Devanagari or accents)
        normalized = unicodedata.normalize("NFKC", text)
        # Collapse multiple whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def detect_language(self, text: str) -> str:
        """Identify if text is pure English, Devanagari Hindi, or Romanized Hinglish."""
        # Check Devanagari Unicode block (0x0900 - 0x097F)
        if any("\u0900" <= char <= "\u097f" for char in text):
            return "hi"
        # Check Hinglish keywords
        hinglish_words = {"kholo", "chalao", "banao", "padho", "kya", "kaise", "samay", "batao", "yaad", "dilana", "karein", "hain"}
        words = set(re.findall(r"\b[a-zA-Z]+\b", text.lower()))
        if words.intersection(hinglish_words):
            return "hi-en"
        return "en"

    def is_question(self, text: str) -> bool:
        """Determine if user input is an informational question rather than an imperative task."""
        lowered = text.lower().strip()
        if lowered.endswith("?"):
            return True
        question_starters = (
            "what", "why", "how", "when", "where", "who", "which",
            "can you explain", "tell me about", "kya", "kaise", "kyun", "kab", "koun"
        )
        return any(lowered.startswith(qs) for qs in question_starters)

    def classify_intent(self, user_text: str) -> ParsedIntent:
        """Main classification pipeline."""
        normalized = self.normalize_text(user_text)
        lowered = normalized.lower()
        language = self.detect_language(normalized)
        is_q = self.is_question(normalized)

        # 1. Ambiguity / empty check
        if not normalized:
            return ParsedIntent(
                intent_type=IntentType.CLARIFICATION_NEEDED,
                action_type="empty_query",
                confidence=1.0,
                raw_query=user_text,
                normalized_query=normalized,
            )

        # 2. Check for reminders / scheduling
        for pat in self._reminder_patterns:
            m = pat.search(normalized)
            if m:
                return ParsedIntent(
                    intent_type=IntentType.SYSTEM_COMMAND,
                    action_type="schedule_reminder",
                    confidence=0.92,
                    entities={"reminder_text": m.group(1).strip()},
                    is_question=False,
                    detected_language=language,
                    raw_query=user_text,
                    normalized_query=normalized,
                )

        # 3. Check for application launching
        for pat in self._app_launch_patterns:
            m = pat.search(normalized)
            if m:
                target_app = m.group(1).strip()
                # If target is a website URL, redirect to browser
                if target_app.startswith(("http://", "https://", "www.")) or target_app.endswith((".com", ".org", ".net")):
                    return ParsedIntent(
                        intent_type=IntentType.SYSTEM_COMMAND,
                        action_type="open_browser",
                        confidence=0.95,
                        entities={"url": target_app},
                        is_question=False,
                        detected_language=language,
                        raw_query=user_text,
                        normalized_query=normalized,
                    )
                return ParsedIntent(
                    intent_type=IntentType.SYSTEM_COMMAND,
                    action_type="launch_app",
                    confidence=0.95,
                    entities={"app_name": target_app},
                    is_question=False,
                    detected_language=language,
                    raw_query=user_text,
                    normalized_query=normalized,
                )

        # 4. Check for system statistics
        for pat in self._sysinfo_patterns:
            if pat.search(lowered):
                return ParsedIntent(
                    intent_type=IntentType.SYSTEM_COMMAND,
                    action_type="get_system_info",
                    confidence=0.90,
                    is_question=is_q,
                    detected_language=language,
                    raw_query=user_text,
                    normalized_query=normalized,
                )

        # 5. Check for file operations
        for pat in self._file_patterns:
            m = pat.search(normalized)
            if m:
                action = "search_files"
                if "create" in lowered or "banao" in lowered:
                    action = "create_file"
                elif "read" in lowered or "padho" in lowered:
                    action = "read_file"
                return ParsedIntent(
                    intent_type=IntentType.SYSTEM_COMMAND,
                    action_type=action,
                    confidence=0.88,
                    entities={"target": m.group(1) if m.groups() else ""},
                    is_question=is_q,
                    detected_language=language,
                    raw_query=user_text,
                    normalized_query=normalized,
                )

        # 6. Check for complex multi-step instructions (workflow)
        multi_step_cues = [" and then ", " then ", " after that ", " summarize and send ", " find and copy "]
        if any(cue in lowered for cue in multi_step_cues):
            return ParsedIntent(
                intent_type=IntentType.AUTOMATION_WORKFLOW,
                action_type="composite_workflow",
                confidence=0.85,
                is_question=False,
                detected_language=language,
                raw_query=user_text,
                normalized_query=normalized,
            )

        # 7. Default to conversational response
        return ParsedIntent(
            intent_type=IntentType.CONVERSATION,
            action_type="general_chat",
            confidence=0.80,
            is_question=is_q,
            detected_language=language,
            raw_query=user_text,
            normalized_query=normalized,
        )
