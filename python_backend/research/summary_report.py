# -*- coding: utf-8 -*-
"""Báo cáo TỔNG HỢP cuối ngày cho quản lý cấp cao — 1 HTML súc tích thay
cho 11 báo cáo chi tiết. Đọc nhanh 2-3 phút.

Nội dung:
  1. Overview các WL: subs, delta, top video hôm nay
  2. Top 10 video bùng nổ toàn công ty (cross-niche)
  3. Cảnh báo cần xử lý gấp (kênh tụt subs, video bị ẩn, etc.)
  4. Chủ đề hot xuyên ngách (cluster cross-WL)
  5. Link tới từng báo cáo chi tiết

Hàm chính: build_summary(wids, out_path=None) → trả path HTML.
"""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _overview_latest_videos(account_tag: str, limit: int = 3) -> list:
    """3 video mới nhất + đủ metrics, gom từ các bảng của page Overview:
    video_overview (views, avg duration, subs), video_thumbnail_daily
    (impressions, CTR), video_daily_stats (watch time = estimated_minutes).
    """
    if not account_tag:
        return []
    try:
        from sqlalchemy import text
        from python_backend.db import engine
        with engine.begin() as conn:
            base = conn.execute(text(
                """
                SELECT video_id, title, thumbnail, publish_date, views,
                       average_view_duration_seconds AS avg_dur,
                       subscribers_gained, subscribers_lost
                FROM video_overview
                WHERE account_tag = :tag
                  AND video_id IS NOT NULL AND video_id <> ''
                ORDER BY publish_date DESC NULLS LAST
                LIMIT :limit
                """), {"tag": account_tag, "limit": limit}).mappings().all()
            vids = [str(r["video_id"]) for r in base]
            imp_map, wt_map = {}, {}
            if vids:
                for r in conn.execute(text(
                    """
                    SELECT video_id, SUM(thumbnail_impressions) AS imp,
                           CASE WHEN SUM(thumbnail_impressions) > 0
                                THEN SUM(COALESCE(thumbnail_ctr, 0)
                                         * thumbnail_impressions)
                                     / SUM(thumbnail_impressions)
                                ELSE NULL END AS ctr
                    FROM video_thumbnail_daily
                    WHERE video_id = ANY(:vids)
                    GROUP BY video_id
                    """), {"vids": vids}).mappings():
                    imp_map[r["video_id"]] = (r["imp"], r["ctr"])
                for r in conn.execute(text(
                    """
                    SELECT video_id, SUM(estimated_minutes) AS wt
                    FROM video_daily_stats
                    WHERE video_id = ANY(:vids)
                    GROUP BY video_id
                    """), {"vids": vids}).mappings():
                    wt_map[r["video_id"]] = r["wt"]
    except Exception:
        return []
    out = []
    for r in base:
        vid = str(r.get("video_id") or "")
        imp, ctr = imp_map.get(vid, (None, None))
        wt = wt_map.get(vid)
        sg, sl = r.get("subscribers_gained"), r.get("subscribers_lost")
        subs = (int(sg or 0) - int(sl or 0)) if (sg is not None or sl is not None) else None
        out.append({
            "title": r.get("title") or "",
            "video_id": vid,
            "url": f"https://www.youtube.com/watch?v={vid}" if vid else "",
            "published_at": str(r.get("publish_date") or "")[:10],
            "thumbnail": r.get("thumbnail") or "",
            "views": int(r.get("views") or 0),
            "avg_view_duration": int(r.get("avg_dur") or 0),
            "watch_minutes": (int(wt) if wt is not None else None),
            "subscribers": subs,
            "impressions": (int(imp) if imp is not None else None),
            "ctr": (round(float(ctr) * 100, 1) if ctr is not None else None),
        })
    return out


