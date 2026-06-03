"""
Tag Analyzer - tính SEO Score cho video (giống VidIQ).
Đánh giá: tag count, keyword overlap, tripled keywords, length...
"""

from __future__ import annotations

import re
from typing import Optional


def _normalize_tokens(text: str) -> set:
    """Trả về set các token đã normalize (lowercase, bỏ dấu câu)."""
    if not text:
        return set()
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return {t for t in text.split() if len(t) >= 2}


def compute_video_seo_score(video) -> dict:
    """
    Tính SEO score cho 1 video. Trả dict với:
      - score (0-100)
      - components: dict các thành phần với điểm + giải thích
    """
    title = video.title or ""
    desc = video.description or ""
    tags = [t.lower() for t in (video.tags or []) if t]

    title_tokens = _normalize_tokens(title)
    desc_tokens = _normalize_tokens(desc)
    tag_tokens = set()
    for t in tags:
        tag_tokens.update(_normalize_tokens(t))

    components = {}

    # 1) Tag count: ideal 3-30 tags
    # (Briggsby study: top-ranked videos avg ~31 tags. YouTube cho phép 500 ký tự.)
    n_tags = len(tags)
    if n_tags == 0:
        c1 = 0
        msg1 = "Không có tag - bỏ lỡ SEO"
    elif n_tags < 3:
        c1 = 5
        msg1 = f"Chỉ {n_tags} tag - quá ít (ideal 3-30)"
    elif n_tags <= 30:
        c1 = 15
        msg1 = f"{n_tags} tags - tốt"
    elif n_tags <= 40:
        c1 = 12
        msg1 = f"{n_tags} tags - hơi nhiều, có thể loãng tín hiệu"
    else:
        c1 = 8
        msg1 = f"{n_tags} tags - quá nhiều (nguy cơ tag stuffing)"
    components["Tag count"] = {"score": c1, "max": 15, "note": msg1}

    # 2) Keywords trong title (tag chính có xuất hiện trong title?)
    overlap_title = len(tag_tokens & title_tokens)
    if not tag_tokens:
        c2 = 0
        msg2 = "Không có tag để check"
    elif overlap_title >= 3:
        c2 = 20
        msg2 = f"{overlap_title} từ khoá tag xuất hiện trong title - rất tốt"
    elif overlap_title >= 1:
        c2 = 15
        msg2 = f"{overlap_title} từ khoá tag trong title"
    else:
        c2 = 0
        msg2 = "Title không chứa từ tag - thiếu SEO"
    components["Keywords trong title"] = {"score": c2, "max": 20, "note": msg2}

    # 3) Keywords trong description
    overlap_desc = len(tag_tokens & desc_tokens)
    if not tag_tokens:
        c3 = 0
        msg3 = ""
    elif overlap_desc >= 5:
        c3 = 15
        msg3 = f"{overlap_desc} từ khoá tag trong description - tốt"
    elif overlap_desc >= 2:
        c3 = 10
        msg3 = f"{overlap_desc} từ khoá tag trong description"
    else:
        c3 = 3
        msg3 = "Description ít chứa từ khoá"
    components["Keywords trong description"] = {"score": c3, "max": 15, "note": msg3}

    # 4) Tripled keywords - cùng từ trong cả 3 chỗ (title + desc + tags)
    tripled = tag_tokens & title_tokens & desc_tokens
    if not tag_tokens:
        c4 = 0
        msg4 = ""
    elif len(tripled) >= 3:
        c4 = 20
        msg4 = f"{len(tripled)} từ xuất hiện cả ở title + desc + tag - mạnh"
    elif len(tripled) >= 1:
        c4 = 10
        msg4 = f"{len(tripled)} từ tripled - khá"
    else:
        c4 = 0
        msg4 = "Không có từ khoá xuất hiện cả 3 chỗ"
    components["Tripled keywords"] = {"score": c4, "max": 20,
                                       "note": msg4, "items": list(tripled)[:5]}

    # 5) Title length: ideal 40-70 chars
    L_title = len(title)
    if L_title < 20:
        c5 = 2
        msg5 = f"Title {L_title} ký tự - quá ngắn"
    elif L_title <= 70:
        c5 = 15
        msg5 = f"Title {L_title} ký tự - tốt"
    elif L_title <= 100:
        c5 = 10
        msg5 = f"Title {L_title} ký tự - hơi dài"
    else:
        c5 = 5
        msg5 = f"Title {L_title} ký tự - quá dài"
    components["Title length"] = {"score": c5, "max": 15, "note": msg5}

    # 6) Description length: ideal 200+ chars
    L_desc = len(desc)
    if L_desc < 50:
        c6 = 0
        msg6 = f"Description {L_desc} ký tự - quá ngắn (nên 200+)"
    elif L_desc < 200:
        c6 = 8
        msg6 = f"Description {L_desc} ký tự - khá"
    else:
        c6 = 15
        msg6 = f"Description {L_desc} ký tự - tốt"
    components["Description length"] = {"score": c6, "max": 15, "note": msg6}

    # Tổng
    total = sum(c["score"] for c in components.values())

    return {
        "score": total,
        "components": components,
        "video_id": getattr(video, "video_id", ""),
        "video_title": title[:80],
    }


def compute_channel_seo_summary(videos: list) -> dict:
    """Tính tổng hợp SEO score cho cả kênh (trung bình + best/worst)."""
    if not videos:
        return {"avg_score": 0, "best": None, "worst": None,
                "video_count": 0, "videos": []}

    scores = []
    for v in videos:
        s = compute_video_seo_score(v)
        scores.append(s)

    avg = sum(s["score"] for s in scores) / len(scores)
    best = max(scores, key=lambda s: s["score"])
    worst = min(scores, key=lambda s: s["score"])

    # Component averages
    components_avg = {}
    if scores:
        keys = scores[0]["components"].keys()
        for k in keys:
            avg_s = sum(s["components"][k]["score"] for s in scores) / len(scores)
            max_s = scores[0]["components"][k]["max"]
            components_avg[k] = {"avg": round(avg_s, 1), "max": max_s}

    return {
        "avg_score": round(avg, 1),
        "best": best,
        "worst": worst,
        "video_count": len(videos),
        "components_avg": components_avg,
        "videos": scores,
    }


def classify_competition(result_count: int) -> dict:
    """Phân loại competition dựa trên số kết quả YouTube trả về."""
    if result_count <= 0:
        return {"level": "unknown", "color": "#999",
                "label": "?", "result_count": result_count}
    if result_count < 50_000:
        return {"level": "low", "color": "#107C10",
                "label": "🟢 LOW",
                "human": f"{result_count:,} kết quả - ít cạnh tranh",
                "result_count": result_count}
    if result_count < 500_000:
        return {"level": "medium", "color": "#B7791F",
                "label": "🟡 MED",
                "human": f"{result_count:,} kết quả - cạnh tranh trung bình",
                "result_count": result_count}
    return {"level": "high", "color": "#D13438",
            "label": "🔴 HIGH",
            "human": f"{result_count:,} kết quả - cạnh tranh cao",
            "result_count": result_count}
