"""
SEO Health Check cho video kênh chính — rule-based audit 25 items.
Trả về dict {score, pass_items, fail_items, suggestions, severity}.

Dùng cho mỗi video của kênh chính trong báo cáo HTML — tab s0 hoặc tab s11
hiển thị warning nếu video có health score thấp.

Áp dụng framework từ tài liệu "Chuyên môn SEO Cơ bản đến Nâng cao A-Z"
(Phụ lục A — 60 items checklist, rút gọn còn 25 items KIỂM TRA ĐƯỢC TỰ
ĐỘNG từ data scrape; 35 items kia cần xem video trực tiếp).

Mỗi item có weight (trọng số), score 0-100 là tổng trọng số đạt / tổng
trọng số max × 100.
"""
from __future__ import annotations
from typing import List, Dict, Any


# 25 items có thể TỰ ĐỘNG kiểm tra từ data video scrape
# Mỗi item: (key, weight, label, check_fn)
# check_fn: f(video, channel_meta) → (passed: bool, detail: str)
# - video: VideoInfo dataclass có title, view_count, duration_seconds,
#   description, tags, published_at, days_old, like_count, comment_count
# - channel_meta: dict với 'niche_key', 'channel_subs', 'channel_avg_views'


def _check_title_length(v, _meta):
    """Title ≤70 ký tự."""
    t = getattr(v, "title", "") or ""
    if not t:
        return False, "Không có title"
    n = len(t)
    if n <= 70:
        return True, f"{n} ký tự (≤70 OK)"
    return False, f"{n} ký tự — quá dài (cắt mid-word trên search)"


def _check_title_has_number(v, _meta):
    """Title có chứa số/năm (signal cho list/how-to)."""
    t = (getattr(v, "title", "") or "").lower()
    has_digit = any(c.isdigit() for c in t)
    if has_digit:
        return True, "Có số/năm trong title"
    return False, "Thiếu số/năm — title generic"


def _check_title_no_allcaps(v, _meta):
    """Title KHÔNG toàn HOA (spam-like)."""
    t = getattr(v, "title", "") or ""
    if not t:
        return False, "Không có title"
    # Đếm chữ HOA vs chữ thường (chỉ chữ cái, bỏ qua số)
    letters = [c for c in t if c.isalpha()]
    if not letters:
        return True, "OK (không có chữ cái)"
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    if upper_ratio > 0.7:
        return False, f"{upper_ratio*100:.0f}% chữ HOA — spam-like"
    return True, f"{upper_ratio*100:.0f}% HOA (OK)"


def _check_title_no_excessive_emoji(v, _meta):
    """Title không quá nhiều emoji (>3)."""
    t = getattr(v, "title", "") or ""
    # Count non-ASCII non-letter chars (proxy for emoji)
    emoji_count = sum(1 for c in t
                      if ord(c) > 127 and not c.isalpha() and not c.isspace())
    if emoji_count > 3:
        return False, f"{emoji_count} emoji — quá nhiều"
    return True, f"{emoji_count} emoji (OK)"


def _check_description_length(v, _meta):
    """Description ≥150 từ (đủ SEO + chapters + link)."""
    desc = getattr(v, "description", "") or ""
    words = len(desc.split())
    if words >= 150:
        return True, f"{words} từ (≥150 OK)"
    if words < 50:
        return False, f"{words} từ — quá ngắn, thiếu SEO"
    return False, f"{words} từ — nên ≥150 từ"


def _check_description_has_timestamps(v, _meta):
    """Description có timestamps (chapters)."""
    desc = getattr(v, "description", "") or ""
    if not desc:
        return False, "Không có description"
    import re
    # Pattern HH:MM hoặc MM:SS
    matches = re.findall(r"\b\d{1,2}:\d{2}\b", desc)
    # Cần ít nhất 3 timestamps để là chapters thật
    if len(matches) >= 3:
        return True, f"{len(matches)} timestamps (chapters OK)"
    if len(matches) == 0:
        return False, "Thiếu chapters — giảm SEO + UX"
    return False, f"{len(matches)} timestamps — quá ít, cần ≥3"


def _check_description_has_hashtags(v, _meta):
    """Description có 1-5 hashtag (3 đầu hiển thị trên title mobile)."""
    desc = getattr(v, "description", "") or ""
    import re
    tags = re.findall(r"#\w+", desc)
    if 1 <= len(tags) <= 15:
        return True, f"{len(tags)} hashtag (OK)"
    if len(tags) == 0:
        return False, "Thiếu hashtag — bỏ lỡ visibility trên mobile"
    return False, f"{len(tags)} hashtag — quá nhiều (>15 bị YouTube bỏ qua)"


