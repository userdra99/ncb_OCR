#!/usr/bin/env python3
"""
List all unread emails with their attachment types.
"""
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def get_gmail_service():
    """Get Gmail service with OAuth."""
    with open('/app/secrets/gmail_token.json', 'r') as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data['token'],
        refresh_token=token_data.get('refresh_token'),
        token_uri='https://oauth2.googleapis.com/token',
        client_id=token_data.get('client_id'),
        client_secret=token_data.get('client_secret')
    )

    return build('gmail', 'v1', credentials=creds)


def main():
    service = get_gmail_service()

    # Get unread messages with attachments
    results = service.users().messages().list(
        userId='me',
        q='is:unread has:attachment',
        maxResults=10
    ).execute()

    messages = results.get('messages', [])
    print(f"Found {len(messages)} unread emails with attachments\n")
    print("=" * 80)

    for idx, msg in enumerate(messages, 1):
        # Get full message
        message = service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='full'
        ).execute()

        # Extract headers
        headers = {h['name']: h['value'] for h in message['payload']['headers']}

        print(f"\n[{idx}] ID: {msg['id']}")
        print(f"    From: {headers.get('From', 'N/A')}")
        print(f"    Subject: {headers.get('Subject', 'N/A')}")

        # Find attachments
        attachments = []
        if 'parts' in message['payload']:
            for part in message['payload']['parts']:
                if part.get('filename'):
                    attachments.append({
                        'filename': part['filename'],
                        'mime_type': part.get('mimeType'),
                        'size': part['body'].get('size', 0)
                    })

        if attachments:
            print(f"    Attachments:")
            for att in attachments:
                is_image = "✅ IMAGE" if att['mime_type'].startswith('image/') else "❌"
                size_kb = att['size'] / 1024
                print(f"      {is_image} {att['filename']} ({att['mime_type']}, {size_kb:.1f} KB)")
        else:
            print(f"    No attachments found")

        print("-" * 80)


if __name__ == "__main__":
    main()
