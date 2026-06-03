# -*- coding: utf-8 -*-
"""Audience-timezone-aware posting time recommender.

Cải tiến `core/posting_time.py` (chỉ dùng giờ trung bình top video).
Phiên bản này kết hợp:
- Audience demographics từ Inside data (% audience theo country)
- Convert giờ về timezone của audience
- Tính prime time thực = giờ mà MAJORITY audience đang xem

Output: heatmap day-of-week × hour ở timezone audience + recommendation
giờ post tối ưu (đã convert về timezone máy đăng).

USAGE:
    from .posting_time_v2 import recommend_posting_time
    rec = recommend_posting_time(
        account_tag="kenh_chinh_tag",
        upload_timezone="Asia/Ho_Chi_Minh",  # giờ máy đăng
    )
    # rec: {best_slots, audience_breakdown, heatmap, advice}
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Callable, Optional


# Country code → UTC offset hours (approximation, peak hours)
# Để chính xác hơn nên dùng pytz/zoneinfo. Đơn giản dùng UTC offset.
COUNTRY_TZ_OFFSET = {
    "US": -6,   # CST trung bình
    "VN": 7,
    "IN": 5.5,
    "ID": 7,
    "BR": -3,
    "PH": 8,
    "MX": -6,
    "GB": 0,
    "FR": 1,
    "DE": 1,
    "JP": 9,
    "KR": 9,
    "TH": 7,
    "RU": 3,
    "ES": 1,
    "IT": 1,
    "CA": -5,
    "AU": 10,
    "TR": 3,
    "EG": 2,
    "PL": 1,
    "AR": -3,
}


def _get_audience_countries(account_tag: str) -> list:
    """Lấy top countries của audience từ Inside data.

    Returns list [{"country": "VN", "pct": 60.5}, ...] hoặc [].
    """
    try:
        from .analytics_inside import get_audience_full
        full = get_audience_full(account_tag)
        return full.get("top_countries") or []
    except Exception:
        return []


def _audience_prime_hours(top_countries: list) -> dict:
    """Tính weighted score của 24h slots theo audience country distribution.

    Mỗi country có prime hours nhất định (sáng/trưa/chiều/tối). Audience
    xem nhiều khi không bận → ưu tiên 7-9pm theo local time.

    Returns: dict {hour_utc: weighted_score}
    """
    # Prime hours của 1 audience (local time) — peak 19-22h
    LOCAL_PRIME_WEIGHTS = {
        # hour → weight
        17: 0.5, 18: 0.7, 19: 1.0, 20: 1.0, 21: 0.9, 22: 0.7,
        12: 0.4, 13: 0.4,  # lunch break
        7: 0.3, 8: 0.3,    # morning commute
    }

    scores = {h: 0.0 for h in range(24)}
    for c in top_countries:
        country = c.get("country", "")
        pct = c.get("pct", 0)
        if pct < 1:
            continue
        offset = COUNTRY_TZ_OFFSET.get(country.upper())
        if offset is None:
            continue
        weight = pct / 100.0
        for local_hr, w in LOCAL_PRIME_WEIGHTS.items():
            utc_hr = int((local_hr - offset) % 24)
            scores[utc_hr] += w * weight

    return scores


def _convert_utc_to_local(utc_hour: int, local_offset: float) -> int:
    """UTC hour → local hour (rounding to nearest hour)."""
    return int(round(utc_hour + local_offset)) % 24


def recommend_posting_time(
    account_tag: str,
    upload_timezone_offset: float = 7.0,  # VN = UTC+7
    log_fn: Callable[[str], None] = print,
) -> dict:
    """Đề xuất giờ post tối ưu theo audience timezone breakdown.

    Args:
        account_tag: token tag kênh (Inside data)
        upload_timezone_offset: UTC offset của máy đăng (VN=7)

    Returns dict {
        audience_breakdown, best_slots_local, all_slots_scored,
        advice
    }
    """
    countries = _get_audience_countries(account_tag)
    if not countries:
        return {"error": "Không có audience data từ Inside"}

    log_fn(f"  🌍 audience: {len(countries)} top countries, "
           f"top 3: {[c.get('country') for c in countries[:3]]}")

    utc_scores = _audience_prime_hours(countries)
    local_scores = {}
    for utc_h, score in utc_scores.items():
        local_h = _convert_utc_to_local(utc_h, upload_timezone_offset)
        local_scores[local_h] = local_scores.get(local_h, 0) + score

    # Sort slots
    sorted_slots = sorted(local_scores.items(),
                          key=lambda x: x[1], reverse=True)
    best_slots = [
        {"local_hour": h, "score": round(s, 2)}
        for h, s in sorted_slots[:6]
    ]

    advice = []
    if best_slots:
        top = best_slots[0]
        advice.append(
            f"⏰ Giờ post tối ưu (giờ máy đăng): "
            f"{top['local_hour']:02d}:00 — score {top['score']}")
        if len(best_slots) >= 3:
            slots_str = ", ".join(
                f"{s['local_hour']:02d}h" for s in best_slots[:3])
            advice.append(f"Top 3 khung: {slots_str}")

    # Audience timezone summary
    audience_summary = []
    for c in countries[:5]:
        country = c.get("country", "")
        pct = c.get("pct", 0)
        offset = COUNTRY_TZ_OFFSET.get(country.upper(), "?")
        audience_summary.append(
            f"{country} ({pct:.1f}%, UTC{offset:+g})"
            if isinstance(offset, (int, float))
            else f"{country} ({pct:.1f}%, TZ?)"
        )

    return {
        "audience_breakdown": audience_summary,
        "best_slots_local": best_slots,
        "all_slots_scored": dict(sorted(local_scores.items())),
        "upload_timezone_offset": upload_timezone_offset,
        "advice": advice,
    }
