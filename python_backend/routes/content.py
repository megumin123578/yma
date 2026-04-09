# routes/content.py
import json
import os
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
from python_backend.token_store import (
    load_token_credentials as load_stored_token_credentials,
    token_exists,
)
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from python_backend.module_trafficsource import sanitize_filename  # dùng lại hàm này
router = APIRouter(prefix="/api/content", tags=["content"])

ALL_CHANNELS_VALUE = "__all__"

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


def _normalize_video_metrics_cache_payload(payload):
    if not isinstance(payload, dict):
        return None, None
    if "video_metrics" in payload:
        metrics = payload.get("video_metrics")
        meta = payload.get("_meta") or {}
        thumbnail_supported = meta.get("thumbnail_supported")
        return metrics if isinstance(metrics, dict) else None, bool(thumbnail_supported)
    return payload, None


def _build_video_metrics_cache_payload(video_metrics: dict, thumbnail_supported: bool):
    return {
        "video_metrics": video_metrics,
        "_meta": {
            "thumbnail_supported": bool(thumbnail_supported),
        },
    }


def _fetch_video_metrics_bulk(creds, channel_id: Optional[str], video_ids, start_date, end_date):
    """
    Fetch per-video aggregated metrics (no day dimension).
    Returns tuple: ({video_id: {views, watch_time_hours, average_view_duration, subscribers,
    impressions, impressions_click_through_rate}}, thumbnail_supported)
    """
    if not video_ids:
        return {}, False

    yta = build("youtubeAnalytics", "v2", credentials=creds)
    ids = f"channel=={channel_id}" if channel_id else "channel==MINE"
    out = {}

    for chunk in _chunked(video_ids, 100):
        chunk_filter = f"video=={','.join(chunk)}"
        
        # 1. Core Metrics (Views + Watch Time + Subscribers) - Combined for speed
        try:
            resp = yta.reports().query(
                ids=ids,
                startDate=start_date,
                endDate=end_date,
                dimensions="video",
                filters=chunk_filter,
                metrics="views,estimatedMinutesWatched,averageViewDuration,subscribersGained"
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
                    out[vid]["average_view_duration"] = float(r[idx["averageViewDuration"]] or 0.0) if "averageViewDuration" in idx else None
                    out[vid]["subscribers"] = int(r[idx["subscribersGained"]] or 0) if "subscribersGained" in idx else 0
        except HttpError as e:
            if e.resp.status != 403: # Only log if not a permission issue
                print(f"[content.video-metrics] Core metrics failed for chunk: {e}")
        except Exception:
            pass

    thumbnail_supported = False
    for vid in video_ids:
        try:
            resp = yta.reports().query(
                ids=ids,
                startDate=start_date,
                endDate=end_date,
                filters=f"video=={vid}",
                metrics="videoThumbnailImpressions,videoThumbnailImpressionsClickRate"
            ).execute() or {}
        except HttpError as e:
            if e.resp.status == 400:
                print(f"[content.video-metrics] Thumbnail metrics unsupported: {e}")
                thumbnail_supported = False
                break
            if e.resp.status != 403:
                print(f"[content.video-metrics] Thumbnail metrics failed for {vid}: {e}")
            continue
        except Exception:
            continue

        headers = resp.get("columnHeaders", []) or []
        if not headers:
            thumbnail_supported = True
            continue

        thumbnail_supported = True
        rows = resp.get("rows") or []
        idx = {h["name"]: i for i, h in enumerate(headers)}
        if not rows:
            continue
        row = rows[0]
        if vid not in out:
            out[vid] = {}
        try:
            out[vid]["impressions"] = int(row[idx["videoThumbnailImpressions"]] or 0)
        except Exception:
            out[vid]["impressions"] = 0
        try:
            out[vid]["impressions_click_through_rate"] = (
                float(row[idx["videoThumbnailImpressionsClickRate"]] or 0.0) * 100.0
            )
        except Exception:
            out[vid]["impressions_click_through_rate"] = None

    if thumbnail_supported:
        for vid in video_ids:
            if vid not in out:
                out[vid] = {}
            if "impressions" not in out[vid]:
                out[vid]["impressions"] = 0
            if "impressions_click_through_rate" not in out[vid]:
                out[vid]["impressions_click_through_rate"] = None

    # Ensure all requested IDs are in out with defaults if missing
    for vid in video_ids:
        if vid not in out:
            out[vid] = {
                "views": None,
                "watch_time_hours": None,
                "average_view_duration": None,
                "subscribers": None,
                "impressions": None,
                "impressions_click_through_rate": None,
            }
        else:
            for key in [
                "views",
                "watch_time_hours",
                "average_view_duration",
                "subscribers",
                "impressions",
                "impressions_click_through_rate",
            ]:
                if key not in out[vid]:
                    out[vid][key] = None

    return out, thumbnail_supported

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


def _build_account_tag_filter(column_name: str, account_tags):
    normalized = [sanitize_filename(tag or "") for tag in (account_tags or []) if tag]
    if not normalized:
        return "1 = 0", {}

    placeholders = []
    params = {}
    for idx, tag in enumerate(normalized):
        key = f"account_tag_{idx}"
        placeholders.append(f":{key}")
        params[key] = tag

    if len(placeholders) == 1:
        return f"{column_name} = {placeholders[0]}", params
    return f"{column_name} IN ({', '.join(placeholders)})", params


def _list_content_video_ids(account_tag: str, start_date: date, end_date: date):
    sql = """
        SELECT v.video_id
        FROM videos v
        LEFT JOIN video_daily_stats s
          ON s.video_id = v.video_id
         AND s.day BETWEEN :start_date AND :end_date
        WHERE v.account_tag = :account_tag
        GROUP BY v.video_id
        HAVING SUM(s.views) > 0 OR MAX(v.views) > 0
        ORDER BY MAX(v.published_at) DESC NULLS LAST;
    """
    rows = query_all_safe(
        sql,
        {
            "account_tag": account_tag,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    return [str(row.get("video_id")) for row in rows if row.get("video_id")]


def _load_or_fetch_video_metrics(
    db: Session,
    account_tag: str,
    start_date: date,
    end_date: date,
    video_ids,
):
    if not video_ids:
        return {}, False

    cached_payload = _load_video_metrics_cache(account_tag, start_date, end_date)
    cached_metrics, cached_thumbnail_supported = _normalize_video_metrics_cache_payload(cached_payload)
    if cached_metrics is not None:
        return cached_metrics, bool(cached_thumbnail_supported)

    credential_row = _find_credential_row(db, account_tag)
    if not credential_row or not getattr(credential_row, "token_name", None):
        return {}, False

    creds = _load_token_credentials(credential_row.token_name)
    if not creds:
        return {}, False

    channel_id = getattr(credential_row, "selected_channel_id", None)
    video_metrics, thumbnail_supported = _fetch_video_metrics_bulk(
        creds,
        channel_id,
        video_ids,
        str(start_date),
        str(end_date),
    )
    _save_video_metrics_cache(
        account_tag,
        start_date,
        end_date,
        _build_video_metrics_cache_payload(video_metrics, thumbnail_supported),
    )
    return video_metrics, thumbnail_supported


def _apply_video_metrics_to_content_rows(rows_mutable, video_metrics: dict, thumbnail_supported: bool):
    if not rows_mutable:
        return
    for row in rows_mutable:
        metrics = video_metrics.get(row.get("videoId")) or {}
        if metrics.get("watch_time_hours") is not None:
            row["watchTimeHours"] = float(metrics["watch_time_hours"])
        if metrics.get("average_view_duration") is not None:
            row["averageViewDuration"] = float(metrics["average_view_duration"])
        if metrics.get("subscribers") is not None:
            row["subscribers"] = int(metrics["subscribers"])
        if metrics.get("impressions") is not None:
            row["impressions"] = int(metrics["impressions"])
        elif thumbnail_supported:
            row["impressions"] = 0

        if "impressions_click_through_rate" in metrics:
            row["impressionsClickThroughRate"] = metrics.get("impressions_click_through_rate")
        elif thumbnail_supported:
            row["impressionsClickThroughRate"] = None


def _should_hide_private_content_row(row: dict) -> bool:
    try:
        watch_time_hours = float(
            row.get("watchTimeHours")
            or row.get("watch_time_hours")
            or 0
        )
    except Exception:
        watch_time_hours = 0.0
    return watch_time_hours <= 0


def _filter_private_timeseries_rows(
    db: Session,
    requested_tags: list[str],
    rows_mutable: list[dict],
):
    return rows_mutable


def _compute_channel_metrics_from_video_metrics(video_metrics: dict):
    impressions = 0
    weighted_ctr_sum = 0.0
    has_supported_value = False
    for metrics in (video_metrics or {}).values():
        impressions_value = metrics.get("impressions")
        if impressions_value is None:
            continue
        has_supported_value = True
        impressions_value = int(impressions_value or 0)
        impressions += impressions_value
        ctr_value = metrics.get("impressions_click_through_rate")
        if ctr_value is not None and impressions_value > 0:
            weighted_ctr_sum += float(ctr_value) * impressions_value

    ctr = (weighted_ctr_sum / impressions) if impressions > 0 else None
    return {
        "impressions": impressions,
        "ctr": ctr,
        "supported": has_supported_value,
    }


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


def _list_content_channels(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
    include_hidden: bool = False,
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
        for row in rows:
            value = sanitize_filename(row.account_tag or "")
            if not value or value in seen:
                continue
            if allowed is not None and value not in allowed:
                continue
            if not include_hidden and hidden_all and value in hidden_all:
                continue
            token_name = (row.token_name or "").strip()
            if not token_name:
                continue
            if not token_exists(token_name):
                continue
            seen.add(value)
            label = row.selected_channel_title or row.account_tag or value
            avatar = row.selected_channel_avatar or None
            items.append({"value": value, "label": label, "avatar": avatar})
    except Exception as e:
        print("[content.channels] ERROR:", e)

    return items


def _resolve_content_account_tags(channel_id: str, channel_items, all_channel_items=None) -> list[str]:
    available_tags = [
        str(item.get("value") or "").strip()
        for item in (channel_items or [])
        if item.get("value")
    ]
    if channel_id == ALL_CHANNELS_VALUE:
        source_items = all_channel_items if all_channel_items is not None else channel_items
        return [
            str(item.get("value") or "").strip()
            for item in (source_items or [])
            if item.get("value")
        ]

    requested = str(channel_id or "").strip()
    if requested and requested in available_tags:
        return [requested]
    return []


@router.get("/channels")
def list_channels(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    return {"items": _list_content_channels(db, current_user)}


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
    channel_items = _list_content_channels(db, current_user)
    all_channel_items = _list_content_channels(db, current_user, include_hidden=True)
    requested_tags = _resolve_content_account_tags(req.channelId, channel_items, all_channel_items)
    if not requested_tags:
        return {
            "items": [],
            "channelMetrics": {"impressions": 0, "ctr": None, "supported": False},
        }

    account_filter_sql, account_filter_params = _build_account_tag_filter(
        "v.account_tag",
        requested_tags,
    )
    sql = f"""
    SELECT
        v.video_id      AS "videoId",
        v.account_tag   AS "channelId",
        v.title,
        v.thumbnail,
        v.published_at  AS "publishedAt",
        v.duration,

        COALESCE(MAX(v.views), 0) AS views,
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
        -- Prefer exact-range reach totals (card + teaser). If unavailable, fall back
        -- to daily card-only metrics because video_daily_stats does not store teaser data.
        COALESCE(
            MAX(r.total_impressions),
            NULLIF(SUM(COALESCE(s.card_impressions, 0)), 0),
            0
        ) AS impressions,

        CASE
            WHEN MAX(r.total_impressions) IS NOT NULL
                THEN COALESCE(MAX(r.total_ctr), 0) * 100.0
            WHEN SUM(COALESCE(s.card_impressions, 0)) > 0
                THEN (
                    SUM(COALESCE(s.card_clicks, 0))::numeric
                    / SUM(COALESCE(s.card_impressions, 0))
                ) * 100.0
            ELSE 0
        END AS "impressionsClickThroughRate",
        
        COALESCE(v.card_impressions, 0) AS "cardImpressions",
        COALESCE(v.ad_impressions, 0) AS "adImpressions"
    FROM videos v
    LEFT JOIN video_daily_stats s
      ON s.video_id = v.video_id
     AND s.day BETWEEN :start AND :end
    LEFT JOIN reach_video_metrics r
      ON r.video_id = v.video_id
     AND r.account_tag = v.account_tag
     AND r.start_date = :start
     AND r.end_date = :end
    WHERE {account_filter_sql}
    GROUP BY
        v.video_id,
        v.account_tag,
        v.title,
        v.thumbnail,
        v.published_at,
        v.duration,
        v.ctr,
        v.card_impressions,
        v.ad_impressions
    HAVING SUM(s.views) > 0 OR MAX(v.views) > 0
    ORDER BY v.published_at DESC;
""" 


    params = {
        "start": req.start,
        "end": req.end,
        **account_filter_params,
    }

    rows_mutable = [dict(r) for r in query_all_safe(sql, params)]
    channel_source_items = all_channel_items if req.channelId == ALL_CHANNELS_VALUE else channel_items
    label_map = {
        str(item.get("value") or ""): str(item.get("label") or item.get("value") or "")
        for item in channel_source_items
        if item.get("value")
    }
    avatar_map = {
        str(item.get("value") or ""): item.get("avatar") or None
        for item in channel_source_items
        if item.get("value")
    }
    for row in rows_mutable:
        channel_id = str(row.get("channelId") or "").strip()
        row["channelTitle"] = label_map.get(channel_id) or channel_id
        row["channelAvatar"] = avatar_map.get(channel_id)

    channel_metrics_payload = _compute_channel_metrics_from_db_for_accounts(
        requested_tags,
        req.start,
        req.end,
    )

    rows_mutable = [row for row in rows_mutable if not _should_hide_private_content_row(row)]

    return {
        "items": rows_mutable,
        "channelMetrics": channel_metrics_payload,
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
    channel_items = _list_content_channels(db, current_user)
    all_channel_items = _list_content_channels(db, current_user, include_hidden=True)
    requested_tags = _resolve_content_account_tags(req.channelId, channel_items, all_channel_items)
    if not requested_tags:
        return {"items": []}

    label_map = {
        str(item.get("value") or ""): str(item.get("label") or item.get("value") or "")
        for item in (all_channel_items if req.channelId == ALL_CHANNELS_VALUE else channel_items)
        if item.get("value")
    }

    if len(requested_tags) == 1:
        cached = _load_timeseries_cache(requested_tags[0], req.start, req.end)
        if cached is not None:
            cached_rows = [dict(row) for row in cached]
            for row in cached_rows:
                channel_id = str(row.get("channelId") or requested_tags[0]).strip()
                row["channelId"] = channel_id
                row["channelTitle"] = label_map.get(channel_id) or channel_id
            cached_rows = _filter_private_timeseries_rows(db, requested_tags, cached_rows)
            return {"items": cached_rows}

    account_filter_sql, account_filter_params = _build_account_tag_filter(
        "v.account_tag",
        requested_tags,
    )
    sql = f"""
        SELECT
            s.day                  AS bucket,
            v.video_id             AS "videoId",
            v.account_tag          AS "channelId",
            v.title                AS title,

            s.views                AS views,
            (s.estimated_minutes / 60.0) AS watch_hours,

            s.likes                AS likes,
            0::numeric             AS revenue,
            0::bigint              AS impressions
        FROM video_daily_stats s
        JOIN videos v
          ON v.video_id = s.video_id
        WHERE {account_filter_sql}
          AND s.day BETWEEN :start AND :end
        ORDER BY
            bucket ASC,
            "channelId" ASC,
            "videoId" ASC;
    """

    params = {
        "start": req.start,
        "end": req.end,
        **account_filter_params,
    }

    rows = [dict(row) for row in query_all_safe(sql, params)]
    for row in rows:
        channel_id = str(row.get("channelId") or "").strip()
        row["channelTitle"] = label_map.get(channel_id) or channel_id
    rows = _filter_private_timeseries_rows(db, requested_tags, rows)

    if len(requested_tags) == 1:
        _save_timeseries_cache(requested_tags[0], req.start, req.end, rows)
    # print("[content.timeseries] rows (sample) =", rows[:5])  # debug
    return {"items": rows}


def _load_token_credentials(token_name: str):
    try:
        return load_stored_token_credentials(token_name)
    except Exception:
        return None


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


def _compute_channel_metrics_from_db(account_tag: str, start_date: date, end_date: date):
    return _compute_channel_metrics_from_db_for_accounts([account_tag], start_date, end_date)


def _compute_channel_metrics_from_db_for_accounts(account_tags, start_date: date, end_date: date):
    account_filter_sql, account_filter_params = _build_account_tag_filter(
        "v.account_tag",
        account_tags,
    )
    sql = f"""
        WITH per_video AS (
            SELECT
                v.video_id,
                COALESCE(
                    MAX(r.total_impressions),
                    NULLIF(SUM(COALESCE(s.card_impressions, 0)), 0),
                    0
                ) AS impressions,
                CASE
                    WHEN MAX(r.total_impressions) IS NOT NULL
                        THEN COALESCE(MAX(r.total_ctr), 0) * 100.0
                    WHEN SUM(COALESCE(s.card_impressions, 0)) > 0
                        THEN (
                            SUM(COALESCE(s.card_clicks, 0))::numeric
                            / SUM(COALESCE(s.card_impressions, 0))
                        ) * 100.0
                    ELSE NULL
                END AS ctr
            FROM videos v
            LEFT JOIN video_daily_stats s
              ON s.video_id = v.video_id
             AND s.day BETWEEN :start_date AND :end_date
            LEFT JOIN reach_video_metrics r
              ON r.video_id = v.video_id
             AND r.account_tag = v.account_tag
             AND r.start_date = :start_date
             AND r.end_date = :end_date
            WHERE {account_filter_sql}
            GROUP BY v.video_id
        )
        SELECT
            COALESCE(SUM(impressions), 0) AS impressions,
            CASE
                WHEN SUM(impressions) > 0
                    THEN SUM(COALESCE(ctr, 0) * impressions) / SUM(impressions)
                ELSE NULL
            END AS ctr
        FROM per_video;
    """
    row = query_all_safe(
        sql,
        {
            "start_date": start_date,
            "end_date": end_date,
            **account_filter_params,
        },
    )
    if not row:
        return {"impressions": 0, "ctr": None, "supported": False}
    payload = row[0]
    impressions = int(payload.get("impressions") or 0)
    ctr = payload.get("ctr")
    ctr = float(ctr) if ctr is not None else None
    return {
        "impressions": impressions,
        "ctr": ctr,
        "supported": impressions > 0 or ctr is not None,
    }


@router.post("/channel-metrics")
def channel_metrics(
    req: ChannelMetricsRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    channel_items = _list_content_channels(db, current_user)
    all_channel_items = _list_content_channels(db, current_user, include_hidden=True)
    requested_tags = _resolve_content_account_tags(req.channelId, channel_items, all_channel_items)
    if not requested_tags:
        return {"impressions": 0, "ctr": None, "supported": False}
    return _compute_channel_metrics_from_db_for_accounts(requested_tags, req.start, req.end)
