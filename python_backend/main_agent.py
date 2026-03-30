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
CONFIG_FILE_NAME = "config.json"
ACCOUNT_LIST_KEY = "MAIL_ACCOUNTS"
MIN_IMAP_PASSWORD_LENGTH = 16


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


def _normalize_imap_password(value: str) -> str:
    return re.sub(r"\s+", "", str(value or ""))


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


def _config_file_path() -> Path:
    return Path(__file__).resolve().parent / CONFIG_FILE_NAME


def load_config_file() -> dict:
    config_path = _config_file_path()
    if not config_path.exists():
        raise RuntimeError(f"{CONFIG_FILE_NAME} was not found next to main_agent.py.")

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid {CONFIG_FILE_NAME}: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"{CONFIG_FILE_NAME} must contain a JSON object.")

    for key, value in payload.items():
        if key == ACCOUNT_LIST_KEY:
            continue
        for env_key, env_value in _iter_json_env_items("", {key: value}):
            normalized = _normalize_value(env_value)
            if normalized is None:
                continue
            os.environ.setdefault(env_key, normalized)

    return payload


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


def _get_account_value(account: dict, name: str):
    if name in account:
        value = account.get(name)
        if value is not None and str(value).strip() != "":
            return value
    return None


def _get_account_string(account: dict, name: str, default: str = "", required: bool = False) -> str:
    value = _get_account_value(account, name)
    if value is None:
        value = os.getenv(name, "").strip() or default
    normalized = str(value or "").strip()
    if required and _is_placeholder(normalized):
        raise RuntimeError(f"Missing or placeholder configuration value: {name}")
    return normalized


def _get_account_bool(account: dict, name: str, default: bool) -> bool:
    value = _get_account_value(account, name)
    if value is None:
        return _get_bool_env(name, default)
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _get_account_int(account: dict, name: str, default: int) -> int:
    value = _get_account_value(account, name)
    if value is None:
        return _get_int_env(name, default)
    return int(value)


def _normalize_account_email(value: str) -> str:
    return str(value or "").strip().lower()


def load_accounts(config_payload: dict) -> list[dict]:
    raw_accounts = config_payload.get(ACCOUNT_LIST_KEY)
    normalized_accounts = []

    if isinstance(raw_accounts, list):
        for index, item in enumerate(raw_accounts, start=1):
            if not isinstance(item, dict):
                raise RuntimeError(f"{ACCOUNT_LIST_KEY}[{index}] must be a JSON object.")

            username = (
                str(item.get("MAIL_IMAP_USERNAME") or item.get("EMAIL") or "").strip()
            )
            password = (
                _normalize_imap_password(
                    item.get("MAIL_IMAP_PASSWORD")
                    or item.get("PASSWORD")
                    or item.get("MAIL_IMAP_APP_PASSWORD")
                    or ""
                )
            )

            if _is_placeholder(username):
                raise RuntimeError(f"{ACCOUNT_LIST_KEY}[{index}] is missing MAIL_IMAP_USERNAME.")
            if _is_placeholder(password):
                raise RuntimeError(f"{ACCOUNT_LIST_KEY}[{index}] is missing MAIL_IMAP_PASSWORD.")
            if len(password) < MIN_IMAP_PASSWORD_LENGTH:
                raise RuntimeError(
                    f"{ACCOUNT_LIST_KEY}[{index}] MAIL_IMAP_PASSWORD must be at least "
                    f"{MIN_IMAP_PASSWORD_LENGTH} characters."
                )

            account = dict(item)
            account["MAIL_IMAP_USERNAME"] = username
            account["MAIL_IMAP_PASSWORD"] = password
            normalized_accounts.append(account)

    if normalized_accounts:
        return normalized_accounts

    fallback_username = os.getenv("MAIL_IMAP_USERNAME", "").strip()
    fallback_password = _normalize_imap_password(
        os.getenv("MAIL_IMAP_PASSWORD", "").strip() or os.getenv("MAIL_IMAP_APP_PASSWORD", "").strip()
    )
    if not _is_placeholder(fallback_username) and not _is_placeholder(fallback_password):
        if len(fallback_password) < MIN_IMAP_PASSWORD_LENGTH:
            raise RuntimeError(
                f"MAIL_IMAP_PASSWORD must be at least {MIN_IMAP_PASSWORD_LENGTH} characters."
            )
        return [
            {
                "MAIL_IMAP_USERNAME": fallback_username,
                "MAIL_IMAP_PASSWORD": fallback_password,
            }
        ]

    raise RuntimeError(f"{CONFIG_FILE_NAME} must contain {ACCOUNT_LIST_KEY} with at least one account.")


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


