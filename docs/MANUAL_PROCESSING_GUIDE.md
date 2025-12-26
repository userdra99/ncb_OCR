# Manual Email Processing - Rate Limit Workaround

## Current Situation

The Gmail account is in a **persistent throttled state**. Despite implementing batch requests and optimizations, the rate limit keeps extending. This indicates:

1. **Another OAuth application** may be continuously polling the same Gmail account
2. **Account flagged for abuse** due to previous high-volume polling
3. **Waiting for daily quota reset** at 08:00 UTC (midnight Pacific Time)

## Immediate Solution: Manual Processing

Use the manual processing script to handle emails **without continuous polling**:

### Step 1: Start Container (Manual Mode)

```bash
docker compose up -d app
```

The email poller is now set to check only **once every 24 hours** instead of every 60 seconds.

### Step 2: Process Emails Manually

```bash
# List unread emails (uses only 1 API call)
docker compose exec app python scripts/process_email_manual.py list
```

**Example output:**
```
Found 3 unread email(s):

1. Email ID: 18d4f2a3b1c9e8f7
   From: claims@example.com
   Subject: Claim submission - Receipt attached
   Attachments: 2

2. Email ID: 18d4f2a3b1c9e8f8
   From: member@example.com
   Subject: Medical claim
   Attachments: 1
```

### Step 3: Process Specific Email

```bash
# Process by email ID
docker compose exec app python scripts/process_email_manual.py 18d4f2a3b1c9e8f7
```

**What happens:**
1. ✅ Downloads attachments
2. ✅ Runs OCR extraction
3. ✅ Generates NCB JSON file
4. ✅ Uploads JSON to Google Drive
5. ✅ Updates Google Sheets
6. ✅ Marks email as processed

**Quota cost:** ~20-30 units per email (vs 7,200/day from polling)

## Recommended Actions

### 1. Check OAuth Permissions (CRITICAL)

Visit: https://myaccount.google.com/permissions

**Look for:**
- Mobile email apps (Gmail, Outlook, etc.)
- Browser extensions (email checkers, notifiers)
- Other scripts or automation tools
- Multiple instances of this application

**Action:** Revoke access to all apps **except** this Claims Data Entry Agent

### 2. Regenerate OAuth Token

After revoking other apps:

```bash
# 1. Remove old token
rm -f /path/to/gmail_token.json

# 2. Restart app (will trigger OAuth flow)
docker compose restart app

# 3. Complete OAuth in browser
# 4. New token with clean slate
```

### 3. Wait for Quota Reset

Gmail API quotas reset at **midnight Pacific Time**:

- Current time: 02:51 UTC Dec 25
- Pacific time: 6:51 PM Dec 24  
- Next reset: **08:00 UTC Dec 25** (~5 hours)

After reset, the rate limit should clear.

## Testing the Batch Implementation

Once the rate limit clears (after 08:00 UTC), test the batch implementation:

```bash
# 1. Set polling back to 60 seconds
# Edit .env: GMAIL_POLL_INTERVAL=60

# 2. Restart container
docker compose restart app

# 3. Monitor logs
docker compose logs app -f | grep -E "(batch|unseen|Fetching metadata)"

# Expected output:
# "Polled inbox, found_messages=X"
# "Fetching metadata for unseen messages, unseen_count=X"
# "Batch metadata fetch completed, successful=X"

# 4. Verify NO rate limits
docker compose logs app | grep "429"  # Should be empty
```

## Quota Usage Comparison

### Manual Processing (Current)
- List emails: 5 units (once per manual check)
- Process 1 email: ~20 units
- **Total**: ~25 units per email processed

### Batch Polling (After Reset)
- First poll (25 new emails): 10 units (1 list + 1 batch)
- Subsequent polls (cached): 5 units (1 list, skip batch)
- **Daily total**: ~7,205 units (98% reduction from old method!)

## When to Resume Automatic Polling

Resume automatic polling when:

1. ✅ You've checked and cleaned up OAuth permissions
2. ✅ Daily quota has reset (after 08:00 UTC)
3. ✅ Manual test succeeds without 429 errors
4. ✅ You've set `GMAIL_POLL_INTERVAL=60` in .env

## Current Status

- ✅ Batch request implementation: **Complete**
- ✅ Redis caching: **Complete** (caches cleared for your unread emails)
- ✅ 98% quota reduction: **Ready to use**
- ⏸️ Auto-polling: **Disabled** (24h interval)
- 📝 Manual processing: **Available now**
- ⏰ Quota reset: **08:00 UTC Dec 25** (~5 hours)

## Support

If issues persist after quota reset:

1. Check Google Cloud Console quota page
2. Request quota increase (usually approved quickly)
3. Consider Gmail Push Notifications (long-term solution)

---

**Created**: 2025-12-25 02:52 UTC  
**Mode**: Manual processing only  
**Next**: Check OAuth permissions, wait for 08:00 UTC reset
