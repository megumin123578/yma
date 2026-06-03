# -*- coding: utf-8 -*-
"""AI Feedback Loop — track xem ý tưởng AI đề xuất kỳ trước có thật sự
được làm + có thành công không.

Logic:
1. Đọc các bản chiến lược AI cũ của watchlist (latest_analysis + analyses
   history) - parse phần "Ý TƯỞNG VIDEO CỤ THỂ" để lấy list ý tưởng.
2. Cho mỗi ý tưởng + ngày đề xuất: tìm video kênh chính đăng SAU ngày đó
   có tiêu đề OVERLAP với ý tưởng (fuzzy match token).
3. Đánh giá performance video đã đăng: views / median của kênh = ratio.
4. Trả dict {ideas_total, ideas_done, ideas_pending, success_rate,
   detail[]} để render vào HTML report.

Hàm chính: build_feedback_for_watchlist(wl, self_res) → dict
"""
from __future__ import annotations

import re
import statistics
from datetime import datetime


# Header pattern để tìm section "Ý TƯỞNG VIDEO" trong analysis text
_IDEA_SECTION_HEADERS = [
    r"##?\s*V?I?\.?\s*Ý\s*T[ƯU]ỞNG\s*VIDEO\s*CỤ?\s*THỂ",
    r"##?\s*\d+\.?\s*Ý\s*T[ƯU]ỞNG\s*VIDEO",
    r"V\.?\s*Ý\s*T[ƯU]ỞNG\s*VIDEO\s*CỤ\s*THỂ",
    r"Ý\s*T[ƯU]ỞNG\s*VIDEO\s*CỤ\s*THỂ\s*ĐỂ\s*LÀM",
    r"VIỆC\s*LÀM\s*NGAY",
]

# Pattern parse 1 ý tưởng: "1." hoặc "1)" + tiêu đề (có thể trong dấu ")
_IDEA_LINE_PATTERNS = [
    re.compile(r'^\s*\d+[\.\)]\s*[""]([^""]+)["",]', re.M),
    re.compile(r'^\s*\d+[\.\)]\s*"([^"]+)"', re.M),
    re.compile(r'^\s*\d+[\.\)]\s*\*\*([^*]+)\*\*', re.M),
    re.compile(r'^\s*\d+[\.\)]\s*([^—\-\n:]+?)(?:\s*[—\-:]|$)', re.M),
]


def extract_ideas_from_text(analysis_text: str) -> list:
    """Parse list ý tưởng video từ 1 bản phân tích AI.

    Trả list str (mỗi str là tiêu đề ý tưởng).
    """
    if not analysis_text:
        return []
    text = str(analysis_text)
    # Tìm section "Ý tưởng video"
    section_text = ""
    for hpat in _IDEA_SECTION_HEADERS:
        m = re.search(hpat, text, re.IGNORECASE)
        if m:
            start = m.end()
            # Section kéo dài đến header tiếp theo (## hoặc dòng có "VI.", "VII.", etc.)
            end_m = re.search(r"\n##\s|\n[IVX]+\.?\s+[A-ZÀ-Ỹ]",
                              text[start:])
            end = start + end_m.start() if end_m else len(text)
            section_text = text[start:end]
            break

    if not section_text:
        # Fallback: scan toàn text cho dòng số 1. 2. 3.
        section_text = text

    # Apply patterns lần lượt cho đến khi tìm được ≥3 ý tưởng
    ideas = []
    for pat in _IDEA_LINE_PATTERNS:
        matches = pat.findall(section_text)
        # Filter: bỏ matches quá ngắn/dài
        matches = [m.strip().strip('"').strip("*").strip()
                   for m in matches]
        matches = [m for m in matches if 8 <= len(m) <= 200]
        if len(matches) >= 3:
            ideas = matches[:10]  # Tối đa 10 ý tưởng/kỳ
            break
        elif len(matches) > len(ideas):
            ideas = matches[:10]

    return ideas


def _tokenize(s: str) -> set:
    """Tách title thành token set (lowercase, loại từ ngắn)."""
    if not s:
        return set()
    toks = re.split(r"[\s,\-_\|\(\)\[\]\.!?:;/'\"]+", s.lower())
    return {t for t in toks if len(t) >= 3}


