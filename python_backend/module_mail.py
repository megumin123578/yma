import hashlib
import json
import os
from datetime import datetime
from html import escape
from typing import Any, Optional

import requests
from sqlalchemy import bindparam, text

from python_backend.db import engine

def _normalize_account_email_scope(account_emails: Optional[list[str]]) -> Optional[list[str]]:
    if account_emails is None:
        return None
    normalized = [
        str(item or "").strip().lower()
        for item in account_emails
        if str(item or "").strip()
    ]
    return list(dict.fromkeys(normalized))


def _append_account_email_scope(
    where_clauses: list[str],
    params: dict[str, Any],
    account_emails: Optional[list[str]],
    *,
    column_name: str = "account_email",
) -> None:
    normalized = _normalize_account_email_scope(account_emails)
    if normalized is None:
        return
    if not normalized:
        where_clauses.append("1 = 0")
        return
    where_clauses.append(f"{column_name} IN :account_emails")
    params["account_emails"] = normalized


def _bind_expanding_params(statement, params: dict[str, Any]):
    if "account_emails" in params:
        return statement.bindparams(bindparam("account_emails", expanding=True))
    return statement


def _infer_mail_match(*, from_name: Optional[str], from_email: Optional[str]) -> tuple[str, Optional[str]]:
    sender_parts = [str(from_name or "").strip().lower(), str(from_email or "").strip().lower()]
    sender_text = " ".join(part for part in sender_parts if part)
    if "youtube" in sender_text:
        return "matched", "from:youtube"
    return "received", None


def _is_telegram_enabled() -> bool:
    raw = str(os.getenv("TELEGRAM_ENABLED", "1") or "").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _mail_record(item: Optional[dict[str, Any]]) -> dict[str, Any]:
    return dict(item or {})


def _build_telegram_match_alert_lines(
    *,
    account_email: str,
    channel_name: Optional[str] = None,
    mailbox: str,
    matched_messages: list[dict[str, Any]],
) -> list[str]:
    normalized_mailbox = str(mailbox or "").strip()
    lines = [f"Account: <code>{escape(account_email or '-')}</code>"]
    normalized_channel_name = str(channel_name or "").strip()
    if normalized_channel_name:
        lines.append(f"Channel: <code>{escape(normalized_channel_name)}</code>")
    if normalized_mailbox and normalized_mailbox.upper() != "INBOX":
        lines.append(f"Mailbox: <code>{escape(normalized_mailbox)}</code>")
    lines.append("")

    for index, item in enumerate(matched_messages[:5], start=1):
        sender = item.get("from_name") or item.get("from_email") or "-"
        subject = item.get("subject") or "(no subject)"
        lines.append(f"{index}. {escape(str(sender))} | {escape(str(subject))}")
        snippet = str(item.get("snippet") or "").strip()
        if snippet:
            if len(snippet) > 500:
                snippet = snippet[:500].rstrip() + "..."
            lines.append(f"<blockquote>{escape(snippet)}</blockquote>")

    if len(matched_messages) > 5:
        lines.append(f"... and {len(matched_messages) - 5} more")

    return lines


def build_telegram_match_alert_payload(
    *,
    account_email: str,
    channel_name: Optional[str] = None,
    mailbox: str,
    matched_messages: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "text": "\n".join(
            _build_telegram_match_alert_lines(
                account_email=account_email,
                channel_name=channel_name,
                mailbox=mailbox,
                matched_messages=matched_messages,
            )
        ),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }


