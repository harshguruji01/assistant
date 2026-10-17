"""
Advanced User Search Service for HarshGuruJi Chat.
Supports exact username, prefix, partial with/without @, HarshGuruJi ID, and display name matching.
Ranks results with exact matches first, followed by prefix matches and partial matches.
Developed by: HarshGuruJi (Website: https://www.webguruji.online)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from falcon.chat.database import ChatDatabaseManager

logger = logging.getLogger("HarshGuruJi.Chat.Search")


class UserSearchService:
    """Provides high-performance, ranked user search across profiles."""

    def __init__(self, db: ChatDatabaseManager):
        self.db = db

    def search_users(
        self,
        query: str,
        current_user_id: Optional[str] = None,
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        """
        Execute unified search and return ranked user suggestions.
        Query can be:
        - Exact username (e.g. 'rahulkumar' or '@rahulkumar')
        - Prefix username (e.g. 'rah')
        - HarshGuruJi Unique ID (e.g. 'HGJ-7F42K9' or partial '7F42K9')
        - Display Name matching
        """
        if not query or not query.strip():
            return []

        raw_query = query.strip()
        clean_user = raw_query.lstrip("@").lower()
        upper_query = raw_query.upper()

        conn = self.db.get_connection()
        cur = conn.cursor()

        # SQL with ranking logic:
        # Rank 1: Exact username or exact HGJ-ID
        # Rank 2: Username starts with query or HGJ-ID starts with query
        # Rank 3: Display name starts with query
        # Rank 4: Display name or username contains query
        sql = """
            SELECT 
                id, username, hgj_id, display_name, avatar_url, is_online, last_seen_at,
                CASE 
                    WHEN lower(username) = ? OR upper(hgj_id) = ? THEN 1
                    WHEN lower(username) LIKE ? OR upper(hgj_id) LIKE ? THEN 2
                    WHEN lower(display_name) LIKE ? THEN 3
                    WHEN lower(username) LIKE ? OR lower(display_name) LIKE ? THEN 4
                    ELSE 5
                END AS rank_score
            FROM users
            WHERE (
                lower(username) LIKE ? 
                OR upper(hgj_id) LIKE ?
                OR lower(display_name) LIKE ?
            )
            AND (? IS NULL OR id != ?)
            ORDER BY rank_score ASC, display_name ASC
            LIMIT ?;
        """

        prefix_user = f"{clean_user}%"
        contains_user = f"%{clean_user}%"
        prefix_hgj = f"%{upper_query}%"
        prefix_disp = f"{clean_user}%"
        contains_disp = f"%{clean_user}%"

        params = (
            clean_user,
            upper_query,
            prefix_user,
            prefix_hgj,
            prefix_disp,
            contains_user,
            contains_disp,
            contains_user,
            prefix_hgj,
            contains_disp,
            current_user_id,
            current_user_id,
            limit,
        )

        cur.execute(sql, params)
        rows = cur.fetchall()

        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "username": r["username"],
                "hgj_id": r["hgj_id"],
                "display_name": r["display_name"],
                "avatar_url": r["avatar_url"],
                "is_online": bool(r["is_online"]),
                "last_seen_at": r["last_seen_at"],
                "rank_score": r["rank_score"],
            })

        return results
