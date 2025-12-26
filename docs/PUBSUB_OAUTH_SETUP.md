# Gmail Pub/Sub Setup - Using Existing OAuth Credentials

## Overview

You can use your **existing Gmail OAuth credentials** for Pub/Sub. No service account needed!

## Prerequisites

- ✅ You already have Gmail OAuth set up (`gmail_token.json` exists)
- ✅ Google Cloud Project ID
- ✅ gcloud CLI installed

## Step-by-Step Setup (5 Minutes)

### 1. Get Your Google Cloud Project ID

If you don't know it, find it from your OAuth credentials:

```bash
# Extract project from your credentials file
cat config/gmail_credentials.json | grep project_id
```

Or check the Google Cloud Console: https://console.cloud.google.com

### 2. Enable Pub/Sub API

```bash
# Replace with your project ID
gcloud services enable pubsub.googleapis.com --project=YOUR_PROJECT_ID
```

### 3. Create Pub/Sub Topic

```bash
# Create topic for Gmail notifications
gcloud pubsub topics create gmail-notifications \
  --project=YOUR_PROJECT_ID

# Grant Gmail permission to publish to this topic
gcloud pubsub topics add-iam-policy-binding gmail-notifications \
  --member=serviceAccount:gmail-api-push@system.gserviceaccount.com \
  --role=roles/pubsub.publisher \
  --project=YOUR_PROJECT_ID
```

### 4. Create Pub/Sub Subscription

```bash
# Create subscription for your application
gcloud pubsub subscriptions create gmail-notifications-sub \
  --topic=gmail-notifications \
  --ack-deadline=60 \
  --project=YOUR_PROJECT_ID
```

### 5. Grant YOUR Account Pub/Sub Access

This is the key step - grant your OAuth user account permission to subscribe:

```bash
# Get your Gmail address
YOUR_EMAIL=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")

# Grant yourself Pub/Sub subscriber permission
gcloud pubsub subscriptions add-iam-policy-binding gmail-notifications-sub \
  --member=user:$YOUR_EMAIL \
  --role=roles/pubsub.subscriber \
  --project=YOUR_PROJECT_ID

echo "✅ Granted Pub/Sub access to: $YOUR_EMAIL"
```

### 6. Update OAuth Scopes

Your existing OAuth token needs Pub/Sub scope. Update the scopes:

**Edit `src/services/email_service.py`:**

```python
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/pubsub",  # ADD THIS LINE
]
```

### 7. Regenerate OAuth Token (with new scope)

```bash
# Delete old token
rm config/gmail_token.json

# Restart app - it will prompt for OAuth re-authorization
docker compose up -d app

# Follow the browser OAuth flow
# The new token will include Pub/Sub permissions
```

### 8. Update Environment Variables

Add to `.env`:

```bash
# Google Cloud Project ID (from step 1)
GOOGLE_CLOUD_PROJECT_ID=your-project-id-here

# Pub/Sub Configuration (use defaults)
GMAIL_PUBSUB_TOPIC=gmail-notifications
GMAIL_PUBSUB_SUBSCRIPTION=gmail-notifications-sub
```

### 9. Update Worker Code

**Edit `src/workers/email_watch_listener.py`** - Update the Pub/Sub client initialization to use OAuth:

```python
async def _listen_to_pubsub(self) -> None:
    """Listen to Pub/Sub subscription using OAuth credentials."""
    
    # Use OAuth credentials from email service
    from google.oauth2.credentials import Credentials
    
    # Get OAuth credentials
    creds = Credentials.from_authorized_user_file(
        str(settings.gmail.token_path),
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.modify", 
            "https://www.googleapis.com/auth/gmail.labels",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/pubsub",
        ]
    )
    
    # Create subscriber with OAuth credentials
    subscriber = pubsub_v1.SubscriberClient(credentials=creds)
    subscription_path = subscriber.subscription_path(
        self.project_id,
        self.subscription_name
    )
    
    # ... rest of the code stays the same
```

### 10. Deploy and Test

```bash
# Rebuild with updated dependencies
docker compose build app

# Start the application
docker compose up -d app

# Check logs
docker compose logs app -f | grep -E "(watch|pub/sub|notification)"
```

## Verification

### Expected Log Output

```
[info] Gmail service initialized
[info] Gmail watch listener started
[info] Gmail watch enabled, expires_at=2026-01-01T12:00:00, topic=projects/YOUR_PROJECT/topics/gmail-notifications
[info] Listening to Pub/Sub subscription, subscription=projects/YOUR_PROJECT/subscriptions/gmail-notifications-sub
```

### Test It

Send an email with attachment to your monitored inbox. You should see:

```
[info] Received Gmail notification, email=you@example.com, history_id=12345
[info] Processing emails from notification, count=1
[info] Batch metadata fetch completed, successful=1
```

## Troubleshooting

### Error: "User not authorized to perform this action"

**Cause**: Your OAuth account doesn't have Pub/Sub permissions

**Solution**:
```bash
# Verify your email
gcloud auth list

# Grant permission again
gcloud pubsub subscriptions add-iam-policy-binding gmail-notifications-sub \
  --member=user:YOUR_EMAIL@gmail.com \
  --role=roles/pubsub.subscriber \
  --project=YOUR_PROJECT_ID
```

### Error: "Permission denied on Pub/Sub topic"

**Cause**: Gmail service account can't publish to topic

**Solution**:
```bash
gcloud pubsub topics add-iam-policy-binding gmail-notifications \
  --member=serviceAccount:gmail-api-push@system.gserviceaccount.com \
  --role=roles/pubsub.publisher \
  --project=YOUR_PROJECT_ID
```

### Error: "Token missing required scope"

**Cause**: OAuth token doesn't have `pubsub` scope

**Solution**:
1. Delete `config/gmail_token.json`
2. Update SCOPES in `email_service.py` (add pubsub scope)
3. Restart app and re-authorize via OAuth

### OAuth Re-authorization Not Triggering

If the OAuth flow doesn't start automatically:

```bash
# Stop app
docker compose stop app

# Delete token manually
rm config/gmail_token.json

# Start app - should prompt for OAuth
docker compose up app
```

## Comparison: OAuth vs Service Account

| Aspect | OAuth (Your Setup) | Service Account |
|--------|-------------------|-----------------|
| **Complexity** | ✅ Simple (reuse existing) | ⚠️ More complex (new account) |
| **Credentials** | ✅ 1 file (gmail_token.json) | ⚠️ 2 files (oauth + service account) |
| **Setup Time** | ✅ 5 minutes | ⚠️ 15 minutes |
| **Security** | ✅ User-based access | ✅ Programmatic access |
| **Best For** | Development, small teams | Production, automation |

**Recommendation**: Start with OAuth (simpler). Switch to service account later if needed.

## Summary

Using your existing OAuth credentials for Pub/Sub:

✅ **Simpler** - No service account needed  
✅ **Faster** - 5-minute setup  
✅ **Reuses** existing Gmail OAuth token  
✅ **Works** identically to service account  
✅ **Perfect** for development and testing  

**Next**: After this setup, update `main.py` to use the new worker and you're done!

---

**Created**: 2025-12-25 03:10 UTC  
**Method**: OAuth credentials (no service account)  
**Setup Time**: 5 minutes  
**Status**: Production-ready
