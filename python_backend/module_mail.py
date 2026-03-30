import hashlib
import json
import os
from datetime import datetime
from html import escape
from typing import Any, Optional

import requests
from sqlalchemy import bindparam, text

from python_backend.db import engine


def _infer_mail_match(*, from_name: Optional[str], from_email: Optional[str]) -> tuple[str, Optional[str]]:
    sender_parts = [str(from_name or "").strip().lower(), str(from_email or "").strip().lower()]
    sender_text = " ".join(part for part in sender_parts if part)
    if "youtube" in sender_text:
        return "matched", "from:youtube"
    return "received", None


def _is_telegram_enabled() -> bool:
    raw = str(os.getenv("TELEGRAM_ENABLED", "1") or "").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _send_telegram_match_alert(
    *,
    vps_id: str,
    account_email: str,
    mailbox: str,
    matched_messages: list[dict[str, Any]],
) -> None:
    if not matched_messages or not _is_telegram_enabled():
        return

    bot_token = str(os.getenv("TELEGRAM_BOT_TOKEN", "") or "").strip()
    chat_id = str(os.getenv("TELEGRAM_CHAT_ID", "") or "").strip()
    if not bot_token or not chat_id:
        return

    lines = [
        "<b>Email Manager</b>",
        f"Machine: <code>{escape(vps_id or '-')}</code>",
        f"Account: <code>{escape(account_email or '-')}</code>",
        f"Mailbox: <code>{escape(mailbox or '-')}</code>",
        f"New matched emails: <b>{len(matched_messages)}</b>",
        "",
    ]

    for index, item in enumerate(matched_messages[:5], start=1):
        sender = item.get("from_name") or item.get("from_email") or "-"
        subject = item.get("subject") or "(no subject)"
        lines.append(f"{index}. {escape(str(sender))} | {escape(str(subject))}")

    if len(matched_messages) > 5:
        lines.append(f"... and {len(matched_messages) - 5} more")

    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": "\n".join(lines),
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        ).raise_for_status()
    except Exception:
        # Telegram notification failure should not break mail ingest.
        return


def send_test_telegram_notification() -> dict[str, Any]:
    bot_token = str(os.getenv("TELEGRAM_BOT_TOKEN", "") or "").strip()
    chat_id = str(os.getenv("TELEGRAM_CHAT_ID", "") or "").strip()

    if not _is_telegram_enabled():
        raise ValueError("TELEGRAM_ENABLED is disabled.")
    if not bot_token:
        raise ValueError("Missing TELEGRAM_BOT_TOKEN.")
    if not chat_id:
        raise ValueError("Missing TELEGRAM_CHAT_ID.")

    lines = [
        "<b>Email Manager</b>",
        "Telegram test notification",
        f"Time: <code>{datetime.utcnow().isoformat()}Z</code>",
        "Status: <b>ok</b>",
    ]

    response = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": "\n".join(lines),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=10,
    )
    response.raise_for_status()

    return {
        "ok": True,
        "chat_id": chat_id,
        "telegram_ok": True,
    }


