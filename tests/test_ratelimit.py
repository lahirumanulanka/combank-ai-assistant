import pytest

from app.core.ratelimit import RateLimiter, TokenBucket
from app.core.rbac import Role


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_bucket_allows_burst_up_to_capacity():
    bucket = TokenBucket(capacity=3, refill_per_second=1, clock=FakeClock())

    results = [bucket.try_acquire().allowed for _ in range(3)]

    assert results == [True, True, True]


def test_bucket_denies_when_empty_and_says_how_long_to_wait():
    bucket = TokenBucket(capacity=2, refill_per_second=0.5, clock=FakeClock())
    bucket.try_acquire()
    bucket.try_acquire()

    result = bucket.try_acquire()

    assert result.allowed is False
    assert result.retry_after_s == pytest.approx(2.0)


def test_bucket_refills_over_time():
    clock = FakeClock()
    bucket = TokenBucket(capacity=1, refill_per_second=1, clock=clock)
    bucket.try_acquire()
    assert bucket.try_acquire().allowed is False

    clock.now += 1

    assert bucket.try_acquire().allowed is True


def test_bucket_never_goes_above_capacity():
    clock = FakeClock()
    bucket = TokenBucket(capacity=2, refill_per_second=1, clock=clock)

    clock.now += 100

    results = [bucket.try_acquire().allowed for _ in range(3)]
    assert results == [True, True, False]


def test_each_user_has_their_own_bucket():
    limiter = RateLimiter({Role.VIEWER: (1, 0.1)}, clock=FakeClock())

    assert limiter.check("alice", Role.VIEWER).allowed is True
    assert limiter.check("alice", Role.VIEWER).allowed is False
    assert limiter.check("bob", Role.VIEWER).allowed is True


def test_roles_get_different_limits():
    limiter = RateLimiter({Role.VIEWER: (1, 0.1), Role.ADMIN: (3, 0.1)}, clock=FakeClock())

    viewer = [limiter.check("v", Role.VIEWER).allowed for _ in range(3)]
    admin = [limiter.check("a", Role.ADMIN).allowed for _ in range(3)]

    assert viewer == [True, False, False]
    assert admin == [True, True, True]
