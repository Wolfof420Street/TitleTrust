#!/usr/bin/env bash
set -euo pipefail

echo "Running TitleTrust smoke checks"

# health endpoints
echo "Checking liveness"
curl --fail --silent http://localhost:8080/health/live || { echo "Liveness failed"; exit 2; }

echo "Checking readiness"
if curl --fail --silent http://localhost:8080/health/ready | grep -q ready; then
  echo "Readiness OK"
else
  echo "Readiness degraded or failed"
  exit 3
fi

# metrics
echo "Top metrics sample:"
curl --silent http://localhost:8080/metrics | head -n 20

echo "Smoke checks complete"