def _send_telegram_match_alert(
    *,
    account_email: str,
    channel_name: Optional[str] = None,
    mailbox: str,
    matched_messages: list[dict[str, Any]],
) -> None:
    if not matched_messages or not _is_telegram_enabled():
        return

    bot_token = str(os.getenv("TELEGRAM_BOT_TOKEN", "") or "").strip()
    chat_id = str(os.getenv("TELEGRAM_CHAT_ID", "") or "").strip()
    if not bot_token or not chat_id:
        return

    payload = build_telegram_match_alert_payload(
        account_email=account_email,
        channel_name=channel_name,
        mailbox=mailbox,
        matched_messages=matched_messages,
    )

    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                **payload,
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

    payload = build_test_telegram_message_payload()

    response = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={
            "chat_id": chat_id,
            **payload,
        },
        timeout=10,
    )
    response.raise_for_status()

    return {
        "ok": True,
        "chat_id": chat_id,
        "telegram_ok": True,
    }


def build_test_telegram_message_payload(*, triggered_at: Optional[str] = None) -> dict[str, Any]:
    lines = [
        "<b>Email Manager</b>",
        "Telegram test notification",
        f"Time: <code>{str(triggered_at or f'{datetime.utcnow().isoformat()}Z').strip()}</code>",
        "Status: <b>ok</b>",
    ]
    return {
        "text": "\n".join(lines),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }


