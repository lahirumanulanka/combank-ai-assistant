import time
from collections.abc import Callable


class CircuitBreaker:
    def __init__(self, failures_to_open: int = 3, cooldown_s: float = 30, clock: Callable[[], float] = time.monotonic):
        self.failures_to_open = failures_to_open
        self.cooldown_s = cooldown_s
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None

    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        return self._clock() - self._opened_at < self.cooldown_s

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failures_to_open:
            self._opened_at = self._clock()
