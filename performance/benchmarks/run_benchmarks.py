"""Runtime benchmarks for TitleTrust enterprise validation.

Produces measured latency and throughput evidence for the core security and
adaptive abuse control path.
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.session_models import SessionRiskLevel, SessionState
from backend.repositories.token_repository import hash_refresh_token
from backend.security.abuse_detection import AbuseDetectionEngine
from backend.security.anomaly_detection import AnomalyDetectionEngine
from backend.security.request_fingerprinting import RequestFingerprinting


@dataclass
class BenchmarkResult:
    name: str
    iterations: int
    total_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    throughput_ops_sec: float


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return round(ordered[index], 4)


def benchmark_token_hashing(iterations: int = 20_000) -> BenchmarkResult:
    samples: List[float] = []
    start = time.perf_counter()
    for index in range(iterations):
        iteration_start = time.perf_counter()
        hash_refresh_token(f"token-{index}-{index * 7}")
        samples.append((time.perf_counter() - iteration_start) * 1000)
    total_ms = (time.perf_counter() - start) * 1000
    return BenchmarkResult(
        name="token_hashing",
        iterations=iterations,
        total_ms=round(total_ms, 4),
        p50_ms=percentile(samples, 50),
        p95_ms=percentile(samples, 95),
        p99_ms=percentile(samples, 99),
        throughput_ops_sec=round(iterations / (total_ms / 1000.0), 2),
    )


def benchmark_request_fingerprinting(iterations: int = 20_000) -> BenchmarkResult:
    fingerprinting = RequestFingerprinting()
    samples: List[float] = []
    start = time.perf_counter()
    for index in range(iterations):
        iteration_start = time.perf_counter()
        fingerprinting.fingerprint(
            tenant_id="tenant-a",
            device_id="device-a",
            ip_address=f"1.2.3.{index % 255}",
            user_agent="Mozilla/5.0",
            correlation_id=f"corr-{index}",
            method="POST",
            path="/auth/login",
            headers={
                "x-tenant-id": "tenant-a",
                "x-device-id": "device-a",
                "accept": "application/json",
            },
        )
        samples.append((time.perf_counter() - iteration_start) * 1000)
    total_ms = (time.perf_counter() - start) * 1000
    return BenchmarkResult(
        name="request_fingerprinting",
        iterations=iterations,
        total_ms=round(total_ms, 4),
        p50_ms=percentile(samples, 50),
        p95_ms=percentile(samples, 95),
        p99_ms=percentile(samples, 99),
        throughput_ops_sec=round(iterations / (total_ms / 1000.0), 2),
    )


def benchmark_abuse_assessment(iterations: int = 5_000) -> BenchmarkResult:
    engine = AbuseDetectionEngine(AnomalyDetectionEngine(None))
    session = SessionState(
        session_id="session-1",
        user_id="user-1",
        created_at=__import__("datetime").datetime.now(),
        expires_at=__import__("datetime").datetime.now(),
        last_activity_at=__import__("datetime").datetime.now(),
        current_refresh_token_id="token-1",
        token_family="family-1",
        current_ip="1.2.3.4",
        risk_score=5.0,
        risk_level=SessionRiskLevel.LOW,
    )
    samples: List[float] = []
    start = time.perf_counter()
    for index in range(iterations):
        iteration_start = time.perf_counter()
        engine.assess(
            tenant_id="tenant-a",
            device_id="device-a",
            ip_address=f"1.2.3.{index % 255}",
            user_agent="Mozilla/5.0",
            method="GET",
            path="/health",
            correlation_id=f"corr-{index}",
            headers={"x-tenant-id": "tenant-a", "x-device-id": "device-a"},
            session=session,
        )
        samples.append((time.perf_counter() - iteration_start) * 1000)
    total_ms = (time.perf_counter() - start) * 1000
    return BenchmarkResult(
        name="abuse_assessment",
        iterations=iterations,
        total_ms=round(total_ms, 4),
        p50_ms=percentile(samples, 50),
        p95_ms=percentile(samples, 95),
        p99_ms=percentile(samples, 99),
        throughput_ops_sec=round(iterations / (total_ms / 1000.0), 2),
    )


async def benchmark_async_queue(total_jobs: int = 20_000, workers: int = 8) -> BenchmarkResult:
    queue: asyncio.Queue[int | None] = asyncio.Queue()
    for index in range(total_jobs):
        queue.put_nowait(index)
    for _ in range(workers):
        queue.put_nowait(None)

    samples: List[float] = []

    async def worker() -> None:
        while True:
            job = await queue.get()
            if job is None:
                queue.task_done()
                return
            started = time.perf_counter()
            _ = job * 2
            await asyncio.sleep(0)
            samples.append((time.perf_counter() - started) * 1000)
            queue.task_done()

    start = time.perf_counter()
    tasks = [asyncio.create_task(worker()) for _ in range(workers)]
    await queue.join()
    await asyncio.gather(*tasks)
    total_ms = (time.perf_counter() - start) * 1000
    return BenchmarkResult(
        name="async_queue_throughput",
        iterations=total_jobs,
        total_ms=round(total_ms, 4),
        p50_ms=percentile(samples, 50),
        p95_ms=percentile(samples, 95),
        p99_ms=percentile(samples, 99),
        throughput_ops_sec=round(total_jobs / (total_ms / 1000.0), 2),
    )


def build_report(results: List[BenchmarkResult]) -> Dict[str, Any]:
    return {
        "environment": {
            "platform": platform.platform(),
            "python": sys.version,
            "cpu_count": os.cpu_count(),
        },
        "results": [asdict(result) for result in results],
    }


async def main() -> None:
    token = benchmark_token_hashing()
    fingerprint = benchmark_request_fingerprinting()
    abuse = benchmark_abuse_assessment()
    async_queue = await benchmark_async_queue()

    report = build_report([token, fingerprint, abuse, async_queue])
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
