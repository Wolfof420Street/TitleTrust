PYTHON ?= python3
PIP ?= python3 -m pip
VENV_DIR ?= venv

.PHONY: help init install install-dev test compile lint bootstrap clean verify
.PHONY: backend-run backend-test backend-compile worker test-verbose test-coverage format docker-up docker-down docker-logs redis-cli

help:
	@echo "TitleTrust Development Commands"
	@echo "================================"
	@echo "make init                - Initialize development environment"
	@echo "make install             - Install production dependencies"
	@echo "make install-dev         - Install development dependencies"
	@echo "make bootstrap           - Bootstrap and validate backend"
	@echo "make compile             - Compile all Python code"
	@echo "make test                - Run test suite"
	@echo "make lint                - Run linters"
	@echo "make worker              - Run background worker"
	@echo "make backend-run         - Run FastAPI backend server"
	@echo "make docker-up           - Start Docker Compose services"
	@echo "make docker-down         - Stop Docker Compose services"
	@echo "make clean               - Clean build artifacts"

init: install bootstrap
	@echo "✓ Development environment initialized"

install:
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt

install-dev:
	$(PIP) install -r backend/requirements.txt
	$(PIP) install pytest pytest-asyncio pytest-cov black flake8 mypy

bootstrap:
	@bash backend/scripts/bootstrap_backend.sh

compile:
	$(PYTHON) -m compileall backend

test:
	$(PYTHON) -m pytest -q backend/tests --tb=short

test-verbose:
	$(PYTHON) -m pytest -v backend/tests

test-coverage:
	$(PYTHON) -m pytest backend/tests --cov=backend --cov-report=html --cov-report=term-missing

lint:
	@echo "Running code quality checks..."
	$(PYTHON) -m flake8 backend --max-line-length=100 --exclude=__pycache__
	$(PYTHON) -m black --check backend

format:
	$(PYTHON) -m black backend

backend-run:
	$(PYTHON) -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

backend-test:
	$(PYTHON) -m pytest -q backend/tests

backend-compile:
	$(PYTHON) -m compileall backend

worker:
	$(PYTHON) backend/workers/run_worker.py

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

redis-cli:
	docker-compose exec redis redis-cli

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type d -name ".mypy_cache" -delete
	find . -type d -name "*.egg-info" -delete
	rm -rf build/ dist/ htmlcov/

verify: compile bootstrap test
	@echo "✓ All verification checks passed"
