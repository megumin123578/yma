# routes/content.py
import base64
import gzip
import hashlib
import json
import os
import threading
import time
from contextlib import contextmanager
from decimal import Decimal
from functools import wraps
from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from typing import Optional
import orjson
from sqlalchemy import text, inspect
from python_backend.db import engine
from python_backend.perf_log import add_log
from sqlalchemy.orm import Session


def _orjson_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def _compact_timeseries_payload(rows):
    """Move per-video metadata into a videos lookup map.

    Why: SQL returns one row per (video, day) with title/channelId/channelTitle
    repeated on every row. Moving the metadata to a map keyed by videoId cuts
    payload size 30-50% (and JSON parse time on the client). Frontend rehydrates
    rows with metadata after parsing.
    """
    videos: dict = {}
    items: list = []
    META_KEYS = ("title", "channelId", "channelTitle")
    for row in rows:
        vid = row.get("videoId")
        if vid:
            existing = videos.get(vid)
            if existing is None:
                meta = {k: row[k] for k in META_KEYS if row.get(k) is not None}
                if meta:
                    videos[vid] = meta
        slim = {k: v for k, v in row.items() if k not in META_KEYS}
        items.append(slim)
    return {"videos": videos, "items": items}


def _fast_response(content) -> Response:
    """Bypass FastAPI's jsonable_encoder; let orjson serialize directly.

    Why: jsonable_encoder is recursive Python and dominates response time for
    payloads with thousands of rows even when the handler is otherwise instant
    (e.g. cache hit). Returning a Response instance makes FastAPI skip
    serialize_response() entirely.
    """
    body = orjson.dumps(
        content,
        option=orjson.OPT_NON_STR_KEYS,
        default=_orjson_default,
    )
    return Response(content=body, media_type="application/json")


@contextmanager
def _time_block(label: str):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        add_log(f"[T] {label}: {(time.perf_counter() - t0) * 1000:.1f}ms")


def _log_handler(name: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                add_log(f"[H] {name}: {(time.perf_counter() - t0) * 1000:.1f}ms")

        return wrapper

    return decorator

from python_backend.api.auth.auth_utils import get_current_user_optional
from python_backend.api.auth.database import get_db
from python_backend.api.auth.visibility import get_allowed_account_tags, get_hidden_account_tags
from python_backend.api.auth.models import UserCredential
from python_backend.token_store import (
    list_token_names,
    load_token_credentials as load_stored_token_credentials,
    normalize_token_name,
    token_exists,
)
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from python_backend.module_trafficsource import sanitize_filename  # dùng lại hàm này
router = APIRouter(prefix="/api/content", tags=["content"])

ALL_CHANNELS_VALUE = "__all__"
CONTENT_CACHE_VERSION = 10
_VIDEO_DAILY_STATS_COLUMNS_CACHE = None
_CONTENT_CACHE_COMPRESS_MIN_BYTES = 2 * 1024 * 1024
_CONTENT_CACHE_MAX_JSONB_BYTES = 240 * 1024 * 1024
CONTENT_TYPE_ALL = "all"
CONTENT_TYPE_LONG = "long"
CONTENT_TYPE_SHORTS = "shorts"

_CHANNELS_CACHE_TTL_SEC = 30.0
_channels_cache_lock = threading.Lock()
_channels_cache: dict[int, tuple[float, tuple[list, list]]] = {}

# In-process layer above the Postgres-backed JSONB cache. Avoids a DB roundtrip
# + JSON/gzip decode on every cache hit for /list and /timeseries.
_PAYLOAD_CACHE_TTL_SEC = 60.0
_payload_cache_lock = threading.Lock()
_payload_cache: dict[tuple, tuple[float, object]] = {}


def _payload_cache_get(key: tuple):
    now = time.monotonic()
    with _payload_cache_lock:
        entry = _payload_cache.get(key)
        if not entry:
            return None
        ts, value = entry
        if (now - ts) >= _PAYLOAD_CACHE_TTL_SEC:
            _payload_cache.pop(key, None)
            return None
        return value


def _payload_cache_set(key: tuple, value) -> None:
    if value is None:
        return
    with _payload_cache_lock:
        _payload_cache[key] = (time.monotonic(), value)


def _payload_cache_invalidate(key: tuple) -> None:
    with _payload_cache_lock:
        _payload_cache.pop(key, None)

_ensure_lock = threading.Lock()
_ensured_tables: set[str] = set()


def _mark_ensured(name: str) -> bool:
    with _ensure_lock:
        if name in _ensured_tables:
            return False
        _ensured_tables.add(name)
        return True


def _unmark_ensured(name: str) -> None:
    with _ensure_lock:
        _ensured_tables.discard(name)


def _ensure_thumbnail_daily_table() -> None:
    if not _mark_ensured("thumbnail_daily"):
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS video_thumbnail_daily (
                    account_tag TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    video_id TEXT NOT NULL,
                    day DATE NOT NULL,
                    thumbnail_impressions BIGINT NOT NULL DEFAULT 0,
                    thumbnail_ctr DOUBLE PRECISION,
                    report_id TEXT,
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (account_tag, video_id, day)
                );
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_video_thumbnail_daily_account_day
                ON video_thumbnail_daily (account_tag, day);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_video_thumbnail_daily_video_day
                ON video_thumbnail_daily (video_id, day);
            """))
    except Exception as e:
        _unmark_ensured("thumbnail_daily")
        print("[content.thumbnail_daily] create table failed:", e)


def _ensure_video_daily_stats_metrics_columns() -> None:
    if not _mark_ensured("video_daily_stats_columns"):
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS video_daily_stats (
                    video_id TEXT NOT NULL,
                    day DATE NOT NULL,
                    views INTEGER,
                    estimated_minutes INTEGER,
                    average_view_duration INTEGER,
                    average_view_percentage DOUBLE PRECISION,
                    engaged_views INTEGER,
                    likes INTEGER,
                    subscribers_gained INTEGER DEFAULT 0,
                    estimated_revenue NUMERIC DEFAULT 0,
                    card_impressions INTEGER DEFAULT 0,
                    card_clicks INTEGER DEFAULT 0,
                    PRIMARY KEY (video_id, day)
                );
            """))
            conn.execute(text("ALTER TABLE video_daily_stats ADD COLUMN IF NOT EXISTS average_view_percentage DOUBLE PRECISION;"))
            conn.execute(text("ALTER TABLE video_daily_stats ADD COLUMN IF NOT EXISTS engaged_views INTEGER;"))
            conn.execute(text("ALTER TABLE video_daily_stats ADD COLUMN IF NOT EXISTS subscribers_gained INTEGER DEFAULT 0;"))
        return
    except Exception as e:
        _unmark_ensured("video_daily_stats_columns")
        print("[content.video_daily_stats] ensure columns failed:", e)


