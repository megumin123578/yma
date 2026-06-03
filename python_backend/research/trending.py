"""
Trending Score — phát hiện video viral vượt mức bình thường của chính kênh đó.

trending_score = views_per_day_of_video / median_views_per_day_of_channel

Video có score >= 3.0 → 🔥 VIRAL (3x mức bình thường)
Video có score >= 1.5 → 📈 trên trung bình
"""

from __future__ import annotations

from statistics import median
from typing import Optional


VIRAL_THRESHOLD = 3.0
ABOVE_AVG_THRESHOLD = 1.5


def compute_channel_baselines(result: dict) -> dict:
    """Tính median views/day cho mỗi kênh xuất hiện trong recent_by_keyword.
    Trả dict {channel_title: median_vpd}."""
    by_channel = {}
    for vids in result.get("recent_by_keyword", {}).values():
        for v in vids:
            ch = v.channel_title or "_unknown"
            by_channel.setdefault(ch, []).append(v.views_per_day)
    # Bổ sung kênh seed nếu có video kênh
    seed_videos = result.get("videos", [])
    if seed_videos:
        seed_title = (result.get("channel").title if result.get("channel") else "") or "_seed"
        seed_vpd = [v.views_per_day for v in seed_videos if v.views_per_day > 0]
        if seed_vpd:
            by_channel.setdefault(seed_title, []).extend(seed_vpd)

    baselines = {}
    for ch, vpds in by_channel.items():
        vpds = [v for v in vpds if v > 0]
        if vpds:
            baselines[ch] = median(vpds)
    return baselines


def trending_score(video, baselines: dict) -> float:
    """Tính trending score cho 1 video dựa trên baseline của kênh nó."""
    ch = video.channel_title or "_unknown"
    base = baselines.get(ch, 0)
    if base <= 0:
        return 0.0
    return video.views_per_day / base


def classify(score: float) -> str:
    """Trả về nhãn: 'viral', 'above_avg', 'normal'."""
    if score >= VIRAL_THRESHOLD:
        return "viral"
    if score >= ABOVE_AVG_THRESHOLD:
        return "above_avg"
    return "normal"


def annotate_result(result: dict) -> None:
    """Tính trending_score cho tất cả video trong result và ghi vào v.trending_score.
    Mutate in place."""
    baselines = compute_channel_baselines(result)
    result["_trending_baselines"] = baselines

    for vids in result.get("recent_by_keyword", {}).values():
        for v in vids:
            v.trending_score = trending_score(v, baselines)
    for vids in result.get("top_by_keyword", {}).values():
        for v in vids:
            v.trending_score = trending_score(v, baselines)
    for v in result.get("videos", []) or []:
        v.trending_score = trending_score(v, baselines)


def get_viral_videos(result: dict, top_n: int = 10) -> list:
    """Trả về list các video viral nhất (score >= VIRAL_THRESHOLD)."""
    all_videos = {}
    for vids in result.get("recent_by_keyword", {}).values():
        for v in vids:
            if v.video_id not in all_videos:
                all_videos[v.video_id] = v
    viral = [v for v in all_videos.values()
             if getattr(v, "trending_score", 0) >= VIRAL_THRESHOLD]
    viral.sort(key=lambda v: v.trending_score, reverse=True)
    return viral[:top_n]
