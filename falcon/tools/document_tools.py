"""
Document Parsing and Extraction Tools for Falcon.
Safely extracts text, structure, and metadata from documents.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from falcon.security.policy import PermissionLevel
from falcon.security.validation import InputValidator, SecurityValidationError
from falcon.tools.registry import BaseTool


class ParseDocumentTool(BaseTool):
    name = "parse_document"
    description = "Read, parse, and analyze text documents (.txt, .md, .json, .csv, .log) safely."
    permission_level = PermissionLevel.READ_ONLY
    parameters_schema = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the document to parse.",
            },
            "max_lines": {
                "type": "integer",
                "description": "Maximum number of lines to inspect (default 500).",
            },
        },
        "required": ["file_path"],
    }

    def __init__(self, allowed_roots: Optional[List[str]] = None):
        self.allowed_roots = allowed_roots

    async def execute(self, file_path: str, max_lines: int = 500) -> Dict[str, Any]:
        target = InputValidator.validate_path_safety(file_path, self.allowed_roots, is_write_operation=False)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"Document not found: '{target}'")

        ext = target.suffix.lower()
        if ext not in {".txt", ".md", ".json", ".csv", ".log", ".py", ".html", ".xml"}:
            raise ValueError(f"Unsupported document format '{ext}'.")

        with open(target, "r", encoding="utf-8", errors="replace") as f:
            lines = [f.readline() for _ in range(max_lines)]

        content = "".join(lines)
        word_count = len(content.split())
        line_count = len(lines)

        # Detect prompt injection
        is_suspicious, reason = InputValidator.detect_prompt_injection(content)

        result: Dict[str, Any] = {
            "file_path": str(target),
            "extension": ext,
            "line_count": line_count,
            "word_count": word_count,
            "content": content,
            "untrusted_warning": reason if is_suspicious else None,
        }

        # If CSV, parse headers and sample rows
        if ext == ".csv":
            try:
                reader = csv.reader(lines)
                rows = list(reader)
                if rows:
                    result["csv_headers"] = rows[0]
                    result["csv_sample_rows"] = rows[1:6]
            except Exception:
                pass

        return result