def ensure_mail_tables() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS mail_monitor_messages (
                    id BIGSERIAL PRIMARY KEY,
                    vps_id TEXT NOT NULL,
                    account_email TEXT NOT NULL DEFAULT '',
                    provider TEXT NOT NULL DEFAULT 'imap',
                    mailbox TEXT NOT NULL,
                    provider_message_id TEXT NOT NULL,
                    uid BIGINT,
                    thread_id TEXT,
                    subject TEXT,
                    from_email TEXT,
                    from_name TEXT,
                    to_email TEXT,
                    received_at TIMESTAMP NULL,
                    seen BOOLEAN NOT NULL DEFAULT FALSE,
                    status TEXT NOT NULL DEFAULT 'received',
                    matched_rule TEXT,
                    snippet TEXT,
                    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    first_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    last_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE (vps_id, account_email, mailbox, provider_message_id)
                );
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE mail_monitor_messages
                ADD COLUMN IF NOT EXISTS account_email TEXT NOT NULL DEFAULT '';
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE mail_monitor_messages
                DROP CONSTRAINT IF EXISTS mail_monitor_messages_vps_id_mailbox_provider_message_id_key;
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_mail_monitor_messages_vps_mailbox
                ON mail_monitor_messages (vps_id, mailbox);
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_mail_monitor_messages_machine_account_mailbox
                ON mail_monitor_messages (vps_id, account_email, mailbox);
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_mail_monitor_messages_received_at
                ON mail_monitor_messages (received_at DESC NULLS LAST);
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_mail_monitor_messages_status
                ON mail_monitor_messages (status);
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS mail_monitor_runs (
                    id BIGSERIAL PRIMARY KEY,
                    vps_id TEXT NOT NULL,
                    account_email TEXT NOT NULL DEFAULT '',
                    provider TEXT NOT NULL DEFAULT 'imap',
                    mailbox TEXT NOT NULL,
                    agent_version TEXT,
                    run_started_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    run_finished_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    status TEXT NOT NULL DEFAULT 'ok',
                    message_count INTEGER NOT NULL DEFAULT 0,
                    inserted_count INTEGER NOT NULL DEFAULT 0,
                    updated_count INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT,
                    cursor TEXT,
                    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                );
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE mail_monitor_runs
                ADD COLUMN IF NOT EXISTS account_email TEXT NOT NULL DEFAULT '';
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_mail_monitor_runs_vps_mailbox
                ON mail_monitor_runs (vps_id, mailbox, run_finished_at DESC);
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_mail_monitor_runs_machine_account_mailbox
                ON mail_monitor_runs (vps_id, account_email, mailbox, run_finished_at DESC);
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_monitor_messages_machine_account_mailbox_message
                ON mail_monitor_messages (vps_id, account_email, mailbox, provider_message_id);
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE SEQUENCE IF NOT EXISTS mail_monitor_vps_seq
                START WITH 1
                INCREMENT BY 1;
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE mail_monitor_messages
                SET
                    status = 'matched',
                    matched_rule = 'from:youtube',
                    updated_at = NOW()
                WHERE
                    (matched_rule IS NULL OR matched_rule = '')
                    AND COALESCE(status, 'received') = 'received'
                    AND (
                        LOWER(COALESCE(from_name, '')) LIKE '%youtube%'
                        OR LOWER(COALESCE(from_email, '')) LIKE '%youtube%'
                    )
                """
            )
        )


def _normalize_message_id(
    vps_id: str,
    account_email: str,
    mailbox: str,
    raw_message_id: Optional[str],
    uid: Optional[int],
    subject: Optional[str],
    from_email: Optional[str],
    received_at: Optional[datetime],
) -> str:
    if raw_message_id:
        return str(raw_message_id).strip()
    if uid is not None:
        return f"uid:{uid}"
    seed = "|".join(
        [
            vps_id,
            account_email,
            mailbox,
            str(subject or ""),
            str(from_email or ""),
            str(received_at.isoformat() if received_at else ""),
        ]
    )
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()


def _normalize_message(
    *,
    vps_id: str,
    account_email: str,
    provider: str,
    mailbox: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    payload = item.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    received_at = item.get("received_at")
    if isinstance(received_at, str):
        try:
            received_at = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        except ValueError:
            received_at = None
    if not isinstance(received_at, datetime):
        received_at = None

    uid = item.get("uid")
    try:
        uid = int(uid) if uid is not None else None
    except (TypeError, ValueError):
        uid = None

    provider_message_id = _normalize_message_id(
        vps_id=vps_id,
        account_email=account_email,
        mailbox=mailbox,
        raw_message_id=item.get("provider_message_id"),
        uid=uid,
        subject=item.get("subject"),
        from_email=item.get("from_email"),
        received_at=received_at,
    )

    inferred_status, inferred_rule = _infer_mail_match(
        from_name=item.get("from_name"),
        from_email=item.get("from_email"),
    )
    status = str(item.get("status") or inferred_status).strip().lower() or inferred_status
    matched_rule = item.get("matched_rule") or inferred_rule
    if status == "received" and matched_rule:
        status = "matched"

    return {
        "vps_id": vps_id,
        "account_email": account_email,
        "provider": provider or "imap",
        "mailbox": mailbox,
        "provider_message_id": provider_message_id,
        "uid": uid,
        "thread_id": item.get("thread_id"),
        "subject": item.get("subject"),
        "from_email": item.get("from_email"),
        "from_name": item.get("from_name"),
        "to_email": item.get("to_email"),
        "received_at": received_at,
        "seen": bool(item.get("seen", False)),
        "status": status,
        "matched_rule": matched_rule,
        "snippet": item.get("snippet"),
        "payload": json.dumps(payload),
    }


def save_mail_ingest(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_mail_tables()

    vps_id = str(payload.get("vps_id") or "").strip()
    account_email = str(payload.get("account_email") or "").strip().lower()
    mailbox = str(payload.get("mailbox") or "INBOX").strip() or "INBOX"
    provider = str(payload.get("provider") or "imap").strip() or "imap"
    status = str(payload.get("status") or "ok").strip().lower() or "ok"
    agent_version = str(payload.get("agent_version") or "").strip() or None
    cursor = str(payload.get("cursor") or "").strip() or None
    error_message = str(payload.get("error_message") or "").strip() or None
    run_started_at = payload.get("run_started_at")
    run_finished_at = payload.get("run_finished_at")
    messages_raw = payload.get("messages") or []
    run_payload = payload.get("payload")
    if not isinstance(run_payload, dict):
        run_payload = {}

    if not vps_id:
        raise ValueError("Missing vps_id")

    if isinstance(run_started_at, str):
        run_started_at = datetime.fromisoformat(run_started_at.replace("Z", "+00:00"))
    if isinstance(run_finished_at, str):
        run_finished_at = datetime.fromisoformat(run_finished_at.replace("Z", "+00:00"))
    if not isinstance(run_started_at, datetime):
        run_started_at = datetime.utcnow()
    if not isinstance(run_finished_at, datetime):
        run_finished_at = datetime.utcnow()

    deduped_messages: dict[str, dict[str, Any]] = {}
    for item in messages_raw:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_message(
            vps_id=vps_id,
            account_email=account_email,
            provider=provider,
            mailbox=mailbox,
            item=item,
        )
        deduped_messages[normalized["provider_message_id"]] = normalized

    normalized_messages = list(deduped_messages.values())
    provider_message_ids = [item["provider_message_id"] for item in normalized_messages]

    inserted_count = 0
    updated_count = 0
    newly_matched_messages: list[dict[str, Any]] = []

    with engine.begin() as conn:
        existing_messages: dict[str, dict[str, Any]] = {}
        if provider_message_ids:
            existing_query = text(
                """
                SELECT provider_message_id, status, matched_rule
                FROM mail_monitor_messages
                WHERE vps_id = :vps_id
                  AND account_email = :account_email
                  AND mailbox = :mailbox
                  AND provider_message_id IN :provider_message_ids
                """
            ).bindparams(bindparam("provider_message_ids", expanding=True))
            rows = conn.execute(
                existing_query,
                {
                    "vps_id": vps_id,
                    "account_email": account_email,
                    "mailbox": mailbox,
                    "provider_message_ids": provider_message_ids,
                },
            ).mappings().all()
            existing_messages = {
                str(row["provider_message_id"]): dict(row)
                for row in rows
                if row.get("provider_message_id") is not None
            }

        if normalized_messages:
            upsert_statement = text(
                """
                INSERT INTO mail_monitor_messages (
                    vps_id,
                    account_email,
                    provider,
                    mailbox,
                    provider_message_id,
                    uid,
                    thread_id,
                    subject,
                    from_email,
                    from_name,
                    to_email,
                    received_at,
                    seen,
                    status,
                    matched_rule,
                    snippet,
                    payload,
                    first_seen_at,
                    last_seen_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    :vps_id,
                    :account_email,
                    :provider,
                    :mailbox,
                    :provider_message_id,
                    :uid,
                    :thread_id,
                    :subject,
                    :from_email,
                    :from_name,
                    :to_email,
                    :received_at,
                    :seen,
                    :status,
                    :matched_rule,
                    :snippet,
                    CAST(:payload AS JSONB),
                    NOW(),
                    NOW(),
                    NOW(),
                    NOW()
                )
                ON CONFLICT (vps_id, account_email, mailbox, provider_message_id)
                DO UPDATE SET
                    provider = EXCLUDED.provider,
                    uid = EXCLUDED.uid,
                    thread_id = EXCLUDED.thread_id,
                    subject = EXCLUDED.subject,
                    from_email = EXCLUDED.from_email,
                    from_name = EXCLUDED.from_name,
                    to_email = EXCLUDED.to_email,
                    received_at = EXCLUDED.received_at,
                    seen = EXCLUDED.seen,
                    status = EXCLUDED.status,
                    matched_rule = EXCLUDED.matched_rule,
                    snippet = EXCLUDED.snippet,
                    payload = EXCLUDED.payload,
                    last_seen_at = NOW(),
                    updated_at = NOW()
                """
            )
            conn.execute(upsert_statement, normalized_messages)

        inserted_count = max(len(normalized_messages) - len(existing_messages), 0)
        updated_count = min(len(existing_messages), len(normalized_messages))

        for message in normalized_messages:
            if message.get("status") != "matched":
                continue
            existing = existing_messages.get(str(message.get("provider_message_id") or ""))
            if existing and str(existing.get("status") or "").strip().lower() == "matched":
                continue
            newly_matched_messages.append(message)

        conn.execute(
            text(
                """
                INSERT INTO mail_monitor_runs (
                    vps_id,
                    account_email,
                    provider,
                    mailbox,
                    agent_version,
                    run_started_at,
                    run_finished_at,
                    status,
                    message_count,
                    inserted_count,
                    updated_count,
                    error_message,
                    cursor,
                    payload,
                    created_at
                )
                VALUES (
                    :vps_id,
                    :account_email,
                    :provider,
                    :mailbox,
                    :agent_version,
                    :run_started_at,
                    :run_finished_at,
                    :status,
                    :message_count,
                    :inserted_count,
                    :updated_count,
                    :error_message,
                    :cursor,
                    CAST(:payload AS JSONB),
                    NOW()
                )
                """
            ),
            {
                "vps_id": vps_id,
                "account_email": account_email,
                "provider": provider,
                "mailbox": mailbox,
                "agent_version": agent_version,
                "run_started_at": run_started_at,
                "run_finished_at": run_finished_at,
                "status": status,
                "message_count": len(normalized_messages),
                "inserted_count": inserted_count,
                "updated_count": updated_count,
                "error_message": error_message,
                "cursor": cursor,
                "payload": json.dumps(run_payload),
            },
        )

    _send_telegram_match_alert(
        vps_id=vps_id,
        account_email=account_email,
        mailbox=mailbox,
        matched_messages=newly_matched_messages,
    )

    return {
        "ok": True,
        "vps_id": vps_id,
        "account_email": account_email,
        "mailbox": mailbox,
        "message_count": len(normalized_messages),
        "inserted_count": inserted_count,
        "updated_count": updated_count,
        "status": status,
    }


def get_mail_overview() -> dict[str, Any]:
    ensure_mail_tables()

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                WITH mailbox_keys AS (
                    SELECT DISTINCT vps_id, account_email, mailbox FROM mail_monitor_messages
                    UNION
                    SELECT DISTINCT vps_id, account_email, mailbox FROM mail_monitor_runs
                ),
                message_stats AS (
                    SELECT
                        vps_id,
                        account_email,
                        mailbox,
                        MAX(provider) AS provider,
                        COUNT(*)::bigint AS total_messages,
                        COUNT(*) FILTER (WHERE COALESCE(seen, FALSE) = FALSE)::bigint AS unread_messages,
                        COUNT(*) FILTER (WHERE status = 'error')::bigint AS error_messages,
                        MAX(received_at) AS latest_received_at,
                        MAX(last_seen_at) AS latest_seen_at
                    FROM mail_monitor_messages
                    GROUP BY vps_id, account_email, mailbox
                ),
                latest_runs AS (
                    SELECT DISTINCT ON (vps_id, account_email, mailbox)
                        vps_id,
                        account_email,
                        mailbox,
                        provider,
                        status AS last_run_status,
                        error_message,
                        run_finished_at,
                        message_count,
                        inserted_count,
                        updated_count
                    FROM mail_monitor_runs
                    ORDER BY vps_id, account_email, mailbox, run_finished_at DESC, id DESC
                )
                SELECT
                    k.vps_id,
                    k.account_email,
                    k.mailbox,
                    COALESCE(r.provider, m.provider, 'imap') AS provider,
                    COALESCE(m.total_messages, 0) AS total_messages,
                    COALESCE(m.unread_messages, 0) AS unread_messages,
                    COALESCE(m.error_messages, 0) AS error_messages,
                    m.latest_received_at,
                    m.latest_seen_at,
                    r.last_run_status,
                    r.error_message,
                    r.run_finished_at AS last_run_finished_at,
                    COALESCE(r.message_count, 0) AS last_run_message_count,
                    COALESCE(r.inserted_count, 0) AS last_run_inserted_count,
                    COALESCE(r.updated_count, 0) AS last_run_updated_count
                FROM mailbox_keys k
                LEFT JOIN message_stats m
                  ON m.vps_id = k.vps_id AND m.account_email = k.account_email AND m.mailbox = k.mailbox
                LEFT JOIN latest_runs r
                  ON r.vps_id = k.vps_id AND r.account_email = k.account_email AND r.mailbox = k.mailbox
                ORDER BY COALESCE(r.run_finished_at, m.latest_seen_at, m.latest_received_at) DESC NULLS LAST,
                         k.vps_id,
                         k.account_email,
                         k.mailbox
                """
            )
        ).mappings().all()

        summary_row = conn.execute(
            text(
                """
                WITH mailbox_keys AS (
                    SELECT DISTINCT vps_id, account_email, mailbox FROM mail_monitor_messages
                    UNION
                    SELECT DISTINCT vps_id, account_email, mailbox FROM mail_monitor_runs
                ),
                message_stats AS (
                    SELECT
                        vps_id,
                        account_email,
                        mailbox,
                        COUNT(*)::bigint AS total_messages,
                        COUNT(*) FILTER (WHERE COALESCE(seen, FALSE) = FALSE)::bigint AS unread_messages
                    FROM mail_monitor_messages
                    GROUP BY vps_id, account_email, mailbox
                ),
                latest_runs AS (
                    SELECT DISTINCT ON (vps_id, account_email, mailbox)
                        vps_id,
                        account_email,
                        mailbox,
                        status AS last_run_status
                    FROM mail_monitor_runs
                    ORDER BY vps_id, account_email, mailbox, run_finished_at DESC, id DESC
                )
                SELECT
                    COUNT(DISTINCT k.vps_id)::bigint AS vps_count,
                    COUNT(DISTINCT NULLIF(k.account_email, ''))::bigint AS account_count,
                    COUNT(*)::bigint AS mailbox_count,
                    COALESCE(SUM(m.total_messages), 0)::bigint AS total_messages,
                    COALESCE(SUM(m.unread_messages), 0)::bigint AS unread_messages,
                    COUNT(*) FILTER (WHERE COALESCE(r.last_run_status, '') = 'error')::bigint AS error_messages
                FROM mailbox_keys k
                LEFT JOIN message_stats m
                  ON m.vps_id = k.vps_id AND m.account_email = k.account_email AND m.mailbox = k.mailbox
                LEFT JOIN latest_runs r
                  ON r.vps_id = k.vps_id AND r.account_email = k.account_email AND r.mailbox = k.mailbox
                """
            )
        ).mappings().first()

    return {
        "summary": dict(summary_row or {}),
        "items": [dict(row) for row in rows],
    }


