"""
Identity & Unique Public Chat ID Generator for HarshGuruJi Chat.
Generates collision-resistant HGJ-XXXXXX identifiers and validates username structures.
Developed by: HarshGuruJi (Website: https://www.webguruji.online)
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import time
from typing import Optional

HGJ_ID_PATTERN = re.compile(r"^HGJ-[0-9A-Z]{6}$")
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{3,30}$")


def generate_hgj_id(salt: Optional[str] = None) -> str:
    """
    Generate a cryptographically collision-resistant public HarshGuruJi chat ID.
    Format: HGJ-XXXXXX (e.g., HGJ-7F42K9)
    Uses high-entropy CSPRNG + epoch timestamp + SHA-256 digest.
    """
    random_bytes = secrets.token_bytes(32)
    timestamp = str(time.time_ns()).encode()
    extra_salt = (salt or str(os.getpid())).encode()

    hasher = hashlib.sha256()
    hasher.update(random_bytes)
    hasher.update(timestamp)
    hasher.update(extra_salt)
    digest = hasher.hexdigest().upper()

    # Take 6 alphanumeric characters avoiding ambiguous glyphs
    charset = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    code = ""
    for i in range(6):
        idx = int(digest[i * 4 : (i + 1) * 4], 16) % len(charset)
        code += charset[idx]

    return f"HGJ-{code}"


def is_valid_hgj_id(hgj_id: str) -> bool:
    """Validate format of HarshGuruJi public ID."""
    if not hgj_id or not isinstance(hgj_id, str):
        return False
    return bool(HGJ_ID_PATTERN.match(hgj_id.strip().upper()))


def sanitize_username(username: str) -> str:
    """Strip leading @ symbol, convert to lowercase, and validate length/characters."""
    clean = username.strip().lstrip("@").lower()
    if not USERNAME_PATTERN.match(clean):
        raise ValueError(
            "Username must be 3-30 characters long and contain only alphanumeric letters and underscores."
        )
    return clean
