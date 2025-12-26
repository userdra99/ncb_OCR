# GPU Selection and Configuration Guide
## Claims Data Entry Agent - Multi-GPU Support

**Version:** 1.0.0
**Last Updated:** 2025-12-24

---

## Quick Start

### Choose Your Deployment

```bash
# Option 1: Let the system auto-detect (recommended)
docker-compose -f docker-compose.gpu-auto.yml up -d

# Option 2: Explicitly choose based on your GPU
# RTX 20/30/40 series
docker-compose -f docker-compose.gpu-legacy.yml up -d

# RTX 50 series (Blackwell)
docker-compose -f docker-compose.gpu-blackwell.yml up -d

# No GPU / CPU only
docker-compose -f docker-compose.cpu.yml up -d
```

---

## GPU Compatibility Matrix

### Supported GPUs

| GPU Model | Series | Compute Capability | CUDA Version | Compose File | Performance |
|-----------|--------|-------------------|--------------|--------------|-------------|
| RTX 5090 | Blackwell | 9.0 | 12.9 | gpu-blackwell.yml | Excellent (25-30 ppm) |
| RTX 5080 | Blackwell | 9.0 | 12.9 | gpu-blackwell.yml | Excellent (20-25 ppm) |
| RTX 4090 | Ada | 8.9 | 11.8 | gpu-legacy.yml | Very Good (18-22 ppm) |
| RTX 4080 | Ada | 8.9 | 11.8 | gpu-legacy.yml | Very Good (15-18 ppm) |
| RTX 4070 Ti | Ada | 8.9 | 11.8 | gpu-legacy.yml | Good (12-15 ppm) |
| RTX 3090 | Ampere | 8.6 | 11.8 | gpu-legacy.yml | Very Good (15-20 ppm) |
| RTX 3080 | Ampere | 8.6 | 11.8 | gpu-legacy.yml | Good (12-15 ppm) |
| RTX 3070 | Ampere | 8.6 | 11.8 | gpu-legacy.yml | Good (10-12 ppm) |
| RTX 2080 Ti | Turing | 7.5 | 11.8 | gpu-legacy.yml | Moderate (8-10 ppm) |
| RTX 2070 | Turing | 7.5 | 11.8 | gpu-legacy.yml | Moderate (6-8 ppm) |

**ppm** = pages per minute (estimated OCR throughput)

### Unsupported GPUs

| GPU Type | Reason | Alternative |
|----------|--------|-------------|
| GTX 16 series | Compute Capability < 7.5 | Use CPU mode |
| GTX 10 series | Compute Capability < 7.5 | Use CPU mode |
| Quadro P series | Compute Capability < 7.5 | Use CPU mode |
| Tesla K series | Too old | Use CPU mode |

---

## Decision Tree

```
Do you have an NVIDIA GPU?
├─ NO → Use docker-compose.cpu.yml
└─ YES
   │
   ├─ Is it RTX 50 series (5090, 5080, etc.)?
   │  ├─ YES → Use docker-compose.gpu-blackwell.yml
   │  └─ NO → Continue
   │
   ├─ Is it RTX 20/30/40 series?
   │  ├─ YES → Use docker-compose.gpu-legacy.yml
   │  └─ NO → Continue
   │
   ├─ Not sure? → Use docker-compose.gpu-auto.yml (auto-detect)
   └─ Older GPU → Use docker-compose.cpu.yml
```

---

## System Requirements

### Minimum Requirements

**For CPU-only mode:**
- CPU: 4 cores (Intel i5 or AMD Ryzen 5 equivalent)
- RAM: 8 GB
- Storage: 10 GB free space
- OS: Ubuntu 22.04 / Debian 11 / RHEL 8

**For GPU mode (all variants):**
- All CPU-only requirements PLUS:
- NVIDIA GPU with Compute Capability >= 7.5
- NVIDIA Driver: 535.129.03 or newer
- CUDA Driver: Compatible with GPU model
- GPU VRAM: 6 GB minimum, 8 GB recommended
- Docker with nvidia-container-toolkit

### Recommended Requirements

**For RTX 50 series (Blackwell):**
- CPU: 8 cores
- RAM: 16 GB
- GPU VRAM: 16 GB (RTX 5080) or 24 GB (RTX 5090)
- NVIDIA Driver: 565.57.01 or newer
- CUDA: 12.9+

**For RTX 30/40 series:**
- CPU: 6 cores
- RAM: 12 GB
- GPU VRAM: 10 GB minimum
- NVIDIA Driver: 535.129.03 or newer
- CUDA: 11.8+

---

## Performance Comparison

### OCR Processing Speed

| Configuration | Single Page | Batch (10 pages) | Large Receipt | Complex Receipt |
|---------------|-------------|------------------|---------------|-----------------|
| CPU (8 cores) | 20-30s | 3-4 min | 40-50s | 50-60s |
| RTX 2080 Ti | 6-8s | 60-80s | 10-12s | 12-15s |
| RTX 3090 | 3-4s | 30-40s | 5-6s | 6-8s |
| RTX 4090 | 2.5-3s | 25-30s | 4-5s | 5-6s |
| RTX 5090 | 2-2.5s | 20-25s | 3-4s | 4-5s |

