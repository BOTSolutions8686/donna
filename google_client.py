"""
Google API client for Donna.
Covers: Gmail, Google Calendar, Google Drive.

Auth: OAuth2 Device Authorization Flow (no browser on server needed).
One-time setup: run `python3 /opt/cloud_agent/google_client.py --auth` on the server,
open the printed URL on your phone, approve, done.
"""

import os
import json
import base64
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive.readonly",
]


# ── Credentials ───────────────────────────────────────────────────────────────

def _creds(username: str = None):
    """Build valid Google credentials for a user from user_integrations.
    Falls back to legacy config.py tokens if username not given or not found.
    """
    import json as _json
    from config import CONFIG
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    import database as _db

    gcfg = CONFIG.get("google", {})
    client_id     = gcfg.get("web_client_id") or gcfg.get("client_id", "")
    client_secret = gcfg.get("web_client_secret") or gcfg.get("client_secret", "")

    # Try per-user credentials first
    if username:
        row = _db.get_user_integration(username, "gmail")
        if row:
            data = _json.loads(row["token_json"])
            creds = Credentials(
                token=data.get("access_token"),
                refresh_token=data.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=SCOPES,
            )
            if creds.expired or not creds.valid:
                creds.refresh(Request())
                data["access_token"] = creds.token
                _db.save_user_integration(username, "gmail", _json.dumps(data),
                    email_address=row.get("email_address"), scopes=row.get("scopes"))
            return creds

    # Legacy fallback: use admin tokens from config.py
    if not gcfg.get("refresh_token"):
        raise ValueError("Google not configured — connect via the Donna web UI")
    creds = Credentials(
        token=gcfg.get("access_token"),
        refresh_token=gcfg.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    if creds.expired or not creds.valid:
        creds.refresh(Request())
        _persist_token(creds.token)
    return creds


def _persist_token(new_token):
    """Write refreshed access token back to config.py."""
    config_path = "/opt/cloud_agent/config.py"
    try:
        with open(config_path, "r") as f:
            text = f.read()
        text = re.sub(
            r'("access_token"\s*:\s*")[^"]*(")',
            f'\\g<1>{new_token}\\g<2>',
            text,
        )
        with open(config_path, "w") as f:
            f.write(text)
    except Exception as e:
        log.warning("Could not persist refreshed Google token: %s", e)


def _gmail(username: str = None):
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=_creds(username), cache_discovery=False)


def _calendar(username: str = None):
    from googleapiclient.discovery import build
    return build("calendar", "v3", credentials=_creds(username), cache_discovery=False)


def _drive(username: str = None):
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=_creds(username), cache_discovery=False)


def google_configured(username: str = None):
    """Return True if Google is configured — checks user_integrations first, then config."""
    try:
        if username:
            import database as _db
            if _db.get_user_integration(username, "gmail"):
                return True
        from config import CONFIG
        return bool(CONFIG.get("google", {}).get("refresh_token"))
    except Exception:
        return False


# ── Gmail ─────────────────────────────────────────────────────────────────────

def get_emails(max_results=20, query="", label="INBOX", since_days=1, username=None):
    """Fetch recent emails. Returns list of parsed email dicts."""
    svc = _gmail(username)
    parts = []
    if query:
        parts.append(query)
    if since_days:
        cutoff = (datetime.now() - timedelta(days=since_days)).strftime("%Y/%m/%d")
        parts.append(f"after:{cutoff}")
    q = " ".join(parts)

    result = svc.users().messages().list(
        userId="me",
        labelIds=[label] if label else [],
        q=q,
        maxResults=max_results,
    ).execute()

    emails = []
    for msg_ref in result.get("messages", []):
        try:
            msg = svc.users().messages().get(userId="me", id=msg_ref["id"], format="full").execute()
            emails.append(_parse_message(msg))
        except Exception as e:
            log.warning("Failed to fetch email %s: %s", msg_ref["id"], e)
    return emails


def get_unread_emails(max_results=20, since_days=1):
    """Fetch unread emails only."""
    return get_emails(max_results=max_results, query="is:unread", since_days=since_days)


