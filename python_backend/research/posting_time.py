"""
Phân tích thời điểm đăng tối ưu dựa trên video kênh.
"""

from __future__ import annotations

from datetime import datetime
from statistics import median
from typing import Optional


WEEKDAY_NAMES = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]


def _parse_iso(iso: str) -> Optional[datetime]:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return None


def analyze(result: dict) -> dict:
    """Trả dict {best_weekday, best_hour_range, by_weekday, by_hour, total_videos}.

    by_weekday: list 7 phần tử [{name, avg_vpd, count, median_vpd}, ...]
    by_hour: list 24 phần tử [{hour, avg_vpd, count}, ...]
    """
    videos = result.get("videos", [])
    if not videos:
        return {"total_videos": 0}

    # Gom theo weekday
    weekday_data = {i: [] for i in range(7)}
    # Gom theo hour
    hour_data = {i: [] for i in range(24)}

    for v in videos:
        dt = _parse_iso(v.published_at)
        if not dt or v.views_per_day <= 0:
            continue
        # Convert UTC → VN time (UTC+7) để khớp thói quen user Việt
        # (đơn giản: +7 giờ)
        from datetime import timezone, timedelta
        try:
            local_dt = dt.astimezone(timezone(timedelta(hours=7)))
        except Exception:
            local_dt = dt
        weekday_data[local_dt.weekday()].append(v.views_per_day)
        hour_data[local_dt.hour].append(v.views_per_day)

    by_weekday = []
    for i in range(7):
        vals = weekday_data[i]
        if vals:
            by_weekday.append({
                "name": WEEKDAY_NAMES[i],
                "weekday": i,
                "count": len(vals),
                "avg_vpd": sum(vals) / len(vals),
                "median_vpd": median(vals),
                "max_vpd": max(vals),
            })
        else:
            by_weekday.append({
                "name": WEEKDAY_NAMES[i],
                "weekday": i, "count": 0, "avg_vpd": 0,
                "median_vpd": 0, "max_vpd": 0,
            })

    by_hour = []
    for i in range(24):
        vals = hour_data[i]
        if vals:
            by_hour.append({
                "hour": i, "count": len(vals),
                "avg_vpd": sum(vals) / len(vals),
                "median_vpd": median(vals),
            })
        else:
            by_hour.append({
                "hour": i, "count": 0, "avg_vpd": 0, "median_vpd": 0,
            })

    # Best weekday: yêu cầu count >= 2 để giảm noise
    valid_wd = [w for w in by_weekday if w["count"] >= 2]
    if valid_wd:
        best_wd = max(valid_wd, key=lambda w: w["median_vpd"])
    else:
        best_wd = max(by_weekday, key=lambda w: w["avg_vpd"])

    # Best hour range: tìm cửa sổ 3 giờ có tổng views cao nhất
    best_hour_start = 0
    best_hour_score = 0
    for h in range(24):
        # 3-hour window
        window = [by_hour[(h + i) % 24] for i in range(3)]
        score = sum(w["avg_vpd"] * w["count"] for w in window)
        if score > best_hour_score:
            best_hour_score = score
            best_hour_start = h

    best_hour_range = f"{best_hour_start:02d}:00 - {(best_hour_start + 3) % 24:02d}:00"

    return {
        "total_videos": sum(1 for v in videos if _parse_iso(v.published_at)),
        "by_weekday": by_weekday,
        "by_hour": by_hour,
        "best_weekday": best_wd["name"],
        "best_weekday_vpd": best_wd["median_vpd"] or best_wd["avg_vpd"],
        "best_hour_range": best_hour_range,
    }


def format_summary(stats: dict) -> str:
    if not stats or stats.get("total_videos", 0) == 0:
        return "(Không đủ dữ liệu để phân tích)"
    return (f"Tốt nhất: {stats['best_weekday']}, khung giờ {stats['best_hour_range']} "
            f"(giờ Việt Nam). Dựa trên {stats['total_videos']} video.")