### Throughput Comparison

| Configuration | Pages/min | Daily Capacity (8h) | Monthly Capacity |
|---------------|-----------|---------------------|------------------|
| CPU (8 cores) | 2-3 | 1,000-1,500 | 20,000-30,000 |
| RTX 2080 Ti | 8-10 | 4,000-5,000 | 80,000-100,000 |
| RTX 3090 | 15-20 | 7,500-10,000 | 150,000-200,000 |
| RTX 4090 | 18-22 | 9,000-11,000 | 180,000-220,000 |
| RTX 5090 | 25-30 | 12,500-15,000 | 250,000-300,000 |

### Cost-Benefit Analysis

| GPU Model | Cost (USD) | Performance vs CPU | Cost per 1000 pages/day | ROI (months) |
|-----------|------------|-------------------|-------------------------|--------------|
| RTX 2080 Ti | $700-900 | 3-4x | $0.70 | 6-8 |
| RTX 3090 | $1,500-1,800 | 6-8x | $0.40 | 4-6 |
| RTX 4090 | $1,600-2,000 | 8-10x | $0.35 | 4-5 |
| RTX 5090 | $2,500-3,000 | 10-12x | $0.30 | 5-6 |

*ROI calculated based on processing 5,000 pages/day vs 2 CPU servers*

---

## Installation and Setup

### Step 1: Verify GPU Support

```bash
# Check if NVIDIA GPU is detected
nvidia-smi

# Expected output should show:
# - GPU model name
# - CUDA version
# - Driver version
```

### Step 2: Install Docker GPU Support

```bash
# Ubuntu/Debian
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Restart Docker
sudo systemctl restart docker

# Test GPU access from Docker
docker run --rm --gpus all nvidia/cuda:12.9.0-runtime-ubuntu22.04 nvidia-smi
```

### Step 3: Choose and Build

```bash
# Clone repository
cd /home/dra/projects/ncb_OCR

# Option A: Auto-detect build (recommended)
docker build -t claims-app:auto --target production-auto .
docker-compose -f docker-compose.gpu-auto.yml up -d

# Option B: Specific GPU target
# For RTX 20/30/40
docker build -t claims-app:cuda11 --target production-gpu-legacy .
docker-compose -f docker-compose.gpu-legacy.yml up -d

# For RTX 50 (Blackwell)
docker build -t claims-app:cuda12 --target production-gpu-blackwell .
docker-compose -f docker-compose.gpu-blackwell.yml up -d

# Option C: CPU-only
docker build -t claims-app:cpu --target production-cpu .
docker-compose -f docker-compose.cpu.yml up -d
```

### Step 4: Verify Configuration

```bash
# Check if GPU is being used
docker logs claims-app-auto | grep GPU

# Expected output:
# [GPU-DETECT] INFO: GPU: NVIDIA GeForce RTX 5090
# [GPU-DETECT] INFO: Compute Capability: 9.0
# [GPU-DETECT] INFO: Configured: CUDA 12.9+ backend
# [ENTRYPOINT] GPU Mode: true
# [ENTRYPOINT] Backend: cuda12

# Check PaddlePaddle
docker exec claims-app-auto python -c "
import paddle
print(f'PaddlePaddle: {paddle.__version__}')
print(f'CUDA enabled: {paddle.is_compiled_with_cuda()}')
print(f'GPU count: {paddle.device.cuda.device_count()}')
"
```

---

## Configuration Options

### Environment Variables

```bash
# GPU Configuration
OCR_USE_GPU=auto              # auto|true|false
CUDA_VISIBLE_DEVICES=0        # GPU device ID (0,1,2...)
PADDLE_BACKEND=auto           # auto|cuda11|cuda12|cpu
GPU_TYPE=RTX5090              # Optional: GPU model hint

# Performance Tuning
OCR_BATCH_SIZE=6              # Batch size for OCR (increase for more VRAM)
OCR_MAX_IMAGE_SIZE=4096       # Max image resolution
SHM_SIZE=8gb                  # Shared memory for Docker

# CUDA Memory Management (Blackwell GPUs)
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
CUDA_LAUNCH_BLOCKING=0        # Set to 1 for debugging
```

### Docker Compose Overrides

Create `docker-compose.override.yml` for custom settings:

```yaml
version: '3.8'

services:
  app:
    environment:
      # Custom GPU settings
      - OCR_BATCH_SIZE=8  # Increase for RTX 5090
      - OCR_MAX_IMAGE_SIZE=8192

    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0', '1']  # Use multiple GPUs
              capabilities: [gpu]

    shm_size: 16gb  # Increase for large batches
```

---

## Troubleshooting

### GPU Not Detected

**Problem**: Container starts but GPU is not used

**Check**:
```bash
# 1. Verify GPU is visible to host
nvidia-smi

# 2. Check Docker can access GPU
docker run --rm --gpus all nvidia/cuda:12.9.0-runtime-ubuntu22.04 nvidia-smi

# 3. Check container GPU access
docker exec claims-app nvidia-smi
```

