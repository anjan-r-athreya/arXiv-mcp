"""Simple rate limiter for API calls."""

from __future__ import annotations

import time


class RateLimiter:
    """Enforces a minimum interval between calls."""

    def __init__(self, min_interval: float = 3.0) -> None:
        self._min_interval = min_interval
        self._last_call: float = 0.0

    def wait(self) -> None:
        """Block until enough time has passed since the last call."""
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()
