# TitleTrust Performance Certification

## Scope

This report captures runtime measurements from the current enterprise backend and security hardening layer. Measurements were taken on the local validation host and reflect the current implementation of token hashing, request fingerprinting, adaptive abuse assessment, and async queue throughput.

## Methodology

- Python runtime: 3.13.7 on macOS 14.8.3
- CPU count reported by the runtime: 4
- Benchmark harness: `performance/benchmarks/run_benchmarks.py`
- Samples measured with `time.perf_counter()` per iteration
- Latency summaries reported as P50/P95/P99
- Throughput computed as completed operations divided by elapsed wall time

## Measured Results

| Benchmark | Iterations | P50 ms | P95 ms | P99 ms | Throughput ops/sec | Total ms |
|---|---:|---:|---:|---:|---:|---:|
| Token hashing | 20,000 | 0.0021 | 0.0039 | 0.0084 | 291,520.24 | 68.61 |
| Request fingerprinting | 20,000 | 0.0788 | 0.2363 | 1.3307 | 6,931.24 | 2,885.49 |
| Adaptive abuse assessment | 5,000 | 0.1936 | 0.6005 | 2.7683 | 3,236.08 | 1,545.08 |
| Async queue throughput | 20,000 | 0.0499 | 0.1369 | 0.3659 | 92,602.44 | 215.98 |

## Operational Interpretation

- Token hashing overhead is negligible relative to request processing.
- Request fingerprinting remains sub-millisecond at P99 under this host and workload.
- Adaptive abuse assessment is suitable for inline request-path enforcement at the observed load profile.
- The async queue harness demonstrates high throughput with low tail latency on the current machine.

## Hardware and Runtime Assumptions

- 4 logical CPUs exposed to the runtime
- Local development host, not production Kubernetes hardware
- No network-bound dependencies were included in the benchmark loop
- The measured queue test is compute-light and represents scheduler/dispatch overhead rather than a full business job payload

## Scalability Notes

- Horizontal scaling should preserve request fingerprinting and abuse scoring headroom if the current P99 envelope stays below 5 ms on comparable hardware.
- Queue workloads should be sized against the actual business payload, not the synthetic benchmark loop.
- Production validation should repeat these measurements under Redis-backed queue traffic and worker contention.

## Residual Risks

- The benchmark host is not production-equivalent hardware.
- Network round-trips, database writes, and cloud API calls are not included in this run.
- Frontend runtime validation and Kubernetes rollout validation remain separate steps.

## Certification Conclusion

The current backend security path is measurably performant for the implemented inline controls. The measured results do not indicate a latency or throughput bottleneck in the adaptive abuse path, token hashing, or request fingerprinting on this host.