def _get_video_daily_stats_columns() -> set[str]:
    global _VIDEO_DAILY_STATS_COLUMNS_CACHE
    if _VIDEO_DAILY_STATS_COLUMNS_CACHE is not None:
        return _VIDEO_DAILY_STATS_COLUMNS_CACHE
    try:
        inspector = inspect(engine)
        columns = inspector.get_columns("video_daily_stats")
        _VIDEO_DAILY_STATS_COLUMNS_CACHE = {
            str(col.get("name") or "").strip()
            for col in columns
            if col.get("name")
        }
    except Exception as e:
        print("[content.video_daily_stats] inspect failed:", e)
        _VIDEO_DAILY_STATS_COLUMNS_CACHE = set()
    return _VIDEO_DAILY_STATS_COLUMNS_CACHE


def _sql_average_view_percentage_expr(alias: str = "s", output_alias: str = '"averagePercentageViewed"') -> str:
    columns = _get_video_daily_stats_columns()
    if "average_view_percentage" not in columns:
        return f'NULL::numeric AS {output_alias}'
    return f"""
        CASE
            WHEN COALESCE(SUM(CASE WHEN {alias}.average_view_percentage IS NOT NULL THEN COALESCE({alias}.views, 0) ELSE 0 END), 0) > 0
                THEN ROUND(
                    SUM(COALESCE({alias}.average_view_percentage, 0) * COALESCE({alias}.views, 0))::numeric
                    / NULLIF(SUM(CASE WHEN {alias}.average_view_percentage IS NOT NULL THEN COALESCE({alias}.views, 0) ELSE 0 END), 0),
                    4
                )
            ELSE NULL
        END AS {output_alias}
    """.strip()


def _sql_engaged_views_expr(alias: str = "s", output_alias: str = '"engagedViews"') -> str:
    columns = _get_video_daily_stats_columns()
    if "engaged_views" not in columns:
        return f'NULL::bigint AS {output_alias}'
    return f"""
        CASE
            WHEN COUNT({alias}.engaged_views) > 0
                THEN COALESCE(SUM({alias}.engaged_views), 0)
            ELSE NULL
        END AS {output_alias}
    """.strip()


def _sql_timeseries_average_view_percentage_expr(alias: str = "s", output_alias: str = '"averagePercentageViewed"') -> str:
    columns = _get_video_daily_stats_columns()
    if "average_view_percentage" not in columns:
        return f'NULL::numeric AS {output_alias}'
    return f'{alias}.average_view_percentage AS {output_alias}'


def _sql_timeseries_average_view_duration_expr(alias: str = "s", output_alias: str = '"averageViewDuration"') -> str:
    return f"""
        CASE
            WHEN SUM({alias}.views) > 0
                THEN ROUND(SUM(COALESCE({alias}.average_view_duration, 0) * COALESCE({alias}.views, 0))::numeric / NULLIF(SUM({alias}.views), 0), 2)
            ELSE NULL
        END AS {output_alias}
    """.strip()


def _sql_timeseries_engaged_views_expr(alias: str = "s", output_alias: str = '"engagedViews"') -> str:
    columns = _get_video_daily_stats_columns()
    if "engaged_views" not in columns:
        return f'NULL::bigint AS {output_alias}'
    return f'{alias}.engaged_views AS {output_alias}'


def _normalize_content_type(value: Optional[str]) -> str:
    normalized = str(value or CONTENT_TYPE_ALL).strip().lower()
    if normalized in {CONTENT_TYPE_ALL, CONTENT_TYPE_LONG, CONTENT_TYPE_SHORTS}:
        return normalized
    return CONTENT_TYPE_ALL


def _sql_duration_seconds_expr(alias: str = "v") -> str:
    return f"""
        (
            COALESCE(NULLIF(SUBSTRING({alias}.duration FROM 'PT([0-9]+)H'), ''), '0')::integer * 3600 +
            COALESCE(NULLIF(SUBSTRING({alias}.duration FROM 'PT(?:[0-9]+H)?([0-9]+)M'), ''), '0')::integer * 60 +
            COALESCE(NULLIF(SUBSTRING({alias}.duration FROM 'PT(?:[0-9]+H)?(?:[0-9]+M)?([0-9]+)S'), ''), '0')::integer
        )
    """.strip()


def _build_content_type_filter_sql(
    content_type: Optional[str],
    alias: str = "v",
) -> tuple[str, dict]:
    normalized = _normalize_content_type(content_type)
    if normalized == CONTENT_TYPE_ALL:
        return "1 = 1", {}

    duration_seconds_expr = _sql_duration_seconds_expr(alias)
    if normalized == CONTENT_TYPE_SHORTS:
        return f"({duration_seconds_expr}) <= 60", {}

    return f"({alias}.duration IS NULL OR {alias}.duration = '' OR ({duration_seconds_expr}) > 60)", {}


def _compose_content_cache_key(base_key: str, content_type: Optional[str]) -> str:
    return f"{base_key}:type={_normalize_content_type(content_type)}"

# cache table for per-video analytics (not daily)
def _ensure_video_metrics_cache_table() -> None:
    if not _mark_ensured("video_metrics_cache"):
        return
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
        _unmark_ensured("video_metrics_cache")
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
        if meta.get("version") != CONTENT_CACHE_VERSION:
            return None, None
        thumbnail_supported = meta.get("thumbnail_supported")
        return metrics if isinstance(metrics, dict) else None, bool(thumbnail_supported)
    return None, None


def _build_video_metrics_cache_payload(video_metrics: dict, thumbnail_supported: bool):
    return {
        "video_metrics": video_metrics,
        "_meta": {
            "version": CONTENT_CACHE_VERSION,
            "thumbnail_supported": bool(thumbnail_supported),
        },
    }