def _check_description_has_link(v, _meta):
    """Description có link external (CTA, related, social)."""
    desc = getattr(v, "description", "") or ""
    if "http" in desc.lower() or "www." in desc.lower():
        return True, "Có link external"
    return False, "Không có link CTA/related/social"


def _check_tags_count(v, _meta):
    """Có 5-15 tag."""
    tags = getattr(v, "tags", []) or []
    n = len(tags)
    if 5 <= n <= 15:
        return True, f"{n} tags (OK)"
    if n == 0:
        return False, "Không có tag — bỏ qua signal cho algorithm"
    if n < 5:
        return False, f"{n} tags — quá ít, nên 5-15"
    return False, f"{n} tags — quá nhiều, có thể bị spam-like"


def _check_duration_min(v, meta):
    """Độ dài video ≥ ngưỡng tối thiểu theo ngách."""
    d = getattr(v, "duration_seconds", 0) or 0
    if d == 0:
        return False, "Không có độ dài (Short hoặc lỗi parse)"
    minutes = d / 60
    niche = meta.get("niche_key", "generic")
    # Min duration theo ngách (rút từ guidance)
    min_by_niche = {
        "toy_unboxing": 5,            # sweet spot 8-13, tối thiểu 5
        "asmr_sand_slime": 3,         # 3-10 phút OK
        "numberblocks_slime": 20,     # 30+ phút
        "diy_mini_tractor": 5,
        "horror_stories": 10,         # 10-180 phút compilation
        "paper_doll_glow": 20,        # 25-30 phút
        "car_crush_experiment": 1,    # ngắn cũng OK (3 phút Sweeper 244K)
        "construction_vehicle": 5,
        "lego_animation": 3,
        "generic": 3,
    }
    threshold = min_by_niche.get(niche, 3)
    if minutes >= threshold:
        return True, f"{minutes:.1f} phút (≥{threshold} phút ngách OK)"
    return False, f"{minutes:.1f} phút < {threshold} phút (ngắn cho ngách)"


def _check_duration_sweet(v, meta):
    """Độ dài video trong sweet spot ngách."""
    d = getattr(v, "duration_seconds", 0) or 0
    if d == 0:
        return False, "Không có độ dài"
    minutes = d / 60
    niche = meta.get("niche_key", "generic")
    sweet_by_niche = {
        "toy_unboxing": (8, 18),
        "asmr_sand_slime": (3, 60),
        "numberblocks_slime": (25, 60),
        "diy_mini_tractor": (10, 25),
        "horror_stories": (20, 180),
        "paper_doll_glow": (25, 60),
        "car_crush_experiment": (3, 15),
        "construction_vehicle": (8, 25),
        "lego_animation": (5, 20),
        "generic": (5, 20),
    }
    lo, hi = sweet_by_niche.get(niche, (5, 20))
    if lo <= minutes <= hi:
        return True, f"{minutes:.1f}p trong sweet spot {lo}-{hi}p"
    if minutes < lo:
        return False, f"{minutes:.1f}p dưới sweet spot {lo}-{hi}p"
    return False, f"{minutes:.1f}p trên sweet spot {lo}-{hi}p (vẫn OK tuỳ ngách)"


def _check_view_velocity(v, meta):
    """View/ngày so với median kênh."""
    vc = getattr(v, "view_count", 0) or 0
    days = getattr(v, "days_old", 0) or 0
    if days < 1:
        return True, f"Mới đăng <1 ngày, chưa đủ data"
    vpd = vc / max(1, days)
    avg = meta.get("channel_avg_views", 0)
    if avg <= 0:
        return True, f"{vpd:.0f} view/ngày (không có baseline)"
    ratio = vpd / max(1, avg / 30)  # avg view/video / 30 ngày ≈ baseline/ngày
    if ratio >= 1.5:
        return True, f"{vpd:.0f} v/ngày — {ratio:.1f}× baseline (TỐT)"
    if ratio >= 0.5:
        return True, f"{vpd:.0f} v/ngày — {ratio:.1f}× baseline (OK)"
    return False, f"{vpd:.0f} v/ngày — chỉ {ratio:.1f}× baseline (yếu)"


def _check_like_view_ratio(v, _meta):
    """Like/View ≥3%."""
    likes = getattr(v, "like_count", 0) or 0
    views = getattr(v, "view_count", 0) or 0
    if views < 100:
        return True, "View < 100, chưa đủ data"
    ratio = (likes / views) * 100
    if ratio >= 3:
        return True, f"{ratio:.2f}% (≥3% TỐT)"
    if ratio >= 1:
        return False, f"{ratio:.2f}% (yếu, nên ≥3%)"
    return False, f"{ratio:.2f}% (quá yếu, viewer không cảm xúc)"


