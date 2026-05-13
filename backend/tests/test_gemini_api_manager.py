from __future__ import annotations

from pathlib import Path

from backend.core.gemini_api_manager import GeminiApiManager


def test_execute_forensic_analysis_uses_cache(tmp_path: Path):
    target = tmp_path / "sample.pdf"
    target.write_bytes(b"same-content")
    manager = GeminiApiManager(
        max_concurrent_requests=1,
        max_calls=5,
        period_seconds=60,
        cache_ttl_seconds=60,
        cache_enabled=True,
    )
    call_count = {"value": 0}

    def callback():
        call_count["value"] += 1
        return {"risk_score": 12, "final_verdict": "GENUINE"}

    first = manager.execute_forensic_analysis(str(target), callback)
    second = manager.execute_forensic_analysis(str(target), callback)

    assert first == second
    assert call_count["value"] == 1


def test_execute_forensic_analysis_does_not_cache_errors(tmp_path: Path):
    target = tmp_path / "sample.pdf"
    target.write_bytes(b"same-content")
    manager = GeminiApiManager(
        max_concurrent_requests=1,
        max_calls=5,
        period_seconds=60,
        cache_ttl_seconds=60,
        cache_enabled=True,
    )
    call_count = {"value": 0}

    def callback():
        call_count["value"] += 1
        return {"error": "rate limited"}

    manager.execute_forensic_analysis(str(target), callback)
    manager.execute_forensic_analysis(str(target), callback)

    assert call_count["value"] == 2
