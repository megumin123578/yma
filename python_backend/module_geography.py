import os
from typing import Dict, List, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import create_engine, text

_PG_GEO_DDL = """
CREATE TABLE IF NOT EXISTS geography_country_metrics (
  account_tag TEXT NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  country TEXT NOT NULL,
  views BIGINT,
  estimated_minutes_watched BIGINT,
  engaged_views BIGINT,
  average_view_duration INTEGER,
  average_view_percentage DOUBLE PRECISION,
  updated_at TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY (account_tag, start_date, end_date, country)
);
CREATE INDEX IF NOT EXISTS idx_gcm_acct ON geography_country_metrics(account_tag);
CREATE INDEX IF NOT EXISTS idx_gcm_dates ON geography_country_metrics(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_gcm_country ON geography_country_metrics(country);
"""

_PG_GEO_UPSERT = """
INSERT INTO geography_country_metrics (
  account_tag,
  start_date,
  end_date,
  country,
  views,
  estimated_minutes_watched,
  engaged_views,
  average_view_duration,
  average_view_percentage,
  updated_at
)
VALUES (
  :account_tag,
  :start_date,
  :end_date,
  :country,
  :views,
  :estimated_minutes_watched,
  :engaged_views,
  :average_view_duration,
  :average_view_percentage,
  NOW()
)
ON CONFLICT (account_tag, start_date, end_date, country) DO UPDATE SET
  views = EXCLUDED.views,
  estimated_minutes_watched = EXCLUDED.estimated_minutes_watched,
  engaged_views = EXCLUDED.engaged_views,
  average_view_duration = EXCLUDED.average_view_duration,
  average_view_percentage = EXCLUDED.average_view_percentage,
  updated_at = NOW()
"""


def _chunks(seq: List[Dict], size: int):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def _get_pg_url(db_url: Optional[str] = None) -> str:
    pg_url = db_url or os.getenv("PG_URL")
    if not pg_url:
        raise ValueError("Missing PG_URL for geography storage.")
    return pg_url


def load_geography_from_postgres(
    account_tag: str,
    start_date: str,
    end_date: str,
    db_url: Optional[str] = None,
):
    engine = create_engine(_get_pg_url(db_url), pool_pre_ping=True, future=True)
    with engine.begin() as conn:
        for stmt in _PG_GEO_DDL.strip().split(";\n"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))
        rows = conn.execute(
            text(
                """
            SELECT
                country,
                views,
                estimated_minutes_watched AS "estimatedMinutesWatched",
                engaged_views AS "engagedViews",
                average_view_duration AS "averageViewDuration",
                average_view_percentage AS "averageViewPercentage"
            FROM geography_country_metrics
            WHERE account_tag = :tag
              AND start_date = :start_date
              AND end_date = :end_date
            ORDER BY views DESC;
            """
            ),
            {"tag": account_tag, "start_date": start_date, "end_date": end_date},
        ).mappings().all()
    return rows


def save_geography_to_postgres(
    rows: List[Dict],
    account_tag: str,
    start_date: str,
    end_date: str,
    db_url: Optional[str] = None,
    batch_size: int = 2000,
):
    if not rows:
        return
    engine = create_engine(_get_pg_url(db_url), pool_pre_ping=True, future=True)
    with engine.begin() as conn:
        for stmt in _PG_GEO_DDL.strip().split(";\n"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))
    payload = [
        {
            "account_tag": account_tag,
            "start_date": start_date,
            "end_date": end_date,
            "country": r.get("country"),
            "views": int(r.get("views") or 0),
            "estimated_minutes_watched": int(r.get("estimatedMinutesWatched") or 0),
            "engaged_views": int(r.get("engagedViews") or 0),
            "average_view_duration": int(r.get("averageViewDuration") or 0),
            "average_view_percentage": float(r.get("averageViewPercentage") or 0),
        }
        for r in rows
    ]
    with engine.begin() as conn:
        for chunk in _chunks(payload, batch_size):
            conn.execute(text(_PG_GEO_UPSERT), chunk)

def fetch_geography(credentials, start_date: str, end_date: str):
    yta = build("youtubeAnalytics", "v2", credentials=credentials)

    metrics = ",".join([
        "views",
        "estimatedMinutesWatched",
        "engagedViews",
        "averageViewDuration",
        "averageViewPercentage",
    ])

    q = {
        "ids": "channel==MINE",
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": "country",
        "metrics": metrics,
        "sort": "-views"
    }

    try:
        resp = yta.reports().query(**q).execute() or {}
    except HttpError as e:
        print("[ERROR] Geography query failed:", e)
        return []

    rows = resp.get("rows", [])
    headers = [h["name"] for h in resp.get("columnHeaders", [])]

    # Map column indexes
    idx = {h: i for i, h in enumerate(headers)}

    out = []
    for r in rows:
        out.append({
            "country": r[idx["country"]],
            "views": int(r[idx["views"]] or 0),
            "estimatedMinutesWatched": int(r[idx["estimatedMinutesWatched"]] or 0),
            "engagedViews": int(r[idx["engagedViews"]] or 0),
            "averageViewDuration": int(r[idx["averageViewDuration"]] or 0),
            "averageViewPercentage": float(r[idx["averageViewPercentage"]] or 0),
        })

    return out