def get_next_vps_id() -> str:
    ensure_mail_tables()

    with engine.begin() as conn:
        existing_max_row = conn.execute(
            text(
                """
                SELECT COALESCE(MAX(suffix), 0)::bigint AS highest_suffix
                FROM (
                    SELECT CAST(SUBSTRING(LOWER(vps_id) FROM '^vps-(\d+)$') AS BIGINT) AS suffix
                    FROM mail_monitor_messages
                    UNION ALL
                    SELECT CAST(SUBSTRING(LOWER(vps_id) FROM '^vps-(\d+)$') AS BIGINT) AS suffix
                    FROM mail_monitor_runs
                ) AS ids
                WHERE suffix IS NOT NULL
                """
            )
        ).mappings().first()

        sequence_row = conn.execute(
            text(
                """
                SELECT last_value, is_called
                FROM mail_monitor_vps_seq
                """
            )
        ).mappings().first()

        highest_existing = int((existing_max_row or {}).get("highest_suffix") or 0)
        sequence_last = int((sequence_row or {}).get("last_value") or 0)
        sequence_is_called = bool((sequence_row or {}).get("is_called"))
        if not sequence_is_called:
            sequence_last = 0

        if sequence_last < highest_existing:
            conn.execute(
                text("SELECT setval('mail_monitor_vps_seq', :value, true)"),
                {"value": highest_existing},
            )

        next_value = conn.execute(
            text("SELECT nextval('mail_monitor_vps_seq') AS next_value")
        ).scalar_one()

    return f"vps-{int(next_value):02d}"


