# Gmail Watch + Google Cloud Pub/Sub Setup Guide

## Overview

This guide explains how to configure Gmail Push Notifications using Google Cloud Pub/Sub to **completely eliminate rate limiting issues**.

### Why Pub/Sub Instead of Polling?

**Polling (Old Method)**:
- Checks Gmail every 30-60 seconds
- 1,440-2,880 API calls per day
- Triggers rate limiting with burst patterns
- Wastes quota even when no emails arrive

**Pub/Sub (New Method)**:
- Gmail sends push notification when email arrives
- Near-zero quota usage (only API calls when needed)
- No rate limiting issues
- Real-time email processing

### Quota Comparison

| Method | Daily API Calls | Quota Usage | Rate Limit Risk |
|--------|----------------|-------------|-----------------|
| **Polling** (60s) | 1,440 | 7,200-727,000 units | **HIGH** |
| **Pub/Sub** (push) | ~10-50 | 50-250 units | **NONE** |

## Prerequisites

1. Google Cloud Project with billing enabled
2. Gmail API enabled
3. Pub/Sub API enabled
4. Service account or OAuth credentials

## Step-by-Step Setup

### 1. Enable Required APIs

```bash
# Enable Pub/Sub API
gcloud services enable pubsub.googleapis.com --project=YOUR_PROJECT_ID

# Enable Gmail API (if not already enabled)
gcloud services enable gmail.googleapis.com --project=YOUR_PROJECT_ID
```

### 2. Create Pub/Sub Topic

```bash
# Create topic for Gmail notifications
gcloud pubsub topics create gmail-notifications --project=YOUR_PROJECT_ID

# Grant Gmail permission to publish to topic
gcloud pubsub topics add-iam-policy-binding gmail-notifications \
  --member=serviceAccount:gmail-api-push@system.gserviceaccount.com \
  --role=roles/pubsub.publisher \
  --project=YOUR_PROJECT_ID
```

**Why this works**: Gmail's internal service account needs permission to send notifications to your Pub/Sub topic.

### 3. Create Pub/Sub Subscription

```bash
# Create subscription for your application
gcloud pubsub subscriptions create gmail-notifications-sub \
  --topic=gmail-notifications \
  --ack-deadline=60 \
  --project=YOUR_PROJECT_ID
```

**Parameters explained**:
- `ack-deadline=60`: Message must be processed within 60 seconds
- Subscription pulls messages and delivers to your application

### 4. Grant Application Permissions

**Option A: Service Account (Recommended for Production)**

```bash
# Create service account
gcloud iam service-accounts create claims-processor \
  --display-name="Claims Data Entry Agent" \
  --project=YOUR_PROJECT_ID

# Grant Pub/Sub subscriber role
gcloud pubsub subscriptions add-iam-policy-binding gmail-notifications-sub \
  --member=serviceAccount:claims-processor@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/pubsub.subscriber \
  --project=YOUR_PROJECT_ID

# Download service account key
gcloud iam service-accounts keys create service-account-key.json \
  --iam-account=claims-processor@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --project=YOUR_PROJECT_ID
```

**Option B: OAuth User Credentials (Development)**

Your existing Gmail OAuth credentials will work if your account has Pub/Sub permissions.

### 5. Configure Environment Variables

Add to `.env`:

```bash
# Google Cloud Project
GOOGLE_CLOUD_PROJECT_ID=your-project-id

# Pub/Sub Configuration
GMAIL_PUBSUB_TOPIC=gmail-notifications
GMAIL_PUBSUB_SUBSCRIPTION=gmail-notifications-sub

# Optional: Service Account Key (if using Option A)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

### 6. Update Docker Compose

If using service account, mount the credentials:

```yaml
services:
  app:
    environment:
      - GOOGLE_APPLICATION_CREDENTIALS=/app/secrets/service-account-key.json
    volumes:
      - ./service-account-key.json:/app/secrets/service-account-key.json:ro
```

### 7. Switch from Polling to Pub/Sub

**Edit `src/main.py`:**

```python
# BEFORE (polling)
from src.workers.email_poller import EmailPollerWorker
email_worker = EmailPollerWorker()
workers["email_poller"] = asyncio.create_task(email_worker.run())

# AFTER (pub/sub)
from src.workers.email_watch_listener import EmailWatchListener
email_worker = EmailWatchListener()
workers["email_watch_listener"] = asyncio.create_task(email_worker.run())
```

### 8. Start the Application

```bash
docker compose up -d app
```

**What happens on startup**:
1. Application sets up Gmail watch
2. Gmail starts sending push notifications to Pub/Sub
3. Application listens to Pub/Sub subscription
4. When email arrives → instant processing (no polling!)

### 9. Verify Setup

**Check logs:**
```bash
docker compose logs app -f | grep -E "(watch|pub/sub|notification)"
```

**Expected output:**
```
[info] Gmail watch listener started
[info] Gmail watch enabled, expires_at=2025-12-31T12:00:00
[info] Listening to Pub/Sub subscription
```

**When email arrives:**
```
[info] Received Gmail notification, history_id=12345
[info] Processing emails from notification, count=1
[info] Batch metadata fetch completed, successful=1
```

## Troubleshooting

### Error: "Permission denied on topic"

**Solution:**
```bash
# Verify Gmail service account has publisher role
gcloud pubsub topics get-iam-policy gmail-notifications \
  --project=YOUR_PROJECT_ID

