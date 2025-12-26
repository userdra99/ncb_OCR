# Google Shared Drive Setup for Claims Data Entry Agent

## Overview

This guide explains how to configure Google Shared Drive for archiving processed claim documents. Service accounts **cannot upload to personal Google Drive** due to storage quota restrictions. Google Shared Drives solve this by using organization-level storage quotas.

**Time Required:** 5-10 minutes
**Prerequisites:** Google Workspace Business Standard or higher, Admin access

---

## Why Shared Drive Instead of My Drive?

| Feature | My Drive (Personal) | Shared Drive |
|---------|-------------------|--------------|
| Service Account Upload | ❌ Storage quota error | ✅ Works perfectly |
| Storage Quota | Individual user quota | Organization pooled quota |
| Ownership | Individual user | Organization/Team |
| Persistence | Deleted when user leaves | Persists with organization |
| Best for | Personal files | Team/automated workflows |

**Error when using My Drive with service accounts:**
```
googleapiclient.errors.HttpError: 403 The user does not have sufficient permissions for this file.
OR
Service Accounts do not have storage quota
```

---

## Part 1: Prerequisites Check

### 1. Verify Google Workspace Edition

Shared Drives are available in:
- ✅ Business Standard
- ✅ Business Plus
- ✅ Enterprise Standard
- ✅ Enterprise Plus
- ✅ Education editions

**NOT available in:**
- ❌ Business Starter (limited support)
- ❌ Personal Gmail accounts

