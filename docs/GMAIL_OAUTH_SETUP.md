# Gmail OAuth2 Setup for Personal Gmail

This guide shows how to set up Gmail API access for **personal Gmail accounts** using OAuth2 user consent flow.

## 📋 Prerequisites

- Personal Gmail account (not Google Workspace)
- Google Cloud project: `ncb-ocr-test`
- Gmail API enabled (done ✅)

## 🔧 Step-by-Step Setup

### 1. Create OAuth2 Desktop Credentials

Go to: [Google Cloud Console - Credentials](https://console.cloud.google.com/apis/credentials?project=ncb-ocr-test)

1. Click **"+ CREATE CREDENTIALS"** → **"OAuth client ID"**
2. If prompted, configure OAuth consent screen:
   - User Type: **External**
   - App name: `Claims Data Entry Agent`
   - User support email: Your email
   - Developer contact: Your email
   - Scopes: Add manually later
   - Test users: Add your Gmail address
   - Click **Save and Continue** through all steps

3. Create OAuth client ID:
   - Application type: **Desktop app**
   - Name: `Claims Agent - Desktop`
   - Click **Create**

4. Download the JSON file:
   - Click the **Download** icon (⬇) next to your newly created OAuth client
   - Save as: `gmail-oauth-credentials.json`

### 2. Move Credentials to Project

```bash
# Move downloaded file to secrets directory
mv ~/Downloads/client_secret_*.json /home/dra/projects/ncb_OCR/secrets/gmail-oauth-credentials.json

# Set secure permissions
chmod 600 /home/dra/projects/ncb_OCR/secrets/gmail-oauth-credentials.json
```

### 3. Run OAuth2 Authorization

This opens a browser for one-time Gmail login:

```bash
cd /home/dra/projects/ncb_OCR

# Install dependencies
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client

# Run authorization script
python scripts/gmail-auth.py
```

**What happens:**
1. Browser opens with Google login
2. Login with your Gmail account
3. Google shows permissions request:
   - ✅ "Read, compose, send, and permanently delete all your email from Gmail"
   - ✅ "Manage your basic mail settings"
4. Click **Allow**
5. Browser shows "Authorization successful!"
6. Token saved to `secrets/gmail_token.json`

### 4. Add Test User (if using External app)

If you configured OAuth consent as "External":

1. Go to: [OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent?project=ncb-ocr-test)
2. Scroll to **Test users**
3. Click **"+ ADD USERS"**
4. Enter your Gmail address
5. Click **Save**

**Note:** External apps are limited to 100 test users. For production, you'd need to verify the app.

### 5. Verify Setup

```bash
# Check files exist
ls -lh secrets/
# Should see:
# - gmail-oauth-credentials.json (OAuth2 client credentials)
# - gmail_token.json (Generated after authorization)
# - service-account-credentials.json (For Sheets/Drive)
```

### 6. Update .env (Already Done)

`.env` is already configured:

```bash
GMAIL_CREDENTIALS_PATH=/app/secrets/gmail-oauth-credentials.json
GMAIL_TOKEN_PATH=/app/secrets/gmail_token.json
```

## 🚀 Start Application

```bash
# Development
docker-compose up -d

# Check logs
docker logs claims-app -f

# Should see:
# ✅ Successfully authenticated with Gmail API
```

## 🔄 Token Refresh

- OAuth2 tokens expire after 1 hour
- Refresh tokens are valid for 6 months (or until revoked)
- The app **automatically refreshes** expired tokens
- No manual intervention needed

## ⚠️ Troubleshooting

### Error: "Access blocked: This app's request is invalid"

**Cause:** OAuth consent screen not configured

**Fix:**
1. Go to [OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent?project=ncb-ocr-test)
2. Fill in all required fields
3. Add your email to Test users
4. Try authorization again

### Error: "invalid_grant"

**Cause:** Token expired or revoked

**Fix:**
```bash
# Delete old token
rm secrets/gmail_token.json

# Re-run authorization
python scripts/gmail-auth.py
```

### Error: "redirect_uri_mismatch"

**Cause:** OAuth client is "Web application" instead of "Desktop app"

**Fix:**
1. Delete the OAuth client in Cloud Console
2. Create new one with type **Desktop app**
3. Download new credentials
4. Re-run authorization

## 🔐 Security Notes

**Files in `secrets/` directory:**
- ✅ `.gitignore` prevents commits
- ✅ File permissions: 600 (owner read/write only)
- ✅ Docker mounts as read-only in container

**OAuth2 Scopes:**
- `https://www.googleapis.com/auth/gmail.readonly` - Read emails
- `https://www.googleapis.com/auth/gmail.modify` - Add labels, mark as read

## 📊 What Gets Accessed

The app will:
- ✅ Read emails from INBOX
- ✅ Download attachments (images)
- ✅ Add "Claims/Processed" label
- ✅ Mark emails as read

The app will NOT:
- ❌ Send emails
- ❌ Delete emails
- ❌ Access contacts
- ❌ Access calendar

## 🔗 Revoke Access (if needed)

To revoke app access:
1. Go to: https://myaccount.google.com/permissions
2. Find "Claims Data Entry Agent"
3. Click **Remove Access**

To re-authorize, run `python scripts/gmail-auth.py` again.

## 🎯 Next Steps

After Gmail is set up, configure:

1. **Google Sheets** - For audit logging
2. **Google Drive** - For receipt archiving
3. **NCB API** - For claim submission

See: `docs/GOOGLE_API_SETUP.md` for Sheets/Drive setup.
