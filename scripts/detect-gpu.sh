#!/bin/bash
# GPU Detection and Configuration Script
# Auto-detects GPU capabilities and configures PaddlePaddle backend
# Part of Claims Data Entry Agent Multi-GPU Architecture

set -euo pipefail

LOG_PREFIX="[GPU-DETECT]"

# Color codes for output (if terminal supports it)
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

log_info() {
    echo -e "${GREEN}${LOG_PREFIX} INFO:${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}${LOG_PREFIX} WARN:${NC} $1" >&2
}

log_error() {
    echo -e "${RED}${LOG_PREFIX} ERROR:${NC} $1" >&2
}

log_debug() {
    if [ "${DEBUG:-false}" = "true" ]; then
        echo -e "${BLUE}${LOG_PREFIX} DEBUG:${NC} $1"
    fi
}

# Check if NVIDIA GPU is available
check_gpu_available() {
    log_debug "Checking for NVIDIA GPU..."

    if ! command -v nvidia-smi &> /dev/null; then
        log_debug "nvidia-smi command not found"
        return 1
    fi

    if ! nvidia-smi &> /dev/null; then
        log_debug "nvidia-smi execution failed"
        return 1
    fi

    return 0
}

# Get GPU compute capability
get_compute_capability() {
    nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | head -n1 | tr -d ' '
}

# Get GPU name
get_gpu_name() {
    nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n1
}

# Get GPU memory in GB
get_gpu_memory() {
    local memory_mb
    memory_mb=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -n1)
    echo "scale=1; $memory_mb / 1024" | bc
}

# Get CUDA runtime version from driver
get_cuda_version_from_driver() {
    nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -n1
}

# Get CUDA version from nvcc if available
get_cuda_version_from_nvcc() {
    if command -v nvcc &> /dev/null; then
        nvcc --version 2>/dev/null | grep "release" | sed -n 's/.*release \([0-9.]*\).*/\1/p'
    else
        echo "0.0"
    fi
}

# Get best CUDA version available
get_cuda_version() {
    local nvcc_version
    local driver_version

    nvcc_version=$(get_cuda_version_from_nvcc)
    driver_version=$(get_cuda_version_from_driver)

    # Prefer nvcc version if available, otherwise use driver version
    if [ "$nvcc_version" != "0.0" ]; then
        echo "$nvcc_version"
    else
        # Map driver version to CUDA version
        # Reference: https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/
        local driver_major
        driver_major=$(echo "$driver_version" | cut -d'.' -f1)

        if [ "$driver_major" -ge 565 ]; then
            echo "12.9"
        elif [ "$driver_major" -ge 535 ]; then
            echo "12.2"
        elif [ "$driver_major" -ge 520 ]; then
            echo "11.8"
        elif [ "$driver_major" -ge 470 ]; then
            echo "11.4"
        else
            echo "11.0"
        fi
    fi
}

