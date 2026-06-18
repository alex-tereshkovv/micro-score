"""Small in-memory login limiter for the local API prototype."""

from __future__ import annotations

from collections.abc import Callable
from math import ceil
from threading import Lock
import time


class LoginRateLimiter:
    def __init__(
        self,
        *,
        max_attempts: int = 5,
        window_seconds: float = 60.0,
        block_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self.clock = clock
        self._attempts: dict[str, list[float]] = {}
        self._blocked_until: dict[str, float] = {}
        self._lock = Lock()

    def retry_after(self, key: str) -> int:
        now = self.clock()
        with self._lock:
            blocked_until = self._blocked_until.get(key, 0.0)
            if blocked_until <= now:
                self._blocked_until.pop(key, None)
                return 0
            return max(1, ceil(blocked_until - now))

    def record_failure(self, key: str) -> int:
        now = self.clock()
        cutoff = now - self.window_seconds
        with self._lock:
            attempts = [stamp for stamp in self._attempts.get(key, []) if stamp > cutoff]
            attempts.append(now)
            if len(attempts) >= self.max_attempts:
                self._attempts.pop(key, None)
                self._blocked_until[key] = now + self.block_seconds
                return max(1, ceil(self.block_seconds))
            self._attempts[key] = attempts
            return 0

    def record_success(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)
            self._blocked_until.pop(key, None)
