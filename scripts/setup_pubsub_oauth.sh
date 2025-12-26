#!/bin/bash
# Quick setup script for Gmail Pub/Sub using existing OAuth credentials

set -e

echo "🚀 Gmail Pub/Sub Setup (OAuth Mode)"
echo "===================================="
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Please install:"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Get project ID
echo "📋 Step 1: Get Project ID"
if [ -f "config/gmail_credentials.json" ]; then
    PROJECT_ID=$(cat config/gmail_credentials.json | grep -o '"project_id": *"[^"]*"' | cut -d'"' -f4)
    echo "   Found project ID: $PROJECT_ID"
else
    echo "   Enter your Google Cloud Project ID:"
    read -r PROJECT_ID
fi

# Validate project ID
if [ -z "$PROJECT_ID" ]; then
    echo "❌ Project ID is required"
    exit 1
fi

echo ""
echo "🔧 Step 2: Enable Pub/Sub API"
gcloud services enable pubsub.googleapis.com --project="$PROJECT_ID"
echo "   ✅ Pub/Sub API enabled"

echo ""
echo "📢 Step 3: Create Pub/Sub Topic"
if gcloud pubsub topics describe gmail-notifications --project="$PROJECT_ID" &> /dev/null; then
    echo "   ℹ️  Topic 'gmail-notifications' already exists"
else
    gcloud pubsub topics create gmail-notifications --project="$PROJECT_ID"
    echo "   ✅ Topic created"
fi

echo ""
echo "🔐 Step 4: Grant Gmail Permission to Publish"
gcloud pubsub topics add-iam-policy-binding gmail-notifications \
  --member=serviceAccount:gmail-api-push@system.gserviceaccount.com \
  --role=roles/pubsub.publisher \
  --project="$PROJECT_ID" &> /dev/null
echo "   ✅ Gmail can publish to topic"

echo ""
echo "📥 Step 5: Create Subscription"
if gcloud pubsub subscriptions describe gmail-notifications-sub --project="$PROJECT_ID" &> /dev/null; then
    echo "   ℹ️  Subscription 'gmail-notifications-sub' already exists"
else
    gcloud pubsub subscriptions create gmail-notifications-sub \
      --topic=gmail-notifications \
      --ack-deadline=60 \
      --project="$PROJECT_ID"
    echo "   ✅ Subscription created"
fi

echo ""
echo "👤 Step 6: Grant Your Account Access"
YOUR_EMAIL=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
echo "   Your account: $YOUR_EMAIL"

gcloud pubsub subscriptions add-iam-policy-binding gmail-notifications-sub \
  --member=user:$YOUR_EMAIL \
  --role=roles/pubsub.subscriber \
  --project="$PROJECT_ID" &> /dev/null
echo "   ✅ Granted Pub/Sub access to your account"

echo ""
echo "📝 Step 7: Update .env File"
if ! grep -q "GOOGLE_CLOUD_PROJECT_ID" .env 2>/dev/null; then
    echo "" >> .env
    echo "# Google Cloud Pub/Sub Configuration" >> .env
    echo "GOOGLE_CLOUD_PROJECT_ID=$PROJECT_ID" >> .env
    echo "GMAIL_PUBSUB_TOPIC=gmail-notifications" >> .env
    echo "GMAIL_PUBSUB_SUBSCRIPTION=gmail-notifications-sub" >> .env
    echo "   ✅ Added Pub/Sub config to .env"
else
    echo "   ℹ️  .env already contains GOOGLE_CLOUD_PROJECT_ID"
    echo "   Verify: GOOGLE_CLOUD_PROJECT_ID=$PROJECT_ID"
fi

echo ""
echo "🔄 Step 8: Regenerate OAuth Token"
echo "   The OAuth token needs the 'pubsub' scope."
echo ""
echo "   Run these commands:"
echo "   1. rm config/gmail_token.json"
echo "   2. docker compose restart app"
echo "   3. Follow OAuth flow in browser"
echo ""

echo "✅ Setup Complete!"
echo ""
echo "📚 Next Steps:"
echo "   1. Regenerate OAuth token (see above)"
echo "   2. Update src/main.py to use EmailWatchListener"
echo "   3. Deploy: docker compose up -d app"
echo ""
echo "📖 Full guide: docs/PUBSUB_OAUTH_SETUP.md"
