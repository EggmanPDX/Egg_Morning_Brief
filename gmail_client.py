# gmail_client.py
import os
import base64
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from config import GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


def get_gmail_service():
    """Build and return an authenticated Gmail service."""
    creds = None

    if os.path.exists(GOOGLE_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_CREDENTIALS_PATH, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(GOOGLE_TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def get_unread_emails_since(service, hours_back=24):
    """
    Fetch unread emails from the last N hours.
    Returns list of dicts: {id, sender, subject, body, date, thread_id}
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours_back)
    cutoff_str = cutoff.strftime("%Y/%m/%d")
    query = f"is:unread after:{cutoff_str}"

    results = service.users().messages().list(
        userId="me", q=query, maxResults=50
    ).execute()

    messages = results.get("messages", [])
    emails = []

    for msg in messages:
        full_msg = service.users().messages().get(
            userId="me", id=msg["id"], format="full"
        ).execute()

        headers = {h["name"]: h["value"] for h in full_msg["payload"]["headers"]}
        body = _extract_body(full_msg["payload"])

        emails.append({
            "id": msg["id"],
            "thread_id": full_msg["threadId"],
            "sender": headers.get("From", ""),
            "subject": headers.get("Subject", "(no subject)"),
            "date": headers.get("Date", ""),
            "body": body[:3000],  # Cap at 3000 chars for API efficiency
        })

    return emails


def _extract_body(payload):
    """Extract plain text body from Gmail message payload."""
    body = ""

    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    elif "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                    break
            elif part.get("mimeType") == "multipart/alternative":
                body = _extract_body(part)
                if body:
                    break

    return body.strip()


def mark_as_read(service, message_id):
    """Mark a message as read after processing."""
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()


# ── Newsletter senders ──────────────────────────────────────────────────────
# NOTE: Verify these against actual Gmail before trusting. These are best-
# known sender addresses — run `fetch_newsletter` in dry-run mode once and
# check the printed senders to confirm / correct.
NEWSLETTER_SENDERS = {
    "The Rundown": ["hi@therundown.ai", "newsletter@therundown.ai"],
    "The Neuron": ["hello@theneurondaily.com", "hi@theneurondaily.com"],
    "TLDR": ["dan@tldrnewsletter.com", "hello@tldr.tech"],
}


def fetch_newsletter(service, name: str, sender_patterns: list, lookback_hours: int = 24) -> dict | None:
    """
    Fetch the most recent newsletter from any of the given sender patterns
    within the last lookback_hours. Returns a dict with {name, subject, date,
    sender, body} or None if not found.
    """
    cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
    cutoff_epoch = int(cutoff.timestamp())

    for pattern in sender_patterns:
        query = f"from:{pattern} after:{cutoff_epoch}"
        try:
            results = service.users().messages().list(
                userId="me", q=query, maxResults=1
            ).execute()
            messages = results.get("messages", [])
            if not messages:
                continue

            full_msg = service.users().messages().get(
                userId="me", id=messages[0]["id"], format="full"
            ).execute()

            headers = {h["name"]: h["value"] for h in full_msg["payload"]["headers"]}
            body = _extract_body(full_msg["payload"])

            return {
                "name": name,
                "subject": headers.get("Subject", "(no subject)"),
                "date": headers.get("Date", ""),
                "sender": headers.get("From", pattern),
                "body": body[:4000],  # cap for Claude
            }
        except Exception as e:
            print(f"   ⚠️  Newsletter fetch error ({name} / {pattern}): {e}")
            continue

    return None


def fetch_all_newsletters(service, lookback_hours: int = 24) -> dict:
    """
    Fetch the most recent issue of each configured newsletter.
    Returns dict: {newsletter_name: result_dict_or_None}
    """
    results = {}
    for name, patterns in NEWSLETTER_SENDERS.items():
        result = fetch_newsletter(service, name, patterns, lookback_hours)
        results[name] = result
        status = f"✅ found ({result['sender']})" if result else "— not found"
        print(f"   Newsletter {name}: {status}")
    return results
