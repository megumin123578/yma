import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import create_engine, text

from module_trafficsource import sanitize_filename


def _date_range_from_env() -> Tuple[str, str]:
    lookback_raw = os.getenv("AUDIENCE_LOOKBACK_DAYS", "").strip()
    if lookback_raw.isdigit():
        days = int(lookback_raw)
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=max(days - 1, 0))
        return start_date.isoformat(), end_date.isoformat()
    return "2005-02-14", datetime.utcnow().date().isoformat()


def _ensure_demographics_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS audience_demographics (
                account_tag TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                gender TEXT NOT NULL,
                age_group TEXT NOT NULL,
                viewer_percentage DOUBLE PRECISION NOT NULL,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                PRIMARY KEY (account_tag, start_date, end_date, gender, age_group)
            );
            """
        )
    )


def _ensure_retention_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS audience_retention (
                account_tag TEXT NOT NULL,
                video_id TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                elapsed_video_time_ratio DOUBLE PRECISION NOT NULL,
                audience_watch_ratio DOUBLE PRECISION,
                relative_retention_performance DOUBLE PRECISION,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                PRIMARY KEY (
                    account_tag,
                    video_id,
                    start_date,
                    end_date,
                    elapsed_video_time_ratio
                )
            );
            """
        )
    )


def fetch_demographics(credentials, channel_id: Optional[str] = None) -> Tuple[List[Dict], str, str]:
    start_date, end_date = _date_range_from_env()
    yta = build("youtubeAnalytics", "v2", credentials=credentials)
    ids = f"channel=={channel_id}" if channel_id else "channel==MINE"
    query = {
        "ids": ids,
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": "gender,ageGroup",
        "metrics": "viewerPercentage",
        "sort": "gender,ageGroup",
    }
    try:
        resp = yta.reports().query(**query).execute() or {}
    except HttpError as e:
        print(f"[WARN] demographics query failed: {e}")
        return [], start_date, end_date

    rows = resp.get("rows") or []
    headers = [h["name"] for h in resp.get("columnHeaders", [])]
    idx = {h: i for i, h in enumerate(headers)}

    out = []
    for row in rows:
        out.append(
            {
                "gender": row[idx["gender"]],
                "age_group": row[idx["ageGroup"]],
                "viewer_percentage": float(row[idx["viewerPercentage"]] or 0),
            }
        )
    return out, start_date, end_date


def save_demographics(pg_url: str, account_tag: str, rows: List[Dict], start_date: str, end_date: str) -> None:
    if not rows:
        return
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        _ensure_demographics_table(conn)
        for row in rows:
            conn.execute(
                text(
                    """
                    INSERT INTO audience_demographics
                        (account_tag, start_date, end_date, gender, age_group, viewer_percentage, updated_at)
                    VALUES
                        (:account_tag, :start_date, :end_date, :gender, :age_group, :viewer_percentage, NOW())
                    ON CONFLICT (account_tag, start_date, end_date, gender, age_group)
                    DO UPDATE SET
                        viewer_percentage = EXCLUDED.viewer_percentage,
                        updated_at = NOW();
                    """
                ),
                {
                    "account_tag": account_tag,
                    "start_date": start_date,
                    "end_date": end_date,
                    "gender": row["gender"],
                    "age_group": row["age_group"],
                    "viewer_percentage": row["viewer_percentage"],
                },
            )


def _list_video_ids(pg_url: str, account_tag: str) -> List[str]:
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT video_id FROM videos WHERE account_tag = :acct"),
            {"acct": account_tag},
        ).fetchall()
    return [r[0] for r in rows]


def fetch_retention(credentials, video_id: str, channel_id: Optional[str] = None) -> Tuple[List[Dict], str, str]:
    start_date, end_date = _date_range_from_env()
    yta = build("youtubeAnalytics", "v2", credentials=credentials)
    ids = f"channel=={channel_id}" if channel_id else "channel==MINE"
    query = {
        "ids": ids,
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": "elapsedVideoTimeRatio",
        "metrics": "audienceWatchRatio,relativeRetentionPerformance",
        "filters": f"video=={video_id}",
        "sort": "elapsedVideoTimeRatio",
    }
    try:
        resp = yta.reports().query(**query).execute() or {}
    except HttpError as e:
        print(f"[WARN] retention query failed for {video_id}: {e}")
        return [], start_date, end_date

    rows = resp.get("rows") or []
    headers = [h["name"] for h in resp.get("columnHeaders", [])]
    idx = {h: i for i, h in enumerate(headers)}

    out = []
    rel_idx = idx.get("relativeRetentionPerformance")
    for row in rows:
        rel_val = None
        if rel_idx is not None and row[rel_idx] is not None:
            try:
                rel_val = float(row[rel_idx] or 0)
            except Exception:
                rel_val = None
        out.append(
            {
                "elapsed_video_time_ratio": float(row[idx["elapsedVideoTimeRatio"]] or 0),
                "audience_watch_ratio": float(row[idx["audienceWatchRatio"]] or 0),
                "relative_retention_performance": rel_val,
            }
        )
    return out, start_date, end_date


def save_retention(
    pg_url: str,
    account_tag: str,
    video_id: str,
    rows: List[Dict],
    start_date: str,
    end_date: str,
) -> None:
    if not rows:
        return
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        _ensure_retention_table(conn)
        for row in rows:
            conn.execute(
                text(
                    """
                    INSERT INTO audience_retention
                        (account_tag, video_id, start_date, end_date, elapsed_video_time_ratio,
                         audience_watch_ratio, relative_retention_performance, updated_at)
                    VALUES
                        (:account_tag, :video_id, :start_date, :end_date, :elapsed_video_time_ratio,
                         :audience_watch_ratio, :relative_retention_performance, NOW())
                    ON CONFLICT (account_tag, video_id, start_date, end_date, elapsed_video_time_ratio)
                    DO UPDATE SET
                        audience_watch_ratio = EXCLUDED.audience_watch_ratio,
                        relative_retention_performance = EXCLUDED.relative_retention_performance,
                        updated_at = NOW();
                    """
                ),
                {
                    "account_tag": account_tag,
                    "video_id": video_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "elapsed_video_time_ratio": row["elapsed_video_time_ratio"],
                    "audience_watch_ratio": row["audience_watch_ratio"],
                    "relative_retention_performance": row["relative_retention_performance"],
                },
            )


def run_audience_analytics(
    credentials,
    account_tag: str,
    pg_url: str,
    channel_id: Optional[str] = None,
) -> None:
    safe_tag = sanitize_filename(account_tag)

    demo_rows, demo_start, demo_end = fetch_demographics(credentials, channel_id=channel_id)
    save_demographics(pg_url, safe_tag, demo_rows, demo_start, demo_end)

    video_ids = _list_video_ids(pg_url, safe_tag)
    if not video_ids:
        return

    for vid in video_ids:
        rows, start_date, end_date = fetch_retention(credentials, vid, channel_id=channel_id)
        save_retention(pg_url, safe_tag, vid, rows, start_date, end_date)
