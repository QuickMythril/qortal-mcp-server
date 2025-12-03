"""
Configuration helpers for the Qortal MCP server.

This module centralizes base URL selection, API key loading, default timeouts,
and safety limits. No secrets are stored in the repository; the API key is read
from environment or a local file if present.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
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
MAX_TRADE_OFFERS = 100
DEFAULT_TRADE_OFFERS = 50
MAX_QDN_RESULTS = 20
DEFAULT_QDN_RESULTS = 10
MAX_NAME_DATA_PREVIEW = 1000
MAX_ASSETS_RETURNED = 100
DEFAULT_ASSETS_RETURNED = 50
MAX_ASSET_BALANCES = 100
DEFAULT_ASSET_BALANCES = 50
MAX_BLOCK_SUMMARIES = 2000
DEFAULT_BLOCK_SUMMARIES = 1000
MAX_BLOCK_RANGE = 500
DEFAULT_BLOCK_RANGE = 100
MAX_TX_SEARCH_LIMIT = 20
DEFAULT_TX_SEARCH_LIMIT = 20
MAX_GROUPS = 100
DEFAULT_GROUPS = 50
MAX_GROUP_MEMBERS = 100
DEFAULT_GROUP_MEMBERS = 50
MAX_GROUP_EVENTS = 100
DEFAULT_RATE_LIMIT_QPS = 5
LOG_LEVEL = os.getenv("QORTAL_MCP_LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("QORTAL_MCP_LOG_FORMAT", "json")  # json or plain
PER_TOOL_RATE_LIMITS: dict[str, float] = {}


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
    max_trade_offers: int = MAX_TRADE_OFFERS
    default_trade_offers: int = DEFAULT_TRADE_OFFERS
    max_qdn_results: int = MAX_QDN_RESULTS
    default_qdn_results: int = DEFAULT_QDN_RESULTS
    max_name_data_preview: int = MAX_NAME_DATA_PREVIEW
    max_assets: int = MAX_ASSETS_RETURNED
    default_assets: int = DEFAULT_ASSETS_RETURNED
    max_asset_balances: int = MAX_ASSET_BALANCES
    default_asset_balances: int = DEFAULT_ASSET_BALANCES
    max_block_summaries: int = MAX_BLOCK_SUMMARIES
    default_block_summaries: int = DEFAULT_BLOCK_SUMMARIES
    max_block_range: int = MAX_BLOCK_RANGE
    default_block_range: int = DEFAULT_BLOCK_RANGE
    max_tx_search: int = MAX_TX_SEARCH_LIMIT
    default_tx_search: int = DEFAULT_TX_SEARCH_LIMIT
    max_groups: int = MAX_GROUPS
    default_groups: int = DEFAULT_GROUPS
    max_group_members: int = MAX_GROUP_MEMBERS
    default_group_members: int = DEFAULT_GROUP_MEMBERS
    max_group_events: int = MAX_GROUP_EVENTS
    rate_limit_qps: float = DEFAULT_RATE_LIMIT_QPS
    log_level: str = LOG_LEVEL
    log_format: str = LOG_FORMAT
    per_tool_rate_limits: dict[str, float] = field(default_factory=dict)


default_config = QortalConfig()
