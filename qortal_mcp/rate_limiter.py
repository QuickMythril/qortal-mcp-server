"""Very lightweight in-memory rate limiter (per-process, best-effort)."""

from __future__ import annotations

import asyncio
import time
from typing import Dict


class TokenBucket:
    def __init__(self, rate: float, capacity: float) -> None:
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.timestamp = time.monotonic()
        self._lock = asyncio.Lock()

    async def consume(self, amount: float = 1.0) -> bool:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.timestamp
            self.timestamp = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            if self.tokens >= amount:
                self.tokens -= amount
                return True
            return False


class RateLimiter:
    def __init__(self, rate_per_sec: float, burst: float | None = None) -> None:
        burst = burst if burst is not None else rate_per_sec
        self.bucket = TokenBucket(rate_per_sec, burst)

    async def allow(self) -> bool:
        return await self.bucket.consume()


class PerKeyRateLimiter:
    """Per-key token buckets with a shared configuration."""

    def __init__(self, rate_per_sec: float, burst: float | None = None) -> None:
        self.rate = rate_per_sec
        self.burst = burst if burst is not None else rate_per_sec
        self._limiters: Dict[str, RateLimiter] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        async with self._lock:
            limiter = self._limiters.get(key)
            if limiter is None:
                limiter = RateLimiter(self.rate, self.burst)
                self._limiters[key] = limiter
        return await limiter.allow()

