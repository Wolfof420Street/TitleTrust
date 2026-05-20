# Background Workers

This directory is reserved for distributed worker runtime (Celery or Dramatiq) with:
- idempotent forensic/geospatial tasks
- retry policy + dead-letter queue routing
- cancellation and status persistence
- correlation-id propagation for traceability

Current phase scaffolds architecture and contracts; production queue runtime should be wired next with Redis broker.
