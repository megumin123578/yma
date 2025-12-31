import os
import sqlite3
import json
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


def _ensure_device_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS audience_devices (
                account_tag TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                device_type TEXT NOT NULL,
                viewer_percentage DOUBLE PRECISION NOT NULL,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                PRIMARY KEY (account_tag, start_date, end_date, device_type)
            );
            """
        )
    )


def _ensure_viewer_type_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS audience_viewer_types (
                account_tag TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                viewer_type TEXT NOT NULL,
                viewer_percentage DOUBLE PRECISION NOT NULL,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                PRIMARY KEY (account_tag, start_date, end_date, viewer_type)
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


def _progress_path(account_tag: str) -> str:
    progress_dir = os.path.join("python_backend", "progress")
    os.makedirs(progress_dir, exist_ok=True)
    return os.path.join(progress_dir, f"{account_tag}.json")


def _write_progress(
    account_tag: str,
    stage: str,
    percent: int,
    status: str,
    message: str = "",
) -> None:
    payload = {
        "account_tag": account_tag,
        "stage": stage,
        "percent": percent,
        "status": status,
        "message": message,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    try:
        with open(_progress_path(account_tag), "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception:
        pass


def _auth_db_path() -> str:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.getenv("AUTH_DB_PATH", os.path.join(repo_root, "auth.db"))


def _stop_requested() -> bool:
    run_id = os.getenv("SCHEDULE_RUN_ID")
    if not run_id:
        return False
    try:
        conn = sqlite3.connect(_auth_db_path())
        cur = conn.cursor()
        cur.execute(
            "SELECT status FROM user_schedule_runs WHERE id = ?",
            (int(run_id),),
        )
        row = cur.fetchone()
        conn.close()
        return bool(row and row[0] in {"stopping", "stopped", "canceled"})
    except Exception:
        return False


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


def fetch_device_types(credentials, channel_id: Optional[str] = None) -> Tuple[List[Dict], str, str]:
    start_date, end_date = _date_range_from_env()
    yta = build("youtubeAnalytics", "v2", credentials=credentials)
    ids = f"channel=={channel_id}" if channel_id else "channel==MINE"
    query = {
        "ids": ids,
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": "deviceType",
        "metrics": "views",
        "sort": "-views",
    }
    try:
        resp = yta.reports().query(**query).execute() or {}
    except HttpError as e:
        print(f"[WARN] device type query failed: {e}")
        return [], start_date, end_date

    rows = resp.get("rows") or []
    headers = [h["name"] for h in resp.get("columnHeaders", [])]
    idx = {h: i for i, h in enumerate(headers)}

    total_views = 0
    for row in rows:
        try:
            total_views += int(row[idx["views"]] or 0)
        except Exception:
            continue

    out = []
    for row in rows:
        try:
            views = int(row[idx["views"]] or 0)
        except Exception:
            views = 0
        viewer_percentage = (views / total_views * 100) if total_views else 0
        out.append(
            {
                "device_type": row[idx["deviceType"]],
                "viewer_percentage": float(viewer_percentage),
            }
        )
    return out, start_date, end_date


def save_device_types(pg_url: str, account_tag: str, rows: List[Dict], start_date: str, end_date: str) -> None:
    if not rows:
        return
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        _ensure_device_table(conn)
        for row in rows:
            conn.execute(
                text(
                    """
                    INSERT INTO audience_devices
                        (account_tag, start_date, end_date, device_type, viewer_percentage, updated_at)
                    VALUES
                        (:account_tag, :start_date, :end_date, :device_type, :viewer_percentage, NOW())
                    ON CONFLICT (account_tag, start_date, end_date, device_type)
                    DO UPDATE SET
                        viewer_percentage = EXCLUDED.viewer_percentage,
                        updated_at = NOW();
                    """
                ),
                {
                    "account_tag": account_tag,
                    "start_date": start_date,
                    "end_date": end_date,
                    "device_type": row["device_type"],
                    "viewer_percentage": row["viewer_percentage"],
                },
            )


def fetch_viewer_types(credentials, channel_id: Optional[str] = None) -> Tuple[List[Dict], str, str]:
    start_date, end_date = _date_range_from_env()
    yta = build("youtubeAnalytics", "v2", credentials=credentials)
    ids = f"channel=={channel_id}" if channel_id else "channel==MINE"
    query = {
        "ids": ids,
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": "subscribedStatus",
        "metrics": "views",
        "sort": "-views",
    }
    try:
        resp = yta.reports().query(**query).execute() or {}
    except HttpError as e:
        print(f"[WARN] viewer type query failed: {e}")
        return [], start_date, end_date

    rows = resp.get("rows") or []
    headers = [h["name"] for h in resp.get("columnHeaders", [])]
    idx = {h: i for i, h in enumerate(headers)}

    total_views = 0
    for row in rows:
        try:
            total_views += int(row[idx["views"]] or 0)
        except Exception:
            continue

    out = []
    for row in rows:
        try:
            views = int(row[idx["views"]] or 0)
        except Exception:
            views = 0
        viewer_percentage = (views / total_views * 100) if total_views else 0
        out.append(
            {
                "viewer_type": row[idx["subscribedStatus"]],
                "viewer_percentage": float(viewer_percentage),
            }
        )
    return out, start_date, end_date


def save_viewer_types(pg_url: str, account_tag: str, rows: List[Dict], start_date: str, end_date: str) -> None:
    if not rows:
        return
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        _ensure_viewer_type_table(conn)
        for row in rows:
            conn.execute(
                text(
                    """
                    INSERT INTO audience_viewer_types
                        (account_tag, start_date, end_date, viewer_type, viewer_percentage, updated_at)
                    VALUES
                        (:account_tag, :start_date, :end_date, :viewer_type, :viewer_percentage, NOW())
                    ON CONFLICT (account_tag, start_date, end_date, viewer_type)
                    DO UPDATE SET
                        viewer_percentage = EXCLUDED.viewer_percentage,
                        updated_at = NOW();
                    """
                ),
                {
                    "account_tag": account_tag,
                    "start_date": start_date,
                    "end_date": end_date,
                    "viewer_type": row["viewer_type"],
                    "viewer_percentage": row["viewer_percentage"],
                },
            )


def _list_video_ids(pg_url: str, account_tag: str) -> List[str]:
    max_videos = int(os.getenv("AUDIENCE_MAX_VIDEOS", "10"))
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT video_id
                FROM videos
                WHERE account_tag = :acct
                ORDER BY published_at DESC NULLS LAST
                LIMIT :limit
                """
            ),
            {"acct": account_tag, "limit": max_videos},
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

    print(f"[INFO] [audience] Fetching demographics for {safe_tag}...")
    demo_rows, demo_start, demo_end = fetch_demographics(credentials, channel_id=channel_id)
    print(f"[INFO] [audience] Demographics rows: {len(demo_rows)} ({demo_start} -> {demo_end})")
    save_demographics(pg_url, safe_tag, demo_rows, demo_start, demo_end)

    device_rows, device_start, device_end = fetch_device_types(credentials, channel_id=channel_id)
    print(f"[INFO] [audience] Device rows: {len(device_rows)} ({device_start} -> {device_end})")
    save_device_types(pg_url, safe_tag, device_rows, device_start, device_end)

    viewer_rows, viewer_start, viewer_end = fetch_viewer_types(credentials, channel_id=channel_id)
    print(f"[INFO] [audience] Viewer type rows: {len(viewer_rows)} ({viewer_start} -> {viewer_end})")
    save_viewer_types(pg_url, safe_tag, viewer_rows, viewer_start, viewer_end)


    video_ids = _list_video_ids(pg_url, safe_tag)
    if not video_ids:
        print(f"[INFO] [audience] No videos found for {safe_tag}.")
        return

    total_videos = len(video_ids)
    print(f"[INFO] [audience] Fetching retention for {total_videos} videos...")
    for idx, vid in enumerate(video_ids, start=1):
        if _stop_requested():
            raise RuntimeError("Stop requested")
        if total_videos > 0:
            percent = 80 + int((idx / total_videos) * 9)
            _write_progress(
                account_tag,
                "audience",
                percent,
                "running",
                f"Audience {idx}/{total_videos}",
            )
        print(f"[INFO] [audience] Retention video: {vid}")
        rows, start_date, end_date = fetch_retention(credentials, vid, channel_id=channel_id)
        save_retention(pg_url, safe_tag, vid, rows, start_date, end_date)
    print(f"[INFO] [audience] Retention saved for {len(video_ids)} videos.")
