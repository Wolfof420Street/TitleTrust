# Backend Agent Components

This file documents the agentic pieces implemented in the `backend/agent` package and their responsibilities (ground truth from the codebase).

Files and responsibilities:

- `backend/agent/marathon_loop.py` — orchestrates the long-running "marathon" investigation loop. Boots and resumes session ticks, schedules Cloud Tasks ticks, and exposes the tick handler invoked by scheduler endpoints.

- `backend/agent/context_loader.py` — responsible for loading and caching contextual knowledge used by agents. It centralizes retrieval of knowledge-base artifacts and material used to ground model prompts.

- `backend/agent/vision.py` — vision-related helpers and structured-output adapters used by forensic and geospatial flows. Contains schema definitions and transformation utilities for model vision outputs.

- `backend/agent/tools.py` — small helpers, prompt templates, and tool adapters used by agent code. These utilities glue the agent prompt/response handling to the rest of the services.

Notes and next steps:

- The agent module is exercised by `backend/services/marathon_service.py` and the audit/background-job flows in `backend/services/background_job_service.py`.
- For maintainers: treat `backend/agent` as the place for model-specific orchestration and purely agent-centric logic; keep I/O, persistence, and scheduling in services and repositories.
