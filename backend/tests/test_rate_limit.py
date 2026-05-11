from backend.infrastructure.rate_limit_store import InMemoryRateLimitStore


def test_rate_limit_store_window_enforcement():
    store = InMemoryRateLimitStore()
    key = "test"
    assert store.hit(key, limit=2, window_seconds=60) == 1
    assert store.hit(key, limit=2, window_seconds=60) == 0
    assert store.hit(key, limit=2, window_seconds=60) == 0
