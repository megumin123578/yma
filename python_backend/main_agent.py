import email
import imaplib
import json
import os
import re
import socket
import time
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime, parseaddr
from pathlib import Path
from typing import Optional

import requests


AGENT_VERSION = "mail-agent-v2"

AGENT_CONFIG_JSON = r"""
{
  "MAIL_INGEST_URL": "https://api.tuanfmcaa.site/api/mail/ingest",
  "MAIL_INGEST_TOKEN": "fmc-2026",
  "MAIL_AGENT_VPS_ID": "vps-01",
  "MAIL_PROVIDER": "imap",
  "MAIL_IMAP_HOST": "imap.gmail.com",
  "MAIL_IMAP_PORT": 993,
  "MAIL_IMAP_SSL": true,
  "MAIL_IMAP_USERNAME": "user@example.com",
  "MAIL_IMAP_PASSWORD": "app-password",
  "MAIL_IMAP_MAILBOXES": [
    "INBOX"
  ],
  "MAIL_AGENT_FETCH_LIMIT": 50,
  "MAIL_IMAP_TIMEOUT": 30,
  "MAIL_INGEST_TIMEOUT": 30,
  "MAIL_AGENT_STATE_FILE": "mail_agent_state.json",
  "MAIL_AGENT_INTERVAL_SECONDS": 3600
}
"""


def _normalize_key(key: str) -> str:
    return (
        str(key or "")
        .strip()
        .replace("-", "_")
        .replace(" ", "_")
        .upper()
    )


