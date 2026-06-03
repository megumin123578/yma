"""
Inside SEO Synthesis — tầng phân tích trên cùng, kết hợp 3 nguồn:
  1. Inside Analytics (SQLite cache từ YouTube Studio dump/API)
  2. Health Check (audit kênh + 19 tiêu chí video)
  3. SEO framework + Niche library (per-niche cụ thể)

Module này KHÔNG phụ thuộc nguồn data (PG dump hay API) — chỉ đọc qua
abstraction layer `analytics_inside.py`. Khi sau này chuyển sang API,
schema SQLite giữ nguyên thì code synthesis chạy y nguyên.

20 hàm (14 mảng SEO + 6 mảng cross-reference):
  G1.  cross_reference_findings()    — Cross Inside × Health × SEO
  G2.  anatomize_top_thumbnails()    — Bóc công thức TOP 15 title/CTR
  G3.  compare_worst_vs_top()        — WORST thiếu gì so TOP
  G4.  traffic_source_playbook()     — Playbook SEO theo từng source
  G5.  drop_points_vs_title()        — Drop retention → diagnosis title
  G6.  audience_keyword_cluster()    — Demographics → keyword đề xuất
  G7.  inside_period_delta()         — Δ giữa 7d này vs 7-14d trước
  G8.  audit_description()           — DESC chuẩn 200+ từ + hashtag + timestamp
  G9.  audit_tags()                  — TAGS 8-15 hierarchy
  G10. optimal_upload_timing()       — Best hour/day từ data + niche
  G11. engagement_signals()          — Like/comment/share ratio vs niche baseline
  G12. caption_audit()               — Caption coverage + multi-lang strategy
  G13. content_strategy_gap()        — Pillars covered vs missing
  G14. title_position_formula_audit()— Keyword position + formula match
  G15. thumbnail_layout_audit()      — Layout map per niche
  G16. retention_techniques_map()    — 8 techniques map per niche
  G17. ctr_sweet_spot_decay()        — Sweet spot per niche + decay check
  G18. channel_seo_x_inside()        — Channel meta cross Inside performance
  G19. competitor_inside_cross()     — Mình vs đối thủ về upload/pillar
  G20. clickbait_penalty_check()     — Clickbait words penalty per niche
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Any, Optional


# ============================================================
# G1. CROSS-REFERENCE — Inside × Health × SEO framework
# ============================================================

def cross_reference_findings(
    inside: Dict[str, Any],
    health: List[Dict[str, Any]],
    health_channel: Dict[str, Any],
    health_keywords: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Kết hợp 3 lớp data → ra "findings" cụ thể với diagnosis + action.

    Returns: list of {finding, diagnosis, action, severity}
    """
    findings: List[Dict[str, Any]] = []
    if not inside:
        return findings
    cs = inside.get("channel_summary", {}) or {}
    af = inside.get("audience_full", {}) or {}
    th = inside.get("traffic_health", {}) or {}
    corr = inside.get("ctr_correlation", {}) or {}
    retention = inside.get("retention_top", []) or []
    devices = af.get("devices", {}) or {}

    # F1. CTR tốt + Subs NET âm → content lệch pillar
    ctr_pct = (cs.get("avg_thumbnail_ctr") or 0) * 100
    subs_net = cs.get("last_subs_net", 0) or 0
    if ctr_pct >= 5 and subs_net < 0:
        findings.append({
            "finding": (f"CTR thumbnail {ctr_pct:.1f}% TỐT nhưng "
                        f"Subs NET 30d {subs_net} (ÂM)"),
            "diagnosis": ("Thumbnail+title đủ hấp dẫn để viewer click, NHƯNG "
                          "sau khi xem họ unsub hoặc không sub. Content có "
                          "thể chệch pillar/promise của kênh."),
            "action": ("Audit 10 video gần nhất: title có khớp với 5 keyword "
                       "chính của kênh không? CTA subscribe trong video "
                       "có dùng đúng pillar không? Reset content roadmap."),
            "severity": "warn",
        })

    # F2. AVD ngắn + retention thấp → hook + pacing yếu
    avd = cs.get("avg_avd_seconds", 0) or 0
    if retention:
        avg_ret = sum((r.get("avg_retention") or 0)
                      for r in retention) / max(1, len(retention))
        if avd < 90 and avg_ret < 30:
            findings.append({
                "finding": (f"AVD {avd:.0f}s NGẮN + avg retention "
                            f"{avg_ret:.1f}% THẤP"),
                "diagnosis": ("Viewer rời video sớm. 2 lý do hàng đầu: "
                              "(a) Hook 10s đầu không nắm bắt attention, "
                              "(b) Pacing quá chậm trong 60s đầu."),
                "action": ("Áp dụng 5 công thức Hook (Result First / "
                           "Problem Punch / Bold Promise / Curiosity Gap / "
                           "Story). Cut nhanh hơn — shot ≤3s, B-roll mỗi "
                           "pattern interrupt mỗi 60s."),
                "severity": "bad",
            })

    # F3. Mobile 90%+ → thumbnail anatomy phải mobile-first
    mobile = devices.get("MOBILE", 0)
    if mobile > 90:
        findings.append({
            "finding": f"MOBILE {mobile:.0f}% — viewer xem trên màn ≤6 inch",
            "diagnosis": ("Thumbnail của bạn được xem ở 200×120px. "
                          "Text >5 từ, mặt nhỏ, chi tiết phức tạp đều "
                          "VÔ HÌNH ở size này."),
            "action": ("Anatomy bắt buộc: Face 30-50% size + Text ≤4 từ "
                       "size lớn + Contrast ratio ≥7:1 + Test ở 200×120px "
                       "trước khi up. Tham khảo 5 thumbnail layouts: "
                       "Face-Centered / Text-Hook / Split-Compare / "
                       "Object-Hero / Reaction-Mix."),
            "severity": "warn",
        })

    # F4. SUBSCRIBER traffic >50% → phụ thuộc sub cũ
    cs_sources = cs.get("traffic_sources_recent", []) or []
    sub_pct = next((s.get("pct", 0) for s in cs_sources
                    if s.get("source") == "SUBSCRIBER"), 0)
    search_pct = next((s.get("pct", 0) for s in cs_sources
                       if s.get("source") in ("YT_SEARCH", "SEARCH")), 0)
    if sub_pct > 50:
        findings.append({
            "finding": (f"SUBSCRIBER traffic {sub_pct:.0f}% — phụ thuộc "
                        f"sub cũ, SEARCH chỉ {search_pct:.0f}%"),
            "diagnosis": ("Kênh không thu hút new viewer. Sub feed đang "
                          "carry, nhưng sub feed sẽ giảm dần nếu CTR "
                          "không cao."),
            "action": ("BẮT BUỘC SEO: 100% video mới phải có keyword chính "
                       "≤50 ký tự đầu Title + đầy đủ tag (8-15 tag) + "
                       "Description 200+ từ với keyword phân bố đều. "
                       "Mục tiêu 3 tháng: SEARCH lên 15-20%."),
            "severity": "bad",
        })

    # F5. Health Check score thấp + Inside performance kém → SEO chính là gốc
    if health:
        avg_health = sum(h.get("score", 0) for h in health) / max(1, len(health))
        if avg_health < 60 and (ctr_pct < 4 or avd < 120):
            findings.append({
                "finding": (f"Health Check TB {avg_health:.0f}/100 (yếu) + "
                            f"Inside performance kém"),
                "diagnosis": ("SEO video kém (title/tag/description chuẩn "
                              "chưa đạt) gây giảm impressions → CTR thấp + "
                              "watchtime thấp."),
                "action": ("Lấy 5 video Health Check thấp nhất → fix "
                           "TITLE + DESC + TAGS theo checklist 19 items. "
                           "Sau 14 ngày đo lại CTR/AVD/retention."),
                "severity": "bad",
            })

    # F6. Keyword alignment kém (Health Check Keywords block)
    if health_keywords:
        gaps = health_keywords.get("gaps", []) or []
        theme = health_keywords.get("theme_consistency", 0) or 0
        if gaps and theme < 60:
            findings.append({
                "finding": (f"Theme consistency {theme:.0f}% (yếu) — "
                            f"{len(gaps)} keyword chính của niche bị thiếu"),
                "diagnosis": ("Kênh đăng video lệch ra ngoài cụm keyword "
                              "ngách → algorithm khó định vị → SUGGESTED "
                              "không đẩy → traffic source SEARCH yếu."),
                "action": (f"Top keyword cần đưa vào title 10 video tiếp: "
                           f"{', '.join(gaps[:5])}. Mỗi video có 1 keyword "
                           f"chính ở vị trí đầu title."),
                "severity": "warn",
            })

    # F7. CTR correlation thấp → thumbnail không có quan hệ với view
    if corr.get("n_videos", 0) >= 10:
        lift = corr.get("ctr_lift", 0) or 0
        if lift < 1:
            findings.append({
                "finding": (f"CTR lift {lift}% — top-view video KHÔNG có CTR "
                            f"cao hơn low-view video"),
                "diagnosis": ("Algorithm đang phân phối qua SUGGESTED/BROWSE "
                              "chứ không phải qua thumbnail click. CTR "
                              "không quyết định views."),
                "action": ("Tập trung AVD + retention (yếu tố SUGGESTED) "
                           "hơn là thumbnail polish. Nếu muốn tăng SEARCH "
                           "traffic thì mới đầu tư thumbnail."),
                "severity": "warn",
            })

    return findings


