import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from app.core.config import get_settings
from app.core.rbac import Role

Clock = Callable[[], float]


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_s: float = 0.0


class TokenBucket:
    def __init__(self, capacity: float, refill_per_second: float, clock: Clock = time.monotonic):
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self._clock = clock
        self._tokens = capacity
        self._updated_at = clock()

    def try_acquire(self) -> RateLimitResult:
        self._refill()
        if self._tokens >= 1:
            self._tokens -= 1
            return RateLimitResult(allowed=True)

        missing = 1 - self._tokens
        return RateLimitResult(allowed=False, retry_after_s=missing / self.refill_per_second)

    def _refill(self) -> None:
        now = self._clock()
        elapsed = now - self._updated_at
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_per_second)
        self._updated_at = now


class RateLimiter:
    def __init__(self, limits: dict[Role, tuple[float, float]], clock: Clock = time.monotonic):
        self._limits = limits
        self._clock = clock
        self._buckets: dict[str, TokenBucket] = {}

    def check(self, user_id: str, role: Role) -> RateLimitResult:
        bucket = self._buckets.get(user_id)
        if bucket is None:
            capacity, refill_per_second = self._limits[role]
            bucket = TokenBucket(capacity, refill_per_second, self._clock)
            self._buckets[user_id] = bucket
        return bucket.try_acquire()


@lru_cache
def get_rate_limiter() -> RateLimiter:
    settings = get_settings()
    return RateLimiter(
        {
            Role.VIEWER: settings.rate_limit_viewer,
            Role.ANALYST: settings.rate_limit_analyst,
            Role.ADMIN: settings.rate_limit_admin,
        }
    )
