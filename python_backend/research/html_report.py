# -*- coding: utf-8 -*-
"""Bộ tạo báo cáo HTML tương tác đầy đủ cho 1 watchlist.

Module lõi — dùng chung cho app.py (phần mềm) và tools/ (script).
Hàm chính: build(watchlist_id, out_path="") -> đường dẫn file HTML.
"""
import base64
import json
import re
import statistics
from datetime import datetime
from pathlib import Path

_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿]")


def _title_features(title):
    """Các đặc điểm của 1 tiêu đề video."""
    t = title or ""
    return {
        "Có con số": bool(re.search(r"\d", t)),
        "Có dấu ngoặc [ ] ( )": bool(re.search(r"[\[\]()]", t)),
        "Có chữ VIẾT HOA (3+ ký tự)": bool(re.search(r"[A-Z]{3,}", t)),
        "Có emoji": bool(_EMOJI.search(t)),
        'Có "vs" (đối đầu)': bool(re.search(r"\bvs\b", t, re.I)),
        "Có dấu hỏi (?)": "?" in t,
        "Có dấu chấm than (!)": "!" in t,
        "Tiêu đề ngắn (<60 ký tự)": 0 < len(t) < 60,
    }


def _title_stats(videos):
    """So sánh view trung vị của video CÓ vs KHÔNG mỗi đặc điểm tiêu
    đề. Trả list dict {feat, n, med_with, med_without, lift}."""
    vids = [v for v in videos
            if v.get("views", 0) > 0 and v.get("title")]
    if len(vids) < 8:
        return []
    tagged = [(v["views"], _title_features(v["title"])) for v in vids]
    rows = []
    for k in _title_features(""):
        wv = [vw for vw, f in tagged if f[k]]
        ov = [vw for vw, f in tagged if not f[k]]
        if len(wv) < 3 or len(ov) < 3:
            continue
        mw = statistics.median(wv)
        mo = statistics.median(ov)
        rows.append({"feat": k, "n": len(wv),
                     "med_with": int(mw), "med_without": int(mo),
                     "lift": round(mw / mo, 2) if mo else 0})
    rows.sort(key=lambda r: r["lift"], reverse=True)
    return rows

_ROOT = Path(__file__).resolve().parent.parent


def vinfo(v):
    vid = getattr(v, "video_id", "") or ""
    url = getattr(v, "url", "") or (
        f"https://www.youtube.com/watch?v={vid}" if vid else "")
    views = int(getattr(v, "view_count", 0) or 0)
    likes = int(getattr(v, "like_count", 0) or 0)
    cmts = int(getattr(v, "comment_count", 0) or 0)
    # Tuổi video (ngày, 1 decimal) — như cột "Ngày" trong phần mềm
    pub = (getattr(v, "published_at", "") or "")[:10]
    age_days = 0.0
    if pub:
        try:
            from datetime import datetime
            d_pub = datetime.fromisoformat(pub)
            age_days = round((datetime.now() - d_pub).total_seconds()
                             / 86400, 1)
        except Exception:
            pass
    return {
        "title": getattr(v, "title", "") or "",
        "vid": vid, "url": url,
        "ch": getattr(v, "channel_title", "") or "",
        "date": pub,                 # "Đăng" (YYYY-MM-DD)
        "age_days": age_days,        # "Ngày" tuổi (1.1, 5.1, ...)
        "views": views,
        "vpd": int(getattr(v, "views_per_day", 0) or 0),
        "likes": likes,
        "cmts": cmts,
        "dur": int(getattr(v, "duration_seconds", 0) or 0),
        # Tỷ lệ tương tác (%) = (like+bình luận)/lượt xem. KHÔNG chặn
        # giá trị cao — tỷ lệ cao bất thường thường do nhân viên bơm
        # like/bình luận (thủ thuật SEO); đó là tín hiệu cần biết.
        "eng": round((likes + cmts) / views * 100, 2) if views else 0,
    }


def _pack(res, wc, inside_ci=None):
    """Trích toàn bộ dữ liệu phân tích 1 kênh.

    inside_ci (chốt 26/05): nếu là self_channel + có Inside data → ưu tiên
    Inside cho avg_daily_views (last_views/7) và avg_daily_subs (last_subs_net/7).
    SB cho self_channel KHÔNG fetch nữa, nên sbs sẽ rỗng → fallback Inside.
    """
    if not res:
        return {"title": (wc.title if wc else ""), "has": False,
                "auto_added": bool(getattr(wc, "auto_added", False))}
    ch = res.get("channel")
    vids = res.get("videos") or []
    seo = (res.get("tag_metrics") or {}).get("seo_summary") or {}
    sb = res.get("socialblade") or {}
    sbs = dict(sb.get("summary") or {})  # copy để mutate an toàn
    sbd = sb.get("daily_stats") or []
    sb_source = "socialblade"

    # === QUY TRÌNH MỚI 26/05: ưu tiên Inside cho self_channel ===
    if inside_ci and inside_ci.get("has_data"):
        last_views_7d = inside_ci.get("last_views", 0) or 0
        last_subs_net = inside_ci.get("last_subs_net", 0)
        last_subs_gained = inside_ci.get("last_subs_gained", 0)
        last_subs_lost = inside_ci.get("last_subs_lost", 0)
        if last_views_7d > 0:
            sbs["avg_daily_views"] = round(last_views_7d / 7)
            sbs["period_views_growth"] = last_views_7d  # 7d total
            sb_source = "inside_api"
        if last_subs_net is not None and (last_subs_gained or last_subs_lost):
            sbs["avg_daily_subs"] = round(last_subs_net / 7)
            sbs["period_subs_growth"] = last_subs_net
            sb_source = "inside_api"
        # Total days = 7 (Inside chỉ track 7 ngày gần đây — recent_days)
        if sb_source == "inside_api":
            sbs.setdefault("total_days", 7)
    delta = res.get("delta") or {}
    since = delta.get("previous_date", "") or ""

    top = sorted(vids, key=lambda v: getattr(v, "view_count", 0),
                 reverse=True)
    new_v = sorted(
        [v for v in vids if since and
         (getattr(v, "published_at", "") or "") > since],
        key=lambda v: getattr(v, "published_at", ""), reverse=True)

    # Video đột biến: lượt xem so với TRUNG VỊ của chính kênh.
    vc_all = [int(getattr(v, "view_count", 0) or 0) for v in vids]
    median_v = statistics.median(vc_all) if vc_all else 0
    # Tỷ lệ tương tác TB kênh = (like+bình luận)/lượt xem.
    tot_e = sum(int(getattr(v, "like_count", 0) or 0)
                + int(getattr(v, "comment_count", 0) or 0)
                for v in vids)
    tot_v = sum(vc_all)
    eng_avg = round(tot_e / tot_v * 100, 2) if tot_v else 0

    def _vmult(v):
        d = vinfo(v)
        d["mult"] = round(d["views"] / median_v, 1) if median_v else 0
        # eng_hi: tỷ lệ tương tác cao bất thường (>=10%) — nghi bị bơm.
        d["eng_hi"] = d["eng"] >= 10
        return d

    # SEO components
    comps = []
    cm = seo.get("components_avg") or {}
    name_vn = {"Tag count": "Số lượng thẻ tag",
               "Keywords trong title": "Từ khoá ở tiêu đề",
               "Keywords trong description": "Từ khoá ở mô tả",
               "Tripled keywords": "Từ khoá đủ 3 chỗ",
               "Title length": "Độ dài tiêu đề",
               "Description length": "Độ dài mô tả"}
    for k in ["Tag count", "Keywords trong title",
              "Keywords trong description", "Tripled keywords",
              "Title length", "Description length"]:
        cv = cm.get(k)
        if cv:
            comps.append({"name": name_vn.get(k, k),
                          "avg": round(cv.get("avg", 0), 1),
                          "max": cv.get("max", 0)})
    # thẻ tag kênh hay dùng
    from collections import Counter
    tagc = Counter()
    for v in vids:
        for t in set((getattr(v, "tags", []) or [])):
            t = (t or "").lower().strip()
            if t:
                tagc[t] += 1
    top_tags = [{"tag": t, "n": n} for t, n in tagc.most_common(15)]

    # Phân cụm nội dung
    clusters = []
    try:
        from . import content_cluster
        cl = content_cluster.cluster_channel_videos(
            vids, channel_name=getattr(ch, "title", ""))
        for c in (cl.get("clusters") or []):
            if c.get("is_other"):
                continue
            clusters.append({"label": c.get("label", ""),
                             "n": c.get("video_count", 0),
                             "avg": c.get("avg_views", 0)})
    except Exception:
        pass

    # Thời điểm đăng
    posting = ""
    try:
        from . import posting_time
        pts = posting_time.analyze(res)
        if pts.get("total_videos", 0) >= 5:
            posting = posting_time.format_summary(pts)
    except Exception:
        pass

    # Thumbnail
    thumb = {}
    ch_t = res.get("channel_thumbnail_analysis") or {}
    ni_t = res.get("thumbnail_analysis") or {}
    cmp_t = res.get("thumbnail_comparison") or {}

    def _thd(d):
        if not d or not d.get("count"):
            return None
        return {
            "bright": f"{d.get('brightness_label','')} "
                      f"({d.get('avg_brightness',0):.0f}/255)",
            "sat": f"{d.get('saturation_label','')} "
                   f"({d.get('avg_saturation',0):.0f}/255)",
            "faces": (f"{d['avg_faces']:.1f} mặt/ảnh"
                      if d.get("avg_faces") is not None else ""),
            "edge": (f"{d['avg_edge_density']*100:.1f}% pixel cạnh "
                     f"({'busy' if d['avg_edge_density'] > 0.15 else 'gọn'})"
                     if d.get("avg_edge_density") is not None else ""),
            "text": (f"{d['pct_text_overlay']*100:.0f}% có chữ overlay"
                     if d.get("pct_text_overlay") is not None else ""),
            "colors": ", ".join(f"{n} {round(p*100)}%"
                                for n, p in d.get("top_colors", [])),
        }
    if ch_t.get("count"):
        thumb = {"self": _thd(ch_t), "niche": _thd(ni_t),
                 "obs": cmp_t.get("observations") or [],
                 "verdict": res.get("thumbnail_ai_verdict", "") or ""}

    # Từ khoá
    per = (res.get("tag_metrics") or {}).get("per_keyword") or {}
    kws = []
    for k in (res.get("keywords") or [])[:30]:
        kw = getattr(k, "keyword", str(k))
        m = per.get(kw) or {}
        comp = m.get("competition") or {}
        tr = m.get("trend") or {}
        kws.append({"kw": kw, "comp": comp.get("level", ""),
                    "rc": comp.get("result_count", 0),
                    "trend": tr.get("score", 0) or 0,
                    "dir": tr.get("direction", ""),
                    "score": round(float(getattr(k, "score", 0) or 0), 2),
                    "sources": sorted(getattr(k, "sources", []) or []),
                    "chv": int(getattr(k, "channel_video_count", 0) or 0),
                    "spark": (tr.get("sparkline", "") or "")[-40:],
                    "sug": [s for s in (m.get("autosuggest") or [])
                            if s.strip().lower() != kw.strip().lower()
                            ][:6]})
    return {
        "has": True,
        "title": getattr(ch, "title", "") or "",
        "subs": int(getattr(ch, "subscriber_count", 0) or 0),
        "url": getattr(ch, "url", "") or "",
        "desc": getattr(ch, "description", "") or "",
        "total_views": int(getattr(ch, "view_count", 0) or 0),
        "ch_vcount": int(getattr(ch, "video_count", 0) or 0),
        "seo": round(seo.get("avg_score", 0) or 0),
        "vcount": res.get("video_count", 0),
        "auto_added": bool(getattr(wc, "auto_added", False)),
        "delta": {"has": bool(delta.get("has_delta")),
                  "sub_d": delta.get("subscriber_delta", 0),
                  "sub_pct": round(delta.get("subscriber_pct", 0), 1),
                  "prev": (delta.get("previous_date", "") or "")[:10],
                  "new_vid": delta.get("new_video_count", 0),
                  "vc_d": delta.get("video_count_delta", 0),
                  "ch_up": delta.get("new_channel_upload_count", 0),
                  "new_kw": [str(k) for k in
                             (delta.get("new_keywords", []) or [])[:15]],
                  "trend_kw": [
                      {"kw": t.get("keyword", ""),
                       "pct": round(t.get("delta_pct", 0))}
                      for t in (delta.get("trending_keywords", []) or [])
                      [:10]]},
        "sb": {"days": sbs.get("total_days", 0),
               "subs_g": sbs.get("period_subs_growth", 0),
               "views_g": sbs.get("period_views_growth", 0),
               "avg_sub": round(sbs.get("avg_daily_subs", 0) or 0),
               "avg_view": round(sbs.get("avg_daily_views", 0) or 0),
               "source": sb_source,  # 'socialblade' hoặc 'inside_api'
               # Bug A37: daily 15d — nếu source=inside_api → dùng Inside
               # daily_metrics (views_daily ≥0 thực, KHÔNG âm như SB recount)
               "daily": (
                   [{"d": (dm.get("day", "") or "")[:10],
                     "s": 0,  # Inside không có total subs/day snapshot
                     "sc": dm.get("subs_net", 0),
                     "v": 0,  # Inside không có total views/day accumulated
                     "vc": dm.get("views_daily", 0)}
                    for dm in (inside_ci.get("daily_metrics_15d") or [])]
                   if (inside_ci and sb_source == "inside_api"
                       and inside_ci.get("daily_metrics_15d"))
                   else [{"d": (e.get("date", "") or "")[:10],
                          "s": e.get("subscribers", 0),
                          "sc": e.get("subs_change", 0),
                          "v": e.get("views", 0),
                          "vc": e.get("views_change", 0)}
                         for e in sbd[-15:]])},
        "ai": res.get("ai_analysis", "") or "",
        "seo_comps": comps,
        "top_tags": top_tags,
        "clusters": clusters,
        "posting": posting,
        "thumb": thumb,
        "kw": kws,
        "median_v": int(median_v),
        "eng_avg": eng_avg,
        "n_outlier": sum(1 for x in vc_all if median_v
                         and x >= 3 * median_v),
        "new_v": [_vmult(v) for v in new_v[:15]],
        "all_v": [_vmult(v) for v in top],
    }


