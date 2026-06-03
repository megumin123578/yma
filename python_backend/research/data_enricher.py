# -*- coding: utf-8 -*-
"""CÔNG ĐOẠN 2: Enrich full data từ ID — qua YouTube Data API v3.

Pattern (chốt 24/05 đêm muộn): nhận list ID từ id_collector (CÔNG ĐOẠN 1),
gọi API videos.list/channels.list batch 50 ID/request (1 điểm/request),
trả về VideoInfo/ChannelInfo cùng schema V1 (drop-in replacement).

Tốc độ: 30 video → 1 request → ~0.5s (175× nhanh hơn V1 enrich 30 /watch
page ~100s). Data ĐẦY ĐỦ + sạch hơn V1 (comment_count, tags, duration
chuẩn ISO 8601).

Quota: 1 điểm/batch 50 ID. 25 WL × 10 channel × 30 video = 7,500 video
= 150 request = 150 điểm (chỉ 1.5% quota free 10K/ngày).
"""
from __future__ import annotations
import re
from datetime import datetime, timezone

from .youtube_api import (videos_list, channels_list,
                           iso_duration_to_seconds,
                           parse_iso8601_datetime)
from .youtube_client import VideoInfo, ChannelInfo


def _published_to_days_old(iso: str) -> float:
    """ISO publishedAt → days_old (float)."""
    dt = parse_iso8601_datetime(iso)
    if not dt:
        return 0.0
    now = datetime.now(timezone.utc)
    delta = now - dt
    return delta.total_seconds() / 86400.0


def _safe_int(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def enrich_videos(video_ids: list, log_fn=print) -> list:
    """Lấy full chi tiết nhiều video qua API. Trả list VideoInfo
    (cùng schema V1, drop-in cho code dùng pkl)."""
    if not video_ids:
        return []
    items = videos_list(
        video_ids,
        parts=("snippet", "statistics", "contentDetails"))
    if log_fn:
        log_fn(f"  [enrich_videos] {len(items)}/{len(video_ids)} video qua API")

    out = []
    for it in items:
        vid = it.get("id", "")
        sn = it.get("snippet", {}) or {}
        st = it.get("statistics", {}) or {}
        cd = it.get("contentDetails", {}) or {}

        title = sn.get("title", "") or ""
        description = sn.get("description", "") or ""
        published_at = sn.get("publishedAt", "") or ""
        channel_id = sn.get("channelId", "") or ""
        channel_title = sn.get("channelTitle", "") or ""
        tags = sn.get("tags", []) or []

        view_count = _safe_int(st.get("viewCount"))
        like_count = _safe_int(st.get("likeCount"))
        comment_count = _safe_int(st.get("commentCount"))

        duration_seconds = iso_duration_to_seconds(cd.get("duration", ""))
        days_old = _published_to_days_old(published_at)
        views_per_day = (view_count / days_old) if days_old > 0 else 0.0

        # VideoInfo dataclass: days_old & views_per_day là @property
        # auto-compute từ published_at + view_count, không cần set.
        v = VideoInfo(
            video_id=vid,
            title=title,
            channel_title=channel_title,
            channel_id=channel_id,
            description=description,
            tags=tags,
            published_at=published_at,
            view_count=view_count,
            like_count=like_count,
            comment_count=comment_count,
            duration_seconds=duration_seconds,
            url=f"https://www.youtube.com/watch?v={vid}",
        )
        out.append(v)
    return out


def enrich_channels(channel_ids: list, log_fn=print) -> list:
    """Lấy full chi tiết nhiều kênh qua API."""
    if not channel_ids:
        return []
    items = channels_list(
        channel_ids,
        parts=("snippet", "statistics", "brandingSettings", "contentDetails"))
    if log_fn:
        log_fn(f"  [enrich_channels] {len(items)}/{len(channel_ids)} channel qua API")

    out = []
    for it in items:
        cid = it.get("id", "")
        sn = it.get("snippet", {}) or {}
        st = it.get("statistics", {}) or {}
        bs = it.get("brandingSettings", {}) or {}
        cd = it.get("contentDetails", {}) or {}

        title = sn.get("title", "") or ""
        description = sn.get("description", "") or ""
        custom_url = sn.get("customUrl", "") or ""
        handle = custom_url.lstrip("@") if custom_url else ""

        sub_count = _safe_int(st.get("subscriberCount"))
        if st.get("hiddenSubscriberCount"):
            sub_count = 0

        view_count = _safe_int(st.get("viewCount"))
        video_count = _safe_int(st.get("videoCount"))

        kw_str = (bs.get("channel", {}) or {}).get("keywords", "") or ""
        keywords = _split_keywords_brand(kw_str)

        uploads = ((cd.get("relatedPlaylists", {}) or {})
                   .get("uploads", "") or "")

        ch = ChannelInfo(
            channel_id=cid,
            title=title,
            handle=handle,
            description=description,
            subscriber_count=sub_count,
            view_count=view_count,
            video_count=video_count,
            keywords=keywords,
            uploads_playlist_id=uploads,
            url=f"https://www.youtube.com/channel/{cid}",
        )
        out.append(ch)
    return out


_KW_QUOTE_RE = re.compile(r'"([^"]+)"|(\S+)')


def _split_keywords_brand(s: str) -> list:
    """'"diy tractor" mini farm' → ['diy tractor', 'mini', 'farm']"""
    if not s:
        return []
    out = []
    for m in _KW_QUOTE_RE.finditer(s):
        kw = m.group(1) or m.group(2)
        if kw:
            out.append(kw.strip())
    return out