def ensure_mail_tables() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS mail_monitor_messages (
                    id BIGSERIAL PRIMARY KEY,
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
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
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
                WITH ranked_duplicates AS (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (
                            PARTITION BY
                                COALESCE(account_email, ''),
                                COALESCE(mailbox, ''),
                                COALESCE(provider_message_id, '')
                            ORDER BY
                                COALESCE(received_at, updated_at, last_seen_at, created_at) DESC NULLS LAST,
                                updated_at DESC NULLS LAST,
                                id DESC
                        ) AS row_num
                    FROM mail_monitor_messages
                )
                DELETE FROM mail_monitor_messages messages
                USING ranked_duplicates duplicates
                WHERE messages.id = duplicates.id
                  AND duplicates.row_num > 1;
                """
            )
        )
        conn.execute(
            text(
                """
                DO $$
                DECLARE constraint_name TEXT;
                BEGIN
                    FOR constraint_name IN
                        SELECT con.conname
                        FROM pg_constraint con
                        JOIN pg_class rel ON rel.oid = con.conrelid
                        WHERE rel.relname = 'mail_monitor_messages'
                          AND con.contype = 'u'
                          AND pg_get_constraintdef(con.oid) ILIKE '%vps_id%'
                    LOOP
                        EXECUTE format(
                            'ALTER TABLE mail_monitor_messages DROP CONSTRAINT IF EXISTS %I',
                            constraint_name
                        );
                    END LOOP;
                END $$;
                """
            )
        )
        conn.execute(
            text(
                """
                DO $$
                DECLARE index_name TEXT;
                BEGIN
                    FOR index_name IN
                        SELECT indexname
                        FROM pg_indexes
                        WHERE tablename = 'mail_monitor_messages'
                          AND indexdef ILIKE '%vps_id%'
                    LOOP
                        EXECUTE format('DROP INDEX IF EXISTS %I', index_name);
                    END LOOP;
                END $$;
                """
            )
        )
        conn.execute(
            text(
                """
                DROP INDEX IF EXISTS idx_mail_monitor_messages_account_mailbox_message;
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE mail_monitor_messages
                DROP COLUMN IF EXISTS vps_id;
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_monitor_messages_account_mailbox_message
                ON mail_monitor_messages (account_email, mailbox, provider_message_id);
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_mail_monitor_messages_account_mailbox
                ON mail_monitor_messages (account_email, mailbox);
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
                DO $$
                DECLARE index_name TEXT;
                BEGIN
                    FOR index_name IN
                        SELECT indexname
                        FROM pg_indexes
                        WHERE tablename = 'mail_monitor_runs'
                          AND indexdef ILIKE '%vps_id%'
                    LOOP
                        EXECUTE format('DROP INDEX IF EXISTS %I', index_name);
                    END LOOP;
                END $$;
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE mail_monitor_runs
                DROP COLUMN IF EXISTS vps_id;
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_mail_monitor_runs_account_mailbox
                ON mail_monitor_runs (account_email, mailbox, run_finished_at DESC);
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
    channel_name = str(payload.get("channel_name") or run_payload.get("channel_name") or "").strip() or None

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
                WHERE account_email = :account_email
                  AND mailbox = :mailbox
                  AND provider_message_id IN :provider_message_ids
                """
            ).bindparams(bindparam("provider_message_ids", expanding=True))
            rows = conn.execute(
                existing_query,
                {
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
                ON CONFLICT (account_email, mailbox, provider_message_id)
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
        account_email=account_email,
        channel_name=channel_name,
        mailbox=mailbox,
        matched_messages=newly_matched_messages,
    )

    return _mail_record({
        "ok": True,
        "account_email": account_email,
        "mailbox": mailbox,
        "message_count": len(normalized_messages),
        "inserted_count": inserted_count,
        "updated_count": updated_count,
        "status": status,
    })


def _canonical_mail_messages_cte() -> str:
    return """
        WITH canonical_messages AS (
            SELECT DISTINCT ON (
                COALESCE(account_email, ''),
                COALESCE(mailbox, ''),
                COALESCE(provider_message_id, '')
            )
                id,
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
            ORDER BY
                COALESCE(account_email, ''),
                COALESCE(mailbox, ''),
                COALESCE(provider_message_id, ''),
                COALESCE(received_at, updated_at, last_seen_at, created_at) DESC NULLS LAST,
                updated_at DESC NULLS LAST,
                id DESC
        )
    """.strip()


def get_mail_overview(*, account_emails: Optional[list[str]] = None) -> dict[str, Any]:
    ensure_mail_tables()
    scope_clauses = []
    scope_params: dict[str, Any] = {}
    _append_account_email_scope(scope_clauses, scope_params, account_emails, column_name="account_email")
    scope_sql = f"WHERE {' AND '.join(scope_clauses)}" if scope_clauses else ""
    canonical_messages_cte = _canonical_mail_messages_cte()

    with engine.begin() as conn:
        rows_stmt = _bind_expanding_params(
            text(
                """
                {canonical_messages_cte},
                mailbox_keys AS (
                    SELECT DISTINCT account_email, mailbox FROM canonical_messages
                    {scope_sql}
                    UNION
                    SELECT DISTINCT account_email, mailbox FROM mail_monitor_runs
                    {scope_sql}
                ),
                message_stats AS (
                    SELECT
                        account_email,
                        mailbox,
                        MAX(provider) AS provider,
                        COUNT(*)::bigint AS total_messages,
                        COUNT(*) FILTER (WHERE COALESCE(seen, FALSE) = FALSE)::bigint AS unread_messages,
                        COUNT(*) FILTER (WHERE status = 'error')::bigint AS error_messages,
                        MAX(received_at) AS latest_received_at,
                        MAX(last_seen_at) AS latest_seen_at
                    FROM canonical_messages
                    GROUP BY account_email, mailbox
                ),
                latest_runs AS (
                    SELECT DISTINCT ON (account_email, mailbox)
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
                    ORDER BY account_email, mailbox, run_finished_at DESC, id DESC
                )
                SELECT
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
                  ON m.account_email = k.account_email AND m.mailbox = k.mailbox
                LEFT JOIN latest_runs r
                  ON r.account_email = k.account_email AND r.mailbox = k.mailbox
                ORDER BY COALESCE(r.run_finished_at, m.latest_seen_at, m.latest_received_at) DESC NULLS LAST,
                         k.account_email,
                         k.mailbox
                """
                .format(scope_sql=scope_sql, canonical_messages_cte=canonical_messages_cte)
            ),
            scope_params,
        )
        rows = conn.execute(rows_stmt, scope_params).mappings().all()

        summary_stmt = _bind_expanding_params(
            text(
                """
                {canonical_messages_cte},
                mailbox_keys AS (
                    SELECT DISTINCT account_email, mailbox FROM canonical_messages
                    {scope_sql}
                    UNION
                    SELECT DISTINCT account_email, mailbox FROM mail_monitor_runs
                    {scope_sql}
                ),
                message_stats AS (
                    SELECT
                        account_email,
                        mailbox,
                        COUNT(*)::bigint AS total_messages,
                        COUNT(*) FILTER (WHERE COALESCE(seen, FALSE) = FALSE)::bigint AS unread_messages
                    FROM canonical_messages
                    GROUP BY account_email, mailbox
                ),
                latest_runs AS (
                    SELECT DISTINCT ON (account_email, mailbox)
                        account_email,
                        mailbox,
                        status AS last_run_status
                    FROM mail_monitor_runs
                    ORDER BY account_email, mailbox, run_finished_at DESC, id DESC
                )
                SELECT
                    COUNT(DISTINCT NULLIF(k.account_email, ''))::bigint AS account_count,
                    COUNT(*)::bigint AS mailbox_count,
                    COALESCE(SUM(m.total_messages), 0)::bigint AS total_messages,
                    COALESCE(SUM(m.unread_messages), 0)::bigint AS unread_messages,
                    COUNT(*) FILTER (WHERE COALESCE(r.last_run_status, '') = 'error')::bigint AS error_messages
                FROM mailbox_keys k
                LEFT JOIN message_stats m
                  ON m.account_email = k.account_email AND m.mailbox = k.mailbox
                LEFT JOIN latest_runs r
                  ON r.account_email = k.account_email AND r.mailbox = k.mailbox
                """
                .format(scope_sql=scope_sql, canonical_messages_cte=canonical_messages_cte)
            ),
            scope_params,
        )
        summary_row = conn.execute(summary_stmt, scope_params).mappings().first()

    return {
        "summary": _mail_record(summary_row),
        "items": [_mail_record(row) for row in rows],
    }


def list_mail_messages(
    *,
    account_email: Optional[str] = None,
    account_emails: Optional[list[str]] = None,
    mailbox: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    per_account_limit: Optional[int] = None,
) -> dict[str, Any]:
    ensure_mail_tables()
    canonical_messages_cte = _canonical_mail_messages_cte()

    where_clauses = []
    params: dict[str, Any] = {
        "limit": max(1, min(int(limit or 100), 500)),
        "offset": max(0, int(offset or 0)),
    }
    normalized_per_account_limit = None
    if per_account_limit is not None:
        normalized_per_account_limit = max(1, min(int(per_account_limit), 500))
        params["per_account_limit"] = normalized_per_account_limit

    if account_email:
        where_clauses.append("account_email = :account_email")
        params["account_email"] = str(account_email).strip().lower()
    _append_account_email_scope(where_clauses, params, account_emails, column_name="account_email")
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
            rows_stmt = _bind_expanding_params(
                text(
                    f"""
                    {canonical_messages_cte},
                    filtered_messages AS (
                        SELECT
                            id,
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
                        FROM canonical_messages
                        {where_sql}
                    ),
                    ranked_messages AS (
                        SELECT
                            id,
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
                        FROM filtered_messages
                    )
                    SELECT
                        id,
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
            )
            rows = conn.execute(rows_stmt, params).mappings().all()

            total_stmt = _bind_expanding_params(
                text(
                    f"""
                    {canonical_messages_cte},
                    filtered_messages AS (
                        SELECT
                            id,
                            account_email,
                            received_at,
                            updated_at
                        FROM canonical_messages
                        {where_sql}
                    ),
                    ranked_messages AS (
                        SELECT
                            ROW_NUMBER() OVER (
                                PARTITION BY COALESCE(account_email, '')
                                ORDER BY COALESCE(received_at, updated_at) DESC NULLS LAST, id DESC
                            ) AS row_num
                        FROM filtered_messages
                    )
                    SELECT COUNT(*)::bigint AS total
                    FROM ranked_messages
                    WHERE row_num <= :per_account_limit
                    """
                ),
                {k: v for k, v in params.items() if k not in {"limit", "offset"}},
            )
            total_row = conn.execute(
                total_stmt,
                {k: v for k, v in params.items() if k not in {"limit", "offset"}},
            ).mappings().first()
        else:
            rows_stmt = _bind_expanding_params(
                text(
                    f"""
                    {canonical_messages_cte},
                    filtered_messages AS (
                        SELECT
                            id,
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
                        FROM canonical_messages
                        {where_sql}
                    )
                    SELECT
                        id,
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
                    FROM filtered_messages
                    ORDER BY COALESCE(received_at, updated_at) DESC NULLS LAST, id DESC
                    LIMIT :limit
                    OFFSET :offset
                    """
                ),
                params,
            )
            rows = conn.execute(rows_stmt, params).mappings().all()

            total_stmt = _bind_expanding_params(
                text(
                    f"""
                    {canonical_messages_cte},
                    filtered_messages AS (
                        SELECT id
                        FROM canonical_messages
                        {where_sql}
                    )
                    SELECT COUNT(*)::bigint AS total
                    FROM filtered_messages
                    """
                ),
                {k: v for k, v in params.items() if k not in {"limit", "offset"}},
            )
            total_row = conn.execute(
                total_stmt,
                {k: v for k, v in params.items() if k not in {"limit", "offset"}},
            ).mappings().first()

    return {
        "items": [_mail_record(row) for row in rows],
        "total": int((total_row or {}).get("total") or 0),
    }