def build_data(wid: str, as_of_day: str = "") -> dict:
    """Ráp toàn bộ dữ liệu báo cáo 22 tab cho 1 watchlist thành dict thuần.

    Tách khỏi render HTML (chốt 2026-06, gộp vào yt_manage_app): pipeline
    trả JSON này qua FastAPI → React render native. Mỗi key trong dict map
    1 tab (xem inventory s0-s22).

    as_of_day (YYYY-MM-DD) rỗng → snapshot mới nhất; có giá trị → dựng báo
    cáo theo snapshot ≤ ngày đó của từng kênh (xem lịch sử theo ngày).
    """
    from . import watchlist as wl, persistence
    w = wl.load_watchlist(wid)
    if not w:
        print(f"Khong tim thay watchlist {wid}")
        return ""
    self_ch = w.self_channel
    self_days = (persistence.snapshot_days_for_channel(self_ch.channel_id)
                 if self_ch else [])
    sel_day = as_of_day or (self_days[0] if self_days else "")
    self_res = (persistence.find_for_channel_as_of(self_ch.channel_id, sel_day)
                if self_ch else None)

    # Quy trình mới 26/05: fetch Inside channel_summary TRƯỚC khi _pack self —
    # _pack sẽ override avg_daily_views/subs từ Inside (chuẩn xác hơn SB)
    self_inside_ci = None
    if self_ch:
        try:
            from .analytics_inside import (
                match_account_tag, get_channel_inside, is_available)
            if is_available():
                tag = match_account_tag(self_ch.title or "",
                                         self_ch.channel_id)
                if tag:
                    self_inside_ci = get_channel_inside(tag, recent_days=7)
        except Exception:
            self_inside_ci = None

    data = {
        "wl": w.name,
        "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "available_dates": self_days,
        "selected_date": sel_day,
        "self": _pack(self_res, self_ch, inside_ci=self_inside_ci),
        "competitors": [], "keywords": [], "niche": {}, "niche_top": {},
        "continuity": {}, "events": [], "sb_compare": [],
        "new_comp": [], "strategy": "",
    }
    for c in w.competitor_channels:
        res = persistence.find_for_channel_as_of(c.channel_id, sel_day)
        data["competitors"].append(_pack(res, c))  # competitor giữ SB

    data["keywords"] = data["self"].get("kw", [])

    # tag_metrics của kênh chính — cần cho block kw_enrich (line ~898)
    # để cột "Cạnh tranh SEO YT" có rc cho 30 top kw kênh chính.
    data["tag_metrics"] = (self_res or {}).get("tag_metrics") or {}

    # === Kho từ khoá keywordtool (cho kênh chính) ===
    # Trả None nếu kênh chưa harvest seed nào. Tab HTML "Kho từ khoá"
    # đọc trường này; rỗng → tab hiện thông báo "chưa có data".
    try:
        from .keyword_bank_analysis import get_channel_kw_bank
        sc_data = data["self"]
        if sc_data.get("has") and self_ch:
            existing = [k.get("kw") for k in sc_data.get("kw", [])
                        if k.get("kw")]
            data["kw_bank"] = get_channel_kw_bank(
                self_ch.channel_id, sc_data.get("title", ""),
                existing_keywords=existing)
        else:
            data["kw_bank"] = None
    except Exception as e:
        print(f"  WARN: kw_bank loi: {e}")
        data["kw_bank"] = None

    # === A43 (26/05 chiều): Lịch sử kho từ khoá (snapshot + diff) ===
    # Tab HTML "📈 Lịch sử kho từ khoá" — render chart timeline +
    # bảng NEW/LOST/CHANGED so với lần chạy trước.
    try:
        from . import keyword_bank_history as kbh
        data["kw_history"] = kbh.get_history(wid, days=30)
    except Exception as e:
        print(f"  WARN: kw_history loi: {e}")
        data["kw_history"] = None

    # === Enrich tất cả từ khoá trong báo cáo với số liệu keywordtool
    # (volume + cạnh tranh THẬT). Mỗi keyword được thêm các field
    # kt_vol, kt_comp, kt_comp_label nếu có trong kho. JS bảng từ khoá
    # ưu tiên hiển thị số keywordtool, fallback về Google Trends. ===
    try:
        from .keyword_bank_analysis import enrich_keywords
        all_kws = set()
        for ch in [data["self"]] + data["competitors"]:
            for k in ch.get("kw", []):
                if k.get("kw"):
                    all_kws.add(k["kw"])
        enriched = enrich_keywords(list(all_kws))
        for ch in [data["self"]] + data["competitors"]:
            for k in ch.get("kw", []):
                kn = (k.get("kw") or "").strip().lower()
                info = enriched.get(kn)
                if info:
                    k["kt_vol"] = info["volume"]
                    k["kt_comp"] = info["competition_norm"]
                    k["kt_comp_label"] = info["competition_label"]
    except Exception as e:
        print(f"  WARN: enrich keywords loi: {e}")

    # === Wave 1: Title Pattern + Thumbnail Vision + AB Recommender ===
    # Chốt 23/05 — chuyên gia phân tích insight bổ sung cho creator.

    # 1. Title Pattern (NLP n-gram + correlation) — cho kênh chính
    try:
        from .title_pattern import analyze_title_patterns
        if self_ch and self_res:
            sc_videos = self_res.get("videos") or []
            if len(sc_videos) >= 10:
                data["title_pattern"] = analyze_title_patterns(
                    sc_videos, log_fn=lambda s: None)
            else:
                data["title_pattern"] = None
        else:
            data["title_pattern"] = None
    except Exception as e:
        print(f"  WARN: title_pattern loi: {e}")
        data["title_pattern"] = None

    # 2. Thumbnail Vision summary (đọc từ pkl nếu có, fallback heuristic
    # nếu chưa — chốt 23/05: KHÔNG để báo cáo trống tab)
    try:
        if self_res:
            tvs = self_res.get("thumbnail_vision_summary")
            if not tvs:
                # Fallback heuristic — Claude expert pattern-based
                from .claude_expert_fallback import (
                    thumbnail_vision_fallback)
                sc_videos = self_res.get("videos") or []
                tvs = thumbnail_vision_fallback(
                    self_ch.channel_id if self_ch else "",
                    sc_videos,
                    self_ch.title if self_ch else "")
            data["thumb_vision_summary"] = tvs
            data["thumb_vision_detail"] = self_res.get(
                "thumbnail_vision_analysis")
        else:
            data["thumb_vision_summary"] = None
            data["thumb_vision_detail"] = None
    except Exception as e:
        print(f"  WARN: thumb_vision loi: {e}")
        data["thumb_vision_summary"] = None
        data["thumb_vision_detail"] = None

    # 3. AB Recommender — rescue video flop của kênh nhà
    try:
        from .ab_recommender import find_rescue_candidates
        data["ab_rescue"] = find_rescue_candidates(
            wid, log_fn=lambda s: None)
    except Exception as e:
        print(f"  WARN: ab_recommender loi: {e}")
        data["ab_rescue"] = []

    # === Wave 2 modules ===
    # 4. Comment Intelligence — đọc từ pkl, fallback heuristic nếu chưa
    try:
        if self_res:
            ci = self_res.get("comment_intelligence")
            if not ci:
                from .claude_expert_fallback import (
                    comment_intelligence_fallback)
                ci = comment_intelligence_fallback(
                    self_ch.channel_id if self_ch else "",
                    self_ch.title if self_ch else "")
            data["comment_intel"] = ci
        else:
            data["comment_intel"] = None
    except Exception as e:
        print(f"  WARN: comment_intel loi: {e}")
        data["comment_intel"] = None

    # 5. Hook Timing — cần Inside data + account_tag
    try:
        from .analytics_inside import is_available, match_account_tag
        from .hook_timing import analyze_hook_timing_for_channel
        if self_ch and is_available():
            tag = match_account_tag(self_ch.title, self_ch.channel_id)
            if tag:
                data["hook_timing"] = analyze_hook_timing_for_channel(
                    tag, top_n=15, log_fn=lambda s: None)
            else:
                data["hook_timing"] = None
        else:
            data["hook_timing"] = None
    except Exception as e:
        print(f"  WARN: hook_timing loi: {e}")
        data["hook_timing"] = None

    # 6. Posting Time V2 — cần Inside data
    try:
        from .posting_time_v2 import recommend_posting_time
        if self_ch:
            from .analytics_inside import match_account_tag
            tag = match_account_tag(self_ch.title, self_ch.channel_id)
            if tag:
                data["posting_v2"] = recommend_posting_time(
                    tag, upload_timezone_offset=7.0,
                    log_fn=lambda s: None)
            else:
                data["posting_v2"] = None
        else:
            data["posting_v2"] = None
    except Exception as e:
        print(f"  WARN: posting_v2 loi: {e}")
        data["posting_v2"] = None

    # 7. Viral Predictor — train + predict cho self_channel video gần đây
    try:
        from .viral_predictor import (
            train_predictor, predict, collect_training_data)
        if self_res and self_ch:
            # Train (cached nếu đã có model trong runtime)
            if not hasattr(build_data, "_viral_model"):
                X, y = collect_training_data(log_fn=lambda s: None)
                build_data._viral_model = train_predictor(X, y,
                                                          log_fn=lambda s: None)
            model = build_data._viral_model
            sc_videos = self_res.get("videos") or []
            ch = self_res.get("channel")
            from statistics import median
            vpds = [(getattr(v, "view_count", 0) or 0)
                    / max(getattr(v, "days_old", 1) or 1, 1)
                    for v in sc_videos]
            vpds = [x for x in vpds if x > 0]
            ch_med = median(vpds) if vpds else 1000
            ch_subs = getattr(ch, "subscriber_count", 0) if ch else 0
            # Predict cho top 5 video gần nhất
            predictions = []
            for v in sorted(sc_videos,
                            key=lambda v: getattr(v, "published_at", ""),
                            reverse=True)[:5]:
                pub = getattr(v, "published_at", "") or ""
                if not pub:
                    continue
                try:
                    from datetime import datetime as _dt
                    pdt = _dt.fromisoformat(pub.replace("Z", "+00:00"))
                    hr = pdt.hour
                    dw = pdt.weekday()
                except Exception:
                    continue
                p = predict(model, ch_subs,
                            getattr(v, "title", ""),
                            getattr(v, "duration_seconds", 0) or 0,
                            hr, dw, ch_med)
                actual_vpd = ((getattr(v, "view_count", 0) or 0)
                              / max(getattr(v, "days_old", 1) or 1, 1))
                predictions.append({
                    "title": getattr(v, "title", ""),
                    "video_id": getattr(v, "video_id", ""),
                    "predicted_vpd": p.get("predicted_vpd", 0),
                    "actual_vpd": int(actual_vpd),
                    "percentile_rank": p.get("percentile_rank", 0),
                    "advice": p.get("advice", []),
                })
            data["viral_predictor"] = {
                "model_r_squared": model.get("r_squared", 0),
                "model_n_samples": model.get("n_samples", 0),
                "predictions": predictions,
            }
        else:
            data["viral_predictor"] = None
    except Exception as e:
        print(f"  WARN: viral_predictor loi: {e}")
        data["viral_predictor"] = None

    # 8. Cross-WL Learning — opportunities (compute once toàn report, đắt)
    # → chỉ compute khi build report tổng hợp, tab này empty trong báo cáo WL
    # individual. Để placeholder cho tab summary sau.

    # (Gộp yt_manage_app 2026-06): BỎ khối ghi ngược 5 field vào pkl self_channel.
    # build_data() nay là READ-ONLY (server endpoint gọi mỗi lần xem báo cáo,
    # không được mutate dữ liệu). Khâu AI sẽ đọc các field này trực tiếp từ JSON
    # ở Phase 5, không cần persist lại vào pkl.

    # Video đột biến toàn ngành — vượt >=3 lần view trung vị kênh đăng,
    # CHỈ video đăng ≤7 ngày gần nhất (chốt 21/05 — tránh outlier evergreen
    # cũ làm nhiễu, tập trung vào tín hiệu trending tươi).
    outs = []
    for c in [data["self"]] + data["competitors"]:
        if not c.get("has"):
            continue
        for v in c.get("all_v", []):
            age = v.get("age_days", 0) or 0
            if (v.get("mult", 0) >= 3
                    and v.get("views", 0) >= 50000
                    and 0 < age <= 7):
                vv = dict(v)
                vv["ch"] = vv.get("ch") or c.get("title", "")
                outs.append(vv)
    outs.sort(key=lambda v: v.get("mult", 0), reverse=True)
    data["outliers"] = outs[:25]

    # Công thức tiêu đề — phân tích trên video mọi kênh trong ngành.
    allvids = []
    for c in [data["self"]] + data["competitors"]:
        allvids += c.get("all_v", [])
    data["title_patterns"] = _title_stats(allvids)
    data["title_n"] = len(allvids)

    # AI FEEDBACK LOOP (Tier 3 #11 - 20/05): track ý tưởng AI kỳ trước
    # có được làm + có thành công không. Đo success rate + perf ratio.
    try:
        from .ai_feedback import build_feedback_for_watchlist
        data["ai_feedback"] = build_feedback_for_watchlist(w, self_res)
    except Exception as e:
        print(f"  WARN: ai_feedback loi: {e}")
        data["ai_feedback"] = {"ideas_total": 0, "ideas_done": 0,
                               "ideas_pending": 0, "success_rate": 0,
                               "avg_perf_ratio": 0, "detail": []}

    # 3 INSIGHT NÂNG CAO (Tier 1 - 20/05): topic clusters, competitive
    # gaps, title variants generator. Hook vào html_report.
    try:
        from .insights_extra import (
            topic_clusters, competitive_gaps, generate_title_variants)
        # Build channels_data từ data đã pack
        ch_data = []
        for c in [data["self"]] + data["competitors"]:
            if not c.get("has"):
                continue
            ch_data.append({
                "title": c.get("title", ""),
                "is_self": (c is data["self"]),
                "keywords": [k.get("kw") for k in c.get("kw", [])
                             if k.get("kw")],
                "videos": [{"title": v.get("title", ""),
                            "view_count": v.get("views", 0)}
                           for v in c.get("all_v", [])],
            })
        data["topic_clusters"] = topic_clusters(ch_data, top_n=12)
        data["competitive_gaps"] = competitive_gaps(
            ch_data, min_competitors=2, top_n=15)
        self_kws_str = [k.get("kw", "") for k in data["self"].get("kw", [])
                        if k.get("kw")]
        data["title_variants"] = generate_title_variants(
            self_videos=data["self"].get("all_v", []),
            keywords=self_kws_str,
            title_patterns={p["feat"]: {"lift": p["lift"]}
                            for p in data["title_patterns"]},
            n_variants=18)
    except Exception as e:
        print(f"  WARN: insights_extra loi (bo qua): {e}")
        data["topic_clusters"] = []
        data["competitive_gaps"] = []
        data["title_variants"] = []

    # Diễn biến lượt xem video kênh chính qua các kỳ giám sát.
    data["video_track"] = []
    try:
        from . import snapshots as _sn
        for v in data["self"].get("all_v", []):
            vid = v.get("vid")
            if not vid:
                continue
            byday = {}
            for r in _sn.get_video_history(vid):
                d = (r.get("snapshot_time") or "")[:10]
                if d:
                    byday[d] = int(r.get("view_count", 0) or 0)
            pts = sorted(byday.items())
            if len(pts) >= 2:
                data["video_track"].append({
                    "title": v.get("title", ""),
                    "url": v.get("url", ""),
                    "pts": [vw for _, vw in pts],
                    "growth": pts[-1][1] - pts[0][1]})
        data["video_track"].sort(key=lambda x: x["growth"],
                                 reverse=True)
    except Exception:
        pass

    # Health Check FULL (21/05/2026 mở rộng):
    # 1. Channel-level audit (7 items)
    # 2. Keyword alignment & strategy
    # 3. Video-level audit (19 items × 10 video)
    # 4. SEO action items tổng hợp
    data["health"] = []
    data["health_channel"] = {}
    data["health_keywords"] = {}
    data["health_actions"] = []
    data["niche_detected"] = "generic"
    try:
        from .health_check import (
            health_check_self_videos, health_check_channel,
            keyword_alignment_check, build_seo_action_items)
        from .niche_detector import detect_niche
        # Detect niche từ channels_data
        ch_data_for_niche = []
        for c in [data["self"]] + data["competitors"]:
            ch_data_for_niche.append({
                "keywords": [k.get("kw", "") for k in c.get("kw", [])],
                "videos": [{"title": v.get("title", "")}
                           for v in c.get("all_v", [])],
            })
        niche_k = detect_niche(ch_data_for_niche)
        data["niche_detected"] = niche_k
        if self_res:
            # Load competitor results để keyword alignment
            comp_results = []
            from .persistence import find_for_channel_as_of
            for c in w.active_channels:  # 24/05: bỏ archived
                if c.is_self:
                    continue
                try:
                    cr = find_for_channel_as_of(c.channel_id, sel_day)
                    if cr:
                        comp_results.append(cr)
                except Exception:
                    pass
            data["health"] = health_check_self_videos(
                self_res, niche_key=niche_k, max_videos=10)
            data["health_channel"] = health_check_channel(self_res)
            data["health_keywords"] = keyword_alignment_check(
                self_res, comp_results)
            data["health_actions"] = build_seo_action_items(
                data["health_channel"], data["health"],
                data["health_keywords"])
    except Exception as e:
        # Giữ default rỗng — không crash report
        pass

    # Analytics Inside (21/05/2026 — cache SQLite từ dump backend)
    # KHÔNG include revenue trong báo cáo HTML public theo yêu cầu user.
    # Mở rộng 21/05 chiều: 5 tabs s13-s17 với phân tích sâu.
    # Tối 21/05: thêm tab s18 — Inside × SEO Synthesis (7 gap).
    data["inside"] = {}
    data["inside_synthesis"] = {}
    try:
        from .analytics_inside import (is_available, match_account_tag,
            get_channel_inside, get_retention_curves,
            get_retention_full, get_thumbnail_ctr_top,
            get_thumbnail_ctr_worst, get_ctr_correlation,
            get_traffic_source_trend, get_audience_full,
            assess_traffic_source, assess_demographics)
        if is_available() and data["self"].get("title"):
            sc_title = data["self"].get("title") or ""
            # FIX 25/05: data["self"] không có key channel_id, dùng self_ch
            # trực tiếp để match_account_tag cho kênh có tên Unicode lạ
            # (vd Baby Fish Car Toys với tag DB "B__C_____Ch_i").
            sc_cid = (self_ch.channel_id if self_ch else
                      data["self"].get("channel_id") or "")
            tag = match_account_tag(sc_title, sc_cid)
            if tag:
                ci = get_channel_inside(tag, recent_days=30)
                if ci.get("has_data"):
                    # Lấy ngày data thumbnail cuối — hiển thị cho user biết
                    last_thumb_day = ""
                    try:
                        from .analytics_inside import last_thumbnail_day
                        last_thumb_day = last_thumbnail_day(tag)
                    except Exception:
                        pass
                    data["inside"] = {
                        "account_tag": tag,
                        "channel_summary": ci,
                        "last_thumbnail_day": last_thumb_day,
                        # 26/05: min_views=1 thay vì 50 — video MỚI NHẤT thường
                        # có view <50 (kênh tiny + video pub <24h). User báo bug:
                        # tab Inside Retention hiển thị video không phải mới
                        # nhất do filter min_views=50 loại video mới. Bây giờ
                        # lấy ALL 5 video mới nhất bất kể view (đúng yêu cầu
                        # "video mới nhất để đánh giá hiệu quả").
                        "retention_top": get_retention_full(
                            tag, top_n=5, min_views=1,
                            order_by="published"),
                        "thumbnail_ctr_top": get_thumbnail_ctr_top(
                            tag, top_n=15, min_impressions=200),
                        "thumbnail_ctr_worst": get_thumbnail_ctr_worst(
                            tag, top_n=10, min_impressions=200),
                        "ctr_correlation": get_ctr_correlation(tag),
                        "traffic_health": assess_traffic_source(
                            ci.get("traffic_sources_recent") or []),
                        "traffic_trend": get_traffic_source_trend(
                            tag, periods=[7, 30, 90]),
                        "audience_full": get_audience_full(tag),
                        "demographics_health": assess_demographics(
                            ci.get("demographics") or []),
                    }
                    # SYNTHESIS — gọi sau khi inside payload đã đầy đủ
                    try:
                        from .inside_synthesis import build_synthesis
                        from .niche_detector import detect_niche
                        # Build channels_data for niche detection
                        nd_pool = []
                        for c in [data["self"]] + data["competitors"]:
                            if not c.get("has"):
                                continue
                            nd_pool.append({
                                "keywords": [k.get("kw") for k in
                                             c.get("kw", []) if k.get("kw")],
                                "videos": [{"title": v.get("title", "")}
                                           for v in c.get("all_v", [])],
                            })
                        niche_key = detect_niche(nd_pool) if nd_pool \
                                    else "general"
                        # Build self_videos cho audit (G8 G9 G14 G20)
                        # self_res.videos là list YouTubeVideo objects
                        self_v_list = []
                        for v in (self_res.get("videos")
                                  if self_res else []) or []:
                            self_v_list.append({
                                "video_id": getattr(v, "video_id", ""),
                                "title": getattr(v, "title", ""),
                                "description": getattr(v, "description", "") or "",
                                "tags": getattr(v, "tags", []) or [],
                                "view_count": getattr(v, "view_count", 0) or 0,
                                "like_count": getattr(v, "like_count", 0) or 0,
                                "comment_count": getattr(v, "comment_count", 0) or 0,
                                "published_at": getattr(v, "published_at", "") or "",
                            })
                        data["inside_synthesis"] = build_synthesis(
                            data["inside"],
                            data.get("health") or [],
                            data.get("health_channel") or {},
                            data.get("health_keywords") or {},
                            niche=niche_key or "general",
                            self_data=data.get("self") or {},
                            competitors=data.get("competitors") or [],
                            self_videos=self_v_list)
                    except Exception as _e:
                        import traceback
                        print(f"  WARN synthesis: {_e}")
                        traceback.print_exc()
                        data["inside_synthesis"] = {}
    except Exception as e:
        # Không có cache hoặc lỗi → tab s13 hiển thị (chưa có data Inside)
        data["inside"] = {}
        data["inside_synthesis"] = {}

    if self_res:
        rbk = self_res.get("recent_by_keyword") or {}
        for kw, vids in rbk.items():
            top = sorted(vids, key=lambda v: getattr(v, "view_count", 0),
                         reverse=True)
            data["niche"][kw] = [vinfo(v) for v in top]
        tbk = self_res.get("top_by_keyword") or {}
        for kw, vids in tbk.items():
            top = sorted(vids, key=lambda v: getattr(v, "view_count", 0),
                         reverse=True)
            data["niche_top"][kw] = [vinfo(v) for v in top]

    # Diễn biến xuyên suốt
    try:
        from . import snapshots
        hist = snapshots.get_subscriber_history(wid, max_dates=8)
        data["continuity"] = {
            "dates": hist.get("dates") or [],
            "channels": [{"title": c["title"],
                          "is_self": c.get("is_self"),
                          "subs": c["subs"]}
                         for c in (hist.get("channels") or [])]}
        evs = snapshots.list_events(watchlist_id=wid, days_back=20)
        data["events"] = [{"date": (e.get("detected_at", "") or "")[:10],
                           "sev": e.get("severity", ""),
                           "title": e.get("title", "")}
                          for e in (evs or [])[:25]]
    except Exception:
        pass

    # So sánh Social Blade toàn ngành
    allch = [("self", data["self"])] + [
        ("comp", c) for c in data["competitors"]]
    rows = []
    for kind, c in allch:
        if not c.get("has"):
            continue
        sb = c.get("sb") or {}
        rows.append({"title": c["title"], "is_self": kind == "self",
                     "subs": c["subs"], "avg_sub": sb.get("avg_sub", 0),
                     "subs_g": sb.get("subs_g", 0),
                     "views_g": sb.get("views_g", 0)})
    rows.sort(key=lambda x: x["avg_sub"], reverse=True)
    data["sb_compare"] = rows

    data["new_comp"] = [c for c in data["competitors"]
                        if c.get("auto_added") and c.get("has")]
    la = w.latest_analysis
    if la:
        data["strategy"] = la.get("content", "") or ""

    # Bình luận khán giả của kênh chính
    data["comments"] = {}
    try:
        from . import comment_miner
        if self_ch:
            cm = comment_miner.analyze_comments(self_ch.channel_id)
            if cm.get("total_comments"):
                s = cm.get("sentiment") or {}
                from . import snapshots as _snap
                allc = _snap.get_comments(channel_id=self_ch.channel_id)
                data["comments"] = {
                    "total": cm["total_comments"],
                    "pos": s.get("positive", 0),
                    "pos_pct": round(s.get("positive_pct", 0)),
                    "neg": s.get("negative", 0),
                    "neg_pct": round(s.get("negative_pct", 0)),
                    "report": w.comment_report or "",
                    "report_at": w.comment_report_at or "",
                    "req_count": cm.get("request_count", 0),
                    "requests": [{"l": r.get("like_count", 0),
                                  "t": r.get("text", "")}
                                 for r in (cm.get("requests") or [])[:20]],
                    "top_liked": [{"l": r.get("like_count", 0),
                                   "a": r.get("author", ""),
                                   "t": r.get("text", "")}
                                  for r in (cm.get("top_liked") or [])[:15]],
                    "words": cm.get("top_words") or [],
                    "phrases": cm.get("top_phrases") or [],
                    "all": [{"l": r.get("like_count", 0),
                             "a": (r.get("author") or "").lstrip("@"),
                             "t": (r.get("text") or "").replace("\n", " ")}
                            for r in allc],
                }
    except Exception:
        pass

    # === Tạo dict kw_enrich toàn cục cho các bảng PHỤ (s6/s7/s12) lookup
    # nhanh số liệu keywordtool cho 1 từ khoá bất kỳ. Block enrich phía
    # trên đã gán k.kt_vol/k.kt_comp cho 2 bảng chính (c.kw, D.keywords);
    # đây bổ sung dict cho các bảng phụ dùng data riêng (topic_clusters,
    # competitive_gaps, health_check.keywords). ===
    try:
        from .keyword_bank_analysis import enrich_keywords as _enr
        _xkw = set()
        for tc in data.get("topic_clusters", []) or []:
            for kw in tc.get("keywords", []) or []:
                if kw:
                    _xkw.add(kw)
        for g in data.get("competitive_gaps", []) or []:
            if g.get("keyword"):
                _xkw.add(g["keyword"])
        _hc = data.get("health_check", {}) or {}
        _hkw = _hc.get("keywords", {}) or {}
        for k in _hkw.get("self_keywords", []) or []:
            if k.get("kw"):
                _xkw.add(k["kw"])
        for n in _hkw.get("niche_keywords", []) or []:
            if n.get("kw"):
                _xkw.add(n["kw"])
        # Gom cả từ khoá trong c.kw để dict đầy đủ
        for ch in [data["self"]] + data["competitors"]:
            for k in ch.get("kw", []):
                if k.get("kw"):
                    _xkw.add(k["kw"])
        _full = _enr(list(_xkw))
        # 24/05: thêm rc (result_count YouTube search) từ tag_metrics
        # để các tab phụ render được cột "Cạnh tranh SEO YT" giống tab "Tu khoa".
        _tag_m = (data.get("tag_metrics") or {}).get("per_keyword", {}) or {}
        _rc_map = {}
        for kn, info in _tag_m.items():
            comp = (info or {}).get("competition") or {}
            rc = comp.get("result_count", 0)
            if rc:
                _rc_map[(kn or "").strip().lower()] = rc
        data["kw_enrich"] = {kn: {"vol": v["volume"],
                                  "comp": v["competition_norm"],
                                  "rc": _rc_map.get((kn or "").strip().lower(), 0)}
                             for kn, v in _full.items()}
        # Thêm các từ chỉ có rc (không có volume KT) — vẫn render cột SEO YT
        for kn_low, rc in _rc_map.items():
            if kn_low not in data["kw_enrich"]:
                data["kw_enrich"][kn_low] = {"vol": None, "comp": None, "rc": rc}
    except Exception as e:
        print(f"  WARN: build kw_enrich loi: {e}")
        data["kw_enrich"] = {}

    return data


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" type="image/png" href="/favicon.png">
<title>Bao cao nghien cuu YouTube</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
/* A50: reserve scrollbar space để body không shift khi đổi tab dài/ngắn */
html{scrollbar-gutter:stable;overflow-y:scroll}
body{font-family:'Segoe UI',Roboto,Arial,sans-serif;background:#f0f0f0;
color:#1a1a1a;font-size:15px;line-height:1.55;margin:0}
/* A46 (26/05 tối): sidebar nav bên trái thay nav ngang nhiều dòng */
.wrap{max-width:1340px;margin:0 auto;background:#fff;min-height:100vh;
display:flex;flex-wrap:wrap;align-content:flex-start}
header{flex:0 0 100%;background:#C8102E;color:#fff;padding:14px 22px;
display:flex;align-items:center;gap:16px;box-sizing:border-box}
header .logo{width:54px;height:54px;flex-shrink:0;border-radius:6px;
background:#fff;padding:3px}
header .title-block{flex:1;min-width:0}
header .company{font-size:12px;font-weight:600;letter-spacing:.6px;
text-transform:uppercase;opacity:.85;margin-bottom:2px}
header h1{font-size:19px;margin:0;line-height:1.25}
header .sub{font-size:12.5px;opacity:.9;margin-top:2px}
/* A47 (26/05 tối): nav 7 nhóm dropdown accordion — click header
   để mở/đóng. Mặc định: nhóm chứa tab active expand, các nhóm khác
   collapse → sidebar gọn, dễ scan */
nav{flex:0 0 240px;display:flex;flex-direction:column;background:#1a1a1a;
position:sticky;top:0;align-self:flex-start;max-height:100vh;
overflow-y:auto;z-index:9}
nav .grp{display:flex;flex-direction:column}
nav .grp-hdr{width:100%;background:#0f0f0f;color:#ccc;border:0;
padding:10px 14px;text-align:left;cursor:pointer;font-size:11px;
font-weight:700;text-transform:uppercase;letter-spacing:.6px;
border-top:1px solid #333;display:flex;align-items:center;gap:8px;
box-sizing:border-box}
nav .grp-hdr:hover{background:#1f1f1f;color:#fff}
nav .grp-hdr .chev{transition:transform .2s;display:inline-block;
font-size:10px;color:#888;width:10px}
nav .grp.collapsed .grp-hdr .chev{transform:rotate(-90deg)}
nav .grp-body{overflow:hidden;max-height:1000px;
transition:max-height .25s ease}
nav .grp.collapsed .grp-body{max-height:0}
nav button.tab{width:100%;background:none;border:0;color:#ddd;
padding:7px 14px 7px 22px;text-align:left;cursor:pointer;font-size:13px;
font-weight:500;display:block;box-sizing:border-box}
nav button.tab:hover{background:#2a2a2a}
nav button.tab.on{background:#C8102E;color:#fff}
/* A48 (26/05 tối): 7 sắc cầu vồng cho 7 nhóm — header đậm, tab con
   pastel cùng tone, body bg tối cùng tone */
/* 🔴 Nhóm 1: Tổng quan — Đỏ FMC */
nav .grp-1 .grp-hdr{background:#C8102E;color:#fff}
nav .grp-1 .grp-hdr:hover{background:#e01a3a}
nav .grp-1 .grp-body{background:#2d1014}
nav .grp-1 button.tab{color:#ff8a98}
nav .grp-1 button.tab:hover{background:#4d181f;color:#fff}
nav .grp-1 button.tab.on{background:#C8102E;color:#fff}
/* 🟠 Nhóm 2: Kênh chính — Cam */
nav .grp-2 .grp-hdr{background:#e67e22;color:#fff}
nav .grp-2 .grp-hdr:hover{background:#f08a30}
nav .grp-2 .grp-body{background:#2d1c0e}
nav .grp-2 button.tab{color:#ffc587}
nav .grp-2 button.tab:hover{background:#4d2e16;color:#fff}
nav .grp-2 button.tab.on{background:#e67e22;color:#fff}
/* 🟡 Nhóm 3: Khán giả — Vàng */
nav .grp-3 .grp-hdr{background:#d4a418;color:#1a1a1a}
nav .grp-3 .grp-hdr:hover{background:#e8b525}
nav .grp-3 .grp-hdr .chev{color:#1a1a1a}
nav .grp-3 .grp-body{background:#2d2509}
nav .grp-3 button.tab{color:#ffea66}
nav .grp-3 button.tab:hover{background:#4d3d10;color:#fff}
nav .grp-3 button.tab.on{background:#d4a418;color:#1a1a1a}
/* 🟢 Nhóm 4: Traffic & CTR — Lục */
nav .grp-4 .grp-hdr{background:#27ae60;color:#fff}
nav .grp-4 .grp-hdr:hover{background:#2ec773}
nav .grp-4 .grp-body{background:#0e2d1c}
nav .grp-4 button.tab{color:#6cd690}
nav .grp-4 button.tab:hover{background:#16472b;color:#fff}
nav .grp-4 button.tab.on{background:#27ae60;color:#fff}
/* 🔵 Nhóm 5: Nội dung — Lam */
nav .grp-5 .grp-hdr{background:#3498db;color:#fff}
nav .grp-5 .grp-hdr:hover{background:#4ba6e8}
nav .grp-5 .grp-body{background:#0e202d}
nav .grp-5 button.tab{color:#87c5ff}
nav .grp-5 button.tab:hover{background:#163647;color:#fff}
nav .grp-5 button.tab.on{background:#3498db;color:#fff}
/* 🟣 Nhóm 6: Từ khoá & SEO — Chàm */
nav .grp-6 .grp-hdr{background:#6c5ce7;color:#fff}
nav .grp-6 .grp-hdr:hover{background:#7d6df0}
nav .grp-6 .grp-body{background:#1c1a2d}
nav .grp-6 button.tab{color:#b1a8ff}
nav .grp-6 button.tab:hover{background:#2e2949;color:#fff}
nav .grp-6 button.tab.on{background:#6c5ce7;color:#fff}
/* 🟪 Nhóm 7: Đối thủ & Ngách — Tím */
nav .grp-7 .grp-hdr{background:#9b59b6;color:#fff}
nav .grp-7 .grp-hdr:hover{background:#ad6cc7}
nav .grp-7 .grp-body{background:#211423}
nav .grp-7 button.tab{color:#d29afa}
nav .grp-7 button.tab:hover{background:#3d2447;color:#fff}
nav .grp-7 button.tab.on{background:#9b59b6;color:#fff}
section{flex:1 1 0;min-width:0;display:none;padding:18px 22px;
box-sizing:border-box}
section.on{display:block}
@media (max-width:900px){
nav{flex:0 0 100%;position:static;max-height:none}
nav .grp-body{max-height:1000px}
nav .grp.collapsed .grp-body{max-height:0}}
h2{color:#C8102E;font-size:17px;margin:20px 0 8px;border-bottom:2px solid
#C8102E;padding-bottom:4px}
h2:first-child{margin-top:4px}
h3{font-size:14.5px;margin:12px 0 5px;color:#333}
.kv{display:grid;grid-template-columns:1fr 1fr;gap:6px 16px;margin:8px 0}
.kv div{background:#f7f7f7;padding:7px 10px;border-radius:5px}
.kv b{color:#C8102E}
table{width:100%;border-collapse:collapse;margin:8px 0;font-size:13px}
th,td{border:1px solid #ddd;padding:6px 8px;text-align:left;
vertical-align:middle}
th{background:#C8102E;color:#fff;cursor:pointer;user-select:none}
th:hover{background:#a60d26}
tr:nth-child(even){background:#f7f7f7}
td img{width:116px;border-radius:4px;display:block}
a{color:#1558b0;text-decoration:none}a:hover{text-decoration:underline}
.num{text-align:right;font-variant-numeric:tabular-nums}
.box{background:#fff7e6;border-left:4px solid #f0a020;padding:10px 14px;
margin:9px 0;white-space:pre-wrap;font-size:14px;border-radius:0 5px 5px 0}
.search{width:100%;padding:9px 12px;font-size:14px;border:1px solid #ccc;
border-radius:6px;margin:6px 0}
select{padding:9px 12px;font-size:15px;border:1px solid #ccc;
border-radius:6px;width:100%;margin:6px 0}
.pill{display:inline-block;padding:2px 9px;border-radius:11px;font-size:12px;
font-weight:700;color:#fff}
.low{background:#1b7a3d}.medium{background:#b7791f}.high{background:#d13438}
.rising{color:#1b7a3d;font-weight:700}.declining{color:#d13438}
.muted{color:#888}.new{background:#fff0a8}
tr.outlier td{background:#ffe6b3}
.tagrow span{display:inline-block;background:#eee;border-radius:10px;
padding:2px 9px;margin:2px;font-size:12px}
.spark{font-family:Consolas,'Courier New',monospace;letter-spacing:1px;
white-space:nowrap;color:#1558b0}
footer{text-align:center;padding:16px;color:#888;font-size:12px}
@media(max-width:680px){.kv{grid-template-columns:1fr}td img{width:92px}
section{padding:14px 12px}}
</style></head><body><div class="wrap">
<header>/*LOGO*/<div class="title-block"><div class="company">Funtime Media Corp</div><h1 id="hT"></h1><div class="sub" id="hS"></div></div></header>
<nav id="nav"></nav>
<section id="s0" class="on"></section><section id="s1"></section>
<section id="s2"></section><section id="s_kw"></section><section id="s_kwh"></section><section id="s3"></section>
<section id="s4"></section><section id="s5"></section>
<section id="s6"></section><section id="s7"></section>
<section id="s8"></section><section id="s9"></section>
<section id="s10"></section>
<section id="s11"></section>
<section id="s12"></section>
<section id="s13"></section>
<section id="s14"></section>
<section id="s15"></section>
<section id="s16"></section>
<section id="s17"></section>
<section id="s18"></section>
<section id="s19"></section>
<section id="s20"></section>
<section id="s21"></section>
<section id="s22"></section>
<footer>Funtime Media Corp — Bao cao nghien cuu YouTube</footer>
</div>
<script>
const D=/*DATA*/;
const fmt=n=>(n||0).toLocaleString('vi-VN');
const sg=n=>(n>=0?'+':'')+fmt(n);
const esc=s=>(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;')
.replace(/>/g,'&gt;');
const fmtdur=s=>{s=Math.round(s||0);if(!s)return '-';
const h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;
return (h?h+':'+String(m).padStart(2,'0'):String(m))+':'+
String(x).padStart(2,'0');};
function cp(lv){const m={low:'Thap',medium:'Trung binh',high:'Cao'};
return lv?`<span class="pill ${lv}">${m[lv]||lv}</span>`:'-';}
function dr(d){return{rising:'dang tang',stable:'on dinh',
declining:'dang giam'}[d]||'';}
function kte(kw){const e=D.kw_enrich||{};
return e[(kw||'').trim().toLowerCase()]||null;}
// 24/05: kteCell render 3 cell — Bid Ads (KT) %, Volume (KT), Cạnh tranh SEO YT.
// Bid Ads = mức bid Google Ads PPC (KHÔNG phản ánh SEO YT).
// Cạnh tranh SEO YT = số kết quả video YouTube (chuẩn SEO video):
//   <100K=Thấp 🟢, 100K-1M=Trung 🟡, >1M=Cao 🔴.
function kteCell(kw){const e=kte(kw);
if(!e)return '<td class="muted">-</td><td class="muted">-</td><td class="muted">-</td>';
// Bid Ads (KT) %
let bidCell='<td class="muted">-</td>';
if(e.comp!=null){
  const cc=e.comp<0.33?'low':(e.comp<0.66?'medium':'high');
  bidCell='<td><span class="pill '+cc+'">'+Math.round(e.comp*100)+'%</span></td>';
}
// Volume (KT)
const volCell=(e.vol!=null)?
  '<td class="num">'+fmt(e.vol)+'</td>':'<td class="muted">-</td>';
// Cạnh tranh SEO YT từ result_count
let seoCell='<td class="muted">-</td>';
if(e.rc>0){
  const lv=(e.rc<100000)?'low':(e.rc<1000000)?'medium':'high';
  const lvLabel={low:'Thấp',medium:'Trung',high:'Cao'}[lv];
  seoCell='<td><span class="pill '+lv+'">'+lvLabel+' ('+fmt(e.rc)+')</span></td>';
}
return bidCell+volCell+seoCell;}
// clKt: tính TB cho cụm — vol, comp (Bid Ads %), rc (SEO YT count)
function clKt(kws){let sV=0,sC=0,sRC=0,nC=0,nRC=0;
for(const kw of (kws||[])){const e=kte(kw);
if(e){sV+=e.vol||0;
  if(e.comp!=null){sC+=e.comp;nC++;}
  if(e.rc>0){sRC+=e.rc;nRC++;}}}
return {vol:sV,comp:nC?sC/nC:null,rc:nRC?Math.round(sRC/nRC):0,hits:nC};}
function vrows(list,full){return list.map(v=>`<tr${
full&&v.mult>=3?' class="outlier"':''}>
<td><a href="${v.url}" target="_blank">${v.vid?
`<img loading="lazy" src="https://i.ytimg.com/vi/${v.vid}/mqdefault.jpg">`
:''}</a></td>
<td><a href="${v.url}" target="_blank">${v.title}</a>${v.ch?
`<br><span class="muted">${v.ch}</span>`:''}</td>
<td class="num">${fmt(v.views)}</td>
<td class="num">${v.age_days||'-'}</td>
<td class="num">${fmt(v.vpd)}</td>
<td class="num">${v.date||''}</td>
${full?`<td class="num">${fmtdur(v.dur)}</td>`+
`<td class="num">${fmt(v.likes)}</td>`+
`<td class="num">${fmt(v.cmts)}</td>`+
`<td class="num">${v.eng?(v.eng_hi?'🔺 ':'')+v.eng+'%':'-'}</td>`+
`<td class="num">${v.mult?(v.mult>=3?'🚀 ':'')+'x'+v.mult:'-'}</td>`
:''}</tr>`).join('');}
function vtable(list,full){return list.length?`<table class="srt"><thead>
<tr><th>Ảnh</th><th>Tiêu đề video</th><th>Lượt xem</th>
<th>Ngày (tuổi)</th><th>Xem/ngày</th><th>Đăng</th>
${full?'<th>Thời lượng</th><th>Thích</th><th>Bình luận</th>'+
'<th>Tương tác</th><th>vs TB kênh</th>':''}
</tr></thead><tbody>${vrows(list,full)}</tbody></table>`:
'<p class="muted">Không có video.</p>';}

// Chi tiet day du 1 kenh (kenh chinh + doi thu)
function chDetail(c){
if(!c||!c.has)return '<p class="muted">Chua co du lieu kenh nay.</p>';
let h=`<div class="kv">
<div><b>Kenh:</b> ${c.url?`<a href="${c.url}" target="_blank">`+
`${c.title}</a>`:c.title}</div>
<div><b>Nguoi dang ky:</b> ${fmt(c.subs)}</div>`+
(c.total_views?`<div><b>Tong luot xem:</b> ${fmt(c.total_views)}</div>`:'')+
(c.ch_vcount?`<div><b>Video kenh da dang:</b> ${fmt(c.ch_vcount)}`+
`</div>`:'')+
`<div><b>Diem SEO:</b> ${c.seo}/100</div>
<div><b>Video da phan tich:</b> ${fmt(c.vcount)}</div>`+
(c.eng_avg?`<div><b>Tuong tac TB:</b> ${c.eng_avg}% (like+bl/view)`+
`</div>`:'')+`</div>`;
const d=c.delta||{};
if(d.has){h+=`<h3>Thay đổi so với kỳ trước (${d.prev})</h3>`+
`<p>Người đăng ký: <b>${sg(d.sub_d)}</b> (${sg(d.sub_pct)}%)`+
(d.vc_d?` • Số video kênh: <b>${sg(d.vc_d)}</b>`:'')+
(d.ch_up?` • Kênh vừa đăng <b>${fmt(d.ch_up)}</b> video mới`:'')+
` • Video mới xuất hiện trong ngành: ${fmt(d.new_vid)}.</p>`;
if(d.new_kw&&d.new_kw.length)h+='<p><b>Từ khoá mới của ngành:</b> '+
d.new_kw.map(esc).join(', ')+'</p>';
if(d.trend_kw&&d.trend_kw.length)h+='<p><b>Từ khoá đang nóng lên:'+
'</b> '+d.trend_kw.map(t=>esc(t.kw)+' ('+sg(t.pct)+'%)').join(', ')+
'</p>';}
const sb=c.sb||{};
// A37 fix: tiêu đề + cột render theo source (Inside cho kênh chính
// không có total snapshot, bỏ 2 cột "Nguoi DK" + "Tong xem")
const isInside=sb.source==='inside_api';
const dailyTitle=isInside?'Inside YouTube Analytics':'Social Blade';
if(sb.days){h+=`<h3>${dailyTitle} — ${sb.days} ngay gan nhat</h3>
<p>Nguoi dang ky: <b>${sg(sb.subs_g)}</b> (TB ${sg(sb.avg_sub)}/ngay) • `+
`Luot xem: <b>${sg(sb.views_g)}</b> (TB ${sg(sb.avg_view)}/ngay)</p>`;
if(sb.daily&&sb.daily.length){
  if(isInside){
    // Kênh chính: chỉ 3 cột (Ngay, DK +/-, Xem +/-) — bỏ "Nguoi DK"
    // và "Tong xem" vì Inside không có total snapshot
    h+=`<table class="srt"><thead><tr>
<th>Ngay</th><th>DK +/-</th><th>Xem +/-</th></tr></thead><tbody>`
+sb.daily.map(r=>`<tr>
<td>${r.d}</td><td class="num">${sg(r.sc)}</td>
<td class="num">${sg(r.vc)}</td></tr>`).join('')+'</tbody></table>';
  }else{
    // Đối thủ: SB đầy đủ 5 cột như cũ
    h+=`<table class="srt"><thead><tr>
<th>Ngay</th><th>Nguoi DK</th><th>DK +/-</th><th>Tong xem</th>
<th>Xem +/-</th></tr></thead><tbody>`+sb.daily.map(r=>`<tr>
<td>${r.d}</td><td class="num">${fmt(r.s)}</td>
<td class="num">${sg(r.sc)}</td><td class="num">${fmt(r.v)}</td>
<td class="num">${sg(r.vc)}</td></tr>`).join('')+'</tbody></table>';
  }
}}
if(c.ai)h+='<h3>Phan tich AI</h3><div class="box">'+
c.ai.replace(/</g,'&lt;')+'</div>';
if(c.seo_comps&&c.seo_comps.length){
h+='<h3>Phan tich the tag & SEO</h3><table class="srt"><thead><tr>'+
'<th>Hang muc</th><th>Diem</th><th>Toi da</th></tr></thead><tbody>'+
c.seo_comps.map(s=>`<tr><td>${s.name}</td>`+
`<td class="num">${s.avg}</td><td class="num">${s.max}</td></tr>`)
.join('')+'</tbody></table>';
if(c.top_tags&&c.top_tags.length)h+='<p><b>The tag hay dung:</b></p>'+
'<div class="tagrow">'+c.top_tags.map(t=>
`<span>${t.tag} (${t.n})</span>`).join('')+'</div>';}
if(c.clusters&&c.clusters.length){
h+='<h3>Phan cum noi dung — format nao hieu qua</h3>'+
'<table class="srt"><thead><tr><th>Cum / Format</th><th>So video</th>'+
'<th>View trung binh</th></tr></thead><tbody>'+c.clusters.map(cl=>
`<tr><td>${cl.label}</td><td class="num">${cl.n}</td>`+
`<td class="num">${fmt(cl.avg)}</td></tr>`).join('')+'</tbody></table>';}
if(c.posting)h+='<h3>Thoi diem dang toi uu</h3><p>'+
c.posting.replace(/</g,'&lt;')+'</p>';
const t=c.thumb||{};
if(t.self){h+='<h3>Anh thu nhỏ (thumbnail)</h3>'+
'<p><b>Kenh minh:</b> do sang '+t.self.bright+', '+t.self.sat+
'. Mau chu dao: '+t.self.colors+'.</p>';
const dpe=[];if(t.self.faces)dpe.push(t.self.faces);
if(t.self.edge)dpe.push(t.self.edge);if(t.self.text)dpe.push(t.self.text);
if(dpe.length)h+='<p><b>Phan tich sau:</b> '+dpe.join(' • ')+'</p>';
if(t.niche){h+='<p><b>Top nganh:</b> do sang '+t.niche.bright+', '+
t.niche.sat+'. Mau: '+t.niche.colors+'.</p>';
const dpn=[];if(t.niche.faces)dpn.push(t.niche.faces);
if(t.niche.edge)dpn.push(t.niche.edge);if(t.niche.text)dpn.push(t.niche.text);
if(dpn.length)h+='<p><b>Phan tich sau ngach:</b> '+dpn.join(' • ')+'</p>';}
(t.obs||[]).forEach(o=>h+='<p>- '+o+'</p>');
if(t.verdict)h+='<div class="box">'+t.verdict.replace(/</g,'&lt;')+
'</div>';}
if(c.new_v&&c.new_v.length){h+='<h3>Video vua dang — moi tu ky truoc ('+
c.new_v.length+')</h3>'+vtable(c.new_v,true);}
h+='<h3>Video cua kenh ('+((c.all_v||[]).length)+
') — sap theo luot xem</h3>';
h+='<p class="muted">'+
(c.n_outlier?'🚀 <b>'+c.n_outlier+' video đột biến</b> (≥3 lần view '+
'trung vị — bôi vàng trong bảng). ':'')+
'Cột "vs TB kênh" = video gấp mấy lần view trung vị. Cột "Tương '+
'tác" = (like+bình luận)/view — 🔺 = cao bất thường (≥10%), video '+
'có thể bị bơm like/bình luận.</p>';
h+=vtable(c.all_v||[],true);
if(c.kw&&c.kw.length){h+='<h3>Tu khoa cua kenh</h3>'+
'<p class="muted"><b>Bid Ads (KT)</b> = mức bid Google Ads PPC keywordtool.io '+
'(KHÔNG phản ánh độ khó SEO YouTube — generic kw như "diy"/"asmr" bid Ads thấp '+
'nhưng SEO YT cực cao). <b>Cạnh tranh SEO YT</b> = số kết quả video YouTube '+
'thực tế (chuẩn cho SEO video). <b>Volume</b>: lượng search/tháng từ keywordtool.io.</p>'+
'<table class="srt"><thead><tr><th>Tu khoa</th>'+
'<th>Bid Ads (KT)</th><th>Volume tim kiem</th>'+
'<th>Canh tranh SEO YT</th><th>SEO score</th></tr></thead><tbody>'+c.kw.map(k=>{
  const cc=(k.kt_comp!=null)?
    '<span class="pill '+(k.kt_comp<0.33?'low':(k.kt_comp<0.66?'medium':'high'))+'">'+
    Math.round(k.kt_comp*100)+'%</span>'
    :'<span class="muted" title="Bank keywordtool chua co tu khoa nay">⏳ Chua harvest</span>';
  const vc=(k.kt_vol!=null)?fmt(k.kt_vol):'<span class="muted" title="Bank keywordtool chua co tu khoa nay">⏳ Chua harvest</span>';
  // Cạnh tranh SEO YT từ result_count YouTube search (số video)
  // <100K = LOW, 100K-1M = MED, >1M = HIGH
  let seoComp='<span class="muted">-</span>';
  if(k.rc>0){
    const lv=(k.rc<100000)?'low':(k.rc<1000000)?'medium':'high';
    const lvLabel={low:'Thap',medium:'Trung',high:'Cao'}[lv];
    seoComp='<span class="pill '+lv+'">'+lvLabel+' ('+fmt(k.rc)+' video)</span>';
  }
  // SEO score = volume / (max(rc/10000, 1)) — cao = ngon (volume cao, rc thấp)
  let seoScore='-';
  if(k.kt_vol!=null&&k.rc>0){
    const s=Math.round(k.kt_vol/Math.max(k.rc/10000, 1));
    seoScore='<b>'+fmt(s)+'</b>';
  }
  return '<tr><td>'+k.kw+'</td><td>'+cc+'</td>'+
  '<td class="num">'+vc+'</td>'+
  '<td>'+seoComp+'</td>'+
  '<td class="num">'+seoScore+'</td></tr>';
}).join('')+'</tbody></table>';}
if(c.desc)h+='<h3>Mo ta kenh</h3><div class="box">'+esc(c.desc)+'</div>';
return h;}

document.getElementById('hT').textContent=
 (D.self.title||D.wl)+' — Bao cao nghien cuu';
document.getElementById('hS').textContent=
 'Danh sach: '+D.wl+'  •  Ngay lap: '+D.date;

// Tabs gom 7 nhóm chủ đề (user chốt 26/05 tối A45):
// [id, label, group_name (nếu là tab đầu nhóm — render divider)]
const tabs=[
// A. Tổng quan & Sức khoẻ
['s12','🩺 Health Check','Tổng quan'],
['s9','Phan hoi AI'],
['s5','Chien luoc AI'],
// B. Kênh chính: Hiệu quả tổng thể
['s0','Kenh chinh','Kênh chính'],
['s13','📊 Inside: Tóm tắt'],
['s18','🧠 Inside × SEO Synthesis'],
// C. Kênh chính: Khán giả
['s14','👥 Inside: Audience','Khán giả'],
['s21','💬 Audience insight'],
['s16','📉 Inside: Retention'],
// D. Kênh chính: Traffic & CTR
['s15','🚦 Inside: Traffic','Traffic & CTR'],
['s17','🖼 Inside: Thumbnail CTR'],
['s20','🤖 AI Vision thumbnail'],
['s22','🔮 Dự đoán + ⏰ Giờ post'],
// E. Nội dung video
['s1','Video theo tu khoa','Nội dung'],
['s10','Video dot bien'],
['s19','💡 Cứu video flop'],
// F. Từ khoá & SEO
['s2','Tu khoa','Từ khoá & SEO'],
['s8','Tieu de mau'],
['s_kw','📚 Kho tu khoa'],
['s_kwh','📈 Lich su KT'],
['s11','📚 SEO Best Practice'],
// G. Đối thủ & Ngách
['s3','Doi thu','Đối thủ & Ngách'],
['s7','Khoang trong doi thu'],
['s6','Cum chu de'],
['s4','Dien bien & Su kien'],
];
// A47 (26/05 tối): render nav theo NHÓM với accordion dropdown.
// Group bằng item có t[2]. Mặc định: chỉ nhóm chứa tab active expand.
const nav=document.getElementById('nav');
const groups=[];let cur=null;
tabs.forEach(t=>{if(t[2]){cur={name:t[2],items:[t]};groups.push(cur);}
else if(cur){cur.items.push(t);}});
groups.forEach((g,gi)=>{
  const grpDiv=document.createElement('div');grpDiv.className='grp';
  grpDiv.classList.add('grp-'+(gi+1)); // A48: 7 sắc cầu vồng
  if(gi!==0)grpDiv.classList.add('collapsed'); // chỉ nhóm đầu expand
  const hdr=document.createElement('button');hdr.className='grp-hdr';
  hdr.innerHTML='<span class="chev">▾</span> '+g.name;
  hdr.onclick=()=>grpDiv.classList.toggle('collapsed');
  grpDiv.appendChild(hdr);
  const body=document.createElement('div');body.className='grp-body';
  g.items.forEach((t,ti)=>{const b=document.createElement('button');
    b.className='tab';b.textContent=t[1];
    if(gi===0&&ti===0)b.classList.add('on');
    b.onclick=()=>{document.querySelectorAll('nav button.tab').forEach(x=>
      x.classList.remove('on'));b.classList.add('on');
      document.querySelectorAll('section').forEach(s=>s.classList.remove('on'));
      document.getElementById(t[0]).classList.add('on');
      window.scrollTo(0,0);bindSort();};
    body.appendChild(b);});
  grpDiv.appendChild(body);nav.appendChild(grpDiv);});

// s0 - Kenh chinh + Binh luan khan gia
function commentsBlock(){const c=D.comments;
if(!c||!c.total)return '';
let h='<h2>Binh luan khan gia ('+fmt(c.total)+')</h2>'+
'<p>Tich cuc: <b>'+fmt(c.pos)+'</b> ('+c.pos_pct+'%) &nbsp;•&nbsp; '+
'Tieu cuc: <b>'+fmt(c.neg)+'</b> ('+c.neg_pct+'%)</p>';
if(c.report)h+='<h3>Nhan dinh AI'+(c.report_at?' — '+c.report_at:'')+
'</h3><div class="box">'+esc(c.report)+'</div>';
if(c.requests&&c.requests.length){h+='<h3>Khan gia xin lam video ('+
c.req_count+' binh luan)</h3><table class="srt"><thead><tr>'+
'<th>Thich</th><th>Noi dung</th></tr></thead><tbody>'+c.requests.map(r=>
`<tr><td class="num">${fmt(r.l)}</td><td>${esc(r.t)}</td></tr>`).join('')+
'</tbody></table>';}
if(c.top_liked&&c.top_liked.length){h+='<h3>Binh luan nhieu thich nhat'+
'</h3><table class="srt"><thead><tr><th>Thich</th><th>Nguoi xem</th>'+
'<th>Noi dung</th></tr></thead><tbody>'+c.top_liked.map(r=>
`<tr><td class="num">${fmt(r.l)}</td><td>${esc(r.a)}</td>`+
`<td>${esc(r.t)}</td></tr>`).join('')+'</tbody></table>';}
if(c.words&&c.words.length)h+='<h3>Tu hay gap trong binh luan</h3>'+
'<div class="tagrow">'+c.words.map(w=>
`<span>${esc(w[0])} (${w[1]})</span>`).join('')+'</div>';
if(c.phrases&&c.phrases.length)h+='<h3>Cum tu hay gap</h3>'+
'<div class="tagrow">'+c.phrases.map(p=>
`<span>${esc(p[0])} (${p[1]})</span>`).join('')+'</div>';
if(c.all&&c.all.length){h+='<h3>Toan bo binh luan ('+c.all.length+
')</h3><input class="search" placeholder="Tim binh luan..." '+
'onkeyup="filterT(this,\'cmtT\')">'+
'<table class="srt" id="cmtT"><thead><tr><th>Thich</th>'+
'<th>Nguoi xem</th><th>Noi dung</th></tr></thead><tbody>'+c.all.map(r=>
`<tr><td class="num">${fmt(r.l)}</td><td>${esc(r.a)}</td>`+
`<td>${esc(r.t)}</td></tr>`).join('')+'</tbody></table>';}
return h;}
function trackBlock(){const T=D.video_track||[];
if(!T.length)return '';
return '<h2>📈 Diễn biến lượt xem video kênh chính</h2>'+
'<p>Lượt xem từng video qua các kỳ giám sát — để biết sớm video '+
'nào đang tăng tốc (nên đẩy thêm) hay đã chững lại.</p>'+
'<table class="srt"><thead><tr><th>Video</th>'+
'<th>Lượt xem qua các kỳ</th><th>Tăng</th></tr></thead><tbody>'+
T.map(t=>`<tr><td><a href="${t.url}" target="_blank">`+
`${esc(t.title)}</a></td>`+
`<td>${t.pts.map(p=>fmt(p)).join(' → ')}</td>`+
`<td class="num">${sg(t.growth)}</td></tr>`).join('')+
'</tbody></table>';}
document.getElementById('s0').innerHTML='<h2>Kenh chinh</h2>'+
chDetail(D.self)+trackBlock()+commentsBlock();

// s1 - Video nganh theo tu khoa (CHỈ tab này có dropdown chọn từ khoá)
const NT=D.niche_top||{};
const nk=Object.keys(D.niche).length?Object.keys(D.niche)
:Object.keys(NT);
let nh='<h2>🔑 Video của ngành theo từ khoá</h2>'+
'<p>Chọn 1 từ khoá để xem các video MỚI nhiều lượt xem + XẾP HẠNG '+
'top video mọi thời cho từ khoá đó (lấy từ '+nk.length+' từ khoá '+
'phần mềm đã trích).</p>'+
'<p><b>Chọn từ khoá: </b>'+
'<select id="kwsel" style="font-size:14px;padding:6px 10px;'+
'border-radius:4px;border:1px solid #ccc;background:#fff;min-width:260px">'+
nk.map((k,i)=>`<option value="${i}">${esc(k)} (${(D.niche[k]||[]).length} video)</option>`)
.join('')+'</select></p><div id="nb"></div>';
document.getElementById('s1').innerHTML=nh;
function showNiche(){const k=nk[document.getElementById('kwsel').value];
document.getElementById('nb').innerHTML=
'<h3>🚀 Video mới nhiều lượt xem — "'+esc(k)+'"</h3>'+vtable(D.niche[k]||[])+
'<h3>🔥 Xếp hạng top video theo từ khoá — "'+esc(k)+'"</h3>'+
vtable(NT[k]||[]);bindSort();}
if(nk.length){document.getElementById('kwsel').onchange=showNiche;
showNiche();}else document.getElementById('s1').innerHTML+=
'<p class="muted">Không có dữ liệu từ khoá ngách.</p>';

// s10 - Video dot bien cua nganh (tab rieng) — CHỈ video ≤7 ngày
const OUT=D.outliers||[];
let obh='<h2>🚀 Video đột biến của ngành ('+OUT.length+')</h2>'+
'<p>Các video <b>đăng ≤7 ngày</b> đạt lượt xem vượt <b>≥3 lần mức '+
'trung vị</b> của chính kênh — dấu hiệu YouTube đang đẩy mạnh chủ đề/'+
'format đó. Nên nghiên cứu kỹ tiêu đề, thumbnail, chủ đề.</p>'+
(OUT.length?'<table class="srt"><thead><tr><th>Ảnh</th><th>Tiêu đề</th>'+
'<th>Kênh</th><th>Ngày (tuổi)</th><th>Đăng</th>'+
'<th>Lượt xem</th><th>Xem/ngày</th><th>vs TB kênh</th>'+
'</tr></thead><tbody>'+
OUT.map(v=>`<tr><td><a href="${v.url}" target="_blank">${v.vid?
`<img loading="lazy" src="https://i.ytimg.com/vi/${v.vid}/mqdefault.jpg">`
:''}</a></td>
<td><a href="${v.url}" target="_blank">${esc(v.title)}</a></td>
<td>${esc(v.ch||'')}</td>
<td class="num">${v.age_days||'-'}</td>
<td class="num">${esc(v.date||'-')}</td>
<td class="num">${fmt(v.views)}</td>
<td class="num">${fmt(v.vpd)}</td>
<td class="num">🚀 x${v.mult}</td></tr>`).join('')+'</tbody></table>'
:'<p class="muted">Chưa có video đột biến đăng trong 7 ngày gần nhất.</p>');
document.getElementById('s10').innerHTML=obh;

// s2 - Tu khoa: bang tong quan + bang canh tranh & xu huong
const hasSpark=D.keywords.some(k=>k.spark);
let s2h='<h2>Tu khoa chu dao cua nganh</h2>'+
'<h3>Bang tu khoa</h3>'+
'<p>Diem = do manh tu khoa khi trich xuat; Nguon = cong cu da phat '+
'hien tu khoa; Video kenh chua = so video cua kenh chinh co dung tu '+
'khoa nay.</p>'+
'<input class="search" placeholder="Tim tu khoa..." '+
'onkeyup="filterT(this,\'kwT1\')">'+
'<table class="srt" id="kwT1"><thead><tr><th>Hang</th><th>Tu khoa</th>'+
'<th>Diem</th><th>Video kenh chua</th><th>Nguon</th></tr></thead><tbody>'+
D.keywords.map((k,i)=>`<tr><td class="num">${i+1}</td><td>${k.kw}</td>`+
`<td class="num">${k.score}</td><td class="num">${fmt(k.chv)}</td>`+
`<td>${(k.sources||[]).join(', ')}</td></tr>`).join('')+'</tbody></table>'+
'<h3>Canh tranh & xu huong tung tu khoa</h3>'+
'<p><b>Bid Ads (KT)</b> = bid Google Ads PPC (KHÔNG phản ánh SEO YT). '+
'<b>Cạnh tranh SEO YT</b> = số video kết quả thực tế (chuẩn SEO video). '+
(hasSpark?'Bieu do 12 thang cho thay luot tim qua thoi gian. ':'')+
'Cot goi y tim kiem la cac cum khan gia hay go.</p>'+
'<input class="search" placeholder="Tim tu khoa..." '+
'onkeyup="filterT(this,\'kwT2\')">'+
'<table class="srt" id="kwT2"><thead><tr><th>Tu khoa</th>'+
'<th>Bid Ads (KT)</th><th>Volume tim kiem</th>'+
'<th>Canh tranh SEO YT</th><th>SEO score</th>'+
(hasSpark?'<th>Bieu do 12 thang</th>':'')+
'<th>Goi y tim kiem</th></tr></thead><tbody>'+
D.keywords.map(k=>{
  const cc=(k.kt_comp!=null)?
    '<span class="pill '+(k.kt_comp<0.33?'low':(k.kt_comp<0.66?'medium':'high'))+'">'+
    Math.round(k.kt_comp*100)+'%</span>'
    :'<span class="muted" title="Bank keywordtool chua co tu khoa nay">⏳ Chua harvest</span>';
  const vc=(k.kt_vol!=null)?fmt(k.kt_vol):'<span class="muted" title="Bank keywordtool chua co tu khoa nay">⏳ Chua harvest</span>';
  // Cạnh tranh SEO YT từ result_count YouTube
  let seoComp='<span class="muted">-</span>';
  if(k.rc>0){
    const lv=(k.rc<100000)?'low':(k.rc<1000000)?'medium':'high';
    const lvLabel={low:'Thap',medium:'Trung',high:'Cao'}[lv];
    seoComp='<span class="pill '+lv+'">'+lvLabel+' ('+fmt(k.rc)+')</span>';
  }
  // SEO score = volume / max(rc/10000, 1) — cao = ngon
  let seoScore='-';
  if(k.kt_vol!=null&&k.rc>0){
    const s=Math.round(k.kt_vol/Math.max(k.rc/10000, 1));
    seoScore='<b>'+fmt(s)+'</b>';
  }
  return '<tr><td>'+k.kw+'</td>'+
  '<td>'+cc+'</td>'+
  '<td class="num">'+vc+'</td>'+
  '<td>'+seoComp+'</td>'+
  '<td class="num">'+seoScore+'</td>'+
  (hasSpark?'<td class="spark">'+(k.spark||'-')+'</td>':'')+
  '<td>'+(k.sug||[]).join(', ')+'</td></tr>';
}).join('')+'</tbody></table>';
const TP=D.title_patterns||[];
if(TP.length)s2h+='<h3>📝 Công thức tiêu đề thắng trong ngành</h3>'+
'<p>So sánh lượt xem TRUNG VỊ của video CÓ vs KHÔNG có mỗi đặc điểm '+
'trong tiêu đề ('+fmt(D.title_n||0)+' video toàn ngành). "Hệ số" >1 '+
'nghĩa là đặc điểm đó đi kèm lượt xem cao hơn — nên áp dụng khi đặt '+
'tiêu đề video.</p>'+
'<table class="srt"><thead><tr><th>Đặc điểm tiêu đề</th>'+
'<th>Số video có</th><th>View TV khi CÓ</th><th>khi KHÔNG</th>'+
'<th>Hệ số</th></tr></thead><tbody>'+TP.map(r=>`<tr>
<td>${r.feat}</td><td class="num">${fmt(r.n)}</td>
<td class="num">${fmt(r.med_with)}</td>
<td class="num">${fmt(r.med_without)}</td>
<td class="num">${r.lift>=1.15?'<b>'+r.lift+'</b>':r.lift}</td>
</tr>`).join('')+'</tbody></table>';
document.getElementById('s2').innerHTML=s2h;

// s_kw - Kho tu khoa keywordtool (CHỈ kênh chính có data trong kho)
const KB=D.kw_bank;
if(!KB){
  document.getElementById('s_kw').innerHTML=
  '<h2>📚 Kho từ khoá keywordtool</h2>'+
  '<p class="muted">Kênh này chưa có data trong kho keywordtool '+
  '(chưa harvest seed nào). Daily run kế tiếp sẽ thu hoạch.</p>';
} else {
  const statusTxt=(KB.status==='full')?'✓ Đã đầy 100%':
  'Đang harvest ('+KB.seeds_done+'/'+KB.seeds_total+' seed)';
  let kbh='<h2>📚 Kho từ khoá keywordtool — '+statusTxt+'</h2>'+
  '<p>Tổng <b>'+fmt(KB.kw_total)+'</b> từ khoá ngách, '+
  '<b>'+fmt(KB.kw_golden)+'</b> từ <b>"vàng"</b> '+
  '(volume cao hơn trung vị + cạnh tranh thấp hơn trung vị). '+
  'Số liệu từ keywordtool.io.</p>';
  if(KB.top_golden&&KB.top_golden.length){
    kbh+='<h3>🏆 Top từ khoá VÀNG — cơ hội ăn view cao nhất</h3>'+
    '<input class="search" placeholder="Tìm từ khoá..." '+
    'onkeyup="filterT(this,\'kbgT\')">'+
    '<table class="srt" id="kbgT"><thead><tr><th>Từ khoá</th>'+
    '<th>Cấp</th><th>Volume tìm kiếm</th><th>Bid Ads (KT)</th>'+
    '<th>Điểm cơ hội</th></tr></thead><tbody>'+
    KB.top_golden.map(k=>'<tr>'+
    '<td>'+esc(k.keyword)+'</td>'+
    '<td class="num">'+(k.level||'-')+'</td>'+
    '<td class="num">'+fmt(k.volume)+'</td>'+
    '<td class="num">'+Math.round(k.comp*100)+'%</td>'+
    '<td class="num">'+fmt(Math.round(k.score))+'</td></tr>').join('')+
    '</tbody></table>';
  }
  if(KB.coverage_gap&&KB.coverage_gap.length){
    kbh+='<h3>⚠ Từ khoá VÀNG kênh CHƯA tận dụng</h3>'+
    '<p>Volume cao + cạnh tranh thấp NHƯNG kênh chưa có video về chúng. '+
    'Cơ hội tăng view nhanh nếu làm sớm.</p>'+
    '<table class="srt"><thead><tr><th>Từ khoá</th>'+
    '<th>Volume tìm kiếm</th><th>Bid Ads (KT)</th>'+
    '<th>Điểm cơ hội</th></tr></thead><tbody>'+
    KB.coverage_gap.map(k=>'<tr>'+
    '<td>'+esc(k.keyword)+'</td>'+
    '<td class="num">'+fmt(k.volume)+'</td>'+
    '<td class="num">'+Math.round(k.comp*100)+'%</td>'+
    '<td class="num">'+fmt(Math.round(k.score))+'</td></tr>').join('')+
    '</tbody></table>';
  }
  if(KB.niche_clusters&&KB.niche_clusters.length){
    kbh+='<h3>🎯 Ngách con (gom theo cụm từ gốc 2 chữ đầu)</h3>'+
    '<p class="muted"><b>Số từ khoá</b> = tổng keyword trong kw_bank bắt đầu '+
    'bằng 2 chữ đó (đã harvest từ keywordtool.io). '+
    '<b>Bid Ads TB</b> = TB mức bid Google Ads PPC (KT) trong cụm — '+
    'KHÔNG phản ánh độ khó SEO YouTube.</p>'+
    '<table class="srt"><thead><tr><th>Ngách</th>'+
    '<th>Số từ khoá</th><th>Tổng volume</th>'+
    '<th>Bid Ads TB (KT)</th></tr></thead><tbody>'+
    KB.niche_clusters.map(n=>{
    return '<tr>'+
    '<td><b>'+esc(n.name)+'</b></td>'+
    '<td class="num">'+fmt(n.kw_count)+'</td>'+
    '<td class="num">'+fmt(n.total_volume)+'</td>'+
    '<td class="num">'+Math.round(n.avg_comp*100)+'%</td></tr>';}).join('')+
    '</tbody></table>';
  }
  kbh+='<p class="muted">Phần đánh giá <b>"bộ từ khoá kênh đủ tốt chưa '+
  '+ ngách nên đi tiếp"</b> có trong tab <b>"Chien luoc AI"</b> '+
  '(phần phân tích AI Opus thủ công cho watchlist).</p>';
  document.getElementById('s_kw').innerHTML=kbh;
}

// s_kwh - Lich su kho tu khoa (A43: snapshot + diff theo moi lan chay)
const KH=D.kw_history;
if(!KH||!KH.snapshot_count){
  document.getElementById('s_kwh').innerHTML=
  '<h2>📈 Lịch sử kho từ khoá</h2>'+
  '<p class="muted">Chưa có snapshot lịch sử. Daily run kế tiếp '+
  'sẽ tự lưu snapshot đầu tiên (baseline). Lần sau mới có diff.</p>';
} else {
  const TL=KH.timeline||[];
  const DH=KH.diff_history||[];
  const LD=KH.latest_diff;
  let kwh='<h2>📈 Lịch sử kho từ khoá — '+TL.length+
  ' snapshot trong 30 ngày qua</h2>';
  // Chart timeline
  if(TL.length>=2){
    const maxKw=Math.max.apply(null,TL.map(t=>t.kw_total||0));
    const maxG=Math.max.apply(null,TL.map(t=>t.kw_golden_count||0));
    kwh+='<h3>Xu hướng kho theo lần chạy</h3>'+
    '<table class="srt"><thead><tr><th>Thời điểm</th>'+
    '<th>Tổng từ khoá</th><th>Từ vàng</th>'+
    '<th>Seed harvest</th><th>Trạng thái</th></tr></thead><tbody>'+
    TL.slice().reverse().map(t=>{
      const dt=(t.taken_at||'').replace('T',' ').slice(0,16);
      return '<tr><td>'+esc(dt)+'</td>'+
      '<td class="num">'+fmt(t.kw_total)+'</td>'+
      '<td class="num"><b>'+fmt(t.kw_golden_count)+'</b></td>'+
      '<td class="num">'+(t.seeds_done||0)+'/'+(t.seeds_total||0)+'</td>'+
      '<td>'+esc(t.status||'-')+'</td></tr>';
    }).join('')+'</tbody></table>';
  }
  // Latest diff: NEW + LOST + CHANGED
  if(LD){
    const vs=(LD.vs_taken_at||LD.vs_snapshot_id||'').replace('T',' ').slice(0,16);
    kwh+='<h3>🔄 Thay đổi từ lần chạy trước ('+esc(vs)+')</h3>';
    const NEW=LD.new||[], LOST=LD.lost||[], CHG=LD.changed||[];
    if(NEW.length){
      kwh+='<h4>🆕 Từ vàng MỚI XUẤT HIỆN ('+NEW.length+')</h4>'+
      '<p class="muted">Lần chạy trước chưa có, lần này lọt top vàng. '+
      'Cơ hội ngách mới nổi.</p>'+
      '<table class="srt"><thead><tr><th>Từ khoá</th>'+
      '<th>Volume</th><th>Bid Ads (KT)</th>'+
      '<th>Điểm cơ hội</th></tr></thead><tbody>'+
      NEW.slice(0,30).map(k=>'<tr>'+
      '<td>'+esc(k.keyword)+'</td>'+
      '<td class="num">'+fmt(k.volume)+'</td>'+
      '<td class="num">'+Math.round((k.comp||0)*100)+'%</td>'+
      '<td class="num">'+fmt(Math.round(k.score||0))+'</td></tr>').join('')+
      '</tbody></table>';
    }
    if(LOST.length){
      kwh+='<h4>❌ Từ vàng RỚT KHỎI TOP ('+LOST.length+')</h4>'+
      '<p class="muted">Lần trước nằm trong top vàng, lần này không '+
      'còn (volume giảm, cạnh tranh tăng, hoặc bị từ khác chiếm chỗ).</p>'+
      '<table class="srt"><thead><tr><th>Từ khoá</th>'+
      '<th>Volume cũ</th><th>Bid Ads cũ</th>'+
      '<th>Điểm cũ</th></tr></thead><tbody>'+
      LOST.slice(0,30).map(k=>'<tr>'+
      '<td>'+esc(k.keyword)+'</td>'+
      '<td class="num">'+fmt(k.volume)+'</td>'+
      '<td class="num">'+Math.round((k.comp||0)*100)+'%</td>'+
      '<td class="num">'+fmt(Math.round(k.score||0))+'</td></tr>').join('')+
      '</tbody></table>';
    }
    if(CHG.length){
      kwh+='<h4>📊 Từ vàng ĐỔI MẠNH ('+CHG.length+'+) — Volume Δ≥20% hoặc Bid Δ≥15%</h4>'+
      '<table class="srt"><thead><tr><th>Từ khoá</th>'+
      '<th>Volume cũ → mới</th><th>Δ Volume</th>'+
      '<th>Bid cũ → mới</th></tr></thead><tbody>'+
      CHG.slice(0,30).map(k=>{
        const arrow=k.vol_pct>=0?'↗':'↘';
        const cls=k.vol_pct>=0?'pos':'neg';
        return '<tr>'+
        '<td>'+esc(k.keyword)+'</td>'+
        '<td class="num">'+fmt(k.old_volume)+' → '+fmt(k.new_volume)+'</td>'+
        '<td class="num '+cls+'">'+arrow+' '+k.vol_pct+'%</td>'+
        '<td class="num">'+Math.round((k.old_comp||0)*100)+'% → '+
        Math.round((k.new_comp||0)*100)+'%</td></tr>';
      }).join('')+'</tbody></table>';
    }
    if(!NEW.length&&!LOST.length&&!CHG.length){
      kwh+='<p class="muted">Không có thay đổi đáng kể từ lần chạy trước.</p>';
    }
  } else {
    kwh+='<p class="muted">Snapshot baseline — lần chạy đầu tiên, '+
    'chưa có diff. Lần kế tiếp sẽ có.</p>';
  }
  // Diff history mini-summary
  if(DH.length>=2){
    kwh+='<h3>Lịch sử diff (số từ vàng thay đổi qua các lần chạy)</h3>'+
    '<table class="srt"><thead><tr><th>Thời điểm</th>'+
    '<th>🆕 Mới</th><th>❌ Mất</th>'+
    '<th>📊 Đổi mạnh</th></tr></thead><tbody>'+
    DH.slice().reverse().map(d=>{
      const dt=(d.taken_at||'').replace('T',' ').slice(0,16);
      return '<tr><td>'+esc(dt)+'</td>'+
      '<td class="num">'+(d.new_count||0)+'</td>'+
      '<td class="num">'+(d.lost_count||0)+'</td>'+
      '<td class="num">'+(d.changed_count||0)+'</td></tr>';
    }).join('')+'</tbody></table>';
  }
  document.getElementById('s_kwh').innerHTML=kwh;
}

// s3 - Doi thu
let ch='<h2>Doi thu trong nganh ('+D.competitors.length+' kenh)</h2>'+
'<p>Chon doi thu de xem day du thong so, AI, video, tu khoa:</p>'+
'<select id="csel">'+D.competitors.map((c,i)=>
`<option value="${i}">${c.title}</option>`).join('')+'</select>'+
'<div id="cb"></div>';
if(D.new_comp.length)ch+='<h2>Doi thu moi duoc ket nap ky nay ('+
D.new_comp.length+')</h2><p>Cac kenh nay vua trung noi dung cao voi '+
'kenh chinh nen duoc tu ket nap:</p>'+D.new_comp.map(c=>
'<h3>'+c.title+'</h3>'+(c.ai?'<div class="box">'+
c.ai.replace(/</g,'&lt;')+'</div>':'')).join('');
ch+='<h2>So sanh tang truong toan nganh (Social Blade)</h2>'+
'<table class="srt"><thead><tr><th>#</th><th>Kenh</th>'+
'<th>Nguoi DK</th><th>DK/ngay</th><th>+DK</th><th>+View</th></tr>'+
'</thead><tbody>'+D.sb_compare.map((r,i)=>`<tr>
<td class="num">${i+1}</td>
<td>${r.is_self?'<b>★ '+r.title+'</b>':r.title}</td>
<td class="num">${fmt(r.subs)}</td><td class="num">${sg(r.avg_sub)}</td>
<td class="num">${sg(r.subs_g)}</td><td class="num">${sg(r.views_g)}</td>
</tr>`).join('')+'</tbody></table>'+
'<h2>Bang tong hop tat ca doi thu</h2>'+
'<input class="search" placeholder="Tim kenh..." '+
'onkeyup="filterT(this,\'cT\')">'+
'<table class="srt" id="cT"><thead><tr><th>Kenh</th><th>Nguoi DK</th>'+
'<th>SEO</th><th>+DK (SB)</th><th>+View (SB)</th></tr></thead><tbody>'+
D.competitors.map(c=>c.has?`<tr>
<td>${c.title}${c.auto_added?' <span class="pill high">MOI</span>':''}</td>
<td class="num">${fmt(c.subs)}</td><td class="num">${c.seo}</td>
<td class="num">${sg((c.sb||{}).subs_g||0)}</td>
<td class="num">${sg((c.sb||{}).views_g||0)}</td></tr>`:
`<tr><td>${c.title}</td><td colspan="4" class="muted">Chua co du lieu`+
`</td></tr>`).join('')+'</tbody></table>';
document.getElementById('s3').innerHTML=ch;
function showComp(){const i=+document.getElementById('csel').value;
document.getElementById('cb').innerHTML='<h3>'+
(D.competitors[i].title||'')+'</h3>'+chDetail(D.competitors[i]);
bindSort();}
if(D.competitors.length){document.getElementById('csel').onchange=
showComp;showComp();}

// s4 - Dien bien & Su kien
let dh='<h2>Dien bien xuyen suot</h2>';
const co=D.continuity||{};const dts=co.dates||[];
if(dts.length>=2){dh+='<p>Nguoi dang ky cac kenh qua cac ky giam sat:'+
'</p><table class="srt"><thead><tr><th>Kenh</th>'+
dts.map(d=>'<th>'+d.slice(5)+'</th>').join('')+'</tr></thead><tbody>'+
(co.channels||[]).map(c=>'<tr><td>'+c.title+
(c.is_self?' ★':'')+'</td>'+dts.map(d=>'<td class="num">'+
(c.subs[d]!=null?fmt(c.subs[d]):'-')+'</td>').join('')+'</tr>')
.join('')+'</tbody></table>';
}else dh+='<p class="muted">Can it nhat 2 ky giam sat moi co dien '+
'bien.</p>';
dh+='<h2>Su kien dang chu y</h2>';
if(D.events.length){dh+='<table class="srt"><thead><tr><th>Ngay</th>'+
'<th>Muc do</th><th>Noi dung</th></tr></thead><tbody>'+
D.events.map(e=>`<tr><td>${e.date}</td>
<td>${({high:'Cao',medium:'TB',low:'Thap'})[e.sev]||e.sev}</td>
<td>${e.title}</td></tr>`).join('')+'</tbody></table>';
}else dh+='<p class="muted">Khong co su kien.</p>';
document.getElementById('s4').innerHTML=dh;

// s5 - Chien luoc
document.getElementById('s5').innerHTML='<h2>Chien luoc AI</h2>'+
(D.strategy?'<div class="box">'+D.strategy.replace(/</g,'&lt;')+
'</div>':'<p class="muted">Chua co chien luoc.</p>');

// s6 - Cum chu de (topic clusters)
const TC=D.topic_clusters||[];
let s6h='<h2>📚 Cụm chủ đề trong ngành</h2>'+
'<p class="muted">Gom từ khoá thành cụm chủ đề chính, đo mức độ "ăn '+
'view" của mỗi cụm. Cột "vs kênh chính" cho biết cụm nào kênh chính '+
'đã làm rồi (✓), cụm nào chưa.</p>';
if(TC.length){
  s6h+='<table class="srt"><thead><tr>'+
  '<th>Cụm chủ đề</th><th>Từ khoá liên quan</th>'+
  '<th>Vol cụm (KT)</th><th>Bid Ads TB (KT)</th>'+
  '<th>Số video</th><th>View trung vị</th><th>View cao nhất</th>'+
  '<th>Top video</th><th>vs kênh chính</th></tr></thead><tbody>'+
  TC.map(c=>{
    const kt=clKt(c.keywords||[]);
    const volCell=kt.hits?'<span title="'+kt.hits+' từ có data KT">'+
      fmt(kt.vol)+'</span>':'<span class="muted">-</span>';
    const compCell=(kt.comp!=null)?
      '<span class="pill '+(kt.comp<0.33?'low':(kt.comp<0.66?'medium':'high'))+'">'+
      Math.round(kt.comp*100)+'%</span>':'<span class="muted">-</span>';
    return '<tr><td><b>'+esc(c.cluster)+'</b></td>'+
    '<td><small>'+(c.keywords||[]).map(esc).join(', ')+'</small></td>'+
    '<td class="num">'+volCell+'</td><td>'+compCell+'</td>'+
    '<td class="num">'+fmt(c.n_videos)+'</td>'+
    '<td class="num">'+fmt(c.view_median)+'</td>'+
    '<td class="num">'+fmt(c.view_max)+'</td>'+
    '<td><small>'+esc(c.top_video_title||'').slice(0,60)+'<br>'+
    '<i>('+esc(c.top_video_channel||'')+')</i></small></td>'+
    '<td>'+(c.is_self_active?'✅ Đang làm':'❌ Chưa làm')+'</td></tr>';
  }).join('')+
  '</tbody></table>';
}else{
  s6h+='<p class="muted">Chưa đủ dữ liệu để gom cụm.</p>';
}
document.getElementById('s6').innerHTML=s6h;

// s7 - Khoang trong doi thu (competitive gaps)
const CG=D.competitive_gaps||[];
let s7h='<h2>🎯 Khoảng trống đối thủ — Cơ hội kênh chính có thể chiếm</h2>'+
'<p class="muted">Chủ đề/từ khoá <b>nhiều đối thủ làm</b> mà <b>kênh '+
'chính chưa làm</b>. Sắp xếp theo view video cao nhất của đối thủ — '+
'càng cao = cơ hội càng lớn nếu kênh chính nhảy vào.</p>';
if(CG.length){
  s7h+='<table class="srt"><thead><tr>'+
  '<th>Từ khoá/chủ đề</th>'+
  '<th>Bid Ads (KT)</th><th>Volume (KT)</th><th>Cạnh tranh SEO YT</th>'+
  '<th>Số đối thủ làm</th>'+
  '<th>View trung vị ở đối thủ</th><th>Video top của đối thủ</th>'+
  '<th>View video top</th><th>Kênh đang chiếm</th></tr></thead><tbody>'+
  CG.map(g=>'<tr><td><b>'+esc(g.keyword)+'</b></td>'+
  kteCell(g.keyword)+
  '<td class="num">'+fmt(g.n_competitors)+'/'+(g.sample_competitors||[]).length+'</td>'+
  '<td class="num">'+fmt(g.competitor_video_views_median)+'</td>'+
  '<td><small>'+esc((g.competitor_top_video_title||'').slice(0,70))+'</small></td>'+
  '<td class="num">'+fmt(g.competitor_top_video_views)+'</td>'+
  '<td><small>'+esc(g.competitor_top_channel||'')+'</small></td></tr>').join('')+
  '</tbody></table>';
}else{
  s7h+='<p class="muted">Chưa phát hiện khoảng trống đáng kể '+
  '(kênh chính đã phủ hết chủ đề hot, hoặc cần thêm đối thủ).</p>';
}
document.getElementById('s7').innerHTML=s7h;

// s8 - Tieu de mau (title variants)
const TV=D.title_variants||[];
let s8h='<h2>✏️ Tiêu đề mẫu — Sinh từ công thức thắng</h2>'+
'<p class="muted">Phần mềm tự sinh 16-18 tiêu đề mẫu dựa trên: từ khoá '+
'của kênh + công thức title đang thắng trong ngành. Cột "Điểm" càng '+
'cao = title chứa càng nhiều dấu hiệu thắng (vd "?", emoji, số). '+
'Team có thể copy + chỉnh nhẹ làm video mới.</p>';
if(TV.length){
  s8h+='<table class="srt"><thead><tr>'+
  '<th>Tiêu đề mẫu</th><th>Điểm</th><th>Mẫu gốc</th></tr></thead><tbody>'+
  TV.map(t=>`<tr><td>${esc(t.title)}</td>`+
  `<td class="num">${t.score}</td>`+
  `<td><small class="muted">${esc(t.template||'')}</small></td></tr>`).join('')+
  '</tbody></table>';
}else{
  s8h+='<p class="muted">Chưa đủ dữ liệu để sinh tiêu đề mẫu '+
  '(cần ít nhất 1 vài từ khoá + công thức title).</p>';
}
document.getElementById('s8').innerHTML=s8h;

// s9 - Phan hoi AI (AI feedback loop)
const FB=D.ai_feedback||{detail:[]};
let s9h='<h2>📈 Phản hồi AI — Ý tưởng đề xuất kỳ trước có thành công không?</h2>'+
'<p class="muted">Bảng dưới đối chiếu các ý tưởng AI đã đề xuất ở '+
'các kỳ trước với <b>video kênh chính thật sự đã đăng sau ngày đó</b>. '+
'Phần mềm fuzzy-match tiêu đề (≥30% token trùng = matched). Hiệu suất '+
'= view video matched / view trung vị kênh.</p>';
if(FB.ideas_total>0){
  s9h+='<div class="kv">'+
  `<div><b>Tổng ý tưởng:</b> ${fmt(FB.ideas_total)}</div>`+
  `<div><b>Đã làm:</b> ${fmt(FB.ideas_done)} (${FB.success_rate}%)</div>`+
  `<div><b>Chưa làm:</b> ${fmt(FB.ideas_pending)}</div>`+
  `<div><b>Hiệu suất TB:</b> ${FB.avg_perf_ratio}x view trung vị</div>`+
  '</div>';
  s9h+='<table class="srt"><thead><tr>'+
  '<th>Ý tưởng AI đề xuất</th><th>Kỳ đề xuất</th><th>Trạng thái</th>'+
  '<th>Video đã đăng (matched)</th><th>Ngày đăng</th>'+
  '<th>View</th><th>Hiệu suất</th></tr></thead><tbody>'+
  (FB.detail||[]).map(d=>{
    if(d.status==='done'){
      const r=d.ratio||0;
      const cls=r>=1.5?'pos':(r<0.5?'neg':'');
      return `<tr><td><small>${esc(d.idea)}</small></td>`+
      `<td>${esc(d.date)}</td>`+
      `<td><b style="color:#1a7a1a">✅ Đã làm</b></td>`+
      `<td><small>${esc(d.video||'')}</small></td>`+
      `<td>${esc(d.video_pub||'')}</td>`+
      `<td class="num">${fmt(d.views||0)}</td>`+
      `<td class="num ${cls}">${r}x</td></tr>`;
    } else {
      return `<tr><td><small>${esc(d.idea)}</small></td>`+
      `<td>${esc(d.date)}</td>`+
      `<td><span class="muted">⏳ Chưa làm</span></td>`+
      `<td colspan="4" class="muted">-</td></tr>`;
    }
  }).join('')+'</tbody></table>';
  s9h+='<p class="muted" style="margin-top:12px"><b>Đọc bảng:</b> '+
  '<b style="color:#1a7a1a">≥1.5x</b> = video vượt trung vị nhiều (ý '+
  'tưởng hay); <b style="color:#C8102E">&lt;0.5x</b> = video kém trung '+
  'vị (ý tưởng không hay hoặc thực thi kém). AI sẽ học từ data này.</p>';
}else{
  s9h+='<p class="muted">Chưa đủ dữ liệu phản hồi — cần ít nhất 1-2 '+
  'kỳ phân tích trước + video đăng sau đó để đối chiếu.</p>';
}
document.getElementById('s9').innerHTML=s9h;

// s11 - SEO Best Practice (tab reference TĨNH, không phụ thuộc data)
// Nội dung từ File 3 Chuyên môn SEO A-Z (21/05/2026)
const bp=`<h2>📚 SEO Best Practice — Framework chuẩn</h2>
<p class="muted">Tham chiếu nhanh các framework SEO quan trọng. Trích từ tài liệu "Chuyên môn SEO Cơ bản đến Nâng cao A-Z" (Funtime Media Corp).</p>

<h3>🎯 4 công thức TITLE thắng</h3>
<table class="srt"><thead><tr><th>Công thức</th><th>Mẫu</th><th>Ví dụ</th></tr></thead><tbody>
<tr><td><b>How-to</b></td><td>Cách + [làm gì] + [cho ai/khi nào]</td><td>Cách trồng rau thuỷ canh tại nhà cho người mới (2026)</td></tr>
<tr><td><b>List</b></td><td>[Số] + [danh từ] + [hứa hẹn]</td><td>10 mẹo SEO YouTube giúp video lên top sau 24h</td></tr>
<tr><td><b>Versus</b></td><td>[A] vs [B]: [câu hỏi]</td><td>iPhone 17 vs Samsung S26: cái nào đáng mua 2026?</td></tr>
<tr><td><b>Question</b></td><td>[Câu hỏi gây tò mò]</td><td>Tại sao 90% nhà sáng tạo không bao giờ đạt 10K subs?</td></tr>
</tbody></table>
<p class="muted"><b>Quy tắc:</b> ≤70 ký tự, keyword chính ở 50 ký tự đầu, có yếu tố tò mò/lợi ích/năm, 1-2 emoji.</p>

<h3>🎬 5 công thức HOOK 10 giây đầu</h3>
<table class="srt"><thead><tr><th>Hook</th><th>Cách triển khai</th></tr></thead><tbody>
<tr><td><b>Result First</b></td><td>Show kết quả/end product TRƯỚC, rồi process</td></tr>
<tr><td><b>Problem Punch</b></td><td>Nêu PAIN POINT mạnh ngay đầu</td></tr>
<tr><td><b>Bold Promise</b></td><td>Hứa benefit lớn + thời gian cụ thể ("5 phút nữa bạn sẽ biết...")</td></tr>
<tr><td><b>Curiosity Gap</b></td><td>Nêu fact gây tò mò không trả lời ngay</td></tr>
<tr><td><b>Story Hook</b></td><td>Bắt đầu bằng câu chuyện cá nhân với conflict</td></tr>
</tbody></table>
<p class="muted"><b>Lưu ý:</b> 10 giây đầu quyết định 80% retention. Drop ở 10s = drop khắp video.</p>

<h3>🖼️ 5 LAYOUT Thumbnail phổ biến</h3>
<table class="srt"><thead><tr><th>Layout</th><th>Khi nào dùng</th></tr></thead><tbody>
<tr><td><b>Face + Text</b></td><td>75% face left, text right - tutorial, vlog, reaction</td></tr>
<tr><td><b>Object + Face</b></td><td>50/50 split - review, unboxing</td></tr>
<tr><td><b>Before/After</b></td><td>Split screen - transformation, comparison</td></tr>
<tr><td><b>Versus</b></td><td>A vs B split với chữ VS to giữa</td></tr>
<tr><td><b>Number + Emoji + Object</b></td><td>List video (Top 10...)</td></tr>
</tbody></table>
<p class="muted"><b>Anatomy:</b> Face 30-50% + Object 20-40% + Text 2-5 từ + Color contrast cao. Test ở size nhỏ 200×120px vẫn đọc được.</p>

<h3>📈 8 kỹ thuật tăng RETENTION</h3>
<ol>
<li><b>Hook 10s mạnh</b> — quan trọng nhất, dùng 5 công thức trên</li>
<li><b>Pattern Interrupt</b> mỗi 1-2 phút: zoom, sound, b-roll, jump cut</li>
<li><b>Open Loops</b>: "Tôi sẽ tiết lộ điều này ở cuối video..."</li>
<li><b>Curiosity Gap</b>: hứa hẹn revelation ở phần sau</li>
<li><b>Numbered Lists</b>: "5 mẹo — đặc biệt #4 thay đổi mọi thứ"</li>
<li><b>Visual Variety</b>: đổi shot type, angle, location</li>
<li><b>Stake Escalation</b>: vấn đề càng lúc càng to</li>
<li><b>Strong CTA cuối</b>: kéo session sang video tiếp</li>
</ol>

<h3>📊 7 KPI cốt lõi + Mốc tốt</h3>
<table class="srt"><thead><tr><th>KPI</th><th>Định nghĩa</th><th>Mốc tốt</th></tr></thead><tbody>
<tr><td><b>CTR</b></td><td>% người thấy thumbnail click vào</td><td><b>5-10%</b> (>10% xuất sắc)</td></tr>
<tr><td><b>AVD</b></td><td>TB phút mỗi viewer xem video</td><td>≥4 phút cho video 10p</td></tr>
<tr><td><b>AVP</b></td><td>% TB video xem</td><td>≥40%</td></tr>
<tr><td><b>Like/View</b></td><td>Tỷ lệ like</td><td>3-7%</td></tr>
<tr><td><b>Comment/1K views</b></td><td>Tỷ lệ comment</td><td>0.5-2</td></tr>
<tr><td><b>Session Duration</b></td><td>Thời gian ở YouTube sau video bạn</td><td>≥10 phút</td></tr>
<tr><td><b>Returning Viewers %</b></td><td>% viewer cũ quay lại</td><td>20-40%</td></tr>
</tbody></table>

<h3>⏰ Vòng lặp tối ưu 48-72h sau publish</h3>
<table class="srt"><thead><tr><th>Giờ</th><th>Hành động</th></tr></thead><tbody>
<tr><td><b>0-2</b></td><td>Verify upload, share Community tab, pin top comment, reply 5-10 comment đầu</td></tr>
<tr><td><b>2-24</b></td><td>Realtime monitor, reply mọi comment trong 30 phút, share IG/FB/TikTok, nếu CTR&lt;3% sau 12h → đổi thumbnail</td></tr>
<tr><td><b>24-48</b></td><td>Check CTR + AVD vs benchmark kênh, nếu thấp → đổi thumbnail/title, nếu cao → tăng ads boost</td></tr>
<tr><td><b>48-72</b></td><td>Đánh giá hit/miss/acceptable, nếu hit → lên variant, nếu miss → ghi nhận lesson learned</td></tr>
</tbody></table>

<h3>🩺 Bảng chẩn đoán triệu chứng → sửa</h3>
<table class="srt"><thead><tr><th>Triệu chứng</th><th>Nguyên nhân</th><th>Sửa</th></tr></thead><tbody>
<tr><td><b>CTR &lt; 3%</b></td><td>Thumbnail/Title yếu</td><td>Redesign thumbnail có face + contrast cao + đổi title thêm benefit/curiosity</td></tr>
<tr><td><b>AVP &lt; 30%</b></td><td>Hook yếu / clickbait</td><td>Quay lại hook 10s + đảm bảo title-thumbnail match nội dung</td></tr>
<tr><td><b>Retention drop 50-70%</b></td><td>Mid-video không giữ</td><td>Boost moment ở giữa: revelation/story/visual change</td></tr>
<tr><td><b>CTR cao + AVP thấp</b></td><td>Click bait</td><td>Title/thumbnail match nội dung hơn</td></tr>
<tr><td><b>CTR thấp + AVP cao</b></td><td>Title/thumbnail yếu nhưng content tốt</td><td>Đổi title/thumbnail — content giữ nguyên</td></tr>
<tr><td><b>Subs đứng yên 3+ kỳ</b></td><td>Sai pillar / quality giảm</td><td>Audit 10 video gần nhất retention curve, quay lại pillar gốc</td></tr>
<tr><td><b>Views/15d giảm âm</b></td><td>Video bị ẩn/xoá</td><td>Kiểm tra YouTube Studio - khôi phục video nếu có</td></tr>
</tbody></table>

<h3>📋 Checklist 25 items pre-publish (rút gọn từ 60 items đầy đủ)</h3>
<ul>
<li>□ Title ≤70 ký tự, có keyword chính trong 50 ký tự đầu?</li>
<li>□ Title KHÔNG clickbait sai sự thật?</li>
<li>□ Description đoạn 1: tóm tắt 2-3 dòng có keyword?</li>
<li>□ Description có chapters (timestamps)?</li>
<li>□ Description có 3-5 link related?</li>
<li>□ Description có 3-5 hashtag cuối?</li>
<li>□ Tags 5-15, tag đầu = keyword chính?</li>
<li>□ Thumbnail 1280×720px, có face/object rõ?</li>
<li>□ Thumbnail text ≤5 từ, đọc được ở mobile?</li>
<li>□ Thumbnail consistent với brand pattern?</li>
<li>□ Captions/Subtitles ngôn ngữ chính đã upload?</li>
<li>□ End Screen 4 elements (video + playlist + subscribe)?</li>
<li>□ Cards (max 5) đặt đúng moment?</li>
<li>□ Pinned comment chuẩn bị sẵn?</li>
<li>□ Made for Kids: đã quyết định Yes/No đúng?</li>
<li>□ Altered content: tick nếu dùng AI synthetic người thật?</li>
<li>□ Hook 10s đầu MẠNH (1 trong 5 công thức)?</li>
<li>□ Video length phù hợp ngách?</li>
<li>□ Audio voice -16 LUFS, music -25 dB, không echo?</li>
<li>□ Video 1080p hoặc 4K, bitrate đủ (8-12 Mbps)?</li>
<li>□ Pattern interrupt mỗi 1-2 phút?</li>
<li>□ CTA mid-video (Subscribe + Share)?</li>
<li>□ Schedule publish đúng giờ peak audience?</li>
<li>□ Add to playlist phù hợp?</li>
<li>□ Sẵn sàng phản hồi comment 24h đầu?</li>
</ul>

<h3>🔄 Repurpose Content — 1 video → 4-10 assets</h3>
<table class="srt"><thead><tr><th>Source</th><th>Output</th></tr></thead><tbody>
<tr><td>Video 15 phút</td><td>→ 3-5 Shorts (highlight)</td></tr>
<tr><td>Video tutorial</td><td>→ Blog post + Pinterest pin + IG carousel</td></tr>
<tr><td>Live 2 tiếng</td><td>→ Highlight 10p + 5-10 Shorts + Podcast audio</td></tr>
<tr><td>Interview</td><td>→ Quote graphic + Article + Newsletter</td></tr>
</tbody></table>

<h3>🤖 AI Prompt templates dùng hàng ngày</h3>
<p><b>Brainstorm tiêu đề:</b></p>
<div class="box"><i>"Tôi đang làm video về [TOPIC] cho ngách [NICHE], audience [PERSONA]. Brainstorm 10 tiêu đề ≤70 ký tự theo 5 công thức (How-to, List, Versus, Question, Story). Mỗi tiêu đề kèm CTR prediction high/medium/low + 1 câu giải thích."</i></div>
<p><b>Viết description:</b></p>
<div class="box"><i>"Viết YouTube description 250-300 từ cho video tiêu đề '[TITLE]' về [TOPIC]. Format: đoạn 1 (2-3 dòng tóm tắt + keyword), đoạn 2 (timestamps), đoạn 3 (5 link + 5 social + 3 hashtag). Keyword chính: [KEYWORD]."</i></div>
<p><b>Phân tích retention:</b></p>
<div class="box"><i>"Tôi có retention curve: [paste numbers]. Phân tích đâu là điểm drop &gt; 5%, đoạn nào spike up, đề xuất 3 hành động cụ thể cho video tiếp theo."</i></div>

<p class="muted" style="margin-top:24px"><b>📖 Đọc đầy đủ:</b> "Chuyên môn SEO Cơ bản đến Nâng cao A-Z.docx" (10.781 từ, 37 bảng) tại folder đào tạo công ty. Phụ lục A có checklist 60 items đầy đủ. Phụ lục B có Career path SEO Junior → Senior.</p>`;
document.getElementById('s11').innerHTML=bp;

// ============================================================
// WAVE 1 (chốt 23/05): Title Pattern + AB Rescue + Thumb Vision
// ============================================================

// === Title Pattern → APPEND vào tab s2 (Tu khoa) ===
// Đổi tên TPK để tránh conflict với TP (title_patterns ngành ở line 1304)
const TPK=D.title_pattern;
if(TPK && !TPK.error){
  let tph='<h3 style="margin-top:32px;border-top:2px solid #e0e0e0;padding-top:16px">📝 Công thức tiêu đề (data-driven từ '+TPK.n_videos+' video)</h3>';
  if((TPK.recommendations||[]).length){
    tph+='<div class="box" style="background:#f0f7ff;padding:12px 16px;border-left:4px solid #1976d2"><b>💡 Khuyến nghị từ data:</b><ul>'
      +TPK.recommendations.map(r=>'<li>'+r+'</li>').join('')+'</ul></div>';
  }
  const fc=TPK.feature_correlation||{};
  const featLabel={has_emoji:'Có emoji',has_number:'Có số',has_question:'Câu hỏi (?)',has_exclamation:'Chấm than (!)',has_uppercase:'In HOA 1 từ',starts_with_number:'Bắt đầu bằng số'};
  tph+='<p style="margin-top:16px"><b>Tương quan feature × views/ngày:</b></p>'
    +'<table class="js-table"><thead><tr><th class="js-sortable">Feature</th><th class="js-sortable">N có</th><th class="js-sortable">View TB CÓ</th><th class="js-sortable">View TB KHÔNG</th><th class="js-sortable">Lift %</th></tr></thead><tbody>';
  for(const k in fc){
    const v=fc[k];
    const lift=v.lift_pct;
    const liftStr=lift>=0?'+'+lift+'%':lift+'%';
    const color=lift>=20?'#1a7a1a':(lift<=-10?'#C8102E':'#666');
    tph+='<tr><td>'+(featLabel[k]||k)+'</td><td class="num">'+v.n_on+'</td><td class="num">'+fmt(v.on_avg)+'</td><td class="num">'+fmt(v.off_avg)+'</td><td class="num" style="color:'+color+';font-weight:bold">'+liftStr+'</td></tr>';
  }
  tph+='</tbody></table>';
  const ls=TPK.length_stats||{};
  tph+='<p style="margin-top:16px"><b>Độ dài tiêu đề × views/ngày:</b></p>'
    +'<table><thead><tr><th>Bucket</th><th>N</th><th>View/ngày TB</th></tr></thead><tbody>';
  for(const b in ls){
    tph+='<tr><td>'+b+'</td><td class="num">'+ls[b].n+'</td><td class="num">'+fmt(ls[b].avg_views_per_day)+'</td></tr>';
  }
  tph+='</tbody></table>';
  if((TPK.winning_ngrams||[]).length){
    tph+='<p style="margin-top:16px"><b>🏆 Cụm từ "công thức thắng" (xuất hiện top, ít ở bottom):</b></p><ul>';
    tph+=TPK.winning_ngrams.slice(0,10).map(n=>'<li><code>'+n.ngram+'</code> — top '+n.top_cnt+' / bot '+n.bot_cnt+'</li>').join('');
    tph+='</ul>';
  }
  if((TPK.losing_ngrams||[]).length){
    tph+='<p style="margin-top:16px;color:#666"><b>⚠ Cụm từ "công thức thua" (cẩn thận):</b></p><ul>';
    tph+=TPK.losing_ngrams.slice(0,7).map(n=>'<li><code>'+n.ngram+'</code> — bot '+n.bot_cnt+' / top '+n.top_cnt+'</li>').join('');
    tph+='</ul>';
  }
  document.getElementById('s2').insertAdjacentHTML('beforeend',tph);
}

// === s19: AB Recommender — Cứu video flop ===
const AB=D.ab_rescue||[];
let abh='<h2>💡 Cứu video flop — gợi ý từ đối thủ</h2>';
if(AB.length===0){
  abh+='<p class="muted">✅ Tốt — không phát hiện video flop nào cần cứu trong kỳ này (hoặc đối thủ chưa có winner cùng tag để so).</p>';
}else{
  abh+='<p class="muted">Phát hiện <b>'+AB.length+'</b> video kênh chính có view/ngày dưới 30% median + có đối thủ cùng tag đạt view cao hơn ≥5 lần. Đề xuất tái upload với công thức đối thủ.</p>';
  AB.forEach((rec,i)=>{
    const sv=rec.self_video;
    const best=rec.competitor_matches[0];
    abh+='<div class="box" style="margin:14px 0;border-left:4px solid #cc7a00;padding:12px 16px;background:#fffbf0">';
    abh+='<p style="margin:0"><b>'+(i+1)+'. Video flop của bạn:</b> <a href="https://youtube.com/watch?v='+sv.video_id+'" target="_blank">'+sv.title.substring(0,80)+'</a></p>';
    abh+='<p style="margin:4px 0 0;color:#666">'+fmt(sv.view_count)+' views • '+fmt(sv.vpd)+' view/ngày • '+Math.round(sv.duration/60)+' phút</p>';
    abh+='<p style="margin:8px 0 0"><b style="color:#1a7a1a">🏆 Đối thủ winner cùng topic (lift '+best.lift_potential+'x):</b></p>';
    rec.competitor_matches.slice(0,3).forEach(m=>{
      abh+='<p style="margin:4px 0 0;padding-left:12px">• <a href="https://youtube.com/watch?v='+m.comp_video.video_id+'" target="_blank">'+m.comp_video.title.substring(0,75)+'</a> — '+m.comp_channel+' — <b>'+fmt(m.comp_video.vpd)+' v/d</b> ('+m.lift_potential+'x lift, '+m.n_overlap+' tag chung)</p>';
    });
    abh+='<p style="margin:8px 0 0;background:#e8f5e8;padding:8px 12px;border-radius:4px"><b>💡 Hành động:</b> '+rec.suggested_action+'</p>';
    abh+='</div>';
  });
}
document.getElementById('s19').innerHTML=abh;

// === s20: AI Vision Thumbnail (rename TV → TVN tránh conflict với line 1511) ===
const TVN=D.thumb_vision_summary;
const TVND=D.thumb_vision_detail||{};
let tvh='<h2>🤖 AI Vision phân tích thumbnail (Claude)</h2>';
if(!TVN){
  tvh+='<p class="muted">ℹ️ Tính năng AI Vision tuỳ chọn — kích hoạt bằng: <code>python tools/run_vision.py</code> (chi phí ~$0.75/kỳ daily run, phân tích click_score 1-10 cho top thumbnail bằng Claude Vision).</p>';
}else if(TVN.error){
  tvh+='<p class="muted">Lỗi: '+TVN.error+'</p>';
}else{
  tvh+='<div class="kv" style="margin-bottom:16px">';
  tvh+='<div><div class="label">Click score TB</div><div class="val">'+TVN.avg_click_score+'/10</div></div>';
  tvh+='<div><div class="label">Số thumbnail phân tích</div><div class="val">'+TVN.n+'</div></div>';
  tvh+='<div><div class="label">% có face</div><div class="val">'+TVN.pct_with_face+'%</div></div>';
  tvh+='<div><div class="label">% có text overlay</div><div class="val">'+TVN.pct_with_text+'%</div></div>';
  tvh+='<div><div class="label">Emotion chủ đạo</div><div class="val">'+TVN.top_emotion+'</div></div>';
  tvh+='<div><div class="label">Subject chủ đạo</div><div class="val">'+TVN.top_subject+'</div></div>';
  tvh+='<div><div class="label">Color scheme</div><div class="val">'+TVN.top_color_scheme+'</div></div>';
  tvh+='</div>';
  if((TVN.common_strengths||[]).length){
    tvh+='<div class="box" style="background:#e8f5e8;padding:10px 14px;border-left:3px solid #1a7a1a;margin-bottom:12px"><b>✓ Điểm mạnh chung:</b><ul style="margin:6px 0">'
      +TVN.common_strengths.map(s=>'<li>'+s+'</li>').join('')+'</ul></div>';
  }
  if((TVN.common_weaknesses||[]).length){
    tvh+='<div class="box" style="background:#fff4e0;padding:10px 14px;border-left:3px solid #cc7a00;margin-bottom:12px"><b>⚠ Điểm yếu chung:</b><ul style="margin:6px 0">'
      +TVN.common_weaknesses.map(s=>'<li>'+s+'</li>').join('')+'</ul></div>';
  }
  if((TVN.sample_improvements||[]).length){
    tvh+='<div class="box" style="background:#f0f7ff;padding:10px 14px;border-left:3px solid #1976d2;margin-bottom:12px"><b>💡 Đề xuất cải thiện (mẫu):</b><ul style="margin:6px 0">'
      +TVN.sample_improvements.map(s=>'<li>'+s+'</li>').join('')+'</ul></div>';
  }
  const detKeys=Object.keys(TVND);
  if(detKeys.length){
    tvh+='<h3 style="margin-top:24px">Chi tiết từng thumbnail</h3>';
    tvh+='<table class="js-table"><thead><tr><th class="js-sortable">Video ID</th><th class="js-sortable">Score</th><th class="js-sortable">Subject</th><th class="js-sortable">Emotion</th><th class="js-sortable">Color</th><th>Đề xuất</th></tr></thead><tbody>';
    detKeys.forEach(vid=>{
      const d=TVND[vid];
      if(d.error){tvh+='<tr><td>'+vid+'</td><td colspan="5" style="color:#999">'+d.error+'</td></tr>';return;}
      const score=d.click_score||0;
      const color=score>=8?'#1a7a1a':(score>=5?'#cc7a00':'#C8102E');
      tvh+='<tr><td><a href="https://youtu.be/'+vid+'" target="_blank">'+vid+'</a></td>'
        +'<td class="num" style="color:'+color+';font-weight:bold">'+score+'/10</td>'
        +'<td>'+(d.subject||'?')+'</td>'
        +'<td>'+(d.emotion||'?')+'</td>'
        +'<td>'+(d.color_scheme||'?')+'</td>'
        +'<td style="font-size:0.85em">'+(d.improvement||'').substring(0,120)+'</td></tr>';
    });
    tvh+='</tbody></table>';
  }
}
document.getElementById('s20').innerHTML=tvh;

// === s21: Comment Intelligence — Audience insight ===
const CI=D.comment_intel;
let cih='<h2>💬 Audience insight — phân tích bình luận khán giả</h2>';
if(!CI){
  cih+='<p class="muted">ℹ️ Tính năng phân tích bình luận tuỳ chọn — kích hoạt: <code>python tools/run_comment_intel.py</code> (cần Anthropic API key, ~$5/kỳ cho 25 WL).</p>';
}else if(CI.error){
  cih+='<p class="muted">Lỗi: '+CI.error+'</p>';
}else{
  cih+='<div class="kv" style="margin-bottom:16px">';
  cih+='<div><div class="label">Comment phân tích</div><div class="val">'+(CI._n_comments_analyzed||0)+'</div></div>';
  cih+='<div><div class="label">Sentiment chung</div><div class="val">'+(CI.sentiment_overall||'?')+'</div></div>';
  cih+='<div><div class="label">Audience hint</div><div class="val">'+(CI.audience_demographic_hint||'?').substring(0,80)+'</div></div>';
  cih+='</div>';
  // Sentiment breakdown
  const sp=CI.sentiment_pct||{};
  if(sp.positive!==undefined){
    cih+='<p><b>Tỷ lệ sentiment:</b> '
      +'<span style="color:#1a7a1a">Tích cực '+sp.positive+'%</span> · '
      +'<span style="color:#666">Trung lập '+(sp.neutral||0)+'%</span> · '
      +'<span style="color:#C8102E">Tiêu cực '+(sp.negative||0)+'%</span></p>';
  }
  // Pain points
  if((CI.pain_points||[]).length){
    cih+='<h3 style="margin-top:20px">😟 Pain points (vấn đề khán giả nêu)</h3>';
    CI.pain_points.forEach(p=>{
      cih+='<div class="box" style="margin:8px 0;padding:10px 14px;background:#fff4f0;border-left:3px solid #C8102E"><b>'+p.theme+'</b> (mention '+p.n_mentions+'x)';
      if((p.example_quotes||[]).length){
        cih+='<ul style="margin:6px 0">'+p.example_quotes.slice(0,2).map(q=>'<li><i>"'+q.substring(0,150)+'"</i></li>').join('')+'</ul>';
      }
      cih+='</div>';
    });
  }
  // Video requests
  if((CI.video_requests||[]).length){
    cih+='<h3 style="margin-top:20px">📝 Yêu cầu video từ khán giả</h3><ul>';
    CI.video_requests.forEach(r=>{
      cih+='<li><b>'+r.topic+'</b> ('+r.n_mentions+' mention)';
      if(r.example) cih+=' — <i>"'+r.example.substring(0,150)+'"</i>';
      cih+='</li>';
    });
    cih+='</ul>';
  }
  // Praise themes
  if((CI.praise_themes||[]).length){
    cih+='<h3 style="margin-top:20px">⭐ Khán giả thích nhất</h3><ul>';
    CI.praise_themes.forEach(p=>{
      cih+='<li><b>'+p.theme+'</b> ('+p.n_mentions+'x)</li>';
    });
    cih+='</ul>';
  }
  // Video ideas
  if((CI.video_ideas||[]).length){
    cih+='<div class="box" style="margin-top:20px;background:#f0f7ff;padding:12px 16px;border-left:4px solid #1976d2"><b>💡 Ý tưởng video từ audience demand:</b><ol>';
    cih+=CI.video_ideas.map(i=>'<li>'+i+'</li>').join('');
    cih+='</ol></div>';
  }
  if((CI.red_flags||[]).length){
    cih+='<div class="box" style="margin-top:14px;background:#ffe8e8;padding:10px 14px;border-left:3px solid #C8102E"><b>🚩 Cảnh báo:</b><ul style="margin:6px 0">'
      +CI.red_flags.map(r=>'<li>'+r+'</li>').join('')+'</ul></div>';
  }
}
document.getElementById('s21').innerHTML=cih;

// === s22: Viral Predictor + Posting Time V2 + Hook Timing ===
let vph='<h2>🔮 Dự đoán viral + ⏰ Giờ post tối ưu</h2>';
// --- Viral Predictor ---
const VP=D.viral_predictor;
vph+='<h3>🔮 Dự đoán views/ngày (theo title + features)</h3>';
if(!VP || VP.error){
  vph+='<p class="muted">ℹ️ Predictor cần lịch sử ≥50 video. Trạng thái: '+(VP&&VP.error?VP.error:'chưa train')+'</p>';
}else{
  vph+='<p class="muted">Model R²='+VP.model_r_squared+' (train từ '+VP.model_n_samples+' video lịch sử). Predict cho top 5 video gần đây của kênh chính:</p>';
  vph+='<table class="js-table"><thead><tr><th>Video</th><th class="js-sortable">Predicted v/d</th><th class="js-sortable">Actual v/d</th><th class="js-sortable">Rank</th><th>Advice</th></tr></thead><tbody>';
  (VP.predictions||[]).forEach(p=>{
    const rankColor=p.percentile_rank>=75?'#1a7a1a':(p.percentile_rank>=50?'#cc7a00':'#C8102E');
    vph+='<tr><td><a href="https://youtu.be/'+p.video_id+'" target="_blank">'+p.title.substring(0,60)+'</a></td>'
      +'<td class="num">'+fmt(p.predicted_vpd)+'</td>'
      +'<td class="num">'+fmt(p.actual_vpd)+'</td>'
      +'<td class="num" style="color:'+rankColor+';font-weight:bold">p'+p.percentile_rank+'</td>'
      +'<td style="font-size:0.85em">'+(p.advice||[]).join('<br>')+'</td></tr>';
  });
  vph+='</tbody></table>';
}
// --- Posting Time V2 ---
const PT=D.posting_v2;
vph+='<h3 style="margin-top:24px">⏰ Giờ post tối ưu (theo audience timezone)</h3>';
if(!PT || PT.error){
  vph+='<p class="muted">ℹ️ Cần Inside data với demographic breakdown. Trạng thái: '+(PT&&PT.error?PT.error:'chưa có')+'</p>';
}else{
  vph+='<p><b>Audience breakdown:</b> '+(PT.audience_breakdown||[]).join(' · ')+'</p>';
  if((PT.best_slots_local||[]).length){
    vph+='<p><b>Top 6 giờ post (giờ VN máy đăng):</b></p><table><thead><tr><th>Giờ VN</th><th>Score</th></tr></thead><tbody>';
    PT.best_slots_local.forEach(s=>{
      vph+='<tr><td>'+String(s.local_hour).padStart(2,"0")+':00</td><td class="num">'+s.score+'</td></tr>';
    });
    vph+='</tbody></table>';
  }
  if((PT.advice||[]).length){
    vph+='<div class="box" style="background:#f0f7ff;padding:10px 14px;border-left:3px solid #1976d2"><ul style="margin:0">'
      +PT.advice.map(a=>'<li>'+a+'</li>').join('')+'</ul></div>';
  }
}
// --- Hook Timing ---
const HK=D.hook_timing;
vph+='<h3 style="margin-top:24px">⏱ Hook timing (15s đầu video)</h3>';
if(!HK || HK.error){
  vph+='<p class="muted">ℹ️ Cần retention curve từ Inside data. Trạng thái: '+(HK&&HK.error?HK.error:'chưa có')+'</p>';
}else{
  vph+='<div class="kv" style="margin-bottom:12px">';
  vph+='<div><div class="label">Video hook MẠNH (>85%)</div><div class="val" style="color:#1a7a1a">'+HK.n_strong+'/'+HK.n_videos+'</div></div>';
  vph+='<div><div class="label">Video hook OK (65-85%)</div><div class="val">'+HK.n_ok+'/'+HK.n_videos+'</div></div>';
  vph+='<div><div class="label">Video hook YẾU (<65%)</div><div class="val" style="color:#C8102E">'+HK.n_weak+'/'+HK.n_videos+'</div></div>';
  vph+='</div>';
  if((HK.recommendations||[]).length){
    vph+='<div class="box" style="background:#fff4e0;padding:10px 14px;border-left:3px solid #cc7a00"><ul style="margin:0">'
      +HK.recommendations.map(r=>'<li>'+r+'</li>').join('')+'</ul></div>';
  }
  if((HK.top_hook_videos||[]).length){
    vph+='<p style="margin-top:14px"><b>🏆 Top 5 hook tốt nhất:</b></p><ol>';
    HK.top_hook_videos.forEach(v=>{
      vph+='<li><a href="https://youtu.be/'+v.video_id+'" target="_blank">'+v.title.substring(0,70)+'</a> — hook '+v.hook_retention+'% ('+fmt(v.views)+' views)</li>';
    });
    vph+='</ol>';
  }
  if((HK.worst_hook_videos||[]).length){
    vph+='<p style="margin-top:14px"><b>⚠ 5 video hook yếu nhất:</b></p><ol>';
    HK.worst_hook_videos.forEach(v=>{
      vph+='<li><a href="https://youtu.be/'+v.video_id+'" target="_blank">'+v.title.substring(0,70)+'</a> — hook '+v.hook_retention+'% ('+fmt(v.views)+' views) — weakest: '+v.weakest_segment+'</li>';
    });
    vph+='</ol>';
  }
}
document.getElementById('s22').innerHTML=vph;

// s12 - Health Check FULL (channel audit + keyword alignment + video audit + actions)
const sevC={good:'#1a7a1a',warn:'#cc7a00',bad:'#C8102E'};
const sevBg2={good:'#e8f5e8',warn:'#fff4e0',bad:'#ffe8e8'};
const prioC={high:'#C8102E',medium:'#cc7a00',low:'#666'};
let hh='<h2>🩺 Health Check kênh chính — Audit toàn diện</h2>'+
'<p class="muted">Áp dụng framework từ "Chuyên môn SEO A-Z" — '+
'kiểm tra Channel/Video/Keyword + đề xuất hành động cụ thể. '+
'Ngách detect: <b>'+(D.niche_detected||'generic')+'</b></p>';

// === A. CHANNEL-LEVEL AUDIT ===
if(D.health_channel&&D.health_channel.score!==undefined){
  const hc=D.health_channel;
  hh+='<h3>A. Audit cấp KÊNH ('+hc.passed_count+'/'+hc.total_checks+' pass)</h3>'+
  '<div style="display:flex;gap:12px;align-items:center;margin:8px 0">'+
  '<div style="font-size:32px;font-weight:bold;color:'+sevC[hc.severity]+'">'+
  hc.score+'/100</div>'+
  '<div style="font-size:16px;font-weight:bold;color:'+sevC[hc.severity]+'">'+
  hc.severity_label+'</div></div>'+
  '<table class="srt"><thead><tr><th>Trạng thái</th><th>Tiêu chí</th>'+
  '<th>Chi tiết</th><th>Trọng số</th></tr></thead><tbody>';
  (hc.pass_items||[]).forEach(it=>{hh+='<tr style="background:'+sevBg2.good+'">'+
    '<td>✅</td><td><b>'+esc(it.label)+'</b></td>'+
    '<td>'+esc(it.detail)+'</td><td class="num">'+it.weight+'</td></tr>';});
  (hc.fail_items||[]).forEach(it=>{hh+='<tr style="background:'+sevBg2.bad+'">'+
    '<td>❌</td><td><b>'+esc(it.label)+'</b></td>'+
    '<td>'+esc(it.detail)+'</td><td class="num">'+it.weight+'</td></tr>';});
  hh+='</tbody></table>';
}

// === B. KEYWORD ALIGNMENT ===
if(D.health_keywords&&D.health_keywords.self_keywords){
  const kw=D.health_keywords;
  hh+='<h3>B. Chiến lược từ khoá — Đồng bộ kênh vs ngách</h3>'+
  '<p><b>Theme consistency:</b> <span style="font-size:18px;font-weight:bold;color:'+
  (kw.theme_consistency>=70?sevC.good:kw.theme_consistency>=50?sevC.warn:sevC.bad)+
  '">'+kw.theme_consistency+'%</span> '+
  '<span class="muted">(% video có top 3 keyword chính trong tiêu đề — '+
  'mục tiêu ≥70%)</span></p>';
  // Top keyword kênh
  hh+='<h4>Top 10 keyword của kênh + đồng bộ</h4>'+
  '<p class="muted"><b>Bid Ads (KT)</b> = mức bid Google Ads PPC (không phản ánh '+
  'SEO YouTube). <b>Cạnh tranh SEO YT</b> = số kết quả video YT cho từ khoá '+
  '(&lt;100K=Thấp, 100K-1M=Trung, &gt;1M=Cao) — chuẩn cho SEO video.</p>'+
  '<table class="srt"><thead><tr><th>Từ khoá</th><th>SEO Score</th>'+
  '<th>Trong About?</th><th>% Video dùng</th>'+
  '<th>Bid Ads (KT)</th><th>Volume (KT)</th><th>Cạnh tranh SEO YT</th>'+
  '</tr></thead><tbody>';
  (kw.self_keywords||[]).slice(0,10).forEach(k=>{
    hh+='<tr><td><b>'+esc(k.kw)+'</b></td>'+
    '<td class="num">'+k.score.toFixed(1)+'</td>'+
    '<td>'+(k.in_about?'<span style="color:'+sevC.good+'">✅ Có</span>':
            '<span style="color:'+sevC.bad+'">❌ Không</span>')+'</td>'+
    '<td class="num">'+k.in_video_pct+'%</td>'+
    kteCell(k.kw)+'</tr>';
  });
  hh+='</tbody></table>';
  // Top keyword ngách
  if((kw.niche_keywords||[]).length){
    hh+='<h4>Top 10 keyword của NGÁCH (từ đối thủ)</h4>'+
    '<p class="muted">Cột <b>Cạnh tranh SEO YT</b> chỉ có data cho từ '+
    'khoá thuộc tag_metrics kênh chính (top ~30 kw). Từ khoá ngách đối thủ '+
    'phổ biến chưa có rc → hiển thị "-".</p>'+
    '<table class="srt"><thead><tr><th>Từ khoá ngách</th>'+
    '<th>Freq (số đối thủ dùng)</th><th>Kênh đang dùng?</th>'+
    '<th>Bid Ads (KT)</th><th>Volume (KT)</th><th>Cạnh tranh SEO YT</th>'+
    '</tr></thead><tbody>';
    kw.niche_keywords.slice(0,10).forEach(n=>{
      hh+='<tr style="background:'+(n.in_self?sevBg2.good:sevBg2.warn)+'">'+
      '<td><b>'+esc(n.kw)+'</b></td>'+
      '<td class="num">'+n.freq_in_niche+'</td>'+
      '<td>'+(n.in_self?'<span style="color:'+sevC.good+
        '">✅ Có</span>':'<span style="color:'+sevC.warn+
        '">⚠ Chưa dùng (GAP)</span>')+'</td>'+
      kteCell(n.kw)+'</tr>';
    });
    hh+='</tbody></table>';
  }
  // GAPS
  if((kw.gaps||[]).length){
    hh+='<h4 style="color:'+sevC.bad+'">🎯 GAP — Keyword ngách MẠNH mà kênh CHƯA dùng</h4>'+
    '<p>Đây là CƠ HỘI lớn — đối thủ ăn view với những keyword này nhưng '+
    'kênh chính chưa khai thác. Đề xuất làm 2-3 video cho mỗi keyword:</p>'+
    '<ul>';
    kw.gaps.forEach(g=>{hh+='<li><b>'+esc(g)+'</b></li>';});
    hh+='</ul>';
  }
  // OVERUSED
  if((kw.overused||[]).length){
    hh+='<h4 style="color:'+sevC.warn+'">⚠ Keyword kênh KHÔNG match ngách</h4>'+
    '<p>Kênh đang dùng nhưng KHÔNG nằm trong top keyword ngách. Hoặc đi trước '+
    'ngách (cơ hội), hoặc lệch ngách (rủi ro) — cần audit:</p><ul>';
    kw.overused.forEach(o=>{hh+='<li><b>'+esc(o)+'</b></li>';});
    hh+='</ul>';
  }
  // Actions từ keyword
  if((kw.actions||[]).length){
    hh+='<h4>Action từ phân tích từ khoá</h4>';
    kw.actions.forEach(a=>{
      const c=sevC[a.severity==='good'?'good':a.severity==='high'?'bad':'warn'];
      hh+='<div style="border-left:4px solid '+c+';padding:8px 12px;margin:6px 0;background:#fafafa">'+
      '<b style="color:'+c+'">['+a.severity.toUpperCase()+'] '+esc(a.title)+'</b><br>'+
      '<span style="font-size:13px">'+esc(a.detail)+'</span></div>';
    });
  }
}

// === C. VIDEO-LEVEL AUDIT ===
if(D.health&&D.health.length){
  const avg=Math.round(D.health.reduce((s,v)=>s+v.score,0)/D.health.length);
  const goodN=D.health.filter(v=>v.severity=='good').length;
  const warnN=D.health.filter(v=>v.severity=='warn').length;
  const badN=D.health.filter(v=>v.severity=='bad').length;
  hh+='<h3>C. Audit 10 video gần nhất (19 tiêu chí mỗi video)</h3>'+
  '<p><b>Điểm TB: '+avg+'/100</b> &nbsp;•&nbsp; '+
  '<span style="color:'+sevC.good+'">●</span> TỐT: '+goodN+' &nbsp;•&nbsp; '+
  '<span style="color:'+sevC.warn+'">●</span> CẦN CẢI THIỆN: '+warnN+
  ' &nbsp;•&nbsp; <span style="color:'+sevC.bad+'">●</span> YẾU: '+badN+'</p>'+
  '<table class="srt"><thead><tr>'+
  '<th>Score</th><th>Tiêu đề</th><th>Ngày</th><th>Độ dài</th><th>Views</th>'+
  '<th>Lỗi cần sửa (top 3)</th></tr></thead><tbody>';
  D.health.forEach(v=>{
    const top3=(v.fail_items||[]).sort((a,b)=>b.weight-a.weight).slice(0,3)
      .map(f=>'<div style="font-size:12px;line-height:1.4">'+
      '<b>×</b> '+esc(f.label)+': <i>'+esc(f.detail)+'</i></div>').join('');
    hh+='<tr style="background:'+sevBg2[v.severity]+'">'+
      '<td class="num" style="font-weight:bold;color:'+sevC[v.severity]+'">'+
        v.score+'</td>'+
      '<td><b>'+esc((v.title||'').slice(0,80))+'</b></td>'+
      '<td class="num">'+(v.days_old?.toFixed(1)||0)+'d</td>'+
      '<td class="num">'+Math.floor(v.duration_seconds/60)+'m</td>'+
      '<td class="num">'+fmt(v.view_count)+'</td>'+
      '<td>'+(top3||'<i class="muted">(không có lỗi)</i>')+'</td></tr>';
  });
  hh+='</tbody></table>';
}

// === D. SEO ACTION ITEMS — tổng hợp việc cần làm ===
if(D.health_actions&&D.health_actions.length){
  hh+='<h3>D. ✅ SEO Action items — Việc CẦN LÀM cho kênh</h3>'+
  '<p class="muted">Tổng hợp từ Channel audit + Video audit + Keyword '+
  'alignment. Sắp xếp theo độ ưu tiên — làm HIGH trước.</p>'+
  '<table class="srt"><thead><tr>'+
  '<th>Ưu tiên</th><th>Nhóm</th><th>Vấn đề</th>'+
  '<th>Hành động cụ thể</th><th>Người làm</th><th>ETA</th>'+
  '</tr></thead><tbody>';
  D.health_actions.forEach(a=>{
    const pc=prioC[a.priority]||'#666';
    hh+='<tr>'+
    '<td><span style="color:'+pc+';font-weight:bold">●</span> '+
       a.priority.toUpperCase()+'</td>'+
    '<td>'+esc(a.category)+'</td>'+
    '<td><b>'+esc(a.issue)+'</b><br><span class="muted" style="font-size:12px">'+
       esc(a.detail||'')+'</span></td>'+
    '<td>'+esc(a.action)+'</td>'+
    '<td>'+esc(a.owner)+'</td>'+
    '<td>'+esc(a.eta)+'</td></tr>';
  });
  hh+='</tbody></table>'+
  '<p class="muted" style="margin-top:12px"><b>💡 Quy tắc:</b> Lỗi LẶP LẠI '+
  'ở ≥5/10 video = lỗi <i>quy trình</i> — sửa template default settings + '+
  'description mặc định cho mọi video tương lai, không sửa từng video một.</p>';
}

if(!D.health_channel||D.health_channel.score===undefined){
  hh+='<p class="muted">Chưa đủ dữ liệu kênh chính để chấm điểm. '+
  'Cần giám sát kênh trước.</p>';
}
document.getElementById('s12').innerHTML=hh;

// ========================================
// INSIDE ANALYTICS — 5 tabs (s13-s17)
// ========================================
const IN=D.inside||{};
const noData='<h2>📊 Inside Analytics</h2><p class="muted">Chưa có dữ liệu '+
  'Inside cho kênh này (data Inside đến từ Postgres).</p>';

// === s13: Inside Summary (KPI grid + overview) ===
let s13h='<h2>📊 Inside: Tóm tắt 30 ngày</h2>';
if(!IN.channel_summary){
  s13h=noData;
}else{
  const CS=IN.channel_summary;
  const netClr=CS.last_subs_net>=0?sevC.good:sevC.bad;
  s13h+='<p class="muted">Account tag: <b>'+esc(IN.account_tag)+'</b> • '+
      'Dữ liệu CHÍNH THỨC từ YouTube Studio (qua dump backend). '+
      '<i>Revenue ẩn khỏi báo cáo public.</i></p>';

  // KPI grid 4 cards
  s13h+='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:12px 0">';
  const kpis=[
    ['Views 30 ngày',fmt(CS.last_views),'#3b82f6'],
    ['Subs NET 30d',(CS.last_subs_net>=0?'+':'')+fmt(CS.last_subs_net),netClr],
    ['AVD trung bình',(CS.avg_avd_seconds||0).toFixed(0)+'s ('+((CS.avg_avd_seconds||0)/60).toFixed(1)+'p)','#9333ea'],
    ['CTR Thumbnail TB',((CS.avg_thumbnail_ctr||0)*100).toFixed(2)+'%',((CS.avg_thumbnail_ctr||0)*100)>=5?sevC.good:sevC.warn],
  ];
  kpis.forEach(k=>{
    s13h+='<div style="background:#fafafa;border-radius:6px;padding:14px;border-left:4px solid '+k[2]+'">'+
      '<div class="muted" style="font-size:12px">'+k[0]+'</div>'+
      '<div style="font-size:22px;font-weight:bold;color:'+k[2]+';margin-top:4px">'+k[1]+'</div></div>';
  });
  s13h+='</div>';

  // Sub gained/lost detail
  s13h+='<h3>Chi tiết Subscribers 30 ngày</h3>'+
    '<table class="srt"><tbody>'+
    '<tr><td><b>Subscribers GAINED</b></td><td class="num" style="color:'+sevC.good+'">+'+fmt(CS.last_subs_gained)+'</td></tr>'+
    '<tr><td><b>Subscribers LOST</b></td><td class="num" style="color:'+sevC.bad+'">−'+fmt(CS.last_subs_lost)+'</td></tr>'+
    '<tr><td><b>NET</b></td><td class="num" style="color:'+netClr+';font-weight:bold;font-size:18px">'+
      (CS.last_subs_net>=0?'+':'')+fmt(CS.last_subs_net)+'</td></tr>'+
    '</tbody></table>';

  // Insight nhanh
  s13h+='<h3>💡 Insight tóm tắt</h3><ul>';
  if(CS.last_subs_net<0){
    s13h+='<li style="color:'+sevC.bad+'"><b>Subs NET ÂM</b> — kênh đang MẤT audience. '+
      'Cần audit pillar content + xem video nào khiến viewer unsub.</li>';
  }else if(CS.last_subs_net<10){
    s13h+='<li style="color:'+sevC.warn+'">Subs NET tăng chậm — cần CTA subscribe mạnh hơn.</li>';
  }else{
    s13h+='<li style="color:'+sevC.good+'">Subs NET tăng tốt — duy trì chiến lược content hiện tại.</li>';
  }
  const ctrPct=(CS.avg_thumbnail_ctr||0)*100;
  if(ctrPct<3){
    s13h+='<li style="color:'+sevC.bad+'">CTR thumbnail '+ctrPct.toFixed(1)+'% — thumbnail/title yếu, redesign.</li>';
  }else if(ctrPct>=10){
    s13h+='<li style="color:'+sevC.good+'">CTR thumbnail '+ctrPct.toFixed(1)+'% — XUẤT SẮC.</li>';
  }
  if(CS.avg_avd_seconds<60){
    s13h+='<li style="color:'+sevC.bad+'">AVD '+CS.avg_avd_seconds.toFixed(0)+'s &lt;1 phút — '+
      'video quá ngắn hoặc viewer drop ở 60s đầu.</li>';
  }
  s13h+='</ul>';
  s13h+='<p class="muted">→ Xem chi tiết ở các tab Audience / Traffic / Retention / Thumbnail CTR.</p>';
}
document.getElementById('s13').innerHTML=s13h;

// === s14: Inside Audience (Demographics + Devices + Countries + Cross) ===
let s14h='<h2>👥 Inside: Audience Profile</h2>';
if(!IN.audience_full){
  s14h+='<p class="muted">Chưa có dữ liệu audience.</p>';
}else{
  const AF=IN.audience_full;
  const CS=IN.channel_summary||{};

  // Insights ở đầu
  if((AF.insights||[]).length){
    s14h+='<h3>🎯 Insights chính</h3><ul>';
    AF.insights.forEach(i=>{s14h+='<li>'+esc(i)+'</li>';});
    s14h+='</ul>';
  }

  // 2 cột: Demographics + Devices
  s14h+='<div style="display:flex;gap:24px;flex-wrap:wrap;margin-top:16px">';

  if((AF.demographics||[]).length){
    // Tổng hợp by age + gender
    const byAge={},byGender={};
    AF.demographics.forEach(d=>{
      byAge[d.age_group]=(byAge[d.age_group]||0)+d.pct;
      byGender[d.gender]=(byGender[d.gender]||0)+d.pct;
    });
    s14h+='<div style="flex:1;min-width:360px"><h3>Tuổi × Giới tính (top 10)</h3>'+
      '<table class="srt"><thead><tr><th>Giới tính</th><th>Tuổi</th><th>%</th></tr></thead><tbody>';
    AF.demographics.slice(0,10).forEach(d=>{
      const bar='<div style="display:inline-block;width:'+Math.min(d.pct*5,200)+
        'px;height:12px;background:#FF8FAB;border-radius:2px"></div>';
      s14h+='<tr><td>'+esc(d.gender)+'</td>'+
            '<td>'+esc(d.age_group)+'</td>'+
            '<td class="num">'+d.pct.toFixed(1)+'% '+bar+'</td></tr>';
    });
    s14h+='</tbody></table>';

    s14h+='<h4 style="margin-top:12px">Phân theo Giới tính</h4><table class="srt"><tbody>';
    Object.entries(byGender).sort((a,b)=>b[1]-a[1]).forEach(([g,p])=>{
      const bar='<div style="display:inline-block;width:'+Math.min(p*4,200)+
        'px;height:12px;background:#FF8FAB;border-radius:2px"></div>';
      s14h+='<tr><td><b>'+esc(g)+'</b></td><td class="num">'+p.toFixed(1)+'% '+bar+'</td></tr>';
    });
    s14h+='</tbody></table>';

    s14h+='<h4 style="margin-top:12px">Phân theo Độ tuổi</h4><table class="srt"><tbody>';
    Object.entries(byAge).sort((a,b)=>b[1]-a[1]).forEach(([a,p])=>{
      const bar='<div style="display:inline-block;width:'+Math.min(p*4,200)+
        'px;height:12px;background:#9b5de5;border-radius:2px"></div>';
      s14h+='<tr><td><b>'+esc(a)+'</b></td><td class="num">'+p.toFixed(1)+'% '+bar+'</td></tr>';
    });
    s14h+='</tbody></table></div>';
  }

  if(AF.devices&&Object.keys(AF.devices).length){
    s14h+='<div style="flex:1;min-width:280px"><h3>Thiết bị xem</h3>'+
      '<table class="srt"><thead><tr><th>Device</th><th>%</th></tr></thead><tbody>';
    Object.entries(AF.devices).sort((a,b)=>b[1]-a[1]).forEach(([d,p])=>{
      const bar='<div style="display:inline-block;width:'+Math.min(p*3,250)+
        'px;height:14px;background:#7AE5A7;border-radius:3px"></div>';
      s14h+='<tr><td><b>'+esc(d)+'</b></td><td class="num">'+p.toFixed(1)+'% '+bar+'</td></tr>';
    });
    s14h+='</tbody></table>';

    // Mobile diagnosis
    const mob=AF.devices.MOBILE||0;
    if(mob>90){
      s14h+='<p style="background:#fff4e0;padding:10px;border-radius:4px;margin-top:8px">'+
        '<b>⚠ Mobile-dominant:</b> '+mob.toFixed(0)+'% viewer xem trên mobile. '+
        'Thumbnail PHẢI tối ưu màn nhỏ: text ≤5 từ size lớn, mặt to, contrast cao. '+
        'Tránh chi tiết nhỏ — không đọc được ở 200×120px.</p>';
    }else if(mob<40){
      s14h+='<p style="background:#e8f5e8;padding:10px;border-radius:4px;margin-top:8px">'+
        '<b>📺 Desktop/TV viewer dominant:</b> mobile chỉ '+mob.toFixed(0)+'%. '+
        'Có thể làm video DÀI HƠN (15-30 phút) — desktop/TV viewer chịu watch time tốt.</p>';
    }
    s14h+='</div>';
  }
  s14h+='</div>';

  // Countries section
  if((AF.countries||[]).length){
    s14h+='<h3 style="margin-top:24px">🌍 Top quốc gia (15)</h3>'+
      '<table class="srt"><thead><tr><th>#</th><th>Quốc gia</th><th>Views</th>'+
      '<th>%</th><th>CPM</th></tr></thead><tbody>';
    const highCpm={US:1,GB:1,AU:1,CA:1,DE:1,FR:1,JP:1,KR:1,NL:1,SE:1,CH:1,NO:1};
    AF.countries.forEach((c,i)=>{
      const bar='<div style="display:inline-block;width:'+Math.min(c.pct*5,300)+
        'px;height:12px;background:#FFD27A;border-radius:2px"></div>';
      const cpmTag=highCpm[c.country]?'<span style="color:'+sevC.good+'">💰 Cao</span>':
        '<span class="muted">Thấp</span>';
      s14h+='<tr><td class="num">'+(i+1)+'</td>'+
        '<td><b>'+esc(c.country)+'</b></td>'+
        '<td class="num">'+fmt(c.views)+'</td>'+
        '<td class="num">'+c.pct.toFixed(1)+'% '+bar+'</td>'+
        '<td>'+cpmTag+'</td></tr>';
    });
    s14h+='</tbody></table>';
  }
}
document.getElementById('s14').innerHTML=s14h;

// === s15: Inside Traffic Sources (breakdown + trend + diagnosis) ===
let s15h='<h2>🚦 Inside: Nguồn Traffic + Chẩn đoán</h2>';
if(!IN.channel_summary){
  s15h+='<p class="muted">Chưa có dữ liệu.</p>';
}else{
  const CS=IN.channel_summary;
  const th=IN.traffic_health||{};
  const thColor={good:sevC.good,warn:sevC.warn,bad:sevC.bad}[th.health]||sevC.warn;

  s15h+='<div style="background:'+sevBg2[th.health||'warn']+';padding:14px;'+
    'border-radius:6px;margin:12px 0">'+
    '<div style="font-size:14px;font-weight:bold;color:'+thColor+'">Health: '+
    (th.health||'?').toUpperCase()+'</div>';
  if((th.issues||[]).length){
    s15h+='<ul style="margin:8px 0 0 0">';
    th.issues.forEach(i=>{s15h+='<li>'+esc(i)+'</li>';});
    s15h+='</ul>';
  }
  s15h+='</div>';

  // Source breakdown 30d
  s15h+='<h3>Phân bố Traffic 30 ngày (theo views)</h3>';
  if((CS.traffic_sources_recent||[]).length){
    // Benchmark cho diagnose từng source
    const benchmark={
      YT_SEARCH:[10,25,'Search ranking — cần keyword/title đúng'],
      RELATED_VIDEO:[30,50,'Suggested — algorithm đẩy (cần CTR+AVD cao)'],
      SUGGESTED:[30,50,'Suggested — algorithm đẩy'],
      YT_CHANNEL:[5,15,'Channel page — sub vào kênh xem'],
      BROWSE:[15,30,'Home page — personalized cho subscriber'],
      SUBSCRIBER:[20,40,'Subscriber feed — sub loyalty'],
      EXT_URL:[3,15,'External — collab, social, embed'],
      EXTERNAL:[3,15,'External'],
      END_SCREEN:[2,8,'End screen — chuyển sang video tiếp'],
      PLAYLIST:[3,15,'Playlist auto-play'],
      NOTIFICATION:[1,5,'Notification cho bell-subscribers'],
      SHORTS:[10,40,'Shorts feed'],
      YT_OTHER_PAGE:[5,15,'Other YouTube pages'],
      NO_LINK_OTHER:[0,5,'No-link (TV apps, etc.)'],
    };
    s15h+='<table class="srt"><thead><tr>'+
      '<th>Source</th><th>Views 30d</th><th>%</th>'+
      '<th>Benchmark</th><th>Đánh giá</th></tr></thead><tbody>';
    CS.traffic_sources_recent.forEach(ts=>{
      const bench=benchmark[ts.source]||[0,100,'(không có benchmark)'];
      let status, scolor;
      if(ts.pct<bench[0]){status='THẤP'; scolor=sevC.bad;}
      else if(ts.pct>bench[1]){status='CAO'; scolor=sevC.warn;}
      else{status='OK'; scolor=sevC.good;}
      const bar='<div style="display:inline-block;width:'+Math.min(ts.pct*3,250)+
        'px;height:12px;background:#7AB8FF;border-radius:2px"></div>';
      s15h+='<tr><td><b>'+esc(ts.source)+'</b><br><span class="muted" style="font-size:11px">'+
        esc(bench[2])+'</span></td>'+
        '<td class="num">'+fmt(ts.views)+'</td>'+
        '<td class="num">'+ts.pct.toFixed(1)+'% '+bar+'</td>'+
        '<td class="muted">'+bench[0]+'-'+bench[1]+'%</td>'+
        '<td><span style="color:'+scolor+';font-weight:bold">'+status+'</span></td></tr>';
    });
    s15h+='</tbody></table>';
  }

  // Trend 7d vs 30d
  if(IN.traffic_trend&&IN.traffic_trend.trend){
    s15h+='<h3 style="margin-top:24px">📈 Trend 7 ngày qua (vs 30 ngày)</h3>'+
      '<p class="muted">Velocity = views/ngày. So sánh 7d gần đây với baseline 30d. '+
      '+% = tăng tốc, −% = giảm.</p>'+
      '<table class="srt"><thead><tr>'+
      '<th>Source</th><th>Velocity 7d (v/ngày)</th>'+
      '<th>Velocity 30d</th><th>Trend</th></tr></thead><tbody>';
    const sorted=Object.entries(IN.traffic_trend.velocity||{})
      .sort((a,b)=>(b[1]['30d']||0)-(a[1]['30d']||0)).slice(0,10);
    sorted.forEach(([src,vels])=>{
      const t=IN.traffic_trend.trend[src]||0;
      const tColor=t>10?sevC.good:t<-10?sevC.bad:sevC.warn;
      const arrow=t>0?'▲':t<0?'▼':'─';
      s15h+='<tr><td><b>'+esc(src)+'</b></td>'+
        '<td class="num">'+(vels['7d']||0).toFixed(0)+'</td>'+
        '<td class="num">'+(vels['30d']||0).toFixed(0)+'</td>'+
        '<td class="num" style="color:'+tColor+';font-weight:bold">'+
        arrow+' '+(t>0?'+':'')+t.toFixed(0)+'%</td></tr>';
    });
    s15h+='</tbody></table>';
  }

  s15h+='<h3 style="margin-top:24px">💡 Hành động đề xuất</h3><ul>';
  s15h+='<li><b>Source SEARCH thấp</b> → audit Title/Description/Tags 10 video gần nhất, '+
    'đảm bảo có keyword chính ≤50 ký tự đầu Title.</li>';
  s15h+='<li><b>Source SUGGESTED thấp</b> → tăng AVD/CTR (sửa hook + thumbnail) → '+
    'algorithm sẽ đẩy mạnh.</li>';
  s15h+='<li><b>Source BROWSE thấp</b> → sub loyalty yếu, cần notification bell + '+
    'community tab tích cực.</li>';
  s15h+='<li><b>Source END_SCREEN &lt;1%</b> → thiếu End Screen 4 elements '+
    '(video tiếp + playlist + subscribe + channel).</li>';
  s15h+='<li><b>Source SUBSCRIBER quá cao &gt;50%</b> → kênh phụ thuộc sub cũ, '+
    'không có new audience. Cần SEO mạnh hơn + Shorts để hút new viewer.</li>';
  s15h+='</ul>';
}
document.getElementById('s15').innerHTML=s15h;

// === s16: Inside Retention (curve + segment analysis + AI) ===
let s16h='<h2>📉 Inside: Retention Curves + Phân tích Drop</h2>';
if(!(IN.retention_top||[]).length){
  s16h+='<p class="muted">Chưa có dữ liệu retention. '+
    'Cần video ≥50 views để hiển thị curve.</p>';
}else{
  s16h+='<p class="muted">Phân tích retention <b>5 video MỚI NHẤT</b> '+
    'của kênh chính (mới nhất lên trên). Mỗi video có: thông tin đầy đủ '+
    '(view/like/cmt/CTR/AVD), retention curve 4 segments (Hook 0-10%, '+
    'Early 10-50%, Mid 50-90%, Outro 90-100%), drop points lớn, và '+
    '<b>phân tích AI rule-based</b> với hành động khuyến nghị cụ thể.</p>'+
    '<p class="muted" style="font-size:12px;background:#fff7e6;padding:8px;'+
    'border-left:3px solid #f59e0b;border-radius:3px">⚠️ <b>Lưu ý CTR/'+
    'Impressions:</b> View/Like/Cmt cập nhật <b>hôm nay</b> (YouTube Data '+
    'API real-time). Riêng CTR + Impressions dùng <b>YouTube Reporting API '+
    '(lag 2-3 ngày)</b>. Data CTR cuối: <b>'+(IN.last_thumbnail_day||'?')+
    '</b>. Video đăng sau ngày này tạm chưa có CTR/Imp — sẽ có data sau '+
    '2-3 ngày khi Google generate report. Phần mềm tự fetch ở lần daily '+
    'run kế tiếp, không cần làm gì thêm.</p>';

  // Limit to 5 video
  const r5=IN.retention_top.slice(0,5);
  // Summary stats — 26/05: BỎ video pending khỏi tính avg (video mới
  // <48h chưa có retention data, avg_retention=0 sẽ kéo TB xuống).
  const allAvg=r5.filter(r=>!r.retention_pending).map(r=>r.avg_retention);
  const meanAvg=allAvg.length?allAvg.reduce((s,v)=>s+v,0)/allAvg.length:0;
  const meanClr=meanAvg>=40?sevC.good:meanAvg>=25?sevC.warn:sevC.bad;
  s16h+='<div style="background:#fafafa;padding:12px;border-radius:6px;margin:12px 0">'+
    '<div class="muted">Avg retention TB của 5 video mới nhất:</div>'+
    '<div style="font-size:28px;font-weight:bold;color:'+meanClr+'">'+
    meanAvg.toFixed(1)+'%</div>'+
    '<div class="muted" style="font-size:12px">Mốc tốt ≥40%, xuất sắc ≥50%</div></div>';
  // Replace forEach source with r5
  IN.retention_top=r5;

  // Each video: title + segments + drop points + SVG curve
  IN.retention_top.forEach((r,idx)=>{
    const segs=r.segments||{};
    const weakest=segs.weakest_segment||'?';
    const weakestMap={hook:'Hook 0-10% (Intro)',early:'Early 10-50% (Mid-early)',mid:'Mid 50-90% (Body)'};
    const weakestLabel=weakestMap[weakest]||weakest;
    const avgClr=r.avg_retention>=40?sevC.good:r.avg_retention>=25?sevC.warn:sevC.bad;

    s16h+='<div style="border:1px solid #ddd;border-radius:6px;padding:12px;margin:12px 0">';
    const publishedStr=(r.published_at||'').substring(0,10);
    const vurl='https://youtu.be/'+r.video_id;
    s16h+='<div><b>#'+(idx+1)+' <a href="'+vurl+'" target="_blank">'+
      esc(r.title.slice(0,80))+'</a></b></div>';
    // Full info row — view, like, cmt, CTR, impressions, engagement
    // CTR/Imp lấy từ Studio Excel dump (YouTube Analytics API public KHÔNG
    // expose). Video đăng sau ngày dump cuối → hiển thị rõ ngày data cuối
    // để user biết khi nào có CTR.
    const hasCtr=r.ctr!=null && r.ctr>0;
    const hasImp=r.impressions!=null && r.impressions>0;
    const lastDump=IN.last_thumbnail_day||'?';
    // 26/05: clarified — view/like/cmt CẬP NHẬT HÔM NAY (YouTube Data API
    // real-time). Riêng CTR/Imp dùng YouTube Reporting API lag 2-3 ngày.
    // Video đăng sau lastDump → chưa có CTR/Imp, các metric khác có.
    const noteData='CTR/Impressions hôm nay chưa có cho video này. '+
                   'Reporting API Google lag 2-3 ngày, data CTR cuối: '+
                   lastDump+'. Sẽ có data vào ~'+lastDump+'+3 ngày. '+
                   'View/Like/Cmt đã cập nhật hôm nay từ YouTube Data API.';
    const ctrPct=hasCtr?(r.ctr<1?r.ctr*100:r.ctr).toFixed(1)+'%':
                  '<span style="color:#999" title="'+noteData+
                  '">hôm nay chưa có (chờ Reporting API)</span>';
    const impStr=hasImp?fmt(r.impressions):
                  '<span style="color:#999" title="'+noteData+
                  '">hôm nay chưa có (chờ Reporting API)</span>';
    const engPct=(r.views>100)?(((r.likes||0)+(r.comments||0))*100/r.views).toFixed(1)+'%':'-';
    s16h+='<div style="display:flex;flex-wrap:wrap;gap:14px;margin:8px 0;font-size:13px">'+
      '<span><b>📅 Đăng:</b> '+(publishedStr||'?')+'</span>'+
      '<span><b>👁 View:</b> '+fmt(r.views)+'</span>'+
      '<span><b>👍 Like:</b> '+fmt(r.likes||0)+'</span>'+
      '<span><b>💬 Cmt:</b> '+fmt(r.comments||0)+'</span>'+
      '<span><b>📊 Impressions:</b> '+impStr+'</span>'+
      '<span><b>🎯 CTR:</b> '+ctrPct+'</span>'+
      '<span><b>💗 Engagement:</b> '+engPct+'</span>'+
      '</div>';
    if(r.retention_pending){
      s16h+='<div style="margin:8px 0;padding:8px;background:#fff7e6;'+
        'border-left:3px solid #f59e0b;border-radius:3px;font-size:13px">'+
        '⏳ <b>Retention đang process</b> — YouTube Analytics chưa generate '+
        'curve cho video mới &lt;48h. Daily run kế tiếp sẽ có data đầy đủ. '+
        'View/Like/Cmt đã cập nhật hôm nay.</div>';
    } else {
      s16h+='<div style="margin:8px 0">Avg retention: '+
        '<span style="color:'+avgClr+';font-weight:bold;font-size:16px">'+r.avg_retention+'%</span>'+
        ' • Weakest: <b style="color:'+sevC.warn+'">'+esc(weakestLabel)+'</b></div>';
    }

    // SVG retention curve
    if((r.curve||[]).length>2){
      const W=600, H=120;
      let path='M ';
      r.curve.forEach((c,i)=>{
        const x=(c[0]*W).toFixed(1);
        const y=(H-c[1]*H).toFixed(1);
        path+=(i===0?'':'L ')+x+' '+y+' ';
      });
      s16h+='<svg width="'+W+'" height="'+H+'" style="background:#fafafa;border-radius:4px">'+
        '<line x1="0" y1="'+(H*0.6)+'" x2="'+W+'" y2="'+(H*0.6)+'" stroke="#ddd" stroke-dasharray="3,3"/>'+
        '<text x="4" y="'+(H*0.6-3)+'" fill="#888" font-size="10">40% (target)</text>'+
        '<path d="'+path+'" stroke="#3b82f6" stroke-width="2" fill="none"/>'+
        '</svg>';
    }

    // Segments table — 26/05: skip cho video pending (data chưa có)
    if(!r.retention_pending){
    s16h+='<table class="srt" style="margin-top:6px"><thead><tr>'+
      '<th>Segment</th><th>Retention TB</th><th>Diagnose</th></tr></thead><tbody>';
    [['Hook 0-10%','hook_retention',45,'Hook yếu → quay lại intro 10s đầu'],
     ['Early 10-50%','early_retention',35,'Pacing chậm → cut nhiều hơn, b-roll'],
     ['Mid 50-90%','mid_retention',25,'Content sag → boost moment giữa video'],
     ['Outro 90-100%','outro_retention',15,'Bình thường drop ở CTA']].forEach(s=>{
      const val=segs[s[1]]||0;
      const ok=val>=s[2];
      const c=ok?sevC.good:val>=s[2]-15?sevC.warn:sevC.bad;
      s16h+='<tr><td>'+s[0]+'</td>'+
        '<td class="num" style="color:'+c+';font-weight:bold">'+val.toFixed(1)+'%</td>'+
        '<td>'+(ok?'<span class="muted">OK</span>':'<b>'+s[3]+'</b>')+'</td></tr>';
    });
    s16h+='</tbody></table>';
    }  // end if(!r.retention_pending) — skip segments table cho pending video

    // Drop points
    if((r.drop_points||[]).length){
      s16h+='<div style="margin-top:6px"><b>Drop points (giảm &gt;5%):</b> ';
      r.drop_points.slice(0,5).forEach(d=>{
        s16h+='<span style="background:#ffe8e8;color:'+sevC.bad+
          ';padding:2px 6px;border-radius:3px;margin-right:6px">'+
          d.at_pct+'%: −'+d.drop_pct+'%</span>';
      });
      s16h+='</div>';
    }
    // AI rule-based analysis cho video này
    if(r.ai_analysis){
      s16h+='<div style="margin-top:10px;padding:10px;background:#f0f8ff;'+
        'border-left:4px solid #3b82f6;border-radius:4px;font-size:13px">'+
        '<b>🤖 Phân tích AI:</b> '+esc(r.ai_analysis)+'</div>';
    }
    s16h+='</div>';
  });

  s16h+='<h3>💡 Hành động sửa Retention</h3><ul>'+
    '<li><b>Hook retention &lt;45%</b> → Hook 10s đầu yếu. Áp dụng 5 công thức Hook '+
    '(Result First / Problem Punch / Bold Promise / Curiosity Gap / Story).</li>'+
    '<li><b>Early retention &lt;35%</b> → Pacing chậm. Cut shot mỗi 3-7s, '+
    'thêm b-roll, pattern interrupt mỗi 60-90s.</li>'+
    '<li><b>Mid retention &lt;25%</b> → Content giữa video không cuốn. '+
    'Boost với revelation, story arc, stake escalation.</li>'+
    '<li><b>Outro retention &lt;15%</b> (vẫn drop quá mạnh ở 90-100%) → '+
    'CTA outro quá dài / không có End Screen kéo session.</li></ul>';
}
document.getElementById('s16').innerHTML=s16h;

// === s17: Inside Thumbnail CTR (top + worst + correlation) ===
let s17h='<h2>🖼 Inside: Thumbnail CTR — Phân tích đầy đủ</h2>';
if(!(IN.thumbnail_ctr_top||[]).length && !(IN.thumbnail_ctr_worst||[]).length){
  s17h+='<p class="muted">Chưa có dữ liệu thumbnail CTR.</p>';
}else{
  // Correlation
  if(IN.ctr_correlation&&IN.ctr_correlation.n_videos){
    const cc=IN.ctr_correlation;
    s17h+='<h3>📊 Phân tích CTR vs Views</h3>'+
      '<table class="srt" style="max-width:600px"><tbody>'+
      '<tr><td><b>Số video phân tích</b></td><td class="num">'+fmt(cc.n_videos)+'</td></tr>'+
      '<tr><td><b>CTR TB toàn kênh</b></td><td class="num">'+cc.avg_ctr_all+'%</td></tr>'+
      '<tr><td><b>CTR TB video TOP view</b></td><td class="num" style="color:'+sevC.good+';font-weight:bold">'+cc.avg_ctr_high_view_videos+'%</td></tr>'+
      '<tr><td><b>CTR TB video LOW view</b></td><td class="num" style="color:'+sevC.bad+';font-weight:bold">'+cc.avg_ctr_low_view_videos+'%</td></tr>'+
      '<tr><td><b>CTR lift</b> (Top - Low)</td><td class="num" style="font-weight:bold">+'+cc.ctr_lift+'%</td></tr>'+
      '</tbody></table>';
    if(cc.ctr_lift>2){
      s17h+='<p style="background:#e8f5e8;padding:10px;border-radius:4px"><b>✅ Tương quan rõ:</b> '+
        'video CTR cao có views cao. THUMBNAIL là yếu tố CRITICAL cho kênh — '+
        'đầu tư redesign thumbnail cho video yếu.</p>';
    }else{
      s17h+='<p style="background:#fff4e0;padding:10px;border-radius:4px"><b>⚠ Tương quan yếu:</b> '+
        'CTR không tương quan rõ với views. Có thể audience tham gia qua suggested/browse '+
        'chứ không click thumbnail trực tiếp.</p>';
    }
  }

  // 2 cột: Top + Worst
  s17h+='<div style="display:flex;gap:24px;flex-wrap:wrap;margin-top:16px">';

  // Top
  if((IN.thumbnail_ctr_top||[]).length){
    s17h+='<div style="flex:1;min-width:480px"><h3>🏆 TOP 15 CTR cao nhất (HỌC HỎI)</h3>'+
      '<table class="srt"><thead><tr><th>#</th><th>CTR</th>'+
      '<th>Imp</th><th>Tiêu đề</th></tr></thead><tbody>';
    IN.thumbnail_ctr_top.forEach((t,i)=>{
      const ctrClr=t.ctr>=10?sevC.good:t.ctr>=5?sevC.warn:sevC.bad;
      s17h+='<tr><td class="num">'+(i+1)+'</td>'+
        '<td class="num" style="color:'+ctrClr+';font-weight:bold">'+t.ctr.toFixed(2)+'%</td>'+
        '<td class="num">'+fmt(t.impressions)+'</td>'+
        '<td><small>'+esc(t.title.slice(0,55))+'</small></td></tr>';
    });
    s17h+='</tbody></table></div>';
  }

  // Worst
  if((IN.thumbnail_ctr_worst||[]).length){
    s17h+='<div style="flex:1;min-width:480px"><h3>⚠ WORST 10 CTR thấp nhất (CẦN SỬA)</h3>'+
      '<table class="srt"><thead><tr><th>#</th><th>CTR</th>'+
      '<th>Imp</th><th>Tiêu đề</th></tr></thead><tbody>';
    IN.thumbnail_ctr_worst.forEach((t,i)=>{
      s17h+='<tr><td class="num">'+(i+1)+'</td>'+
        '<td class="num" style="color:'+sevC.bad+';font-weight:bold">'+t.ctr.toFixed(2)+'%</td>'+
        '<td class="num">'+fmt(t.impressions)+'</td>'+
        '<td><small>'+esc(t.title.slice(0,55))+'</small></td></tr>';
    });
    s17h+='</tbody></table></div>';
  }
  s17h+='</div>';

  s17h+='<h3 style="margin-top:24px">💡 Hành động đề xuất</h3><ul>'+
    '<li><b>Học từ TOP 5 thumbnail CTR cao</b>: pattern nào lặp? Face emotion? '+
    'Color scheme? Text size? Áp dụng cho video mới.</li>'+
    '<li><b>Redesign WORST 5 thumbnail</b>: ưu tiên video có IMPRESSIONS cao '+
    '(thuật toán đang đẩy nhưng người không click).</li>'+
    '<li><b>A/B test thumbnail</b> (YouTube Studio → Test thumbnail) cho video '+
    'có IMPRESSIONS &gt;5K nhưng CTR &lt;3%.</li>'+
    '<li><b>Anatomy thumbnail thắng</b>: Face 30-50% + Object 20-40% + Text '+
    '2-5 từ + Color contrast cao + Test ở 200×120px (mobile).</li></ul>';
}
document.getElementById('s17').innerHTML=s17h;

// === s18: Inside × SEO Synthesis (7 gap kết hợp 3 lớp data) ===
const SYN=D.inside_synthesis||{};
let s18h='<h2>🧠 Inside × SEO Synthesis — 7 lớp kết hợp</h2>';
if(!SYN.findings && !SYN.top_anatomy && !SYN.traffic_playbook){
  s18h+='<p class="muted">Chưa có dữ liệu synthesis. Cần Inside data + Health Check để chạy.</p>';
}else{
  s18h+='<p class="muted">Kết hợp <b>Inside Analytics</b> (data thực YouTube Studio) × '+
    '<b>Health Check</b> (audit SEO 19 tiêu chí) × <b>SEO framework</b> '+
    '(Title/Hook/Thumbnail/Retention 10 mục) — ra plan SEO cụ thể.</p>';

  // ========= G1. FINDINGS =========
  if((SYN.findings||[]).length){
    s18h+='<h3>🎯 G1. Findings Cross-Reference Inside × Health × SEO</h3>';
    SYN.findings.forEach((f,i)=>{
      const c={good:sevC.good,warn:sevC.warn,bad:sevC.bad}[f.severity]||sevC.warn;
      const bg={good:'#e8f5e8',warn:'#fff4e0',bad:'#ffe8e8'}[f.severity]||'#fff4e0';
      s18h+='<div style="background:'+bg+';border-left:4px solid '+c+
        ';padding:12px;border-radius:4px;margin:10px 0">'+
        '<div style="font-weight:bold;color:'+c+';margin-bottom:6px">'+
        '#'+(i+1)+' '+esc(f.finding)+'</div>'+
        '<div style="margin-bottom:6px"><b>Chẩn đoán:</b> '+esc(f.diagnosis)+'</div>'+
        '<div><b>Hành động:</b> '+esc(f.action)+'</div></div>';
    });
  }

  // ========= G7. PERIOD DELTA (đặt sớm để nhân viên thấy alert trước) =========
  const PD=SYN.period_delta||{};
  if(PD.current){
    s18h+='<h3 style="margin-top:24px">⏱ G7. So sánh chu kỳ 7 ngày này vs 7-14 ngày trước</h3>';
    if((PD.alerts||[]).length){
      PD.alerts.forEach(a=>{
        const c={good:sevC.good,warn:sevC.warn,bad:sevC.bad}[a.level]||sevC.warn;
        const bg={good:'#e8f5e8',warn:'#fff4e0',bad:'#ffe8e8'}[a.level]||'#fff4e0';
        s18h+='<div style="background:'+bg+';color:'+c+';padding:10px;'+
          'border-radius:4px;margin:6px 0;font-weight:bold">⚠ '+esc(a.msg)+'</div>';
      });
    }
    const C=PD.current, P=PD.previous, DL=PD.delta||{};
    s18h+='<table class="srt" style="max-width:720px"><thead><tr>'+
      '<th>Metric</th><th>Chu kỳ này (7d)</th><th>Chu kỳ trước (7d)</th><th>Δ</th></tr></thead><tbody>';
    const rowsPD=[
      ['Views',fmt(C.views),fmt(P.views),DL.views_pct],
      ['Subs NET',(C.subs_net>=0?'+':'')+fmt(C.subs_net),(P.subs_net>=0?'+':'')+fmt(P.subs_net),null,DL.subs_net_delta],
      ['AVD (s)',C.avd.toFixed(0),P.avd.toFixed(0),DL.avd_pct],
      ['CTR (%)',C.ctr.toFixed(2),P.ctr.toFixed(2),DL.ctr_pct],
    ];
    rowsPD.forEach(r=>{
      let dCell='-', dColor='inherit';
      if(r[3]!==null && r[3]!==undefined){
        const dv=r[3];
        dColor=dv>10?sevC.good:dv<-10?sevC.bad:'inherit';
        dCell=(dv>0?'+':'')+dv.toFixed(1)+'%';
      }else if(r[4]!==undefined){
        const dv=r[4];
        dColor=dv>0?sevC.good:dv<0?sevC.bad:'inherit';
        dCell=(dv>=0?'+':'')+fmt(dv);
      }
      s18h+='<tr><td><b>'+r[0]+'</b></td><td class="num">'+r[1]+'</td>'+
        '<td class="num">'+r[2]+'</td>'+
        '<td class="num" style="color:'+dColor+';font-weight:bold">'+dCell+'</td></tr>';
    });
    s18h+='</tbody></table>';
  }

  // ========= G2. TOP ANATOMY =========
  const TA=SYN.top_anatomy||{};
  if((TA.patterns||[]).length){
    s18h+='<h3 style="margin-top:24px">🏆 G2. Công thức TOP 15 Thumbnail/Title CTR cao</h3>';
    s18h+='<div style="background:#e8f5e8;border-left:4px solid '+sevC.good+
      ';padding:12px;border-radius:4px;margin:10px 0">'+
      '<div class="muted">Phân tích từ '+TA.n_analyzed+' video CTR cao nhất:</div>'+
      '<div style="font-size:18px;font-weight:bold;margin-top:6px">'+
      'Formula: '+esc(TA.formula)+'</div>'+
      '<div class="muted" style="margin-top:6px">Title TB '+TA.title_length_avg+' ký tự, '+
      (TA.minute_avg?'TB '+TA.minute_avg+' phút':'')+'</div></div>';
    s18h+='<table class="srt"><thead><tr><th>Pattern</th><th>% xuất hiện</th>'+
      '<th>Ví dụ titles</th></tr></thead><tbody>';
    TA.patterns.forEach(p=>{
      const bar='<div style="display:inline-block;width:'+Math.min(p.freq_pct*3,200)+
        'px;height:12px;background:#7AE5A7;border-radius:2px;margin-right:6px"></div>';
      const examples=(p.example_titles||[]).map(t=>esc(t.slice(0,55))).join('<br>');
      s18h+='<tr><td><b>'+esc(p.name)+'</b></td>'+
        '<td class="num">'+bar+p.freq_pct+'%</td>'+
        '<td><small>'+examples+'</small></td></tr>';
    });
    s18h+='</tbody></table>';
  }

  // ========= G3. WORST vs TOP =========
  const WT=SYN.worst_vs_top||{};
  if(WT.summary){
    s18h+='<h3 style="margin-top:24px">⚠ G3. WORST 10 thiếu gì so với TOP 15</h3>';
    s18h+='<div style="background:#fff4e0;border-left:4px solid '+sevC.warn+
      ';padding:12px;border-radius:4px;margin:10px 0"><b>Insight: </b>'+esc(WT.summary)+'</div>';
    if((WT.missing_patterns||[]).length){
      s18h+='<table class="srt"><thead><tr><th>Pattern thiếu</th><th>TOP có</th>'+
        '<th>WORST có</th><th>Gap</th></tr></thead><tbody>';
      WT.missing_patterns.forEach(m=>{
        s18h+='<tr><td><b>'+esc(m.pattern)+'</b></td>'+
          '<td class="num" style="color:'+sevC.good+'">'+m.top_pct+'%</td>'+
          '<td class="num" style="color:'+sevC.bad+'">'+m.worst_pct+'%</td>'+
          '<td class="num" style="font-weight:bold">+'+m.delta+'pp</td></tr>';
      });
      s18h+='</tbody></table>';
    }
    if((WT.per_video_diag||[]).length){
      s18h+='<h4 style="margin-top:14px">Sửa từng video WORST:</h4>';
      WT.per_video_diag.forEach(d=>{
        s18h+='<div style="border:1px solid #ddd;border-radius:6px;padding:10px;margin:8px 0">'+
          '<div><b style="color:'+sevC.bad+'">CTR '+d.ctr.toFixed(2)+'%</b> — '+
          esc(d.title.slice(0,70))+'</div>'+
          '<ul style="margin:6px 0 0 0">';
        (d.missing||[]).forEach(m=>{
          s18h+='<li>'+esc(m)+'</li>';
        });
        s18h+='</ul></div>';
      });
    }
  }

  // ========= G4. TRAFFIC PLAYBOOK =========
  if((SYN.traffic_playbook||[]).length){
    s18h+='<h3 style="margin-top:24px">🚦 G4. Playbook SEO theo từng Traffic Source</h3>';
    SYN.traffic_playbook.forEach(tp=>{
      const c={LOW:sevC.bad,OK:sevC.good,HIGH:sevC.warn}[tp.status]||sevC.warn;
      const bg={LOW:'#ffe8e8',OK:'#e8f5e8',HIGH:'#fff4e0'}[tp.status]||'#fff4e0';
      s18h+='<div style="background:'+bg+';border-left:4px solid '+c+
        ';padding:12px;border-radius:4px;margin:10px 0">'+
        '<div><b>'+esc(tp.source)+' — '+esc(tp.name)+'</b> '+
        '<span class="muted">('+tp.share_pct.toFixed(1)+'%, benchmark '+
        tp.benchmark+', status <b style="color:'+c+'">'+tp.status+'</b>)</span></div>'+
        '<ul style="margin:8px 0 0 0">';
      (tp.actions||[]).forEach(a=>{s18h+='<li>'+esc(a)+'</li>';});
      s18h+='</ul></div>';
    });
  }

  // ========= G5. DROP POINTS =========
  if((SYN.drop_diag||[]).length){
    s18h+='<h3 style="margin-top:24px">📉 G5. Drop Point Retention → Title Strategy</h3>';
    s18h+='<p class="muted">Mỗi video: vị trí drop lớn nhất → chẩn đoán nguyên nhân + action.</p>';
    SYN.drop_diag.forEach((d,i)=>{
      s18h+='<div style="border:1px solid #ddd;border-radius:6px;padding:10px;margin:8px 0">'+
        '<div><b>#'+(i+1)+'</b> '+esc(d.title.slice(0,70))+
        ' <span class="muted">('+fmt(d.views)+' views, '+d.avg_retention+'% retention)</span></div>'+
        '<div style="margin-top:6px"><b style="color:'+sevC.bad+'">Drop '+d.drop_pct+
        '%</b> tại <b>'+d.biggest_drop_at+'%</b> video</div>'+
        '<div style="margin-top:6px"><b>Chẩn đoán:</b> '+esc(d.diagnosis)+'</div>'+
        '<div style="margin-top:4px"><b>Action:</b> '+esc(d.action)+'</div></div>';
    });
  }

  // ========= G6. KEYWORD CLUSTER =========
  const KC=SYN.keyword_cluster||{};
  if(KC.primary){
    s18h+='<h3 style="margin-top:24px">🔑 G6. Keyword Cluster đề xuất theo Audience</h3>';
    s18h+='<p class="muted">'+esc(KC.reasoning||'')+'</p>';
    s18h+='<div style="display:flex;gap:20px;flex-wrap:wrap;margin-top:10px">';
    s18h+='<div style="flex:1;min-width:280px"><h4>Primary keyword (ưu tiên 1)</h4>'+
      '<ul>'+(KC.primary||[]).map(k=>'<li><b>'+esc(k)+'</b></li>').join('')+'</ul></div>';
    s18h+='<div style="flex:1;min-width:280px"><h4>Secondary (long-tail)</h4>'+
      '<ul>'+(KC.secondary||[]).map(k=>'<li>'+esc(k)+'</li>').join('')+'</ul></div>';
    s18h+='<div style="flex:1;min-width:280px"><h4>Modifier (style/format)</h4>'+
      '<ul>'+(KC.modifiers||[]).map(k=>'<li>'+esc(k)+'</li>').join('')+'</ul></div>';
    s18h+='</div>';
    s18h+='<div style="background:#fafafa;padding:10px;border-radius:4px;margin-top:10px">'+
      '<b>Cách dùng:</b> Mỗi video mới chọn 1 PRIMARY + 1-2 SECONDARY '+
      'làm tag và keyword trong title. Description chèn 3-5 SECONDARY. '+
      'MODIFIER dùng cho thumbnail style.</div>';
  }

  // =====================================================
  // PHASE 2 — G8-G20 (Niche-specific 14 mảng SEO)
  // =====================================================
  s18h+='<hr style="margin:30px 0;border:none;border-top:2px solid #333"/>';
  s18h+='<h2>📚 PHASE 2 — Niche-specific SEO ('+esc(SYN.niche_name||'')+')</h2>';

  // ====== G8. DESCRIPTION AUDIT ======
  const DA=SYN.desc_audit||{};
  if(DA.avg_word_count!==undefined){
    const fr=DA.fail_rate_pct||0;
    const fc=fr>=70?sevC.bad:fr>=30?sevC.warn:sevC.good;
    const fbg=fr>=70?'#ffe8e8':fr>=30?'#fff4e0':'#e8f5e8';
    s18h+='<h3 style="margin-top:24px">📝 G8. DESCRIPTION Audit (10 video gần nhất)</h3>';
    s18h+='<div style="background:'+fbg+';border-left:4px solid '+fc+';padding:12px;border-radius:4px;margin:10px 0">'+
      '<div><b>'+fr+'%</b> video FAIL chuẩn description.</div>'+
      '<div class="muted">Avg word count: <b>'+DA.avg_word_count+'</b> từ '+
      '(yêu cầu ≥'+DA.min_required+' từ).</div>'+
      '<div class="muted" style="margin-top:6px"><b>Rule keyword distribution:</b> '+
      esc(DA.keyword_distribution_rule||'')+'</div></div>';
    if((DA.per_video||[]).length){
      s18h+='<table class="srt"><thead><tr>'+
        '<th>Title</th><th>Words</th><th>Hashtag</th><th>Timestamp</th>'+
        '<th>CTA Sub</th><th>Link</th><th>Issues</th></tr></thead><tbody>';
      DA.per_video.slice(0,10).forEach(p=>{
        const wcClr=p.word_count>=DA.min_required?sevC.good:sevC.bad;
        s18h+='<tr><td><small>'+esc(p.title)+'</small></td>'+
          '<td class="num" style="color:'+wcClr+'">'+p.word_count+'</td>'+
          '<td class="num">'+p.hashtags_count+'</td>'+
          '<td class="num">'+p.timestamps_count+'</td>'+
          '<td>'+(p.has_subscribe?'✓':'✗')+'</td>'+
          '<td>'+(p.has_link?'✓':'✗')+'</td>'+
          '<td><small>'+(p.issues||[]).map(i=>esc(i)).join('<br>')+'</small></td></tr>';
      });
      s18h+='</tbody></table>';
    }
    if(DA.template_recommended){
      s18h+='<details style="margin-top:10px"><summary><b>📄 Template description (click mở)</b></summary>'+
        '<pre style="background:#fafafa;padding:10px;border-radius:4px;white-space:pre-wrap;font-size:12px">'+
        esc(DA.template_recommended)+'</pre></details>';
    }
  }

  // ====== G9. TAGS AUDIT ======
  const TG=SYN.tags_audit||{};
  if(TG.fail_rate_pct!==undefined){
    const fr=TG.fail_rate_pct||0;
    const fc=fr>=70?sevC.bad:fr>=30?sevC.warn:sevC.good;
    const fbg=fr>=70?'#ffe8e8':fr>=30?'#fff4e0':'#e8f5e8';
    s18h+='<h3 style="margin-top:24px">🏷 G9. TAGS Audit</h3>';
    s18h+='<div style="background:'+fbg+';border-left:4px solid '+fc+';padding:12px;border-radius:4px;margin:10px 0">'+
      '<div><b>'+fr+'%</b> video FAIL chuẩn tags.</div>'+
      '<div class="muted">Recommend: <b>'+TG.recommended_count[0]+'-'+TG.recommended_count[1]+' tag</b> '+
      'theo hierarchy broad → specific → question.</div></div>';
    s18h+='<div style="display:flex;gap:20px;flex-wrap:wrap;margin-top:10px">';
    s18h+='<div style="flex:1;min-width:280px"><h4>BROAD tags (5-7 tag chung)</h4>'+
      '<ul>'+(TG.recommended_broad||[]).map(t=>'<li>'+esc(t)+'</li>').join('')+'</ul></div>';
    s18h+='<div style="flex:1;min-width:280px"><h4>SPECIFIC tags (long-tail)</h4>'+
      '<ul>'+(TG.recommended_specific||[]).map(t=>'<li>'+esc(t)+'</li>').join('')+'</ul></div>';
    s18h+='<div style="flex:1;min-width:280px"><h4>Top tags kênh đang dùng</h4>'+
      '<ul>'+(TG.most_used_tags||[]).slice(0,10).map(t=>'<li>'+esc(t.tag)+' <span class="muted">×'+t.n+'</span></li>').join('')+'</ul></div>';
    s18h+='</div>';
    if((TG.per_video||[]).length){
      s18h+='<table class="srt" style="margin-top:10px"><thead><tr>'+
        '<th>Title</th><th>#Tags</th><th>BROAD</th><th>SPECIFIC</th>'+
        '<th>Issues</th></tr></thead><tbody>';
      TG.per_video.slice(0,10).forEach(p=>{
        const nClr=p.n_tags>=TG.recommended_count[0]?sevC.good:sevC.bad;
        s18h+='<tr><td><small>'+esc(p.title)+'</small></td>'+
          '<td class="num" style="color:'+nClr+'">'+p.n_tags+'</td>'+
          '<td class="num">'+p.has_broad_match+'</td>'+
          '<td class="num">'+p.has_specific_match+'</td>'+
          '<td><small>'+(p.issues||[]).map(i=>esc(i)).join('<br>')+'</small></td></tr>';
      });
      s18h+='</tbody></table>';
    }
  }

  // ====== G14. TITLE POSITION + FORMULA ======
  const TT=SYN.title_audit||{};
  if(TT.videos_analyzed){
    s18h+='<h3 style="margin-top:24px">✏ G14. TITLE — Position keyword + 4 SEO Formulas</h3>';
    s18h+='<div style="background:#fafafa;padding:12px;border-radius:4px;margin:10px 0">'+
      '<div><b>Niche formula best:</b> '+esc(TT.niche_formula_best||'')+'</div>'+
      '<div class="muted">Keyword position: '+esc(TT.niche_keyword_position_rule||'')+
      ' • Optimal length: '+TT.niche_optimal_length[0]+'-'+TT.niche_optimal_length[1]+' ký tự</div></div>';
    if((TT.formula_distribution||[]).length){
      s18h+='<h4>Phân bố Title Formulas</h4>'+
        '<table class="srt"><thead><tr><th>Formula</th><th>Số video</th>'+
        '<th>Cách dùng</th></tr></thead><tbody>';
      TT.formula_distribution.forEach(f=>{
        s18h+='<tr><td><b>'+esc(f.formula)+'</b></td>'+
          '<td class="num">'+f.count+'</td>'+
          '<td><small>'+esc(f.desc)+'</small></td></tr>';
      });
      s18h+='</tbody></table>';
    }
    if(TT.issues_count>0){
      s18h+='<p style="color:'+sevC.warn+';margin-top:10px"><b>⚠ '+TT.issues_count+
        ' video</b> có vấn đề về độ dài title.</p>';
    }
  }

  // ====== G20. CLICKBAIT PENALTY ======
  const CB=SYN.clickbait_check||{};
  if(CB.forbidden_words){
    const vio=CB.violations_count||0;
    if(vio>0){
      s18h+='<h3 style="margin-top:24px">🚫 G20. CLICKBAIT Penalty</h3>';
      s18h+='<div style="background:#ffe8e8;border-left:4px solid '+sevC.bad+
        ';padding:12px;border-radius:4px;margin:10px 0">'+
        '<b>⚠ Phát hiện '+vio+' video dùng từ KHÔNG NÊN trong niche này:</b> '+
        CB.forbidden_words.join(', ')+'</div>';
      s18h+='<table class="srt"><thead><tr><th>Title</th>'+
        '<th>Từ vi phạm</th><th>Views</th></tr></thead><tbody>';
      (CB.violations||[]).forEach(v=>{
        s18h+='<tr><td><small>'+esc(v.title)+'</small></td>'+
          '<td style="color:'+sevC.bad+';font-weight:bold">'+
          v.violating_words.join(', ')+'</td>'+
          '<td class="num">'+fmt(v.views)+'</td></tr>';
      });
      s18h+='</tbody></table>';
    }else if((CB.forbidden_words||[]).length){
      s18h+='<h3 style="margin-top:24px">🚫 G20. CLICKBAIT Penalty Check</h3>';
      s18h+='<div style="background:#e8f5e8;color:'+sevC.good+
        ';padding:10px;border-radius:4px"><b>✓ KHÔNG VI PHẠM</b> — '+
        'không title nào dùng từ penalty: '+CB.forbidden_words.join(', ')+'</div>';
    }
  }

  // ====== G15. THUMBNAIL LAYOUT per niche ======
  const TL=SYN.thumbnail_layout||{};
  if(TL.primary_layout){
    s18h+='<h3 style="margin-top:24px">🖼 G15. THUMBNAIL Layout per niche</h3>';
    const ss=TL.status;
    const sc={good:sevC.good,warn:sevC.warn,bad:sevC.bad}[ss]||sevC.warn;
    const sbg={good:'#e8f5e8',warn:'#fff4e0',bad:'#ffe8e8'}[ss]||'#fff4e0';
    s18h+='<div style="background:'+sbg+';border-left:4px solid '+sc+
      ';padding:12px;border-radius:4px;margin:10px 0">'+
      '<div><b>Layout chính niche này:</b> <span style="font-size:16px">'+
      esc(TL.primary_layout)+'</span></div>'+
      '<div class="muted" style="margin-top:6px">CTR hiện tại: <b>'+
      TL.current_avg_ctr_pct+'%</b> • Sweet spot niche: '+
      TL.niche_sweet_spot[0]+'-'+TL.niche_sweet_spot[1]+'% → status '+
      '<b style="color:'+sc+'">'+ss+'</b></div></div>';
    s18h+='<h4>Recipe 3 layout có thể dùng:</h4><table class="srt"><thead><tr>'+
      '<th>Layout</th><th>Công thức</th></tr></thead><tbody>';
    Object.entries(TL.layouts_recipe||{}).forEach(([n,r])=>{
      s18h+='<tr><td><b>'+esc(n)+'</b></td><td>'+esc(r)+'</td></tr>';
    });
    s18h+='</tbody></table>';
    s18h+='<div style="background:#fafafa;padding:10px;border-radius:4px;margin-top:10px">'+
      '<b>Quy chuẩn thumbnail:</b><br>'+
      '• Color palette: '+esc(TL.color_palette||'')+'<br>'+
      '• Text max: '+TL.text_words_max+' từ, size ≥'+TL.text_size_min_px+'px<br>'+
      '• Face size: '+TL.face_size_pct_range[0]+'-'+TL.face_size_pct_range[1]+'% thumbnail</div>';
  }

  // ====== G17. CTR SWEET SPOT ======
  const CS2=SYN.ctr_sweet||{};
  if(CS2.current_avg_ctr_pct!==undefined){
    s18h+='<h3 style="margin-top:24px">📊 G17. CTR — Niche Sweet Spot</h3>';
    const ss=CS2.status;
    const sc={excellent:sevC.good,good:sevC.good,low:sevC.warn,bad:sevC.bad}[ss]||sevC.warn;
    s18h+='<table class="srt" style="max-width:600px"><tbody>'+
      '<tr><td><b>CTR hiện tại</b></td><td class="num" style="color:'+sc+
      ';font-weight:bold">'+CS2.current_avg_ctr_pct+'%</td></tr>'+
      '<tr><td><b>TOP 5 CTR TB</b></td><td class="num">'+CS2.top5_avg_ctr_pct+'%</td></tr>'+
      '<tr><td><b>Niche sweet spot</b></td><td class="num">'+
      CS2.niche_sweet_spot[0]+'-'+CS2.niche_sweet_spot[1]+'%</td></tr>'+
      '<tr><td><b>Xuất sắc</b></td><td class="num">≥'+CS2.niche_high_excellent+'%</td></tr>'+
      '<tr><td><b>Cảnh báo</b></td><td class="num">≤'+CS2.niche_low_warning+'%</td></tr>'+
      '<tr><td><b>Decay period</b></td><td class="num">'+
      CS2.niche_decay_days[0]+'-'+CS2.niche_decay_days[1]+' ngày</td></tr>'+
      '<tr><td><b>Status</b></td><td style="color:'+sc+';font-weight:bold;text-transform:uppercase">'+
      ss+'</td></tr></tbody></table>';
    if(CS2.gap_to_excellent_pct>0){
      s18h+='<p style="margin-top:10px">→ <b>Còn '+CS2.gap_to_excellent_pct+
        '%</b> để đạt mức xuất sắc. Tập trung redesign WORST 5 thumbnail.</p>';
    }
  }

  // ====== G16. RETENTION TECHNIQUES per niche ======
  const RM=SYN.retention_map||{};
  if((RM.all_techniques||[]).length){
    s18h+='<h3 style="margin-top:24px">📉 G16. RETENTION — 8 Techniques per niche</h3>';
    s18h+='<div style="background:#fafafa;padding:12px;border-radius:4px;margin:10px 0">'+
      '<b>Retention TB hiện tại:</b> '+RM.current_avg_retention_pct+'% • '+
      '<b>Weakest segment:</b> <span style="color:'+sevC.warn+';font-weight:bold">'+
      (RM.weakest_segment||'?')+'</span></div>';
    if((RM.prioritized_techniques||[]).length){
      s18h+='<h4>🎯 Techniques ƯU TIÊN cho '+(RM.weakest_segment||'?')+' segment</h4>';
      s18h+='<ol>';
      RM.prioritized_techniques.forEach(t=>{
        s18h+='<li><b>'+esc(t)+'</b></li>';
      });
      s18h+='</ol>';
    }
    s18h+='<details style="margin-top:10px"><summary><b>Full 8 techniques niche này (click)</b></summary><ul>';
    RM.all_techniques.forEach(t=>{
      s18h+='<li>'+esc(t)+'</li>';
    });
    s18h+='</ul></details>';
    const pt=RM.pacing_target||{};
    if(pt.cuts_per_min){
      s18h+='<div style="background:#fafafa;padding:10px;border-radius:4px;margin-top:10px">'+
        '<b>Pacing target niche:</b> '+
        pt.cuts_per_min[0]+'-'+pt.cuts_per_min[1]+' cuts/phút • '+
        'B-roll '+pt.b_roll_pct[0]+'-'+pt.b_roll_pct[1]+'% • '+
        'Pattern interrupt mỗi '+pt.pattern_interrupt_sec+'s</div>';
    }
  }

  // ====== G10. UPLOAD TIMING ======
  const UT=SYN.upload_timing||{};
  if(UT.videos_analyzed){
    s18h+='<h3 style="margin-top:24px">⏰ G10. UPLOAD TIMING — Best time slot</h3>';
    s18h+='<div style="display:flex;gap:20px;flex-wrap:wrap">';
    s18h+='<div style="flex:1;min-width:280px"><h4>Niche khuyến nghị</h4><ul>'+
      '<li>Giờ tốt: '+(UT.niche_recommended_hours||[]).map(h=>h[0]+'h-'+h[1]+'h').join(', ')+'</li>'+
      '<li>Ngày tốt: '+(UT.niche_recommended_days||[]).join(', ')+'</li>'+
      '<li>Tần suất: '+(UT.niche_frequency_per_week||[0,0])[0]+'-'+(UT.niche_frequency_per_week||[0,0])[1]+' video/tuần</li>'+
      '<li>Premiere: '+(UT.premiere_recommended?'CÓ — bell-sub + sleep timer':'KHÔNG cần')+'</li>'+
      '</ul></div>';
    if((UT.actual_best_weekdays||[]).length){
      s18h+='<div style="flex:1;min-width:280px"><h4>Data thực tế kênh ('+UT.videos_analyzed+' video)</h4>'+
        '<b>Ngày TB views cao:</b><ul>';
      UT.actual_best_weekdays.forEach(d=>{
        s18h+='<li>'+d.day+': '+fmt(d.avg_views)+' views</li>';
      });
      s18h+='</ul>';
      if((UT.actual_best_hours||[]).length){
        s18h+='<b>Giờ TB views cao:</b><ul>';
        UT.actual_best_hours.forEach(h=>{
          s18h+='<li>'+h.hour+'h: '+fmt(h.avg_views)+' views</li>';
        });
        s18h+='</ul>';
      }
      s18h+='</div>';
    }
    s18h+='</div>';
  }

  // ====== G11. ENGAGEMENT SIGNALS ======
  const EG=SYN.engagement||{};
  if(EG.videos_analyzed){
    s18h+='<h3 style="margin-top:24px">💬 G11. ENGAGEMENT Signals (like/comment baseline)</h3>';
    const cl={good:sevC.good,warn:sevC.warn,bad:sevC.bad}[EG.status_like]||sevC.warn;
    const cc={good:sevC.good,warn:sevC.warn,bad:sevC.bad}[EG.status_comment]||sevC.warn;
    s18h+='<table class="srt" style="max-width:700px"><thead><tr><th>Metric</th>'+
      '<th>Hiện tại</th><th>Baseline niche</th><th>Status</th></tr></thead><tbody>'+
      '<tr><td><b>Like / View</b></td><td class="num">'+EG.avg_like_pct+'%</td>'+
      '<td class="num">'+EG.baseline_like_pct+'%</td>'+
      '<td style="color:'+cl+';font-weight:bold;text-transform:uppercase">'+EG.status_like+'</td></tr>'+
      '<tr><td><b>Comment / View</b></td><td class="num">'+EG.avg_comment_pct+'%</td>'+
      '<td class="num">'+EG.baseline_comment_pct+'%</td>'+
      '<td style="color:'+cc+';font-weight:bold;text-transform:uppercase">'+EG.status_comment+'</td></tr>'+
      '</tbody></table>';
    if((EG.actions||[]).length){
      s18h+='<ul style="margin-top:10px">';
      EG.actions.forEach(a=>{s18h+='<li>'+esc(a)+'</li>';});
      s18h+='</ul>';
    }
    if((EG.low_engagement_videos||[]).length){
      s18h+='<details style="margin-top:10px"><summary><b>Video engagement THẤP (click)</b></summary>'+
        '<table class="srt"><thead><tr><th>Title</th><th>Views</th><th>Like%</th><th>Cmt%</th></tr></thead><tbody>';
      EG.low_engagement_videos.forEach(v=>{
        s18h+='<tr><td><small>'+esc(v.title)+'</small></td>'+
          '<td class="num">'+fmt(v.views)+'</td>'+
          '<td class="num">'+v.like_pct+'%</td>'+
          '<td class="num">'+v.comment_pct+'%</td></tr>';
      });
      s18h+='</tbody></table></details>';
    }
  }

  // ====== G12. CAPTION strategy ======
  const CP=SYN.caption||{};
  if((CP.recommended_languages||[]).length){
    s18h+='<h3 style="margin-top:24px">🌐 G12. CAPTION — Multi-language strategy</h3>';
    s18h+='<div style="background:#fafafa;padding:10px;border-radius:4px;margin:10px 0">'+
      '<b>'+CP.total_audience_in_top5_lang+'%</b> audience nói các ngôn ngữ chính. '+
      'Auto-translate title: <b>'+(CP.auto_translate_title?'CÓ':'KHÔNG')+'</b> • '+
      'Auto-caption: <b>'+(CP.auto_caption?'CÓ':'KHÔNG')+'</b></div>';
    s18h+='<table class="srt" style="max-width:600px"><thead><tr><th>Ngôn ngữ</th>'+
      '<th>% audience</th><th>Priority niche</th></tr></thead><tbody>';
    CP.recommended_languages.forEach(l=>{
      s18h+='<tr><td><b>'+esc(l.language)+'</b></td>'+
        '<td class="num">'+l.audience_share_pct+'%</td>'+
        '<td>'+(l.priority_in_niche?'<span style="color:'+sevC.good+'">✓ Có</span>':'<span class="muted">−</span>')+'</td></tr>';
    });
    s18h+='</tbody></table>';
  }

  // ====== G13. CONTENT STRATEGY GAP ======
  const CG=SYN.content_gap||{};
  if(CG.pillars_total){
    s18h+='<h3 style="margin-top:24px">📂 G13. CONTENT — Pillar coverage</h3>';
    s18h+='<div style="background:#fafafa;padding:10px;border-radius:4px;margin:10px 0">'+
      '<b>'+CG.pillars_covered+'/'+CG.pillars_total+'</b> pillar đã làm. '+
      '<b style="color:'+sevC.warn+'">'+CG.pillars_missing+' pillar CHƯA chạm</b>.</div>';
    if((CG.covered_detail||[]).length){
      s18h+='<h4>Pillar đã làm</h4><table class="srt"><thead><tr>'+
        '<th>Pillar</th><th>Số video</th><th>% trong video gần đây</th></tr></thead><tbody>';
      CG.covered_detail.forEach(c=>{
        const bar='<div style="display:inline-block;width:'+Math.min(c.share_pct*3,200)+
          'px;height:10px;background:#7AE5A7;border-radius:2px"></div>';
        s18h+='<tr><td><b>'+esc(c.pillar)+'</b></td>'+
          '<td class="num">'+c.video_count+'</td>'+
          '<td class="num">'+c.share_pct+'% '+bar+'</td></tr>';
      });
      s18h+='</tbody></table>';
    }
    if((CG.new_video_ideas||[]).length){
      s18h+='<h4 style="margin-top:14px">💡 Ý tưởng video MỚI cho pillar chưa làm</h4>';
      CG.new_video_ideas.forEach(idea=>{
        s18h+='<div style="border:1px solid #ddd;border-radius:4px;padding:8px;margin:6px 0">'+
          '<b>'+esc(idea.pillar)+'</b><br>'+
          '<small class="muted">Template: '+esc(idea.title_template)+'</small></div>';
      });
    }
  }

  // ====== G18. CHANNEL × INSIDE ======
  const CXI=SYN.channel_x_inside||{};
  if((CXI.findings||[]).length){
    s18h+='<h3 style="margin-top:24px">⚙ G18. CHANNEL META × INSIDE Performance</h3>';
    s18h+='<div style="background:#fafafa;padding:10px;border-radius:4px;margin:10px 0">'+
      'Channel Health Score: <b>'+CXI.channel_score+'/100</b> • '+
      'Inside CTR: <b>'+CXI.inside_ctr_pct+'%</b> • '+
      'Inside AVD: <b>'+CXI.inside_avd_seconds+'s</b></div>';
    CXI.findings.forEach((f,i)=>{
      s18h+='<div style="background:#fff4e0;border-left:4px solid '+sevC.warn+
        ';padding:10px;border-radius:4px;margin:8px 0">'+
        '<b>#'+(i+1)+'</b> '+esc(f.issue)+'<br>'+
        '<b>Chẩn đoán:</b> '+esc(f.diagnosis)+'<br>'+
        '<b>Action:</b> '+esc(f.action)+'</div>';
    });
  }

  // ====== G19. COMPETITOR × INSIDE ======
  const CCX=SYN.competitor_cross||{};
  if(CCX.self){
    s18h+='<h3 style="margin-top:24px">⚔ G19. COMPETITOR × INSIDE Cross</h3>';
    const sf=CCX.self;
    s18h+='<table class="srt" style="max-width:800px"><thead><tr>'+
      '<th>Channel</th><th>Subs</th><th>Video/30d</th><th>Avg view</th>'+
      '</tr></thead><tbody>';
    s18h+='<tr style="background:#fff4e0"><td><b>BẠN</b></td>'+
      '<td class="num">'+fmt(sf.subs)+'</td>'+
      '<td class="num"><b>'+sf.videos_30d+'</b></td>'+
      '<td class="num"><b>'+fmt(sf.avg_view)+'</b></td></tr>';
    (CCX.competitors||[]).forEach(c=>{
      s18h+='<tr><td>'+esc(c.title)+'</td>'+
        '<td class="num">'+fmt(c.subs)+'</td>'+
        '<td class="num">'+c.videos_30d+'</td>'+
        '<td class="num">'+fmt(c.avg_view)+'</td></tr>';
    });
    s18h+='<tr style="background:#fafafa"><td><b>TB đối thủ</b></td>'+
      '<td>-</td>'+
      '<td class="num">'+CCX.competitor_avg_freq_30d+'</td>'+
      '<td class="num">'+fmt(CCX.competitor_avg_view)+'</td></tr>';
    s18h+='</tbody></table>';
    if((CCX.findings||[]).length){
      CCX.findings.forEach((f,i)=>{
        s18h+='<div style="background:#fff4e0;border-left:4px solid '+sevC.warn+
          ';padding:10px;border-radius:4px;margin:8px 0">'+
          '<b>'+esc(f.issue)+'</b><br>'+
          '<b>Action:</b> '+esc(f.action)+'</div>';
      });
    }
  }

}
document.getElementById('s18').innerHTML=s18h;

function filterT(inp,id){const q=inp.value.toLowerCase();
document.querySelectorAll('#'+id+' tbody tr').forEach(tr=>{
tr.style.display=tr.textContent.toLowerCase().includes(q)?'':'none';});}
function bindSort(){document.querySelectorAll('table.srt').forEach(t=>{
if(t.dataset.sb)return;t.dataset.sb='1';
t.querySelectorAll('th').forEach((th,ci)=>{th.onclick=()=>{
const tb=t.tBodies[0];const rows=[...tb.rows];
const asc=th.dataset.asc!=='1';th.dataset.asc=asc?'1':'0';
rows.sort((a,b)=>{const x=a.cells[ci]?a.cells[ci].textContent.trim():'';
const y=b.cells[ci]?b.cells[ci].textContent.trim():'';
const nx=parseFloat(x.replace(/[^0-9.-]/g,''));
const ny=parseFloat(y.replace(/[^0-9.-]/g,''));
if(!isNaN(nx)&&!isNaN(ny))return asc?nx-ny:ny-nx;
return asc?x.localeCompare(y):y.localeCompare(x);});
rows.forEach(r=>tb.appendChild(r));};});});}
bindSort();
</script>
__INTERACTIVE_PLACEHOLDER__
</body></html>
"""