# Determine optimal backend configuration
configure_backend() {
    local compute_cap=$1
    local cuda_version=$2
    local gpu_name=$3
    local gpu_memory=$4

    # Convert compute capability to comparable number (e.g., 7.5 -> 75, 9.0 -> 90)
    local cc_major cc_minor cc_num
    cc_major=$(echo "$compute_cap" | cut -d'.' -f1)
    cc_minor=$(echo "$compute_cap" | cut -d'.' -f2)
    cc_num=$((cc_major * 10 + cc_minor))

    log_info "GPU Configuration Detected:"
    log_info "  Model: $gpu_name"
    log_info "  Memory: ${gpu_memory} GB"
    log_info "  Compute Capability: $compute_cap"
    log_info "  CUDA Version: $cuda_version"

    # Determine GPU generation and configure accordingly
    if [ "$cc_num" -ge 90 ]; then
        # RTX 50 series Blackwell: Compute Capability 9.0+
        log_info "→ Blackwell GPU detected (RTX 50 series)"

        local cuda_major
        cuda_major=$(echo "$cuda_version" | cut -d'.' -f1)

        if [ "$cuda_major" -ge 12 ]; then
            export OCR_USE_GPU=true
            export PADDLE_BACKEND="cuda12"
            export LD_LIBRARY_PATH="/usr/local/lib/cuda-12:/usr/local/cuda-12.9/lib64:${LD_LIBRARY_PATH:-}"
            export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

            # Optimize batch size based on GPU memory
            if [ "${gpu_memory%.*}" -ge 20 ]; then
                export OCR_BATCH_SIZE=8  # RTX 5090 24GB
            else
                export OCR_BATCH_SIZE=6  # RTX 5080 16GB
            fi

            log_info "✓ Configured: CUDA 12.9+ backend (optimized for Blackwell)"
            log_info "  Batch size: ${OCR_BATCH_SIZE}"
        else
            log_warn "Blackwell GPU requires CUDA 12.9+, found $cuda_version"
            log_warn "Falling back to CPU mode"
            export OCR_USE_GPU=false
            export PADDLE_BACKEND="cpu"
        fi

    elif [ "$cc_num" -ge 86 ]; then
        # RTX 40 series Ada / RTX 3090: Compute Capability 8.6-8.9
        log_info "→ Ada/Ampere GPU detected (RTX 40/3090 series)"

        local cuda_major
        cuda_major=$(echo "$cuda_version" | cut -d'.' -f1)

        if [ "$cuda_major" -ge 11 ]; then
            export OCR_USE_GPU=true
            export PADDLE_BACKEND="cuda11"
            export LD_LIBRARY_PATH="/usr/local/lib/cuda-11:/usr/local/cuda-11.8/lib64:${LD_LIBRARY_PATH:-}"
            export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

            # Optimize batch size based on GPU memory
            if [ "${gpu_memory%.*}" -ge 20 ]; then
                export OCR_BATCH_SIZE=8  # RTX 4090 24GB
            elif [ "${gpu_memory%.*}" -ge 12 ]; then
                export OCR_BATCH_SIZE=6  # RTX 4080 16GB
            else
                export OCR_BATCH_SIZE=4  # RTX 4070 12GB
            fi

            log_info "✓ Configured: CUDA 11.8 backend"
            log_info "  Batch size: ${OCR_BATCH_SIZE}"
        else
            log_warn "GPU requires CUDA 11.8+, found $cuda_version"
            log_warn "Falling back to CPU mode"
            export OCR_USE_GPU=false
            export PADDLE_BACKEND="cpu"
        fi

    elif [ "$cc_num" -ge 80 ]; then
        # RTX 30 series Ampere: Compute Capability 8.0-8.5
        log_info "→ Ampere GPU detected (RTX 30 series)"

        export OCR_USE_GPU=true
        export PADDLE_BACKEND="cuda11"
        export LD_LIBRARY_PATH="/usr/local/lib/cuda-11:/usr/local/cuda-11.8/lib64:${LD_LIBRARY_PATH:-}"
        export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

        # Optimize batch size based on GPU memory
        if [ "${gpu_memory%.*}" -ge 20 ]; then
            export OCR_BATCH_SIZE=6  # RTX 3090 24GB
        elif [ "${gpu_memory%.*}" -ge 10 ]; then
            export OCR_BATCH_SIZE=4  # RTX 3080 12GB
        else
            export OCR_BATCH_SIZE=3  # RTX 3070 8GB
        fi

        log_info "✓ Configured: CUDA 11.8 backend"
        log_info "  Batch size: ${OCR_BATCH_SIZE}"

    elif [ "$cc_num" -ge 75 ]; then
        # RTX 20 series Turing: Compute Capability 7.5
        log_info "→ Turing GPU detected (RTX 20 series)"

        export OCR_USE_GPU=true
        export PADDLE_BACKEND="cuda11"
        export LD_LIBRARY_PATH="/usr/local/lib/cuda-11:/usr/local/cuda-11.8/lib64:${LD_LIBRARY_PATH:-}"
        export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

        # Conservative batch size for older GPUs
        if [ "${gpu_memory%.*}" -ge 10 ]; then
            export OCR_BATCH_SIZE=4  # RTX 2080 Ti 11GB
        else
            export OCR_BATCH_SIZE=3  # RTX 2070 8GB
        fi

        log_info "✓ Configured: CUDA 11.8 backend"
        log_info "  Batch size: ${OCR_BATCH_SIZE}"

    else
        # Older GPUs or unsupported compute capability
        log_warn "GPU compute capability $compute_cap is below minimum (7.5)"
        log_warn "Minimum required: 7.5 (RTX 20 series / Tesla T4)"
        log_warn "Falling back to CPU mode"

        export OCR_USE_GPU=false
        export PADDLE_BACKEND="cpu"
    fi
}

# Generate configuration file for application
write_config_file() {
    local config_file="/tmp/gpu-config.env"

    log_debug "Writing configuration to $config_file"

    cat > "$config_file" << EOF
# GPU Configuration (auto-generated by detect-gpu.sh)
# Generated at: $(date -Iseconds)

# GPU Status
export OCR_USE_GPU=${OCR_USE_GPU}
export PADDLE_BACKEND=${PADDLE_BACKEND:-cpu}

# GPU Details
export GPU_NAME="${GPU_NAME:-none}"
export GPU_COMPUTE_CAP=${GPU_COMPUTE_CAP:-0.0}
export GPU_MEMORY_GB=${GPU_MEMORY_GB:-0}
export CUDA_VERSION=${CUDA_VERSION:-0.0}

# Performance Tuning
export OCR_BATCH_SIZE=${OCR_BATCH_SIZE:-4}
export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}