def _fetch_video_metrics_bulk(creds, channel_id: Optional[str], video_ids, start_date, end_date):
    """
    Fetch per-video aggregated metrics (no day dimension).
    Returns tuple: ({video_id: {views, watch_time_hours, average_view_duration,
    average_view_percentage, engaged_views, subscribers}}, thumbnail_supported)

    Thumbnail impressions / CTR are sourced only from the reporting bulk tables
    in DB, so this helper must not query them directly from Analytics API.
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

        try:
            resp = yta.reports().query(
                ids=ids,
                startDate=start_date,
                endDate=end_date,
                dimensions="video",
                filters=chunk_filter,
                metrics="averageViewPercentage,engagedViews",
            ).execute() or {}

            rows = resp.get("rows") or []
            headers = resp.get("columnHeaders", []) or []
            if rows and headers:
                idx = {h["name"]: i for i, h in enumerate(headers)}
                for r in rows:
                    vid = r[idx["video"]]
                    if vid not in out:
                        out[vid] = {}
                    out[vid]["average_view_percentage"] = (
                        float(r[idx["averageViewPercentage"]] or 0.0)
                        if "averageViewPercentage" in idx
                        else None
                    )
                    out[vid]["engaged_views"] = (
                        int(r[idx["engagedViews"]] or 0)
                        if "engagedViews" in idx
                        else None
                    )
        except HttpError as e:
            if e.resp.status != 403:
                print(f"[content.video-metrics] Engagement metrics failed for chunk: {e}")
        except Exception:
            pass

    thumbnail_supported = False

    # Ensure all requested IDs are in out with defaults if missing
    for vid in video_ids:
        if vid not in out:
            out[vid] = {
                "views": None,
                "watch_time_hours": None,
                "average_view_duration": None,
                "average_view_percentage": None,
                "engaged_views": None,
                "subscribers": None,
                "impressions": None,
                "impressions_click_through_rate": None,
            }
        else:
            for key in [
                "views",
                "watch_time_hours",
                "average_view_duration",
                "average_view_percentage",
                "engaged_views",
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
    t0 = time.perf_counter()
    try:
        with engine.begin() as conn:
            rs = conn.execute(text(sql), params or {})
            rows = rs.mappings().all()
            line = " ".join(sql.split())
            add_log(
                f"[DB] {(time.perf_counter() - t0) * 1000:.1f}ms"
                f" rows={len(rows)} sql={line[:80]}{'...' if len(line) > 80 else ''}"
            )
            return rows
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
        if metrics.get("average_view_percentage") is not None:
            row["averagePercentageViewed"] = float(metrics["average_view_percentage"])
        if metrics.get("engaged_views") is not None:
            row["engagedViews"] = int(metrics["engaged_views"])
        if metrics.get("subscribers") is not None:
            row["subscribers"] = int(metrics["subscribers"])
        existing_impressions = row.get("impressions")
        if existing_impressions is None and metrics.get("impressions") is not None:
            row["impressions"] = int(metrics["impressions"])
        elif existing_impressions is None and thumbnail_supported:
            row["impressions"] = 0

        existing_ctr = row.get("impressionsClickThroughRate")
        if existing_ctr is None and "impressions_click_through_rate" in metrics:
            row["impressionsClickThroughRate"] = metrics.get("impressions_click_through_rate")
        elif existing_ctr is None and thumbnail_supported:
            row["impressionsClickThroughRate"] = None


def _aggregate_supported_video_metrics(video_metrics: dict):
    weighted_average_percentage = 0.0
    weighted_average_percentage_views = 0
    engaged_views_total = 0
    has_engaged_views = False

    for metrics in (video_metrics or {}).values():
        views_value = metrics.get("views")
        average_percentage_value = metrics.get("average_view_percentage")
        if average_percentage_value is not None and views_value is not None:
            try:
                views_int = int(views_value or 0)
                if views_int > 0:
                    weighted_average_percentage += float(average_percentage_value) * views_int
                    weighted_average_percentage_views += views_int
            except Exception:
                pass

        engaged_views_value = metrics.get("engaged_views")
        if engaged_views_value is not None:
            has_engaged_views = True
            try:
                engaged_views_total += int(engaged_views_value or 0)
            except Exception:
                pass

    return {
        "averagePercentageViewed": (
            weighted_average_percentage / weighted_average_percentage_views
            if weighted_average_percentage_views > 0
            else None
        ),
        "engagedViews": engaged_views_total if has_engaged_views else None,
    }


def _should_hide_private_content_row(row: dict) -> bool:
    privacy_status = str(row.get("privacy_status") or row.get("privacyStatus") or "").strip().lower()
    if privacy_status and privacy_status != "private":
        return False
    try:
        watch_time_hours = float(
            row.get("watchTimeHours")
            or row.get("watch_time_hours")
            or 0
        )
    except Exception:
        watch_time_hours = 0.0
    return privacy_status == "private" and watch_time_hours <= 0


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


def _decode_content_cache_payload(payload):
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        return None
    if payload.get("encoding") != "gzip+base64":
        return payload

    encoded = str(payload.get("data") or "").strip()
    if not encoded:
        return None

    raw_bytes = gzip.decompress(base64.b64decode(encoded))
    decoded = json.loads(raw_bytes.decode("utf-8"))
    return decoded if isinstance(decoded, dict) else None


def _encode_content_cache_payload(payload: dict, cache_label: str) -> str:
    raw_json = json.dumps(payload, default=str)
    raw_bytes = raw_json.encode("utf-8")
    if len(raw_bytes) <= _CONTENT_CACHE_COMPRESS_MIN_BYTES:
        if len(raw_bytes) > _CONTENT_CACHE_MAX_JSONB_BYTES:
            raise ValueError(
                f"{cache_label} payload is too large for JSONB ({len(raw_bytes)} bytes)"
            )
        return raw_json

    compressed_bytes = gzip.compress(raw_bytes, compresslevel=5)
    wrapped_json = json.dumps(
        {
            "version": payload.get("version", CONTENT_CACHE_VERSION),
            "encoding": "gzip+base64",
            "size_bytes": len(raw_bytes),
            "data": base64.b64encode(compressed_bytes).decode("ascii"),
        }
    )
    wrapped_bytes = wrapped_json.encode("utf-8")
    if len(wrapped_bytes) > _CONTENT_CACHE_MAX_JSONB_BYTES:
        raise ValueError(
            f"{cache_label} payload is too large for JSONB even after compression "
            f"({len(wrapped_bytes)} bytes)"
        )
    return wrapped_json


def _ensure_timeseries_cache_table() -> None:
    if not _mark_ensured("timeseries_cache"):
        return
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
        _unmark_ensured("timeseries_cache")
        print("[content.cache] create table failed:", e)


def _load_timeseries_cache(account_tag: str, start_date, end_date):
    mem_key = ("ts", account_tag, start_date, end_date)
    cached = _payload_cache_get(mem_key)
    if cached is not None:
        return cached
    _ensure_timeseries_cache_table()
    try:
        with engine.connect() as conn:
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
        payload = _decode_content_cache_payload(row.get("payload"))
        if not isinstance(payload, dict) or payload.get("version") != CONTENT_CACHE_VERSION:
            return None
        rows = payload.get("rows")
        result = rows if isinstance(rows, list) else []
        _payload_cache_set(mem_key, result)
        return result
    except Exception as e:
        print("[content.cache] load failed:", e)
        return None


def _save_timeseries_cache(account_tag: str, start_date, end_date, rows):
    _ensure_timeseries_cache_table()
    try:
        payload_rows = [dict(r) for r in rows]
        _payload_cache_set(("ts", account_tag, start_date, end_date), payload_rows)
        payload = _encode_content_cache_payload(
            {
                "version": CONTENT_CACHE_VERSION,
                "rows": payload_rows,
            },
            "content timeseries cache",
        )
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
    except Exception as e:
        print("[content.cache] save failed:", e)


def _make_multi_tag_cache_key(tags: list[str]) -> str:
    """Tạo cache key duy nhất cho tập hợp nhiều account_tag."""
    normalized = sorted({
        str(tag or "").strip()
        for tag in (tags or [])
        if str(tag or "").strip()
    })
    joined = "|".join(normalized)
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()
    return f"__multi__:{len(normalized)}:{digest}"


def _load_list_cache(cache_key: str, start_date, end_date):
    """Load cache cho /list endpoint (cả single lẫn multi-channel)."""
    mem_key = ("list", cache_key, start_date, end_date)
    cached = _payload_cache_get(mem_key)
    if cached is not None:
        return cached
    _ensure_timeseries_cache_table()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT payload
                    FROM content_timeseries_cache
                    WHERE account_tag = :tag
                      AND start_date = :start_date
                      AND end_date = :end_date
                    LIMIT 1;
                """),
                {"tag": f"list:{cache_key}", "start_date": start_date, "end_date": end_date},
            ).mappings().first()
        if not row:
            return None
        payload = _decode_content_cache_payload(row.get("payload"))
        if not isinstance(payload, dict) or payload.get("version") != CONTENT_CACHE_VERSION:
            return None
        data = payload.get("data")
        if not isinstance(data, dict):
            return None
        _payload_cache_set(mem_key, data)
        return data
    except Exception as e:
        print("[content.list_cache] load failed:", e)
        return None