# Re-add if missing
gcloud pubsub topics add-iam-policy-binding gmail-notifications \
  --member=serviceAccount:gmail-api-push@system.gserviceaccount.com \
  --role=roles/pubsub.publisher \
  --project=YOUR_PROJECT_ID
```

### Error: "Subscription not found"

**Solution:**
```bash
# List subscriptions
gcloud pubsub subscriptions list --project=YOUR_PROJECT_ID

# Create if missing
gcloud pubsub subscriptions create gmail-notifications-sub \
  --topic=gmail-notifications \
  --project=YOUR_PROJECT_ID
```

### Error: "Gmail watch expired"

**Cause**: Gmail watch expires after 7 days

**Solution**: The worker **automatically renews** watch 1 day before expiration. Check logs:
```
[info] Renewing Gmail watch (expiring soon)
[info] Gmail watch enabled, expires_at=2025-12-31T12:00:00
```

### No notifications received

**Debugging steps:**
```bash
# 1. Check if watch is active
curl -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://gmail.googleapis.com/gmail/v1/users/me/watch"

# 2. Send test email to trigger notification
# 3. Check Pub/Sub metrics
gcloud pubsub subscriptions describe gmail-notifications-sub \
  --project=YOUR_PROJECT_ID

# 4. Pull message manually
gcloud pubsub subscriptions pull gmail-notifications-sub \
  --limit=1 \
  --project=YOUR_PROJECT_ID
```

## Monitoring

### View Pub/Sub Metrics

```bash
# Subscription metrics
gcloud pubsub subscriptions describe gmail-notifications-sub \
  --project=YOUR_PROJECT_ID

# Topic metrics
gcloud pubsub topics describe gmail-notifications \
  --project=YOUR_PROJECT_ID
```

### Monitor in Google Cloud Console

1. Visit: https://console.cloud.google.com/cloudpubsub
2. Select your project
3. View **gmail-notifications** topic
4. Check:
   - Message publish rate
   - Subscription delivery rate
   - Acknowledgment rate

## Cost Estimate

Pub/Sub is extremely cheap for this use case:

**Pricing** (as of 2025):
- First 10 GB/month: **FREE**
- Additional data: $0.04 per GB

**Typical usage**:
- ~100 emails/day = ~10KB notifications/day
- Monthly: ~300KB = **FREE tier**

**Total cost: $0/month** (well within free tier)

## Security Best Practices

1. **Use Service Account** (not personal OAuth)
2. **Least Privilege**: Only grant `pubsub.subscriber` role
3. **Rotate Keys**: Regenerate service account keys periodically
4. **Monitor Access**: Review IAM logs for unexpected access
5. **Enable VPC Service Controls** (optional, enterprise)

## Rollback to Polling

If needed, switch back to polling:

```python
# In src/main.py
from src.workers.email_poller import EmailPollerWorker
email_worker = EmailPollerWorker()
workers["email_poller"] = asyncio.create_task(email_worker.run())
```

No other changes needed - both workers use the same batch request implementation.

## Advanced Configuration

### Custom Ack Deadline

```bash
# Increase for slow processing
gcloud pubsub subscriptions update gmail-notifications-sub \
  --ack-deadline=120 \
  --project=YOUR_PROJECT_ID
```

### Dead Letter Topic

```bash
# Create dead letter topic for failed messages
gcloud pubsub topics create gmail-notifications-dlq \
  --project=YOUR_PROJECT_ID

# Update subscription
gcloud pubsub subscriptions update gmail-notifications-sub \
  --dead-letter-topic=gmail-notifications-dlq \
  --max-delivery-attempts=5 \
  --project=YOUR_PROJECT_ID
```

### Multiple Subscriptions

```bash
# Create multiple subscriptions for load balancing
gcloud pubsub subscriptions create gmail-notifications-sub-2 \
  --topic=gmail-notifications \
  --project=YOUR_PROJECT_ID
```

## Summary

✅ **Setup complete when you see:**
- Gmail watch enabled (7-day expiration)
- Listening to Pub/Sub subscription
- Real-time notifications on email arrival
- No rate limit errors

✅ **Benefits:**
- **98%+ quota reduction** vs polling
- **Zero rate limit risk**
- **Real-time processing** (instant, not 30-60s delay)
- **Auto-renewing** watch (7-day cycle)
- **Production-ready** architecture

---

**Created**: 2025-12-25 03:00 UTC  
**Status**: Ready for deployment  
**Prerequisites**: Google Cloud Project + Billing
