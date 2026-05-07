# routes/overview.py
import json
import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from datetime import date, datetime, timedelta
from sqlalchemy import text
from python_backend.db import engine
from sqlalchemy.orm import Session
from googleapiclient.discovery import build

from python_backend.api.auth.auth_utils import get_current_user_optional
from python_backend.api.auth.database import get_db
from python_backend.api.auth.visibility import get_allowed_account_tags, get_hidden_account_tags
from python_backend.api.auth.models import LiveCounterSnapshot, SAIGON_TZ, UserCredential
from python_backend.module_trafficsource import sanitize_filename
from python_backend.module_trafficsource import create_token_from_credentials
from python_backend.module_geography import fetch_geography, load_geography_from_postgres, save_geography_to_postgres
from python_backend.module_channel_daily import _ensure_channel_daily_table
from python_backend.token_store import token_exists

router = APIRouter(prefix="/api/video_overview", tags=["video_overview"])



def query(sql: str, params=None):
    try:
        with engine.begin() as conn:
            rs = conn.execute(text(sql), params or {})
            return rs.mappings().all()
    except Exception as e:
        print("[DB ERROR]", e)
        return []


def scalar(sql: str, params=None):
    try:
        with engine.begin() as conn:
            return conn.execute(text(sql), params or {}).scalar()
    except Exception as e:
        print("[DB ERROR]", e)
        return None


def _allowed_or_hidden_blocked(current_user, db, account_tag: str) -> bool:
    allowed = get_allowed_account_tags(db, current_user)
    if allowed is not None and account_tag not in allowed:
        return True
    return False


def _now_saigon_naive() -> datetime:
    return datetime.now(SAIGON_TZ).replace(tzinfo=None)


def _serialize_saigon_naive(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=SAIGON_TZ)
    return value.isoformat()


def _resolve_live_counter_window(
    hours: Optional[int],
    minutes: Optional[int],
) -> tuple[timedelta, str, int]:
    if hours is not None and minutes is not None:
        raise HTTPException(
            status_code=400,
            detail="Use either hours or minutes, not both",
        )
    if hours is None and minutes is None:
        hours = 24
    if hours is not None:
        return timedelta(hours=hours), "hours", hours
    return timedelta(minutes=minutes), "minutes", minutes


def _load_credential_path(account_tag: str) -> Optional[str]:
    if not account_tag:
        return None
    if token_exists(account_tag):
        return account_tag
    safe = sanitize_filename(account_tag)
    if safe != account_tag:
        if token_exists(safe):
            return safe
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
    if range_key == "14d":
        return today - timedelta(days=13), today
    if range_key == "28d":
        return today - timedelta(days=27), today
    if range_key == "90d":
        return today - timedelta(days=89), today
    if range_key == "180d":
        return today - timedelta(days=179), today
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

    rows = [r for r in rows if _load_credential_path(r["value"])]

    tags = [r["value"] for r in rows]
    label_map = {}
    if tags:
        creds = (
            db.query(UserCredential.account_tag, UserCredential.selected_channel_title)
            .filter(UserCredential.account_tag.in_(tags))
            .all()
        )
        label_map = {
            sanitize_filename(row.account_tag): (row.selected_channel_title or row.account_tag)
            for row in creds
            if row.account_tag
        }
    rows = [
        {"value": r["value"], "label": label_map.get(r["value"], r["label"])}
        for r in rows
    ]

    return {"items": rows}