def _normalize_value(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        items = [str(item).strip() for item in value if item is not None and str(item).strip() != ""]
        return ",".join(items) if items else None
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    normalized = str(value).strip()
    return normalized or None


def _iter_json_env_items(prefix: str, value):
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            child_name = _normalize_key(child_key)
            if not child_name:
                continue
            merged = f"{prefix}_{child_name}" if prefix else child_name
            yield from _iter_json_env_items(merged, child_value)
        return

    yield prefix, value


def load_embedded_config() -> None:
    try:
        payload = json.loads(AGENT_CONFIG_JSON)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid AGENT_CONFIG_JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("AGENT_CONFIG_JSON must contain a JSON object.")

    for key, value in payload.items():
        for env_key, env_value in _iter_json_env_items("", {key: value}):
            normalized = _normalize_value(env_value)
            if normalized is None:
                continue
            os.environ.setdefault(env_key, normalized)


def _is_placeholder(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return True
    return normalized in {
        "replace-me",
        "user@example.com",
        "app-password",
        "imap.yourmail.com",
        "https://your-domain/api/mail/ingest",
        "vps-01",
    }


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if _is_placeholder(value):
        raise RuntimeError(f"Missing or placeholder configuration value: {name}")
    return value


def _get_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return int(raw)


def _log(message: str) -> None:
    print(f"[{datetime.utcnow().isoformat()}] {message}", flush=True)


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


def _state_file_path() -> Path:
    raw = os.getenv("MAIL_AGENT_STATE_FILE", "").strip()
    if raw:
        path = Path(raw).expanduser()
        if path.is_absolute():
            return path
        return Path(__file__).resolve().parent / path
    return Path(__file__).resolve().parent / "mail_agent_state.json"


def load_state() -> dict:
    path = _state_file_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict) -> None:
    path = _state_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")


def connect_imap():
    host = _require_env("MAIL_IMAP_HOST")
    port = _get_int_env("MAIL_IMAP_PORT", 993)
    username = _require_env("MAIL_IMAP_USERNAME")
    password = os.getenv("MAIL_IMAP_PASSWORD", "").strip() or _require_env("MAIL_IMAP_APP_PASSWORD")
    use_ssl = _get_bool_env("MAIL_IMAP_SSL", True)
    timeout = _get_int_env("MAIL_IMAP_TIMEOUT", 30)

    socket.setdefaulttimeout(timeout)
    client = imaplib.IMAP4_SSL(host, port) if use_ssl else imaplib.IMAP4(host, port)
    client.login(username, password)
    return client


def list_mailboxes() -> list[str]:
    raw = os.getenv("MAIL_IMAP_MAILBOXES", "").strip()
    if not raw:
        return ["INBOX"]
    return [item.strip() for item in raw.split(",") if item.strip()]


def _extract_flags(fetch_response) -> list[str]:
    metadata_bytes = []
    for part in fetch_response:
        if isinstance(part, tuple) and isinstance(part[0], bytes):
            metadata_bytes.append(part[0])
    metadata = b" ".join(metadata_bytes)
    match = re.search(rb"FLAGS \((.*?)\)", metadata)
    if not match:
        return []
    raw_flags = match.group(1).decode("utf-8", errors="replace")
    return [item.strip() for item in raw_flags.split() if item.strip()]


def _extract_message_bytes(fetch_response) -> bytes:
    for part in fetch_response:
        if isinstance(part, tuple) and isinstance(part[1], (bytes, bytearray)):
            return bytes(part[1])
    return b""


def fetch_mailbox_messages(
    client,
    mailbox: str,
    last_uid: int,
    fetch_limit: int,
) -> tuple[list[dict], int]:
    status, _ = client.select(mailbox, readonly=True)
    if status != "OK":
        raise RuntimeError(f"Cannot select mailbox {mailbox}")

    status, data = client.uid("search", None, "ALL")
    if status != "OK":
        raise RuntimeError(f"Cannot search mailbox {mailbox}")

    all_uids = [item for item in (data[0] or b"").split() if item]
    if not all_uids:
        return [], last_uid

    if last_uid > 0:
        candidate_uids = [item for item in all_uids if int(item) > last_uid]
    else:
        candidate_uids = all_uids[-fetch_limit:]

    if fetch_limit > 0 and len(candidate_uids) > fetch_limit:
        candidate_uids = candidate_uids[-fetch_limit:]

    messages = []
    new_last_uid = last_uid
    for uid_bytes in candidate_uids:
        uid_text = uid_bytes.decode("utf-8", errors="replace")
        status, fetch_response = client.uid("fetch", uid_bytes, "(BODY.PEEK[] FLAGS)")
        if status != "OK":
            continue

        raw_message = _extract_message_bytes(fetch_response)
        if not raw_message:
            continue

        parsed = email.message_from_bytes(raw_message)
        from_name, from_email = parseaddr(_decode_header_value(parsed.get("From")))
        _, to_email = parseaddr(_decode_header_value(parsed.get("To")))
        flags = _extract_flags(fetch_response)
        message_id = str(parsed.get("Message-ID") or "").strip()

        messages.append(
            {
                "provider_message_id": message_id or None,
                "uid": int(uid_text),
                "thread_id": str(parsed.get("Thread-Index") or "").strip() or None,
                "subject": _decode_header_value(parsed.get("Subject")),
                "from_email": from_email or None,
                "from_name": from_name or None,
                "to_email": to_email or None,
                "received_at": _parse_received_at(parsed.get("Date")),
                "seen": "\\Seen" in flags,
                "status": "received",
                "matched_rule": None,
                "snippet": _extract_plain_text(parsed),
                "payload": {
                    "flags": flags,
                    "mailbox": mailbox,
                    "size": len(raw_message),
                    "text_body": _extract_plain_text_full(parsed),
                    "html_body": _extract_html_text(parsed),
                },
            }
        )
        new_last_uid = max(new_last_uid, int(uid_text))

    return messages, new_last_uid


def post_ingest(payload: dict) -> None:
    ingest_url = _require_env("MAIL_INGEST_URL")
    ingest_token = _require_env("MAIL_INGEST_TOKEN")
    timeout = _get_int_env("MAIL_INGEST_TIMEOUT", 30)

    response = requests.post(
        ingest_url,
        headers={
            "Content-Type": "application/json",
            "X-Mail-Ingest-Token": ingest_token,
        },
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()


def run_once() -> None:
    vps_id = os.getenv("MAIL_AGENT_VPS_ID", "").strip() or socket.gethostname()
    provider = os.getenv("MAIL_PROVIDER", "").strip() or "imap"
    fetch_limit = max(1, _get_int_env("MAIL_AGENT_FETCH_LIMIT", 50))
    state = load_state()

    client = connect_imap()
    try:
        for mailbox in list_mailboxes():
            mailbox_state = state.get(mailbox) or {}
            last_uid = int(mailbox_state.get("last_uid") or 0)
            run_started_at = datetime.utcnow().isoformat()
            try:
                messages, new_last_uid = fetch_mailbox_messages(
                    client=client,
                    mailbox=mailbox,
                    last_uid=last_uid,
                    fetch_limit=fetch_limit,
                )
                payload = {
                    "vps_id": vps_id,
                    "provider": provider,
                    "mailbox": mailbox,
                    "agent_version": AGENT_VERSION,
                    "run_started_at": run_started_at,
                    "run_finished_at": datetime.utcnow().isoformat(),
                    "status": "ok",
                    "cursor": str(new_last_uid),
                    "messages": messages,
                    "payload": {
                        "last_uid_before": last_uid,
                        "last_uid_after": new_last_uid,
                    },
                }
                post_ingest(payload)
                state[mailbox] = {"last_uid": new_last_uid}
            except Exception as exc:
                _log(f"Mailbox {mailbox} failed: {exc}")
                try:
                    post_ingest(
                        {
                            "vps_id": vps_id,
                            "provider": provider,
                            "mailbox": mailbox,
                            "agent_version": AGENT_VERSION,
                            "run_started_at": run_started_at,
                            "run_finished_at": datetime.utcnow().isoformat(),
                            "status": "error",
                            "error_message": str(exc),
                            "cursor": str(last_uid),
                            "messages": [],
                            "payload": {
                                "last_uid_before": last_uid,
                                "last_uid_after": last_uid,
                            },
                        }
                    )
                except Exception as report_exc:
                    _log(f"Failed to report mailbox error for {mailbox}: {report_exc}")
        save_state(state)
    finally:
        try:
            client.logout()
        except Exception:
            pass

    _log("Cycle finished.")


def main() -> int:
    load_embedded_config()
    interval_seconds = max(60, _get_int_env("MAIL_AGENT_INTERVAL_SECONDS", 3600))
    _log(f"Mail agent started. Run interval: {interval_seconds} seconds.")

    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            _log("Stopped by user.")
            return 0
        except Exception as exc:
            _log(f"Cycle failed: {exc}")

        _log(f"Sleeping for {interval_seconds} seconds before the next cycle.")
        try:
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            _log("Stopped by user.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