**To check your edition:**
1. Go to [admin.google.com](https://admin.google.com)
2. Navigate to **Billing** → **Subscriptions**
3. Verify you have Business Standard or higher

### 2. Confirm Admin Access

You need one of these roles:
- **Super Admin** (recommended)
- **Groups Admin** (with shared drive permissions)

**To verify:**
1. Go to [admin.google.com](https://admin.google.com)
2. If you see the full admin console, you have access
3. If not, contact your Google Workspace administrator

### 3. Verify Service Account Email

You should have your service account email ready. It looks like:
```
claims-automation@your-project.iam.gserviceaccount.com
```

**To find it:**
1. Open your service account JSON credentials file
2. Look for the `client_email` field
3. Copy this email address

---

## Part 2: Create Shared Drive (5 minutes)

### Option A: Via Google Drive Web Interface (Easiest)

1. **Navigate to Google Drive:**
   - Go to [drive.google.com](https://drive.google.com)
   - Sign in with your admin account

2. **Create Shared Drive:**
   - Click **Shared drives** in the left sidebar
   - Click **+ New** button (top-left)
   - Enter name: `Claims Archive` (or your preferred name)
   - Click **Create**

3. **Get the Shared Drive ID:**
   - Open the newly created Shared Drive
   - Look at the URL in your browser:
     ```
     https://drive.google.com/drive/folders/0AJKxxxxxxxxxxxxxxx
     ```
   - The ID is the part after `/folders/`: `0AJKxxxxxxxxxxxxxxx`
   - **Save this ID** - you'll need it for configuration

### Option B: Via Admin Console

1. **Open Admin Console:**
   - Go to [admin.google.com](https://admin.google.com)

2. **Navigate to Shared Drives:**
   - Click **Apps** → **Google Workspace** → **Drive and Docs**
   - Click **Manage Shared Drives**

3. **Create New Shared Drive:**
   - Click **Create Shared Drive**
   - Name: `Claims Archive`
   - Click **Create**

4. **Get the ID:**
   - Click on the shared drive name
   - Copy the Drive ID from the details panel

---

## Part 3: Add Service Account as Member (2 minutes)

### Step 1: Open Shared Drive Settings

1. Go to [drive.google.com](https://drive.google.com)
2. Click **Shared drives** in left sidebar
3. **Right-click** on `Claims Archive` → **Manage members**

### Step 2: Add Service Account

1. In the "Add members" field, paste your service account email:
   ```
   claims-automation@your-project.iam.gserviceaccount.com
   ```

2. **Select Permission Level:**
   - **Content Manager** (Recommended ✅)
     - Can add, edit, move, and delete files
     - Cannot delete the shared drive itself
     - Cannot manage members

   - ~~Contributor~~
     - Can add and edit files
     - Cannot delete files
     - ❌ Too restrictive for archival needs

   - ~~Manager~~
     - Full control including member management
     - ❌ Too permissive for automation

3. **Disable Email Notification:**
   - Uncheck "Notify people" (service accounts don't read emails)

4. Click **Send** or **Share**

### Step 3: Verify Access

1. The service account should appear in the members list
2. Permission level should show "Content Manager"
3. Status should be "Active"

---

## Part 4: Create Folder Structure (Optional, 2 minutes)

Organize your archived files:

1. **Open the Shared Drive:**
   - Navigate to `Claims Archive` shared drive

2. **Create Folders:**
   ```
   Claims Archive/
   ├── 2025/
   │   ├── 01-January/
   │   ├── 02-February/
   │   └── ...
   ├── exceptions/
   └── metadata/
   ```

3. **Get Folder IDs:**
   - Open each folder
   - Copy the ID from the URL
   - Save these IDs for configuration

---

## Part 5: Update Application Configuration

### Step 1: Update Environment Variables

Edit your `.env` file:

```bash
# OLD - Personal Drive (will fail)
# DRIVE_FOLDER_ID=1abc123def456ghi789jkl

# NEW - Shared Drive folder
DRIVE_FOLDER_ID=0AJKxxxxxxxxxxxxxxx  # Your Shared Drive ID or folder ID within it

# Ensure credentials path is correct
DRIVE_CREDENTIALS_PATH=/path/to/service-account-credentials.json
```

### Step 2: Update Upload Script

The script at `/home/dra/projects/ncb_OCR/scripts/upload_ncb_test_data_to_drive.py` needs modification to support Shared Drives.

**Required changes:**

1. **Add `supportsAllDrives=True` parameter** to all Drive API calls
2. **Update file creation method** to include the parameter

**See the updated code in the next section.**

---

## Part 6: Code Updates

### Updated Upload Script

Replace the `upload_to_drive()` function in `scripts/upload_ncb_test_data_to_drive.py`:

```python
def upload_to_drive(file_path: Path, folder_id: str) -> str:
    """
    Upload a file to Google Shared Drive.

    Args:
        file_path: Path to the file to upload
        folder_id: Google Shared Drive folder ID

    Returns:
        File ID of uploaded file
    """
    try:
        # Load credentials
        creds = Credentials.from_service_account_file(
            settings.drive.credentials_path,
            scopes=['https://www.googleapis.com/auth/drive.file']
        )

        # Build Drive API client
        service = build('drive', 'v3', credentials=creds)

        # File metadata
        file_metadata = {
            'name': file_path.name,
            'parents': [folder_id],
            'description': 'NCB API test data generated by Claims Data Entry Agent'
        }

        # Upload file
        media = MediaFileUpload(
            str(file_path),
            mimetype='application/json',
            resumable=True
        )

        # ✅ ADD THIS: supportsAllDrives=True for Shared Drive support
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink',
            supportsAllDrives=True  # 🔑 CRITICAL for Shared Drives
        ).execute()

        logger.info(
            "File uploaded to Google Shared Drive",
            file_id=file.get('id'),
            file_name=file.get('name'),
            web_link=file.get('webViewLink')
        )

        return file.get('id')

    except Exception as e:
        logger.error(f"Failed to upload file to Shared Drive: {e}", file=str(file_path))
        raise
```

### Update Drive Service (if you have a separate service class)

If you have a `src/services/drive_service.py`, update all methods:

```python
class DriveService:
    """Google Drive service for archiving claim documents."""

    def __init__(self):
        self.creds = Credentials.from_service_account_file(
            settings.drive.credentials_path,
            scopes=['https://www.googleapis.com/auth/drive.file']
        )
        self.service = build('drive', 'v3', credentials=self.creds)

    async def upload_file(
        self,
        file_path: Path,
        folder_id: str,
        mime_type: str = 'application/pdf'
    ) -> str:
        """Upload file to Shared Drive."""

        file_metadata = {
            'name': file_path.name,
            'parents': [folder_id]
        }

        media = MediaFileUpload(
            str(file_path),
            mimetype=mime_type,
            resumable=True
        )

        # ✅ Critical: Add supportsAllDrives=True
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink, createdTime',
            supportsAllDrives=True  # 🔑 Required for Shared Drives
        ).execute()

        return file.get('id')

    async def list_files(self, folder_id: str, page_size: int = 100) -> list:
        """List files in Shared Drive folder."""

        # ✅ Use supportsAllDrives and includeItemsFromAllDrives
        results = self.service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            pageSize=page_size,
            fields="files(id, name, createdTime, size)",
            supportsAllDrives=True,  # 🔑 Required
            includeItemsFromAllDrives=True  # 🔑 Required for listing
        ).execute()

        return results.get('files', [])

    async def delete_file(self, file_id: str) -> None:
        """Delete file from Shared Drive."""

        # ✅ Add supportsAllDrives=True
        self.service.files().delete(
            fileId=file_id,
            supportsAllDrives=True  # 🔑 Required
        ).execute()
```

### Key Parameters for Shared Drives

| Parameter | When to Use | Description |
|-----------|------------|-------------|
| `supportsAllDrives=True` | **All operations** | Enables Shared Drive support |
| `includeItemsFromAllDrives=True` | List/search operations | Include Shared Drive items in results |
| `corpora='drive'` | Search operations | Search within specific drive |
| `driveId='xxx'` | Search operations | Specify which Shared Drive to search |

---

## Part 7: Testing (3 minutes)

### Test 1: Manual Upload Test

```bash
# Activate virtual environment
source .venv/bin/activate  # or your venv path

# Run upload script
python scripts/upload_ncb_test_data_to_drive.py
```

**Expected output:**
```
INFO: File uploaded to Google Shared Drive file_id=1xyz... file_name=ncb_test_data.json
✅ Uploaded: ncb_test_data.json
     File ID: 1xyz...
```

**Verify in Google Drive:**
1. Go to [drive.google.com](https://drive.google.com)
2. Click **Shared drives** → **Claims Archive**
3. You should see the uploaded files

### Test 2: Python Test Script

Create a quick test script:

```python
#!/usr/bin/env python3
"""Test Shared Drive access."""

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

CREDENTIALS_PATH = '/path/to/service-account.json'
SHARED_DRIVE_ID = '0AJKxxxxxxxxxxxxxxx'  # Your Shared Drive ID

def test_shared_drive_access():
    """Test service account can access Shared Drive."""

    creds = Credentials.from_service_account_file(
        CREDENTIALS_PATH,
        scopes=['https://www.googleapis.com/auth/drive']
    )

    service = build('drive', 'v3', credentials=creds)

    # Test 1: List files in Shared Drive
    print("Testing Shared Drive access...")
    results = service.files().list(
        q=f"'{SHARED_DRIVE_ID}' in parents",
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()

    files = results.get('files', [])
    print(f"✅ Success! Found {len(files)} files in Shared Drive")

    for file in files:
        print(f"  - {file['name']} (ID: {file['id']})")

if __name__ == '__main__':
    test_shared_drive_access()
```

Run it:
```bash
python test_shared_drive.py
```

### Test 3: Integration Test

```bash
# Run your full test suite
pytest tests/test_drive_service.py -v

# Or run with coverage
pytest tests/test_drive_service.py -v --cov=src/services/drive_service
```

---

## Troubleshooting

### Error: "File not found: 404"

**Cause:** Missing `supportsAllDrives=True` parameter

**Solution:**
```python
# ❌ Wrong
service.files().create(body=metadata, media_body=media).execute()

# ✅ Correct
service.files().create(
    body=metadata,
    media_body=media,
    supportsAllDrives=True  # Add this!
).execute()
```

### Error: "Insufficient permissions"

**Cause:** Service account not added to Shared Drive or insufficient role

**Solution:**
1. Verify service account email is in members list
2. Check permission level is "Content Manager" or higher
3. Re-add if necessary

### Error: "Storage quota exceeded"

**Cause:** Organization storage quota reached (unlikely)

**Solution:**
1. Contact Google Workspace admin
2. Increase organization storage quota
3. Check pricing at [workspace.google.com/pricing](https://workspace.google.com/pricing.html)

### Error: "Domain policy prevents sharing"

**Cause:** Admin restrictions on external sharing

**Solution:**
1. Go to [admin.google.com](https://admin.google.com)
2. **Apps** → **Google Workspace** → **Drive and Docs**
3. **Sharing settings** → Allow external sharing (if appropriate)

### Files Upload but Don't Appear

**Cause:** Looking in wrong drive (My Drive vs Shared Drive)

**Solution:**
1. Check **Shared drives** section (left sidebar)
2. NOT in "My Drive"
3. Verify you're using correct Shared Drive ID

---

## Production Checklist

Before deploying to production:

- [ ] Shared Drive created with descriptive name
- [ ] Service account added as Content Manager
- [ ] Folder structure created (optional but recommended)
- [ ] `.env` updated with correct `DRIVE_FOLDER_ID`
- [ ] Code updated with `supportsAllDrives=True` in all Drive API calls
- [ ] Manual upload test successful
- [ ] Integration tests passing
- [ ] Monitoring/logging configured for Drive uploads
- [ ] Backup strategy documented (Shared Drives have 30-day trash)
- [ ] Access review scheduled (quarterly recommended)

---

## Security Best Practices

### 1. Least Privilege Access

- ✅ Use "Content Manager" role (not "Manager")
- ✅ One service account per application
- ❌ Don't use "Manager" role unless necessary
- ❌ Don't share service account credentials

### 2. Credential Management

```bash
# Store credentials securely
chmod 600 /path/to/service-account.json

# Never commit to git
echo "*.json" >> .gitignore
echo "credentials/" >> .gitignore

# Use environment variables
export DRIVE_CREDENTIALS_PATH=/secure/path/credentials.json
```

### 3. Audit Logging

Enable audit logs in Admin Console:
1. [admin.google.com](https://admin.google.com) → **Reporting** → **Audit**
2. Enable **Drive audit log**
3. Monitor service account activity

### 4. Access Review

Schedule quarterly reviews:
- Review shared drive members
- Remove unused service accounts
- Verify permission levels
- Check for anomalous uploads

---

## Storage Quotas

### Business Standard
- **2 TB per user** (pooled across organization)
- Shared Drive storage counts against organization pool
- Monitor usage at [admin.google.com](https://admin.google.com) → **Reports** → **Drive**

### Business Plus
- **5 TB per user** (pooled)
- Same monitoring as Business Standard

### Enterprise
- **Unlimited*** (5+ users)
- **1 TB per user** (if fewer than 5 users)

*Subject to fair use policy

---

## API Limits

| Quota | Limit | Notes |
|-------|-------|-------|
| Queries per day | 1,000,000,000 | Shared across project |
| Queries per 100 seconds per user | 1,000 | Per service account |
| Upload file size | 5 TB | Per file |
| Shared Drive size | No limit* | Subject to organization quota |

*Monitor at [console.cloud.google.com](https://console.cloud.google.com) → **APIs & Services** → **Dashboard**

---

## FAQ

### Q: Can I use the same service account for Gmail, Sheets, and Drive?

**A:** Yes! Use one service account with multiple scopes:
```python
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]
```

### Q: Do I need a Shared Drive for each environment (dev/staging/prod)?

**A:** Recommended approach:
```
Shared Drive: Claims Archive
├── production/
├── staging/
└── development/
```

Or create separate Shared Drives:
- `Claims Archive - Production`
- `Claims Archive - Staging`
- `Claims Archive - Development`

### Q: How long are deleted files retained?

**A:** Shared Drive trash retention:
- **30 days** in trash
- After 30 days: permanently deleted
- Admins can recover within 30 days

### Q: Can I automate Shared Drive creation?

**A:** Yes, using Drive API:
```python
drive_metadata = {
    'name': 'Claims Archive',
    'capabilities': {'canManageMembers': True}
}

service.drives().create(
    body=drive_metadata,
    requestId='unique-request-id',
    fields='id, name'
).execute()
```

### Q: What happens if service account is removed?

**A:** Files remain in Shared Drive (owned by organization), but service account loses access. Re-add the service account to restore access.

---

## Additional Resources

- **Official Documentation:**
  - [Shared Drives Admin Guide](https://support.google.com/a/answer/7337469)
  - [Drive API Shared Drives](https://developers.google.com/drive/api/guides/enable-shareddrives)
  - [Manage Shared Drives](https://developers.google.com/drive/api/guides/manage-shareddrives)

- **Google Cloud Console:**
  - [API Dashboard](https://console.cloud.google.com/apis/dashboard)
  - [Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)

- **Admin Console:**
  - [Drive Settings](https://admin.google.com/ac/apps/gmail/settings)
  - [Audit Logs](https://admin.google.com/ac/reporting/audit)

---

## Summary

**Key Points:**
1. ✅ Shared Drives solve service account storage quota issues
2. ✅ Requires Google Workspace Business Standard or higher
3. ✅ Add service account as "Content Manager"
4. ✅ Use `supportsAllDrives=True` in all Drive API calls
5. ✅ Test before production deployment

**Configuration Time:** ~10 minutes
**Code Changes:** Minimal (add one parameter)
**Storage:** Organization pooled quota (2TB+ per user)

**Next Steps:**
1. Complete Prerequisites Check
2. Create Shared Drive
3. Add service account
4. Update code with `supportsAllDrives=True`
5. Test upload
6. Deploy to production

---

*Last Updated: 2024-12-24*
*Version: 1.0*
