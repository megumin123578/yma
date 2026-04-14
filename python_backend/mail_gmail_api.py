import base64
import email
import json
import os
import re
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from typing import Optional

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from python_backend.api.auth.models import MailAccount
from python_backend.module_mail import delete_mail_account as delete_mail_account_rows
from python_backend.module_mail import save_mail_ingest
from python_backend.token_store import (
    delete_token_credentials,
    load_token_credentials,
    rename_token_credentials,
    store_token_credentials,
)

MAIL_AGENT_VERSION = "mail-backend-v1"
MAIL_GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
MAIL_OAUTH_TTL_MINUTES = 15


class GmailHistoryExpired(RuntimeError):
    pass


def normalize_mail_account_email(value: str) -> str:
    return str(value or "").strip().lower()


def normalize_mail_label_ids(values) -> list[str]:
    if values is None:
        return ["INBOX"]
    if isinstance(values, str):
        try:
            parsed = json.loads(values)
        except Exception:
            parsed = [item.strip() for item in values.split(",") if item.strip()]
        values = parsed
    if isinstance(values, list):
        normalized = [str(item).strip() for item in values if str(item or "").strip()]
        return normalized or ["INBOX"]
    return ["INBOX"]


def serialize_mail_label_ids(values) -> str:
    return json.dumps(normalize_mail_label_ids(values), ensure_ascii=True)


def deserialize_mail_label_ids(raw_value: str) -> list[str]:
    return normalize_mail_label_ids(raw_value)


def mail_token_name_for_email(email: str) -> str:
    normalized = normalize_mail_account_email(email)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", normalized).strip("._-")
    return f"mail__{safe or 'gmail_account'}"


def mail_oauth_success_html() -> str:
    return """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Gmail Connected</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        font-family: Arial, sans-serif;
        background: #f8fafc;
        color: #0f172a;
      }
      .card {
        max-width: 440px;
        padding: 24px;
        border-radius: 16px;
        background: #ffffff;
        box-shadow: 0 16px 32px rgba(15, 23, 42, 0.12);
        border: 1px solid rgba(148, 163, 184, 0.28);
      }
      h1 { margin: 0 0 12px; font-size: 22px; }
      p { margin: 0; line-height: 1.6; color: #475569; }
    </style>
  </head>
  <body>
    <div class="card">
      <h1>Gmail connected</h1>
      <p>You can close this window and return to the Email Manager.</p>
    </div>
  </body>
</html>
""".strip()


def build_mail_oauth_flow(redirect_url: str) -> Flow:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET")

    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_url],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=MAIL_GMAIL_SCOPES)
    flow.redirect_uri = redirect_url
    return flow


def _build_gmail_service(creds):
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def fetch_gmail_profile(creds) -> dict[str, str]:
    service = _build_gmail_service(creds)
    profile = service.users().getProfile(userId="me").execute()
    return {
        "email": normalize_mail_account_email(profile.get("emailAddress") or ""),
        "history_id": str(profile.get("historyId") or "").strip(),
    }


def _decode_header_value(value: Optional[str]) -> str:
    if not value:
        return ""
    parts = []
    for chunk, charset in decode_header(value):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(str(chunk))
    return "".join(parts).strip()


def _extract_plain_text(message: email.message.Message, limit: int = 280) -> str:
    fragments = []
    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition") or "").lower()
            if content_type != "text/plain" or "attachment" in disposition:
                continue
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            fragments.append(payload.decode(charset, errors="replace"))
            if fragments:
                break
    else:
        payload = message.get_payload(decode=True) or b""
        charset = message.get_content_charset() or "utf-8"
        fragments.append(payload.decode(charset, errors="replace"))

    text = " ".join(fragment.strip() for fragment in fragments if fragment.strip())
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _extract_plain_text_full(message: email.message.Message) -> str:
    fragments = []
    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition") or "").lower()
            if content_type != "text/plain" or "attachment" in disposition:
                continue
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            fragments.append(payload.decode(charset, errors="replace"))
    else:
        if message.get_content_type() == "text/plain":
            payload = message.get_payload(decode=True) or b""
            charset = message.get_content_charset() or "utf-8"
            fragments.append(payload.decode(charset, errors="replace"))

    return "\n\n".join(fragment.strip() for fragment in fragments if fragment.strip()).strip()


