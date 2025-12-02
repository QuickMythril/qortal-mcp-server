import logging

from qortal_mcp.config import default_config


def test_logging_level_config():
    level = getattr(logging, default_config.log_level.upper(), logging.INFO)
    assert level in (
        logging.DEBUG,
        logging.INFO,
        logging.WARNING,
        logging.ERROR,
        logging.CRITICAL,
    )
