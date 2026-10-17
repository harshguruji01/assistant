"""
File and Directory Tools for Falcon.
Provides secure path-validated file operations, search, and inspection.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import datetime
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
from falcon.security.policy import PermissionLevel
from falcon.security.validation import InputValidator, SecurityValidationError
from falcon.tools.registry import BaseTool


class ListDirectoryTool(BaseTool):
    name = "list_directory"
    description = "List files and folders in a given directory with their sizes and modification times."
    permission_level = PermissionLevel.READ_ONLY
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the directory to inspect (e.g. '.' or 'C:/Users/.../Desktop').",
            },
            "max_items": {
                "type": "integer",
                "description": "Maximum number of items to return (default 50).",
            },
        },
        "required": ["path"],
    }

    def __init__(self, allowed_roots: Optional[List[str]] = None):
        self.allowed_roots = allowed_roots

    async def execute(self, path: str, max_items: int = 50) -> Dict[str, Any]:
        target = InputValidator.validate_path_safety(path, self.allowed_roots, is_write_operation=False)
        if not target.exists() or not target.is_dir():
            raise FileNotFoundError(f"Directory not found: '{target}'")

        items = []
        for entry in os.scandir(target):
            try:
                stat = entry.stat()
                items.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size_bytes": stat.st_size if not entry.is_dir() else None,
                    "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
            except Exception:
                continue
            if len(items) >= max_items:
                break

        return {
            "path": str(target),
            "total_listed": len(items),
            "items": items,
        }


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read the textual content of a file with safety boundaries and length limits."
    permission_level = PermissionLevel.READ_ONLY
    parameters_schema = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to read.",
            },
            "max_bytes": {
                "type": "integer",
                "description": "Maximum number of bytes to read (default 100000).",
            },
        },
        "required": ["file_path"],
    }

    def __init__(self, allowed_roots: Optional[List[str]] = None):
        self.allowed_roots = allowed_roots

    async def execute(self, file_path: str, max_bytes: int = 100000) -> Dict[str, Any]:
        target = InputValidator.validate_path_safety(file_path, self.allowed_roots, is_write_operation=False)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"File not found: '{target}'")

        with open(target, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_bytes)

        # Check for prompt injection in external untrusted file
        is_suspicious, reason = InputValidator.detect_prompt_injection(content)

        return {
            "file_path": str(target),
            "content": content,
            "truncated": len(content) >= max_bytes,
            "untrusted_warning": reason if is_suspicious else None,
        }


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Create or write text content to a specified file."
    permission_level = PermissionLevel.MEDIUM_RISK
    parameters_schema = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the destination file.",
            },
            "content": {
                "type": "string",
                "description": "Text content to write.",
            },
            "append": {
                "type": "boolean",
                "description": "If true, append to existing content instead of overwriting.",
            },
        },
        "required": ["file_path", "content"],
    }

    def __init__(self, allowed_roots: Optional[List[str]] = None):
        self.allowed_roots = allowed_roots

    async def execute(self, file_path: str, content: str, append: bool = False) -> Dict[str, Any]:
        target = InputValidator.validate_path_safety(file_path, self.allowed_roots, is_write_operation=True)
        target.parent.mkdir(parents=True, exist_ok=True)

        mode = "a" if append else "w"
        with open(target, mode, encoding="utf-8") as f:
            f.write(content)

        return {
            "file_path": str(target),
            "bytes_written": len(content.encode("utf-8")),
            "mode": "append" if append else "overwrite",
            "success": True,
        }


class SearchFilesTool(BaseTool):
    name = "search_files"
    description = "Recursively search for files matching a filename pattern or keyword."
    permission_level = PermissionLevel.READ_ONLY
    parameters_schema = {
        "type": "object",
        "properties": {
            "root_dir": {
                "type": "string",
                "description": "Root directory to start searching in.",
            },
            "pattern": {
                "type": "string",
                "description": "Wildcard pattern (e.g. '*.txt', '*report*').",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of search results (default 30).",
            },
        },
        "required": ["root_dir", "pattern"],
    }

    def __init__(self, allowed_roots: Optional[List[str]] = None):
        self.allowed_roots = allowed_roots

    async def execute(self, root_dir: str, pattern: str, max_results: int = 30) -> Dict[str, Any]:
        target = InputValidator.validate_path_safety(root_dir, self.allowed_roots, is_write_operation=False)
        if not target.exists() or not target.is_dir():
            raise FileNotFoundError(f"Root search directory not found: '{target}'")

        matches = []
        for p in target.rglob(pattern):
            if p.is_file():
                matches.append(str(p))
                if len(matches) >= max_results:
                    break

        return {
            "root_dir": str(target),
            "pattern": pattern,
            "match_count": len(matches),
            "matches": matches,
        }


class MoveFileTool(BaseTool):
    name = "move_file"
    description = "Move or rename a file with safety collision checks."
    permission_level = PermissionLevel.MEDIUM_RISK
    parameters_schema = {
        "type": "object",
        "properties": {
            "source_path": {
                "type": "string",
                "description": "Source file path.",
            },
            "destination_path": {
                "type": "string",
                "description": "Destination file path.",
            },
            "overwrite": {
                "type": "boolean",
                "description": "Whether to overwrite existing destination (default false).",
            },
        },
        "required": ["source_path", "destination_path"],
    }

    def __init__(self, allowed_roots: Optional[List[str]] = None):
        self.allowed_roots = allowed_roots

    async def execute(self, source_path: str, destination_path: str, overwrite: bool = False) -> Dict[str, Any]:
        src = InputValidator.validate_path_safety(source_path, self.allowed_roots, is_write_operation=False)
        dest = InputValidator.validate_path_safety(destination_path, self.allowed_roots, is_write_operation=True)

        if not src.exists():
            raise FileNotFoundError(f"Source file does not exist: '{src}'")

        if dest.exists() and not overwrite:
            raise FileExistsError(f"Destination '{dest}' already exists and overwrite is False.")

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))

        return {
            "source": str(src),
            "destination": str(dest),
            "status": "moved",
        }
