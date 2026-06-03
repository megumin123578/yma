# -*- coding: utf-8 -*-
"""Hook Timing Analyzer — phân tích 15s đầu video kênh nhà.

Dùng retention curve từ YouTube Analytics API (Inside data, đã có sẵn
trong `core/analytics_inside.py::get_retention_full`).

Output:
- Top hook (top videos có retention 0-10% cao nhất)
- Worst hook (drop nhiều nhất ở 0-10%)
- Pattern title của video hook tốt vs yếu
- Recommendation: hook style nào nên dùng

USAGE:
    from .hook_timing import analyze_hook_timing_for_channel
    result = analyze_hook_timing_for_channel(
        account_tag="kenh_chinh_tag",
        top_n=20,
    )
"""
from __future__ import annotations

from typing import Callable, Optional


def analyze_hook_timing_for_channel(
    account_tag: str,
    top_n: int = 20,
    min_views: int = 500,
    log_fn: Callable[[str], None] = print,
) -> dict:
    """Phân tích hook timing cho 1 kênh (qua Inside data).

    Args:
        account_tag: OAuth token tag (match qua match_account_tag)
        top_n: số video phân tích
        min_views: min views threshold

    Returns: dict {
        n_videos, hook_quality_distribution,
        top_hook_videos (top 5 hook tốt),
        worst_hook_videos (top 5 hook yếu),
        title_pattern_winning_hook, title_pattern_losing_hook,
        recommendations
    }
    """
    try:
        from .analytics_inside import (
            is_available, get_retention_full)
    except Exception as e:
        return {"error": f"analytics_inside không có: {e}"}

    if not is_available():
        return {"error": "Inside data chưa cài (analytics.db không có)"}

    curves = get_retention_full(account_tag, top_n=top_n,
                                min_views=min_views)
    if not curves:
        return {"error": f"Không có retention curve cho '{account_tag}'"}

    log_fn(f"  ⏱ hook_timing: phân tích {len(curves)} video của "
           f"{account_tag}")

    # Gom theo hook_retention
    quality = {"strong": [], "ok": [], "weak": []}
    # strong: hook_retention >= 85% (drop < 15% trong 10s đầu)
    # ok:     65-85%
    # weak:   < 65% (drop > 35%)
    for c in curves:
        seg = c.get("segments") or {}
        hr = seg.get("hook_retention", 0)
        if hr >= 85:
            quality["strong"].append(c)
        elif hr >= 65:
            quality["ok"].append(c)
        else:
            quality["weak"].append(c)

    # Sort each by hook_retention
    quality["strong"].sort(
        key=lambda c: c.get("segments", {}).get("hook_retention", 0),
        reverse=True)
    quality["weak"].sort(
        key=lambda c: c.get("segments", {}).get("hook_retention", 0))

    # Pattern title hook tốt vs yếu
    titles_strong = [c.get("title", "") for c in quality["strong"]]
    titles_weak = [c.get("title", "") for c in quality["weak"]]

    pattern = {}
    if len(titles_strong) >= 3 and len(titles_weak) >= 3:
        try:
            from .title_pattern import extract_features
            strong_feats = [extract_features(t) for t in titles_strong]
            weak_feats = [extract_features(t) for t in titles_weak]

            def _pct(feats, key):
                return round(100 * sum(1 for f in feats if f[key])
                             / len(feats), 0) if feats else 0

            pattern = {
                "strong_avg_word_count": round(
                    sum(f["word_count"] for f in strong_feats)
                    / len(strong_feats), 1),
                "weak_avg_word_count": round(
                    sum(f["word_count"] for f in weak_feats)
                    / len(weak_feats), 1),
                "strong_has_question_pct": _pct(strong_feats, "has_question"),
                "weak_has_question_pct": _pct(weak_feats, "has_question"),
                "strong_has_number_pct": _pct(strong_feats, "has_number"),
                "weak_has_number_pct": _pct(weak_feats, "has_number"),
                "strong_has_emoji_pct": _pct(strong_feats, "has_emoji"),
                "weak_has_emoji_pct": _pct(weak_feats, "has_emoji"),
            }
        except Exception as e:
            log_fn(f"  ⚠ title pattern hook err: {e}")

    # Recommendations
    recs = []
    n_strong = len(quality["strong"])
    n_weak = len(quality["weak"])
    n_total = len(curves)

    if n_weak / max(n_total, 1) > 0.4:
        recs.append(
            f"⚠ {n_weak}/{n_total} video có hook YẾU (retention < 65% "
            f"trong 10s đầu) — cần cải thiện hook style")

    if pattern:
        if (pattern.get("strong_avg_word_count", 0)
                < pattern.get("weak_avg_word_count", 0) - 1):
            recs.append(
                f"Video hook TỐT có tiêu đề NGẮN hơn "
                f"({pattern['strong_avg_word_count']} vs "
                f"{pattern['weak_avg_word_count']} từ) — rút gọn tiêu đề")
        if (pattern.get("strong_has_question_pct", 0)
                > pattern.get("weak_has_question_pct", 0) + 20):
            recs.append(
                f"Tiêu đề CÂU HỎI cho hook tốt hơn "
                f"({pattern['strong_has_question_pct']}% vs "
                f"{pattern['weak_has_question_pct']}%)")
        if (pattern.get("strong_has_number_pct", 0)
                > pattern.get("weak_has_number_pct", 0) + 20):
            recs.append(
                f"Tiêu đề có SỐ cho hook tốt hơn "
                f"({pattern['strong_has_number_pct']}% vs "
                f"{pattern['weak_has_number_pct']}%)")

    return {
        "n_videos": n_total,
        "n_strong": n_strong,
        "n_ok": len(quality["ok"]),
        "n_weak": n_weak,
        "top_hook_videos": [
            {
                "title": c.get("title", ""),
                "video_id": c.get("video_id", ""),
                "hook_retention": (c.get("segments", {})
                                   .get("hook_retention", 0)),
                "views": c.get("views", 0),
            } for c in quality["strong"][:5]
        ],
        "worst_hook_videos": [
            {
                "title": c.get("title", ""),
                "video_id": c.get("video_id", ""),
                "hook_retention": (c.get("segments", {})
                                   .get("hook_retention", 0)),
                "views": c.get("views", 0),
                "weakest_segment": (c.get("segments", {})
                                    .get("weakest_segment", "?")),
            } for c in quality["weak"][:5]
        ],
        "title_pattern": pattern,
        "recommendations": recs,
    }