# ============================================================
# G2. ANATOMIZE TOP — bóc công thức TOP 15 thumbnail/title
# ============================================================

# Từ khóa niche thường gặp trong title
_NICHE_KW = [
    "satisfying", "asmr", "unboxing", "review", "compilation",
    "playset", "collection", "doll", "kitchen", "playtime",
    "minutes", "crushing", "experiment", "horror", "story",
    "tractor", "diy", "mini", "build", "paper", "couple",
    "glow", "number", "blocks", "slime", "rainbow",
]

# Brand/character names
_BRAND_KW = [
    "disney", "peppa pig", "minnie mouse", "cocomelon", "barbie",
    "pinkfong", "hello kitty", "lego", "playmobil", "fisher price",
    "marvel", "frozen", "elsa", "spiderman", "transformers",
    "numberblocks",
]

# Emotion/promise words
_EMOTION_KW = [
    "cute", "amazing", "best", "ultimate", "perfect", "cool",
    "magic", "secret", "shocking", "wow", "epic", "huge",
    "rainbow", "colorful", "pastel", "glitter", "sparkle",
]


def _extract_patterns(title: str) -> Dict[str, Any]:
    """Bóc các pattern phổ biến trong 1 title."""
    t = (title or "").lower()
    # Số phút
    minutes = re.findall(r"(\d+)\s*minute", t)
    minute_n = int(minutes[0]) if minutes else 0
    # Niche keywords
    niche_hit = [k for k in _NICHE_KW if k in t]
    # Brand
    brand_hit = [k for k in _BRAND_KW if k in t]
    # Emotion
    emo_hit = [k for k in _EMOTION_KW if k in t]
    # Has number anywhere
    has_number = bool(re.search(r"\d+", t))
    # Length
    length = len(title or "")
    # Punctuation
    has_emoji = bool(re.search(r"[^\w\s,.\-!?()\[\]&|/'\"]", title or ""))
    has_caps_word = bool(re.findall(r"\b[A-Z]{2,}\b", title or ""))
    has_pipe = "|" in (title or "")
    has_pipe_or_dash = "|" in (title or "") or " - " in (title or "")
    return {
        "minute_n": minute_n,
        "niche_kw": niche_hit,
        "brand_kw": brand_hit,
        "emotion_kw": emo_hit,
        "has_number": has_number,
        "length": length,
        "has_emoji": has_emoji,
        "has_caps_word": has_caps_word,
        "has_pipe": has_pipe,
        "has_pipe_or_dash": has_pipe_or_dash,
    }


