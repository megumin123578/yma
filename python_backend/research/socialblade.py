"""
Lấy dữ liệu tăng trưởng theo ngày từ socialblade.com.

Mục đích sử dụng: cá nhân, không thương mại. Tương đương việc user tự
copy số liệu từ trang. Có cache 6 giờ để không gọi nhiều.

Cấu trúc data Social Blade (Next.js):
  pageProps.trpcState.json.queries[N].state.data
  → list 15 entry {date, subscribers, views, videos}
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional


CACHE_DIR = Path.home() / ".youtube_research" / "sb_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_HOURS = 2  # 21/05: giảm từ 6h → 2h để daily run sáng (4-7h) sau khi
                     # SB close ngày trước (0h UTC = 7h VN) sẽ refresh data mới
                     # chứ không xài cache 6h từ daily run hôm trước.

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def _cache_path(channel_id: str) -> Path:
    return CACHE_DIR / f"{channel_id}.json"


def _load_cache(channel_id: str) -> Optional[dict]:
    p = _cache_path(channel_id)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        age_h = (time.time() - data.get("_cache_ts", 0)) / 3600
        if age_h > CACHE_TTL_HOURS:
            return None
        return data
    except Exception:
        return None


def _save_cache(channel_id: str, data: dict) -> None:
    p = _cache_path(channel_id)
    try:
        out = dict(data)
        out["_cache_ts"] = time.time()
        p.write_text(json.dumps(out, ensure_ascii=False),
                     encoding="utf-8")
    except Exception:
        pass


def _fetch_html(channel_id: str, timeout: int = 15) -> Optional[str]:
    url = f"https://socialblade.com/youtube/channel/{channel_id}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,*/*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _extract_next_data(html: str) -> Optional[dict]:
    """Trích __NEXT_DATA__ JSON từ HTML Next.js."""
    m = re.search(
        r'<script\s+id="__NEXT_DATA__"\s+type="application/json"[^>]*>(.+?)</script>',
        html, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def _find_daily_stats(data: dict) -> Optional[list]:
    """Lùng dict tìm array có keys ['date', 'subscribers', 'views', 'videos']."""
    found = []

    def walk(obj):
        if isinstance(obj, list):
            if obj and isinstance(obj[0], dict):
                keys = set(obj[0].keys())
                if {"date", "subscribers", "views"}.issubset(keys):
                    found.append(obj)
            for item in obj:
                walk(item)
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v)

    walk(data)
    # Lấy array dài nhất (thường là full history)
    if not found:
        return None
    return max(found, key=len)


def get_channel_growth(channel_id: str,
                       force_refresh: bool = False) -> dict:
    """Trả về dict {channel_id, daily_stats, summary, error}.

    daily_stats: list các entry {date, subscribers, views, videos,
                                  subs_change, views_change, videos_change}
    summary: dict {total_days, latest_subs, latest_views,
                   avg_daily_subs, avg_daily_views, growth_subs, growth_views}
    """
    if not channel_id or not channel_id.startswith("UC"):
        return {"error": "channel_id không hợp lệ (cần bắt đầu UC...)",
                "channel_id": channel_id}

    if not force_refresh:
        cached = _load_cache(channel_id)
        if cached:
            return cached

    html = _fetch_html(channel_id)
    if not html:
        return {"error": "Không tải được trang Social Blade",
                "channel_id": channel_id}

    data = _extract_next_data(html)
    if not data:
        return {"error": "Không parse được __NEXT_DATA__ (HTML đổi cấu trúc?)",
                "channel_id": channel_id}

    daily = _find_daily_stats(data)
    if not daily:
        return {"error": "Không tìm được mảng daily stats trong data",
                "channel_id": channel_id}

    # Sort theo ngày tăng dần (cũ → mới)
    try:
        daily_sorted = sorted(daily, key=lambda x: x.get("date", ""))
    except Exception:
        daily_sorted = daily

    # Tính delta hàng ngày
    enriched = []
    prev = None
    for entry in daily_sorted:
        e = dict(entry)
        try:
            cur_subs = int(entry.get("subscribers") or 0)
            cur_views = int(entry.get("views") or 0)
            cur_videos = int(entry.get("videos") or 0)
        except Exception:
            cur_subs = cur_views = cur_videos = 0
        if prev:
            e["subs_change"] = cur_subs - prev["_subs"]
            e["views_change"] = cur_views - prev["_views"]
            e["videos_change"] = cur_videos - prev["_videos"]
        else:
            e["subs_change"] = 0
            e["views_change"] = 0
            e["videos_change"] = 0
        e["_subs"] = cur_subs
        e["_views"] = cur_views
        e["_videos"] = cur_videos
        enriched.append(e)
        prev = {"_subs": cur_subs, "_views": cur_views, "_videos": cur_videos}

    # Summary
    summary = {}
    if enriched:
        last = enriched[-1]
        summary["total_days"] = len(enriched)
        summary["latest_subs"] = last["_subs"]
        summary["latest_views"] = last["_views"]
        summary["latest_videos"] = last["_videos"]
        summary["latest_date"] = last.get("date", "")

        # Trung bình tăng trưởng hàng ngày (bỏ entry đầu tiên = 0 change)
        changes_subs = [e["subs_change"] for e in enriched[1:]]
        changes_views = [e["views_change"] for e in enriched[1:]]
        if changes_subs:
            summary["avg_daily_subs"] = sum(changes_subs) / len(changes_subs)
            summary["max_daily_subs"] = max(changes_subs)
            summary["min_daily_subs"] = min(changes_subs)
        if changes_views:
            summary["avg_daily_views"] = sum(changes_views) / len(changes_views)
            summary["max_daily_views"] = max(changes_views)
            summary["min_daily_views"] = min(changes_views)

        # Tăng trưởng tổng cộng trong giai đoạn
        first = enriched[0]
        summary["period_subs_growth"] = last["_subs"] - first["_subs"]
        summary["period_views_growth"] = last["_views"] - first["_views"]

    # Clean internal fields
    for e in enriched:
        e.pop("_subs", None)
        e.pop("_views", None)
        e.pop("_videos", None)

    result = {
        "channel_id": channel_id,
        "daily_stats": enriched,
        "summary": summary,
        "source": "socialblade.com",
        "error": "",
    }
    _save_cache(channel_id, result)
    return result


def load_cached_growth(channel_id: str) -> Optional[dict]:
    """Đọc dữ liệu Social Blade từ cache trên đĩa, BỎ QUA hạn cache.

    Dùng khi tạo báo cáo: cần số liệu ngay, không gọi mạng. Dữ liệu
    hơi cũ vẫn tốt hơn không có. Trả None nếu chưa từng cache."""
    if not channel_id:
        return None
    p = _cache_path(channel_id)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("error"):
            return None
        return data
    except Exception:
        return None


def make_sparkline(values: list, width: int = 20) -> str:
    """Tạo sparkline từ list số (▁▂▃▄▅▆▇█). Chỉ lấy `width` điểm cuối."""
    if not values:
        return ""
    vals = values[-width:]
    bars = "▁▂▃▄▅▆▇█"
    lo = min(vals)
    hi = max(vals)
    if hi == lo:
        return bars[3] * len(vals)
    out = []
    for v in vals:
        idx = int((v - lo) / (hi - lo) * (len(bars) - 1))
        out.append(bars[max(0, min(idx, len(bars) - 1))])
    return "".join(out)
