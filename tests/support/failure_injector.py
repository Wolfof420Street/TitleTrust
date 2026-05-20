from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class FailureInjector:
    """Deterministic fault toggles for backend chaos tests.

    The rules are intentionally simple so the same seedless configuration
    always produces the same failure pattern.
    """

    redis_available: bool = True
    drop_every_n: Optional[int] = None
    duplicate_every_n: Optional[int] = None
    delay_every_n_ms: Optional[int] = None
    malformed_every_n: Optional[int] = None
    fail_xadd_on_n: Optional[int] = None
    fail_publish_on_n: Optional[int] = None
    truncate_stream_at: Optional[int] = None

    def should_drop(self, index: int) -> bool:
        return bool(self.drop_every_n and self.drop_every_n > 0 and index % self.drop_every_n == 0)

    def should_duplicate(self, index: int) -> bool:
        return bool(self.duplicate_every_n and self.duplicate_every_n > 0 and index % self.duplicate_every_n == 0)

    def should_delay(self, index: int) -> bool:
        return bool(self.delay_every_n_ms and self.delay_every_n_ms > 0 and index % self.delay_every_n_ms == 0)

    def should_malformed(self, index: int) -> bool:
        return bool(self.malformed_every_n and self.malformed_every_n > 0 and index % self.malformed_every_n == 0)

    def should_fail_xadd(self, index: int) -> bool:
        return bool(self.fail_xadd_on_n and index == self.fail_xadd_on_n)

    def should_fail_publish(self, index: int) -> bool:
        return bool(self.fail_publish_on_n and index == self.fail_publish_on_n)