def anatomize_top_thumbnails(
    top_videos: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Bóc tách pattern lặp trong TOP video CTR cao.

    Returns: {
      "patterns": [{"name", "freq_pct", "example_titles"}, ...],
      "formula": "<recipe text>",
      "title_length_avg": int,
      "minute_avg": int,
    }
    """
    if not top_videos:
        return {"patterns": [], "formula": "", "title_length_avg": 0}

    extracted = [_extract_patterns(v.get("title", "")) for v in top_videos]
    n = len(extracted)

    pats: List[Dict[str, Any]] = []

    # Pattern: số phút
    with_min = [e for e in extracted if e["minute_n"]]
    if with_min:
        avg_min = round(sum(e["minute_n"] for e in with_min) / len(with_min))
        freq = round(100 * len(with_min) / n)
        pats.append({
            "name": f"Số PHÚT đầu title (TB {avg_min} phút)",
            "freq_pct": freq,
            "example_titles": [v.get("title", "")
                               for v, e in zip(top_videos, extracted)
                               if e["minute_n"]][:3],
        })

    # Pattern: niche keyword
    niche_count = Counter()
    for e in extracted:
        for k in e["niche_kw"]:
            niche_count[k] += 1
    if niche_count:
        top_niche = niche_count.most_common(5)
        for kw, c in top_niche:
            if c >= n * 0.3:  # >=30% video có
                pats.append({
                    "name": f"Từ khóa niche '{kw.upper()}'",
                    "freq_pct": round(100 * c / n),
                    "example_titles": [v.get("title", "")
                                       for v, e in zip(top_videos, extracted)
                                       if kw in e["niche_kw"]][:2],
                })

    # Pattern: brand
    brand_count = Counter()
    for e in extracted:
        for k in e["brand_kw"]:
            brand_count[k] += 1
    if brand_count:
        top_brand = brand_count.most_common(3)
        for kw, c in top_brand:
            if c >= n * 0.2:
                pats.append({
                    "name": f"Brand/Character '{kw.title()}'",
                    "freq_pct": round(100 * c / n),
                    "example_titles": [v.get("title", "")
                                       for v, e in zip(top_videos, extracted)
                                       if kw in e["brand_kw"]][:2],
                })

    # Pattern: emotion word
    emo_count = Counter()
    for e in extracted:
        for k in e["emotion_kw"]:
            emo_count[k] += 1
    if emo_count:
        for kw, c in emo_count.most_common(3):
            if c >= n * 0.3:
                pats.append({
                    "name": f"Emotion '{kw.upper()}'",
                    "freq_pct": round(100 * c / n),
                    "example_titles": [v.get("title", "")
                                       for v, e in zip(top_videos, extracted)
                                       if kw in e["emotion_kw"]][:2],
                })

    # Pattern: pipe/dash separator
    pipe_count = sum(1 for e in extracted if e["has_pipe_or_dash"])
    if pipe_count >= n * 0.4:
        pats.append({
            "name": "Phân cách | hoặc - (tách 2 phần title)",
            "freq_pct": round(100 * pipe_count / n),
            "example_titles": [v.get("title", "")
                               for v, e in zip(top_videos, extracted)
                               if e["has_pipe_or_dash"]][:2],
        })

    # Length stats
    length_avg = round(sum(e["length"] for e in extracted) / n)
    min_avg = (round(sum(e["minute_n"] for e in with_min) / len(with_min))
               if with_min else 0)

    # Build formula
    formula_parts = []
    if with_min and round(100 * len(with_min) / n) >= 50:
        formula_parts.append(f"[{min_avg} Minutes]")
    if niche_count:
        top_n_kw = [k for k, c in niche_count.most_common(2) if c >= n * 0.3]
        if top_n_kw:
            formula_parts.append(f"[{'/'.join(k.title() for k in top_n_kw)}]")
    if emo_count:
        top_emo = [k for k, c in emo_count.most_common(2) if c >= n * 0.3]
        if top_emo:
            formula_parts.append(f"[{'/'.join(k.title() for k in top_emo)}]")
    if brand_count:
        top_b = [k.title() for k, c in brand_count.most_common(1)
                 if c >= n * 0.2]
        if top_b:
            formula_parts.append(f"[{top_b[0]}]")
    if pipe_count >= n * 0.4:
        formula_parts.append("| [Pillar Keyword]")
    formula = " + ".join(formula_parts) if formula_parts else \
              "(Không có pattern dominant — title đa dạng, ngẫu nhiên)"

    return {
        "patterns": pats,
        "formula": formula,
        "title_length_avg": length_avg,
        "minute_avg": min_avg,
        "n_analyzed": n,
    }


# ============================================================
# G3. WORST vs TOP comparison
# ============================================================

def compare_worst_vs_top(
    top_videos: List[Dict[str, Any]],
    worst_videos: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """So sánh patterns 2 nhóm → ra "thiếu gì" cho video worst.

    Returns: {
      "missing_patterns": [{"pattern", "top_pct", "worst_pct"}, ...],
      "per_video_diag": [{"video_id", "title", "missing": [...]}, ...],
      "minute_stats": {"top_avg", "worst_avg", "diff"},
      "summary": "<text>",
    }
    """
    if not top_videos or not worst_videos:
        return {"missing_patterns": [], "per_video_diag": []}

    top_ext = [_extract_patterns(v.get("title", "")) for v in top_videos]
    worst_ext = [_extract_patterns(v.get("title", "")) for v in worst_videos]

    def pct_with(ext_list, fn):
        return round(100 * sum(1 for e in ext_list if fn(e))
                     / max(1, len(ext_list)))

    # Minute stats — quan trọng: nhiều niche có "sweet spot" độ dài
    top_min = [e["minute_n"] for e in top_ext if e["minute_n"]]
    worst_min = [e["minute_n"] for e in worst_ext if e["minute_n"]]
    top_min_avg = round(sum(top_min) / len(top_min)) if top_min else 0
    worst_min_avg = round(sum(worst_min) / len(worst_min)) if worst_min else 0

    # Top niche keywords specifically dominant in TOP
    top_niche_count = Counter()
    for e in top_ext:
        for k in e["niche_kw"]:
            top_niche_count[k] += 1
    worst_niche_count = Counter()
    for e in worst_ext:
        for k in e["niche_kw"]:
            worst_niche_count[k] += 1

    # Find keyword dominant trong TOP nhưng yếu ở WORST
    n_top = len(top_ext)
    n_worst = len(worst_ext)
    keyword_gaps = []
    for kw, c in top_niche_count.most_common(10):
        tp = round(100 * c / n_top)
        wp = round(100 * worst_niche_count.get(kw, 0) / max(1, n_worst))
        if tp - wp >= 15:
            keyword_gaps.append({"keyword": kw, "top_pct": tp,
                                  "worst_pct": wp, "delta": tp - wp})

    checks = [
        ("Có số phút đầu title", lambda e: e["minute_n"] > 0),
        ("Có từ khóa niche chính", lambda e: bool(e["niche_kw"])),
        ("Có brand/character name", lambda e: bool(e["brand_kw"])),
        ("Có emotion word", lambda e: bool(e["emotion_kw"])),
        ("Có | hoặc - tách 2 phần", lambda e: e["has_pipe_or_dash"]),
        ("Title 60-90 ký tự", lambda e: 60 <= e["length"] <= 90),
        ("KHÔNG có CAPS WORD (như ULTIMATE)",
         lambda e: not e["has_caps_word"]),
    ]

    missing = []
    for name, fn in checks:
        tp = pct_with(top_ext, fn)
        wp = pct_with(worst_ext, fn)
        # Lowered to 15pp threshold (was 20)
        if tp - wp >= 15:
            missing.append({
                "pattern": name,
                "top_pct": tp,
                "worst_pct": wp,
                "delta": tp - wp,
            })

    # Add minute gap as a missing pattern
    if top_min_avg and worst_min_avg and (top_min_avg - worst_min_avg >= 5):
        missing.insert(0, {
            "pattern": (f"Độ dài video ~{top_min_avg} phút "
                        f"(WORST chỉ {worst_min_avg} phút)"),
            "top_pct": 100,
            "worst_pct": 0,
            "delta": top_min_avg - worst_min_avg,
        })

    # Add keyword gaps
    for kg in keyword_gaps[:3]:
        missing.append({
            "pattern": f"Keyword '{kg['keyword'].upper()}' trong title",
            "top_pct": kg["top_pct"],
            "worst_pct": kg["worst_pct"],
            "delta": kg["delta"],
        })

    # Per-video diagnosis
    per_video = []
    for v, e in zip(worst_videos[:10], worst_ext[:10]):
        miss = []
        # Minute gap
        if top_min_avg and (not e["minute_n"] or
                            top_min_avg - e["minute_n"] >= 5):
            miss.append(f"Độ dài ngắn — nên ~{top_min_avg} phút")
        # Caps word penalty
        if e["has_caps_word"]:
            miss.append("Có CAPS WORD (như ULTIMATE) — bỏ đi")
        # Missing patterns
        for name, fn in checks:
            tp = pct_with(top_ext, fn)
            if tp >= 50 and not fn(e):
                miss.append(name)
        # Missing top keywords
        for kg in keyword_gaps[:3]:
            if kg["keyword"] not in e["niche_kw"]:
                miss.append(f"Thêm keyword '{kg['keyword'].upper()}'")
        if miss:
            per_video.append({
                "video_id": v.get("video_id"),
                "title": v.get("title", ""),
                "ctr": v.get("ctr", 0),
                "missing": miss[:5],
            })

    summary_parts = []
    if top_min_avg and worst_min_avg:
        summary_parts.append(
            f"TOP video TB ~{top_min_avg} phút, WORST chỉ ~{worst_min_avg} "
            f"phút. Video càng dài → CTR càng cao (sweet spot này).")
    if keyword_gaps:
        kws = [kg["keyword"] for kg in keyword_gaps[:3]]
        summary_parts.append(
            f"Keyword CRITICAL trong TOP: {', '.join(kws).upper()}.")
    summary = " ".join(summary_parts) if summary_parts else \
              ("Pattern TOP/WORST khá tương tự — khác biệt nằm ở "
               "THUMBNAIL hơn là TITLE.")

    return {
        "missing_patterns": missing,
        "per_video_diag": per_video,
        "minute_stats": {
            "top_avg": top_min_avg,
            "worst_avg": worst_min_avg,
            "diff": top_min_avg - worst_min_avg,
        },
        "summary": summary,
    }


# ============================================================
# G4. TRAFFIC SOURCE PLAYBOOK — SEO action theo source
# ============================================================

_SOURCE_PLAYBOOK = {
    "YT_SEARCH": {
        "name": "YouTube Search",
        "low_actions": [
            "Title ≤60 ký tự, keyword chính 50 ký tự ĐẦU",
            "Description 200+ từ, keyword phân bố đều (đầu/giữa/cuối)",
            "Tags 8-15 cụm: từ chung → cụ thể → câu hỏi",
            "Sub-title cho 5 chương đầu video (chapter markers)",
            "Hashtag #pillar #niche #brand trong description",
            "Transcript đầy đủ (caption) — Google index nội dung audio",
        ],
        "high_actions": [
            "DUY TRÌ — kênh đang ranking tốt",
            "Mở rộng keyword cluster sang long-tail variants",
            "A/B test thumbnail giữa video ranking cùng keyword",
        ],
    },
    "RELATED_VIDEO": {
        "name": "Suggested Videos",
        "low_actions": [
            "Tăng AVD: pacing cut nhanh 3-7s, b-roll, pattern interrupt",
            "Tăng CTR: A/B test thumbnail (Studio Test feature)",
            "Tag chung với top video kênh (algorithm tìm video cùng cluster)",
            "End screen 4 elements (video + playlist + sub + channel)",
            "Card mid-video tham chiếu video cùng pillar",
        ],
        "high_actions": [
            "TỐT — algorithm đang đẩy",
            "Tạo series 5-10 video cùng pillar để loop watch session",
            "Đặt playlist 'Watch Next' đầu description",
        ],
    },
    "SUGGESTED": {
        "name": "Suggested Videos",
        "low_actions": ["Tăng AVD + CTR — algorithm sẽ đẩy"],
        "high_actions": ["DUY TRÌ"],
    },
    "BROWSE": {
        "name": "Home Page / Browse",
        "low_actions": [
            "Sub loyalty yếu — push notification cho new video",
            "Community tab post tích cực (poll, image, GIF)",
            "Schedule upload đều đặn (cùng giờ, cùng ngày trong tuần)",
            "Personalize: title phù hợp gu sub cũ (xem video popular)",
        ],
        "high_actions": [
            "TỐT — sub loyalty cao",
            "Test thumbnail thumbnail style mới (sub đã quen)",
        ],
    },
    "SUBSCRIBER": {
        "name": "Subscriber Feed",
        "low_actions": [
            "Push CTA subscribe trong video (đầu + outro)",
            "Pin comment yêu cầu subscribe",
            "Channel trailer mạnh (auto-play khi vào page)",
        ],
        "high_actions": [
            "⚠ NẾU >50%: phụ thuộc sub cũ. Cần đẩy SEARCH + RELATED",
            "Tạo channel keyword + about để hút new sub",
            "Optimize thumbnail mobile-first (sub cũ click qua feed)",
        ],
    },
    "EXTERNAL": {
        "name": "External (collab, social, embed)",
        "low_actions": [
            "Đăng video lên TikTok/IG Reels/Facebook (link YT trong bio)",
            "Collab cross-promote với kênh cùng pillar",
            "Embed video lên blog/website đối tác",
            "Share trong group cộng đồng (Reddit, Discord)",
        ],
        "high_actions": ["DUY TRÌ collab + social activity"],
    },
    "EXT_URL": {  # Alias
        "name": "External",
        "low_actions": [
            "Đăng video lên TikTok/IG Reels/Facebook (link YT trong bio)",
            "Collab cross-promote với kênh cùng pillar",
        ],
        "high_actions": ["DUY TRÌ"],
    },
    "END_SCREEN": {
        "name": "End Screen",
        "low_actions": [
            "Đảm bảo MỌI video có 4 End Screen elements",
            "Video gợi ý phải cùng pillar (algorithm match)",
            "Thời lượng 15-20s outro để viewer click",
        ],
        "high_actions": ["DUY TRÌ"],
    },
    "PLAYLIST": {
        "name": "Playlist",
        "low_actions": [
            "Tạo playlist theo pillar (5-10 playlist)",
            "Đặt playlist đầu description video",
            "Pin playlist hot lên channel page",
        ],
        "high_actions": ["DUY TRÌ — playlist đang đẩy auto-play"],
    },
    "NOTIFICATION": {
        "name": "Notification (bell)",
        "low_actions": [
            "CTA bật bell notification trong video",
            "Upload đều đặn để bell-sub active",
        ],
        "high_actions": ["DUY TRÌ"],
    },
    "SHORTS": {
        "name": "Shorts Feed",
        "low_actions": [
            "Mỗi tuần upload 2-3 Shorts cùng pillar",
            "Title Shorts ≤40 ký tự, hashtag #shorts #pillar",
            "Hook 1-2 giây đầu, không có intro",
        ],
        "high_actions": ["DUY TRÌ + tạo Shorts series"],
    },
}


def traffic_source_playbook(
    traffic_sources: List[Dict[str, Any]],
    channel_summary: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Theo source distribution, ra playbook SEO cụ thể.

    Returns: list of {source, name, share_pct, status, actions: [...]}
    """
    if not traffic_sources:
        return []
    # Benchmark range (low, high)
    bench = {
        "YT_SEARCH": (10, 25),
        "SEARCH": (10, 25),
        "RELATED_VIDEO": (30, 50),
        "SUGGESTED": (30, 50),
        "BROWSE": (15, 30),
        "SUBSCRIBER": (20, 40),
        "EXT_URL": (3, 15),
        "EXTERNAL": (3, 15),
        "END_SCREEN": (2, 8),
        "PLAYLIST": (3, 15),
        "NOTIFICATION": (1, 5),
        "SHORTS": (10, 40),
    }
    result = []
    for ts in traffic_sources:
        src = ts.get("source", "")
        pct = ts.get("pct", 0) or 0
        pb = _SOURCE_PLAYBOOK.get(src)
        if not pb:
            continue
        bm = bench.get(src, (0, 100))
        if pct < bm[0]:
            status = "LOW"
            actions = pb["low_actions"]
        elif pct > bm[1]:
            status = "HIGH"
            actions = pb["high_actions"]
        else:
            status = "OK"
            actions = ["Trong khoảng tốt — duy trì chiến lược hiện tại."]
        result.append({
            "source": src,
            "name": pb["name"],
            "share_pct": pct,
            "views": ts.get("views", 0),
            "benchmark": f"{bm[0]}-{bm[1]}%",
            "status": status,
            "actions": actions[:5],
        })
    return result


# ============================================================
# G5. DROP POINTS → TITLE STRATEGY
# ============================================================

def drop_points_vs_title(
    retention_videos: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Phân tích drop point lớn nhất → chẩn đoán title strategy.

    Returns: list of {video_id, title, biggest_drop_at, drop_pct,
                      diagnosis, action}
    """
    out = []
    for r in retention_videos:
        drops = r.get("drop_points", []) or []
        if not drops:
            continue
        # Drop point lớn nhất
        biggest = max(drops, key=lambda d: d.get("drop_pct", 0))
        at = biggest.get("at_pct", 0)
        dp = biggest.get("drop_pct", 0)
        title = r.get("title", "")

        # Diagnose theo vị trí drop
        if at <= 10:
            diagnosis = ("Drop ở Hook (0-10%) — title hứa A nhưng intro "
                         "không deliver A.")
            action = ("Mở video bằng RESULT-FIRST (5s đầu show ngay output) "
                      "hoặc PROBLEM-PUNCH (gặp vấn đề ngay). Cắt bỏ "
                      "intro logo + 'Hello guys'.")
        elif at <= 30:
            diagnosis = ("Drop ở Early (10-30%) — pacing chậm sau hook. "
                         "Có thể intro/recap quá dài.")
            action = ("Cut hết shot tĩnh >3s. B-roll mỗi 5-7s. Pattern "
                      "interrupt (zoom, sound, text overlay) ở giây 30-45.")
        elif at <= 60:
            diagnosis = ("Drop ở giữa (30-60%) — content sag. Viewer mất "
                         "hứng vì story arc phẳng.")
            action = ("Re-introduce 'pillar' giữa video: nhắc lại stakes, "
                      "tease kết quả. Áp Curiosity Gap mỗi 90s.")
        elif at <= 85:
            diagnosis = ("Drop ở Late (60-85%) — viewer đã thỏa mãn, "
                         "không thấy stakes mới.")
            action = ("Escalation rule: payoff lớn nhất ở 70-80%. Outro "
                      "≤15s. End screen elements đặt sớm (60-90s trước "
                      "outro).")
        else:
            diagnosis = ("Drop ở Outro (85-100%) — bình thường, nhưng "
                         "có thể outro quá dài.")
            action = ("Đảm bảo End Screen có 4 elements (video tiếp + "
                      "playlist + sub + channel). Outro 10-15s thôi.")

        out.append({
            "video_id": r.get("video_id", ""),
            "title": title,
            "views": r.get("views", 0),
            "avg_retention": r.get("avg_retention", 0),
            "biggest_drop_at": at,
            "drop_pct": dp,
            "diagnosis": diagnosis,
            "action": action,
        })
    return out


# ============================================================
# G6. AUDIENCE → KEYWORD CLUSTER
# ============================================================

# Map (age_group, gender, niche_hint) → keyword cluster
_KEYWORD_LIBRARY = {
    # Toy unboxing — female 25-34, mobile
    "toy_unboxing": [
        "satisfying unboxing", "asmr unboxing", "playset toys",
        "kitchen playset", "doll playset", "miniature toys",
        "review toys", "cute toys", "kids playtime",
        "compilation toys", "kid friendly", "no music",
    ],
    "asmr_sand_slime": [
        "satisfying slime", "asmr slime", "slime crunchy",
        "kinetic sand", "satisfying sand", "color slime",
        "no music asmr", "sleep aid",
    ],
    "paper_doll_glow": [
        "paper doll", "paper diy", "glow paper", "couple drawing",
        "diy paper craft", "trending tiktok", "satisfying drawing",
    ],
    "horror_stories": [
        "horror story", "scary radio", "creepypasta",
        "ghost story narrated", "horror compilation",
        "true crime", "scary stories at night",
    ],
    "lego_animation": [
        "lego animation", "lego stop motion", "lego brick",
        "lego film", "brick story",
    ],
    "car_crush_experiment": [
        "crushing experiment", "car crushing", "satisfying crush",
        "crushing toys", "asmr crush", "experiment car",
    ],
    "diy_mini_tractor": [
        "mini tractor diy", "mini machine", "diy farm",
        "tractor toy", "rc tractor", "satisfying machine",
    ],
    "construction_vehicle": [
        "construction toys", "excavator toy", "dump truck",
        "construction vehicle", "kids vehicle",
    ],
    "numberblocks_slime": [
        "number slime", "numberblocks", "math slime",
        "learning slime", "rainbow numbers",
    ],
    # Default
    "general": [
        "compilation", "best of", "review", "tutorial",
        "satisfying", "asmr", "kid friendly",
    ],
}


def audience_keyword_cluster(
    audience_full: Dict[str, Any],
    niche: str = "general"
) -> Dict[str, Any]:
    """Map demographics + niche → keyword cluster đề xuất.

    Returns: {
      "primary": [...],   # 5-7 keyword chính (high priority)
      "secondary": [...], # 8-12 keyword phụ
      "modifiers": [...], # 5-7 modifier (mobile-friendly, no-music...)
      "reasoning": "<text>",
    }
    """
    af = audience_full or {}
    devices = af.get("devices", {}) or {}
    demo = af.get("demographics", []) or []
    countries = af.get("countries", []) or []

    # Niche library
    base_keywords = _KEYWORD_LIBRARY.get(niche, _KEYWORD_LIBRARY["general"])

    # Top age group + gender
    by_age, by_gender = {}, {}
    for d in demo:
        by_age[d.get("age_group", "")] = by_age.get(d.get("age_group", ""), 0) + d.get("pct", 0)
        by_gender[d.get("gender", "")] = by_gender.get(d.get("gender", ""), 0) + d.get("pct", 0)
    top_age = max(by_age.items(), key=lambda x: x[1])[0] if by_age else ""
    top_gender = max(by_gender.items(), key=lambda x: x[1])[0] if by_gender else ""

    mobile_pct = devices.get("MOBILE", 0) or 0
    top_country = countries[0].get("country", "") if countries else ""

    # Modifiers theo audience
    modifiers = []
    if mobile_pct > 80:
        modifiers += ["short title", "big text thumbnail",
                      "vertical-friendly hook"]
    if "female" in top_gender.lower():
        modifiers += ["pastel color", "cute aesthetic", "diy gentle"]
    elif "male" in top_gender.lower():
        modifiers += ["action verbs", "bold colors", "experiment"]

    if "age13-17" in top_age or "age18-24" in top_age:
        modifiers += ["trending", "viral", "tiktok style"]
    elif "age25-34" in top_age:
        modifiers += ["satisfying", "asmr", "lifestyle"]
    elif "age35-44" in top_age:
        modifiers += ["family friendly", "educational", "review"]

    if top_country in ("VN", "VI"):
        modifiers.append("tiếng Việt")
    elif top_country in ("ID", "MY", "TH", "PH"):
        modifiers.append("Southeast Asia friendly")
    elif top_country in ("US", "GB", "AU", "CA"):
        modifiers.append("English native")

    primary = base_keywords[:7]
    secondary = base_keywords[7:] + [
        f"{m} {primary[0].split()[0] if primary else 'video'}"
        for m in modifiers[:3]
    ]

    reasoning = (
        f"Audience chính: {top_gender} {top_age}, mobile {mobile_pct:.0f}%, "
        f"top country {top_country}. Niche: {niche}.")

    return {
        "primary": primary,
        "secondary": secondary[:12],
        "modifiers": list(dict.fromkeys(modifiers))[:7],
        "reasoning": reasoning,
        "niche": niche,
    }


# ============================================================
# G7. INSIDE PERIOD DELTA — so sánh chu kỳ
# ============================================================

def inside_period_delta(account_tag: str,
                         days_now: int = 7,
                         days_prev: int = 7,
                         offset: int = 7) -> Dict[str, Any]:
    """So sánh metrics chu kỳ hiện tại vs chu kỳ trước.

    days_now=7, offset=7, days_prev=7
    → so 0-7 ngày trước với 7-14 ngày trước.

    Returns: {
      "current": {views, subs_net, avd, ctr},
      "previous": {...},
      "delta": {views_pct, subs_delta, avd_pct, ctr_pct},
      "alerts": [list]
    }
    """
    from .analytics_inside import _connect
    conn = _connect()
    if not conn:
        return {}
    try:
        cur = conn.cursor()

        def _period(d_offset_start, d_offset_end):
            # Views + subs từ channel_daily_metrics (đã có account_tag)
            cur.execute(
                "SELECT "
                "  SUM(CAST(views AS INTEGER)), "
                "  SUM(CAST(subscribers_gained AS INTEGER)), "
                "  SUM(CAST(subscribers_lost AS INTEGER)) "
                "FROM channel_daily_metrics "
                "WHERE account_tag = ? "
                "AND day >= date('now', ?) AND day < date('now', ?)",
                (account_tag,
                 f"-{d_offset_end} days",
                 f"-{d_offset_start} days"))
            row = cur.fetchone()
            views = int(row[0] or 0)
            gained = int(row[1] or 0)
            lost = int(row[2] or 0)
            # AVD weighted = SUM(views*avd)/SUM(views) — qua JOIN videos
            cur.execute(
                "SELECT SUM(CAST(vds.views AS INTEGER)) as v, "
                "  SUM(CAST(vds.views AS INTEGER) * "
                "      CAST(vds.average_view_duration AS REAL)) as wsum "
                "FROM video_daily_stats vds "
                "JOIN videos v ON v.video_id = vds.video_id "
                "WHERE v.account_tag = ? "
                "AND vds.day >= date('now', ?) AND vds.day < date('now', ?)",
                (account_tag,
                 f"-{d_offset_end} days",
                 f"-{d_offset_start} days"))
            r2 = cur.fetchone()
            vsum = int(r2[0] or 0) if r2 else 0
            wsum = float(r2[1] or 0) if r2 else 0
            avd = wsum / vsum if vsum > 0 else 0
            # CTR thumbnail
            cur.execute(
                "SELECT AVG(CAST(thumbnail_ctr AS REAL)) "
                "FROM video_thumbnail_daily "
                "WHERE account_tag = ? "
                "AND day >= date('now', ?) AND day < date('now', ?)",
                (account_tag,
                 f"-{d_offset_end} days",
                 f"-{d_offset_start} days"))
            ctr = (cur.fetchone() or [0])[0] or 0
            return {
                "views": views,
                "subs_gained": gained,
                "subs_lost": lost,
                "subs_net": gained - lost,
                "avd": round(avd, 1),
                "ctr": round(ctr * 100, 2),
            }

        current = _period(0, days_now)
        previous = _period(offset, offset + days_prev)

        def _pct_delta(a, b):
            if b <= 0:
                return None
            return round(100 * (a - b) / b, 1)

        delta = {
            "views_pct": _pct_delta(current["views"], previous["views"]),
            "subs_net_delta": current["subs_net"] - previous["subs_net"],
            "avd_pct": _pct_delta(current["avd"], previous["avd"]),
            "ctr_pct": _pct_delta(current["ctr"], previous["ctr"]),
        }

        # Alerts
        alerts = []
        if delta["views_pct"] is not None and delta["views_pct"] < -20:
            alerts.append({
                "level": "bad",
                "msg": (f"Views giảm {delta['views_pct']:.0f}% so chu kỳ "
                        f"trước — check video mới gần nhất.")})
        if delta["ctr_pct"] is not None and delta["ctr_pct"] < -15:
            alerts.append({
                "level": "warn",
                "msg": (f"CTR giảm {delta['ctr_pct']:.0f}% — thumbnail "
                        f"mới không hiệu quả.")})
        if delta["avd_pct"] is not None and delta["avd_pct"] < -10:
            alerts.append({
                "level": "warn",
                "msg": (f"AVD giảm {delta['avd_pct']:.0f}% — pacing/hook "
                        f"video mới yếu hơn.")})
        if delta["subs_net_delta"] < -20:
            alerts.append({
                "level": "bad",
                "msg": (f"Subs NET sụt {delta['subs_net_delta']} so chu kỳ "
                        f"trước — content có thể chệch pillar.")})
        if (current["subs_net"] < 0 and previous["subs_net"] > 0):
            alerts.append({
                "level": "bad",
                "msg": "Subs NET CHUYỂN TỪ DƯƠNG → ÂM. Audit ngay."})

        return {
            "current": current,
            "previous": previous,
            "delta": delta,
            "alerts": alerts,
            "period_now_days": days_now,
            "period_prev_days": days_prev,
            "offset_days": offset,
        }
    finally:
        conn.close()


# ============================================================
# G8. AUDIT DESCRIPTION — 200+ từ, hashtag, timestamp
# ============================================================

def _count_words(text: str) -> int:
    if not text:
        return 0
    return len(re.findall(r"\w+", text))


def audit_description(
    videos: List[Dict[str, Any]],
    niche_data: Dict[str, Any],
    top_n: int = 10,
) -> Dict[str, Any]:
    """Audit DESCRIPTION 10 video gần nhất.

    Check: word count, hashtag count, timestamp, keyword distribution,
    CTA subscribe, social links.
    """
    if not videos:
        return {}
    nd = niche_data.get("description", {}) or {}
    min_words = nd.get("min_words", 200)
    target_hashtags = nd.get("hashtags_count", (3, 5))

    per_video = []
    failed_count = 0
    for v in videos[:top_n]:
        desc = (v.get("description") or "")
        wc = _count_words(desc)
        hashtags = re.findall(r"#\w+", desc)
        timestamps = re.findall(r"\d{1,2}:\d{2}", desc)
        has_subscribe = bool(re.search(r"subscribe|🔔", desc, re.IGNORECASE))
        has_link = bool(re.search(r"https?://", desc))
        issues = []
        if wc < min_words:
            issues.append(f"Quá ngắn {wc} từ (cần ≥{min_words})")
        if len(hashtags) < target_hashtags[0]:
            issues.append(f"Hashtag thiếu ({len(hashtags)}, cần "
                          f"≥{target_hashtags[0]})")
        if len(timestamps) < 3:
            issues.append(f"Timestamps thiếu ({len(timestamps)}, cần ≥3)")
        if not has_subscribe:
            issues.append("Thiếu CTA Subscribe")
        if not has_link:
            issues.append("Thiếu link playlist/social")
        if issues:
            failed_count += 1
        per_video.append({
            "video_id": v.get("video_id", ""),
            "title": v.get("title", "")[:60],
            "word_count": wc,
            "hashtags_count": len(hashtags),
            "timestamps_count": len(timestamps),
            "has_subscribe": has_subscribe,
            "has_link": has_link,
            "issues": issues,
        })

    avg_words = round(sum(p["word_count"] for p in per_video)
                      / max(1, len(per_video)))
    fail_rate = round(100 * failed_count / max(1, len(per_video)))

    template = nd.get("template", "")
    distribution = nd.get("keyword_distribution",
                          "Keyword chính trong 25 từ đầu + lặp 3-5 lần")
    return {
        "avg_word_count": avg_words,
        "min_required": min_words,
        "fail_rate_pct": fail_rate,
        "per_video": per_video,
        "template_recommended": template,
        "keyword_distribution_rule": distribution,
    }


# ============================================================
# G9. AUDIT TAGS — 8-15 tag hierarchy
# ============================================================

def audit_tags(
    videos: List[Dict[str, Any]],
    niche_data: Dict[str, Any],
    top_n: int = 10,
) -> Dict[str, Any]:
    """Audit TAGS 10 video gần nhất.

    Check: số tag, tag length, hierarchy (broad/specific/question/branded).
    """
    if not videos:
        return {}
    nd = niche_data.get("tags", {}) or {}
    count_range = nd.get("count_range", (8, 15))
    recommended_broad = nd.get("broad", [])
    recommended_specific = nd.get("specific", [])

    per_video = []
    failed = 0
    all_tags_used = Counter()
    for v in videos[:top_n]:
        tags = v.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        n = len(tags)
        for t in tags:
            all_tags_used[str(t).lower()] += 1
        long_tags = [t for t in tags if len(str(t)) > 50]
        very_short = [t for t in tags if len(str(t)) < 3]
        # Match niche broad/specific
        tag_set = {str(t).lower() for t in tags}
        has_broad = sum(1 for b in recommended_broad
                        if b.lower() in tag_set)
        has_specific = sum(1 for s in recommended_specific
                           if s.lower() in tag_set)
        issues = []
        if n < count_range[0]:
            issues.append(f"Thiếu tag ({n}, cần {count_range[0]}-{count_range[1]})")
        elif n > count_range[1]:
            issues.append(f"Tag quá nhiều ({n}) — algorithm bỏ qua tag dư")
        if long_tags:
            issues.append(f"{len(long_tags)} tag >50 ký tự — quá dài")
        if has_broad < 2:
            issues.append(f"Thiếu tag BROAD ({has_broad}, cần ≥2)")
        if has_specific < 2:
            issues.append(f"Thiếu tag SPECIFIC ({has_specific}, cần ≥2)")
        if issues:
            failed += 1
        per_video.append({
            "video_id": v.get("video_id", ""),
            "title": v.get("title", "")[:60],
            "n_tags": n,
            "has_broad_match": has_broad,
            "has_specific_match": has_specific,
            "issues": issues,
            "tags_sample": tags[:5],
        })

    most_used = [{"tag": t, "n": c} for t, c in all_tags_used.most_common(15)]
    fail_rate = round(100 * failed / max(1, len(per_video)))
    return {
        "fail_rate_pct": fail_rate,
        "recommended_count": count_range,
        "recommended_broad": recommended_broad,
        "recommended_specific": recommended_specific,
        "most_used_tags": most_used,
        "per_video": per_video,
    }


# ============================================================
# G10. OPTIMAL UPLOAD TIMING
# ============================================================

def optimal_upload_timing(
    account_tag: str,
    videos: List[Dict[str, Any]],
    niche_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Phân tích upload time tối ưu.

    Inside data không có hourly viewer → dùng combination:
    - published_at + first-day views correlation
    - Niche library best_hours fallback
    """
    nd_upload = niche_data.get("upload_time", {}) or {}
    best_hours = nd_upload.get("best_hours_local", [(15, 18)])
    best_days = nd_upload.get("best_days", ["Saturday", "Sunday"])
    freq = nd_upload.get("frequency_per_week", (2, 4))

    # Phân tích published_at thực tế
    from datetime import datetime
    weekday_views = {}
    hour_views = {}
    for v in videos[:30]:
        pa = v.get("published_at") or ""
        if not pa:
            continue
        try:
            dt = datetime.fromisoformat(pa.replace("Z", "+00:00"))
            wd = dt.strftime("%A")
            hr = dt.hour
            vc = int(v.get("view_count") or v.get("views") or 0)
            weekday_views.setdefault(wd, []).append(vc)
            hour_views.setdefault(hr, []).append(vc)
        except Exception:
            continue

    actual_best_wd = sorted(
        [(wd, sum(v) / len(v)) for wd, v in weekday_views.items()],
        key=lambda x: -x[1])[:3]
    actual_best_hr = sorted(
        [(hr, sum(v) / len(v)) for hr, v in hour_views.items()],
        key=lambda x: -x[1])[:3]

    return {
        "niche_recommended_hours": best_hours,
        "niche_recommended_days": best_days,
        "niche_frequency_per_week": freq,
        "premiere_recommended": nd_upload.get("premiere", False),
        "actual_best_weekdays": [{"day": d, "avg_views": int(v)}
                                  for d, v in actual_best_wd],
        "actual_best_hours": [{"hour": h, "avg_views": int(v)}
                               for h, v in actual_best_hr],
        "videos_analyzed": len(videos[:30]),
    }


# ============================================================
# G11. ENGAGEMENT SIGNALS
# ============================================================

def engagement_signals(
    videos: List[Dict[str, Any]],
    niche_data: Dict[str, Any],
    top_n: int = 20,
) -> Dict[str, Any]:
    """Phân tích like-to-view + comment-to-view + share-rate baseline.

    YouTube algorithm dùng engagement rate làm tín hiệu mạnh.
    """
    if not videos:
        return {}
    baseline = niche_data.get("engagement_baseline", {})
    bl_like = baseline.get("like_view_pct", 3.0)
    bl_comment = baseline.get("comment_view_pct", 0.3)

    rows = []
    for v in videos[:top_n]:
        views = int(v.get("view_count") or v.get("views") or 0)
        likes = int(v.get("like_count") or v.get("likes") or 0)
        comments = int(v.get("comment_count") or v.get("comments") or 0)
        if views <= 0:
            continue
        like_pct = round(100 * likes / views, 2)
        cmt_pct = round(100 * comments / views, 3)
        rows.append({
            "video_id": v.get("video_id", ""),
            "title": v.get("title", "")[:60],
            "views": views,
            "like_pct": like_pct,
            "comment_pct": cmt_pct,
        })

    if not rows:
        return {}

    avg_like = round(sum(r["like_pct"] for r in rows) / len(rows), 2)
    avg_cmt = round(sum(r["comment_pct"] for r in rows) / len(rows), 3)

    low_engage = [r for r in rows
                   if r["like_pct"] < bl_like * 0.6
                   or r["comment_pct"] < bl_comment * 0.6]
    high_engage = [r for r in rows
                    if r["like_pct"] > bl_like * 1.3
                    and r["comment_pct"] > bl_comment * 1.2][:5]

    status_like = ("bad" if avg_like < bl_like * 0.7
                    else "warn" if avg_like < bl_like
                    else "good")
    status_cmt = ("bad" if avg_cmt < bl_comment * 0.5
                   else "warn" if avg_cmt < bl_comment
                   else "good")

    return {
        "videos_analyzed": len(rows),
        "avg_like_pct": avg_like,
        "avg_comment_pct": avg_cmt,
        "baseline_like_pct": bl_like,
        "baseline_comment_pct": bl_comment,
        "status_like": status_like,
        "status_comment": status_cmt,
        "low_engagement_videos": low_engage[:10],
        "high_engagement_videos": high_engage,
        "actions": _engagement_actions(status_like, status_cmt, avg_like,
                                        avg_cmt, bl_like, bl_comment),
    }


def _engagement_actions(s_like, s_cmt, av_l, av_c, bl_l, bl_c) -> list:
    out = []
    if s_like == "bad":
        out.append(f"Like-rate {av_l}% thấp hơn baseline {bl_l}% — "
                   f"CTA 'tap like nếu thấy hay' rõ ràng đầu+giữa video, "
                   f"thêm pinned comment kêu gọi like.")
    if s_cmt == "bad":
        out.append(f"Comment-rate {av_c}% thấp hơn baseline {bl_c}% — "
                   f"đặt câu hỏi cuối video, reply mọi comment 24h đầu, "
                   f"pin câu thú vị nhất.")
    if s_like == "good" and s_cmt == "good":
        out.append("Engagement TỐT — duy trì + tận dụng community tab.")
    return out


# ============================================================
# G12. CAPTION AUDIT — multi-language strategy
# ============================================================

# Country → preferred language
_COUNTRY_LANG = {
    "US": "English", "GB": "English", "AU": "English", "CA": "English",
    "IN": "Hindi/English", "ID": "Indonesian", "MX": "Spanish",
    "BR": "Portuguese", "DE": "German", "FR": "French", "JP": "Japanese",
    "KR": "Korean", "VN": "Vietnamese", "TH": "Thai", "PH": "Filipino/English",
    "MY": "Malay/English", "ES": "Spanish", "IT": "Italian", "TR": "Turkish",
    "RU": "Russian", "AR": "Arabic", "SA": "Arabic",
}


def caption_audit(
    audience_full: Dict[str, Any],
    niche_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Phân tích cần caption ngôn ngữ nào dựa trên top countries."""
    countries = (audience_full or {}).get("countries", []) or []
    if not countries:
        return {}
    nd_cap = niche_data.get("caption", {}) or {}
    priority_niche = nd_cap.get("priority_languages", ["English"])

    # Top 5 countries → ngôn ngữ
    top_lang_share = {}
    for c in countries[:10]:
        country_code = c.get("country", "")
        pct = c.get("pct", 0) or 0
        lang = _COUNTRY_LANG.get(country_code, "Other")
        top_lang_share[lang] = top_lang_share.get(lang, 0) + pct

    # Sort by share
    sorted_lang = sorted(top_lang_share.items(), key=lambda x: -x[1])

    recommended = []
    for lang, share in sorted_lang[:5]:
        if share >= 5:  # >=5% market share
            recommended.append({
                "language": lang,
                "audience_share_pct": round(share, 1),
                "priority_in_niche": lang in priority_niche,
            })

    return {
        "recommended_languages": recommended,
        "niche_priority_languages": priority_niche,
        "auto_translate_title": nd_cap.get("auto_translate_title", False),
        "auto_caption": nd_cap.get("auto_caption", True),
        "total_audience_in_top5_lang": round(
            sum(r["audience_share_pct"] for r in recommended), 1),
    }


# ============================================================
# G13. CONTENT STRATEGY GAP — pillars covered vs missing
# ============================================================

def content_strategy_gap(
    videos: List[Dict[str, Any]],
    niche_data: Dict[str, Any],
    top_n: int = 30,
) -> Dict[str, Any]:
    """Phân tích pillars đã làm vs niche pillars khuyến nghị."""
    pillars = niche_data.get("content_pillars", []) or []
    if not pillars or not videos:
        return {}
    # Build pillar keyword sets
    pillar_keywords = {}
    for p in pillars:
        # 'unboxing-kitchen-playset' → ['unboxing', 'kitchen', 'playset']
        kws = [k.lower() for k in p.replace("_", "-").split("-")]
        pillar_keywords[p] = kws

    # Match video titles to pillars
    pillar_video_count = {p: 0 for p in pillars}
    for v in videos[:top_n]:
        title = (v.get("title") or "").lower()
        for p, kws in pillar_keywords.items():
            if all(k in title for k in kws[:2]):  # first 2 kw must match
                pillar_video_count[p] += 1

    total = sum(pillar_video_count.values())
    covered = [{"pillar": p, "video_count": c,
                "share_pct": round(100 * c / max(1, total))}
               for p, c in pillar_video_count.items() if c > 0]
    missing = [p for p in pillars if pillar_video_count[p] == 0]

    # Recommend mỗi pillar 2-3 video tới
    new_video_ideas = []
    for p in missing[:5]:
        kws = pillar_keywords[p]
        new_video_ideas.append({
            "pillar": p,
            "title_template": f"[X Minutes] {' '.join(kws).title()} | "
                              f"{niche_data.get('name', '')}",
            "priority": "high",
        })

    return {
        "pillars_total": len(pillars),
        "pillars_covered": len(covered),
        "pillars_missing": len(missing),
        "covered_detail": sorted(covered, key=lambda x: -x["share_pct"]),
        "missing_pillars": missing,
        "new_video_ideas": new_video_ideas,
        "niche_pillars_full": pillars,
    }


# ============================================================
# G14. TITLE POSITION + FORMULA AUDIT
# ============================================================

_TITLE_FORMULAS_4 = {
    "Number-Promise": "Format: [Number] + [Niche] + [Promise] (VD: '10 Tips ...')",
    "How-To": "Format: How to [Action] + [Result] (VD: 'How to grow channel')",
    "Versus": "Format: [A] vs [B] + [Result] (VD: 'iPhone vs Android')",
    "Curiosity-Gap": "Format: [Hook question/teaser] (VD: 'You won't believe...')",
}


def title_position_formula_audit(
    videos: List[Dict[str, Any]],
    niche_data: Dict[str, Any],
    top_n: int = 15,
) -> Dict[str, Any]:
    """Audit title position keyword + match 4 SEO formulas."""
    nd_title = niche_data.get("title", {}) or {}
    keyword_position = nd_title.get("keyword_position",
                                     "Keyword chính trong 30 ký tự đầu")
    optimal_length = nd_title.get("optimal_length", (50, 80))
    niche_formula = nd_title.get("formula_best", "")

    per_video = []
    formula_match_count = {f: 0 for f in _TITLE_FORMULAS_4}
    issues_count = 0
    for v in videos[:top_n]:
        title = v.get("title", "") or ""
        length = len(title)
        first30 = title[:30].lower()

        # Detect formula
        detected = "Other"
        if re.search(r"^\d+\s", title):
            detected = "Number-Promise"
        elif "how to" in title.lower():
            detected = "How-To"
        elif " vs " in title.lower() or " vs. " in title.lower():
            detected = "Versus"
        elif re.search(r"\?", title) or "secret" in title.lower():
            detected = "Curiosity-Gap"
        if detected in formula_match_count:
            formula_match_count[detected] += 1

        # Length check
        issues = []
        if length < optimal_length[0]:
            issues.append(f"Title ngắn ({length}, cần {optimal_length[0]}+)")
        elif length > optimal_length[1]:
            issues.append(f"Title dài ({length}, max {optimal_length[1]}) — "
                          f"có thể bị cắt")
        if issues:
            issues_count += 1
        per_video.append({
            "video_id": v.get("video_id", ""),
            "title": title,
            "length": length,
            "formula_detected": detected,
            "first30_chars": first30,
            "issues": issues,
        })

    return {
        "videos_analyzed": len(per_video),
        "niche_formula_best": niche_formula,
        "niche_keyword_position_rule": keyword_position,
        "niche_optimal_length": optimal_length,
        "formula_distribution": [
            {"formula": f, "count": c,
             "desc": _TITLE_FORMULAS_4.get(f, "")}
            for f, c in formula_match_count.items() if c > 0
        ],
        "issues_count": issues_count,
        "per_video": per_video,
    }


# ============================================================
# G15. THUMBNAIL LAYOUT AUDIT per niche
# ============================================================

def thumbnail_layout_audit(
    niche_data: Dict[str, Any],
    inside_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """Map niche thumbnail recipe + check vs current CTR performance."""
    nd_thumb = niche_data.get("thumbnail", {}) or {}
    if not nd_thumb:
        return {}

    avg_ctr_pct = (inside_summary.get("avg_thumbnail_ctr") or 0) * 100
    ctr_sweet = niche_data.get("ctr", {}).get("sweet_spot_pct", (4, 8))

    status = ("bad" if avg_ctr_pct < ctr_sweet[0]
              else "good" if avg_ctr_pct > ctr_sweet[1] * 0.8
              else "warn")

    return {
        "primary_layout": nd_thumb.get("primary_layout", ""),
        "layouts_recipe": nd_thumb.get("layouts", {}),
        "color_palette": nd_thumb.get("color_palette", ""),
        "text_words_max": nd_thumb.get("text_words_max", 5),
        "text_size_min_px": nd_thumb.get("text_size_min_px", 60),
        "face_size_pct_range": nd_thumb.get("face_size_pct", (20, 40)),
        "current_avg_ctr_pct": round(avg_ctr_pct, 2),
        "niche_sweet_spot": ctr_sweet,
        "status": status,
    }


# ============================================================
# G16. RETENTION TECHNIQUES MAP (8 techniques per niche)
# ============================================================

def retention_techniques_map(
    retention_top: List[Dict[str, Any]],
    niche_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Map 8 retention techniques (niche-specific) vs current retention gaps."""
    techniques = niche_data.get("retention_techniques", []) or []
    if not techniques:
        return {}

    # Phân tích current retention
    avg_ret = 0
    if retention_top:
        rates = [r.get("avg_retention", 0) for r in retention_top
                 if r.get("avg_retention")]
        avg_ret = round(sum(rates) / max(1, len(rates)), 1) if rates else 0

    # Weakest segment from retention_top
    weakest_count = Counter()
    for r in retention_top:
        seg = r.get("segments", {}).get("weakest_segment")
        if seg:
            weakest_count[seg] += 1
    top_weakest = weakest_count.most_common(1)[0][0] if weakest_count else None

    # Match techniques to weakest segment
    segment_technique_map = {
        "hook": [t for t in techniques if any(
            kw in t.lower() for kw in ["hook", "0-2s", "0-3s", "intro",
                                        "first", "open"])],
        "early": [t for t in techniques if any(
            kw in t.lower() for kw in ["pacing", "interrupt", "cut", "rhythm",
                                        "early"])],
        "mid": [t for t in techniques if any(
            kw in t.lower() for kw in ["mid", "stake", "escalation", "curiosity",
                                        "story", "build"])],
    }

    return {
        "all_techniques": techniques,
        "current_avg_retention_pct": avg_ret,
        "weakest_segment": top_weakest,
        "prioritized_techniques": segment_technique_map.get(top_weakest, []),
        "pacing_target": niche_data.get("pacing", {}),
    }


# ============================================================
# G17. CTR SWEET SPOT + DECAY
# ============================================================

def ctr_sweet_spot_decay(
    inside_summary: Dict[str, Any],
    thumbnail_ctr_top: List[Dict[str, Any]],
    niche_data: Dict[str, Any],
) -> Dict[str, Any]:
    """CTR niche sweet spot + decay analysis."""
    nd_ctr = niche_data.get("ctr", {}) or {}
    sweet = nd_ctr.get("sweet_spot_pct", (4, 8))
    decay_days = nd_ctr.get("decay_days", (60, 180))
    high_exc = nd_ctr.get("high_excellent", 8)
    low_warn = nd_ctr.get("low_warning", 2)

    current = (inside_summary.get("avg_thumbnail_ctr") or 0) * 100
    status = ("excellent" if current >= high_exc
              else "good" if current >= sweet[0]
              else "low" if current >= low_warn
              else "bad")

    # Top CTR videos
    top_avg = 0
    if thumbnail_ctr_top:
        top_avg = round(sum(t.get("ctr", 0) for t in thumbnail_ctr_top[:5])
                         / max(1, min(5, len(thumbnail_ctr_top))), 2)

    return {
        "current_avg_ctr_pct": round(current, 2),
        "niche_sweet_spot": sweet,
        "niche_high_excellent": high_exc,
        "niche_low_warning": low_warn,
        "niche_decay_days": decay_days,
        "status": status,
        "top5_avg_ctr_pct": top_avg,
        "gap_to_excellent_pct": round(high_exc - current, 2)
            if current < high_exc else 0,
    }


# ============================================================
# G18. CHANNEL SEO × INSIDE PERFORMANCE
# ============================================================

def channel_seo_x_inside(
    health_channel: Dict[str, Any],
    inside_summary: Dict[str, Any],
    health_keywords: Dict[str, Any],
) -> Dict[str, Any]:
    """Cross-reference channel meta SEO với Inside performance."""
    if not health_channel:
        return {}
    score = health_channel.get("score", 0) or 0
    failed = health_channel.get("failed", []) or []
    ctr = (inside_summary.get("avg_thumbnail_ctr") or 0) * 100
    avd = inside_summary.get("avg_avd_seconds", 0) or 0

    findings = []
    if score < 60 and ctr < 5:
        findings.append({
            "issue": (f"Channel meta SEO yếu ({score}/100) + CTR thumbnail "
                      f"thấp ({ctr:.1f}%)"),
            "diagnosis": ("Channel meta (about/keyword) yếu khiến algorithm "
                          "không định vị được pillar → impressions ít → CTR "
                          "thấp dù thumbnail tốt."),
            "action": (f"Sửa channel meta trước: {', '.join(failed[:3])}"),
        })
    if health_keywords:
        gaps = health_keywords.get("gaps", []) or []
        theme = health_keywords.get("theme_consistency", 0) or 0
        if gaps and theme < 60:
            findings.append({
                "issue": (f"Channel keyword không khớp với 5 keyword "
                          f"chính của niche ({len(gaps)} keyword thiếu)"),
                "diagnosis": ("Algorithm không hiểu kênh thuộc cluster nào → "
                              "SUGGESTED traffic yếu, BROWSE yếu."),
                "action": (f"Thêm vào Channel Keywords (Settings): "
                           f"{', '.join(gaps[:5])}"),
            })
    if score >= 80 and ctr < 4 and avd >= 120:
        findings.append({
            "issue": (f"Meta SEO tốt ({score}/100) + AVD ổn ({avd:.0f}s) "
                      f"NHƯNG CTR thấp ({ctr:.1f}%)"),
            "diagnosis": ("Vấn đề nằm ở THUMBNAIL/TITLE chứ không phải "
                          "channel meta. Tập trung A/B test thumbnail."),
            "action": "Redesign thumbnail 5 video gần nhất theo niche layout.",
        })
    return {
        "channel_score": score,
        "channel_failed_count": len(failed),
        "inside_ctr_pct": round(ctr, 2),
        "inside_avd_seconds": avd,
        "findings": findings,
    }


# ============================================================
# G19. COMPETITOR × INSIDE CROSS
# ============================================================

def competitor_inside_cross(
    self_data: Dict[str, Any],
    competitors: List[Dict[str, Any]],
    inside_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """So sánh mình vs đối thủ về upload frequency + pillar."""
    if not competitors:
        return {}
    # Self stats
    self_videos = self_data.get("all_v", []) or []
    self_subs = self_data.get("subs", 0) or 0
    self_total_views = sum(int(v.get("views", 0)) for v in self_videos)

    # Avg view per video kênh chính
    self_avg_view = (self_total_views / max(1, len(self_videos))
                     if self_videos else 0)

    # Frequency from published_at: số video trong 30 ngày gần nhất
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=30)
    def recent_count(videos):
        c = 0
        for v in videos:
            pa = v.get("published_at") or ""
            try:
                dt = datetime.fromisoformat(pa.replace("Z", "+00:00"))
                if dt.replace(tzinfo=None) >= cutoff:
                    c += 1
            except Exception:
                continue
        return c

    self_freq = recent_count(self_videos)

    # Competitor stats
    comp_stats = []
    for c in competitors:
        if not c.get("has"):
            continue
        cv = c.get("all_v", []) or []
        ctot = sum(int(v.get("views", 0)) for v in cv)
        c_avg = ctot / max(1, len(cv))
        c_freq = recent_count(cv)
        comp_stats.append({
            "title": c.get("title", ""),
            "subs": c.get("subs", 0),
            "videos_30d": c_freq,
            "avg_view": int(c_avg),
            "total_videos": len(cv),
        })

    if not comp_stats:
        return {}

    # Aggregate
    comp_avg_freq = sum(c["videos_30d"] for c in comp_stats) / len(comp_stats)
    comp_avg_view = sum(c["avg_view"] for c in comp_stats) / len(comp_stats)

    findings = []
    if self_freq < comp_avg_freq * 0.6:
        findings.append({
            "issue": (f"Upload frequency của bạn ({self_freq} video/30d) "
                      f"chỉ bằng {round(self_freq/max(1, comp_avg_freq)*100)}% "
                      f"đối thủ ({comp_avg_freq:.1f} video/30d TB)"),
            "action": "Tăng cadence: ít nhất 3 video/tuần để algorithm coi "
                      "là active channel.",
        })
    if self_avg_view < comp_avg_view * 0.5:
        findings.append({
            "issue": (f"Avg view/video của bạn ({int(self_avg_view):,}) "
                      f"chỉ bằng {round(self_avg_view/max(1, comp_avg_view)*100)}% "
                      f"đối thủ ({int(comp_avg_view):,} TB)"),
            "action": "Audit pillar: đối thủ đăng pillar gì hot mà bạn "
                      "chưa làm? Copy formula + variation.",
        })

    return {
        "self": {
            "subs": self_subs,
            "videos_30d": self_freq,
            "avg_view": int(self_avg_view),
            "total_videos": len(self_videos),
        },
        "competitors": comp_stats[:8],
        "competitor_avg_freq_30d": round(comp_avg_freq, 1),
        "competitor_avg_view": int(comp_avg_view),
        "findings": findings,
    }


# ============================================================
# G20. CLICKBAIT PENALTY CHECK
# ============================================================

def clickbait_penalty_check(
    videos: List[Dict[str, Any]],
    niche_data: Dict[str, Any],
    top_n: int = 15,
) -> Dict[str, Any]:
    """Check title có dùng từ clickbait penalty list (niche-specific)."""
    nd_title = niche_data.get("title", {}) or {}
    forbidden = [w.upper() for w in nd_title.get("clickbait_avoid", [])]
    if not forbidden:
        return {}

    violations = []
    for v in videos[:top_n]:
        title = (v.get("title") or "").upper()
        hits = [w for w in forbidden if w in title]
        if hits:
            violations.append({
                "video_id": v.get("video_id", ""),
                "title": v.get("title", "")[:70],
                "violating_words": hits,
                "views": int(v.get("view_count") or v.get("views") or 0),
            })

    return {
        "forbidden_words": forbidden,
        "videos_checked": len(videos[:top_n]),
        "violations_count": len(violations),
        "violations": violations,
    }


# ============================================================
# MAIN ENTRY — gọi từ html_report.py
# ============================================================

def build_synthesis(
    inside: Dict[str, Any],
    health_audits: List[Dict[str, Any]],
    health_channel: Dict[str, Any],
    health_keywords: Dict[str, Any],
    niche: str = "general",
    self_data: Dict[str, Any] = None,
    competitors: List[Dict[str, Any]] = None,
    self_videos: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Entry point — gọi cả 20 gap (G1-G20), return full synthesis dict.

    self_data: dict kênh chính (từ data["self"] trong html_report)
    competitors: list kênh đối thủ (từ data["competitors"])
    self_videos: list video kênh chính dạng dict (title, description,
                  tags, view_count, like_count, comment_count,
                  published_at, video_id)
    """
    if not inside or not inside.get("channel_summary"):
        return {}

    # Lazy import niche library
    from .niche_seo_library import get_niche_seo
    niche_data = get_niche_seo(niche)

    cs = inside.get("channel_summary", {}) or {}
    af = inside.get("audience_full", {}) or {}
    account_tag = inside.get("account_tag", "")
    sv = self_videos or []
    competitors = competitors or []

    out: Dict[str, Any] = {"niche_key": niche, "niche_name": niche_data.get("name", "")}

    # G1
    out["findings"] = cross_reference_findings(
        inside, health_audits or [], health_channel or {},
        health_keywords or {})

    # G2
    out["top_anatomy"] = anatomize_top_thumbnails(
        inside.get("thumbnail_ctr_top", []) or [])

    # G3
    out["worst_vs_top"] = compare_worst_vs_top(
        inside.get("thumbnail_ctr_top", []) or [],
        inside.get("thumbnail_ctr_worst", []) or [])

    # G4
    out["traffic_playbook"] = traffic_source_playbook(
        cs.get("traffic_sources_recent", []) or [], cs)

    # G5
    out["drop_diag"] = drop_points_vs_title(
        inside.get("retention_top", []) or [])

    # G6
    out["keyword_cluster"] = audience_keyword_cluster(af, niche)

    # G7
    if account_tag:
        try:
            out["period_delta"] = inside_period_delta(
                account_tag, days_now=7, days_prev=7, offset=7)
        except Exception:
            out["period_delta"] = {}
    else:
        out["period_delta"] = {}

    # G8 — DESCRIPTION audit
    try:
        out["desc_audit"] = audit_description(sv, niche_data)
    except Exception:
        out["desc_audit"] = {}

    # G9 — TAGS audit
    try:
        out["tags_audit"] = audit_tags(sv, niche_data)
    except Exception:
        out["tags_audit"] = {}

    # G10 — Upload timing
    try:
        out["upload_timing"] = optimal_upload_timing(
            account_tag, sv, niche_data)
    except Exception:
        out["upload_timing"] = {}

    # G11 — Engagement signals
    try:
        out["engagement"] = engagement_signals(sv, niche_data)
    except Exception:
        out["engagement"] = {}

    # G12 — Caption strategy
    try:
        out["caption"] = caption_audit(af, niche_data)
    except Exception:
        out["caption"] = {}

    # G13 — Content strategy gap
    try:
        out["content_gap"] = content_strategy_gap(sv, niche_data)
    except Exception:
        out["content_gap"] = {}

    # G14 — Title position + formula
    try:
        out["title_audit"] = title_position_formula_audit(sv, niche_data)
    except Exception:
        out["title_audit"] = {}

    # G15 — Thumbnail layout
    try:
        out["thumbnail_layout"] = thumbnail_layout_audit(niche_data, cs)
    except Exception:
        out["thumbnail_layout"] = {}

    # G16 — Retention techniques map
    try:
        out["retention_map"] = retention_techniques_map(
            inside.get("retention_top", []) or [], niche_data)
    except Exception:
        out["retention_map"] = {}

    # G17 — CTR sweet spot
    try:
        out["ctr_sweet"] = ctr_sweet_spot_decay(
            cs, inside.get("thumbnail_ctr_top", []) or [], niche_data)
    except Exception:
        out["ctr_sweet"] = {}

    # G18 — Channel SEO × Inside
    try:
        out["channel_x_inside"] = channel_seo_x_inside(
            health_channel or {}, cs, health_keywords or {})
    except Exception:
        out["channel_x_inside"] = {}

    # G19 — Competitor cross
    try:
        out["competitor_cross"] = competitor_inside_cross(
            self_data or {}, competitors, cs)
    except Exception:
        out["competitor_cross"] = {}

    # G20 — Clickbait penalty
    try:
        out["clickbait_check"] = clickbait_penalty_check(sv, niche_data)
    except Exception:
        out["clickbait_check"] = {}

    return out
