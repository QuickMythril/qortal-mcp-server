import os
import sys

import pytest

# Ensure repository root is on sys.path before importing project modules.
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from qortal_mcp.metrics import default_metrics  # noqa: E402


@pytest.fixture(autouse=True)
def reset_metrics():
    default_metrics.reset()
    yield
    default_metrics.reset()