def _parse_message(msg):
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    from_name, from_addr = parseaddr(headers.get("from", ""))
    labels = msg.get("labelIds", [])
    body = _extract_body(msg.get("payload", {}))
    return {
        "message_id": msg["id"],
        "thread_id": msg.get("threadId", ""),
        "subject": headers.get("subject", "(no subject)"),
        "from_name": from_name or from_addr,
        "from_addr": from_addr,
        "to": headers.get("to", ""),
        "date": headers.get("date", ""),
        "snippet": msg.get("snippet", ""),
        "body_preview": body[:2000] if body else msg.get("snippet", ""),
        "labels": labels,
        "is_unread": "UNREAD" in labels,
        "is_important": "IMPORTANT" in labels,
    }


def _extract_body(payload):
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")
    if mime_type == "text/plain" and body_data:
        try:
            return base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")
        except Exception:
            return ""
    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result
    return ""


def send_reply(thread_id, to, subject, body, cc=None, reply_all=True, username=None):
    """
    Send an email reply in an existing thread.
    reply_all=True (default): fetches original message and CCs all To/CC recipients.
    cc: explicit list of CC addresses (overrides reply_all auto-detection).
    """
    import email.mime.text
    from email.utils import getaddresses
    svc = _gmail(username)

    # Auto-detect CC recipients for reply-all
    cc_addresses = []
    if reply_all and cc is None:
        try:
            # Get the last message in the thread to extract all recipients
            thread = svc.users().threads().get(userId="me", id=thread_id, format="metadata",
                metadataHeaders=["To", "Cc", "From"]).execute()
            messages = thread.get("messages", [])
            if messages:
                last_msg = messages[-1]
                hdrs = {h["name"].lower(): h["value"]
                        for h in last_msg.get("payload", {}).get("headers", [])}
                # Collect To + Cc, excluding the sender (to avoid duplicate)
                raw_recipients = hdrs.get("to", "") + "," + hdrs.get("cc", "")
                all_addrs = [addr for name, addr in getaddresses([raw_recipients])
                             if addr and addr.lower() != to.lower()]
                cc_addresses = list(dict.fromkeys(all_addrs))  # dedupe, preserve order
        except Exception as e:
            log.warning("reply-all CC detection failed: %s", e)
    elif cc:
        cc_addresses = cc

    mime = email.mime.text.MIMEText(body)
    mime["to"] = to
    mime["subject"] = subject if subject.startswith("Re:") else f"Re: {subject}"
    if cc_addresses:
        mime["cc"] = ", ".join(cc_addresses)
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    sent = svc.users().messages().send(
        userId="me", body={"raw": raw, "threadId": thread_id}
    ).execute()
    return sent.get("id"), cc_addresses


def send_new_email(to, subject, body, username=None):
    """Send a new email (not a reply)."""
    import email.mime.text
    svc = _gmail(username)
    mime = email.mime.text.MIMEText(body)
    mime["to"] = to
    mime["subject"] = subject
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    sent = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    return sent.get("id")


def mark_as_read(message_id):
    svc = _gmail()
    svc.users().messages().modify(
        userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
    ).execute()


def get_thread(thread_id, username=None):
    """Fetch all messages in a thread."""
    svc = _gmail(username)
    thread = svc.users().threads().get(userId="me", id=thread_id, format="full").execute()
    return [_parse_message(m) for m in thread.get("messages", [])]


# ── Google Calendar ───────────────────────────────────────────────────────────

