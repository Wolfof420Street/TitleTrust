import json
import time
from backend.queues.redis_queue import RedisQueue
from backend import config


def test_redis_reconnect(monkeypatch):
    # Ensure settings present
    config.settings.REDIS_URL = "redis://fake:6379/0"
    calls = {"connect": 0, "rpush": 0}

    class FakeClient:
        def rpush(self, queue_name, data):
            calls["rpush"] += 1
            calls["last"] = (queue_name, data)
            return 1

        def blpop(self, queue, timeout):
            return None

        def ping(self):
            return True

    def fake_connect(self):
        calls["connect"] += 1
        # Simulate transient failure on first connect, success afterwards
        if calls["connect"] < 2:
            self._client = None
        else:
            self._client = FakeClient()

    monkeypatch.setattr(RedisQueue, "_connect", fake_connect)

    rq = RedisQueue()
    rq.enqueue("testq", {"a": 1})

    assert calls["rpush"] == 1
    qname, raw = calls["last"]
    payload = json.loads(raw)
    assert payload["payload"]["a"] == 1