# CUDA Paths
export LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}
EOF

    log_debug "Configuration written successfully"
}

# Validate PaddlePaddle installation
validate_paddle() {
    log_info "Validating PaddlePaddle installation..."

    if ! python3 -c "import paddle" 2>/dev/null; then
        log_error "PaddlePaddle not installed or not importable"
        return 1
    fi

    local paddle_version
    paddle_version=$(python3 -c "import paddle; print(paddle.__version__)" 2>/dev/null)
    log_info "  PaddlePaddle version: $paddle_version"

    if [ "${OCR_USE_GPU}" = "true" ]; then
        if ! python3 -c "import paddle; assert paddle.is_compiled_with_cuda()" 2>/dev/null; then
            log_error "PaddlePaddle not compiled with CUDA support"
            log_warn "Falling back to CPU mode"
            export OCR_USE_GPU=false
            export PADDLE_BACKEND="cpu"
            return 0
        fi

        local gpu_count
        gpu_count=$(python3 -c "import paddle; print(paddle.device.cuda.device_count())" 2>/dev/null)
        log_info "  CUDA support: enabled"
        log_info "  GPU count: $gpu_count"

        if [ "$gpu_count" -eq 0 ]; then
            log_warn "CUDA enabled but no GPUs found, falling back to CPU"
            export OCR_USE_GPU=false
            export PADDLE_BACKEND="cpu"
        fi
    else
        log_info "  Running in CPU mode"
    fi

    return 0
}

# Main detection logic
main() {
    log_info "Starting GPU detection and configuration..."
    log_info "=========================================="

    # Check for manual override
    if [ "${OCR_USE_GPU:-auto}" = "false" ]; then
        log_info "GPU manually disabled by environment variable"
        export OCR_USE_GPU=false
        export PADDLE_BACKEND="cpu"
        export GPU_NAME="none"
        export GPU_COMPUTE_CAP="0.0"
        export GPU_MEMORY_GB="0"
        export CUDA_VERSION="0.0"
        export OCR_BATCH_SIZE="${OCR_BATCH_SIZE:-4}"

        write_config_file
        log_info "=========================================="
        log_info "Configuration complete: CPU mode"
        return 0
    fi

    # Check GPU availability
    if ! check_gpu_available; then
        log_info "No NVIDIA GPU detected, using CPU mode"
        export OCR_USE_GPU=false
        export PADDLE_BACKEND="cpu"
        export GPU_NAME="none"
        export GPU_COMPUTE_CAP="0.0"
        export GPU_MEMORY_GB="0"
        export CUDA_VERSION="0.0"
        export OCR_BATCH_SIZE="${OCR_BATCH_SIZE:-4}"

        write_config_file
        log_info "=========================================="
        log_info "Configuration complete: CPU mode (no GPU found)"
        return 0
    fi

    # Get GPU information
    local compute_cap cuda_version gpu_name gpu_memory

    gpu_name=$(get_gpu_name)
    compute_cap=$(get_compute_capability)
    cuda_version=$(get_cuda_version)
    gpu_memory=$(get_gpu_memory)

    # Validate we got valid data
    if [ -z "$compute_cap" ] || [ -z "$gpu_name" ]; then
        log_error "Failed to retrieve GPU information"
        log_warn "Falling back to CPU mode"
        export OCR_USE_GPU=false
        export PADDLE_BACKEND="cpu"
        write_config_file
        return 1
    fi

    # Export for other functions
    export GPU_NAME="$gpu_name"
    export GPU_COMPUTE_CAP="$compute_cap"
    export GPU_MEMORY_GB="$gpu_memory"
    export CUDA_VERSION="$cuda_version"

    # Configure backend based on GPU capabilities
    configure_backend "$compute_cap" "$cuda_version" "$gpu_name" "$gpu_memory"

    # Write configuration file
    write_config_file

    # Validate PaddlePaddle
    if ! validate_paddle; then
        log_warn "PaddlePaddle validation failed, configuration may be incorrect"
    fi

    # Log final configuration summary
    log_info "=========================================="
    log_info "GPU Detection Complete!"
    log_info ""
    log_info "Final Configuration:"
    log_info "  GPU Mode: ${OCR_USE_GPU}"
    log_info "  Backend: ${PADDLE_BACKEND}"
    log_info "  GPU: ${GPU_NAME}"
    log_info "  Compute Cap: ${GPU_COMPUTE_CAP}"
    log_info "  VRAM: ${GPU_MEMORY_GB} GB"
    log_info "  CUDA: ${CUDA_VERSION}"
    log_info "  Batch Size: ${OCR_BATCH_SIZE}"
    log_info ""
    log_info "Config saved to: /tmp/gpu-config.env"
    log_info "=========================================="

    return 0
}

# Run main function
main "$@"
exit_code=$?

# Exit with appropriate code
exit $exit_code
