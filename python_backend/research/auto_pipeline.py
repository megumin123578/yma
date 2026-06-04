# -*- coding: utf-8 -*-
"""Dây chuyền tự động SAU GIÁM SÁT — giúp phần mềm tự chạy đúng quy
trình thủ công khi đã gắn khoá API AI.

Gọi sau khi đã giám sát + phát hiện đối thủ xong. Các bước:
  2a. refresh_socialblade  — fill SocialBlade cho các kênh (đã tách khỏi
                              run_research để tránh rate limit khi parallel)
  2b. refresh_trends       — fill Google Trends cho keyword (tương tự)
  3.  carry_forward_ai     — chuyển AI kỳ trước sang bản ghi mới nhất
  4a. generate_missing_ai  — sinh AI cho kênh chưa có (kênh chính, đối
                              thủ mới, đối thủ SEO lệch nhiều)
  4b. generate_strategy    — sinh chiến lược AI cho cả danh sách

Báo cáo serve JSON on-demand qua API (html_report.build_data → React);
khâu AI dùng Claude Code CLI.
"""
# Lệch SEO (điểm) coi là "số liệu đã đổi" -> phải sinh AI mới, không chép.
SEO_DRIFT_MAX = 7


def _log(log_fn, msg):
    if log_fn:
        try:
            log_fn(msg)
        except Exception:
            pass


def _seo(res):
    """Điểm SEO trung bình của 1 result."""
    return ((res or {}).get("tag_metrics") or {}).get(
        "seo_summary", {}).get("avg_score", 0) or 0


def _has_ai(res):
    return bool(res and (res.get("ai_analysis") or "").strip())


def _channel_records(persistence, channel_id):
    """Các bản ghi nghiên cứu 'channel' của 1 kênh — mới nhất trước."""
    return persistence.records_for_channel(channel_id)


def carry_forward_ai(wid, log_fn=None):
    """Bước 3: chuyển AI kỳ trước sang bản ghi mới nhất của từng kênh.

    QUY TẮC AN TOÀN: không chép AI kênh chính (luôn sinh mới); không
    chép đối thủ có SEO lệch > SEO_DRIFT_MAX. Trả về list dict
    {channel_id, title, is_self, previous_ai} các kênh CẦN sinh AI mới
    (previous_ai để truyền vào prompt cho AI mới biết "nhắc lại kỳ
    trước nếu chưa làm")."""
    from . import persistence, watchlist as wl_mod
    wl = wl_mod.load_watchlist(wid)
    if not wl:
        return []
    need_fresh = []
    carried = 0
    for c in wl.channels:
        recs = _channel_records(persistence, c.channel_id)
        if not recs:
            continue
        new_e = recs[0]
        new_res = persistence.load_result(new_e["id"])
        if new_res is None:
            continue
        if _has_ai(new_res):
            continue
        # Tìm AI kỳ trước (nếu có) — luôn lấy, kể cả khi quyết định
        # "cần sinh AI mới", để truyền vào prompt.
        prev_ai = ""
        prev_res = None
        for old_e in recs[1:]:
            old_res = persistence.load_result(old_e["id"])
            if old_res is None:
                continue
            if _has_ai(old_res):
                prev_res = old_res
                prev_ai = (old_res.get("ai_analysis") or "").strip()
                break
        if c.is_self:
            need_fresh.append({
                "channel_id": c.channel_id,
                "title": c.title,
                "is_self": True,
                "previous_ai": prev_ai,
            })
            continue
        if not prev_res:
            need_fresh.append({
                "channel_id": c.channel_id,
                "title": c.title,
                "is_self": False,
                "previous_ai": "",
            })
            continue
        if abs(_seo(new_res) - _seo(prev_res)) > SEO_DRIFT_MAX:
            need_fresh.append({
                "channel_id": c.channel_id,
                "title": c.title,
                "is_self": False,
                "previous_ai": prev_ai,
            })
            continue
        if persistence.update_result_field(
                new_e["id"], "ai_analysis", prev_res["ai_analysis"]):
            carried += 1
    _log(log_fn, f"Chuyển AI kỳ trước: {carried} kênh; "
                 f"{len(need_fresh)} kênh cần sinh AI mới.")
    return need_fresh


def _retry(fn, log_fn=None, label="task", retries=2, delay_sec=5):
    """Helper: chạy fn() có retry. Trả về kết quả hoặc None nếu fail.

    Pattern chuẩn từ 21/05/2026: pipeline KHÔNG dừng khi 1 task lỗi,
    chỉ retry vài lần rồi skip task đó. Tránh 1 kênh lỗi làm toàn bộ
    WL không có báo cáo.
    """
    import time as _t
    last_err = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if attempt < retries:
                _log(log_fn, f"  ! {label} lỗi (lần {attempt+1}): {e} "
                             f"— thử lại sau {delay_sec}s")
                _t.sleep(delay_sec)
            else:
                _log(log_fn, f"  ! {label} fail sau {retries+1} lần: {e}"
                             f" — SKIP, pipeline tiếp tục.")
    return None