def connect_imap(account: dict):
    host = _get_account_string(account, "MAIL_IMAP_HOST", required=True)
    port = _get_account_int(account, "MAIL_IMAP_PORT", 993)
    username = _get_account_string(account, "MAIL_IMAP_USERNAME", required=True)
    password = _normalize_imap_password(
        _get_account_string(account, "MAIL_IMAP_PASSWORD")
        or _get_account_string(
            account,
            "MAIL_IMAP_APP_PASSWORD",
            required=True,
        )
    )
    if len(password) < MIN_IMAP_PASSWORD_LENGTH:
        raise RuntimeError(
            f"MAIL_IMAP_PASSWORD must be at least {MIN_IMAP_PASSWORD_LENGTH} characters."
        )
    use_ssl = _get_account_bool(account, "MAIL_IMAP_SSL", True)
    timeout = _get_account_int(account, "MAIL_IMAP_TIMEOUT", 30)

    socket.setdefaulttimeout(timeout)
    client = imaplib.IMAP4_SSL(host, port) if use_ssl else imaplib.IMAP4(host, port)
    client.login(username, password)
    return client


def list_mailboxes(account: dict) -> list[str]:
    value = _get_account_value(account, "MAIL_IMAP_MAILBOXES")
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item or "").strip()]
        return items or ["INBOX"]

    raw = str(value).strip() if value is not None else os.getenv("MAIL_IMAP_MAILBOXES", "").strip()
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


def run_once(config_payload: dict) -> None:
    vps_id = os.getenv("MAIL_AGENT_VPS_ID", "").strip() or socket.gethostname()
    provider = os.getenv("MAIL_PROVIDER", "").strip() or "imap"
    fetch_limit = max(1, _get_int_env("MAIL_AGENT_FETCH_LIMIT", 50))
    accounts = load_accounts(config_payload)
    raw_state = load_state()
    state_accounts = raw_state.get("accounts") if isinstance(raw_state.get("accounts"), dict) else {}

    # Migrate legacy single-account state keyed directly by mailbox.
    if not state_accounts and len(accounts) == 1:
        legacy_state = {
            key: value
            for key, value in raw_state.items()
            if key != "accounts" and isinstance(value, dict)
        }
        if legacy_state:
            state_accounts[_normalize_account_email(accounts[0].get("MAIL_IMAP_USERNAME", ""))] = legacy_state

    for account in accounts:
        account_email = _normalize_account_email(_get_account_string(account, "MAIL_IMAP_USERNAME", required=True))
        account_provider = _get_account_string(account, "MAIL_PROVIDER", default=provider) or provider
        account_state = state_accounts.get(account_email)
        if not isinstance(account_state, dict):
            account_state = {}
            state_accounts[account_email] = account_state

        client = connect_imap(account)
        try:
            for mailbox in list_mailboxes(account):
                mailbox_state = account_state.get(mailbox) or {}
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
                        "account_email": account_email,
                        "provider": account_provider,
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
                    account_state[mailbox] = {"last_uid": new_last_uid}
                except Exception as exc:
                    _log(f"Account {account_email} mailbox {mailbox} failed: {exc}")
                    try:
                        post_ingest(
                            {
                                "vps_id": vps_id,
                                "account_email": account_email,
                                "provider": account_provider,
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
                        _log(f"Failed to report mailbox error for {account_email}/{mailbox}: {report_exc}")
        finally:
            try:
                client.logout()
            except Exception:
                pass

    save_state({"accounts": state_accounts})

    _log("Cycle finished.")


def main() -> int:
    config_payload = load_config_file()
    interval_seconds = max(60, _get_int_env("MAIL_AGENT_INTERVAL_SECONDS", 3600))
    _log(f"Mail agent started. Run interval: {interval_seconds} seconds.")

    while True:
        try:
            run_once(config_payload)
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