def _save_list_cache(cache_key: str, start_date, end_date, payload: dict):
    """Save cache cho /list endpoint."""
    _ensure_timeseries_cache_table()
    try:
        _payload_cache_set(("list", cache_key, start_date, end_date), payload)
        payload_json = _encode_content_cache_payload(
            {
                "version": CONTENT_CACHE_VERSION,
                "data": payload,
            },
            "content list cache",
        )
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO content_timeseries_cache (
                        account_tag, start_date, end_date, payload, updated_at
                    )
                    VALUES (:tag, :start_date, :end_date, :payload, NOW())
                    ON CONFLICT (account_tag, start_date, end_date) DO UPDATE SET
                        payload = EXCLUDED.payload,
                        updated_at = NOW();
                """),
                {
                    "tag": f"list:{cache_key}",
                    "start_date": start_date,
                    "end_date": end_date,
                    "payload": payload_json,
                },
            )
    except Exception as e:
        print("[content.list_cache] save failed:", e)


def _list_content_channels(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
    include_hidden: bool = False,
):
    visible, all_items = _list_content_channels_both(db, current_user)
    return all_items if include_hidden else visible


def _list_content_channels_both(db: Session, current_user):
    user_key = getattr(current_user, "id", 0) or 0
    now = time.monotonic()

    with _channels_cache_lock:
        cached = _channels_cache.get(user_key)
        if cached and (now - cached[0]) < _CHANNELS_CACHE_TTL_SEC:
            return cached[1]

    visible_items = []
    all_items = []
    success = False
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
        existing_tokens = {normalize_token_name(name) for name in list_token_names()}

        seen = set()
        for row in rows:
            value = sanitize_filename(row.account_tag or "")
            if not value or value in seen:
                continue
            if allowed is not None and value not in allowed:
                continue
            token_name = (row.token_name or "").strip()
            if not token_name:
                continue
            if normalize_token_name(token_name) not in existing_tokens:
                continue
            seen.add(value)
            label = row.selected_channel_title or row.account_tag or value
            avatar = row.selected_channel_avatar or None
            item = {"value": value, "label": label, "avatar": avatar}
            all_items.append(item)
            if not (hidden_all and value in hidden_all):
                visible_items.append(item)
        success = True
    except Exception as e:
        print("[content.channels] ERROR:", e)

    if success:
        with _channels_cache_lock:
            _channels_cache[user_key] = (now, (visible_items, all_items))

    return visible_items, all_items


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
    contentType: str = CONTENT_TYPE_ALL


@router.post("/list")
@_log_handler("content/list")
def content_list(
    req: ContentListRequest,
    skip_enrich: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    content_type = _normalize_content_type(req.contentType)
    with _time_block("content/list_channels (combined)"):
        channel_items, all_channel_items = _list_content_channels_both(db, current_user)
    requested_tags = _resolve_content_account_tags(req.channelId, channel_items, all_channel_items)
    if not requested_tags:
        return _fast_response({
            "items": [],
            "channelMetrics": {"impressions": 0, "ctr": None, "supported": False},
        })

    list_cache_key = (
        requested_tags[0] if len(requested_tags) == 1
        else _make_multi_tag_cache_key(requested_tags)
    )
    list_cache_key = _compose_content_cache_key(list_cache_key, content_type)
    if not skip_enrich:
        with _time_block("content/load_list_cache"):
            cached_list = _load_list_cache(list_cache_key, req.start, req.end)
        if cached_list is not None:
            add_log("[T] content/list: served from cache")
            return _fast_response(cached_list)

    account_filter_sql, account_filter_params = _build_account_tag_filter(
        "v.account_tag",
        requested_tags,
    )
    content_type_filter_sql, _ = _build_content_type_filter_sql(content_type, "v")
    with _time_block("content/ensure_tables (DDL)"):
        _ensure_thumbnail_daily_table()
        _ensure_video_daily_stats_metrics_columns()
    average_view_percentage_expr = _sql_average_view_percentage_expr()
    engaged_views_expr = _sql_engaged_views_expr()
    sql = f"""
    SELECT
        v.video_id      AS "videoId",
        v.account_tag   AS "channelId",
        v.title,
        v.thumbnail,
        v.published_at  AS "publishedAt",
        v.duration,
        v.privacy_status AS "privacyStatus",

        COALESCE(MAX(v.views), 0) AS views,
        COALESCE(SUM(s.estimated_minutes) / 60.0, 0) AS "watchTimeHours",
        CASE
            WHEN COALESCE(SUM(s.views), 0) > 0
                THEN ROUND(SUM(COALESCE(s.average_view_duration, 0) * COALESCE(s.views, 0))::numeric / NULLIF(SUM(s.views), 0), 2)
            ELSE NULL
        END AS "averageViewDuration",

        COALESCE(SUM(s.likes), 0) AS likes,
        {average_view_percentage_expr},
        {engaged_views_expr},
        -- Sum daily stats for engagement and reach metrics
        COALESCE(SUM(s.subscribers_gained), 0) AS "subscribers",
        MAX(tr.thumbnail_impressions) AS impressions,

        CASE
            WHEN MAX(tr.thumbnail_impressions) IS NOT NULL
                THEN MAX(tr.thumbnail_ctr) * 100.0
            ELSE NULL
        END AS "impressionsClickThroughRate",
        
        COALESCE(v.card_impressions, 0) AS "cardImpressions",
        COALESCE(v.ad_impressions, 0) AS "adImpressions"
    FROM videos v
    LEFT JOIN video_daily_stats s
      ON s.video_id = v.video_id
     AND s.day BETWEEN :start AND :end
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
        WHERE day BETWEEN :start AND :end
        GROUP BY account_tag, video_id
        ) tr
      ON tr.video_id = v.video_id
     AND tr.account_tag = v.account_tag
    WHERE {account_filter_sql}
      AND {content_type_filter_sql}
    GROUP BY
        v.video_id,
        v.account_tag,
        v.title,
        v.thumbnail,
        v.published_at,
        v.duration,
        v.privacy_status,
        v.ctr,
        v.card_impressions,
        v.ad_impressions
    HAVING SUM(s.views) > 0
        OR MAX(v.views) > 0
        OR (
            v.published_at IS NOT NULL
            AND v.published_at BETWEEN :start AND :end
        )
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

    metrics_by_channel = {}
    thumbnail_supported_by_channel = {}
    rows_by_channel = {}
    for row in rows_mutable:
        channel_id = str(row.get("channelId") or "").strip()
        if not channel_id or not row.get("videoId"):
            continue
        rows_by_channel.setdefault(channel_id, []).append(row)

    if not skip_enrich:
        with _time_block(
            f"content/enrich_video_metrics (channels={len(rows_by_channel)})"
        ):
            for channel_id, channel_rows in rows_by_channel.items():
                video_ids = [str(row.get("videoId")) for row in channel_rows if row.get("videoId")]
                if not video_ids:
                    continue
                video_metrics, thumbnail_supported = _load_or_fetch_video_metrics(
                    db,
                    channel_id,
                    req.start,
                    req.end,
                    video_ids,
                )
                metrics_by_channel[channel_id] = video_metrics
                thumbnail_supported_by_channel[channel_id] = thumbnail_supported
                _apply_video_metrics_to_content_rows(channel_rows, video_metrics, thumbnail_supported)

    with _time_block("content/compute_channel_metrics"):
        channel_metrics_payload = _compute_channel_metrics_from_db_for_accounts(
            requested_tags,
            req.start,
            req.end,
            content_type=content_type,
        )

    rows_mutable = [row for row in rows_mutable if not _should_hide_private_content_row(row)]

    result = {
        "items": rows_mutable,
        "channelMetrics": channel_metrics_payload,
    }
    if not skip_enrich:
        with _time_block("content/save_list_cache"):
            _save_list_cache(list_cache_key, req.start, req.end, result)
    return _fast_response(result)