def _pack_wl(wid: str) -> dict:
    """Đóng gói dữ liệu 1 WL cho summary."""
    import time as _t
    from . import watchlist as wl_mod, persistence
    w = wl_mod.load_watchlist(wid)
    if not w:
        return None

    sc = w.self_channel
    self_res = (persistence.find_previous_for_channel(sc.channel_id)
                if sc and sc.channel_id else None)

    # Lấy bản ghi KỲ TRƯỚC của kênh chính → build map video_id → (views, time)
    # để tính view/ngày GẦN ĐÂY thay vì lifetime
    # (Lifetime sai cho video viral lại: 8M views / 883 ngày = 9K/ngày
    #  trong khi thực tế đang tăng 600K/ngày trong tuần qua.)
    prev_view_map = {}  # video_id → (prev_views, prev_scrape_time)
    if sc and sc.channel_id:
        recs = persistence.records_for_channel(sc.channel_id)
        if len(recs) >= 2:
            try:
                prev = recs[1]
                prev_res = persistence.load_result(prev["id"])
                # prev_scrape_time = ngày snapshot kỳ trước (entry date) thay
                # cho mtime file — chính xác hơn (mtime đổi khi SB/AI ghi lại).
                from datetime import datetime as _dt
                prev_time = _dt.fromisoformat(prev.get("date", "")).timestamp()
                for pv in (prev_res.get("videos") or []):
                    vid = getattr(pv, "video_id", "") or ""
                    if vid:
                        prev_view_map[vid] = (
                            int(getattr(pv, "view_count", 0) or 0),
                            prev_time,
                        )
            except Exception:
                pass

    info = {
        "wid": wid,
        "name": w.name,
        "self_title": sc.title if sc else "",
        "self_channel_id": sc.channel_id if sc else "",
        "self_url": sc.url if sc else "",
        "n_channels": len(w.channels),
        "last_monitored": w.last_monitored or "",
        # A52 (26/05 tối, R19): đánh dấu ACTIVE/INACTIVE để báo cáo tổng
        # hợp hiển thị trạng thái daily run
        "is_active": not bool(getattr(w, "paused", False)),
        "paused_reason": getattr(w, "paused_reason", "") or "",
        "subs": 0,
        # 21/05: User chốt mốc 7 NGÀY (gần đây, ý nghĩa hơn 15d cho tracking).
        "subs_delta_7d": 0,
        "views_delta_7d": 0,
        "avg_daily_views_7d": 0,  # View/ngày KÊNH TB 7 ngày cuối từ SB
        "top_videos_today": [],   # video kênh chính tăng mạnh hôm nay
        "latest_videos": [],       # 3 video mới nhất (page Overview) — expand UI
        "account_tag": "",         # map kênh chính → account_tag (Overview/Inside)
        "outlier_videos": [],      # video toàn ngách đột biến
        "warnings": [],
        "strategy_preview": "",
        "report_path": "",
    }

    if not self_res:
        return info

    # Channel info — đọc subs từ channel object
    ch = self_res.get("channel")
    ch_subs = int(getattr(ch, "subscriber_count", 0) or 0) if ch else 0

    # SocialBlade: tính delta 7 NGÀY (gần đây nhất) từ daily_stats
    # 21/05 fix theo yêu cầu user: BỎ ngày view ÂM (do ẩn/xóa video làm
    # tổng view bị trừ mạnh, vd Show ASMR ngày 08/05 có -75.248.076).
    # Lấy ngày cũ hơn (lùi sâu hơn trong daily_stats) bù vào để vẫn đủ 7 ngày.
    sb = self_res.get("socialblade") or {}
    sb_subs = 0
    n_skip_negative = 0  # đếm số ngày âm đã bỏ qua
    if isinstance(sb, dict) and not sb.get("error"):
        summary = sb.get("summary") or {}
        sb_subs = int(summary.get("latest_subs", 0) or 0)
        daily = sb.get("daily_stats") or []
        # Filter ngày views_change ≥ 0 (giữ ngày 0 view như hôm nay
        # chưa close của SB). Ngày <0 = ẩn video → bỏ.
        positive_days = [d for d in daily
                         if (d.get("views_change", 0) or 0) >= 0]
        n_skip_negative = len(daily) - len(positive_days)
        last7 = positive_days[-7:] if len(positive_days) >= 7 else positive_days
        if last7:
            info["subs_delta_7d"] = int(sum(
                (e.get("subs_change", 0) or 0) for e in last7))
            info["views_delta_7d"] = int(sum(
                (e.get("views_change", 0) or 0) for e in last7))
            # avg_daily_views_7d: trung bình view tăng/ngày (loại bỏ ngày
            # 0 view do "today" chưa close của SB).
            valid_views = [int(e.get("views_change", 0) or 0)
                           for e in last7
                           if (e.get("views_change", 0) or 0) > 0]
            if valid_views:
                info["avg_daily_views_7d"] = int(
                    sum(valid_views) / len(valid_views))
        # Cảnh báo: subs đứng yên hoặc giảm 7d
        if (info["subs_delta_7d"] <= 0
                and max(ch_subs, sb_subs) > 1000):
            info["warnings"].append(
                f"Subs 7 ngày: {info['subs_delta_7d']:+,} (đứng yên hoặc giảm)")
        # Cảnh báo: có ngày bị ẩn/xóa video (sau filter mới phát hiện)
        if n_skip_negative > 0:
            info["warnings"].append(
                f"Phát hiện {n_skip_negative} ngày có view âm "
                f"(video bị ẩn/xoá) trong 15 ngày qua - đã loại khỏi "
                f"tổng 7d, kiểm tra YouTube Studio.")

    # 21/05 fix: SUBS — ưu tiên SB latest_subs nếu ch_subs lệch lớn (parse
    # fail Playwright: "3.36M" → 3, "21K" → 21). Lấy max của 2 nguồn để
    # đảm bảo hiển thị số đúng nhất.
    info["subs"] = max(ch_subs, sb_subs)

    # A54 (27/05 sáng — FIX hồi quy A36): patch A36 skip self_channel
    # khỏi stage_socialblade → pkl.socialblade rỗng → subs_delta_7d /
    # views_delta_7d / avg_daily_views_7d của 5/6 WL active = 0 (sai).
    # FIX: cho self_channel, override SB bằng Inside (channel_daily_metrics
    # 7 ngày gần nhất). Inside có data chính xác hơn SB cho self channel.
    # Map kênh chính → account_tag (dùng cho Inside override + video Overview).
    account_tag = ""
    try:
        from .analytics_inside import match_account_tag
        if sc:
            account_tag = match_account_tag(sc.title, sc.channel_id) or ""
    except Exception:
        account_tag = ""
    info["account_tag"] = account_tag

    try:
        from .analytics_inside import get_channel_inside
        if account_tag:
            inside_ci = get_channel_inside(account_tag, recent_days=7)
            if inside_ci and inside_ci.get("has_data"):
                daily = inside_ci.get("daily_metrics_15d") or []
                last7 = daily[-7:] if len(daily) >= 7 else daily
                if last7:
                    views_vals = [int(d.get("views_daily", 0) or 0)
                                  for d in last7]
                    views_vals = [v for v in views_vals if v >= 0]
                    if views_vals:
                        info["avg_daily_views_7d"] = int(
                            sum(views_vals) / len(views_vals))
                        info["views_delta_7d"] = sum(views_vals)
                    subs_vals = [int(d.get("subs_net", 0) or 0)
                                 for d in last7]
                    if subs_vals:
                        info["subs_delta_7d"] = sum(subs_vals)
                    # Tăng subs đếm từ Inside.last_subs_net (7d)
                    # → có thể override nếu SB rỗng
                    info["data_source"] = "inside"
    except Exception as e:
        pass  # silent fallback to SB

    # Top video hôm nay của kênh chính (sort theo views/ngày GẦN ĐÂY)
    # Ưu tiên: tính delta views vs kỳ trước → mới chính xác view/ngày hiện tại.
    # Fallback: nếu video MỚI ĐĂNG ≤14 ngày → dùng lifetime (cũng ≈ recent).
    # Skip: video CŨ (>14 ngày) mà không có data kỳ trước (vì lifetime sai).
    videos = self_res.get("videos") or []
    today_vids = []
    now_ts = _t.time()
    for v in videos:
        try:
            pub = getattr(v, "published_at", "") or ""
            views = int(getattr(v, "view_count", 0) or 0)
            title = getattr(v, "title", "") or ""
            vid = getattr(v, "video_id", "") or ""
            days_old = None
            if pub:
                d_pub = datetime.fromisoformat(pub[:10])
                days_old = max(1, (datetime.now() - d_pub).days)
            # Ưu tiên 1: delta vs kỳ trước (chính xác nhất)
            vpd = None
            vpd_kind = ""  # nhãn để hiển thị
            prev_data = prev_view_map.get(vid)
            if prev_data:
                prev_views, prev_time = prev_data
                delta_views = views - prev_views
                delta_days = (now_ts - prev_time) / 86400
                if delta_days >= 0.1 and delta_views > 0:
                    vpd = delta_views / delta_days
                    vpd_kind = "recent"
            # Ưu tiên 2: video mới ≤14 ngày → lifetime tạm chấp nhận
            if vpd is None and days_old is not None and days_old <= 14:
                vpd = views / days_old
                vpd_kind = "new_lifetime"
            # Skip: video cũ (>14d) mà không có prev data — không tính nổi
            #       view/ngày gần đây → bỏ qua, tránh hiển thị số sai lệch.
            if vpd is None:
                continue
            today_vids.append({
                "title": title, "views": views, "vpd": int(vpd),
                "vpd_kind": vpd_kind,
                "pub": pub[:10] if pub else "",
                "days_old": days_old or 0,
                "vid": vid,
            })
        except Exception:
            continue
    today_vids.sort(key=lambda v: v["vpd"], reverse=True)
    info["top_videos_today"] = today_vids[:3]

    # 3 video MỚI NHẤT — ưu tiên data page Overview (bảng video_overview,
    # data chính chủ của kênh). Fallback scrape ngách nếu chưa map account_tag.
    info["latest_videos"] = _overview_latest_videos(account_tag, limit=3)
    if not info["latest_videos"]:
        latest = sorted(
            videos, key=lambda v: getattr(v, "published_at", "") or "",
            reverse=True)[:3]
        info["latest_videos"] = [{
            "title": getattr(v, "title", "") or "",
            "video_id": getattr(v, "video_id", "") or "",
            "url": (getattr(v, "url", "") or
                    (f"https://www.youtube.com/watch?v={getattr(v, 'video_id', '')}"
                     if getattr(v, "video_id", "") else "")),
            "published_at": (getattr(v, "published_at", "") or "")[:10],
            "thumbnail": "",
            "views": int(getattr(v, "view_count", 0) or 0),
            "avg_view_duration": None,
            "watch_minutes": None,
            "subscribers": None,
            "impressions": None,
            "ctr": None,
        } for v in latest]

    # Outlier videos (view ≥3x median của kênh, ≥50K views)
    if videos:
        try:
            view_list = sorted([int(getattr(v, "view_count", 0) or 0)
                                for v in videos])
            n = len(view_list)
            median_v = view_list[n // 2] if n else 0
            for v in videos:
                views = int(getattr(v, "view_count", 0) or 0)
                if median_v > 0 and views >= median_v * 3 and views >= 50000:
                    info["outlier_videos"].append({
                        "title": getattr(v, "title", "") or "",
                        "views": views,
                        "mult": round(views / median_v, 1),
                        "channel": ch.title if ch else "",
                    })
        except Exception:
            pass

    # Strategy preview (lấy 200 ký tự đầu của chiến lược mới nhất)
    la = w.latest_analysis
    if isinstance(la, dict):
        content = la.get("content", "")
        info["strategy_preview"] = content[:250].strip()
    elif isinstance(la, str):
        info["strategy_preview"] = la[:250].strip()

    return info


def _collect_cross_niche_videos(wl_data: list, top_n: int = 15) -> list:
    """Top video bùng nổ TOÀN CÔNG TY (cross-niche). Sort theo vpd."""
    all_vids = []
    for w in wl_data:
        if not w:
            continue
        # Lấy outlier + top_videos_today
        for v in w.get("outlier_videos", []):
            all_vids.append({
                "title": v["title"],
                "views": v["views"],
                "mult": v["mult"],
                "channel": v["channel"],
                "wl_name": w["name"],
                "source": "outlier",
            })
        for v in w.get("top_videos_today", [])[:2]:
            all_vids.append({
                "title": v["title"],
                "views": v["views"],
                "vpd": v["vpd"],
                "pub": v["pub"],
                "channel": w["self_title"],
                "wl_name": w["name"],
                "source": "self_top",
            })
    # Sort: outlier (mult cao) trộn với self_top (vpd cao)
    # Đơn giản: sort theo views descending
    all_vids.sort(key=lambda v: v.get("views", 0), reverse=True)
    return all_vids[:top_n]


def _find_latest_report(wid: str, wl_name: str) -> str:
    """Tìm file HTML báo cáo mới nhất của 1 WL trong ket_qua/bao_cao_html/."""
    d = _ROOT / "ket_qua" / "bao_cao_html"
    if not d.exists():
        return ""
    # Format file: "DDMMYY <wl_name> báo cáo HHMMSS.html"
    candidates = []
    for f in d.glob(f"*{wl_name[:25]}*báo cáo*.html"):
        if "_test_" in f.name:
            continue
        candidates.append((f.stat().st_mtime, f.name))
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]
    return ""