def list_mail_messages(
    *,
    vps_id: Optional[str] = None,
    account_email: Optional[str] = None,
    mailbox: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    per_account_limit: Optional[int] = None,
) -> dict[str, Any]:
    ensure_mail_tables()

    where_clauses = []
    params: dict[str, Any] = {
        "limit": max(1, min(int(limit or 100), 500)),
        "offset": max(0, int(offset or 0)),
    }
    normalized_per_account_limit = None
    if per_account_limit is not None:
        normalized_per_account_limit = max(1, min(int(per_account_limit), 500))
        params["per_account_limit"] = normalized_per_account_limit

    if vps_id:
        where_clauses.append("vps_id = :vps_id")
        params["vps_id"] = vps_id
    if account_email:
        where_clauses.append("account_email = :account_email")
        params["account_email"] = str(account_email).strip().lower()
    if mailbox:
        where_clauses.append("mailbox = :mailbox")
        params["mailbox"] = mailbox
    if status:
        where_clauses.append("status = :status")
        params["status"] = status
    if search:
        where_clauses.append(
            """
            (
                COALESCE(subject, '') ILIKE :search
                OR COALESCE(from_email, '') ILIKE :search
                OR COALESCE(from_name, '') ILIKE :search
                OR COALESCE(snippet, '') ILIKE :search
                OR COALESCE(provider_message_id, '') ILIKE :search
            )
            """
        )
        params["search"] = f"%{search.strip()}%"

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    with engine.begin() as conn:
        if normalized_per_account_limit is not None:
            rows = conn.execute(
                text(
                    f"""
                    WITH ranked_messages AS (
                        SELECT
                            id,
                            vps_id,
                            account_email,
                            provider,
                            mailbox,
                            provider_message_id,
                            uid,
                            thread_id,
                            subject,
                            from_email,
                            from_name,
                            to_email,
                            received_at,
                            seen,
                            status,
                            matched_rule,
                            snippet,
                            last_seen_at,
                            updated_at,
                            ROW_NUMBER() OVER (
                                PARTITION BY COALESCE(account_email, '')
                                ORDER BY COALESCE(received_at, updated_at) DESC NULLS LAST, id DESC
                            ) AS row_num
                        FROM mail_monitor_messages
                        {where_sql}
                    )
                    SELECT
                        id,
                        vps_id,
                        account_email,
                        provider,
                        mailbox,
                        provider_message_id,
                        uid,
                        thread_id,
                        subject,
                        from_email,
                        from_name,
                        to_email,
                        received_at,
                        seen,
                        status,
                        matched_rule,
                        snippet,
                        last_seen_at,
                        updated_at
                    FROM ranked_messages
                    WHERE row_num <= :per_account_limit
                    ORDER BY
                        COALESCE(account_email, '') ASC,
                        COALESCE(received_at, updated_at) DESC NULLS LAST,
                        id DESC
                    LIMIT :limit
                    OFFSET :offset
                    """
                ),
                params,
            ).mappings().all()

            total_row = conn.execute(
                text(
                    f"""
                    WITH ranked_messages AS (
                        SELECT
                            ROW_NUMBER() OVER (
                                PARTITION BY COALESCE(account_email, '')
                                ORDER BY COALESCE(received_at, updated_at) DESC NULLS LAST, id DESC
                            ) AS row_num
                        FROM mail_monitor_messages
                        {where_sql}
                    )
                    SELECT COUNT(*)::bigint AS total
                    FROM ranked_messages
                    WHERE row_num <= :per_account_limit
                    """
                ),
                {k: v for k, v in params.items() if k not in {"limit", "offset"}},
            ).mappings().first()
        else:
            rows = conn.execute(
                text(
                    f"""
                    SELECT
                        id,
                        vps_id,
                        account_email,
                        provider,
                        mailbox,
                        provider_message_id,
                        uid,
                        thread_id,
                        subject,
                        from_email,
                        from_name,
                        to_email,
                        received_at,
                        seen,
                        status,
                        matched_rule,
                        snippet,
                        last_seen_at,
                        updated_at
                    FROM mail_monitor_messages
                    {where_sql}
                    ORDER BY COALESCE(received_at, updated_at) DESC NULLS LAST, id DESC
                    LIMIT :limit
                    OFFSET :offset
                    """
                ),
                params,
            ).mappings().all()

            total_row = conn.execute(
                text(
                    f"""
                    SELECT COUNT(*)::bigint AS total
                    FROM mail_monitor_messages
                    {where_sql}
                    """
                ),
                {k: v for k, v in params.items() if k not in {"limit", "offset"}},
            ).mappings().first()

    return {
        "items": [dict(row) for row in rows],
        "total": int((total_row or {}).get("total") or 0),
    }


