"""
Utility functions for the GitHub AI DevOps Agent API.
"""

import hashlib
import re
from datetime import UTC, datetime


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = text.strip("-")
    return text


def compute_fingerprint(content: str) -> str:
    """Compute a stable SHA-256 fingerprint for deduplication."""
    return hashlib.sha256(content.encode()).hexdigest()


def utcnow() -> datetime:
    return datetime.now(UTC)


def mask_secret(value: str, visible: int = 4) -> str:
    """Mask a secret string, keeping only the last N characters visible."""
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]


def parse_repo_full_name(full_name: str) -> tuple[str, str]:
    """Split 'owner/repo' into (owner, repo). Raises ValueError if invalid."""
    parts = full_name.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid repository full name: {full_name!r}")
    return parts[0], parts[1]


def truncate(text: str, max_length: int = 200, suffix: str = "...") -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix
