# routes/content.py
import json
import os
import pickle
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from datetime import date
from typing import Optional
from sqlalchemy import text
from python_backend.db import engine
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user_optional
from python_backend.api.auth.database import get_db
from python_backend.api.auth.visibility import get_allowed_account_tags, get_hidden_account_tags
from python_backend.api.auth.models import UserCredential
from python_backend.module_trafficsource import sanitize_filename  # dùng lại hàm này
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request

router = APIRouter(prefix="/api/content", tags=["content"])

TOKEN_DIR = "./python_backend/token"

# cache table for per-video analytics (not daily)
def _ensure_video_metrics_cache_table() -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS content_video_metrics_cache (
                    account_tag TEXT NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    payload JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (account_tag, start_date, end_date)
                );
            """))
    except Exception as e:
        print("[content.metrics_cache] create table failed:", e)


def _load_video_metrics_cache(account_tag: str, start_date, end_date):
    _ensure_video_metrics_cache_table()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("""
                    SELECT payload
                    FROM content_video_metrics_cache
                    WHERE account_tag = :tag
                      AND start_date = :start_date
                      AND end_date = :end_date
                    LIMIT 1;
                """),
                {"tag": account_tag, "start_date": start_date, "end_date": end_date},
            ).mappings().first()
        if not row:
            return None
        payload = row.get("payload")
        if isinstance(payload, str):
            return json.loads(payload)
        return payload
    except Exception as e:
        print("[content.metrics_cache] load failed:", e)
        return None


def _save_video_metrics_cache(account_tag: str, start_date, end_date, payload: dict):
    _ensure_video_metrics_cache_table()
    try:
        payload_json = json.dumps(payload, default=str)
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO content_video_metrics_cache (
                        account_tag,
                        start_date,
                        end_date,
                        payload,
                        updated_at
                    )
                    VALUES (
                        :tag,
                        :start_date,
                        :end_date,
                        :payload,
                        NOW()
                    )
                    ON CONFLICT (account_tag, start_date, end_date) DO UPDATE SET
                        payload = EXCLUDED.payload,
                        updated_at = NOW();
                """),
                {
                    "tag": account_tag,
                    "start_date": start_date,
                    "end_date": end_date,
                    "payload": payload_json,
                },
            )
        print("[content.metrics_cache] save ok")
    except Exception as e:
        print("[content.metrics_cache] save failed:", e)


def _chunked(ids, size=50):
    return [ids[i:i + size] for i in range(0, len(ids), size)]


def _fetch_video_metrics_bulk(creds, channel_id: Optional[str], video_ids, start_date, end_date):
    """
    Fetch per-video aggregated metrics (no day dimension).
    Returns dict: {video_id: {estimatedRevenue, subscribers, impressions, impressionsClickThroughRate}}
    """
    if not video_ids:
        return {}

    yta = build("youtubeAnalytics", "v2", credentials=creds)
    ids = f"channel=={channel_id}" if channel_id else "channel==MINE"
    out = {}
    
    # Track if Reach metrics are supported to avoid repeated 400 errors
    reach_supported = True

    for chunk in _chunked(video_ids, 100):
        chunk_filter = f"video=={','.join(chunk)}"
        
        # 1. Core Metrics (Views + Watch Time + Subscribers + Revenue) - Combined for speed
        try:
            resp = yta.reports().query(
                ids=ids,
                startDate=start_date,
                endDate=end_date,
                dimensions="video",
                filters=chunk_filter,
                metrics="views,estimatedMinutesWatched,subscribersGained,estimatedRevenue"
            ).execute() or {}
            
            rows = resp.get("rows") or []
            headers = resp.get("columnHeaders", []) or []
            if rows and headers:
                idx = {h["name"]: i for i, h in enumerate(headers)}
                for r in rows:
                    vid = r[idx["video"]]
                    if vid not in out: out[vid] = {}
                    out[vid]["views"] = int(r[idx["views"]] or 0) if "views" in idx else 0
                    out[vid]["watch_time_hours"] = round(float(r[idx["estimatedMinutesWatched"]] or 0) / 60.0, 2) if "estimatedMinutesWatched" in idx else 0.0
                    out[vid]["subscribers"] = int(r[idx["subscribersGained"]] or 0) if "subscribersGained" in idx else 0
                    out[vid]["estimated_revenue"] = float(r[idx["estimatedRevenue"]] or 0.0) if "estimatedRevenue" in idx else 0.0
        except HttpError as e:
            if e.resp.status != 403: # Only log if not a permission issue
                print(f"[content.video-metrics] Core metrics failed for chunk: {e}")
        except Exception:
            pass

        # 2. Reach (Impressions) - Circuit breaker: stop trying if first chunk fails with 400
        if reach_supported:
            try:
                resp = yta.reports().query(
                    ids=ids,
                    startDate=start_date,
                    endDate=end_date,
                    dimensions="video",
                    filters=chunk_filter,
                    metrics="videoThumbnailImpressions,videoThumbnailImpressionsClickRate"
                ).execute() or {}
                
                rows = resp.get("rows") or []
                headers = resp.get("columnHeaders", []) or []
                if rows and headers:
                    idx = {h["name"]: i for i, h in enumerate(headers)}
                    for r in rows:
                        vid = r[idx["video"]]
                        if vid not in out: out[vid] = {}
                        out[vid]["impressions"] = int(r[idx["videoThumbnailImpressions"]] or 0)
                        ctr = float(r[idx["videoThumbnailImpressionsClickRate"]] or 0.0) * 100.0
                        out[vid]["impressions_click_through_rate"] = ctr
            except HttpError as e:
                if e.resp.status == 400:
                    reach_supported = False # Disable for future chunks to save time
                elif e.resp.status != 403:
                    print(f"[content.video-metrics] Reach metrics failed: {e}")
            except Exception:
                reach_supported = False

    # Ensure all requested IDs are in out with defaults if missing
    for vid in video_ids:
        if vid not in out:
            out[vid] = {
                "views": None,
                "watch_time_hours": None,
                "subscribers": None,
                "estimated_revenue": None,
                "impressions": None,
                "impressions_click_through_rate": None,
            }
        else:
            for key in ["views", "watch_time_hours", "subscribers", "estimated_revenue", "impressions", "impressions_click_through_rate"]:
                if key not in out[vid]:
                    out[vid][key] = None

    return out

# ==============================
# Helper query
# ==============================
def query_all_safe(sql: str, params=None):
    try:
        with engine.begin() as conn:
            rs = conn.execute(text(sql), params or {})
            return rs.mappings().all()
    except Exception as e:
        print("[content.query_all_safe] failed:", e)
        return []


def _ensure_timeseries_cache_table() -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS content_timeseries_cache (
                    account_tag TEXT NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    payload JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (account_tag, start_date, end_date)
                );
            """))
    except Exception as e:
        print("[content.cache] create table failed:", e)


def _load_timeseries_cache(account_tag: str, start_date, end_date):
    _ensure_timeseries_cache_table()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("""
                    SELECT payload
                    FROM content_timeseries_cache
                    WHERE account_tag = :tag
                      AND start_date = :start_date
                      AND end_date = :end_date
                    LIMIT 1;
                """),
                {"tag": account_tag, "start_date": start_date, "end_date": end_date},
            ).mappings().first()
        if not row:
            return None
        payload = row.get("payload")
        if isinstance(payload, str):
            return json.loads(payload)
        return payload
    except Exception as e:
        print("[content.cache] load failed:", e)
        return None


def _save_timeseries_cache(account_tag: str, start_date, end_date, rows):
    _ensure_timeseries_cache_table()
    try:
        payload_rows = [dict(r) for r in rows]
        payload = json.dumps(payload_rows, default=str)
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO content_timeseries_cache (
                        account_tag,
                        start_date,
                        end_date,
                        payload,
                        updated_at
                    )
                    VALUES (
                        :tag,
                        :start_date,
                        :end_date,
                        :payload,
                        NOW()
                    )
                    ON CONFLICT (account_tag, start_date, end_date) DO UPDATE SET
                        payload = EXCLUDED.payload,
                        updated_at = NOW();
                """),
                {
                    "tag": account_tag,
                    "start_date": start_date,
                    "end_date": end_date,
                    "payload": payload,
                },
            )
        print("[content.cache] save ok")
    except Exception as e:
        print("[content.cache] save failed:", e)