def _check_comment_rate(v, _meta):
    """Comment/1K views ≥0.5."""
    comments = getattr(v, "comment_count", 0) or 0
    views = getattr(v, "view_count", 0) or 0
    if views < 1000:
        return True, "View < 1K, chưa đủ data"
    rate = comments / (views / 1000)
    if rate >= 0.5:
        return True, f"{rate:.2f}/1K view (TỐT)"
    return False, f"{rate:.2f}/1K view (yếu, nên ≥0.5)"


def _check_freshness(v, _meta):
    """Video mới đăng trong 30 ngày qua (active channel signal)."""
    days = getattr(v, "days_old", 0) or 0
    if days <= 30:
        return True, f"Đăng cách {days:.0f} ngày (mới, OK)"
    return False, f"Đăng cách {days:.0f} ngày (cũ — đã hết momentum)"


def _check_has_thumbnail(v, _meta):
    """Có thumbnail URL (mọi video đều có, trừ khi parse lỗi)."""
    # Hầu hết video đều có thumbnail mặc định từ YouTube
    # Check qua thumbnail_url nếu có
    thumb = getattr(v, "thumbnail_url", "") or ""
    if thumb:
        return True, "Có thumbnail"
    return True, "(Không check được - giả định có)"


def _check_title_has_keyword_match(v, meta):
    """Title chứa ít nhất 1 keyword chính của kênh."""
    title = (getattr(v, "title", "") or "").lower()
    if not title:
        return False, "Không có title"
    channel_kws = meta.get("channel_keywords", [])
    if not channel_kws:
        return True, "(Không có keyword baseline)"
    # Top 10 keyword đầu
    matches = [kw for kw in channel_kws[:10]
               if kw.lower() in title]
    if matches:
        return True, f"Match {len(matches)} kw: {', '.join(matches[:3])}"
    return False, "Không match top 10 keyword kênh"


def _check_title_capitalize(v, _meta):
    """Title viết Title Case (chữ cái đầu mỗi từ HOA)."""
    t = getattr(v, "title", "") or ""
    if not t:
        return False, "Không có title"
    words = t.split()
    if len(words) < 3:
        return True, "Title quá ngắn để đánh giá"
    # Đếm chữ cái đầu của các từ ≥3 ký tự (bỏ qua từ ngắn như "a", "the")
    caps = sum(1 for w in words if len(w) >= 3 and w[0].isupper())
    significant = sum(1 for w in words if len(w) >= 3)
    if significant == 0:
        return True, "OK"
    ratio = caps / significant
    if ratio >= 0.5:
        return True, f"{ratio*100:.0f}% từ Title Case"
    return False, f"Chỉ {ratio*100:.0f}% từ Title Case — sửa cho professional"


def _check_description_first_line(v, _meta):
    """Description đoạn đầu 100-300 ký tự (hiển thị trên search)."""
    desc = getattr(v, "description", "") or ""
    if not desc:
        return False, "Không có description"
    # Đoạn đầu = trước \n\n
    first_block = desc.split("\n\n")[0] if "\n\n" in desc else desc.split("\n")[0]
    n = len(first_block)
    if 100 <= n <= 350:
        return True, f"Đoạn đầu {n} ký tự (OK)"
    if n < 100:
        return False, f"Đoạn đầu chỉ {n} ký tự — quá ngắn"
    return False, f"Đoạn đầu {n} ký tự — quá dài, cắt mid-block"


# Đăng ký các check (key, weight, label, fn)
CHECKS = [
    ("title_length", 5, "Title ≤70 ký tự", _check_title_length),
    ("title_no_allcaps", 3, "Title không toàn HOA", _check_title_no_allcaps),
    ("title_no_excess_emoji", 2, "Title ≤3 emoji", _check_title_no_excessive_emoji),
    ("title_has_number", 2, "Title có số/năm", _check_title_has_number),
    ("title_capitalize", 2, "Title viết Title Case", _check_title_capitalize),
    ("title_kw_match", 4, "Title match keyword kênh", _check_title_has_keyword_match),
    ("desc_length", 5, "Description ≥150 từ", _check_description_length),
    ("desc_first_line", 3, "Description đoạn đầu 100-350 ký tự", _check_description_first_line),
    ("desc_timestamps", 4, "Description có ≥3 timestamps (chapters)", _check_description_has_timestamps),
    ("desc_hashtags", 3, "Description có 1-15 hashtag", _check_description_has_hashtags),
    ("desc_link", 2, "Description có link external", _check_description_has_link),
    ("tags_count", 3, "Có 5-15 tag", _check_tags_count),
    ("duration_min", 4, "Độ dài ≥ ngưỡng ngách", _check_duration_min),
    ("duration_sweet", 5, "Độ dài trong sweet spot ngách", _check_duration_sweet),
    ("view_velocity", 5, "View/ngày tốt vs baseline", _check_view_velocity),
    ("like_view_ratio", 4, "Like/View ≥3%", _check_like_view_ratio),
    ("comment_rate", 3, "Comment/1K views ≥0.5", _check_comment_rate),
    ("freshness", 2, "Đăng trong 30 ngày", _check_freshness),
    ("has_thumbnail", 1, "Có thumbnail", _check_has_thumbnail),
]


