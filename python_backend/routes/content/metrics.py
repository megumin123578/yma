import hashlib
from datetime import date
from typing import Optional

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user_optional
from python_backend.api.auth.database import get_db
from python_backend.perf_log import add_log

from .common import (
    router,
    ALL_CHANNELS_VALUE,
    CONTENT_TYPE_ALL,
    _build_account_tag_filter,
    _build_content_type_filter_sql,
    _compact_timeseries_payload,
    _compose_content_cache_key,
    _compute_channel_metrics_from_db_for_accounts,
    _ensure_thumbnail_daily_table,
    _ensure_video_daily_stats_metrics_columns,
    _fast_response,
    _filter_private_timeseries_rows,
    _list_content_channels_both,
    _load_timeseries_cache,
    _log_handler,
    _make_multi_tag_cache_key,
    _normalize_content_type,
    _resolve_content_account_tags,
    _save_timeseries_cache,
    _sql_timeseries_average_view_percentage_expr,
    _sql_timeseries_engaged_views_expr,
    _time_block,
    query_all_safe,
)


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

