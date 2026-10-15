"""Client-side throttle that keeps us under Sleeper's request ceiling."""

import threading
import time
from collections.abc import Callable


class RateLimiter:
    """Spaces calls at least `60 / max_per_minute` seconds apart.

    Even spacing (rather than a token bucket that allows bursts) is the simplest scheme that
    can never exceed the per-minute ceiling in any 60-second window, and its waits are easy to
    predict and test. Each caller reserves the next free time slot while holding the lock, then
    sleeps *outside* the lock, so concurrent callers queue up without blocking each other's
    bookkeeping.
    """

    def __init__(
        self,
        max_per_minute: int,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_per_minute <= 0:
            raise ValueError(f"max_per_minute must be positive, got {max_per_minute}")
        self.interval = 60.0 / max_per_minute
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_slot = float("-inf")  # the very first call never waits

    def acquire(self) -> None:
        """Block until this caller's slot arrives."""
        with self._lock:
            now = self._clock()
            slot = max(now, self._next_slot)
            self._next_slot = slot + self.interval
        wait = slot - now
        if wait > 0:
            self._sleep(wait)