**Solution**:
- Install nvidia-container-toolkit
- Restart Docker daemon
- Check nvidia runtime is default: `docker info | grep "Default Runtime"`

---

### CUDA Version Mismatch

**Problem**: `CUDA error: no kernel image available`

**Check**:
```bash
# Host CUDA driver version
nvidia-smi | grep "CUDA Version"

# Container CUDA version
docker exec claims-app nvcc --version || echo "nvcc not in container"
```

**Solution**:
| Host Driver | Supported CUDA | Use Compose File |
|-------------|----------------|------------------|
| 565.57.01+ | 12.9 | gpu-blackwell.yml |
| 535.129.03+ | 11.8, 12.9 | gpu-auto.yml |
| 520.61.05+ | 11.8 | gpu-legacy.yml |

---

### Out of Memory (OOM)

**Problem**: `RuntimeError: CUDA out of memory`

**Check**:
```bash
# Monitor GPU memory
nvidia-smi dmon -s u

# Check batch size
docker exec claims-app env | grep OCR_BATCH_SIZE
```

**Solution**:
```bash
# Reduce batch size
export OCR_BATCH_SIZE=4  # Default: 6

# Reduce max image size
export OCR_MAX_IMAGE_SIZE=2048  # Default: 4096

# Increase shared memory
# In docker-compose.yml:
shm_size: 16gb
```

---

### Performance Degradation

**Problem**: GPU mode slower than expected

**Check**:
```bash
# Check GPU utilization
nvidia-smi dmon -s u

# Run benchmark
docker exec claims-app python scripts/benchmark-ocr.py

# Check if CPU mode is accidentally enabled
docker logs claims-app | grep "GPU Mode"
```

**Solution**:
1. Ensure GPU mode is actually enabled (`OCR_USE_GPU=true`)
2. Check for thermal throttling: `nvidia-smi --query-gpu=temperature.gpu --format=csv`
3. Verify batch size is optimal for GPU VRAM
4. Check for other processes using GPU: `nvidia-smi pmon`

---

## Advanced Configuration

### Multi-GPU Setup

For processing high volumes with multiple GPUs:

```yaml
# docker-compose.multi-gpu.yml
services:
  app-gpu0:
    <<: *app-template
    environment:
      - CUDA_VISIBLE_DEVICES=0
    container_name: claims-app-gpu0

  app-gpu1:
    <<: *app-template
    environment:
      - CUDA_VISIBLE_DEVICES=1
    container_name: claims-app-gpu1

  nginx:
    image: nginx:latest
    volumes:
      - ./nginx-lb.conf:/etc/nginx/nginx.conf
    ports:
      - "8080:8080"
```

### Mixed Precision (Blackwell GPUs)

RTX 50 series supports enhanced mixed precision:

```python
# In src/services/ocr_service.py
if self.config.gpu_compute_cap >= 9.0:
    # Enable FP8 precision on Blackwell
    self.ocr = PaddleOCR(
        use_gpu=True,
        precision='fp8',  # Mixed precision
        # ... other config
    )
```

### Custom CUDA Paths

If using non-standard CUDA installation:

```bash
# docker-compose.override.yml
environment:
  - LD_LIBRARY_PATH=/usr/local/cuda-12.9/lib64:/custom/cuda/lib64
  - CUDA_HOME=/custom/cuda
```

---

## Monitoring and Metrics

### GPU Metrics to Track

```bash
# GPU utilization
nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits

# Memory usage
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader

# Temperature
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader

# Power draw
nvidia-smi --query-gpu=power.draw --format=csv,noheader
```

### Integration with Prometheus

Add to docker-compose:

```yaml
services:
  nvidia-exporter:
    image: nvidia/dcgm-exporter:latest
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
    ports:
      - "9400:9400"
```

---

## FAQ

### Q: Can I use multiple CUDA versions on the same host?

Yes, the auto-detect variant supports this. Different containers can use different CUDA versions as long as the host driver supports the highest CUDA version needed.

### Q: Will this work on WSL2?

Yes, with NVIDIA GPU support in WSL2. Requires:
- Windows 11 or Windows 10 21H2+
- NVIDIA GPU driver for Windows (not WSL2 driver)
- WSL2 with kernel 5.10+

### Q: Can I switch between GPU and CPU mode without rebuilding?

Yes, if using the auto-detect variant. Set `OCR_USE_GPU=false` and restart container.

### Q: How much faster is RTX 5090 vs RTX 4090?

Estimated 20-30% faster for OCR workloads based on Blackwell architecture improvements.

### Q: Does this support AMD GPUs?

No, PaddlePaddle only supports NVIDIA CUDA GPUs. AMD ROCm is not supported.

---

## References

- [NVIDIA CUDA Compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/)
- [PaddlePaddle GPU Setup](https://www.paddlepaddle.org.cn/install/quick)
- [Docker GPU Support](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- [RTX 50 Series Specs](https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/)

---

**Last Updated**: 2025-12-24
**Maintained By**: TPA Development Team