@router.get("/videos")
def list_videos(
    accountTag: str,
    range: str = Query("28d"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    allowed = get_allowed_account_tags(db, current_user)
    if allowed is not None and accountTag not in allowed:
        return []
    if _allowed_or_hidden_blocked(current_user, db, accountTag):
        return []
    has_videos_table = bool(scalar("SELECT to_regclass('public.videos') IS NOT NULL"))
    has_thumbnail_daily_table = bool(
        scalar("SELECT to_regclass('public.video_thumbnail_daily') IS NOT NULL")
    )
    start_date, end_date = _range_to_dates(range)
    sql = """
        SELECT
            vo.account_tag,
            vo.video_id,
            vo.title,
            vo.thumbnail,
            vo.publish_date,
            vo.views,
            vo.likes,
            vo.comments,
            vo.dislikes,
            vo.engaged_views,
            NULL::DOUBLE PRECISION AS thumbnail_ctr,
            vo.annotation_click_through_rate,
            vo.annotation_close_rate,
            vo.average_view_duration_seconds,
            vo.shares,
            vo.subscribers_gained,
            vo.subscribers_lost,
            vo.updated_at
        FROM video_overview vo
        WHERE vo.account_tag = :tag
        ORDER BY vo.publish_date DESC;
    """
    params = {"tag": accountTag}
    if has_videos_table and has_thumbnail_daily_table:
        sql = """
            SELECT
                vo.account_tag,
                vo.video_id,
                vo.title,
                vo.thumbnail,
                COALESCE(vo.publish_date, v.published_at::text) AS publish_date,
                GREATEST(COALESCE(vo.views, 0), COALESCE(v.views, 0)) AS views,
                GREATEST(COALESCE(vo.likes, 0), COALESCE(v.likes, 0)) AS likes,
                GREATEST(COALESCE(vo.comments, 0), COALESCE(v.comments, 0)) AS comments,
                vo.dislikes,
                vo.engaged_views,
                CASE
                    WHEN tr.thumbnail_impressions IS NOT NULL
                        THEN tr.thumbnail_ctr * 100.0
                    ELSE v.ctr
                END AS thumbnail_ctr,
                vo.annotation_click_through_rate,
                vo.annotation_close_rate,
                vo.average_view_duration_seconds,
                vo.shares,
                vo.subscribers_gained,
                vo.subscribers_lost,
                vo.updated_at
            FROM video_overview vo
            LEFT JOIN videos v
                ON v.account_tag = vo.account_tag
               AND v.video_id = vo.video_id
            LEFT JOIN (
                SELECT
                    account_tag,
                    video_id,
                    SUM(thumbnail_impressions) AS thumbnail_impressions,
                    CASE
                        WHEN SUM(thumbnail_impressions) > 0
                            THEN SUM(COALESCE(thumbnail_ctr, 0) * thumbnail_impressions)
                                 / SUM(thumbnail_impressions)
                        ELSE NULL
                    END AS thumbnail_ctr
                FROM video_thumbnail_daily
                WHERE (:start_date IS NULL OR day >= :start_date)
                  AND (:end_date IS NULL OR day <= :end_date)
                GROUP BY account_tag, video_id
            ) tr
                ON tr.account_tag = vo.account_tag
               AND tr.video_id = vo.video_id
            WHERE vo.account_tag = :tag
            ORDER BY publish_date DESC;
        """
        params.update({"start_date": start_date, "end_date": end_date})
    elif has_videos_table:
        sql = """
            SELECT
                vo.account_tag,
                vo.video_id,
                vo.title,
                vo.thumbnail,
                COALESCE(vo.publish_date, v.published_at::text) AS publish_date,
                GREATEST(COALESCE(vo.views, 0), COALESCE(v.views, 0)) AS views,
                GREATEST(COALESCE(vo.likes, 0), COALESCE(v.likes, 0)) AS likes,
                GREATEST(COALESCE(vo.comments, 0), COALESCE(v.comments, 0)) AS comments,
                vo.dislikes,
                vo.engaged_views,
                v.ctr AS thumbnail_ctr,
                vo.annotation_click_through_rate,
                vo.annotation_close_rate,
                vo.average_view_duration_seconds,
                vo.shares,
                vo.subscribers_gained,
                vo.subscribers_lost,
                vo.updated_at
            FROM video_overview vo
            LEFT JOIN videos v
                ON v.account_tag = vo.account_tag
               AND v.video_id = vo.video_id
            WHERE vo.account_tag = :tag
            ORDER BY publish_date DESC;
        """
    rows = query(sql, params)

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
    elif range == "14d":
        start_date, end_date = "14d", None
    elif range == "28d":
        start_date, end_date = "28d", None
    elif range == "90d":
        start_date, end_date = "90d", None
    elif range == "180d":
        start_date, end_date = "180d", None
    elif range == "365d":
        start_date, end_date = "365d", None
    else:
        start_date, end_date = "28d", None
    creds = create_token_from_credentials(cred_path)
    if start_date in {"7d", "14d", "28d", "90d", "180d", "365d"}:
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
    try:
        with engine.begin() as conn:
            _ensure_channel_daily_table(conn)
    except Exception as e:
        print("[DB ERROR]", e)
        return []
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


@router.get("/live_counters")
def live_counters(
    accountTag: str,
    limit: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    if _allowed_or_hidden_blocked(current_user, db, accountTag):
        return {
            "channel": None,
            "videos": [],
            "refreshedAt": None,
        }

    cred_row = (
        db.query(UserCredential)
        .filter(UserCredential.account_tag == accountTag)
        .order_by(UserCredential.updated_at.desc())
        .first()
    )
    if not cred_row:
        raise HTTPException(status_code=404, detail="Channel credentials not found")

    cred_path = _load_credential_path(accountTag)
    if not cred_path:
        raise HTTPException(status_code=404, detail="Token file not found")

    credentials = create_token_from_credentials(cred_path)
    youtube = build("youtube", "v3", credentials=credentials)

    channel_query = {"part": "snippet,statistics"}
    if cred_row.selected_channel_id:
        channel_query["id"] = cred_row.selected_channel_id
    else:
        channel_query["mine"] = True

    channel_resp = youtube.channels().list(**channel_query).execute() or {}
    channel_items = channel_resp.get("items") or []
    if not channel_items:
        raise HTTPException(status_code=404, detail="Channel not found")

    channel_item = channel_items[0]
    channel_snippet = channel_item.get("snippet", {}) or {}
    channel_stats = channel_item.get("statistics", {}) or {}

    rows = query(
        """
        SELECT video_id, title, thumbnail, publish_date
        FROM video_overview
        WHERE account_tag = :tag
          AND video_id IS NOT NULL
          AND video_id != ''
        ORDER BY publish_date DESC
        LIMIT :limit
        """,
        {"tag": accountTag, "limit": limit},
    )
    recent_videos = []
    video_ids = [str(row.get("video_id") or "").strip() for row in rows if row.get("video_id")]

    if video_ids:
        videos_resp = youtube.videos().list(
            part="snippet,statistics",
            id=",".join(video_ids),
        ).execute() or {}
        by_id = {
            item.get("id"): item
            for item in (videos_resp.get("items") or [])
            if item.get("id")
        }

        for row in rows:
            video_id = str(row.get("video_id") or "").strip()
            item = by_id.get(video_id, {})
            stats = item.get("statistics", {}) or {}
            snippet = item.get("snippet", {}) or {}
            thumbs = snippet.get("thumbnails", {}) or {}
            recent_videos.append(
                {
                    "videoId": video_id,
                    "title": snippet.get("title") or row.get("title") or video_id,
                    "thumbnail": (
                        (thumbs.get("medium") or {}).get("url")
                        or (thumbs.get("default") or {}).get("url")
                        or row.get("thumbnail")
                        or ""
                    ),
                    "publishedAt": snippet.get("publishedAt") or row.get("publish_date"),
                    "viewCount": int(stats.get("viewCount", 0) or 0),
                    "likeCount": int(stats.get("likeCount", 0) or 0),
                    "commentCount": int(stats.get("commentCount", 0) or 0),
                }
            )

    return {
        "channel": {
            "id": channel_item.get("id", ""),
            "title": channel_snippet.get("title") or cred_row.selected_channel_title or accountTag,
            "thumbnail": (
                ((channel_snippet.get("thumbnails") or {}).get("medium") or {}).get("url")
                or cred_row.selected_channel_avatar
                or ""
            ),
            "subscriberCount": int(channel_stats.get("subscriberCount", 0) or 0),
            "viewCount": int(channel_stats.get("viewCount", 0) or 0),
            "videoCount": int(channel_stats.get("videoCount", 0) or 0),
        },
        "videos": recent_videos,
        "refreshedAt": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/live_counters/history")
def live_counters_history(
    accountTag: str,
    hours: Optional[int] = Query(None, ge=1, le=168),
    minutes: Optional[int] = Query(None, ge=1, le=10080),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    if _allowed_or_hidden_blocked(current_user, db, accountTag):
        return {"rows": []}

    window_delta, window_unit, window_value = _resolve_live_counter_window(hours, minutes)
    cutoff = _now_saigon_naive() - window_delta
    rows = (
        db.query(LiveCounterSnapshot)
        .filter(
            LiveCounterSnapshot.account_tag == accountTag,
            LiveCounterSnapshot.captured_at >= cutoff,
        )
        .order_by(LiveCounterSnapshot.captured_at.asc())
        .all()
    )
    normalized_rows = []
    max_view_count = None
    for row in rows:
        view_count = int(row.view_count or 0)
        if max_view_count is None:
            max_view_count = view_count
        else:
            max_view_count = max(max_view_count, view_count)
        normalized_rows.append(
            {
                "capturedAt": _serialize_saigon_naive(row.captured_at),
                "subscriberCount": row.subscriber_count,
                "viewCount": max_view_count,
                "videoCount": row.video_count,
            }
        )
    return {
        "window": {
            "unit": window_unit,
            "value": window_value,
            "minutes": int(window_delta.total_seconds() // 60),
        },
        "rows": normalized_rows
    }


@router.get("/live_counters/summary")
def live_counters_summary(
    accountTag: str,
    hours: Optional[int] = Query(None, ge=1, le=168),
    minutes: Optional[int] = Query(None, ge=1, le=10080),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    if _allowed_or_hidden_blocked(current_user, db, accountTag):
        return {
            "window": None,
            "windowViews": None,
            "currentViewCount": None,
            "baselineViewCount": None,
            "capturedAt": None,
            "baselineCapturedAt": None,
            "sampleCount": 0,
            "hasData": False,
            "hasFullWindow": False,
        }

    window_delta, window_unit, window_value = _resolve_live_counter_window(hours, minutes)
    cutoff = _now_saigon_naive() - window_delta

    latest_row = (
        db.query(LiveCounterSnapshot)
        .filter(LiveCounterSnapshot.account_tag == accountTag)
        .order_by(LiveCounterSnapshot.captured_at.desc(), LiveCounterSnapshot.id.desc())
        .first()
    )
    if not latest_row or not latest_row.captured_at or latest_row.captured_at < cutoff:
        return {
            "window": {
                "unit": window_unit,
                "value": window_value,
                "minutes": int(window_delta.total_seconds() // 60),
            },
            "windowViews": None,
            "currentViewCount": int(latest_row.view_count or 0) if latest_row else None,
            "baselineViewCount": None,
            "capturedAt": _serialize_saigon_naive(latest_row.captured_at) if latest_row else None,
            "baselineCapturedAt": None,
            "sampleCount": 0,
            "hasData": False,
            "hasFullWindow": False,
        }

    baseline_row = (
        db.query(LiveCounterSnapshot)
        .filter(
            LiveCounterSnapshot.account_tag == accountTag,
            LiveCounterSnapshot.captured_at <= cutoff,
        )
        .order_by(LiveCounterSnapshot.captured_at.desc(), LiveCounterSnapshot.id.desc())
        .first()
    )
    window_rows = (
        db.query(LiveCounterSnapshot)
        .filter(
            LiveCounterSnapshot.account_tag == accountTag,
            LiveCounterSnapshot.captured_at >= cutoff,
        )
        .order_by(LiveCounterSnapshot.captured_at.asc(), LiveCounterSnapshot.id.asc())
        .all()
    )
    if not baseline_row:
        return {
            "window": {
                "unit": window_unit,
                "value": window_value,
                "minutes": int(window_delta.total_seconds() // 60),
            },
            "windowViews": None,
            "currentViewCount": int(latest_row.view_count or 0),
            "baselineViewCount": None,
            "capturedAt": _serialize_saigon_naive(latest_row.captured_at),
            "baselineCapturedAt": None,
            "sampleCount": len(window_rows),
            "hasData": True,
            "hasFullWindow": False,
        }

    current_view_count = int(latest_row.view_count or 0)
    baseline_view_count = int(baseline_row.view_count or 0)
    window_views = max(0, current_view_count - baseline_view_count)

    return {
        "window": {
            "unit": window_unit,
            "value": window_value,
            "minutes": int(window_delta.total_seconds() // 60),
        },
        "windowViews": window_views,
        "currentViewCount": current_view_count,
        "baselineViewCount": baseline_view_count,
        "capturedAt": _serialize_saigon_naive(latest_row.captured_at),
        "baselineCapturedAt": _serialize_saigon_naive(baseline_row.captured_at),
        "sampleCount": len(window_rows),
        "hasData": True,
        "hasFullWindow": True,
    }