@router.get("/channels")
def list_channels(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    items = []
    try:
        hidden_all = set()
        allowed = get_allowed_account_tags(db, current_user)
        if current_user:
            hidden = get_hidden_account_tags(db, current_user.id)
            hidden_all = hidden | {sanitize_filename(t) for t in hidden}

        rows = (
            db.query(UserCredential)
            .filter(UserCredential.token_name.isnot(None))
            .order_by(UserCredential.updated_at.desc())
            .all()
        )
        seen = set()
        now = datetime.utcnow()
        avatar_ttl = timedelta(days=30)
        for row in rows:
            value = sanitize_filename(row.account_tag or "")
            if not value or value in seen:
                continue
            if allowed is not None and value not in allowed:
                continue
            if hidden_all and value in hidden_all:
                continue
            seen.add(value)
            label = row.selected_channel_title or row.account_tag or value
            avatar = row.selected_channel_avatar or None
            is_stale = not row.updated_at or (row.updated_at < (now - avatar_ttl))
            if (not avatar or is_stale) and row.token_name:
                try:
                    creds = _load_token_credentials(row.token_name)
                    if creds:
                        youtube = build("youtube", "v3", credentials=creds)
                        query = {"part": "snippet", "maxResults": 1}
                        if row.selected_channel_id:
                            query["id"] = row.selected_channel_id
                        else:
                            query["mine"] = True
                        resp = youtube.channels().list(**query).execute() or {}
                        it = (resp.get("items") or [])
                        if it:
                            snippet = it[0].get("snippet", {})
                            thumbs = snippet.get("thumbnails", {}) or {}
                            avatar = (
                                (thumbs.get("high") or {}).get("url")
                                or (thumbs.get("medium") or {}).get("url")
                                or (thumbs.get("default") or {}).get("url")
                            )
                            if avatar:
                                row.selected_channel_avatar = avatar
                                if not row.selected_channel_title and snippet.get("title"):
                                    row.selected_channel_title = snippet.get("title")
                                row.updated_at = now
                                db.add(row)
                                db.commit()
                except HttpError as e:
                    print("[content.channels] avatar fetch failed:", e)
                except Exception as e:
                    print("[content.channels] avatar fetch error:", e)
            items.append({"value": value, "label": label, "avatar": avatar})
    except Exception as e:
        print("[content.channels] ERROR:", e)

    return {"items": items}


class ContentListRequest(BaseModel):
    start: date
    end: date
    channelId: str


@router.post("/list")
def content_list(
    req: ContentListRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    allowed = get_allowed_account_tags(db, current_user)
    if allowed is not None and req.channelId not in allowed:
        return {"items": []}
    if current_user:
        hidden = get_hidden_account_tags(db, current_user.id)
        hidden_all = hidden | {sanitize_filename(t) for t in hidden}
        if req.channelId in hidden_all:
            return {"items": []}
    sql = """
    SELECT
        v.video_id      AS "videoId",
        v.title,
        v.thumbnail,
        v.published_at  AS "publishedAt",
        v.duration,

        COALESCE(SUM(s.views), 0) AS views,
        COALESCE(SUM(s.estimated_minutes) / 60.0, 0) AS "watchTimeHours",
        CASE
            WHEN COALESCE(SUM(s.views), 0) > 0
                THEN ROUND(SUM(COALESCE(s.average_view_duration, 0) * COALESCE(s.views, 0))::numeric / NULLIF(SUM(s.views), 0), 2)
            ELSE NULL
        END AS "averageViewDuration",

        COALESCE(SUM(s.likes), 0) AS likes,
        NULL::numeric AS "averagePercentageViewed",
        NULL::bigint AS "engagedViews",
        NULL::numeric AS "stayedToWatch",
        NULL::bigint AS "uniqueViewers",
        NULL::numeric AS "averageViewsPerViewer",
        NULL::bigint AS "newViewers",
        NULL::bigint AS "returningViewers",
        NULL::bigint AS "casualViewers",
        NULL::bigint AS "regularViewers",
        
        -- Sum daily stats for engagement and reach metrics
        COALESCE(SUM(s.subscribers_gained), 0) AS "subscribers",
        COALESCE(SUM(s.estimated_revenue), 0) AS "estimatedRevenue",
        
        -- Unified Impressions logic: Prefer daily stats sum (card+anno), fallback to reach table
        COALESCE(
            NULLIF(SUM(COALESCE(s.card_impressions, 0) + COALESCE(s.annotation_impressions, 0)), 0),
            MAX(r.total_impressions), 
            0
        ) AS impressions,

        -- Unified CTR logic: Weighted calculation based on the same source as impressions
        CASE 
            WHEN SUM(COALESCE(s.card_impressions, 0) + COALESCE(s.annotation_impressions, 0)) > 0
                THEN (SUM(COALESCE(s.card_clicks, 0) + COALESCE(s.annotation_clicks, 0))::numeric / 
                      SUM(COALESCE(s.card_impressions, 0) + COALESCE(s.annotation_impressions, 0))) * 100.0
            ELSE COALESCE(MAX(r.total_ctr), 0) * 100.0
        END AS "impressionsClickThroughRate",
        
        COALESCE(v.card_impressions, 0) AS "cardImpressions",
        COALESCE(v.ad_impressions, 0) AS "adImpressions",
        COALESCE(v.annotation_impressions, 0) AS "annotationImpressions"
    FROM videos v
    LEFT JOIN video_daily_stats s
      ON s.video_id = v.video_id
     AND s.day BETWEEN :start AND :end
    LEFT JOIN reach_video_metrics r
      ON r.video_id = v.video_id
     AND r.account_tag = :account_tag
    WHERE v.account_tag = :account_tag
    GROUP BY
        v.video_id,
        v.title,
        v.thumbnail,
        v.published_at,
        v.duration,
        v.ctr,
        v.card_impressions,
        v.ad_impressions,
        v.annotation_impressions
    HAVING SUM(s.views) > 0 OR MAX(v.views) > 0
    ORDER BY v.published_at DESC;
"""


    params = {
        "start": req.start,
        "end": req.end,
        "account_tag": req.channelId,
    }

    rows_mutable = [dict(r) for r in query_all_safe(sql, params)]

    # enrich per-video metrics (impressions, ctr, revenue, subscribers)
    try:
        cred_row = _find_credential_row(db, req.channelId)
        metrics_map = None
        if cred_row and cred_row.token_name:
            cached = _load_video_metrics_cache(req.channelId, req.start, req.end)
            if cached is not None:
                metrics_map = cached
            else:
                creds = _load_token_credentials(cred_row.token_name)
                if creds:
                    # Limit real-time enrichment to top 200 videos by views/priority for speed
                    # The rest will stay with DB fallback values.
                    video_ids = [r.get("videoId") for r in rows_mutable if r.get("videoId")][:200]
                    metrics_map = _fetch_video_metrics_bulk(
                        creds,
                        cred_row.selected_channel_id,
                        video_ids,
                        req.start.isoformat(),
                        req.end.isoformat(),
                    )
                    _save_video_metrics_cache(req.channelId, req.start, req.end, metrics_map)
        if metrics_map:
            for r in rows_mutable:
                vid = r.get("videoId")
                m = metrics_map.get(vid)
                if not m:
                    continue
                
                # Core metrics usually always available
                if m.get("views") is not None:
                    r["views"] = m.get("views")
                if m.get("watch_time_hours") is not None:
                    r["watchTimeHours"] = m.get("watch_time_hours")
                if m.get("subscribers") is not None:
                    r["subscribers"] = m.get("subscribers")
                if m.get("estimated_revenue") is not None:
                    r["estimatedRevenue"] = m.get("estimated_revenue")
                
                # Only overwrite Reach metrics if API actually returned them.
                # Since many channels return 400 for these, we keep the DB fallback otherwise.
                if m.get("impressions") is not None:
                    r["impressions"] = m.get("impressions")
                if m.get("impressions_click_through_rate") is not None:
                    r["impressionsClickThroughRate"] = m.get("impressions_click_through_rate")
    except Exception as e:
        print("[content.list] metrics enrich failed:", e)

    channel_metrics_data = None
    try:
        channel_metrics_data = channel_metrics(
            ChannelMetricsRequest(start=req.start, end=req.end, channelId=req.channelId),
            db,
            current_user,
        )
    except Exception as e:
        print("[content.list] channel metrics enrichment failed:", e)

    return {
        "items": rows_mutable,
        "channelMetrics": channel_metrics_data,
    }

class TimeSeriesRequest(BaseModel):
    start: date
    end: date
    channelId: str  # = account_tag


class ChannelMetricsRequest(BaseModel):
    start: date
    end: date
    channelId: str


@router.post("/timeseries")
def content_timeseries(
    req: TimeSeriesRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    allowed = get_allowed_account_tags(db, current_user)
    if allowed is not None and req.channelId not in allowed:
        return {"items": []}
    if current_user:
        hidden = get_hidden_account_tags(db, current_user.id)
        hidden_all = hidden | {sanitize_filename(t) for t in hidden}
        if req.channelId in hidden_all:
            return {"items": []}

    cached = _load_timeseries_cache(req.channelId, req.start, req.end)
    if cached is not None:
        return {"items": cached}

    sql = """
        SELECT
            s.day                  AS bucket,
            v.video_id             AS "videoId",
            v.title                AS title,

            s.views                AS views,
            (s.estimated_minutes / 60.0) AS watch_hours,

            s.likes                AS likes,
            0::numeric             AS revenue,
            0::bigint              AS impressions
        FROM video_daily_stats s
        JOIN videos v
          ON v.video_id = s.video_id
        WHERE v.account_tag = :account_tag
          AND s.day BETWEEN :start AND :end
        ORDER BY
            bucket ASC,
            "videoId" ASC;
    """

    params = {
        "account_tag": req.channelId,
        "start": req.start,
        "end": req.end,
    }

    rows = query_all_safe(sql, params)
    _save_timeseries_cache(req.channelId, req.start, req.end, rows)
    # print("[content.timeseries] rows (sample) =", rows[:5])  # debug
    return {"items": rows}


def _load_token_credentials(token_name: str):
    token_path = os.path.join(TOKEN_DIR, token_name)
    if not os.path.exists(token_path):
        return None
    try:
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
    except Exception:
        return None
    if not creds:
        return None
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, "wb") as f:
                    pickle.dump(creds, f)
            except Exception:
                return None
        else:
            return None
    return creds


def _find_credential_row(db: Session, account_tag: str) -> Optional[UserCredential]:
    row = (
        db.query(UserCredential)
        .filter(UserCredential.account_tag == account_tag)
        .order_by(UserCredential.updated_at.desc())
        .first()
    )
    if row:
        return row
    rows = (
        db.query(UserCredential)
        .filter(UserCredential.token_name.isnot(None))
        .all()
    )
    for r in rows:
        if sanitize_filename(r.account_tag) == account_tag:
            return r
    return None


@router.post("/channel-metrics")
def channel_metrics(
    req: ChannelMetricsRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    allowed = get_allowed_account_tags(db, current_user)
    if allowed is not None and req.channelId not in allowed:
        return {"impressions": 0, "ctr": None, "supported": False}
    if current_user:
        hidden = get_hidden_account_tags(db, current_user.id)
        hidden_all = hidden | {sanitize_filename(t) for t in hidden}
        if req.channelId in hidden_all:
            return {"impressions": 0, "ctr": None, "supported": False}
    cred_row = _find_credential_row(db, req.channelId)
    if not cred_row or not cred_row.token_name:
        return {"impressions": 0, "ctr": None, "supported": False}
    creds = _load_token_credentials(cred_row.token_name)
    if not creds:
        return {"impressions": 0, "ctr": None, "supported": False}

    yta = build("youtubeAnalytics", "v2", credentials=creds)
    ids = (
        f"channel=={cred_row.selected_channel_id}"
        if cred_row.selected_channel_id
        else "channel==MINE"
    )

    # Attempt channel-level reach metrics first. If unsupported, fall back
    # to aggregating per-video metrics (dimension=video).
    query = {
        "ids": ids,
        "startDate": req.start.isoformat(),
        "endDate": req.end.isoformat(),
        "metrics": "videoThumbnailImpressions,videoThumbnailImpressionsClickRate",
    }
    # Note: 'dimensions': 'day' is removed because Reach metrics 
    # (impressions, CTR) are not supported with daily granularity 
    # at the channel level in YT Analytics API v2.
    try:
        resp = yta.reports().query(**query).execute() or {}
        rows = resp.get("rows") or []
        if rows:
            headers = resp.get("columnHeaders", []) or []
            idx = {h["name"]: i for i, h in enumerate(headers)}
            i_impr = idx.get("videoThumbnailImpressions")
            i_ctr = idx.get("videoThumbnailImpressionsClickRate")
            if i_impr is not None and i_ctr is not None:
                total_impressions = 0
                weighted_ctr_sum = 0.0
                for row in rows:
                    try:
                        impr = int(row[i_impr] or 0)
                    except Exception:
                        impr = 0
                    try:
                        ctr_val = float(row[i_ctr] or 0.0)
                    except Exception:
                        ctr_val = 0.0
                    total_impressions += impr
                    weighted_ctr_sum += ctr_val * impr

                ctr = (weighted_ctr_sum / total_impressions) * 100.0 if total_impressions > 0 else None
                return {"impressions": total_impressions, "ctr": ctr, "supported": True}
    except HttpError as e:
        # We silence 400 errors here because videoThumbnailImpressions 
        # is often not supported for standard channels at the channel level.
        if e.resp.status != 400:
            print(f"[content.channel-metrics] HttpError: {e}")
    except Exception as e:
        print(f"[content.channel-metrics] ERROR: {e}")

    # Fallback: aggregate per-video metrics
    try:
        rows = query_all_safe(
            "SELECT video_id FROM videos WHERE account_tag = :tag",
            {"tag": req.channelId},
        )
        video_ids = [r.get("video_id") for r in rows if r.get("video_id")]
        metrics_map = _fetch_video_metrics_bulk(
            creds,
            cred_row.selected_channel_id,
            video_ids,
            req.start.isoformat(),
            req.end.isoformat(),
        )
        if not metrics_map:
            return {"impressions": 0, "ctr": None, "supported": False}

        total_impressions = 0
        weighted_ctr_sum = 0.0
        for m in metrics_map.values():
            try:
                impr = int(m.get("impressions") or 0)
            except Exception:
                impr = 0
            try:
                ctr_val = float(m.get("impressions_click_through_rate") or 0.0)
            except Exception:
                ctr_val = 0.0
            total_impressions += impr
            weighted_ctr_sum += ctr_val * impr

        ctr = (weighted_ctr_sum / total_impressions) if total_impressions > 0 else None
        return {"impressions": total_impressions, "ctr": ctr, "supported": True}
    except Exception as e:
        print(f"[content.channel-metrics] fallback failed: {e}")
        return {"impressions": 0, "ctr": None, "supported": False}
