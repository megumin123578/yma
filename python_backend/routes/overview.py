# routes/overview.py
import json
import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from datetime import date
from sqlalchemy import text
from python_backend.db import engine
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user_optional
from python_backend.api.auth.database import get_db
from python_backend.api.auth.visibility import get_allowed_account_tags, get_hidden_account_tags
from python_backend.module_trafficsource import sanitize_filename
from python_backend.module_trafficsource import create_token_from_credentials
from python_backend.module_geography import fetch_geography, load_geography_from_postgres, save_geography_to_postgres

router = APIRouter(prefix="/api/video_overview", tags=["video_overview"])
CREDENTIALS_DIR = "./python_backend/credentials"



def query(sql: str, params=None):
    try:
        with engine.begin() as conn:
            rs = conn.execute(text(sql), params or {})
            return rs.mappings().all()
    except Exception as e:
        print("[DB ERROR]", e)
        return []


def _allowed_or_hidden_blocked(current_user, db, account_tag: str) -> bool:
    allowed = get_allowed_account_tags(db, current_user)
    if allowed is not None and account_tag not in allowed:
        return True
    if current_user:
        hidden = get_hidden_account_tags(db, current_user.id)
        hidden_all = hidden | {sanitize_filename(t) for t in hidden}
        if account_tag in hidden_all:
            return True
    return False


def _load_credential_path(account_tag: str) -> Optional[str]:
    if not account_tag:
        return None
    direct = os.path.join(CREDENTIALS_DIR, f"{account_tag}.json")
    if os.path.exists(direct):
        return direct
    safe = sanitize_filename(account_tag)
    if safe != account_tag:
        safe_path = os.path.join(CREDENTIALS_DIR, f"{safe}.json")
        if os.path.exists(safe_path):
            return safe_path
    return None


def _external_source(source: str) -> bool:
    if not source:
        return False
    upper = source.upper()
    if upper.startswith("EXT"):
        return True
    return "EXTERNAL" in upper


def _range_to_dates(range_key: str):
    from datetime import date, timedelta
    today = date.today()
    if range_key == "7d":
        return today - timedelta(days=6), today
    if range_key == "28d":
        return today - timedelta(days=27), today
    if range_key == "90d":
        return today - timedelta(days=89), today
    if range_key == "365d":
        return today - timedelta(days=364), today
    if range_key == "lifetime":
        return None, None
    return today - timedelta(days=27), today


class VideoFilter(BaseModel):
    accountTag: str
    startDate: Optional[date] = None
    endDate: Optional[date] = None


