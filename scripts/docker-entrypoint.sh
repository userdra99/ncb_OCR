#!/bin/bash
# Docker entrypoint script for Claims Data Entry Agent
# Handles startup, health checks, and graceful shutdown

set -e

# Color output for better visibility
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# Wait for dependencies
# =============================================================================
wait_for_redis() {
    log_info "Waiting for Redis to be ready..."

    REDIS_HOST=$(echo "$REDIS_URL" | sed -E 's/redis:\/\/([^:]+).*/\1/')
    REDIS_PORT=$(echo "$REDIS_URL" | sed -E 's/redis:\/\/[^:]+:([0-9]+).*/\1/' || echo "6379")

    MAX_RETRIES=30
    RETRY_COUNT=0

    until python -c "import redis; r = redis.Redis(host='$REDIS_HOST', port=$REDIS_PORT); r.ping()" 2>/dev/null; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
            log_error "Redis is not available after $MAX_RETRIES attempts"
            exit 1
        fi
        log_warn "Redis is unavailable - sleeping (attempt $RETRY_COUNT/$MAX_RETRIES)"
        sleep 2
    done

    log_info "Redis is ready!"
}

# =============================================================================
# Setup
# =============================================================================
setup_directories() {
    log_info "Setting up directories..."

    # Create necessary directories if they don't exist
    mkdir -p /app/data/temp
    mkdir -p /app/logs

    # Cleanup old temp files if configured
    if [ -n "$TEMP_FILE_MAX_AGE_HOURS" ]; then
        log_info "Cleaning up temp files older than ${TEMP_FILE_MAX_AGE_HOURS} hours..."
        find /app/data/temp -type f -mmin +$((TEMP_FILE_MAX_AGE_HOURS * 60)) -delete 2>/dev/null || true
    fi

    log_info "Directories ready"
}

check_secrets() {
    log_info "Checking secrets configuration..."

    # Check if required secret files exist (only in production)
    if [ "$APP_ENV" = "production" ]; then
        REQUIRED_SECRETS=(
            "$GMAIL_CREDENTIALS_PATH"
            "$SHEETS_CREDENTIALS_PATH"
            "$DRIVE_CREDENTIALS_PATH"
        )

        for secret in "${REQUIRED_SECRETS[@]}"; do
            if [ -n "$secret" ] && [ ! -f "$secret" ]; then
                log_error "Required secret file not found: $secret"
                exit 1
            fi
        done

        log_info "All required secrets are present"
    else
        log_warn "Running in development mode - skipping strict secret validation"
    fi
}

verify_gpu() {
    if [ "$OCR_USE_GPU" = "true" ]; then
        log_info "Verifying GPU availability..."

        if command -v nvidia-smi &> /dev/null; then
            # Display GPU information
            GPU_INFO=$(nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader)
            echo "$GPU_INFO"
            log_info "GPU is available and ready"

            # Detect GPU type for optimizations
            GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader)

            # Set PYTORCH optimizations for all GPUs
            export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

            # Apply RTX 5090 / Blackwell-specific optimizations
            if echo "$GPU_NAME" | grep -qi "RTX 5090\|RTX 50"; then
                log_info "Detected Blackwell GPU (RTX 5090) - Applying optimizations..."
                export GPU_TYPE="RTX5090"

                # NCCL optimizations for RTX 5090
                export NCCL_DEBUG="${NCCL_DEBUG:-INFO}"
                export NCCL_MIN_NRINGS="${NCCL_MIN_NRINGS:-2}"
                export NCCL_MAX_NRINGS="${NCCL_MAX_NRINGS:-4}"
                export NCCL_TREE_THRESHOLD="${NCCL_TREE_THRESHOLD:-0}"
                export NCCL_NET_GDR_LEVEL="${NCCL_NET_GDR_LEVEL:-5}"
                export NCCL_P2P_LEVEL="${NCCL_P2P_LEVEL:-SYS}"
                export NCCL_P2P_DISABLE="${NCCL_P2P_DISABLE:-0}"
                export NCCL_SHM_DISABLE="${NCCL_SHM_DISABLE:-0}"

                log_info "RTX 5090 optimizations applied"
            elif echo "$GPU_NAME" | grep -qi "RTX 40\|RTX 4090\|RTX 4080"; then
                log_info "Detected Ada Lovelace GPU - Applying optimizations..."
                export GPU_TYPE="RTX40"
            elif echo "$GPU_NAME" | grep -qi "RTX 30\|RTX 3090\|RTX 3080"; then
                log_info "Detected Ampere GPU - Standard configuration"
                export GPU_TYPE="RTX30"
            elif echo "$GPU_NAME" | grep -qi "RTX 20\|RTX 2080\|RTX 2060"; then
                log_info "Detected Turing GPU - Standard configuration"
                export GPU_TYPE="RTX20"
            else
                log_info "GPU detected: $GPU_NAME - Using default configuration"
                export GPU_TYPE="GENERIC"
            fi

            log_info "PYTORCH_CUDA_ALLOC_CONF=$PYTORCH_CUDA_ALLOC_CONF"
        else
            log_warn "GPU requested but nvidia-smi not found - falling back to CPU mode"
            export OCR_USE_GPU=false
        fi
    else
        log_info "Running in CPU-only mode"
    fi
}

