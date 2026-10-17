"""
Browser and Web Integration Tools for Falcon.
Safely opens validated websites and executes web queries in default Windows browser.
Developed by: HarshGuruJi
"""

from __future__ import annotations

import urllib.parse
import webbrowser
from typing import Any, Dict
from falcon.security.policy import PermissionLevel
from falcon.security.validation import SecurityValidationError
from falcon.tools.registry import BaseTool


class OpenUrlTool(BaseTool):
    name = "open_url"
    description = "Open a valid website URL in the user's default browser."
    permission_level = PermissionLevel.LOW_RISK
    parameters_schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Full URL to open (must start with http:// or https://).",
            },
        },
        "required": ["url"],
    }

    async def execute(self, url: str) -> Dict[str, Any]:
        target = url.strip()
        if not (target.startswith("http://") or target.startswith("https://")):
            # Auto-prefix https if user provides domain.com
            if "." in target and not target.startswith("//"):
                target = "https://" + target
            else:
                raise SecurityValidationError(f"Invalid URL protocol for '{url}'. Only HTTP/HTTPS are allowed.")

        # Validate parsed URL
        parsed = urllib.parse.urlparse(target)
        if not parsed.netloc:
            raise SecurityValidationError(f"Invalid domain in URL '{target}'.")

        # Open in default system browser
        webbrowser.open(target)
        return {
            "url": target,
            "status": "opened_in_browser",
        }


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web for a given query in the default browser."
    permission_level = PermissionLevel.LOW_RISK
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search keywords or question.",
            },
            "engine": {
                "type": "string",
                "description": "Search engine: 'google' (default) or 'bing' or 'duckduckgo'.",
            },
        },
        "required": ["query"],
    }

    async def execute(self, query: str, engine: str = "google") -> Dict[str, Any]:
        encoded = urllib.parse.quote_plus(query.strip())
        engine_map = {
            "google": f"https://www.google.com/search?q={encoded}",
            "bing": f"https://www.bing.com/search?q={encoded}",
            "duckduckgo": f"https://duckduckgo.com/?q={encoded}",
        }
        search_url = engine_map.get(engine.lower(), engine_map["google"])
        webbrowser.open(search_url)

        return {
            "query": query,
            "engine": engine,
            "search_url": search_url,
            "status": "opened",
        }
