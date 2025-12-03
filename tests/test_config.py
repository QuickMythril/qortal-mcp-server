import os
from pathlib import Path

from qortal_mcp.config import (
    _load_timeout,
    _parse_public_nodes,
    load_api_key,
    QortalConfig,
)


def test_load_timeout_invalid_env(monkeypatch):
    monkeypatch.setenv("QORTAL_HTTP_TIMEOUT", "not-a-number")
    assert _load_timeout() == 10.0  # falls back to default on parse error


def test_load_timeout_valid_env(monkeypatch):
    monkeypatch.setenv("QORTAL_HTTP_TIMEOUT", "5.5")
    assert _load_timeout() == 5.5


def test_load_api_key_env_over_file(monkeypatch, tmp_path):
    # Env var wins over file
    monkeypatch.setenv("QORTAL_API_KEY", "env-key")
    monkeypatch.setenv("QORTAL_API_KEY_FILE", str(tmp_path / "apikey.txt"))
    assert load_api_key() == "env-key"


def test_load_api_key_from_file(monkeypatch, tmp_path):
    key_file = tmp_path / "apikey.txt"
    key_file.write_text("file-key", encoding="utf-8")
    monkeypatch.delenv("QORTAL_API_KEY", raising=False)
    monkeypatch.setenv("QORTAL_API_KEY_FILE", str(key_file))
    assert load_api_key() == "file-key"


def test_default_config_uses_loaded_key(monkeypatch, tmp_path):
    key_file = tmp_path / "apikey.txt"
    key_file.write_text("file-key", encoding="utf-8")
    monkeypatch.setenv("QORTAL_API_KEY_FILE", str(key_file))
    # load_api_key will see the file after monkeypatch
    key = load_api_key()
    assert key == "file-key"
    cfg = QortalConfig(api_key=key)
    assert cfg.api_key == "file-key"


def test_parse_public_nodes():
    raw = " https://a.example.com , , https://b.example.com ,"
    assert _parse_public_nodes(raw) == ["https://a.example.com", "https://b.example.com"]


def test_qortal_config_public_nodes_opt_in():
    cfg = QortalConfig(
        base_url="http://primary",
        public_nodes=["http://fallback"],
        allow_public_fallback=True,
    )
    assert cfg.allow_public_fallback is True
    assert cfg.public_nodes == ["http://fallback"]