def build_summary_data(wids: list) -> dict:
    """Payload executive summary cho API/React, dung cung logic voi HTML cu."""
    wl_data = []
    for wid in wids:
        info = _pack_wl(wid)
        if info:
            info["report_path"] = _find_latest_report(wid, info["name"])
            wl_data.append(info)

    wl_data.sort(key=lambda w: w.get("views_delta_7d", 0), reverse=True)
    cross_top_videos = _collect_cross_niche_videos(wl_data, top_n=15)

    cross_wl_opps = []
    try:
        from .cross_wl_learning import find_propagation_opportunities
        cross_wl_opps = find_propagation_opportunities(log_fn=lambda s: None)
    except Exception as e:
        print(f"  WARN: cross_wl_learning loi: {e}")

    return {
        "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "n_wl": len(wl_data),
        "total_subs": sum(w["subs"] for w in wl_data),
        "total_subs_delta_7d": sum(w["subs_delta_7d"] for w in wl_data),
        "total_views_delta_7d": sum(w["views_delta_7d"] for w in wl_data),
        "n_warnings": sum(len(w["warnings"]) for w in wl_data),
        "watchlists": wl_data,
        "cross_top_videos": cross_top_videos,
        "cross_wl_opps": cross_wl_opps[:20],
    }


# ============================================================
# Lưu lịch sử snapshot (mỗi lần WL run xong) — giống page SEO.
# Index nhẹ (id, date) + 1 file data/snapshot để list nhanh, load lẻ.
# ============================================================
_SUMMARY_HISTORY_MAX = 60


