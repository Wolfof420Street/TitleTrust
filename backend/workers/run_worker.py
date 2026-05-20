from __future__ import annotations

import sys

try:
    from backend.workers.runtime import worker_runtime
except ModuleNotFoundError:
    from workers.runtime import worker_runtime


if __name__ == "__main__":
    if "--healthcheck" in sys.argv:
        raise SystemExit(0 if worker_runtime.healthcheck() else 1)
    worker_runtime.run_forever()
