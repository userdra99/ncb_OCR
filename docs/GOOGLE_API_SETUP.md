# Google API Setup Guide

## ✅ Service Account Created

Your service account credentials are already in place:
- **File:** `secrets/service-account-credentials.json`
- **Project:** ncb-ocr-test
- **Email:** claims-data-entry-agent@ncb-ocr-test.iam.gserviceaccount.com

## 🔧 Next Steps

### 1. Enable Required APIs

Go to [Google Cloud Console](https://console.cloud.google.com/apis/library?project=ncb-ocr-test):

```bash
# Enable these APIs:
✅ Gmail API - https://console.cloud.google.com/apis/library/gmail.googleapis.com
✅ Google Sheets API - https://console.cloud.google.com/apis/library/sheets.googleapis.com
✅ Google Drive API - https://console.cloud.google.com/apis/library/drive.googleapis.com
```

### 2. Configure Gmail Domain-Wide Delegation

**For Gmail API to work with service accounts:**

1. Go to [Google Workspace Admin Console](https://admin.google.com)
2. Navigate to: **Security → API controls → Domain-wide delegation**
3. Click **Add new**
4. Enter Client ID: `116817852550275478734`
5. Add OAuth scopes:
   ```
   https://www.googleapis.com/auth/gmail.readonly
   https://www.googleapis.com/auth/gmail.modify
   ```
6. Click **Authorize**

**OR use OAuth2 for Gmail (if no domain-wide access):**

If you don't have Google Workspace admin access, you'll need to switch Gmail to OAuth2 flow. Let me know if you need this alternative setup.

### 3. Create Google Sheets Spreadsheet

```bash
# 1. Create new spreadsheet
https://sheets.google.com

# 2. Share with service account email:
claims-data-entry-agent@ncb-ocr-test.iam.gserviceaccount.com
(Give "Editor" permission)

# 3. Copy Spreadsheet ID from URL:
https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit
                                      ^^^^^^^^^^^^^^^^^^^^

# 4. Update .env:
SHEETS_SPREADSHEET_ID=your-spreadsheet-id-here
```

**Required columns in Sheet:**
- Timestamp
- Email ID
- Attachment Filename
- Member ID
- Member Name
- Service Date
- Amount
- Confidence Score
- Status
- Error Message (if any)

### 4. Create Google Drive Folder

```bash
# 1. Create folder for archiving receipts
https://drive.google.com

# 2. Share with service account email:
claims-data-entry-agent@ncb-ocr-test.iam.gserviceaccount.com
(Give "Editor" permission)

# 3. Copy Folder ID from URL:
https://drive.google.com/drive/folders/{FOLDER_ID}
                                        ^^^^^^^^^^^

# 4. Update .env:
DRIVE_FOLDER_ID=your-folder-id-here
```

### 5. Update .env File

Already configured in `.env`, but you need to update:

```bash
# Google Sheets
SHEETS_SPREADSHEET_ID=your-spreadsheet-id-here  # Replace with actual ID

# Google Drive
DRIVE_FOLDER_ID=your-folder-id-here  # Replace with actual ID

# NCB API (get from NCB team)
NCB_API_BASE_URL=https://ncb.internal.company.com/api/v1
NCB_API_KEY=your-ncb-api-key-here
```

## 🧪 Test API Access

```bash
# Start Redis
docker-compose up -d redis

# Test Google APIs
python -c "
from google.oauth2 import service_account
from googleapiclient.discovery import build

creds = service_account.Credentials.from_service_account_file(
    'secrets/service-account-credentials.json',
    scopes=['https://www.googleapis.com/auth/spreadsheets']
)

sheets = build('sheets', 'v4', credentials=creds)
print('✅ Sheets API connected')

drive = build('drive', 'v3', credentials=creds)
print('✅ Drive API connected')
"
```

## 📋 Gmail Setup Options

### Option A: Domain-Wide Delegation (Recommended for production)
- Requires Google Workspace admin access
- Service account can access any user's Gmail
- Follow step 2 above

### Option B: OAuth2 Flow (For testing without admin access)
If you don't have domain-wide delegation, let me know and I'll update the code to use OAuth2 with user consent flow.

## 🚀 Ready to Deploy

Once you've:
1. ✅ Enabled APIs
2. ✅ Configured Gmail delegation (or chosen OAuth2)
3. ✅ Created and shared Spreadsheet
4. ✅ Created and shared Drive folder
5. ✅ Updated `.env` with IDs
6. ✅ Got NCB API credentials

Then run:

```bash
# Development
docker-compose up -d

# Production
docker-compose -f docker-compose.prod.yml up -d
```

## 🔍 Verification

```bash
# Check logs
docker logs claims-app -f

# Should see:
# ✅ Gmail API authenticated
# ✅ Sheets API connected
# ✅ Drive API connected
# ✅ GPU detected: RTX 5090
# ✅ Redis connected
```

## ⚠️ Security Notes

- ✅ `secrets/` directory is in `.gitignore` - credentials won't be committed
- ✅ File permissions set to 600 (owner read/write only)
- ✅ Docker mounts secrets as read-only

**Never commit service account credentials to git!**
