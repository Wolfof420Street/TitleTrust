# Contributing to TitleTrust

TitleTrust is being shaped as a production-grade Flutter and FastAPI repository. Contributions should preserve traceability, security boundaries, and a clear separation between client, API, worker, and persistence concerns.

## Code of Conduct

Be respectful, precise, and professional. Review comments should focus on behavior, risk, maintainability, and evidence.

## Development Setup

Backend:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pytest backend/tests -q
```

Frontend:

```bash
cd frontend/titletrust
flutter pub get
flutter analyze
flutter test
```

## Coding Style

Backend:

* Prefer small route handlers and push business logic into service or repository classes.
* Keep request validation in Pydantic schemas and route dependencies.
* Use the existing Ruff, mypy, pytest, and security-test tooling already present in CI.

Frontend:

* Keep Riverpod providers and controllers narrow in scope.
* Favor explicit asynchronous error handling over silent fallthrough.
* Keep widget tests close to the UI surface they cover.

General:

* Do not commit secrets or API keys.
* Preserve correlation-id propagation and structured logging.
* Update docs when behavior, setup, or deployment assumptions change.

## Branching Strategy

Use GitHub Flow unless the team has already standardized on a stricter release process:

* Branch from `main`.
* Keep branches focused on one logical change.
* Rebase or merge only after CI passes.

## Commit Messages

Use short, descriptive commit messages that explain the user-visible or operational impact.

Examples:

* `docs: add remediation roadmap`
* `test: expand auth controller coverage`
* `ci: add flutter test gate`

## Pull Requests

Every pull request should include:

* A summary of what changed and why.
* The verification steps you ran.
* Screenshots or screen recordings for UI changes.
* Notes on any migration, config, or operational follow-up.

## Issue Reports

Please include:

* The affected environment.
* Exact reproduction steps.
* Relevant logs, trace ids, or correlation ids.
* Expected versus actual behavior.

## Security Reports

Report vulnerabilities through the private security channel used by the project owner or organization. Do not post exploit details in public issues or pull requests.

Refer to [SECURITY_BOUNDARIES.md](SECURITY_BOUNDARIES.md) for the current trust and failure-domain model.