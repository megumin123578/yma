import threading
from datetime import date, timedelta

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user_optional
from python_backend.api.auth.database import get_db
from python_backend.db import engine

from .common import (
    router,
    ALL_CHANNELS_VALUE,
    CONTENT_TYPE_ALL,
    _aggregate_supported_video_metrics,
    _build_account_tag_filter,
    _build_content_type_filter_sql,
    _compose_content_cache_key,
    _compute_channel_metrics_from_db_for_accounts,
    _ensure_thumbnail_daily_table,
    _ensure_video_daily_stats_metrics_columns,
    _fast_response,
    _list_content_channels_both,
    _load_list_cache,
    _load_timeseries_cache,
    _load_video_metrics_cache,
    _make_multi_tag_cache_key,
    _normalize_content_type,
    _normalize_video_metrics_cache_payload,
    _resolve_content_account_tags,
    _save_list_cache,
    _save_timeseries_cache,
    _sql_average_view_percentage_expr,
    _sql_engaged_views_expr,
    _sql_timeseries_average_view_duration_expr,
    _sql_timeseries_average_view_percentage_expr,
    _sql_timeseries_engaged_views_expr,
    query_all_safe,
)


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
