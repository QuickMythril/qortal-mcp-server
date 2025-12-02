"""
Configuration helpers for the Qortal MCP server.

This module centralizes base URL selection, API key loading, default timeouts,
and safety limits. No secrets are stored in the repository; the API key is read
from environment or a local file if present.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Default connection settings
DEFAULT_BASE_URL = os.getenv("QORTAL_BASE_URL", "http://localhost:12391")


def _load_timeout() -> float:
    raw_timeout = os.getenv("QORTAL_HTTP_TIMEOUT")
    if raw_timeout:
        try:
            return float(raw_timeout)
        except ValueError:
            return 10.0
    return 10.0


DEFAULT_TIMEOUT = _load_timeout()

# API key handling
API_KEY_ENV_VAR = "QORTAL_API_KEY"
API_KEY_FILE_ENV_VAR = "QORTAL_API_KEY_FILE"
DEFAULT_API_KEY_FILE = "apikey.txt"

# Safety limits
MAX_NAMES_RETURNED = 100


def load_api_key() -> Optional[str]:
    """
    Load the Qortal API key from environment or a local file.

    Returns:
        The API key string if available, otherwise None. The key is never logged
        or returned to callers.
    """
    env_key = os.getenv(API_KEY_ENV_VAR)
    if env_key:
        return env_key.strip()

    key_path = os.getenv(API_KEY_FILE_ENV_VAR, DEFAULT_API_KEY_FILE)
    if key_path:
        path = Path(key_path)
        if path.is_file():
            return path.read_text(encoding="utf-8").strip() or None

    return None


@dataclass(slots=True)
class QortalConfig:
    """Runtime configuration for Qortal Core access."""

    base_url: str = DEFAULT_BASE_URL
    timeout: float = DEFAULT_TIMEOUT
    api_key: Optional[str] = load_api_key()
    max_names: int = MAX_NAMES_RETURNED


default_config = QortalConfig()
