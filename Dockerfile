# Multi-stage Dockerfile for Claims Data Entry Agent with CUDA support
# Optimized for both GPU and CPU execution modes

# =============================================================================
# Stage 1: Base image with CUDA runtime
# =============================================================================
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 AS base

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3.10-dev \
    python3-pip \
    poppler-utils \
    libgomp1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic link for python
RUN ln -sf /usr/bin/python3.10 /usr/bin/python

# Upgrade pip and install build dependencies
RUN python -m pip install --upgrade pip setuptools wheel

# =============================================================================
# Stage 2: Dependencies builder
# =============================================================================
FROM base AS builder

# Set working directory for building
WORKDIR /build

# Copy dependency files
COPY pyproject.toml requirements.txt ./

# Install Python dependencies in a virtual environment
RUN python -m pip install --prefix=/install \
    paddlepaddle-gpu==2.5.0 \
    fastapi>=0.104.0 \
    uvicorn[standard]>=0.24.0 \
    pydantic>=2.5.0 \
    pydantic-settings>=2.1.0 \
    python-dotenv>=1.0.0 \
    redis>=5.0.0 \
    rq>=1.15.0 \
    paddleocr>=2.7.0 \
    google-api-python-client>=2.100.0 \
    google-auth-httplib2>=0.1.0 \
    google-auth-oauthlib>=1.1.0 \
    gspread>=5.12.0 \
    Pillow>=10.0.0 \
    pdf2image>=1.16.0 \
    opencv-python>=4.8.0 \
    httpx>=0.25.0 \
    structlog>=23.2.0 \
    tenacity>=8.2.0

# =============================================================================
# Stage 3: Production runtime image
# =============================================================================
FROM base AS production

# Metadata
LABEL maintainer="TPA Development Team" \
      version="1.0.0" \
      description="Claims Data Entry Agent with OCR and GPU support"

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Create necessary directories with proper permissions
RUN mkdir -p \
    /app/data/temp \
    /app/logs \
    /app/secrets \
    && chown -R appuser:appuser /app

# Copy application code
COPY --chown=appuser:appuser src/ /app/src/
COPY --chown=appuser:appuser scripts/ /app/scripts/
COPY --chown=appuser:appuser pyproject.toml /app/

# Make entrypoint script executable
RUN chmod +x /app/scripts/docker-entrypoint.sh

# Install the application in editable mode
RUN pip install -e .

# Switch to non-root user
USER appuser

# Expose ports
EXPOSE 8080 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/health', timeout=5.0)" || exit 1

# Set entrypoint
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]

# Default command (can be overridden)
CMD ["app"]

# =============================================================================
# Stage 4: CPU-only variant (for environments without GPU)
# =============================================================================
FROM ubuntu:22.04 AS cpu-only

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OCR_USE_GPU=false

# Install system dependencies (same as base)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3.10-dev \
    python3-pip \
    poppler-utils \
    libgomp1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.10 /usr/bin/python
RUN python -m pip install --upgrade pip setuptools wheel

# Create user
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser

WORKDIR /app

# Install CPU-only PaddlePaddle and other dependencies
RUN python -m pip install \
    paddlepaddle==2.5.0 \
    fastapi>=0.104.0 \
    uvicorn[standard]>=0.24.0 \
    pydantic>=2.5.0 \
    pydantic-settings>=2.1.0 \
    python-dotenv>=1.0.0 \
    redis>=5.0.0 \
    rq>=1.15.0 \
    paddleocr>=2.7.0 \
    google-api-python-client>=2.100.0 \
    google-auth-httplib2>=0.1.0 \
    google-auth-oauthlib>=1.1.0 \
    gspread>=5.12.0 \
    Pillow>=10.0.0 \
    pdf2image>=1.16.0 \
    opencv-python>=4.8.0 \
    httpx>=0.25.0 \
    structlog>=23.2.0 \
    tenacity>=8.2.0

# Create directories
RUN mkdir -p /app/data/temp /app/logs /app/secrets \
    && chown -R appuser:appuser /app

# Copy application
COPY --chown=appuser:appuser src/ /app/src/
COPY --chown=appuser:appuser scripts/ /app/scripts/
COPY --chown=appuser:appuser pyproject.toml /app/

RUN chmod +x /app/scripts/docker-entrypoint.sh
RUN pip install -e .

USER appuser
EXPOSE 8080 9090

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/health', timeout=5.0)" || exit 1

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["app"]
