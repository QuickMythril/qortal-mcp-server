"""Shared validation helpers for Qortal MCP tools."""

from __future__ import annotations

import re
from typing import Optional

# Qortal addresses are Base58, 34 characters, prefixed with "Q".
ADDRESS_REGEX = re.compile(r"^Q[1-9A-HJ-NP-Za-km-z]{33}$")

# Names: allow alnum, space, dollar, dot, dash, underscore per observed Core acceptance.
NAME_MIN_LENGTH = 3
NAME_MAX_LENGTH = 40
NAME_REGEX = re.compile(r"^[A-Za-z0-9$][A-Za-z0-9$._\\- ]{1,38}[A-Za-z0-9$]$")


def is_valid_qortal_address(address: Optional[str]) -> bool:
    """Basic format validation for Qortal addresses."""
    if not address:
        return False
    return bool(ADDRESS_REGEX.fullmatch(address.strip()))


def is_valid_qortal_name(name: Optional[str]) -> bool:
    """Conservative validation for Qortal names."""
    if not name:
        return False
    stripped = name.strip()
    if not (NAME_MIN_LENGTH <= len(stripped) <= NAME_MAX_LENGTH):
        return False
    return bool(NAME_REGEX.fullmatch(stripped))


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
