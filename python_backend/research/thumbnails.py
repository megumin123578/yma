"""
Tải thumbnail YouTube + cache trong thư mục local.
"""

from __future__ import annotations

import hashlib
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional


def cache_dir() -> Path:
    d = Path.home() / ".youtube_research" / "thumbs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def thumb_url_for(video_id: str, quality: str = "mqdefault") -> str:
    """
    quality: 'default' (120x90), 'mqdefault' (320x180),
             'hqdefault' (480x360), 'maxresdefault' (1280x720)
    """
    return f"https://i.ytimg.com/vi/{video_id}/{quality}.jpg"


def cache_path_for(video_id: str, quality: str = "mqdefault") -> Path:
    safe_id = hashlib.md5(f"{video_id}_{quality}".encode()).hexdigest()[:16]
    return cache_dir() / f"{video_id}_{quality}.jpg"


def download_thumbnail(video_id: str, quality: str = "mqdefault",
                       timeout: int = 10) -> Optional[Path]:
    """Tải thumbnail về cache. Trả Path hoặc None nếu lỗi.
    Nếu đã có trong cache, trả luôn (không tải lại)."""
    p = cache_path_for(video_id, quality)
    if p.exists() and p.stat().st_size > 100:
        return p

    url = thumb_url_for(video_id, quality)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        # YouTube trả 1x1 GIF nếu video không có thumbnail; thử quality khác
        if len(data) < 1000 and quality == "mqdefault":
            # fallback to hqdefault
            return download_thumbnail(video_id, "hqdefault", timeout)
        p.write_bytes(data)
        return p
    except Exception:
        return None


def download_many(video_ids: list, quality: str = "mqdefault",
                  on_progress=None) -> dict:
    """Tải nhiều thumbnail. Trả dict {video_id: Path | None}."""
    result = {}
    total = len(video_ids)
    for i, vid in enumerate(video_ids, 1):
        result[vid] = download_thumbnail(vid, quality)
        if on_progress:
            on_progress(i, total, vid)
    return result


def pick_videos_for_thumbnails(recent_by_keyword: dict,
                               limit: int = 30) -> list:
    """Chọn list video tiêu biểu để tải/phân tích thumbnail.

    Lấy top 2 video/từ khoá, ưu tiên kênh xuất hiện nhiều lần trong ngách
    (tránh các kênh giant generic chiếm hết slot). Trả list VideoInfo.
    """
    from collections import Counter
    rec = recent_by_keyword or {}

    # Đếm tần suất kênh xuất hiện trong ngách
    channel_freq = Counter()
    for vids in rec.values():
        seen = set()
        for v in vids:
            cid = v.channel_id or v.channel_title or ""
            if cid and cid not in seen:
                channel_freq[cid] += 1
                seen.add(cid)

    # Top 2 video/từ khoá, dedupe theo video_id
    all_videos = {}
    for vids in rec.values():
        top2 = sorted(vids, key=lambda v: v.view_count, reverse=True)[:2]
        for v in top2:
            if v.video_id and v.video_id not in all_videos:
                all_videos[v.video_id] = v

    def _sort_key(v):
        cid = v.channel_id or v.channel_title or ""
        return (channel_freq.get(cid, 0), v.view_count)

    return sorted(all_videos.values(), key=_sort_key,
                  reverse=True)[:limit]
