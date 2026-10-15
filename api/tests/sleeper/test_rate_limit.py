import threading

import pytest

from app.sleeper.rate_limit import RateLimiter
from tests.sleeper.helpers import FakeTime


def make_limiter(max_per_minute: int, fake: FakeTime) -> RateLimiter:
    return RateLimiter(max_per_minute, clock=fake.clock, sleep=fake.sleep)


def test_first_call_does_not_wait() -> None:
    fake = FakeTime()

    make_limiter(600, fake).acquire()

    assert fake.sleeps == []


def test_back_to_back_calls_are_spaced_sixty_over_max_per_minute_seconds_apart() -> None:
    fake = FakeTime()
    limiter = make_limiter(600, fake)

    for _ in range(4):
        limiter.acquire()

    assert fake.sleeps == pytest.approx([0.1, 0.1, 0.1])


def test_waits_only_for_the_remainder_of_the_interval() -> None:
    fake = FakeTime()
    limiter = make_limiter(60, fake)
    limiter.acquire()
    fake.now += 0.25  # the caller did other work for a quarter of the 1s interval

    limiter.acquire()

    assert fake.sleeps == pytest.approx([0.75])


def test_calls_already_spaced_far_enough_apart_never_wait() -> None:
    fake = FakeTime()
    limiter = make_limiter(60, fake)

    for _ in range(3):
        limiter.acquire()
        fake.now += 1.5

    assert fake.sleeps == []


def test_concurrent_callers_each_get_their_own_slot() -> None:
    # Frozen clock: every thread arrives at t=0, so the n-th caller to take the lock must
    # wait n intervals. Any interleaving gives the same set of waits.
    waits: list[float] = []
    waits_lock = threading.Lock()

    def record(seconds: float) -> None:
        with waits_lock:
            waits.append(seconds)

    limiter = RateLimiter(60, clock=lambda: 0.0, sleep=record)
    threads = [threading.Thread(target=limiter.acquire) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(waits) == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]


@pytest.mark.parametrize("max_per_minute", [0, -5])
def test_rejects_a_non_positive_rate(max_per_minute: int) -> None:
    with pytest.raises(ValueError, match="max_per_minute"):
        RateLimiter(max_per_minute)