def get_mail_message_detail(message_id: int, *, account_emails: Optional[list[str]] = None) -> Optional[dict[str, Any]]:
    ensure_mail_tables()
    where_clauses = ["id = :message_id"]
    params: dict[str, Any] = {"message_id": int(message_id)}
    _append_account_email_scope(where_clauses, params, account_emails, column_name="account_email")
    where_sql = f"WHERE {' AND '.join(where_clauses)}"

    with engine.begin() as conn:
        stmt = _bind_expanding_params(
            text(
                """
                SELECT
                    id,
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
                {where_sql}
                LIMIT 1
                """
                .format(where_sql=where_sql)
            ),
            params,
        )
        row = conn.execute(stmt, params).mappings().first()

    return _mail_record(row) if row else None


def delete_mail_account(account_email: str) -> dict[str, Any]:
    ensure_mail_tables()

    normalized_account_email = str(account_email or "").strip().lower()
    if not normalized_account_email:
        raise ValueError("Account email is required.")

    with engine.begin() as conn:
        message_deleted = conn.execute(
            text(
                """
                DELETE FROM mail_monitor_messages
                WHERE account_email = :account_email
                """
            ),
            {
                "account_email": normalized_account_email,
            },
        ).rowcount or 0

        run_deleted = conn.execute(
            text(
                """
                DELETE FROM mail_monitor_runs
                WHERE account_email = :account_email
                """
            ),
            {
                "account_email": normalized_account_email,
            },
        ).rowcount or 0

    return {
        "ok": True,
        "account_email": normalized_account_email,
        "deleted_messages": int(message_deleted),
        "deleted_runs": int(run_deleted),
    }


def list_mail_runs(
    *,
    account_email: Optional[str] = None,
    account_emails: Optional[list[str]] = None,
    mailbox: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    ensure_mail_tables()

    where_clauses = []
    params: dict[str, Any] = {
        "limit": max(1, min(int(limit or 50), 200)),
    }

    if account_email:
        where_clauses.append("account_email = :account_email")
        params["account_email"] = str(account_email).strip().lower()
    _append_account_email_scope(where_clauses, params, account_emails, column_name="account_email")
    if mailbox:
        where_clauses.append("mailbox = :mailbox")
        params["mailbox"] = mailbox

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    with engine.begin() as conn:
        stmt = _bind_expanding_params(
            text(
                f"""
                SELECT
                    id,
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
        )
        rows = conn.execute(stmt, params).mappings().all()

    return {"items": [_mail_record(row) for row in rows]}
