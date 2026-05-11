from __future__ import annotations

try:
    from backend.workers.runtime import worker_runtime
except ModuleNotFoundError:
    from workers.runtime import worker_runtime


if __name__ == "__main__":
    worker_runtime.run_forever()
