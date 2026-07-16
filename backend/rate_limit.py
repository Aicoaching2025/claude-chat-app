"""A minimal per-IP rate limiter.

This is demo-grade on purpose: in-memory, single-process, resets on
restart. It exists so a public deployment can't be trivially hammered into
running up your Anthropic bill. If you deploy with multiple worker
processes/instances, replace this with a shared store (e.g. Redis) — each
process would otherwise track its own counts.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from . import config


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        hits = self._hits[key]

        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()

        if len(hits) >= self.max_requests:
            retry_after = int(self.window_seconds - (now - hits[0])) + 1
            return False, retry_after

        hits.append(now)
        return True, 0


rate_limiter = RateLimiter(
    max_requests=config.RATE_LIMIT_MAX_REQUESTS,
    window_seconds=config.RATE_LIMIT_WINDOW_SECONDS,
)
