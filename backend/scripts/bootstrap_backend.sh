#!/bin/bash

# TitleTrust Backend Bootstrap Script
# Validates dependencies, services, and runtime readiness

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
BACKEND_DIR="${PROJECT_ROOT}/backend"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

# 1. Check Python version
log_info "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
if [[ "$python_version" == 3.* ]]; then
    log_success "Python $python_version"
else
    log_error "Python 3.x not found"
    exit 1
fi

# 2. Check virtual environment
if [[ -z "$VIRTUAL_ENV" ]]; then
    log_warning "Not in virtual environment. Using system Python."
fi

# 3. Validate backend structure
log_info "Validating backend structure..."
for dir in api core domain services repositories workers; do
    if [[ -d "$BACKEND_DIR/$dir" ]]; then
        log_success "Directory: $dir"
    else
        log_error "Missing directory: $dir"
        exit 1
    fi
done

# 4. Install/upgrade dependencies
log_info "Installing dependencies..."
python3 -m pip install --upgrade pip --quiet
python3 -m pip install -r "${PROJECT_ROOT}/backend/requirements.txt" --quiet
log_success "Dependencies installed"

# 5. Compile Python code
log_info "Compiling Python code..."
if python3 -m compileall "$BACKEND_DIR" > /dev/null 2>&1; then
    log_success "All Python files compile successfully"
else
    log_error "Python compilation failed"
    exit 1
fi

# 6. Test Redis connectivity
log_info "Testing Redis connectivity..."
python3 << 'EOF'
import redis
import os
import sys

redis_host = os.environ.get('REDIS_HOST', 'localhost')
redis_port = int(os.environ.get('REDIS_PORT', '6379'))

try:
    r = redis.Redis(host=redis_host, port=redis_port, socket_connect_timeout=5, decode_responses=True)
    r.ping()
    print(f"  ✓ Redis available at {redis_host}:{redis_port}")
except Exception as e:
    print(f"  ⚠ Redis not available: {e}")
    print("    Start Redis with: docker-compose up -d redis")
    # Don't exit - allow local dev to continue without Redis
EOF

# 7. Check configuration
log_info "Checking configuration..."
python3 << 'EOF'
import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

try:
    from config import settings
    print(f"  ✓ Settings loaded (ENV={settings.ENV})")
    print(f"  ✓ LOG_LEVEL={settings.LOG_LEVEL}")
except Exception as e:
    print(f"  ✗ Configuration error: {e}")
    sys.exit(1)
EOF

if [[ $? -ne 0 ]]; then
    exit 1
fi

# 8. Test critical imports
log_info "Testing critical imports..."
python3 << 'EOF'
import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

modules_to_test = [
    'config',
    'logging_config',
    'main',
    'auth',
    'models',
    'services.firebase',
    'repositories.session_repository',
    'repositories.user_repository',
    'routers.audit',
    'agent.marathon_loop',
    'workers.runtime',
]

failed = []
for module in modules_to_test:
    try:
        __import__(module)
        print(f"  ✓ {module}")
    except Exception as e:
        print(f"  ✗ {module}: {e}")
        failed.append((module, str(e)))

if failed:
    print(f"\n✗ Import failures:")
    for mod, err in failed:
        print(f"  {mod}: {err}")
    sys.exit(1)
EOF

if [[ $? -ne 0 ]]; then
    exit 1
fi

# 9. Run tests (optional)
if [[ "${RUN_TESTS:-true}" == "true" ]]; then
    log_info "Running test suite..."
    if python3 -m pytest -q backend/tests 2>/dev/null; then
        log_success "All tests passed"
    else
        log_warning "Some tests failed or pytest not available"
    fi
fi

# 10. Summary
log_info "Bootstrap validation complete!"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}TitleTrust Backend is ready for development${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo "Next steps:"
echo "  1. Start Redis (if not running): docker-compose up -d redis"
echo "  2. Run API server: python -m backend.main"
echo "  3. Run worker: python -m backend.workers.run_worker"
echo "  4. Run tests: pytest backend/tests"
echo ""
