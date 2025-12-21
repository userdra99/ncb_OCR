#!/bin/bash
# Quick start script for Claims Data Entry Agent
# Automates initial setup and deployment

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Claims Data Entry Agent - Quick Start Setup           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# =============================================================================
# Check prerequisites
# =============================================================================
log_info "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    log_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

log_info "Docker: $(docker --version)"
log_info "Docker Compose: $(docker-compose --version)"

# Check for GPU support
if command -v nvidia-smi &> /dev/null; then
    log_info "NVIDIA GPU detected"
    nvidia-smi --query-gpu=name --format=csv,noheader | head -1
    GPU_AVAILABLE=true
else
    log_warn "No NVIDIA GPU detected - will use CPU mode"
    GPU_AVAILABLE=false
fi

echo ""

# =============================================================================
# Environment selection
# =============================================================================
echo "Select deployment mode:"
echo "  1) Development (default)"
echo "  2) Production"
read -p "Enter choice [1]: " MODE_CHOICE
MODE_CHOICE=${MODE_CHOICE:-1}

if [ "$MODE_CHOICE" = "2" ]; then
    DEPLOY_MODE="production"
    COMPOSE_FILE="docker-compose.prod.yml"
    ENV_FILE=".env.production"
else
    DEPLOY_MODE="development"
    COMPOSE_FILE="docker-compose.yml"
    ENV_FILE=".env"
fi

log_info "Deployment mode: $DEPLOY_MODE"
echo ""

# =============================================================================
# Environment file setup
# =============================================================================
if [ ! -f "$ENV_FILE" ]; then
    log_warn "Environment file not found: $ENV_FILE"

    if [ "$DEPLOY_MODE" = "production" ]; then
        if [ -f ".env.production.example" ]; then
            cp .env.production.example "$ENV_FILE"
            log_info "Created $ENV_FILE from template"
        fi
    else
        if [ -f ".env.example" ]; then
            cp .env.example "$ENV_FILE"
            log_info "Created $ENV_FILE from template"
        fi
    fi

    log_warn "Please edit $ENV_FILE with your credentials before continuing"
    read -p "Press Enter after editing the file..."
fi

# =============================================================================
# Secrets setup
# =============================================================================
log_info "Checking secrets directory..."

if [ ! -d "secrets" ]; then
    mkdir -p secrets
    log_info "Created secrets directory"
fi

REQUIRED_SECRETS=(
    "gmail_credentials.json"
    "sheets_credentials.json"
    "drive_credentials.json"
)

MISSING_SECRETS=false
for secret in "${REQUIRED_SECRETS[@]}"; do
    if [ ! -f "secrets/$secret" ]; then
        log_warn "Missing: secrets/$secret"
        MISSING_SECRETS=true
    fi
done

if [ "$MISSING_SECRETS" = true ]; then
    log_warn "Please add the required credential files to the secrets/ directory"
    read -p "Press Enter after adding the files..."
fi

# =============================================================================
# GPU configuration
# =============================================================================
if [ "$GPU_AVAILABLE" = false ] && [ "$DEPLOY_MODE" = "development" ]; then
    log_info "Configuring for CPU-only mode..."

    # Update .env to use CPU
    if grep -q "OCR_USE_GPU=true" "$ENV_FILE"; then
        sed -i 's/OCR_USE_GPU=true/OCR_USE_GPU=false/' "$ENV_FILE"
        log_info "Updated OCR_USE_GPU=false in $ENV_FILE"
    fi
fi

# =============================================================================
# Build and start
# =============================================================================
log_info "Building Docker images..."
docker-compose -f "$COMPOSE_FILE" build

echo ""
log_info "Starting services..."
docker-compose -f "$COMPOSE_FILE" up -d

echo ""
log_info "Waiting for services to be healthy..."
sleep 10

# =============================================================================
# Verify deployment
# =============================================================================
log_info "Verifying deployment..."

# Check Redis
if docker-compose -f "$COMPOSE_FILE" ps redis | grep -q "Up"; then
    log_info "Redis is running"
else
    log_error "Redis failed to start"
    docker-compose -f "$COMPOSE_FILE" logs redis
    exit 1
fi

# Check app
if docker-compose -f "$COMPOSE_FILE" ps app | grep -q "Up"; then
    log_info "Application is running"
else
    log_error "Application failed to start"
    docker-compose -f "$COMPOSE_FILE" logs app
    exit 1
fi

# Check health endpoint
sleep 5
if curl -s -f http://localhost:8080/health > /dev/null; then
    log_info "Health check passed"
else
    log_warn "Health check failed - service may still be starting"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  Deployment Successful!                    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Services:"
echo "  • Application:   http://localhost:8080"
echo "  • Metrics:       http://localhost:9090/metrics"
echo "  • Redis:         localhost:6379"
echo ""
echo "Useful commands:"
echo "  • View logs:     docker-compose -f $COMPOSE_FILE logs -f"
echo "  • Stop services: docker-compose -f $COMPOSE_FILE down"
echo "  • Restart app:   docker-compose -f $COMPOSE_FILE restart app"
echo "  • Shell access:  docker-compose -f $COMPOSE_FILE exec app bash"
echo ""

if [ "$GPU_AVAILABLE" = true ]; then
    echo "GPU Status:"
    docker-compose -f "$COMPOSE_FILE" exec app nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader || true
    echo ""
fi

log_info "Setup complete! Check logs with: docker-compose -f $COMPOSE_FILE logs -f"
