import pytest

from qortal_mcp.tools import validators


def test_address_validation():
    assert validators.is_valid_qortal_address("QgB7zMfujQMLkisp1Lc8PBkVYs75sYB3vV")
    assert not validators.is_valid_qortal_address("invalid")
    assert not validators.is_valid_qortal_address(None)


def test_name_validation():
    assert validators.is_valid_qortal_name("valid-name_123")
    assert not validators.is_valid_qortal_name("no")  # too short
    assert not validators.is_valid_qortal_name("!bad")  # invalid char


def test_clamp_limit():
    assert validators.clamp_limit(None, default=10, max_value=20) == 10
    assert validators.clamp_limit(5, default=10, max_value=20) == 5
    assert validators.clamp_limit(50, default=10, max_value=20) == 20
    assert validators.clamp_limit(-1, default=10, max_value=20) == 10
