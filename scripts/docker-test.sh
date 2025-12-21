#!/bin/bash
# Docker deployment testing script
# Verifies that all Docker components are working correctly

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PASSED=0
FAILED=0

test_pass() {
    echo -e "${GREEN}[✓]${NC} $1"
    PASSED=$((PASSED + 1))
}

test_fail() {
    echo -e "${RED}[✗]${NC} $1"
    FAILED=$((FAILED + 1))
}

test_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

echo "╔════════════════════════════════════════════════════════════╗"
echo "║          Docker Deployment Test Suite                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# =============================================================================
# Test 1: Docker files exist
# =============================================================================
echo "[1] Testing Docker configuration files..."

if [ -f "Dockerfile" ]; then
    test_pass "Dockerfile exists"
else
    test_fail "Dockerfile not found"
fi

if [ -f "docker-compose.yml" ]; then
    test_pass "docker-compose.yml exists"
else
    test_fail "docker-compose.yml not found"
fi

if [ -f "docker-compose.prod.yml" ]; then
    test_pass "docker-compose.prod.yml exists"
else
    test_fail "docker-compose.prod.yml not found"
fi

if [ -f ".dockerignore" ]; then
    test_pass ".dockerignore exists"
else
    test_fail ".dockerignore not found"
fi

if [ -f "scripts/docker-entrypoint.sh" ]; then
    test_pass "docker-entrypoint.sh exists"
else
    test_fail "docker-entrypoint.sh not found"
fi

# =============================================================================
# Test 2: Docker Compose validation
# =============================================================================
echo ""
echo "[2] Validating Docker Compose files..."

if docker-compose -f docker-compose.yml config > /dev/null 2>&1; then
    test_pass "docker-compose.yml is valid"
else
    test_fail "docker-compose.yml has syntax errors"
fi

if docker-compose -f docker-compose.prod.yml config > /dev/null 2>&1; then
    test_pass "docker-compose.prod.yml is valid"
else
    test_fail "docker-compose.prod.yml has syntax errors"
fi

# =============================================================================
# Test 3: Build Docker image
# =============================================================================
echo ""
echo "[3] Building Docker image (this may take a few minutes)..."

if docker build -t claims-agent:test --target production . > /dev/null 2>&1; then
    test_pass "Docker image builds successfully (GPU variant)"
else
    test_fail "Docker image build failed"
fi

if docker build -t claims-agent:test-cpu --target cpu-only . > /dev/null 2>&1; then
    test_pass "Docker image builds successfully (CPU variant)"
else
    test_fail "Docker CPU image build failed"
fi

# =============================================================================
# Test 4: Image inspection
# =============================================================================
echo ""
echo "[4] Inspecting built image..."

# Check if non-root user exists
if docker run --rm claims-agent:test id appuser > /dev/null 2>&1; then
    test_pass "Non-root user 'appuser' exists"
else
    test_fail "Non-root user not configured"
fi

# Check if required directories exist
if docker run --rm claims-agent:test ls /app/data/temp > /dev/null 2>&1; then
    test_pass "Required directories created"
else
    test_fail "Required directories missing"
fi

# Check if Python is installed
if docker run --rm claims-agent:test python --version > /dev/null 2>&1; then
    test_pass "Python is installed"
    PYTHON_VERSION=$(docker run --rm claims-agent:test python --version)
    echo "     → $PYTHON_VERSION"
else
    test_fail "Python not installed"
fi

# Check if PaddlePaddle is installed
if docker run --rm claims-agent:test python -c "import paddle" > /dev/null 2>&1; then
    test_pass "PaddlePaddle is installed"
else
    test_fail "PaddlePaddle not installed"
fi

# Check if FastAPI is installed
if docker run --rm claims-agent:test python -c "import fastapi" > /dev/null 2>&1; then
    test_pass "FastAPI is installed"
else
    test_fail "FastAPI not installed"
fi

# =============================================================================
# Test 5: Entrypoint script
# =============================================================================
echo ""
echo "[5] Testing entrypoint script..."

# Check if entrypoint is executable
if docker run --rm claims-agent:test test -x /app/scripts/docker-entrypoint.sh; then
    test_pass "Entrypoint script is executable"
