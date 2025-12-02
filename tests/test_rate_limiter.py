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


@pytest.mark.asyncio
async def test_per_tool_override():
    limiter = PerKeyRateLimiter(rate_per_sec=10, burst=5, per_tool={"slow_tool": 0.1})
    # Trigger creation of limiters
    assert await limiter.allow("slow_tool")
    assert await limiter.allow("fast_tool")
    slow = limiter._limiters["slow_tool"]
    fast = limiter._limiters["fast_tool"]
    assert slow.bucket.rate == pytest.approx(0.1)
    assert fast.bucket.rate == pytest.approx(10)
