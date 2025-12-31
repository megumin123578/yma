import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import create_engine, text

try:
    from python_backend.module_trafficsource import create_token_from_credentials
except ModuleNotFoundError:
    from module_trafficsource import create_token_from_credentials


def _date_range_from_env() -> Tuple[str, str]:
    lookback_raw = os.getenv("REVENUE_LOOKBACK_DAYS", "").strip()
    if lookback_raw.isdigit():
        days = int(lookback_raw)
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=max(days - 1, 0))
        return start_date.isoformat(), end_date.isoformat()
    return "2005-02-14", datetime.utcnow().date().isoformat()


def _ensure_revenue_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS revenue_daily (
                account_tag TEXT NOT NULL,
                channel_id TEXT NOT NULL DEFAULT '',
                day DATE NOT NULL,
                estimated_revenue DOUBLE PRECISION DEFAULT 0,
                ad_revenue DOUBLE PRECISION DEFAULT 0,
                gross_revenue DOUBLE PRECISION DEFAULT 0,
                cpm DOUBLE PRECISION,
                playback_cpm DOUBLE PRECISION,
                rpm DOUBLE PRECISION,
                monetized_playbacks BIGINT DEFAULT 0,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                PRIMARY KEY (account_tag, channel_id, day)
            );
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_rev_day ON revenue_daily(day);"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_rev_acct ON revenue_daily(account_tag);"))


def _fetch_revenue_rows(
    credentials,
    start_date: str,
    end_date: str,
    channel_id: Optional[str] = None,
) -> Tuple[List[Dict], str, str]:
    yta = build("youtubeAnalytics", "v2", credentials=credentials)
    ids = f"channel=={channel_id}" if channel_id else "channel==MINE"
    metrics = [
        "estimatedRevenue",
        "adRevenue",
        "grossRevenue",
        "cpm",
        "playbackBasedCpm",
        "rpm",
        "monetizedPlaybacks",
    ]
    base_query = {
        "ids": ids,
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": "day",
        "sort": "day",
    }
    try:
        resp = yta.reports().query(**{**base_query, "metrics": ",".join(metrics)}).execute() or {}
    except HttpError:
        resp = yta.reports().query(
            **{**base_query, "metrics": "estimatedRevenue"}
        ).execute() or {}
        metrics = ["estimatedRevenue"]

    headers = [h["name"] for h in resp.get("columnHeaders", [])]
    idx = {name: i for i, name in enumerate(headers)}
    rows = []
    for row in resp.get("rows") or []:
        def get_value(key: str, default=0):
            i = idx.get(key)
            if i is None:
                return default
            try:
                return float(row[i])
            except Exception:
                return default

        def get_int(key: str, default=0):
            i = idx.get(key)
            if i is None:
                return default
            try:
                return int(row[i])
            except Exception:
                return default

        rows.append(
            {
                "day": row[idx["day"]],
                "estimated_revenue": get_value("estimatedRevenue", 0),
                "ad_revenue": get_value("adRevenue", 0),
                "gross_revenue": get_value("grossRevenue", 0),
                "cpm": get_value("cpm", None),
                "playback_cpm": get_value("playbackBasedCpm", None),
                "rpm": get_value("rpm", None),
                "monetized_playbacks": get_int("monetizedPlaybacks", 0),
            }
        )
    return rows, start_date, end_date


def run_revenue_analytics(
    credentials,
    account_tag: str,
    pg_url: str,
    channel_id: Optional[str] = None,
) -> Tuple[int, str, str]:
    start_date, end_date = _date_range_from_env()
    rows, start_date, end_date = _fetch_revenue_rows(
        credentials,
        start_date,
        end_date,
        channel_id=channel_id,
    )
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        _ensure_revenue_table(conn)
        for row in rows:
            conn.execute(
                text(
                    """
                    INSERT INTO revenue_daily (
                        account_tag,
                        channel_id,
                        day,
                        estimated_revenue,
                        ad_revenue,
                        gross_revenue,
                        cpm,
                        playback_cpm,
                        rpm,
                        monetized_playbacks,
                        updated_at
                    )
                    VALUES (
                        :account_tag,
                        :channel_id,
                        :day,
                        :estimated_revenue,
                        :ad_revenue,
                        :gross_revenue,
                        :cpm,
                        :playback_cpm,
                        :rpm,
                        :monetized_playbacks,
                        NOW()
                    )
                    ON CONFLICT (account_tag, channel_id, day) DO UPDATE SET
                        estimated_revenue = EXCLUDED.estimated_revenue,
                        ad_revenue = EXCLUDED.ad_revenue,
                        gross_revenue = EXCLUDED.gross_revenue,
                        cpm = EXCLUDED.cpm,
                        playback_cpm = EXCLUDED.playback_cpm,
                        rpm = EXCLUDED.rpm,
                        monetized_playbacks = EXCLUDED.monetized_playbacks,
                        updated_at = NOW();
                    """
                ),
                {
                    "account_tag": account_tag,
                    "channel_id": channel_id or "",
                    "day": row["day"],
                    "estimated_revenue": row["estimated_revenue"],
                    "ad_revenue": row["ad_revenue"],
                    "gross_revenue": row["gross_revenue"],
                    "cpm": row["cpm"],
                    "playback_cpm": row["playback_cpm"],
                    "rpm": row["rpm"],
                    "monetized_playbacks": row["monetized_playbacks"],
                },
            )
    return len(rows), start_date, end_date


def run_revenue_for_account(account_tag: str, cred_path: str, pg_url: str, channel_id: Optional[str] = None):
    credentials = create_token_from_credentials(cred_path)
    return run_revenue_analytics(credentials, account_tag, pg_url, channel_id=channel_id)
