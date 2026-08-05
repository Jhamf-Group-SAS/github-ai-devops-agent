"""
Simple in-memory rate limiter for webhook endpoints.
"""

import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self._calls: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        window = self._calls[key]
        # Remove expired timestamps
        self._calls[key] = [t for t in window if now - t < self.period]
        if len(self._calls[key]) >= self.max_calls:
            return False
        self._calls[key].append(now)
        return True

    def remaining(self, key: str) -> int:
        now = time.monotonic()
        active = [t for t in self._calls[key] if now - t < self.period]
        return max(0, self.max_calls - len(active))


# Default limiter: 100 requests per 60 seconds per key
webhook_limiter = RateLimiter(max_calls=100, period=60.0)