def _match_score(idea_title: str, video_title: str) -> float:
    """Tính độ giống giữa idea title và video title. 0-1."""
    a = _tokenize(idea_title)
    b = _tokenize(video_title)
    if not a or not b:
        return 0.0
    common = a & b
    if not common:
        return 0.0
    # Jaccard similarity
    return len(common) / len(a | b)


def build_feedback_for_watchlist(wl, self_res, min_match: float = 0.3) -> dict:
    """Build feedback data cho 1 watchlist.

    wl: Watchlist object (có analyses list).
    self_res: pkl mới nhất của kênh chính (có videos list).
    min_match: threshold độ giống để coi là "matched" (default 0.3 = 30% token).

    Trả dict {
        ideas_total, ideas_done, ideas_pending, success_rate,
        avg_perf_ratio, detail: [{idea, date, status, video?, views?, ratio?}]
    }
    """
    if not wl or not hasattr(wl, "analyses"):
        return {"ideas_total": 0, "ideas_done": 0, "ideas_pending": 0,
                "success_rate": 0, "avg_perf_ratio": 0, "detail": []}

    # Bước 1: extract tất cả ideas từ các kỳ phân tích cũ
    all_ideas = []  # list (date, idea_title)
    for an in (wl.analyses or []):
        if not isinstance(an, dict):
            continue
        content = an.get("content", "")
        date = an.get("analyzed_at", "")[:10]
        if not content or not date:
            continue
        ideas = extract_ideas_from_text(content)
        for idea in ideas:
            all_ideas.append((date, idea))

    if not all_ideas:
        return {"ideas_total": 0, "ideas_done": 0, "ideas_pending": 0,
                "success_rate": 0, "avg_perf_ratio": 0, "detail": []}

    # Dedupe: cùng idea title (lowercase) → giữ ngày đề xuất sớm nhất
    dedup = {}
    for date, idea in all_ideas:
        key = idea.lower().strip()
        if key not in dedup or date < dedup[key][0]:
            dedup[key] = (date, idea)
    all_ideas = list(dedup.values())
    all_ideas.sort()   # sort by date

    # Bước 2: lấy videos kênh chính + median
    if not self_res:
        return {"ideas_total": len(all_ideas), "ideas_done": 0,
                "ideas_pending": len(all_ideas), "success_rate": 0,
                "avg_perf_ratio": 0, "detail": [
                    {"idea": idea, "date": date, "status": "pending"}
                    for date, idea in all_ideas]}

    videos = self_res.get("videos") or []
    view_list = sorted([int(getattr(v, "view_count", 0) or 0)
                        for v in videos])
    median_v = (view_list[len(view_list) // 2] if view_list else 1) or 1

    # Bước 3: cho mỗi idea, tìm video đăng sau ngày đề xuất + match title
    details = []
    n_done = 0
    perf_ratios = []
    for date_proposed, idea in all_ideas:
        # Lọc videos đăng SAU ngày đề xuất
        candidates = []
        for v in videos:
            pub = (getattr(v, "published_at", "") or "")[:10]
            if pub and pub >= date_proposed:
                title = getattr(v, "title", "") or ""
                score = _match_score(idea, title)
                if score >= min_match:
                    candidates.append((score, v, title))

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_v, best_title = candidates[0]
            views = int(getattr(best_v, "view_count", 0) or 0)
            ratio = round(views / median_v, 2)
            perf_ratios.append(ratio)
            n_done += 1
            details.append({
                "idea": idea,
                "date": date_proposed,
                "status": "done",
                "video": best_title,
                "video_pub": (getattr(best_v, "published_at", "") or "")[:10],
                "views": views,
                "ratio": ratio,
                "match_score": round(best_score, 2),
            })
        else:
            details.append({
                "idea": idea,
                "date": date_proposed,
                "status": "pending",
            })

    n_total = len(all_ideas)
    n_pending = n_total - n_done
    success_rate = round(n_done / n_total * 100, 1) if n_total else 0
    avg_ratio = (round(statistics.mean(perf_ratios), 2)
                 if perf_ratios else 0)

    return {
        "ideas_total": n_total,
        "ideas_done": n_done,
        "ideas_pending": n_pending,
        "success_rate": success_rate,
        "avg_perf_ratio": avg_ratio,
        "median_v": median_v,
        "detail": details,
    }