class TimeSeriesRequest(BaseModel):
    start: date
    end: date
    channelId: str  # = account_tag
    contentType: str = CONTENT_TYPE_ALL
    topVideoIds: Optional[list[str]] = None


class ChannelMetricsRequest(BaseModel):
    start: date
    end: date
    channelId: str
    contentType: str = CONTENT_TYPE_ALL


@router.post("/timeseries")
@_log_handler("content/timeseries")
def content_timeseries(
    req: TimeSeriesRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    content_type = _normalize_content_type(req.contentType)
    with _time_block("content/timeseries_channels (combined)"):
        channel_items, all_channel_items = _list_content_channels_both(db, current_user)
    requested_tags = _resolve_content_account_tags(req.channelId, channel_items, all_channel_items)
    if not requested_tags:
        return _fast_response({"items": []})

    label_map = {
        str(item.get("value") or ""): str(item.get("label") or item.get("value") or "")
        for item in (all_channel_items if req.channelId == ALL_CHANNELS_VALUE else channel_items)
        if item.get("value")
    }

    ts_cache_key = (
        requested_tags[0] if len(requested_tags) == 1
        else _make_multi_tag_cache_key(requested_tags)
    )
    ts_cache_key = _compose_content_cache_key(ts_cache_key, content_type)

    top_video_ids = [str(v).strip() for v in (req.topVideoIds or []) if str(v).strip()]
    if top_video_ids:
        sorted_ids = sorted(set(top_video_ids))
        digest = hashlib.sha1("|".join(sorted_ids).encode("utf-8")).hexdigest()[:12]
        ts_cache_key = f"{ts_cache_key}:top={len(sorted_ids)}:{digest}"

    with _time_block("content/load_timeseries_cache"):
        cached = _load_timeseries_cache(ts_cache_key, req.start, req.end)
    if cached is not None:
            add_log("[T] content/timeseries: served from cache")
            cached_rows = [dict(row) for row in cached]
            for row in cached_rows:
                channel_id = str(row.get("channelId") or ts_cache_key).strip()
                row["channelId"] = channel_id
                row["channelTitle"] = label_map.get(channel_id) or channel_id
            cached_rows = _filter_private_timeseries_rows(db, requested_tags, cached_rows)
            return _fast_response(_compact_timeseries_payload(cached_rows))

    account_filter_sql, account_filter_params = _build_account_tag_filter(
        "v.account_tag",
        requested_tags,
    )
    content_type_filter_sql, _ = _build_content_type_filter_sql(content_type, "v")
    with _time_block("content/timeseries_ensure_tables (DDL)"):
        _ensure_thumbnail_daily_table()
        _ensure_video_daily_stats_metrics_columns()
    timeseries_average_view_percentage_expr = _sql_timeseries_average_view_percentage_expr()
    timeseries_engaged_views_expr = _sql_timeseries_engaged_views_expr()

    top_filter_sql = ""
    top_filter_params: dict = {}
    if top_video_ids:
        placeholders = []
        for idx, vid in enumerate(top_video_ids):
            key = f"top_vid_{idx}"
            placeholders.append(f":{key}")
            top_filter_params[key] = vid
        top_filter_sql = f" AND v.video_id IN ({', '.join(placeholders)})"

    sql = f"""
        SELECT
            s.day                  AS bucket,
            v.video_id             AS "videoId",
            v.account_tag          AS "channelId",
            v.title                AS title,

            s.views                AS views,
            (s.estimated_minutes / 60.0) AS watch_hours,
            s.average_view_duration AS "averageViewDuration",
            {timeseries_average_view_percentage_expr},
            {timeseries_engaged_views_expr},

            s.likes                AS likes,
            0::numeric             AS revenue,
            t.thumbnail_impressions::bigint AS impressions
        FROM video_daily_stats s
        JOIN videos v
          ON v.video_id = s.video_id
        LEFT JOIN video_thumbnail_daily t
          ON t.account_tag = v.account_tag
         AND t.video_id = v.video_id
         AND t.day = s.day
        WHERE {account_filter_sql}
          AND {content_type_filter_sql}
          AND s.day BETWEEN :start AND :end
          {top_filter_sql}
        ORDER BY
            bucket ASC,
            "channelId" ASC,
            "videoId" ASC;
    """

    params = {
        "start": req.start,
        "end": req.end,
        **account_filter_params,
        **top_filter_params,
    }

    with _time_block("content/timeseries_query"):
        rows = [dict(row) for row in query_all_safe(sql, params)]
    for row in rows:
        channel_id = str(row.get("channelId") or "").strip()
        row["channelTitle"] = label_map.get(channel_id) or channel_id
    rows = _filter_private_timeseries_rows(db, requested_tags, rows)

    with _time_block("content/save_timeseries_cache"):
        _save_timeseries_cache(ts_cache_key, req.start, req.end, rows)
    return _fast_response(_compact_timeseries_payload(rows))


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


def _compute_channel_metrics_from_db(
    account_tag: str,
    start_date: date,
    end_date: date,
    content_type: str = CONTENT_TYPE_ALL,
):
    return _compute_channel_metrics_from_db_for_accounts(
        [account_tag],
        start_date,
        end_date,
        content_type=content_type,
    )


def _compute_channel_metrics_from_db_for_accounts(
    account_tags,
    start_date: date,
    end_date: date,
    content_type: str = CONTENT_TYPE_ALL,
):
    account_filter_sql, account_filter_params = _build_account_tag_filter(
        "v.account_tag",
        account_tags,
    )
    content_type_filter_sql, _ = _build_content_type_filter_sql(content_type, "v")
    _ensure_thumbnail_daily_table()
    _ensure_video_daily_stats_metrics_columns()
    sql = f"""
        WITH per_video AS (
            SELECT
                v.account_tag,
                v.video_id,
                MAX(tr.thumbnail_impressions) AS impressions,
                CASE
                    WHEN MAX(tr.thumbnail_impressions) IS NOT NULL
                        THEN MAX(tr.thumbnail_ctr) * 100.0
                    ELSE NULL
                END AS ctr,
                CASE
                    WHEN MAX(tr.has_rows) > 0 THEN 1
                    ELSE 0
                END AS has_thumbnail
            FROM videos v
            LEFT JOIN video_daily_stats s
              ON s.video_id = v.video_id
             AND s.day BETWEEN :start_date AND :end_date
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
                    END AS thumbnail_ctr,
                    COUNT(*) AS has_rows
                FROM video_thumbnail_daily
                WHERE day BETWEEN :start_date AND :end_date
                GROUP BY account_tag, video_id
            ) tr
             ON tr.video_id = v.video_id
             AND tr.account_tag = v.account_tag
            WHERE {account_filter_sql}
              AND {content_type_filter_sql}
            GROUP BY v.account_tag, v.video_id
        )
        SELECT
            SUM(impressions) AS impressions,
            CASE
                WHEN SUM(impressions) > 0
                    THEN SUM(COALESCE(ctr, 0) * impressions) / SUM(impressions)
                ELSE NULL
            END AS ctr,
            COALESCE(SUM(has_thumbnail), 0) AS thumbnail_rows
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
    raw_impressions = payload.get("impressions")
    impressions = int(raw_impressions) if raw_impressions is not None else None
    ctr = payload.get("ctr")
    ctr = float(ctr) if ctr is not None else None
    thumbnail_rows = int(payload.get("thumbnail_rows") or 0)
    return {
        "impressions": impressions,
        "ctr": ctr,
        "supported": thumbnail_rows > 0,
    }


@router.post("/channel-metrics")
def channel_metrics(
    req: ChannelMetricsRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    content_type = _normalize_content_type(req.contentType)
    channel_items, all_channel_items = _list_content_channels_both(db, current_user)
    requested_tags = _resolve_content_account_tags(req.channelId, channel_items, all_channel_items)
    if not requested_tags:
        return {"impressions": 0, "ctr": None, "supported": False}
    return _compute_channel_metrics_from_db_for_accounts(
        requested_tags,
        req.start,
        req.end,
        content_type=content_type,
    )


# ---------------------------------------------------------------------------
# All Channels Summary endpoint
# ---------------------------------------------------------------------------

class AllChannelsSummaryRequest(BaseModel):
    start: date
    end: date
    contentType: str = CONTENT_TYPE_ALL


@router.post("/all_channels")
def content_all_channels(
    req: AllChannelsSummaryRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    content_type = _normalize_content_type(req.contentType)
    channel_items, all_channel_items = _list_content_channels_both(db, current_user)
    requested_tags = _resolve_content_account_tags(ALL_CHANNELS_VALUE, channel_items, all_channel_items)

    if not requested_tags:
        return _fast_response({"channels": [], "timeseries": [], "channelMetrics": {"impressions": 0, "ctr": None, "supported": False}})

    label_map = {str(item.get("value") or ""): str(item.get("label") or item.get("value") or "") for item in all_channel_items if item.get("value")}
    avatar_map = {str(item.get("value") or ""): item.get("avatar") or None for item in all_channel_items if item.get("value")}

    cache_key = f"all_channels:{_make_multi_tag_cache_key(requested_tags) if len(requested_tags) > 1 else requested_tags[0]}"
    cache_key = _compose_content_cache_key(cache_key, content_type)
    cached = _load_list_cache(cache_key, req.start, req.end)
    if cached is not None:
        return _fast_response(cached)

    account_filter_sql, account_filter_params = _build_account_tag_filter("v.account_tag", requested_tags)
    content_type_filter_sql, _ = _build_content_type_filter_sql(content_type, "v")
    _ensure_thumbnail_daily_table()
    _ensure_video_daily_stats_metrics_columns()
    average_view_percentage_expr = _sql_average_view_percentage_expr()
    engaged_views_expr = _sql_engaged_views_expr()
    all_channels_timeseries_average_view_duration_expr = _sql_timeseries_average_view_duration_expr()
    all_channels_timeseries_average_view_percentage_expr = _sql_average_view_percentage_expr(output_alias='"averagePercentageViewed"')
    all_channels_timeseries_engaged_views_expr = _sql_engaged_views_expr(output_alias='"engagedViews"')
    params = {"start": req.start, "end": req.end, **account_filter_params}

    channels_sql = f"""
        SELECT
            v.account_tag AS "channelId",
            COUNT(DISTINCT v.video_id) AS "videoCount",
            COALESCE(SUM(s.views), MAX(v.views), 0) AS views,
            COALESCE(SUM(s.estimated_minutes) / 60.0, 0) AS "watchTimeHours",
            COALESCE(SUM(s.likes), 0) AS likes,
            COALESCE(SUM(s.subscribers_gained), 0) AS subscribers,
            CASE WHEN SUM(s.views) > 0
                THEN ROUND(SUM(COALESCE(s.average_view_duration, 0) * COALESCE(s.views, 0))::numeric / NULLIF(SUM(s.views), 0), 2)
                ELSE NULL END AS "averageViewDuration",
            {average_view_percentage_expr},
            {engaged_views_expr},
            COALESCE(SUM(tr.thumbnail_impressions), 0) AS impressions,
            CASE WHEN SUM(tr.thumbnail_impressions) > 0
                THEN ROUND(SUM(COALESCE(tr.thumbnail_ctr, 0) * COALESCE(tr.thumbnail_impressions, 0))::numeric / NULLIF(SUM(tr.thumbnail_impressions), 0) * 100.0, 4)
                ELSE NULL END AS "impressionsClickThroughRate",
            MAX(v.published_at) AS "latestPublishedAt"
        FROM videos v
        LEFT JOIN video_daily_stats s ON s.video_id = v.video_id AND s.day BETWEEN :start AND :end
        LEFT JOIN (
            SELECT account_tag, video_id,
                SUM(thumbnail_impressions) AS thumbnail_impressions,
                CASE WHEN SUM(thumbnail_impressions) > 0
                    THEN SUM(COALESCE(thumbnail_ctr, 0) * thumbnail_impressions) / SUM(thumbnail_impressions)
                    ELSE NULL END AS thumbnail_ctr
            FROM video_thumbnail_daily
            WHERE day BETWEEN :start AND :end
            GROUP BY account_tag, video_id
        ) tr ON tr.video_id = v.video_id AND tr.account_tag = v.account_tag
        WHERE {account_filter_sql}
          AND {content_type_filter_sql}
        GROUP BY v.account_tag
        HAVING COALESCE(SUM(s.views), 0) > 0 OR MAX(COALESCE(v.views, 0)) > 0
        ORDER BY COALESCE(SUM(s.views), MAX(v.views), 0) DESC;
    """

    timeseries_sql = f"""
        SELECT
            s.day AS bucket,
            SUM(s.views) AS views,
            SUM(s.estimated_minutes) / 60.0 AS watch_hours,
            {all_channels_timeseries_average_view_duration_expr},
            {all_channels_timeseries_average_view_percentage_expr},
            {all_channels_timeseries_engaged_views_expr},
            SUM(s.likes) AS likes
        FROM video_daily_stats s
        JOIN videos v ON v.video_id = s.video_id
        WHERE {account_filter_sql}
          AND {content_type_filter_sql}
          AND s.day BETWEEN :start AND :end
        GROUP BY s.day
        ORDER BY s.day ASC;
    """

    channels = [dict(r) for r in query_all_safe(channels_sql, params)]
    for ch in channels:
        cid = str(ch.get("channelId") or "").strip()
        ch["channelTitle"] = label_map.get(cid) or cid
        ch["channelAvatar"] = avatar_map.get(cid)
        ch["id"] = cid
        ch["title"] = ch["channelTitle"]
        ch["displayTitle"] = ch["channelTitle"]
        ch["published"] = ch.get("latestPublishedAt")
        # Only enrich with video metrics from cache — do NOT make new YouTube API calls here
        # to avoid blocking the all_channels response for 30-60s per channel.
        # averagePercentageViewed and engagedViews are already computed from video_daily_stats SQL above.
        cached_payload = _load_video_metrics_cache(cid, req.start, req.end)
        cached_metrics, _ = _normalize_video_metrics_cache_payload(cached_payload)
        if cached_metrics:
            aggregated_metrics = _aggregate_supported_video_metrics(cached_metrics)
            if aggregated_metrics.get("averagePercentageViewed") is not None:
                ch["averagePercentageViewed"] = aggregated_metrics["averagePercentageViewed"]
            if aggregated_metrics.get("engagedViews") is not None:
                ch["engagedViews"] = aggregated_metrics["engagedViews"]

    timeseries = [dict(r) for r in query_all_safe(timeseries_sql, params)]
    channel_metrics = _compute_channel_metrics_from_db_for_accounts(
        requested_tags,
        req.start,
        req.end,
        content_type=content_type,
    )

    result = {"channels": channels, "timeseries": timeseries, "channelMetrics": channel_metrics}
    _save_list_cache(cache_key, req.start, req.end, result)
    return _fast_response(result)


# ---------------------------------------------------------------------------
# Cache pre-warming
# ---------------------------------------------------------------------------

PREWARM_PERIODS_DAYS = [7, 28, 90]


def _get_all_account_tags_from_db() -> list[str]:
    """Lấy tất cả account_tag từ bảng videos (không qua auth)."""
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text("SELECT DISTINCT account_tag FROM videos WHERE account_tag IS NOT NULL")
            ).fetchall()
        return [str(r[0]).strip() for r in rows if r[0]]
    except Exception as e:
        print("[content.prewarm] get tags failed:", e)
        return []


def _prewarm_worker() -> None:
    import time
    time.sleep(8)  # Đợi server khởi động xong

    print("[content.prewarm] starting cache pre-warm...")
    all_tags = _get_all_account_tags_from_db()
    if not all_tags:
        print("[content.prewarm] no channels found, skipping")
        return

    cache_key = _make_multi_tag_cache_key(all_tags) if len(all_tags) > 1 else all_tags[0]
    cache_key = _compose_content_cache_key(cache_key, CONTENT_TYPE_ALL)
    account_filter_sql, account_filter_params = _build_account_tag_filter("v.account_tag", all_tags)
    today = date.today()

    for days in PREWARM_PERIODS_DAYS:
        start = today - timedelta(days=days)
        end = today

        # --- Pre-warm /list ---
        if _load_list_cache(cache_key, start, end) is None:
            try:
                _ensure_thumbnail_daily_table()
                _ensure_video_daily_stats_metrics_columns()
                average_view_percentage_expr = _sql_average_view_percentage_expr()
                engaged_views_expr = _sql_engaged_views_expr()
                list_sql = f"""
                    SELECT
                        v.video_id      AS "videoId",
                        v.account_tag   AS "channelId",
                        v.title,
                        v.thumbnail,
                        v.published_at  AS "publishedAt",
                        v.duration,
                        v.privacy_status AS "privacyStatus",
                        COALESCE(MAX(v.views), 0) AS views,
                        COALESCE(SUM(s.estimated_minutes) / 60.0, 0) AS "watchTimeHours",
                        CASE WHEN COALESCE(SUM(s.views), 0) > 0
                            THEN ROUND(SUM(COALESCE(s.average_view_duration, 0) * COALESCE(s.views, 0))::numeric / NULLIF(SUM(s.views), 0), 2)
                            ELSE NULL END AS "averageViewDuration",
                        COALESCE(SUM(s.likes), 0) AS likes,
                        COALESCE(SUM(s.subscribers_gained), 0) AS "subscribers",
                        {average_view_percentage_expr},
                        {engaged_views_expr},
                        MAX(tr.thumbnail_impressions) AS impressions,
                        CASE
                            WHEN MAX(tr.thumbnail_impressions) IS NOT NULL
                                THEN MAX(tr.thumbnail_ctr) * 100.0
                            ELSE NULL
                        END AS "impressionsClickThroughRate",
                        COALESCE(v.card_impressions, 0) AS "cardImpressions",
                        COALESCE(v.ad_impressions, 0) AS "adImpressions"
                    FROM videos v
                    LEFT JOIN video_daily_stats s
                      ON s.video_id = v.video_id AND s.day BETWEEN :start AND :end
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
                        WHERE day BETWEEN :start AND :end
                        GROUP BY account_tag, video_id
                    ) tr
                      ON tr.video_id = v.video_id
                     AND tr.account_tag = v.account_tag
                    WHERE {account_filter_sql}
                    GROUP BY v.video_id, v.account_tag, v.title, v.thumbnail,
                             v.published_at, v.duration, v.privacy_status, v.ctr, v.card_impressions, v.ad_impressions
                    HAVING SUM(s.views) > 0
                        OR MAX(v.views) > 0
                        OR (
                            v.published_at IS NOT NULL
                            AND v.published_at BETWEEN :start AND :end
                        )
                    ORDER BY v.published_at DESC;
                """
                params = {"start": start, "end": end, **account_filter_params}
                rows = [dict(r) for r in query_all_safe(list_sql, params)]
                channel_metrics = _compute_channel_metrics_from_db_for_accounts(all_tags, start, end)
                result = {"items": rows, "channelMetrics": channel_metrics}
                _save_list_cache(cache_key, start, end, result)
                print(f"[content.prewarm] list cached: last {days}d ({len(rows)} videos)")
            except Exception as e:
                print(f"[content.prewarm] list failed for last {days}d:", e)

        # --- Pre-warm /timeseries ---
        if _load_timeseries_cache(cache_key, start, end) is None:
            try:
                _ensure_thumbnail_daily_table()
                _ensure_video_daily_stats_metrics_columns()
                timeseries_average_view_percentage_expr = _sql_timeseries_average_view_percentage_expr()
                timeseries_engaged_views_expr = _sql_timeseries_engaged_views_expr()
                ts_sql = f"""
                    SELECT
                        s.day           AS bucket,
                        v.video_id      AS "videoId",
                        v.account_tag   AS "channelId",
                        v.title         AS title,
                        s.views         AS views,
                        (s.estimated_minutes / 60.0) AS watch_hours,
                        s.average_view_duration AS "averageViewDuration",
                        {timeseries_average_view_percentage_expr},
                        {timeseries_engaged_views_expr},
                        s.likes         AS likes,
                        0::numeric      AS revenue,
                        t.thumbnail_impressions::bigint AS impressions
                    FROM video_daily_stats s
                    JOIN videos v ON v.video_id = s.video_id
                    LEFT JOIN video_thumbnail_daily t
                      ON t.account_tag = v.account_tag AND t.video_id = v.video_id AND t.day = s.day
                    WHERE {account_filter_sql}
                      AND s.day BETWEEN :start AND :end
                    ORDER BY bucket ASC, "channelId" ASC, "videoId" ASC;
                """
                params = {"start": start, "end": end, **account_filter_params}
                rows = [dict(r) for r in query_all_safe(ts_sql, params)]
                _save_timeseries_cache(cache_key, start, end, rows)
                print(f"[content.prewarm] timeseries cached: last {days}d ({len(rows)} rows)")
            except Exception as e:
                print(f"[content.prewarm] timeseries failed for last {days}d:", e)

    print("[content.prewarm] done")


def prewarm_content_cache() -> None:
    """Khởi động background thread để pre-warm cache khi server start."""
    t = threading.Thread(target=_prewarm_worker, daemon=True, name="content-prewarm")
    t.start()
