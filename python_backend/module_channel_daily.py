import os
from datetime import datetime, timedelta
from typing import List, Tuple

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import create_engine, text

try:
    from python_backend.module_trafficsource import sanitize_filename
except ModuleNotFoundError:
    from module_trafficsource import sanitize_filename


def _date_range_from_env() -> Tuple[str, str]:
    lookback_raw = os.getenv("CHANNEL_DAILY_LOOKBACK_DAYS", "").strip()
    if lookback_raw.isdigit():
        days = int(lookback_raw)
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=max(days - 1, 0))
        return start_date.isoformat(), end_date.isoformat()
    return "2005-02-14", datetime.utcnow().date().isoformat()


def _ensure_channel_daily_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS channel_daily_metrics (
                account_tag TEXT NOT NULL,
                day DATE NOT NULL,
                subscribers_gained BIGINT DEFAULT 0,
                subscribers_lost BIGINT DEFAULT 0,
                views BIGINT DEFAULT 0,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                PRIMARY KEY (account_tag, day)
            );
            """
        )
    )


def fetch_channel_daily(credentials) -> Tuple[List[dict], str, str]:
    start_date, end_date = _date_range_from_env()
    yta = build("youtubeAnalytics", "v2", credentials=credentials)
    query = {
        "ids": "channel==MINE",
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": "day",
        "metrics": "subscribersGained,subscribersLost,views",
        "sort": "day",
    }
    try:
        resp = yta.reports().query(**query).execute() or {}
    except HttpError as e:
        print(f"[WARN] channel daily query failed: {e}")
        return [], start_date, end_date

    rows = resp.get("rows") or []
    headers = [h["name"] for h in resp.get("columnHeaders", [])]
    idx = {h: i for i, h in enumerate(headers)}
    out = []
    for row in rows:
        out.append(
            {
                "day": row[idx["day"]],
                "subscribers_gained": int(row[idx["subscribersGained"]] or 0),
                "subscribers_lost": int(row[idx["subscribersLost"]] or 0),
                "views": int(row[idx["views"]] or 0),
            }
        )
    return out, start_date, end_date


def save_channel_daily(pg_url: str, account_tag: str, rows: List[dict]) -> None:
    if not rows:
        return
    safe_tag = sanitize_filename(account_tag)
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        _ensure_channel_daily_table(conn)
        for row in rows:
            conn.execute(
                text(
                    """
                    INSERT INTO channel_daily_metrics
                        (account_tag, day, subscribers_gained, subscribers_lost, views, updated_at)
                    VALUES
                        (:acct, :day, :gained, :lost, :views, NOW())
                    ON CONFLICT (account_tag, day)
                    DO UPDATE SET
                        subscribers_gained = EXCLUDED.subscribers_gained,
                        subscribers_lost = EXCLUDED.subscribers_lost,
                        views = EXCLUDED.views,
                        updated_at = NOW();
                    """
                ),
                {
                    "acct": safe_tag,
                    "day": row["day"],
                    "gained": row["subscribers_gained"],
                    "lost": row["subscribers_lost"],
                    "views": row["views"],
                },
            )


def run_channel_daily(credentials, account_tag: str, pg_url: str) -> None:
    rows, _start, _end = fetch_channel_daily(credentials)
    save_channel_daily(pg_url, account_tag, rows)
