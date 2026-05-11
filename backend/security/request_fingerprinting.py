"""Request fingerprinting utilities for abuse detection.

Produces correlation-aware fingerprints from request metadata so the backend can
cluster suspicious traffic without relying on a single IP or user agent.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, Optional


_DEFAULT_HEADER_KEYS = (
    "user-agent",
    "accept",
    "accept-language",
    "accept-encoding",
    "x-forwarded-for",
    "x-correlation-id",
    "x-device-id",
    "x-tenant-id",
)


@dataclass(frozen=True)
class RequestFingerprint:
    """Stable request fingerprint used for abuse clustering."""

    fingerprint_id: str
    tenant_id: str
    device_id: str
    ip_address: str
    user_agent: str
    correlation_id: str
    method: str
    path: str
    header_hash: str
    entropy_score: float

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


class RequestFingerprinting:
    """Build stable fingerprints for requests."""

    def __init__(self, header_keys: Iterable[str] = _DEFAULT_HEADER_KEYS) -> None:
        self._header_keys = tuple(header_keys)

    def fingerprint(
        self,
        *,
        tenant_id: str,
        device_id: str,
        ip_address: str,
        user_agent: str,
        correlation_id: str,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> RequestFingerprint:
        normalized_headers = self._normalize_headers(headers or {})
        serialized = json.dumps(
            {
                "tenant_id": tenant_id,
                "device_id": device_id,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "correlation_id": correlation_id,
                "method": method.upper(),
                "path": path,
                "headers": normalized_headers,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        fingerprint_id = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        entropy_score = self._entropy_score(serialized)
        header_hash = hashlib.sha256(
            json.dumps(normalized_headers, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return RequestFingerprint(
            fingerprint_id=fingerprint_id,
            tenant_id=tenant_id,
            device_id=device_id,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
            method=method.upper(),
            path=path,
            header_hash=header_hash,
            entropy_score=entropy_score,
        )

    def _normalize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        normalized: Dict[str, str] = {}
        for key in self._header_keys:
            value = headers.get(key) or headers.get(key.lower()) or headers.get(key.title())
            if value:
                normalized[key.lower()] = value.strip()
        return normalized

    @staticmethod
    def _entropy_score(value: str) -> float:
        if not value:
            return 0.0
        byte_counts: Dict[int, int] = {}
        encoded = value.encode("utf-8")
        for byte in encoded:
            byte_counts[byte] = byte_counts.get(byte, 0) + 1
        total = len(encoded)
        entropy = 0.0
        for count in byte_counts.values():
            probability = count / total
            entropy -= probability * math.log2(probability)
        return round(entropy, 4)