def generate_missing_ai(need_fresh, api_key, model, log_fn=None):
    """Bước 4a: sinh AI cho các kênh trong need_fresh bằng ai_insights.
    Cần khoá API. Trả về số kênh đã sinh AI thành công.

    Áp dụng error recovery: 1 kênh lỗi → retry 2 lần → skip nếu vẫn
    fail, KHÔNG dừng vòng lặp.

    need_fresh: list dict {channel_id, title, is_self, previous_ai}.
    """
    from . import persistence, ai_insights
    # 29/05: cho chạy khi backend CLI bật (gói subscription, không cần key).
    if not api_key and not ai_insights.cli_available():
        _log(log_fn, "Chưa có khoá API AI — bỏ qua sinh AI từng kênh.")
        return 0
    done = 0
    for item in need_fresh:
        # Hỗ trợ ngược dạng tuple cũ (channel_id, title)
        if isinstance(item, tuple):
            channel_id, title = item
            is_self_ch = False
            prev_ai = ""
        else:
            channel_id = item.get("channel_id")
            title = item.get("title", "")
            is_self_ch = bool(item.get("is_self"))
            prev_ai = item.get("previous_ai", "") or ""
        recs = _channel_records(persistence, channel_id)
        if not recs:
            continue
        new_e = recs[0]

        def _gen():
            res = persistence.load_result(new_e["id"])
            if res is None:
                raise RuntimeError("snapshot không còn")
            # Kênh chính cần token nhiều hơn (6 mục chi tiết), đối
            # thủ chỉ 3 mục ngắn.
            mt = 3500 if is_self_ch else 1800
            text = ai_insights.analyze(
                res, api_key, model=model,
                previous_ai=prev_ai,
                is_self_channel=is_self_ch,
                max_tokens=mt)
            if not text or not text.strip():
                raise RuntimeError("AI trả về rỗng")
            persistence.update_result_field(new_e["id"], "ai_analysis",
                                            text.strip())
            return text

        result_text = _retry(
            _gen, log_fn=log_fn,
            label=f"AI kênh {title}",
            retries=2, delay_sec=5)
        if result_text:
            done += 1
            tag = "★ kênh chính" if is_self_ch else "đối thủ"
            _log(log_fn, f"  AI kênh ({tag}): {title} — OK")
    _log(log_fn, f"Đã sinh AI {done}/{len(need_fresh)} kênh.")
    return done


def generate_strategy(wid, api_key, model, log_fn=None):
    """Bước 4b: sinh chiến lược AI đầy đủ cho watchlist.

    Áp dụng error recovery: retry 2 lần nếu lỗi, không dừng pipeline.
    Truyền previous_analysis_text + previous_channels_data để AI sinh
    đối chiếu trực tiếp + nhắc lại khuyến nghị kỳ trước.
    """
    from . import watchlist as wl_mod, ai_insights
    # 29/05: cho chạy khi backend CLI bật (gói subscription, không cần key).
    if not api_key and not ai_insights.cli_available():
        return False
    wl = wl_mod.load_watchlist(wid)
    if not wl:
        return False

    def _gen():
        channels_data = ai_insights.collect_watchlist_data(wl)
        # Lấy chiến lược kỳ trước (nếu có) để AI biết tham chiếu, nhắc
        # lại khuyến nghị nếu kênh chưa làm
        prev_text = ""
        try:
            if getattr(wl, "analyses", None):
                last = wl.analyses[-1]
                if isinstance(last, dict):
                    prev_text = (last.get("content") or "").strip()
                else:
                    prev_text = (getattr(last, "content", "") or "").strip()
        except Exception:
            pass
        prev_data = None
        try:
            prev_data = ai_insights.collect_watchlist_data_previous(wl)
        except Exception:
            pass
        text = ai_insights.analyze_watchlist_strategy(
            wl, channels_data, api_key, model=model,
            previous_channels_data=prev_data,
            previous_analysis_text=prev_text)
        if not text or not text.strip():
            raise RuntimeError("Chiến lược AI trả về rỗng")
        wl_mod.save_analysis(wid, text.strip(), analyzed_by=model)
        return text

    out = _retry(_gen, log_fn=log_fn,
                 label=f"Chiến lược WL {wl.name}",
                 retries=2, delay_sec=5)
    if out:
        _log(log_fn, "Đã sinh chiến lược AI.")
        return True
    return False


def refresh_socialblade(wid, log_fn=None):
    """Fill SocialBlade cho các kênh trong WL (1 worker delay 3s, cache 6h
    built-in, early-stop khi rate limit). Đóng gói được vào exe."""
    _log(log_fn, "Bước 2a: Fill Social Blade...")
    try:
        from .refreshers import refresh_socialblade_for_watchlist
        refresh_socialblade_for_watchlist(wid, log_fn=lambda m: _log(log_fn, m))
    except Exception as e:
        _log(log_fn, f"  ! SocialBlade refresh loi: {e}")


def refresh_trends(wid, log_fn=None):
    """Fill Google Trends cho keyword trong WL (1 worker delay 4s, cache 24h
    built-in, hard timeout 20s/keyword, early-stop khi rate limit). Đóng
    gói được vào exe."""
    _log(log_fn, "Bước 2b: Fill Google Trends...")
    try:
        from .refreshers import refresh_trends_for_watchlist
        refresh_trends_for_watchlist(wid, log_fn=lambda m: _log(log_fn, m))
    except Exception as e:
        _log(log_fn, f"  ! Trends refresh loi: {e}")
