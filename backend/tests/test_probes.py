import sys
import types

# Provide a fake firebase module and a fake backend.services.firebase to avoid
# importing firebase_admin during tests.
fake_fb = types.ModuleType("backend.services.firebase")

class _FakeDB:
    def collection(self, name):
        class C:
            def limit(self, n):
                return self

            def get(self):
                return [1]

        return C()

fake_fb.db = _FakeDB()
sys.modules["backend.services.firebase"] = fake_fb
sys.modules["services.firebase"] = fake_fb

import backend.api.health_router as health_router


def test_liveness():
    resp = health_router.liveness_check()
    assert isinstance(resp, dict)
    assert resp.get("status") == "alive"


def test_readiness_healthy(monkeypatch):
    class DummyColl:
        def limit(self, n):
            return self

        def get(self):
            return [1]


    class DummyDB:
        def collection(self, name):
            return DummyColl()


    monkeypatch.setattr(health_router, "db", DummyDB())
    resp = health_router.readiness_check()
    assert isinstance(resp, dict)
    assert resp.get("status") == "ready"


def test_readiness_degraded(monkeypatch):
    class BadDB:
        def collection(self, name):
            raise Exception("unavailable")


    monkeypatch.setattr(health_router, "db", BadDB())
    resp = health_router.readiness_check()
    assert isinstance(resp, dict)
    assert resp.get("status") == "degraded"
