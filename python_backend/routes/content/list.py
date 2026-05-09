from datetime import date

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
    _apply_video_metrics_to_content_rows,
    _build_account_tag_filter,
    _build_content_type_filter_sql,
    _compose_content_cache_key,
    _compute_channel_metrics_from_db_for_accounts,
    _ensure_thumbnail_daily_table,
    _ensure_video_daily_stats_metrics_columns,
    _fast_response,
    _list_content_channels_both,
    _load_list_cache,
    _load_or_fetch_video_metrics,
    _log_handler,
    _make_multi_tag_cache_key,
    _normalize_content_type,
    _resolve_content_account_tags,
    _save_list_cache,
    _should_hide_private_content_row,
    _sql_average_view_percentage_expr,
    _sql_engaged_views_expr,
    _time_block,
    query_all_safe,
)


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

