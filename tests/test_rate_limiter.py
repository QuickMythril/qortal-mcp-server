import asyncio

import pytest

from qortal_mcp.rate_limiter import PerKeyRateLimiter


@pytest.mark.asyncio
async def test_per_key_rate_limiter_allows_then_blocks():
    limiter = PerKeyRateLimiter(rate_per_sec=1, burst=1)
    assert await limiter.allow("tool")
    # Immediately requesting again should fail due to no tokens
    assert not await limiter.allow("tool")
    # After waiting ~1s, should allow again
    await asyncio.sleep(1.05)
    assert await limiter.allow("tool")

