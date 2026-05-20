import re
from typing import Any, Dict


SENSITIVE_PATTERNS = [
    re.compile(r"(?i)api[_-]?key\b"),
    re.compile(r"(?i)authorization\b"),
    re.compile(r"(?i)token\b"),
    re.compile(r"(?i)secret\b"),
    re.compile(r"(?i)password\b"),
]


def _redact_str(s: str, max_len: int = 200) -> str:
    # truncate long strings
    if len(s) > max_len:
        s = s[:max_len] + "...[truncated]"
    # simple key=value redaction
    s = re.sub(
        r"(?i)(api[_-]?key|token|secret|authorization|password)\s*=\s*(?:\".*?\"|'.*?'|[^\s,;]+)",
        r"\1=[REDACTED]",
        s,
    )
    return s


def _sanitize(obj: Any):
    if isinstance(obj, dict):
        return {k: _sanitize(v) if not _is_sensitive_key(k) else "[REDACTED]" for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, str):
        return _redact_str(obj)
    return obj


def _is_sensitive_key(key: str) -> bool:
    for pat in SENSITIVE_PATTERNS:
        if pat.search(key):
            return True
    return False


def sanitize_event_payload(payload: Dict) -> Dict:
    """Sanitize event payload: redact sensitive keys and truncate long strings."""
    try:
        return _sanitize(payload)
    except Exception:
        return {"error": "payload_sanitization_failed"}
