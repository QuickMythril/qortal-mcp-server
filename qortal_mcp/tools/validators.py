"""Shared validation helpers for Qortal MCP tools."""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

# Qortal addresses are Base58, 34 characters, prefixed with "Q".
ADDRESS_REGEX = re.compile(r"^Q[1-9A-HJ-NP-Za-km-z]{33}$")
BASE58_REGEX = re.compile(r"^[1-9A-HJ-NP-Za-km-z]+$")

NAME_MIN_LENGTH = 3
NAME_MAX_LENGTH = 40
ZERO_WIDTH_CHARS = "\u200b\u200c\u200d\u2060\ufeff"
ZERO_WIDTH_REGEX = re.compile(f"[{ZERO_WIDTH_CHARS}]")


def is_valid_qortal_address(address: Optional[str]) -> bool:
    """Basic format validation for Qortal addresses."""
    if not address:
        return False
    return bool(ADDRESS_REGEX.fullmatch(address.strip()))


def _normalize_name(value: str) -> str:
    """Approximate Core's Unicode.normalize: NFKC, remove zero-width, collapse whitespace."""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = ZERO_WIDTH_REGEX.sub("", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def is_valid_qortal_name(name: Optional[str]) -> bool:
    """Validate names similar to Core: length 3-40 bytes and normalized form unchanged."""
    if not name or not isinstance(name, str):
        return False
    normalized = _normalize_name(name)
    # Reject if normalization changes the input (matches Core's NAME_NOT_NORMALIZED check)
    if normalized != name:
        return False
    encoded_len = len(name.encode("utf-8"))
    return NAME_MIN_LENGTH <= encoded_len <= NAME_MAX_LENGTH


def clamp_limit(value: Optional[int], *, default: int, max_value: int) -> int:
    """Clamp limit/offset-style integers to configured bounds."""
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed < 0:
        return default
    return min(parsed, max_value)


def is_base58_string(value: Optional[str], *, min_length: int = 1, max_length: Optional[int] = None) -> bool:
    """Validate a Base58 string using a simple character check and length bounds."""
    if not value or not isinstance(value, str):
        return False
    if not BASE58_REGEX.fullmatch(value):
        return False
    length = len(value)
    if length < min_length:
        return False
    if max_length is not None and length > max_length:
        return False
    return True