def _summary_dir() -> Path:
    d = Path.home() / ".youtube_research" / "summary_reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path() -> Path:
    return _summary_dir() / "index.json"


def _read_index() -> list:
    p = _index_path()
    if not p.exists():
        return []
    try:
        items = json.loads(p.read_text(encoding="utf-8"))
        return items if isinstance(items, list) else []
    except Exception:
        return []


def list_snapshots() -> list:
    """Metadata snapshot (không kèm data) — mới nhất trước."""
    return [{"id": it.get("id"), "date": it.get("date")}
            for it in _read_index()]


def get_snapshot(snapshot_id: str = "") -> dict | None:
    """Snapshot đầy đủ {id, date, data}. snapshot_id rỗng → bản mới nhất."""
    idx = _read_index()
    if not idx:
        return None
    meta = (idx[0] if not snapshot_id
            else next((it for it in idx if it.get("id") == snapshot_id), None))
    if not meta:
        return None
    p = _summary_dir() / f"{meta['id']}.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return {"id": meta["id"], "date": meta["date"], "data": data}


def save_snapshot(data: dict) -> dict:
    """Ghi 1 snapshot, prune quá _SUMMARY_HISTORY_MAX. Trả {id, date}."""
    now = datetime.now()
    sid = "sum_" + now.strftime("%Y%m%d_%H%M%S")
    date_s = now.strftime("%Y-%m-%d %H:%M")
    (_summary_dir() / f"{sid}.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8")
    idx = _read_index()
    idx.insert(0, {"id": sid, "date": date_s})
    keep, drop = idx[:_SUMMARY_HISTORY_MAX], idx[_SUMMARY_HISTORY_MAX:]
    _index_path().write_text(
        json.dumps(keep, ensure_ascii=False), encoding="utf-8")
    for old in drop:
        try:
            (_summary_dir() / f"{old['id']}.json").unlink(missing_ok=True)
        except Exception:
            pass
    return {"id": sid, "date": date_s}