# =============================================================================
# Graceful shutdown handler
# =============================================================================
shutdown() {
    log_info "Received shutdown signal, gracefully stopping..."

    # Kill child processes gracefully
    if [ -n "$APP_PID" ]; then
        kill -TERM "$APP_PID" 2>/dev/null || true
        wait "$APP_PID" 2>/dev/null || true
    fi

    if [ -n "$WORKER_PID" ]; then
        kill -TERM "$WORKER_PID" 2>/dev/null || true
        wait "$WORKER_PID" 2>/dev/null || true
    fi

    log_info "Shutdown complete"
    exit 0
}

# Register shutdown handler
trap shutdown SIGTERM SIGINT SIGQUIT

# =============================================================================
# Main execution
# =============================================================================
main() {
    log_info "Starting Claims Data Entry Agent..."
    log_info "Environment: ${APP_ENV:-development}"
    log_info "Log level: ${LOG_LEVEL:-INFO}"

    # Wait for dependencies
    wait_for_redis

    # Setup
    setup_directories
    check_secrets
    verify_gpu

    # Determine what to run based on command
    CMD=${1:-app}

    case "$CMD" in
        app)
            log_info "Starting FastAPI application..."
            # Convert LOG_LEVEL to lowercase for uvicorn
            UVICORN_LOG_LEVEL=$(echo "${LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')
            exec uvicorn src.main:app \
                --host 0.0.0.0 \
                --port "${ADMIN_PORT:-8080}" \
                --log-level "$UVICORN_LOG_LEVEL" \
                --proxy-headers \
                --forwarded-allow-ips='*'
            ;;

        worker)
            WORKER_TYPE=${2:-all}
            log_info "Starting worker: $WORKER_TYPE"

            if [ "$WORKER_TYPE" = "ocr" ]; then
                exec python -m src.workers.ocr_processor
            elif [ "$WORKER_TYPE" = "submission" ]; then
                exec python -m src.workers.ncb_submitter
            else
                # Start all workers
                log_info "Starting all workers in background..."
                python -m src.workers.ocr_processor &
                WORKER_PID=$!

                # Keep container running
                wait $WORKER_PID
            fi
            ;;

        test)
            log_info "Running tests..."
            exec pytest tests/ -v --cov=src
            ;;

        shell)
            log_info "Starting interactive shell..."
            exec /bin/bash
            ;;

        *)
            log_error "Unknown command: $CMD"
            echo "Available commands:"
            echo "  app              - Start FastAPI application (default)"
            echo "  worker [type]    - Start worker (ocr, submission, or all)"
            echo "  test             - Run tests"
            echo "  shell            - Interactive shell"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
