from types import SimpleNamespace

from backend.infrastructure.rate_limit_store import InMemoryRateLimitStore
from backend.middleware.rate_limit import _request_key


def test_rate_limit_store_window_enforcement():
    store = InMemoryRateLimitStore()
    key = "test"
    assert store.hit(key, limit=2, window_seconds=60) == 1
    assert store.hit(key, limit=2, window_seconds=60) == 1
    assert store.hit(key, limit=2, window_seconds=60) == 0


def test_request_key_ignores_user_controlled_user_id_header():
    request_a = SimpleNamespace(
        headers={
            "x-forwarded-for": "203.0.113.10",
            "authorization": "Bearer stable-token",
            "x-user-id": "attacker-a",
        },
        client=SimpleNamespace(host="127.0.0.1"),
        url=SimpleNamespace(path="/auth/device-sessions"),
    )
    request_b = SimpleNamespace(
        headers={
            "x-forwarded-for": "203.0.113.10",
            "authorization": "Bearer stable-token",
            "x-user-id": "attacker-b",
        },
        client=SimpleNamespace(host="127.0.0.1"),
        url=SimpleNamespace(path="/auth/device-sessions"),
    )

    assert _request_key(request_a) == _request_key(request_b)


def test_request_key_changes_when_authenticated_principal_changes():
    request_a = SimpleNamespace(
        headers={"authorization": "Bearer token-a"},
        client=SimpleNamespace(host="127.0.0.1"),
        url=SimpleNamespace(path="/auth/device-sessions"),
    )
    request_b = SimpleNamespace(
        headers={"authorization": "Bearer token-b"},
        client=SimpleNamespace(host="127.0.0.1"),
        url=SimpleNamespace(path="/auth/device-sessions"),
    )

    assert _request_key(request_a) != _request_key(request_b)
