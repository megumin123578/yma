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


REVENUE_METRIC_SPECS = {
    "estimatedRevenue": {
        "column": "estimated_revenue",
        "default": 0.0,
        "parser": float,
    },
    "estimatedAdRevenue": {
        "column": "ad_revenue",
        "default": 0.0,
        "parser": float,
    },
    "grossRevenue": {
        "column": "gross_revenue",
        "default": 0.0,
        "parser": float,
    },
    "estimatedRedPartnerRevenue": {
        "column": "estimated_red_partner_revenue",
        "default": 0.0,
        "parser": float,
    },
    "cpm": {
        "column": "cpm",
        "default": None,
        "parser": float,
    },
    "playbackBasedCpm": {
        "column": "playback_cpm",
        "default": None,
        "parser": float,
    },
    "monetizedPlaybacks": {
        "column": "monetized_playbacks",
        "default": 0,
        "parser": int,
    },
    "adImpressions": {
        "column": "ad_impressions",
        "default": 0,
        "parser": int,
    },
    "views": {
        "column": "views",
        "default": 0,
        "parser": int,
    },
}


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
                estimated_red_partner_revenue DOUBLE PRECISION DEFAULT 0,
                cpm DOUBLE PRECISION,
                playback_cpm DOUBLE PRECISION,
                rpm DOUBLE PRECISION,
                monetized_playbacks BIGINT DEFAULT 0,
                ad_impressions BIGINT DEFAULT 0,
                views BIGINT DEFAULT 0,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                PRIMARY KEY (account_tag, channel_id, day)
            );
            """
        )
    )
    conn.execute(
        text(
            "ALTER TABLE revenue_daily ADD COLUMN IF NOT EXISTS estimated_red_partner_revenue DOUBLE PRECISION DEFAULT 0;"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE revenue_daily ADD COLUMN IF NOT EXISTS ad_impressions BIGINT DEFAULT 0;"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE revenue_daily ADD COLUMN IF NOT EXISTS views BIGINT DEFAULT 0;"
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_rev_day ON revenue_daily(day);"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_rev_acct ON revenue_daily(account_tag);"))


def _empty_revenue_row(day_value: str) -> Dict:
    return {
        "day": day_value,
        "estimated_revenue": 0.0,
        "ad_revenue": 0.0,
        "gross_revenue": 0.0,
        "estimated_red_partner_revenue": 0.0,
        "cpm": None,
        "playback_cpm": None,
        "rpm": None,
        "monetized_playbacks": 0,
        "ad_impressions": 0,
        "views": 0,
    }


def _query_daily_metric(
    yta,
    base_query: Dict[str, str],
    metric_name: str,
) -> Optional[Dict[str, float]]:
    spec = REVENUE_METRIC_SPECS[metric_name]
    try:
        resp = yta.reports().query(
            **{**base_query, "metrics": metric_name}
        ).execute() or {}
    except HttpError as exc:
        print(f"[WARN] Revenue metric {metric_name} failed: {exc}")
        return None

    headers = [header["name"] for header in resp.get("columnHeaders", [])]
    idx = {name: i for i, name in enumerate(headers)}
    day_idx = idx.get("day")
    metric_idx = idx.get(metric_name)
    if day_idx is None or metric_idx is None:
        return {}

    out: Dict[str, float] = {}
    parser = spec["parser"]
    default = spec["default"]
    for row in resp.get("rows") or []:
        day_value = row[day_idx]
        try:
            out[day_value] = parser(row[metric_idx])
        except Exception:
            out[day_value] = default
    return out


def _fetch_revenue_rows(
    credentials,
    start_date: str,
    end_date: str,
    channel_id: Optional[str] = None,
) -> Tuple[List[Dict], str, str]:
    yta = build("youtubeAnalytics", "v2", credentials=credentials)
    ids = f"channel=={channel_id}" if channel_id else "channel==MINE"
    base_query = {
        "ids": ids,
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": "day",
        "sort": "day",
    }
    rows_by_day: Dict[str, Dict] = {}

    for metric_name, spec in REVENUE_METRIC_SPECS.items():
        metric_rows = _query_daily_metric(yta, base_query, metric_name)
        if metric_rows is None:
            continue
        for day_value, metric_value in metric_rows.items():
            row = rows_by_day.setdefault(day_value, _empty_revenue_row(day_value))
            row[spec["column"]] = metric_value

    rows = []
    for day_value in sorted(rows_by_day.keys()):
        row = rows_by_day[day_value]
        views = int(row.get("views") or 0)
        estimated_revenue = float(row.get("estimated_revenue") or 0.0)
        row["rpm"] = (estimated_revenue * 1000.0 / views) if views > 0 else None
        rows.append(row)
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
                        estimated_red_partner_revenue,
                        cpm,
                        playback_cpm,
                        rpm,
                        monetized_playbacks,
                        ad_impressions,
                        views,
                        updated_at
                    )
                    VALUES (
                        :account_tag,
                        :channel_id,
                        :day,
                        :estimated_revenue,
                        :ad_revenue,
                        :gross_revenue,
                        :estimated_red_partner_revenue,
                        :cpm,
                        :playback_cpm,
                        :rpm,
                        :monetized_playbacks,
                        :ad_impressions,
                        :views,
                        NOW()
                    )
                    ON CONFLICT (account_tag, channel_id, day) DO UPDATE SET
                        estimated_revenue = EXCLUDED.estimated_revenue,
                        ad_revenue = EXCLUDED.ad_revenue,
                        gross_revenue = EXCLUDED.gross_revenue,
                        estimated_red_partner_revenue = EXCLUDED.estimated_red_partner_revenue,
                        cpm = EXCLUDED.cpm,
                        playback_cpm = EXCLUDED.playback_cpm,
                        rpm = EXCLUDED.rpm,
                        monetized_playbacks = EXCLUDED.monetized_playbacks,
                        ad_impressions = EXCLUDED.ad_impressions,
                        views = EXCLUDED.views,
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
                    "estimated_red_partner_revenue": row["estimated_red_partner_revenue"],
                    "cpm": row["cpm"],
                    "playback_cpm": row["playback_cpm"],
                    "rpm": row["rpm"],
                    "monetized_playbacks": row["monetized_playbacks"],
                    "ad_impressions": row["ad_impressions"],
                    "views": row["views"],
                },
            )
    return len(rows), start_date, end_date


def run_revenue_for_account(account_tag: str, cred_path: str, pg_url: str, channel_id: Optional[str] = None):
    credentials = create_token_from_credentials(cred_path)
    return run_revenue_analytics(credentials, account_tag, pg_url, channel_id=channel_id)