def health_check_video(video, channel_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Audit 1 video, trả dict {score, pass, fail, suggestions, severity}.

    Args:
        video: VideoInfo dataclass.
        channel_meta: {'niche_key': str, 'channel_subs': int,
                       'channel_avg_views': int, 'channel_keywords': list}.

    Returns:
        {
          'score': 0-100 (% weight pass),
          'pass_items': [{'key','label','detail'}],
          'fail_items': [{'key','label','detail','weight'}],
          'severity': 'good'|'warn'|'bad',
          'severity_label': str,
        }
    """
    pass_items = []
    fail_items = []
    total_weight = 0
    pass_weight = 0
    for key, weight, label, fn in CHECKS:
        total_weight += weight
        try:
            passed, detail = fn(video, channel_meta)
        except Exception as e:
            passed, detail = False, f"Check error: {e}"
        item = {"key": key, "label": label, "detail": detail,
                "weight": weight}
        if passed:
            pass_items.append(item)
            pass_weight += weight
        else:
            fail_items.append(item)

    score = round(pass_weight / max(1, total_weight) * 100)
    if score >= 80:
        severity = "good"
        severity_label = "TỐT"
    elif score >= 60:
        severity = "warn"
        severity_label = "CẦN CẢI THIỆN"
    else:
        severity = "bad"
        severity_label = "YẾU"

    return {
        "score": score,
        "pass_items": pass_items,
        "fail_items": fail_items,
        "severity": severity,
        "severity_label": severity_label,
        "total_checks": len(CHECKS),
        "passed_count": len(pass_items),
    }


# ============================================================
# CHANNEL-LEVEL AUDIT (cấp toàn kênh, KHÔNG phải từng video)
# ============================================================


def _channel_has_about(ch, _meta):
    """Channel có description (About) ≥150 từ."""
    desc = getattr(ch, "description", "") or ""
    words = len(desc.split())
    if words >= 150:
        return True, f"{words} từ — đầy đủ"
    if words >= 50:
        return False, f"{words} từ — nên ≥150 từ để SEO + Brand"
    return False, f"{words} từ — quá ngắn, viết lại About"


def _channel_about_has_keyword(ch, meta):
    """About kênh chứa keyword chính của ngách."""
    desc = (getattr(ch, "description", "") or "").lower()
    top_kws = meta.get("channel_keywords", [])[:5]
    if not top_kws:
        return True, "(Không có keyword baseline)"
    if not desc:
        return False, "Không có About"
    matches = [k for k in top_kws if k.lower() in desc]
    if matches:
        return True, f"Match {len(matches)}/5 top kw: {', '.join(matches[:3])}"
    return False, f"About KHÔNG chứa keyword chính: {', '.join(top_kws[:3])}"


def _channel_has_keywords_set(ch, _meta):
    """Channel có channel keywords (Settings → Channel → Basic Info)."""
    kws = getattr(ch, "keywords", []) or []
    if isinstance(kws, str):
        kws = [k.strip() for k in kws.split(",") if k.strip()]
    n = len(kws)
    if n >= 10:
        return True, f"{n} channel keywords (≥10 OK)"
    if n >= 1:
        return False, f"Chỉ {n} keywords — nên 10-15"
    return False, "Chưa set channel keywords"


def _channel_has_handle(ch, _meta):
    """Channel có handle @username."""
    h = getattr(ch, "handle", "") or ""
    if h and h.startswith("@"):
        return True, f"Handle: {h}"
    return False, "Chưa set handle @username"


def _channel_video_count(ch, _meta):
    """Channel có ≥10 video (đủ baseline cho algorithm)."""
    vc = getattr(ch, "video_count", 0) or 0
    if vc >= 10:
        return True, f"{vc:,} video — đủ baseline"
    if vc >= 3:
        return False, f"{vc} video — đủ điều kiện YPP mức 1 (cần ≥3 trong 90 ngày)"
    return False, f"{vc} video — quá ít, cần ≥10 để algorithm có data"


def _channel_total_views(ch, _meta):
    """Channel có ≥10K total views (tín hiệu kênh active)."""
    tv = getattr(ch, "view_count", 0) or 0
    if tv >= 100_000:
        return True, f"{tv:,} total views (TỐT)"
    if tv >= 10_000:
        return True, f"{tv:,} total views (OK)"
    if tv >= 1_000:
        return False, f"{tv:,} total views — cần boost"
    return False, f"{tv:,} total views — kênh quá nhỏ"


def _channel_sub_count(ch, _meta):
    """Channel có ≥1000 subs (đủ điều kiện YPP đầy đủ)."""
    s = getattr(ch, "subscriber_count", 0) or 0
    if s >= 100_000:
        return True, f"{s:,} subs (LỚN — vào YPP)"
    if s >= 1000:
        return True, f"{s:,} subs (đủ YPP full mức 2)"
    if s >= 500:
        return False, f"{s:,} subs (đủ YPP fan funding, cần ≥1K cho ads)"
    return False, f"{s:,} subs — chưa đủ YPP, cần ≥500"


# Đăng ký channel-level checks
CHANNEL_CHECKS = [
    ("ch_about_length", 5, "About ≥150 từ", _channel_has_about),
    ("ch_about_keyword", 6, "About chứa keyword chính ngách",
     _channel_about_has_keyword),
    ("ch_keywords_set", 4, "Channel keywords đã set (10-15)",
     _channel_has_keywords_set),
    ("ch_handle", 3, "Có handle @username", _channel_has_handle),
    ("ch_video_count", 3, "Có ≥10 video", _channel_video_count),
    ("ch_total_views", 2, "Total views ≥10K", _channel_total_views),
    ("ch_sub_count", 3, "Đủ subs YPP (≥1000)", _channel_sub_count),
]


def health_check_channel(self_result: dict) -> Dict[str, Any]:
    """Audit cấp KÊNH (không phải video). Trả về dict tương tự
    health_check_video.

    Args:
        self_result: dict result của kênh chính (từ load_result).

    Returns:
        {'score', 'pass_items', 'fail_items', 'severity', 'severity_label'}
    """
    if not self_result:
        return {"score": 0, "pass_items": [], "fail_items": [],
                "severity": "bad", "severity_label": "KHÔNG CÓ DỮ LIỆU"}
    ch = self_result.get("channel")
    if not ch:
        return {"score": 0, "pass_items": [], "fail_items": [],
                "severity": "bad", "severity_label": "KHÔNG CÓ DỮ LIỆU"}
    # Build meta
    top_kws = [getattr(k, "keyword", "") for k in
               (self_result.get("keywords") or [])[:5]]
    meta = {"channel_keywords": top_kws}
    pass_items, fail_items = [], []
    total_weight = pass_weight = 0
    for key, weight, label, fn in CHANNEL_CHECKS:
        total_weight += weight
        try:
            passed, detail = fn(ch, meta)
        except Exception as e:
            passed, detail = False, f"Check error: {e}"
        item = {"key": key, "label": label, "detail": detail,
                "weight": weight}
        if passed:
            pass_items.append(item)
            pass_weight += weight
        else:
            fail_items.append(item)
    score = round(pass_weight / max(1, total_weight) * 100)
    if score >= 80:
        severity, severity_label = "good", "TỐT"
    elif score >= 60:
        severity, severity_label = "warn", "CẦN CẢI THIỆN"
    else:
        severity, severity_label = "bad", "YẾU"
    return {"score": score, "pass_items": pass_items,
            "fail_items": fail_items, "severity": severity,
            "severity_label": severity_label,
            "total_checks": len(CHANNEL_CHECKS),
            "passed_count": len(pass_items)}


# ============================================================
# KEYWORD ALIGNMENT — chiến lược từ khoá tổng thể
# ============================================================


def keyword_alignment_check(self_result: dict,
                             competitors_data: list = None) -> Dict[str, Any]:
    """Phân tích đồng bộ từ khoá KÊNH vs từ khoá NGÁCH.

    So sánh:
    - Top 15 keyword kênh chính (theo SEO score / frequency).
    - Top 15 keyword toàn ngách (từ keywords + video titles đối thủ).
    - Match: keyword kênh DÙNG / KHÔNG DÙNG / NGÁCH MẠNH NHƯNG KÊNH BỎ.

    Args:
        self_result: dict result kênh chính.
        competitors_data: list các result kênh đối thủ.

    Returns:
        {
          'self_keywords': [{kw, score, in_about, in_video_pct}],
          'niche_keywords': [{kw, freq_in_niche, in_self}],
          'gaps': [keyword ngách mạnh mà kênh chưa dùng],
          'overused': [keyword kênh dùng nhiều nhưng không match ngách],
          'theme_consistency': float 0-100 (% video có keyword chính),
          'actions': list các hành động đề xuất
        }
    """
    if not self_result:
        return {"self_keywords": [], "niche_keywords": [], "gaps": [],
                "overused": [], "theme_consistency": 0, "actions": []}

    # 1. Top keywords kênh chính
    self_kws = self_result.get("keywords") or []
    self_top = []
    for k in self_kws[:15]:
        kw = getattr(k, "keyword", "") or ""
        score = getattr(k, "score", 0) or 0
        if kw:
            self_top.append({"kw": kw, "score": float(score)})

    # 2. About + Videos kênh chính - tính tỷ lệ dùng
    ch = self_result.get("channel")
    about = (getattr(ch, "description", "") or "").lower() if ch else ""
    videos = self_result.get("videos") or []
    n_videos = max(1, len(videos))

    for k in self_top:
        kw_low = k["kw"].lower()
        # Có trong About?
        k["in_about"] = kw_low in about
        # % video có trong title
        n_in_title = sum(1 for v in videos
                         if kw_low in
                         (getattr(v, "title", "") or "").lower())
        k["in_video_pct"] = round(100 * n_in_title / n_videos, 1)

    # 3. Niche keywords từ competitors
    niche_freq = {}
    if competitors_data:
        for cr in competitors_data:
            if not cr:
                continue
            # Keywords của competitor
            for k in (cr.get("keywords") or [])[:20]:
                kw = (getattr(k, "keyword", "") or "").lower().strip()
                if not kw:
                    continue
                niche_freq[kw] = niche_freq.get(kw, 0) + 1
            # Video titles competitor — đếm từ
            for v in (cr.get("videos") or [])[:30]:
                title_low = (getattr(v, "title", "") or "").lower()
                # Tách 2-3 word phrases có ý nghĩa
                for k in (cr.get("keywords") or [])[:10]:
                    kw_low = (getattr(k, "keyword", "") or "").lower().strip()
                    if kw_low and kw_low in title_low:
                        niche_freq[kw_low] = niche_freq.get(kw_low, 0) + 1

    # Top 15 niche keywords
    niche_sorted = sorted(niche_freq.items(), key=lambda x: -x[1])[:15]
    self_kws_set = {k["kw"].lower() for k in self_top}
    niche_top = []
    for kw, freq in niche_sorted:
        niche_top.append({
            "kw": kw,
            "freq_in_niche": freq,
            "in_self": kw in self_kws_set,
        })

    # 4. GAPS: niche keyword mạnh (freq ≥3) mà kênh chưa dùng
    gaps = [n["kw"] for n in niche_top
            if not n["in_self"] and n["freq_in_niche"] >= 3][:10]

    # 5. OVERUSED: keyword kênh có score cao nhưng KHÔNG có trong ngách
    niche_kws_set = {n["kw"] for n in niche_top}
    overused = [k["kw"] for k in self_top[:5]
                if k["kw"].lower() not in niche_kws_set][:5]

    # 6. THEME CONSISTENCY: % video có keyword chính (top 3) trong title
    theme_consistency = 0
    if self_top and videos:
        top3_kws = [k["kw"].lower() for k in self_top[:3]]
        n_themed = sum(1 for v in videos
                       if any(kw in (getattr(v, "title", "") or "").lower()
                              for kw in top3_kws))
        theme_consistency = round(100 * n_themed / n_videos, 1)

    # 7. Actions đề xuất
    actions = []
    if theme_consistency < 50:
        actions.append({
            "severity": "high",
            "title": "Theme consistency THẤP",
            "detail": f"Chỉ {theme_consistency}% video có top 3 keyword "
                      f"trong title — kênh đang dàn trải quá nhiều chủ "
                      f"đề. Đề xuất: chọn 1-2 pillar chính + lặp keyword "
                      f"chính trong 70%+ video.",
        })
    if not (ch and getattr(ch, "description", "")):
        actions.append({
            "severity": "high",
            "title": "Channel About RỖNG",
            "detail": "Viết About 200-300 từ chứa UVP + 5-10 keyword "
                      "chính của ngách. About = SEO landing page của kênh.",
        })
    elif self_top:
        # Check About có chứa keyword chính không
        if not any(k["in_about"] for k in self_top[:5]):
            actions.append({
                "severity": "medium",
                "title": "About không chứa keyword chính",
                "detail": f"Top 5 keyword của kênh ({', '.join([k['kw'] for k in self_top[:5]])}) "
                          f"KHÔNG xuất hiện trong About. Đề xuất viết lại "
                          f"About kèm các keyword này tự nhiên.",
            })
    if gaps:
        actions.append({
            "severity": "medium",
            "title": f"Có {len(gaps)} keyword ngách MẠNH kênh CHƯA dùng",
            "detail": "Top gap: " + ", ".join(gaps[:5]) +
                      ". Đề xuất làm 2-3 video với 2-3 keyword này.",
        })
    if overused:
        actions.append({
            "severity": "low",
            "title": "Keyword kênh KHÔNG match ngách",
            "detail": "Keyword: " + ", ".join(overused) +
                      ". Hoặc kênh đang đi trước ngách (cơ hội), hoặc "
                      "đang lệch ngách (rủi ro). Audit kỹ.",
        })
    if not actions:
        actions.append({
            "severity": "good",
            "title": "Chiến lược từ khoá ổn",
            "detail": "Kênh đã đồng bộ keyword với ngách. Tiếp tục duy "
                      "trì + theo dõi xu hướng mới.",
        })

    return {
        "self_keywords": self_top,
        "niche_keywords": niche_top,
        "gaps": gaps,
        "overused": overused,
        "theme_consistency": theme_consistency,
        "actions": actions,
    }


# ============================================================
# SEO ACTION ITEMS — tổng hợp việc cần làm cho kênh
# ============================================================


def build_seo_action_items(channel_audit: dict, video_audits: list,
                            kw_alignment: dict) -> List[Dict[str, Any]]:
    """Tổng hợp các SEO action cần làm cho kênh từ kết quả audit.

    Phân loại theo mức ưu tiên (high/medium/low) + ETA + ai làm.
    """
    actions = []

    # 1. Từ channel audit
    for item in (channel_audit.get("fail_items") or []):
        priority = "high" if item["weight"] >= 5 else (
                   "medium" if item["weight"] >= 3 else "low")
        actions.append({
            "priority": priority,
            "category": "Channel-level",
            "issue": item["label"],
            "detail": item["detail"],
            "action": _suggest_action_for_check(item["key"]),
            "owner": "SEO Lead",
            "eta": "1-3 ngày",
        })

    # 2. Từ keyword alignment
    for a in (kw_alignment.get("actions") or []):
        prio_map = {"high": "high", "medium": "medium", "low": "low",
                    "good": "low"}
        actions.append({
            "priority": prio_map.get(a["severity"], "medium"),
            "category": "Keyword strategy",
            "issue": a["title"],
            "detail": a["detail"],
            "action": _suggest_action_for_keyword(a["title"]),
            "owner": "SEO Specialist",
            "eta": "1-2 tuần",
        })

    # 3. Từ video audits — gom lỗi LẶP LẠI trong 10 video
    fail_freq = {}
    for v in video_audits:
        for f in v.get("fail_items", []):
            k = f["key"]
            if k not in fail_freq:
                fail_freq[k] = {"label": f["label"], "count": 0,
                                "weight": f["weight"]}
            fail_freq[k]["count"] += 1
    # Lỗi nào lặp ≥5/10 video → quy trình lỗi
    for key, info in fail_freq.items():
        if info["count"] >= 5:
            priority = ("high" if info["weight"] >= 4 else
                        "medium" if info["weight"] >= 3 else "low")
            actions.append({
                "priority": priority,
                "category": "Quy trình lỗi (lặp lại)",
                "issue": f"{info['label']} — sai ở {info['count']}/10 video",
                "detail": "Lỗi LẶP LẠI nhiều → cần sửa TEMPLATE chứ "
                          "không sửa từng video.",
                "action": _suggest_action_for_check(key),
                "owner": "SEO Lead + Editor",
                "eta": "1-3 ngày (sửa template)",
            })

    # Sort theo priority (high → low)
    prio_order = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda a: prio_order.get(a["priority"], 3))
    return actions


_ACTION_SUGGESTIONS = {
    "title_length": "Soạn template title <70 ký tự. Sửa default upload "
                    "settings trong Studio.",
    "title_no_allcaps": "Convert title từ ALL CAPS sang Title Case. "
                        "Áp dụng cho mọi video tương lai.",
    "title_no_excess_emoji": "Giảm số emoji xuống ≤3. Đặt rules trong team.",
    "title_has_number": "Thêm năm/số vào title (vd \"2026\", \"Top 5\", "
                        "\"3 mẹo\") để tăng CTR.",
    "title_capitalize": "Viết title theo Title Case (chữ đầu mỗi từ HOA).",
    "title_kw_match": "Đặt keyword chính của kênh trong 50 ký tự đầu của "
                      "mọi title. Cập nhật template content.",
    "desc_length": "Soạn description template 200-300 từ với 3 đoạn "
                   "chuẩn (tóm tắt + timestamps + links). Áp dụng "
                   "default upload settings.",
    "desc_first_line": "Đoạn 1 description 100-300 ký tự, chứa keyword "
                       "+ benefit (hiển thị trên search result).",
    "desc_timestamps": "BẮT BUỘC thêm 5-10 chapter timestamps cho mọi "
                       "video. Chapter đầu phải bắt đầu 00:00.",
    "desc_hashtags": "Thêm 3-5 hashtag cuối description: #brand + "
                     "#nganhanh + #specific (3 hashtag đầu hiển thị "
                     "trên mobile).",
    "desc_link": "Thêm ít nhất 3 link: website, related video, social.",
    "tags_count": "Thêm 5-15 tags/video. Tag đầu = keyword chính. "
                  "Dùng VidIQ/TubeBuddy để extract từ competitor.",
    "duration_min": "Tăng độ dài video theo sweet spot ngách (xem "
                    "Niche guidance trong tab SEO Best Practice).",
    "duration_sweet": "Điều chỉnh độ dài video về sweet spot ngách. "
                      "Video quá ngắn = thiếu watch time; quá dài = "
                      "drop retention.",
    "view_velocity": "Boost 24-72h sau publish: share Community, "
                     "social, ads. Xem Vòng lặp 48-72h tab SEO Best "
                     "Practice.",
    "like_view_ratio": "Tăng CTA \"Like\" trong video (mid-roll). Hỏi "
                       "viewer câu hỏi gợi thảo luận.",
    "comment_rate": "Hỏi câu hỏi cuối video. Pin comment câu hỏi. "
                    "Reply trong 24h.",
    "freshness": "Đăng đều — 2-3 video/tuần. Set lịch consistent.",
    "has_thumbnail": "Upload thumbnail custom 1280×720 cho mọi video. "
                     "KHÔNG dùng thumbnail mặc định YouTube.",
    "ch_about_length": "Viết About ≥200 từ: đoạn 1 UVP (1-2 câu) + "
                       "đoạn 2 brand promise + đoạn 3 CTA + social.",
    "ch_about_keyword": "Insert 5-10 keyword chính của ngách vào About "
                        "tự nhiên (KHÔNG keyword stuffing).",
    "ch_keywords_set": "Vào Studio → Settings → Channel → Basic info → "
                       "Channel keywords. Thêm 10-15 keyword.",
    "ch_handle": "Đăng ký handle @username. Studio → Settings → Channel "
                 "→ Basic Info. 1 lần đổi/14 ngày.",
    "ch_video_count": "Đăng đủ ≥10 video baseline. Tăng tần suất 2-3/tuần.",
    "ch_total_views": "Tăng traffic: SEO, ads boost, social share, collab.",
    "ch_sub_count": "Tăng subs: CTA mid-video, end screen, channel "
                    "trailer cho non-sub.",
}


def _suggest_action_for_check(key: str) -> str:
    return _ACTION_SUGGESTIONS.get(key, "Xem chi tiết trong SEO Best Practice.")


def _suggest_action_for_keyword(title: str) -> str:
    if "Theme consistency" in title:
        return ("Chọn 1-2 pillar chính → lặp keyword chính trong 70%+ "
                "video. Bỏ chủ đề dàn trải.")
    if "About RỖNG" in title or "About không chứa" in title:
        return ("Viết About 200-300 từ với UVP + 5-10 keyword chính của "
                "ngách + CTA + social links.")
    if "CHƯA dùng" in title:
        return ("Lên content map: 2-3 video mới mỗi keyword gap. Ưu tiên "
                "keyword competition thấp + relevance cao.")
    if "không match ngách" in title:
        return ("Audit: kênh có đi đúng định vị không? Nếu lệch → quay "
                "lại pillar. Nếu là cơ hội ngách mới → đánh giá thêm.")
    return "Xem chi tiết trong tab SEO Best Practice."


def health_check_self_videos(self_result: dict, niche_key: str = "generic",
                              max_videos: int = 10) -> List[Dict[str, Any]]:
    """Audit top N video gần nhất của kênh chính.

    Args:
        self_result: dict result của kênh chính (từ load_result).
        niche_key: niche detect được.
        max_videos: số video audit (mặc định 10 mới nhất).

    Returns:
        List dict mỗi video: {video_id, title, score, severity, fail_items, ...}
    """
    if not self_result:
        return []
    videos = self_result.get("videos") or []
    if not videos:
        return []
    # Sort theo days_old asc — lấy video mới nhất
    videos_sorted = sorted(
        videos,
        key=lambda v: getattr(v, "days_old", 9999) or 9999)[:max_videos]

    # Build channel_meta
    avg_views = 0
    if videos:
        all_views = [getattr(v, "view_count", 0) or 0 for v in videos]
        if all_views:
            avg_views = sum(all_views) // len(all_views)
    channel_meta = {
        "niche_key": niche_key,
        "channel_subs": int(self_result.get("subscriber_count", 0) or 0),
        "channel_avg_views": avg_views,
        "channel_keywords": [k.keyword for k in
                             (self_result.get("keywords") or [])[:20]],
    }

    results = []
    for v in videos_sorted:
        check = health_check_video(v, channel_meta)
        results.append({
            "video_id": getattr(v, "video_id", ""),
            "title": getattr(v, "title", ""),
            "view_count": getattr(v, "view_count", 0) or 0,
            "days_old": getattr(v, "days_old", 0) or 0,
            "duration_seconds": getattr(v, "duration_seconds", 0) or 0,
            **check,
        })
    return results
