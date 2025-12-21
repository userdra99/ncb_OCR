# Production Deployment Guide

Complete guide for deploying the Claims Data Entry Agent to production environments.

## Table of Contents

- [Overview](#overview)
- [Server Requirements](#server-requirements)
- [Pre-Deployment Checklist](#pre-deployment-checklist)
- [Initial Setup](#initial-setup)
- [Credentials Configuration](#credentials-configuration)
- [Deployment Steps](#deployment-steps)
- [Post-Deployment Validation](#post-deployment-validation)
- [Health Monitoring](#health-monitoring)
- [Backup and Recovery](#backup-and-recovery)
- [Scaling Considerations](#scaling-considerations)
- [Maintenance Procedures](#maintenance-procedures)
- [Security Hardening](#security-hardening)
- [Rollback Procedures](#rollback-procedures)

## Overview

This guide covers deploying the Claims Data Entry Agent to a production server with proper security, monitoring, and maintenance procedures.

### Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Production Server                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│  │   Nginx    │  │  Docker    │  │   Redis    │       │
│  │  (Proxy)   │  │ Containers │  │ (Sentinel) │       │
│  │   :80/443  │  │            │  │   :6379    │       │
│  └─────┬──────┘  └──────┬─────┘  └─────┬──────┘       │
│        │                │              │               │
│        └────────────────┴──────────────┘               │
│                         │                               │
│              ┌──────────▼──────────┐                   │
│              │   Monitoring Stack   │                   │
│              │  (Prometheus/Grafana)│                   │
│              └─────────────────────┘                   │
│                                                          │
└─────────────────────────────────────────────────────────┘
           │                │                │
           ▼                ▼                ▼
    Gmail API        NCB API       Google Workspace
```

## Server Requirements

### Minimum Specifications

| Component | Requirement |
|-----------|-------------|
| **CPU** | 8+ cores (Intel Xeon or AMD EPYC) |
| **RAM** | 16GB DDR4 |
| **GPU** | NVIDIA GPU with 8GB+ VRAM (RTX 3070 or better) |
| **Storage** | 100GB NVMe SSD |
| **Network** | 1Gbps connection, static IP |
| **OS** | Ubuntu 22.04 LTS |

### Recommended Specifications

| Component | Recommendation |
|-----------|----------------|
| **CPU** | 16+ cores |
| **RAM** | 32GB DDR4 |
| **GPU** | NVIDIA RTX 4090 or A4000 (16GB VRAM) |
| **Storage** | 250GB NVMe SSD (RAID 1) |
| **Network** | 10Gbps connection |

### Software Requirements

- Docker Engine 24.0+
- Docker Compose 2.20+
- NVIDIA Driver 535+
- NVIDIA Container Toolkit
- Git
- Python 3.10+ (for setup scripts)
- Nginx or Traefik (reverse proxy)

## Pre-Deployment Checklist

### Infrastructure

- [ ] Server provisioned with required specifications
- [ ] Static IP address assigned
- [ ] DNS records configured (if needed)
- [ ] Firewall rules configured
- [ ] SSH key-based authentication enabled
- [ ] Backup storage configured
- [ ] Monitoring infrastructure ready

### Access & Credentials

- [ ] Gmail API credentials obtained
- [ ] Gmail OAuth flow completed
- [ ] NCB API key issued
- [ ] Google Sheets service account created
- [ ] Google Drive folder created and shared
- [ ] Admin API keys generated
- [ ] SMTP credentials for alerts configured

### Application Setup

- [ ] Repository cloned
- [ ] Environment variables configured
- [ ] Secrets stored securely
- [ ] Docker images built
- [ ] Database migration scripts prepared
- [ ] Test data prepared

### Documentation

- [ ] Runbooks prepared
- [ ] Contact lists updated
- [ ] Escalation procedures documented
- [ ] Disaster recovery plan reviewed

## Initial Setup

### 1. Server Preparation

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install essential tools
sudo apt install -y \
  build-essential \
  curl \
  git \
  vim \
  htop \
  net-tools \
  ufw

# Configure timezone
sudo timedatectl set-timezone Asia/Kuala_Lumpur

# Set hostname
sudo hostnamectl set-hostname ncb-ocr-prod
```

### 2. Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Enable Docker service
sudo systemctl enable docker
sudo systemctl start docker

# Install Docker Compose
sudo apt install docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

### 3. Install NVIDIA Components

```bash
# Install NVIDIA driver
sudo apt install -y ubuntu-drivers-common
sudo ubuntu-drivers autoinstall

# Reboot to load driver
sudo reboot

# After reboot, verify driver
nvidia-smi

# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update
sudo apt install -y nvidia-container-toolkit

# Configure Docker runtime
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Test GPU access
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### 4. Configure Firewall

```bash
# Enable UFW
sudo ufw enable

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS (for reverse proxy)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow internal API (optional, if exposing directly)
# sudo ufw allow 8000/tcp

# Check status
sudo ufw status verbose
```

### 5. Setup Application Directory

```bash
# Create application directory
sudo mkdir -p /opt/ncb-ocr
sudo chown $USER:$USER /opt/ncb-ocr

# Clone repository
cd /opt/ncb-ocr
git clone <repository-url> .

# Create required directories
mkdir -p data/{temp,models,logs}
mkdir -p secrets
mkdir -p backups

# Set permissions
chmod 700 secrets
chmod 755 data backups
```

## Credentials Configuration

### 1. Gmail API Setup

```bash
# Copy Gmail credentials
cp /path/to/gmail_credentials.json /opt/ncb-ocr/secrets/

# Run OAuth flow (one-time)
docker compose run --rm api python scripts/setup_gmail.py

# This will generate gmail_token.json
# Verify token exists
ls -la secrets/gmail_token.json
```

### 2. Google Sheets Setup

```bash
# Copy service account credentials
cp /path/to/sheets_credentials.json /opt/ncb-ocr/secrets/

# Initialize spreadsheet
docker compose run --rm api python scripts/init_sheets.py

# Note the spreadsheet ID from output
# Add to .env: SHEETS_SPREADSHEET_ID=<id>
```

### 3. Google Drive Setup

```bash
# Copy service account credentials (may be same as Sheets)
cp /path/to/drive_credentials.json /opt/ncb-ocr/secrets/

# Create folder and get ID
# 1. Create folder in Google Drive
# 2. Share with service account email
# 3. Get folder ID from URL: drive.google.com/drive/folders/<FOLDER_ID>
# 4. Add to .env: DRIVE_FOLDER_ID=<id>
```

### 4. Environment Variables

```bash
# Copy production environment template
cp .env.example .env.prod

# Edit production environment
nano .env.prod
```

**Critical variables to set:**

```bash
# Application
APP_ENV=production
APP_DEBUG=false
LOG_LEVEL=INFO

# Gmail
GMAIL_CREDENTIALS_PATH=/app/secrets/gmail_credentials.json
GMAIL_TOKEN_PATH=/app/secrets/gmail_token.json
GMAIL_POLL_INTERVAL=30

# NCB API
NCB_API_BASE_URL=https://ncb.internal.company.com/api/v1
NCB_API_KEY=your-production-api-key

# Google Sheets
SHEETS_CREDENTIALS_PATH=/app/secrets/sheets_credentials.json
SHEETS_SPREADSHEET_ID=your-spreadsheet-id

# Google Drive
DRIVE_CREDENTIALS_PATH=/app/secrets/drive_credentials.json
DRIVE_FOLDER_ID=your-folder-id

# Redis
REDIS_URL=redis://redis:6379/0

# OCR
OCR_USE_GPU=true
OCR_BATCH_SIZE=8
OCR_HIGH_CONFIDENCE_THRESHOLD=0.90

# Admin
ADMIN_API_KEY=generate-strong-random-key

# Alerts
ALERTS_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=alerts@company.com
SMTP_PASSWORD=your-smtp-password
ALERT_RECIPIENTS=ops@company.com,manager@company.com

# Monitoring
METRICS_ENABLED=true
SENTRY_DSN=https://your-sentry-dsn
```

### 5. Secure Secrets

```bash
# Set strict permissions
chmod 600 /opt/ncb-ocr/secrets/*.json
chmod 600 /opt/ncb-ocr/.env.prod

# Verify permissions
ls -la /opt/ncb-ocr/secrets/
ls -la /opt/ncb-ocr/.env.prod

# Optional: Encrypt secrets at rest
# Using git-crypt or similar
```

## Deployment Steps

### 1. Build Images

```bash
cd /opt/ncb-ocr

# Build production images
docker compose -f docker-compose.prod.yml build --no-cache

# Tag images with version
docker tag ncb-ocr-api:latest ncb-ocr-api:v1.0.0
docker tag ncb-ocr-worker:latest ncb-ocr-worker:v1.0.0
docker tag ncb-ocr-poller:latest ncb-ocr-poller:v1.0.0
```

### 2. Initialize Database/Storage

```bash
# Start Redis first
docker compose -f docker-compose.prod.yml up -d redis

# Wait for Redis to be ready
sleep 5

# Verify Redis
docker compose -f docker-compose.prod.yml exec redis redis-cli ping
```

### 3. Run Pre-flight Checks

```bash
# Check environment configuration
docker compose -f docker-compose.prod.yml config

# Validate credentials
docker compose -f docker-compose.prod.yml run --rm api python scripts/validate_credentials.py

# Test NCB API connectivity
docker compose -f docker-compose.prod.yml run --rm api python scripts/test_ncb_connection.py
```

### 4. Start Services

```bash
# Start all services
docker compose -f docker-compose.prod.yml up -d

# View startup logs
docker compose -f docker-compose.prod.yml logs -f

# Wait for services to be healthy
docker compose -f docker-compose.prod.yml ps
```

### 5. Configure Reverse Proxy

**Nginx Configuration:**

```bash
# Create Nginx config
sudo nano /etc/nginx/sites-available/ncb-ocr
```

```nginx
upstream ncb_ocr {
    server localhost:8000;
}

server {
    listen 80;
    server_name ocr.internal.company.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ocr.internal.company.com;

    ssl_certificate /etc/ssl/certs/ncb-ocr.crt;
    ssl_certificate_key /etc/ssl/private/ncb-ocr.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 30M;

    location / {
        proxy_pass http://ncb_ocr;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for long-running OCR requests
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    location /health {
        proxy_pass http://ncb_ocr/health;
        access_log off;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/ncb-ocr /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

## Post-Deployment Validation

### 1. Health Checks

```bash
# Check API health
curl http://localhost:8000/health

# Detailed health status
curl http://localhost:8000/health/detailed | jq

# Check all containers
docker compose -f docker-compose.prod.yml ps

# Verify GPU access
docker compose -f docker-compose.prod.yml exec worker nvidia-smi
```

### 2. Functional Testing

```bash
# Send test email with claim
python scripts/send_test_claim.py

# Monitor processing
docker compose -f docker-compose.prod.yml logs -f worker

# Verify submission to NCB
# Check NCB system for test claim

# Verify Google Sheets logging
# Open spreadsheet and check for test entry

# Verify Drive archival
# Check Drive folder for test attachment
```

### 3. Performance Testing

```bash
# Run load test
python scripts/load_test.py --claims 10

# Monitor resource usage
docker stats

# Check GPU utilization
watch -n 1 nvidia-smi

# Verify queue processing
docker compose -f docker-compose.prod.yml exec redis redis-cli INFO
```

### 4. Alert Testing

```bash
# Trigger test alert
python scripts/trigger_test_alert.py

# Verify email received by ops team

# Test exception queue
python scripts/send_low_confidence_claim.py

# Verify exception dashboard shows item
```

## Health Monitoring

### 1. Application Monitoring

**Prometheus Setup:**

```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=secure-password

volumes:
  prometheus-data:
  grafana-data:
```

**prometheus.yml:**

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'ncb-ocr'
    static_configs:
      - targets: ['api:9090']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']

  - job_name: 'docker'
    static_configs:
      - targets: ['host.docker.internal:9323']
```

### 2. Log Aggregation

```bash
# Configure Docker logging
# In docker-compose.prod.yml

services:
  api:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**Centralized logging with Loki:**

```bash
# Add Loki to monitoring stack
docker compose -f docker-compose.monitoring.yml up -d loki

# Configure Grafana data source for Loki
# View logs in Grafana
```

### 3. Alerting Rules

```yaml
# alerting_rules.yml
groups:
  - name: ncb-ocr-alerts
    interval: 30s
    rules:
      - alert: ServiceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Service {{ $labels.job }} is down"

      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"

      - alert: QueueBacklog
        expr: redis_queue_length > 100
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Queue backlog exceeds threshold"

      - alert: GPUUtilizationLow
        expr: gpu_utilization < 20
        for: 30m
        labels:
          severity: info
        annotations:
          summary: "GPU utilization is low"
```

### 4. Monitoring Dashboard

**Key Metrics to Monitor:**

| Metric | Threshold | Action |
|--------|-----------|--------|
| API response time | >5s | Investigate |
| Error rate | >5% | Alert ops team |
| Queue length | >100 | Scale workers |
| GPU utilization | <20% or >95% | Adjust batch size |
| Memory usage | >90% | Scale or optimize |
| Disk usage | >80% | Clean temp files |

## Backup and Recovery

### 1. Backup Strategy

**Daily Backups:**

```bash
#!/bin/bash
# /opt/ncb-ocr/scripts/daily_backup.sh

DATE=$(date +%Y%m%d)
BACKUP_DIR="/opt/ncb-ocr/backups"

# Backup Redis data
docker compose -f /opt/ncb-ocr/docker-compose.prod.yml exec redis redis-cli BGSAVE
sleep 10
docker cp ncb_ocr_redis:/data/dump.rdb "$BACKUP_DIR/redis_$DATE.rdb"

# Backup configuration
tar czf "$BACKUP_DIR/config_$DATE.tar.gz" \
  /opt/ncb-ocr/.env.prod \
  /opt/ncb-ocr/docker-compose.prod.yml

# Backup logs
tar czf "$BACKUP_DIR/logs_$DATE.tar.gz" \
  /opt/ncb-ocr/data/logs

# Remove backups older than 30 days
find "$BACKUP_DIR" -name "*.rdb" -mtime +30 -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete

# Upload to remote storage (optional)
# aws s3 sync "$BACKUP_DIR" s3://company-backups/ncb-ocr/
```

**Schedule with cron:**

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /opt/ncb-ocr/scripts/daily_backup.sh >> /opt/ncb-ocr/logs/backup.log 2>&1
```

### 2. Recovery Procedures

**Restore from Backup:**

```bash
#!/bin/bash
# scripts/restore.sh

BACKUP_DATE=$1

if [ -z "$BACKUP_DATE" ]; then
  echo "Usage: $0 YYYYMMDD"
  exit 1
fi

cd /opt/ncb-ocr

# Stop services
docker compose -f docker-compose.prod.yml down

# Restore Redis data
docker cp "backups/redis_$BACKUP_DATE.rdb" ncb_ocr_redis:/data/dump.rdb

# Restore configuration
tar xzf "backups/config_$BACKUP_DATE.tar.gz" -C /

# Start services
docker compose -f docker-compose.prod.yml up -d

echo "Restore completed from $BACKUP_DATE"
```

### 3. Disaster Recovery Plan

**RTO (Recovery Time Objective):** 4 hours
**RPO (Recovery Point Objective):** 24 hours

**Recovery Steps:**

1. **Provision new server** (1 hour)
2. **Install dependencies** (30 minutes)
3. **Restore from backup** (1 hour)
4. **Validate services** (30 minutes)
5. **Update DNS/routing** (1 hour)

**Testing Schedule:**
- Monthly DR drills
- Quarterly full recovery tests

## Scaling Considerations

### Horizontal Scaling

```yaml
# Scale OCR workers
services:
  worker:
    deploy:
      replicas: 3
```

```bash
# Scale at runtime
docker compose -f docker-compose.prod.yml up -d --scale worker=5
```

### Vertical Scaling

```yaml
# Increase resources per container
services:
  worker:
    deploy:
      resources:
        limits:
          cpus: '8'
          memory: 16G
```

### Load Balancing

**Multiple API instances:**

```yaml
services:
  api:
    deploy:
      replicas: 2
```

**Nginx load balancing:**

```nginx
upstream ncb_ocr {
    least_conn;
    server api-1:8000;
    server api-2:8000;
}
```

### Auto-scaling (Advanced)

Consider Kubernetes for automatic scaling based on metrics:

```yaml
# kubernetes/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ncb-ocr-worker
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ncb-ocr-worker
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## Maintenance Procedures

### Routine Maintenance

**Weekly:**
- Review error logs
- Check disk usage
- Verify backup integrity
- Update dependency CVE scan

**Monthly:**
- Review performance metrics
- Optimize database queries
- Update documentation
- Security audit

### Update Procedures

```bash
#!/bin/bash
# scripts/update.sh

cd /opt/ncb-ocr

# Pull latest changes
git fetch origin
git checkout main
git pull origin main

# Rebuild images
docker compose -f docker-compose.prod.yml build --no-cache

# Stop services gracefully
docker compose -f docker-compose.prod.yml down

# Start updated services
docker compose -f docker-compose.prod.yml up -d

# Verify health
sleep 30
curl http://localhost:8000/health

# Monitor logs
docker compose -f docker-compose.prod.yml logs -f
```

### Database Migrations

```bash
# Run migrations
docker compose -f docker-compose.prod.yml run --rm api python scripts/migrate.py

# Verify migration
docker compose -f docker-compose.prod.yml run --rm api python scripts/verify_migration.py
```

## Security Hardening

### 1. Container Security

```yaml
# docker-compose.prod.yml
services:
  api:
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
    read_only: true
    tmpfs:
      - /tmp
```

### 2. Network Security

```bash
# Restrict Docker network
docker network create --internal backend

# Use internal network for Redis
services:
  redis:
    networks:
      - backend
```

### 3. Secret Management

Consider using Docker Secrets or HashiCorp Vault:

```yaml
secrets:
  ncb_api_key:
    file: ./secrets/ncb_api_key.txt

services:
  api:
    secrets:
      - ncb_api_key
```

### 4. Image Scanning

```bash
# Scan images for vulnerabilities
docker scan ncb-ocr-api:latest

# Use Trivy
trivy image ncb-ocr-api:latest
```

### 5. Audit Logging

```bash
# Enable Docker audit logging
sudo auditctl -w /usr/bin/docker -k docker
sudo auditctl -w /var/lib/docker -k docker

# Review audit logs
sudo ausearch -k docker
```

## Rollback Procedures

### Quick Rollback

```bash
#!/bin/bash
# scripts/rollback.sh

VERSION=$1

if [ -z "$VERSION" ]; then
  echo "Usage: $0 <version>"
  exit 1
fi

cd /opt/ncb-ocr

# Stop current services
docker compose -f docker-compose.prod.yml down

# Checkout previous version
git checkout "tags/v$VERSION"

# Start services
docker compose -f docker-compose.prod.yml up -d

# Verify
curl http://localhost:8000/health

echo "Rolled back to version $VERSION"
```

### Emergency Stop

```bash
# Immediate stop all services
docker compose -f /opt/ncb-ocr/docker-compose.prod.yml down

# Clear queues if needed
docker compose -f /opt/ncb-ocr/docker-compose.prod.yml exec redis redis-cli FLUSHDB
```

## Support and Escalation

### Contact Information

| Role | Contact | Escalation |
|------|---------|------------|
| L1 Support | ops@company.com | 15 minutes |
| L2 DevOps | devops@company.com | 30 minutes |
| L3 Engineering | engineering@company.com | 1 hour |
| Management | manager@company.com | Critical only |

### Incident Response

1. **Detect** - Monitoring alerts triggered
2. **Assess** - Determine severity
3. **Respond** - Follow runbook
4. **Escalate** - If unresolved in SLA
5. **Document** - Post-mortem report

## References

- [Docker Security](https://docs.docker.com/engine/security/)
- [NVIDIA Container Best Practices](https://docs.nvidia.com/deeplearning/frameworks/user-guide/)
- [Production Checklist](https://docs.docker.com/compose/production/)

## Appendix

### A. Environment Variable Reference

See `.env.example` for complete list.

### B. API Endpoints

See `docs/API_CONTRACTS.md` for detailed API documentation.

### C. Runbooks

See `docs/runbooks/` directory for specific incident procedures.