@router.get("/channels")
def list_channels(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    rows = query("""
        SELECT DISTINCT account_tag AS value, account_tag AS label
        FROM video_overview
        WHERE account_tag IS NOT NULL
        ORDER BY account_tag;
    """)

    allowed = get_allowed_account_tags(db, current_user)
    if allowed is not None:
        rows = [r for r in rows if r["value"] in allowed]
    if current_user:
        hidden = get_hidden_account_tags(db, current_user.id)
        hidden_all = hidden | {sanitize_filename(t) for t in hidden}
        rows = [r for r in rows if r["value"] not in hidden_all]

    return {"items": rows}

@router.get("/videos")
def list_videos(
    accountTag: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    allowed = get_allowed_account_tags(db, current_user)
    if allowed is not None and accountTag not in allowed:
        return []
    if _allowed_or_hidden_blocked(current_user, db, accountTag):
        return []
    rows = query("""
        SELECT
            account_tag,
            video_id,
            title,
            thumbnail,
            publish_date,
            views,
            likes,
            comments,
            dislikes,
            engaged_views,
            annotation_click_through_rate,
            annotation_close_rate,
            average_view_duration_seconds,
            shares,
            subscribers_gained,
            subscribers_lost,
            updated_at
        FROM video_overview
        WHERE account_tag = :tag
        ORDER BY publish_date DESC;
    """, {"tag": accountTag})

    return rows


@router.post("/list")
def list_filtered(
    req: VideoFilter,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    allowed = get_allowed_account_tags(db, current_user)
    if allowed is not None and req.accountTag not in allowed:
        return []
    if _allowed_or_hidden_blocked(current_user, db, req.accountTag):
        return []
    sql = """
        SELECT
            video_id, title, thumbnail, publish_date,
            views, likes, comments,
            dislikes, engaged_views,
            annotation_click_through_rate,
            annotation_close_rate,
            average_view_duration_seconds,
            shares, subscribers_gained, subscribers_lost,
            updated_at
        FROM video_overview
        WHERE account_tag = :tag
    """

    params = {"tag": req.accountTag}

    if req.startDate:
        sql += " AND publish_date >= :startDate"
        params["startDate"] = req.startDate

    if req.endDate:
        sql += " AND publish_date <= :endDate"
        params["endDate"] = req.endDate

    sql += " ORDER BY publish_date DESC"

    rows = query(sql, params)
    return rows



@router.get("/detail/{video_id}")
def video_detail(video_id: str):
    rows = query("""
        SELECT *
        FROM video_overview
        WHERE video_id = :vid
        LIMIT 1;
    """, {"vid": video_id})

    if not rows:
        raise HTTPException(404, "Video not found")

    return rows[0]



class AggRequest(BaseModel):
    accountTag: str
    start: date
    end: date


@router.post("/stats")
def overview_stats(
    req: AggRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    allowed = get_allowed_account_tags(db, current_user)
    if allowed is not None and req.accountTag not in allowed:
        return {}
    if _allowed_or_hidden_blocked(current_user, db, req.accountTag):
        return {}
    rows = query("""
        SELECT
            COUNT(*) AS totalVideos,
            SUM(views)::bigint AS views,
            SUM(likes)::bigint AS likes,
            SUM(comments)::bigint AS comments,
            SUM(dislikes)::bigint AS dislikes,
            SUM(engaged_views)::bigint AS engagedViews,
            SUM(subscribers_gained)::bigint AS subsGained,
            SUM(subscribers_lost)::bigint AS subsLost
        FROM video_overview
        WHERE account_tag = :tag
          AND publish_date BETWEEN :start AND :end
    """, {
        "tag": req.accountTag,
        "start": req.start,
        "end": req.end,
    })

    return rows[0] if rows else {}


@router.get("/top_videos")
def top_videos(
    accountTag: str,
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    if _allowed_or_hidden_blocked(current_user, db, accountTag):
        return []
    rows = query(
        """
        SELECT video_id, title, thumbnail, views
        FROM videos
        WHERE account_tag = :tag
        ORDER BY views DESC
        LIMIT :limit
        """,
        {"tag": accountTag, "limit": limit},
    )
    return rows


@router.get("/top_keywords")
def top_keywords(
    accountTag: str,
    range: str = Query("28d"),
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    if _allowed_or_hidden_blocked(current_user, db, accountTag):
        return []
    start_date, end_date = _range_to_dates(range)
    rows = query(
        """
        SELECT v.tags, COALESCE(SUM(s.views), 0) AS views
        FROM videos v
        JOIN video_daily_stats s
          ON s.video_id = v.video_id
        WHERE v.account_tag = :tag
          AND v.tags IS NOT NULL
          AND (:start_date IS NULL OR s.day >= :start_date)
          AND (:end_date IS NULL OR s.day <= :end_date)
        GROUP BY v.video_id, v.tags
        """,
        {"tag": accountTag, "start_date": start_date, "end_date": end_date},
    )
    totals = {}
    for row in rows:
        tags_raw = row.get("tags")
        try:
            tags = json.loads(tags_raw) if tags_raw else []
        except Exception:
            tags = []
        for tag in tags:
            key = str(tag).strip().lower()
            if not key:
                continue
            totals[key] = totals.get(key, 0) + int(row.get("views") or 0)
    ordered = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [{"keyword": k, "views": v} for k, v in ordered]


@router.get("/top_sources")
def top_sources(
    accountTag: str,
    range: str = Query("28d"),
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    if _allowed_or_hidden_blocked(current_user, db, accountTag):
        return []
    start_date, end_date = _range_to_dates(range)
    rows = query(
        """
        SELECT source, SUM(views)::bigint AS views
        FROM traffic_source_daily
        WHERE account_tag = :tag
          AND (:start_date IS NULL OR day >= :start_date)
          AND (:end_date IS NULL OR day <= :end_date)
        GROUP BY source
        ORDER BY views DESC
        LIMIT :limit
        """,
        {"tag": accountTag, "limit": limit, "start_date": start_date, "end_date": end_date},
    )
    return rows


@router.get("/top_external_sources")
def top_external_sources(
    accountTag: str,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    if _allowed_or_hidden_blocked(current_user, db, accountTag):
        return []
    rows = query(
        """
        SELECT source, SUM(views)::bigint AS views
        FROM traffic_source_daily
        WHERE account_tag = :tag
        GROUP BY source
        ORDER BY views DESC
        """,
        {"tag": accountTag},
    )
    filtered = [r for r in rows if _external_source(r.get("source"))]
    return filtered[:limit]


@router.get("/views_by_country")
def views_by_country(
    accountTag: str,
    range: str = Query("28d"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    if _allowed_or_hidden_blocked(current_user, db, accountTag):
        return {"rows": []}
    cred_path = _load_credential_path(accountTag)
    if not cred_path:
        return {"rows": []}
    if range == "7d":
        start_date, end_date = "7d", None
    elif range == "28d":
        start_date, end_date = "28d", None
    elif range == "90d":
        start_date, end_date = "90d", None
    elif range == "365d":
        start_date, end_date = "365d", None
    else:
        start_date, end_date = "28d", None
    creds = create_token_from_credentials(cred_path)
    if start_date in {"7d", "28d", "90d", "365d"}:
        from datetime import datetime, timedelta
        today = datetime.today().date()
        days = int(start_date[:-1])
        s = today - timedelta(days=days - 1)
        e = today
    else:
        s = start_date
        e = end_date
    try:
        rows = load_geography_from_postgres(accountTag, s.isoformat(), e.isoformat())
    except Exception as e:
        print(f"[WARN] Geography DB load failed: {e}")
        rows = []
    if not rows:
        rows = fetch_geography(creds, s.isoformat(), e.isoformat())
        try:
            save_geography_to_postgres(rows, accountTag, s.isoformat(), e.isoformat())
        except Exception as e:
            print(f"[WARN] Geography DB save failed: {e}")
    return {"rows": rows}


@router.get("/subscribers_timeseries")
def subscribers_timeseries(
    accountTag: str,
    days: int = Query(90, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    if _allowed_or_hidden_blocked(current_user, db, accountTag):
        return []
    from datetime import date, timedelta
    start_date = date.today() - timedelta(days=days - 1)
    rows = query(
        """
        SELECT day, subscribers_gained, subscribers_lost, views
        FROM channel_daily_metrics
        WHERE account_tag = :tag
          AND day >= :start_date
        ORDER BY day ASC
        """,
        {"tag": accountTag, "start_date": start_date},
    )
    return rows
