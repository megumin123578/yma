# -*- coding: utf-8 -*-
"""A/B Recommendation Engine — rescue video flop.

Phát hiện video flop của kênh nhà + đối thủ cùng topic ăn → đề xuất
tái upload (hoặc làm lại) với title/thumbnail "công thức của đối thủ".

LOGIC:
1. Lấy video kênh nhà có views_per_day < median × 0.3 (flop)
2. Với mỗi video flop: extract top 3 tags + keywords từ title
3. Tìm video đối thủ trong WL có cùng tags/keywords (top 3 video matching)
4. Nếu video đối thủ có views_per_day > median × 2 → đề xuất:
   - Title của đối thủ làm mẫu
   - Thumbnail concept của đối thủ
   - Tính lift_potential = (competitor_vpd - self_vpd) / self_vpd

USAGE:
    from .ab_recommender import find_rescue_candidates
    recs = find_rescue_candidates(wl_id="wl_xxx")
    # recs: list[{
    #   self_video: {title, video_id, vpd, ...},
    #   competitor_video: {title, channel, vpd, ...},
    #   matching_tags: [...],
    #   lift_potential: 5.2,
    #   suggested_new_title: "<gợi ý>",
    # }]
"""
from __future__ import annotations

import re
from statistics import median
from typing import Callable, Optional


def _normalize(text: str) -> set:
    """Tokenize + lowercase + strip → set words (for tag matching)."""
    if not text:
        return set()
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return set(w for w in text.split() if len(w) >= 3)


def _video_tags_set(video) -> set:
    """Gộp tags + title words cho 1 video → set unique tokens."""
    tags = getattr(video, "tags", []) or []
    title = getattr(video, "title", "") or ""
    s = set(t.lower().strip() for t in tags if t and len(t) >= 3)
    s |= _normalize(title)
    return s


def _video_vpd(video) -> float:
    vc = getattr(video, "view_count", 0) or 0
    do = getattr(video, "days_old", None)
    if do is None or do <= 0:
        return 0
    return vc / max(do, 1)


def find_rescue_candidates(
    wl_id: str,
    flop_ratio_threshold: float = 0.3,
    winner_ratio_threshold: float = 2.0,
    min_tag_overlap: int = 2,
    top_n_recommendations: int = 10,
    log_fn: Callable[[str], None] = print,
) -> list:
    """Tìm video kênh nhà cần "rescue" + đối thủ làm template.

    Args:
        wl_id: watchlist id
        flop_ratio_threshold: video flop = vpd < median × ratio
        winner_ratio_threshold: video winner = vpd > median × ratio
        min_tag_overlap: tối thiểu N tag chung để match
        top_n_recommendations: top N recommendations trả về

    Returns: list dict {self_video, competitor_video, matching_tags,
        lift_potential, suggested_new_title}
    """
    import pickle
    from . import persistence, watchlist as wl_mod

    w = wl_mod.load_watchlist(wl_id)
    if not w or not w.self_channel:
        log_fn(f"  ⚠ WL {wl_id} không có self_channel")
        return []

    # Load self videos
    self_recs = persistence.records_for_channel(w.self_channel.channel_id)
    if not self_recs:
        return []
    self_pkl = persistence.load_result(self_recs[0]["id"])
    if self_pkl is None:
        return []
    self_videos = self_pkl.get("videos") or []
    if not self_videos:
        return []
    self_vpds = [_video_vpd(v) for v in self_videos]
    self_vpds = [x for x in self_vpds if x > 0]
    if not self_vpds:
        return []
    self_median = median(self_vpds)

    # Detect flop videos
    flop_threshold = self_median * flop_ratio_threshold
    flops = [v for v in self_videos
             if 0 < _video_vpd(v) < flop_threshold]
    log_fn(f"  📉 {w.self_channel.title[:25]}: {len(flops)} flop "
           f"(vpd < {int(flop_threshold)})")

    if not flops:
        return []

    # Load all competitor videos (with tags + vpd > winner threshold)
    competitor_winners = []
    for c in w.channels:
        if c.channel_id == w.self_channel.channel_id:
            continue
        recs = persistence.records_for_channel(c.channel_id)
        if not recs:
            continue
        comp_pkl = persistence.load_result(recs[0]["id"])
        if comp_pkl is None:
            continue
        comp_vids = comp_pkl.get("videos") or []
        comp_vpds = [_video_vpd(v) for v in comp_vids]
        comp_vpds = [x for x in comp_vpds if x > 0]
        if not comp_vpds:
            continue
        comp_median = median(comp_vpds)
        winner_threshold = comp_median * winner_ratio_threshold
        for v in comp_vids:
            vpd = _video_vpd(v)
            if vpd > winner_threshold and vpd > flop_threshold * 5:
                # winner = vpd cao + ít nhất 5x flop của kênh nhà
                competitor_winners.append((c, v, vpd))

    if not competitor_winners:
        log_fn(f"  ⚠ Không có đối thủ winner để so")
        return []

    log_fn(f"  🏆 {len(competitor_winners)} đối thủ winner để match")

    # Match: với mỗi flop, tìm top 3 competitor winner có nhiều tag overlap nhất
    recommendations = []
    for flop_v in flops:
        flop_tags = _video_tags_set(flop_v)
        if len(flop_tags) < min_tag_overlap:
            continue
        flop_vpd = _video_vpd(flop_v)

        matches = []
        for comp_c, comp_v, comp_vpd in competitor_winners:
            comp_tags = _video_tags_set(comp_v)
            overlap = flop_tags & comp_tags
            if len(overlap) < min_tag_overlap:
                continue
            lift = comp_vpd / max(flop_vpd, 1)
            matches.append({
                "comp_channel": comp_c.title,
                "comp_channel_id": comp_c.channel_id,
                "comp_video": {
                    "title": getattr(comp_v, "title", ""),
                    "video_id": getattr(comp_v, "video_id", ""),
                    "vpd": int(comp_vpd),
                    "duration": getattr(comp_v, "duration_seconds", 0),
                },
                "matching_tags": sorted(overlap)[:10],
                "n_overlap": len(overlap),
                "lift_potential": round(lift, 1),
            })

        # Sort matches theo lift × n_overlap (mạnh nhất trước)
        matches.sort(key=lambda m: m["lift_potential"] * m["n_overlap"],
                     reverse=True)
        best = matches[:3]
        if not best:
            continue

        recommendations.append({
            "self_video": {
                "title": getattr(flop_v, "title", ""),
                "video_id": getattr(flop_v, "video_id", ""),
                "vpd": int(flop_vpd),
                "view_count": getattr(flop_v, "view_count", 0),
                "duration": getattr(flop_v, "duration_seconds", 0),
                "tags": list(flop_tags)[:10],
            },
            "competitor_matches": best,
            "best_lift": best[0]["lift_potential"],
            "suggested_action": (
                f"Học từ '{best[0]['comp_video']['title'][:60]}' "
                f"(đối thủ {best[0]['comp_channel'][:25]} đạt "
                f"{best[0]['comp_video']['vpd']:,} vpd vs bạn "
                f"{int(flop_vpd):,} vpd, lift {best[0]['lift_potential']}x)"
            ),
        })

    # Sort theo best_lift
    recommendations.sort(key=lambda r: r["best_lift"], reverse=True)
    return recommendations[:top_n_recommendations]