def build_and_save_snapshot(wids: list) -> dict:
    """Dựng payload summary cho wids rồi lưu snapshot. Trả {id, date}."""
    return save_snapshot(build_summary_data(wids))


def build_summary(wids: list, out_path: str = "") -> str:
    """Tạo HTML executive summary cho list WL. Trả path file."""
    wl_data = []
    for wid in wids:
        info = _pack_wl(wid)
        if info:
            info["report_path"] = _find_latest_report(wid, info["name"])
            wl_data.append(info)

    if not wl_data:
        print("Khong co WL nao co data.")
        return ""

    # 21/05: sort wl_data theo Δ Views 7d giảm dần — kênh tăng trưởng
    # mạnh nhất lên đầu để quản lý cấp cao nhìn 1 phát thấy ai đang nóng.
    wl_data.sort(key=lambda w: w.get("views_delta_7d", 0), reverse=True)

    # Cross-niche analysis
    cross_top_videos = _collect_cross_niche_videos(wl_data, top_n=15)

    # === Cross-WL Learning (chốt 23/05): propagation opportunities ===
    cross_wl_opps = []
    try:
        from .cross_wl_learning import find_propagation_opportunities
        cross_wl_opps = find_propagation_opportunities(
            log_fn=lambda s: None)
    except Exception as e:
        print(f"  WARN: cross_wl_learning loi: {e}")

    # Total subs, total warnings — mốc 7 ngày
    total_subs = sum(w["subs"] for w in wl_data)
    total_views_delta = sum(w["views_delta_7d"] for w in wl_data)
    total_subs_delta = sum(w["subs_delta_7d"] for w in wl_data)
    n_warnings = sum(len(w["warnings"]) for w in wl_data)

    data = {
        "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "n_wl": len(wl_data),
        "total_subs": total_subs,
        "total_subs_delta_7d": total_subs_delta,
        "total_views_delta_7d": total_views_delta,
        "n_warnings": n_warnings,
        "watchlists": wl_data,
        "cross_top_videos": cross_top_videos,
        "cross_wl_opps": cross_wl_opps[:20],
    }

    # Logo base64
    logo_b64 = ""
    lp = _ROOT / "logo.png"
    if lp.exists():
        logo_b64 = base64.b64encode(lp.read_bytes()).decode()

    txt = _TEMPLATE.replace("/*LOGO*/", (
        f'<img class="logo" src="data:image/png;base64,{logo_b64}">'
        if logo_b64 else "")).replace(
        "/*DATA*/", json.dumps(data, ensure_ascii=False))

    if not out_path:
        d = _ROOT / "ket_qua" / "bao_cao_html"
        d.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%d%m%y_%H%M%S")
        out_path = str(d / f"{ts}_TONG_HOP_executive_summary.html")
    Path(out_path).write_text(txt, encoding="utf-8")
    print(f"Da tao Executive Summary: {out_path}")
    return out_path


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" type="image/png" href="/favicon.png">
<title>Bao cao tong hop - Executive Summary</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',Roboto,Arial,sans-serif;background:#f0f0f0;
color:#1a1a1a;font-size:15px;line-height:1.55}
.wrap{max-width:1080px;margin:0 auto;background:#fff;min-height:100vh}
header{background:#C8102E;color:#fff;padding:14px 22px;display:flex;
align-items:center;gap:16px}
header .logo{width:54px;height:54px;flex-shrink:0;border-radius:6px;
background:#fff;padding:3px}
header .title-block{flex:1}
header .company{font-size:12px;font-weight:600;letter-spacing:.6px;
text-transform:uppercase;opacity:.85;margin-bottom:2px}
header h1{font-size:21px;margin:0;line-height:1.25}
header .sub{font-size:12.5px;opacity:.9;margin-top:2px}
section{padding:18px 22px;border-bottom:1px solid #eee}
h2{color:#C8102E;font-size:17px;margin:0 0 12px;border-bottom:2px solid
#C8102E;padding-bottom:4px}
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;
margin:14px 0}
.kpi{background:#f7f7f7;padding:14px;border-radius:6px;text-align:center;
border-left:4px solid #C8102E}
.kpi .v{font-size:22px;font-weight:700;color:#C8102E}
.kpi .l{font-size:12px;color:#666;margin-top:4px}
.kpi.pos .v{color:#1a7a1a}.kpi.neg .v{color:#C8102E}
table{width:100%;border-collapse:collapse;margin:8px 0;font-size:13.5px}
th,td{border:1px solid #ddd;padding:7px 10px;text-align:left;
vertical-align:middle}
th{background:#C8102E;color:#fff}
tr:nth-child(even){background:#fafafa}
.num{text-align:right;font-variant-numeric:tabular-nums}
.pos{color:#1a7a1a;font-weight:600}.neg{color:#C8102E;font-weight:600}
.warn-list{background:#fff7e6;border:1px solid #ffb84d;border-radius:6px;
padding:10px 14px;margin:8px 0}
.warn-list li{margin:4px 0 4px 18px}
.warn-list b{color:#C8102E}
.video-card{background:#f7f7f7;border-radius:6px;padding:10px;margin:6px 0;
border-left:4px solid #C8102E}
.video-card .t{font-weight:600;color:#1a1a1a}
.video-card .m{font-size:12px;color:#666;margin-top:3px}
.video-card .badge{display:inline-block;background:#C8102E;color:#fff;
padding:1px 7px;border-radius:3px;font-size:11px;font-weight:600;
margin-right:6px}
a{color:#1558b0;text-decoration:none}a:hover{text-decoration:underline}
.muted{color:#888;font-style:italic;font-size:13px}
footer{text-align:center;padding:14px;color:#888;font-size:12px;
background:#fafafa}
@media (max-width:720px){
.kpi-grid{grid-template-columns:repeat(2,1fr)}
section{padding:14px}
}
</style></head>
<body>
<div class="wrap">
<header>/*LOGO*/<div class="title-block">
<div class="company">Funtime Media Corp</div>
<h1>Báo cáo tổng hợp ngày — Executive Summary</h1>
<div class="sub" id="hS"></div></div></header>

<section>
<h2>Tổng quan</h2>
<div class="kpi-grid" id="kpiGrid"></div>
</section>

<section>
<h2>📊 Tình hình từng kênh</h2>
<table id="tbWL"><thead><tr>
<th>Kênh</th><th>Trạng thái</th><th>Subs</th><th>Δ Subs 7d</th><th>Δ Views 7d</th>
<th>View/ngày KÊNH<br><small>(TB 7d, từ SB)</small></th><th>Video hot nhất hôm nay</th><th>Báo cáo chi tiết</th>
</tr></thead><tbody></tbody></table>
</section>

<section>
<h2>🔥 Top 15 video nổi bật toàn công ty hôm nay</h2>
<div id="crossTop"></div>
</section>

<section>
<h2>🔗 Cơ hội Cross-WL — propagate insight giữa các kênh</h2>
<p class="muted">Phát hiện cụm đang viral ở WL A → đề xuất WL B (có overlap audience) thử cùng cụm.</p>
<div id="crossWl"></div>
</section>

<section id="warnSection" style="display:none">
<h2>⚠️ Cảnh báo cần xử lý gấp</h2>
<div id="warnList"></div>
</section>

<section>
<h2>🧠 Tóm lược chiến lược mỗi kênh</h2>
<div id="stratList"></div>
</section>

<footer>Funtime Media Corp — Executive Summary | <span id="ft"></span></footer>
</div>

<script>
const D=/*DATA*/;
const fmt=(n)=>(+n||0).toLocaleString('vi-VN');
const sg=(n)=>{const x=+n||0;const c=x>=0?'pos':'neg';
return `<span class="${c}">${x>=0?'+':''}${fmt(x)}</span>`;};
const esc=(s)=>(s||'').toString().replace(/[&<>"]/g,
m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));

document.getElementById('hS').textContent='Ngày '+D.date+
' • '+D.n_wl+' kênh đang theo dõi';
document.getElementById('ft').textContent='Sinh '+D.date;

// KPI grid (mốc 7 ngày)
const kpiHtml=[
['n_wl','Kênh theo dõi','','muted'],
['total_subs','Tổng người đăng ký','','pos'],
['total_subs_delta_7d','Δ Subs 7 ngày','sg',''],
['total_views_delta_7d','Δ Views 7 ngày','sg',''],
].map(([k,l,sg_flag,cls])=>{
  const v=D[k]||0;
  const cl=sg_flag==='sg'?(v>=0?'pos':'neg'):(cls||'');
  const vstr=sg_flag==='sg'?sg(v):fmt(v);
  return `<div class="kpi ${cl}"><div class="v">${vstr}</div>`+
    `<div class="l">${l}</div></div>`;
}).join('');
document.getElementById('kpiGrid').innerHTML=kpiHtml;

// Bảng WL — A55 (27/05): sort ACTIVE đầu, PAUSED sau (trong nhóm sort view/ngày DESC)
const tbody=document.querySelector('#tbWL tbody');
D.watchlists.sort((a,b)=>{
  const aa=a.is_active?1:0, bb=b.is_active?1:0;
  if(aa!==bb) return bb-aa;
  return (b.avg_daily_views_7d||0)-(a.avg_daily_views_7d||0);
}).forEach(w=>{
  const topV=(w.top_videos_today&&w.top_videos_today[0])||{};
  const rp=w.report_path?`<a href="${esc(w.report_path)}" target="_blank">Mở</a>`:'<span class="muted">N/A</span>';
  // View/ngày KÊNH dùng avg_daily_views_7d (TB 7d, loại ngày 0 view),
  // fallback ÷7 nếu không có.
  const chVpd=w.avg_daily_views_7d||(
    (w.views_delta_7d||0)>0?Math.round((w.views_delta_7d||0)/7):0);
  // Video hot nhất: title + view/ngày của VIDEO ĐÓ (in nhỏ phía dưới)
  const topVHtml=topV.title?
    `<b>${esc(topV.title.slice(0,55))}</b>`+
    (topV.vpd?`<br><small class="muted">~${fmt(topV.vpd)} view/ngày của video này</small>`:''):
    '<span class="muted">-</span>';
  // A52: badge trạng thái ACTIVE/INACTIVE (R19)
  const statusBadge=w.is_active?
    '<span style="background:#27ae60;color:#fff;padding:3px 9px;border-radius:10px;font-size:11px;font-weight:700">🟢 ACTIVE</span>':
    `<span style="background:#777;color:#fff;padding:3px 9px;border-radius:10px;font-size:11px;font-weight:700" title="${esc(w.paused_reason||'')}">⏸ PAUSED</span>`;
  tbody.innerHTML+=`<tr${w.is_active?'':' style="opacity:.55"'}>
<td><b>${esc(w.self_title)}</b><br><small class="muted">${esc(w.name)}</small></td>
<td>${statusBadge}</td>
<td class="num">${fmt(w.subs)}</td>
<td class="num">${sg(w.subs_delta_7d)}</td>
<td class="num">${sg(w.views_delta_7d)}</td>
<td class="num"><b>${chVpd?fmt(chVpd):'-'}</b></td>
<td>${topVHtml}</td>
<td>${rp}</td></tr>`;
});

// Cross top videos
const ct=D.cross_top_videos||[];
const ctHtml=ct.map(v=>{
  const badge=v.source==='outlier'?
    `<span class="badge">🚀 x${v.mult}</span>`:
    `<span class="badge">📈 ${fmt(v.vpd||0)}/ngày</span>`;
  return `<div class="video-card">
<div>${badge}<span class="t">${esc(v.title)}</span></div>
<div class="m">${esc(v.channel)} • ${esc(v.wl_name)} • ${fmt(v.views)} view</div>
</div>`;
}).join('');
document.getElementById('crossTop').innerHTML=ctHtml||
'<p class="muted">Hôm nay chưa có video bùng nổ.</p>';

// === Cross-WL Opportunities ===
const cwlOpps=D.cross_wl_opps||[];
let cwlHtml='';
if(cwlOpps.length===0){
  cwlHtml='<p class="muted">Không phát hiện cơ hội propagation rõ ràng. Có thể vì 25 WL chưa đủ overlap audience, hoặc viral cluster chưa hình thành.</p>';
}else{
  cwlHtml='<div style="display:grid;gap:12px">';
  cwlOpps.forEach((o,i)=>{
    cwlHtml+='<div class="video-card" style="border-left:4px solid #6a1b9a;padding:12px 16px">'
      +'<div style="font-weight:bold;color:#6a1b9a">'+(i+1)+'. WL "'+esc(o.source_wl_name)+'" → WL "'+esc(o.target_wl_name)+'" (similarity '+o.similarity_score+')</div>'
      +'<div style="margin-top:6px"><b>Cluster viral:</b> <code>'+esc(o.viral_cluster)+'</code> ('+fmt(o.cluster_avg_vpd)+' views/ngày TB)</div>'
      +'<div style="margin-top:6px;color:#666;font-size:0.92em">'+esc(o.reason)+'</div>';
    if((o.sample_videos||[]).length){
      cwlHtml+='<div style="margin-top:8px"><b>Video mẫu:</b><ul style="margin:4px 0">';
      o.sample_videos.forEach(v=>{
        cwlHtml+='<li>'+esc(v.title)+' — '+esc(v.channel)+' ('+fmt(v.vpd)+' v/d)</li>';
      });
      cwlHtml+='</ul></div>';
    }
    cwlHtml+='</div>';
  });
  cwlHtml+='</div>';
}
document.getElementById('crossWl').innerHTML=cwlHtml;

// Cảnh báo
const allWarns=[];
D.watchlists.forEach(w=>{
  (w.warnings||[]).forEach(msg=>allWarns.push({wl:w.self_title,msg}));
});
if(allWarns.length){
  document.getElementById('warnSection').style.display='block';
  document.getElementById('warnList').innerHTML='<ul class="warn-list">'+
    allWarns.map(w=>`<li><b>${esc(w.wl)}:</b> ${esc(w.msg)}</li>`).join('')+
    '</ul>';
}

// Strategy preview
const stratList=D.watchlists.map(w=>{
  const sp=w.strategy_preview||'<span class="muted">Chưa có chiến lược</span>';
  return `<div style="margin:10px 0">
<b style="color:#C8102E">${esc(w.self_title)}</b><br>
<small>${esc(sp)}${sp.length>=250?'...':''}</small></div>`;
}).join('');
document.getElementById('stratList').innerHTML=stratList;
</script>
</body></html>
"""
