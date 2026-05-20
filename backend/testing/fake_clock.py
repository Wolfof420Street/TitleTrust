import time


class FakeClock:
    def __init__(self, start: float = None):
        self._t = start if start is not None else time.time()

    def time(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds

    def patch_monkey(self, monkeypatch):
        monkeypatch.setattr("time.time", lambda: self.time())
