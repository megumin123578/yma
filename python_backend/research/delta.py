"""
Tính delta giữa 2 lần nghiên cứu (kết quả hiện tại vs kết quả trước).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional


def _safe_pct(new: float, old: float) -> float:
    if not old:
        return 0.0
    return (new - old) / old * 100.0


def compute_delta(current: dict, previous: dict) -> dict:
    """So sánh current với previous result, trả về dict delta để hiển thị."""
    if not previous:
        return {}

    # Ngày của lần trước
    prev_date = ""
    prev_params_date = previous.get("params", {})
    # Thử lấy date từ trường có sẵn (output_path chứa timestamp)
    try:
        prev_out = previous.get("output_path", "")
        # Format: ..._YYYYMMDD_HHMMSS.xlsx
        import re
        m = re.search(r"(\d{8}_\d{6})", prev_out)
        if m:
            prev_date = datetime.strptime(m.group(1), "%Y%m%d_%H%M%S").isoformat(timespec="seconds")
    except Exception:
        pass

    # Số liệu kênh
    cur_subs = current.get("subscriber_count", 0) or 0
    prev_subs = previous.get("subscriber_count", 0) or 0
    subs_delta = cur_subs - prev_subs

    cur_videos = current.get("video_count", 0) or 0
    prev_videos = previous.get("video_count", 0) or 0
    video_delta = cur_videos - prev_videos

    # Từ khoá
    cur_kw_set = {k.keyword.lower() for k in current.get("keywords", [])}
    prev_kw_set = {k.keyword.lower() for k in previous.get("keywords", [])}
    new_keywords = sorted(cur_kw_set - prev_kw_set)
    dropped_keywords = sorted(prev_kw_set - cur_kw_set)
    kept_keywords = cur_kw_set & prev_kw_set

    # Top videos mới xuất hiện trong tab "recent" (video mới nhiều view)
    cur_recent_videos = {}
    for kw, vids in current.get("recent_by_keyword", {}).items():
        for v in vids:
            if v.video_id not in cur_recent_videos:
                cur_recent_videos[v.video_id] = v

    prev_recent_ids = set()
    for kw, vids in previous.get("recent_by_keyword", {}).items():
        for v in vids:
            prev_recent_ids.add(v.video_id)

    new_video_ids = set(cur_recent_videos.keys()) - prev_recent_ids
    # Sort theo view count, lấy top 10 video mới xuất hiện
    new_videos = sorted(
        [cur_recent_videos[vid] for vid in new_video_ids],
        key=lambda v: v.view_count, reverse=True,
    )[:10]

    # Trending keywords: keyword nào có tổng views (trong recent_by_keyword) tăng nhiều nhất
    def _kw_total_views(result, keywords):
        out = {}
        recent = result.get("recent_by_keyword", {})
        for kw in keywords:
            vids = recent.get(kw, [])
            # tìm key case-insensitive nếu không match
            if not vids:
                for k, vs in recent.items():
                    if k.lower() == kw.lower():
                        vids = vs
                        break
            out[kw.lower()] = sum(v.view_count for v in vids)
        return out

    cur_views_by_kw = _kw_total_views(current, [k.keyword for k in current.get("keywords", [])])
    prev_views_by_kw = _kw_total_views(previous, [k.keyword for k in previous.get("keywords", [])])

    trending_kws = []
    for kw in kept_keywords:
        cur_v = cur_views_by_kw.get(kw, 0)
        prev_v = prev_views_by_kw.get(kw, 0)
        if prev_v > 0 and cur_v > prev_v * 1.3:  # tăng ≥ 30%
            trending_kws.append({
                "keyword": kw,
                "delta_views": cur_v - prev_v,
                "delta_pct": _safe_pct(cur_v, prev_v),
            })
    trending_kws.sort(key=lambda x: x["delta_pct"], reverse=True)

    # Video MỚI do CHÍNH KÊNH đăng (so danh sách video của kênh 2 lần)
    new_channel_uploads = []
    prev_ch_videos = previous.get("videos", []) or []
    if prev_ch_videos:
        prev_ch_ids = {v.video_id for v in prev_ch_videos}
        cur_ch = {v.video_id: v for v in (current.get("videos", []) or [])}
        up_ids = set(cur_ch) - prev_ch_ids
        new_channel_uploads = sorted(
            [cur_ch[i] for i in up_ids],
            key=lambda v: getattr(v, "published_at", "") or "",
            reverse=True)

    return {
        "has_delta": True,
        "previous_date": prev_date,
        "subscriber_delta": subs_delta,
        "subscriber_pct": _safe_pct(cur_subs, prev_subs),
        "video_count_delta": video_delta,
        "new_keywords": new_keywords[:15],
        "dropped_keywords": dropped_keywords[:15],
        "new_keyword_count": len(new_keywords),
        "new_videos": new_videos,
        "new_video_count": len(new_video_ids),
        "trending_keywords": trending_kws[:10],
        "new_channel_uploads": new_channel_uploads,
        "new_channel_upload_count": len(new_channel_uploads),
    }


def format_delta_summary(delta: dict) -> str:
    """Tóm tắt delta thành 1 đoạn text cho log."""
    if not delta or not delta.get("has_delta"):
        return ""
    parts = []
    if delta["subscriber_delta"]:
        sign = "+" if delta["subscriber_delta"] > 0 else ""
        parts.append(f"Subs {sign}{delta['subscriber_delta']:,} "
                     f"({sign}{delta['subscriber_pct']:.1f}%)")
    if delta["new_video_count"]:
        parts.append(f"{delta['new_video_count']} video mới xuất hiện")
    if delta["new_keyword_count"]:
        parts.append(f"{delta['new_keyword_count']} từ khoá mới")
    if delta["trending_keywords"]:
        parts.append(f"{len(delta['trending_keywords'])} từ khoá đang nóng")
    return " • ".join(parts) if parts else "không thay đổi đáng kể"