def get_upcoming_events(days_ahead=7, max_results=20, username=None):
    """Fetch upcoming calendar events."""
    svc = _calendar(username)
    now = datetime.now(timezone.utc).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat()
    result = svc.events().list(
        calendarId="primary",
        timeMin=now, timeMax=end,
        maxResults=max_results,
        singleEvents=True, orderBy="startTime",
    ).execute()

    events = []
    for e in result.get("items", []):
        start = e.get("start", {}).get("dateTime") or e.get("start", {}).get("date", "")
        end_dt = e.get("end", {}).get("dateTime") or e.get("end", {}).get("date", "")
        attendees = [a.get("email", "") for a in e.get("attendees", []) if not a.get("self")]
        meet_link = e.get("hangoutLink") or ""
        events.append({
            "event_id": e.get("id"),
            "title": e.get("summary", "(no title)"),
            "start": start,
            "end": end_dt,
            "location": e.get("location", ""),
            "description": (e.get("description") or "")[:200],
            "attendees": attendees,
            "meet_link": meet_link,
            "organizer": e.get("organizer", {}).get("email", ""),
        })
    return events


def get_today_events():
    """Fetch today's events only."""
    svc = _calendar()
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
    result = svc.events().list(
        calendarId="primary",
        timeMin=today_start, timeMax=today_end,
        singleEvents=True, orderBy="startTime",
    ).execute()
    return [
        {
            "title": e.get("summary", "(no title)"),
            "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date", ""),
            "end": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date", ""),
            "meet_link": e.get("hangoutLink", ""),
            "attendees": [a.get("email", "") for a in e.get("attendees", []) if not a.get("self")],
        }
        for e in result.get("items", [])
    ]


def create_event(title, start_dt, end_dt, description="", attendees=None, location="", username=None):
    """Create a calendar event. start_dt/end_dt are ISO strings with timezone."""
    svc = _calendar(username)
    body = {
        "summary": title,
        "description": description,
        "location": location,
        "start": {"dateTime": start_dt, "timeZone": "Asia/Riyadh"},
        "end": {"dateTime": end_dt, "timeZone": "Asia/Riyadh"},
    }
    if attendees:
        body["attendees"] = [{"email": a} for a in attendees]
    event = svc.events().insert(calendarId="primary", body=body, sendUpdates="all").execute()
    return {
        "event_id": event.get("id"),
        "title": event.get("summary"),
        "start": event.get("start", {}).get("dateTime"),
        "link": event.get("htmlLink", ""),
    }


def create_event_with_meet(title, start_dt, end_dt, description="", attendees=None, username=None):
    """Create a calendar event with a Google Meet link. Returns meet_link in result."""
    import uuid
    svc = _calendar(username)
    body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_dt, "timeZone": "Asia/Riyadh"},
        "end": {"dateTime": end_dt, "timeZone": "Asia/Riyadh"},
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    if attendees:
        body["attendees"] = [{"email": a} for a in attendees]
    event = svc.events().insert(
        calendarId="primary",
        body=body,
        conferenceDataVersion=1,
        sendUpdates="all",
    ).execute()
    meet_link = event.get("hangoutLink", "")
    if not meet_link:
        # Fallback: check conferenceData
        conf = event.get("conferenceData", {})
        for ep in conf.get("entryPoints", []):
            if ep.get("entryPointType") == "video":
                meet_link = ep.get("uri", "")
                break
    return {
        "event_id": event.get("id"),
        "title": event.get("summary"),
        "start": event.get("start", {}).get("dateTime"),
        "link": event.get("htmlLink", ""),
        "meet_link": meet_link,
    }


# ── Google Drive ──────────────────────────────────────────────────────────────

def search_drive(query, max_results=10, username=None):
    """Search Drive files by name."""
    svc = _drive(username)
    result = svc.files().list(
        q=f"name contains '{query}' and trashed=false",
        pageSize=max_results,
        fields="files(id,name,mimeType,modifiedTime,size,webViewLink)",
        orderBy="modifiedTime desc",
    ).execute()
    return [
        {
            "file_id": f.get("id"),
            "name": f.get("name"),
            "type": f.get("mimeType", "").split(".")[-1],
            "modified": f.get("modifiedTime", "")[:10],
            "web_link": f.get("webViewLink", ""),
        }
        for f in result.get("files", [])
    ]