else
    test_fail "Entrypoint script not executable"
fi

# Test help output
if docker run --rm claims-agent:test help 2>&1 | grep -q "Available commands"; then
    test_pass "Entrypoint help works"
else
    test_fail "Entrypoint help failed"
fi

# =============================================================================
# Test 6: GPU support (optional)
# =============================================================================
echo ""
echo "[6] Testing GPU support (optional)..."

if command -v nvidia-smi &> /dev/null; then
    if docker run --rm --gpus all claims-agent:test nvidia-smi > /dev/null 2>&1; then
        test_pass "GPU is accessible in container"
        GPU_INFO=$(docker run --rm --gpus all claims-agent:test nvidia-smi --query-gpu=name --format=csv,noheader)
        echo "     → $GPU_INFO"
    else
        test_warn "GPU not accessible (check nvidia-docker2 installation)"
    fi
else
    test_warn "NVIDIA drivers not detected - skipping GPU tests"
fi

# =============================================================================
# Test 7: Volume mounts
# =============================================================================
echo ""
echo "[7] Testing volume mounts..."

# Create test volume
TEST_VOLUME="claims-test-volume"
docker volume create "$TEST_VOLUME" > /dev/null 2>&1

# Test write to volume
if docker run --rm -v "$TEST_VOLUME:/test" claims-agent:test sh -c "echo 'test' > /test/test.txt"; then
    test_pass "Can write to volume"
else
    test_fail "Cannot write to volume"
fi

# Test read from volume
if docker run --rm -v "$TEST_VOLUME:/test" claims-agent:test cat /test/test.txt | grep -q "test"; then
    test_pass "Can read from volume"
else
    test_fail "Cannot read from volume"
fi

# Cleanup
docker volume rm "$TEST_VOLUME" > /dev/null 2>&1

# =============================================================================
# Test 8: Network connectivity
# =============================================================================
echo ""
echo "[8] Testing network connectivity..."

# Start test network
TEST_NETWORK="claims-test-network"
docker network create "$TEST_NETWORK" > /dev/null 2>&1

# Start Redis for testing
docker run -d --name claims-test-redis --network "$TEST_NETWORK" redis:7-alpine > /dev/null 2>&1
sleep 2

# Test Redis connectivity
if docker run --rm --network "$TEST_NETWORK" -e REDIS_URL=redis://claims-test-redis:6379/0 \
    claims-agent:test python -c "import redis; r = redis.Redis.from_url('redis://claims-test-redis:6379/0'); r.ping()" 2>&1; then
    test_pass "Can connect to Redis"
else
    test_fail "Cannot connect to Redis"
fi

# Cleanup
docker stop claims-test-redis > /dev/null 2>&1
docker rm claims-test-redis > /dev/null 2>&1
docker network rm "$TEST_NETWORK" > /dev/null 2>&1

# =============================================================================
# Test 9: Environment files
# =============================================================================
echo ""
echo "[9] Testing environment configuration..."

if [ -f ".env.example" ]; then
    test_pass ".env.example exists"
else
    test_fail ".env.example not found"
fi

if [ -f ".env.production.example" ]; then
    test_pass ".env.production.example exists"
else
    test_fail ".env.production.example not found"
fi

# =============================================================================
# Test 10: Security checks
# =============================================================================
echo ""
echo "[10] Security checks..."

# Check if running as non-root
USER_ID=$(docker run --rm claims-agent:test id -u)
if [ "$USER_ID" != "0" ]; then
    test_pass "Container runs as non-root user (UID: $USER_ID)"
else
    test_fail "Container runs as root (security risk)"
fi

# Check if no-new-privileges is set in production compose
if grep -q "no-new-privileges:true" docker-compose.prod.yml; then
    test_pass "no-new-privileges security option enabled"
else
    test_warn "Consider adding no-new-privileges security option"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                     Test Results                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo -e "Tests passed: ${GREEN}$PASSED${NC}"
echo -e "Tests failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed! Docker setup is ready.${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Copy .env.example to .env and configure"
    echo "  2. Add credentials to secrets/ directory"
    echo "  3. Run: docker-compose up -d"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please fix the issues above.${NC}"
    exit 1
fi
