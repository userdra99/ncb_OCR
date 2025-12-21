# Docker Deployment Guide

Complete guide for deploying the Claims Data Entry Agent using Docker and Docker Compose.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Development Setup](#development-setup)
- [Production Deployment](#production-deployment)
- [GPU Configuration](#gpu-configuration)
- [Docker Compose Services](#docker-compose-services)
- [Volume Management](#volume-management)
- [Network Configuration](#network-configuration)
- [Environment Variables](#environment-variables)
- [Health Monitoring](#health-monitoring)
- [Troubleshooting](#troubleshooting)
- [Performance Tuning](#performance-tuning)

## Prerequisites

### Required Software

1. **Docker Engine 20.10+**
   \`\`\`bash
   # Install Docker on Ubuntu/Debian
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh

   # Add user to docker group
   sudo usermod -aG docker $USER
   newgrp docker

   # Verify installation
   docker --version
   \`\`\`

2. **Docker Compose 2.0+**
   \`\`\`bash
   # Install Docker Compose
   sudo apt-get update
   sudo apt-get install docker-compose-plugin

   # Verify installation
   docker compose version
   \`\`\`

3. **NVIDIA Docker Runtime** (for GPU support)
   \`\`\`bash
   # Add NVIDIA Docker repository
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
   curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \\
     sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \\
     sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

   # Install NVIDIA Container Toolkit
   sudo apt-get update
   sudo apt-get install -y nvidia-container-toolkit

   # Configure Docker to use NVIDIA runtime
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker

   # Test GPU access
   docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
   \`\`\`

### System Requirements

| Component | Development | Production |
|-----------|-------------|------------|
| CPU | 4+ cores | 8+ cores |
| RAM | 8GB+ | 16GB+ |
| GPU | NVIDIA GPU with 4GB+ VRAM | NVIDIA GPU with 8GB+ VRAM |
| CUDA | 11.8+ | 11.8+ |
| Storage | 20GB+ | 50GB+ |
| OS | Ubuntu 20.04+ | Ubuntu 22.04+ LTS |

## Installation

### 1. Clone Repository

\`\`\`bash
git clone <repository-url>
cd ncb_OCR
\`\`\`

### 2. Create Required Directories

\`\`\`bash
# Create data directories
mkdir -p data/{temp,models,logs}

# Create secrets directory
mkdir -p secrets

# Set appropriate permissions
chmod 700 secrets
chmod 755 data
\`\`\`

### 3. Configure Environment

\`\`\`bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
\`\`\`

See [Environment Variables](#environment-variables) section for detailed configuration.

### 4. Add Google API Credentials

\`\`\`bash
# Copy credentials to secrets directory
cp /path/to/gmail_credentials.json secrets/
cp /path/to/sheets_credentials.json secrets/
cp /path/to/drive_credentials.json secrets/

# Set secure permissions
chmod 600 secrets/*.json
\`\`\`

## Development Setup

### Quick Start

\`\`\`bash
# Build development image
docker compose build

# Start services
docker compose up -d

# View logs
docker compose logs -f

# Check service status
docker compose ps
\`\`\`

### Development Workflow

1. **Start Redis Only** (for local Python development)
   \`\`\`bash
   docker compose up -d redis

   # Run application locally
   python -m venv venv
   source venv/bin/activate
   pip install -e ".[dev]"
   python -m src.main
   \`\`\`

2. **Full Docker Development**
   \`\`\`bash
   # Start all services
   docker compose up -d

   # Watch logs
   docker compose logs -f api worker

   # Restart specific service
   docker compose restart worker
   \`\`\`

3. **Interactive Shell**
   \`\`\`bash
   # Enter container
   docker compose exec api bash

   # Or run one-off command
   docker compose run --rm api python -m pytest
   \`\`\`

## Production Deployment

### Build Production Image

\`\`\`bash
# Build optimized production image
docker compose -f docker-compose.prod.yml build --no-cache

# Tag image
docker tag ncb-ocr-api:latest ncb-ocr-api:v1.0.0
\`\`\`

### Deploy Services

\`\`\`bash
# Start production services
docker compose -f docker-compose.prod.yml up -d

# Verify services
docker compose -f docker-compose.prod.yml ps

# Check health
docker compose -f docker-compose.prod.yml exec api curl http://localhost:8000/health
\`\`\`

## GPU Configuration

### Enable GPU Support

1. **Verify GPU Availability**
   \`\`\`bash
   # Check NVIDIA driver
   nvidia-smi

   # Test Docker GPU access
   docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
   \`\`\`

2. **Configure Docker Compose**
   \`\`\`yaml
   services:
     worker:
       deploy:
         resources:
           reservations:
             devices:
               - driver: nvidia
                 count: 1  # or 'all'
                 capabilities: [gpu]
   \`\`\`

3. **Environment Variables**
   \`\`\`bash
   # In .env file
   OCR_USE_GPU=true
   CUDA_VISIBLE_DEVICES=0  # Specify GPU ID
   \`\`\`

## Troubleshooting

### Common Issues

#### 1. GPU Not Detected

**Symptoms:**
\`\`\`
RuntimeError: No CUDA GPUs are available
\`\`\`

**Solutions:**
\`\`\`bash
# Verify NVIDIA driver
nvidia-smi

# Check Docker GPU runtime
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Restart Docker daemon
sudo systemctl restart docker
\`\`\`

#### 2. Permission Denied (Secrets)

**Symptoms:**
\`\`\`
PermissionError: [Errno 13] Permission denied: '/app/secrets/gmail_credentials.json'
\`\`\`

**Solutions:**
\`\`\`bash
# Fix file permissions
chmod 600 secrets/*.json
chmod 700 secrets
\`\`\`

#### 3. Redis Connection Failed

**Symptoms:**
\`\`\`
redis.exceptions.ConnectionError: Error connecting to Redis
\`\`\`

**Solutions:**
\`\`\`bash
# Check Redis container
docker compose ps redis

# Test Redis connection
docker compose exec redis redis-cli ping
\`\`\`

## Performance Tuning

### GPU Optimization

\`\`\`bash
# In .env file
OCR_BATCH_SIZE=8  # 8GB VRAM
OCR_BATCH_SIZE=16 # 16GB VRAM
\`\`\`

### Monitoring Performance

\`\`\`bash
# Real-time stats
docker stats

# GPU usage
watch -n 1 nvidia-smi
\`\`\`

## References

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