def get_mail_message_detail(message_id: int) -> Optional[dict[str, Any]]:
    ensure_mail_tables()

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    id,
                    vps_id,
                    account_email,
                    provider,
                    mailbox,
                    provider_message_id,
                    uid,
                    thread_id,
                    subject,
                    from_email,
                    from_name,
                    to_email,
                    received_at,
                    seen,
                    status,
                    matched_rule,
                    snippet,
                    payload,
                    first_seen_at,
                    last_seen_at,
                    created_at,
                    updated_at
                FROM mail_monitor_messages
                WHERE id = :message_id
                LIMIT 1
                """
            ),
            {"message_id": int(message_id)},
        ).mappings().first()

    return dict(row) if row else None


def delete_mail_machine(vps_id: str) -> dict[str, Any]:
    ensure_mail_tables()

    normalized_vps_id = str(vps_id or "").strip()
    if not normalized_vps_id:
        raise ValueError("Machine is required.")

    with engine.begin() as conn:
        message_deleted = conn.execute(
            text(
                """
                DELETE FROM mail_monitor_messages
                WHERE vps_id = :vps_id
                """
            ),
            {"vps_id": normalized_vps_id},
        ).rowcount or 0

        run_deleted = conn.execute(
            text(
                """
                DELETE FROM mail_monitor_runs
                WHERE vps_id = :vps_id
                """
            ),
            {"vps_id": normalized_vps_id},
        ).rowcount or 0

    return {
        "ok": True,
        "vps_id": normalized_vps_id,
        "deleted_messages": int(message_deleted),
        "deleted_runs": int(run_deleted),
    }


def delete_mail_account(vps_id: str, account_email: str) -> dict[str, Any]:
    ensure_mail_tables()

    normalized_vps_id = str(vps_id or "").strip()
    normalized_account_email = str(account_email or "").strip().lower()
    if not normalized_vps_id:
        raise ValueError("Machine is required.")
    if not normalized_account_email:
        raise ValueError("Account email is required.")

    with engine.begin() as conn:
        message_deleted = conn.execute(
            text(
                """
                DELETE FROM mail_monitor_messages
                WHERE vps_id = :vps_id
                  AND account_email = :account_email
                """
            ),
            {
                "vps_id": normalized_vps_id,
                "account_email": normalized_account_email,
            },
        ).rowcount or 0

        run_deleted = conn.execute(
            text(
                """
                DELETE FROM mail_monitor_runs
                WHERE vps_id = :vps_id
                  AND account_email = :account_email
                """
            ),
            {
                "vps_id": normalized_vps_id,
                "account_email": normalized_account_email,
            },
        ).rowcount or 0

    return {
        "ok": True,
        "vps_id": normalized_vps_id,
        "account_email": normalized_account_email,
        "deleted_messages": int(message_deleted),
        "deleted_runs": int(run_deleted),
    }


def list_mail_runs(
    *,
    vps_id: Optional[str] = None,
    account_email: Optional[str] = None,
    mailbox: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    ensure_mail_tables()

    where_clauses = []
    params: dict[str, Any] = {
        "limit": max(1, min(int(limit or 50), 200)),
    }

    if vps_id:
        where_clauses.append("vps_id = :vps_id")
        params["vps_id"] = vps_id
    if account_email:
        where_clauses.append("account_email = :account_email")
        params["account_email"] = str(account_email).strip().lower()
    if mailbox:
        where_clauses.append("mailbox = :mailbox")
        params["mailbox"] = mailbox

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT
                    id,
                    vps_id,
                    account_email,
                    provider,
                    mailbox,
                    agent_version,
                    run_started_at,
                    run_finished_at,
                    status,
                    message_count,
                    inserted_count,
                    updated_count,
                    error_message,
                    cursor,
                    created_at
                FROM mail_monitor_runs
                {where_sql}
                ORDER BY run_finished_at DESC NULLS LAST, id DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()

    return {"items": [dict(row) for row in rows]}