def get_recent_drive_files(max_results=10, username=None):
    """Get recently modified Drive files."""
    svc = _drive(username)
    result = svc.files().list(
        pageSize=max_results,
        fields="files(id,name,mimeType,modifiedTime,webViewLink)",
        orderBy="modifiedTime desc",
        q="trashed=false",
    ).execute()
    return [
        {
            "file_id": f.get("id"),
            "name": f.get("name"),
            "modified": f.get("modifiedTime", "")[:16].replace("T", " "),
            "web_link": f.get("webViewLink", ""),
        }
        for f in result.get("files", [])
    ]


def read_drive_file(file_id):
    """Read text content of a Drive file (Docs→text, Sheets→CSV)."""
    svc = _drive()
    meta = svc.files().get(fileId=file_id, fields="name,mimeType").execute()
    mime = meta.get("mimeType", "")
    export_map = {
        "application/vnd.google-apps.document": "text/plain",
        "application/vnd.google-apps.spreadsheet": "text/csv",
        "application/vnd.google-apps.presentation": "text/plain",
    }
    if mime in export_map:
        content = svc.files().export(fileId=file_id, mimeType=export_map[mime]).execute()
    else:
        content = svc.files().get_media(fileId=file_id).execute()
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    return str(content)


# ── Device Authorization Flow (one-time setup) ───────────────────────────────

def run_device_auth(client_id, client_secret):
    """
    OAuth2 Device Authorization Flow.
    Prints a URL and code. User visits URL on any device and approves.
    No browser on server needed. Prints config snippet when done.
    """
    import requests as req
    import time

    # Step 1: Request device code
    r = req.post("https://oauth2.googleapis.com/device/code", data={
        "client_id": client_id,
        "scope": " ".join(SCOPES),
    })
    r.raise_for_status()
    data = r.json()

    device_code = data["device_code"]
    user_code = data["user_code"]
    verification_url = data["verification_url"]
    interval = data.get("interval", 5)
    expires_in = data.get("expires_in", 1800)

    print("\n" + "="*60)
    print("DONNA GOOGLE AUTH — Device Flow")
    print("="*60)
    print(f"\n1. Open this URL on your phone or laptop:")
    print(f"\n   {verification_url}\n")
    print(f"2. Enter this code when prompted:\n")
    print(f"   {user_code}\n")
    print("="*60)
    print("Waiting for you to approve... (will check every %ds)" % interval)

    # Step 2: Poll for token
    start = time.time()
    while time.time() - start < expires_in:
        time.sleep(interval)
        token_r = req.post("https://oauth2.googleapis.com/token", data={
            "client_id": client_id,
            "client_secret": client_secret,
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        })
        token_data = token_r.json()

        if "access_token" in token_data:
            print("\n✅ Approved! Token received.")
            _print_config_snippet(client_id, client_secret, token_data)
            return token_data

        error = token_data.get("error", "")
        if error == "authorization_pending":
            print(".", end="", flush=True)
            continue
        elif error == "slow_down":
            interval += 5
            continue
        else:
            print(f"\n❌ Auth failed: {token_data}")
            return None

    print("\n❌ Timed out. Run again.")
    return None


def _print_config_snippet(client_id, client_secret, token_data):
    refresh_token = token_data.get("refresh_token", "")
    access_token = token_data.get("access_token", "")
    print("\n" + "="*60)
    print("Add this to CONFIG in /opt/cloud_agent/config.py:")
    print("="*60)
    snippet = f'''
    "google": {{
        "client_id": "{client_id}",
        "client_secret": "{client_secret}",
        "refresh_token": "{refresh_token}",
        "access_token": "{access_token}",
        "scopes": {json.dumps(SCOPES, indent=8)},
    }},'''
    print(snippet)
    print("="*60)
    print("\nThen restart: systemctl restart cloud_agent")


if __name__ == "__main__":
    import sys
    if "--auth" in sys.argv:
        print("Donna — Google Device Authorization Setup")
        print("-" * 40)
        client_id = input("Paste your Google OAuth Client ID: ").strip()
        client_secret = input("Paste your Google OAuth Client Secret: ").strip()
        run_device_auth(client_id, client_secret)
    else:
        print("Usage: python3 google_client.py --auth")