def _extract_html_text(message: email.message.Message) -> str:
    fragments = []
    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition") or "").lower()
            if content_type != "text/html" or "attachment" in disposition:
                continue
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            fragments.append(payload.decode(charset, errors="replace"))
    else:
        if message.get_content_type() == "text/html":
            payload = message.get_payload(decode=True) or b""
            charset = message.get_content_charset() or "utf-8"
            fragments.append(payload.decode(charset, errors="replace"))

    return "\n".join(fragment for fragment in fragments if fragment).strip()


def _parse_received_at(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _parse_internal_date(value) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromtimestamp(int(raw) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None
    return dt.isoformat()


def _decode_gmail_raw(raw_value: str) -> bytes:
    if not raw_value:
        return b""
    padded = raw_value + ("=" * (-len(raw_value) % 4))
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _fetch_gmail_message(service, message_id: str) -> dict:
    response = service.users().messages().get(userId="me", id=message_id, format="raw").execute()
    raw_message = _decode_gmail_raw(str(response.get("raw") or ""))
    parsed = email.message_from_bytes(raw_message) if raw_message else email.message.Message()
    from_name, from_email = parseaddr(_decode_header_value(parsed.get("From")))
    _, to_email = parseaddr(_decode_header_value(parsed.get("To")))
    label_ids = [str(item).strip() for item in response.get("labelIds", []) if str(item).strip()]
    received_at = _parse_internal_date(response.get("internalDate")) or _parse_received_at(parsed.get("Date"))

    return {
        "provider_message_id": str(response.get("id") or message_id).strip() or message_id,
        "uid": None,
        "thread_id": str(response.get("threadId") or "").strip() or None,
        "subject": _decode_header_value(parsed.get("Subject")),
        "from_email": from_email or None,
        "from_name": from_name or None,
        "to_email": to_email or None,
        "received_at": received_at,
        "seen": "UNREAD" not in label_ids,
        "status": "received",
        "matched_rule": None,
        "snippet": str(response.get("snippet") or "").strip() or _extract_plain_text(parsed),
        "payload": {
            "gmail_label_ids": label_ids,
            "size": int(response.get("sizeEstimate") or len(raw_message) or 0),
            "text_body": _extract_plain_text_full(parsed),
            "html_body": _extract_html_text(parsed),
            "gmail_history_id": str(response.get("historyId") or "").strip() or None,
            "gmail_message_header_id": str(parsed.get("Message-ID") or "").strip() or None,
        },
    }


def _message_for_mailbox(message: dict, mailbox: str) -> dict:
    payload = dict(message.get("payload") or {})
    payload["mailbox"] = mailbox
    next_message = dict(message)
    next_message["payload"] = payload
    return next_message


def _resolve_label_specs(service, account: MailAccount) -> list[dict[str, str]]:
    response = service.users().labels().list(userId="me").execute()
    labels = response.get("labels", []) or []
    by_id = {}
    by_name = {}
    for item in labels:
        label_id = str(item.get("id") or "").strip()
        label_name = str(item.get("name") or "").strip()
        if label_id:
            by_id[label_id] = item
        if label_name:
            by_name[label_name.lower()] = item

    resolved = []
    seen_mailboxes = set()
    for raw_value in deserialize_mail_label_ids(account.label_ids_json):
        item = by_id.get(raw_value) or by_name.get(raw_value.lower())
        if not item:
            raise RuntimeError(f"Unknown Gmail label for {account.account_email}: {raw_value}")
        mailbox = str(item.get("name") or raw_value).strip() or raw_value
        label_id = str(item.get("id") or raw_value).strip() or raw_value
        if mailbox.lower() in seen_mailboxes:
            continue
        seen_mailboxes.add(mailbox.lower())
        resolved.append({"mailbox": mailbox, "label_id": label_id})

    return resolved or [{"mailbox": "INBOX", "label_id": "INBOX"}]


def _list_recent_message_ids(service, label_id: str, fetch_limit: int) -> list[str]:
    response = service.users().messages().list(
        userId="me",
        labelIds=[label_id],
        maxResults=max(1, min(fetch_limit, 500)),
    ).execute()
    return [str(item.get("id") or "").strip() for item in response.get("messages", []) if item.get("id")]


def _initial_sync_account(service, label_specs: list[dict[str, str]], fetch_limit: int) -> tuple[dict[str, list[dict]], str]:
    message_cache: dict[str, dict] = {}
    messages_by_mailbox = {spec["mailbox"]: [] for spec in label_specs}

    for spec in label_specs:
        message_ids = _list_recent_message_ids(service, spec["label_id"], fetch_limit)
        for message_id in reversed(message_ids):
            if message_id not in message_cache:
                try:
                    message_cache[message_id] = _fetch_gmail_message(service, message_id)
                except Exception as exc:
                    if _gmail_http_status_code(exc) == 404:
                        continue
                    raise
            message = message_cache[message_id]
            label_ids = set(message.get("payload", {}).get("gmail_label_ids", []))
            if spec["label_id"] in label_ids:
                messages_by_mailbox[spec["mailbox"]].append(_message_for_mailbox(message, spec["mailbox"]))

    profile = service.users().getProfile(userId="me").execute()
    return messages_by_mailbox, str(profile.get("historyId") or "").strip()


def _gmail_http_status_code(exc: Exception) -> Optional[int]:
    if isinstance(exc, HttpError):
        try:
            return int(getattr(exc.resp, "status", 0) or 0)
        except Exception:
            return None
    return None


def _list_history_message_ids(service, start_history_id: str) -> tuple[list[str], str]:
    message_ids = []
    next_history_id = str(start_history_id or "").strip()
    page_token = None

    while True:
        try:
            response = service.users().history().list(
                userId="me",
                startHistoryId=start_history_id,
                historyTypes=["messageAdded"],
                pageToken=page_token,
                maxResults=500,
            ).execute()
        except Exception as exc:
            if _gmail_http_status_code(exc) == 404:
                raise GmailHistoryExpired(str(exc)) from exc
            raise

        response_history_id = str(response.get("historyId") or "").strip()
        if response_history_id:
            next_history_id = response_history_id

        for history_item in response.get("history", []) or []:
            history_item_id = str(history_item.get("id") or "").strip()
            if history_item_id:
                next_history_id = history_item_id
            for item in history_item.get("messagesAdded", []) or []:
                message = item.get("message") or {}
                message_id = str(message.get("id") or "").strip()
                if message_id:
                    message_ids.append(message_id)

        page_token = str(response.get("nextPageToken") or "").strip()
        if not page_token:
            break

    return list(dict.fromkeys(message_ids)), next_history_id


def _sync_account_from_history(service, label_specs: list[dict[str, str]], start_history_id: str) -> tuple[dict[str, list[dict]], str]:
    message_ids, next_history_id = _list_history_message_ids(service, start_history_id)
    messages_by_mailbox = {spec["mailbox"]: [] for spec in label_specs}
    if not message_ids:
        profile = service.users().getProfile(userId="me").execute()
        return messages_by_mailbox, str(profile.get("historyId") or "").strip() or next_history_id or start_history_id

    label_map = {spec["label_id"]: spec["mailbox"] for spec in label_specs}
    message_cache = {}
    for message_id in message_ids:
        if message_id not in message_cache:
            try:
                message_cache[message_id] = _fetch_gmail_message(service, message_id)
            except Exception as exc:
                if _gmail_http_status_code(exc) == 404:
                    continue
                raise
        message = message_cache[message_id]
        label_ids = set(message.get("payload", {}).get("gmail_label_ids", []))
        for label_id, mailbox in label_map.items():
            if label_id in label_ids:
                messages_by_mailbox[mailbox].append(_message_for_mailbox(message, mailbox))

    if not next_history_id:
        profile = service.users().getProfile(userId="me").execute()
        next_history_id = str(profile.get("historyId") or "").strip() or start_history_id
    return messages_by_mailbox, next_history_id


def sync_mail_account(db: Session, account: MailAccount, fetch_limit: int = 50) -> dict[str, object]:
    now = datetime.utcnow()
    label_ids = deserialize_mail_label_ids(account.label_ids_json)
    try:
        creds = load_token_credentials(account.token_name)
        service = _build_gmail_service(creds)
        label_specs = _resolve_label_specs(service, account)

        if not account.history_id:
            messages_by_mailbox, next_history_id = _initial_sync_account(service, label_specs, fetch_limit)
        else:
            try:
                messages_by_mailbox, next_history_id = _sync_account_from_history(
                    service,
                    label_specs,
                    account.history_id,
                )
            except GmailHistoryExpired:
                messages_by_mailbox, next_history_id = _initial_sync_account(service, label_specs, fetch_limit)

        total_messages = 0
        for spec in label_specs:
            mailbox = spec["mailbox"]
            messages = messages_by_mailbox.get(mailbox, [])
            total_messages += len(messages)
            save_mail_ingest(
                {
                    "account_email": account.account_email,
                    "provider": account.provider or "gmail_api",
                    "mailbox": mailbox,
                    "agent_version": MAIL_AGENT_VERSION,
                    "run_started_at": now.isoformat(),
                    "run_finished_at": datetime.utcnow().isoformat(),
                    "status": "ok",
                    "cursor": str(next_history_id or account.history_id or ""),
                    "messages": messages,
                    "payload": {
                        "account_id": account.id,
                        "label_ids": label_ids,
                    },
                }
            )

        account.history_id = str(next_history_id or account.history_id or "")
        account.last_sync_status = "ok"
        account.last_error_message = None
        account.last_synced_at = datetime.utcnow()
        account.updated_at = datetime.utcnow()
        db.add(account)
        db.commit()
        db.refresh(account)
        return {
            "ok": True,
            "account_id": account.id,
            "account_email": account.account_email,
            "message_count": total_messages,
            "history_id": account.history_id,
        }
    except Exception as exc:
        account.last_sync_status = "error"
        account.last_error_message = str(exc)
        account.last_synced_at = datetime.utcnow()
        account.updated_at = datetime.utcnow()
        db.add(account)
        db.commit()
        for mailbox in label_ids or ["INBOX"]:
            try:
                save_mail_ingest(
                    {
                        "account_email": account.account_email,
                        "provider": account.provider or "gmail_api",
                        "mailbox": mailbox,
                        "agent_version": MAIL_AGENT_VERSION,
                        "run_started_at": now.isoformat(),
                        "run_finished_at": datetime.utcnow().isoformat(),
                        "status": "error",
                        "error_message": str(exc),
                        "cursor": str(account.history_id or ""),
                        "messages": [],
                        "payload": {
                            "account_id": account.id,
                            "label_ids": label_ids,
                        },
                    }
                )
            except Exception:
                pass
        raise


def sync_all_mail_accounts(db: Session, *, user_id: Optional[int] = None, fetch_limit: int = 50) -> dict[str, object]:
    query = db.query(MailAccount).filter(MailAccount.enabled.is_(True))
    if user_id is not None:
        query = query.filter(MailAccount.user_id == user_id)
    rows = query.order_by(MailAccount.account_email.asc()).all()

    items = []
    for row in rows:
        try:
            items.append(sync_mail_account(db, row, fetch_limit=fetch_limit))
        except Exception as exc:
            items.append(
                {
                    "ok": False,
                    "account_id": row.id,
                    "account_email": row.account_email,
                    "error": str(exc),
                }
            )
    return {"items": items, "count": len(items)}


def upsert_mail_account(
    db: Session,
    *,
    user_id: int,
    account_email: str,
    creds,
    label_ids: list[str],
) -> MailAccount:
    normalized_email = normalize_mail_account_email(account_email)
    token_name = mail_token_name_for_email(normalized_email)
    store_token_credentials(token_name, creds)

    row = (
        db.query(MailAccount)
        .filter(
            MailAccount.user_id == user_id,
            MailAccount.account_email == normalized_email,
        )
        .first()
    )
    if row:
        previous_token_name = row.token_name
        row.provider = "gmail_api"
        row.token_name = token_name
        row.label_ids_json = serialize_mail_label_ids(label_ids)
        row.enabled = True
        row.updated_at = datetime.utcnow()
        if previous_token_name and previous_token_name != token_name:
            rename_token_credentials(previous_token_name, token_name)
    else:
        row = MailAccount(
            user_id=user_id,
            account_email=normalized_email,
            provider="gmail_api",
            token_name=token_name,
            label_ids_json=serialize_mail_label_ids(label_ids),
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(row)

    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_mail_account_integration(db: Session, account: MailAccount) -> None:
    delete_token_credentials(account.token_name)
    delete_mail_account_rows(account.account_email)
    db.delete(account)
    db.commit()
