"""
Analytics Inside — query PostgreSQL (kho analytics chung của app).

Trước đây module này đọc SQLite dump (analytics.db). Từ 2026-06 dữ liệu Inside
kênh chính do cronjob của app chính sinh ra (`get_data.py` → `module_*` →
Postgres), nên module chỉ còn ĐỌC từ Postgres qua engine `python_backend.db`.
Pipeline watchlist KHÔNG còn tự fetch Inside (stage_inside đã bỏ).

Hàm chính:
- match_account_tag(channel_title, channel_id) → account_tag
- get_channel_inside(account_tag) → dict tổng hợp tất cả metrics
- get_retention_curves, get_retention_full, get_demographics, get_devices,
  get_traffic_source_trend, get_top_countries, get_thumbnail_ctr,
  get_audience_full, get_revenue_summary

Quy tắc bảo mật:
- Revenue table CHỈ truy cập qua get_revenue_summary() (kèm warning).
- Báo cáo HTML public KHÔNG nên include revenue.

Degrade an toàn: thiếu Postgres / PG_URL → mọi hàm trả rỗng, không crash.
"""
from __future__ import annotations

import re
from typing import Optional, List, Dict, Any

from sqlalchemy import text


# ============================================================
# Engine — lazy, degrade an toàn nếu không có Postgres
# ============================================================

_ENGINE = None
_ENGINE_TRIED = False
_AVAILABLE: Optional[bool] = None


def _get_engine():
    global _ENGINE, _ENGINE_TRIED
    if not _ENGINE_TRIED:
        _ENGINE_TRIED = True
        try:
            from python_backend.db import engine
            _ENGINE = engine
        except Exception:
            _ENGINE = None
    return _ENGINE


def _day_str(v) -> str:
    """DATE/datetime → 'YYYY-MM-DD' (giữ contract cũ trả chuỗi)."""
    try:
        return v.isoformat()[:10]
    except AttributeError:
        return str(v) if v is not None else ""


def is_available() -> bool:
    """True nếu Postgres analytics kết nối được."""
    global _AVAILABLE
    if _AVAILABLE is not None:
        return _AVAILABLE
    eng = _get_engine()
    if eng is None:
        _AVAILABLE = False
        return False
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        _AVAILABLE = True
    except Exception:
        _AVAILABLE = False
    return _AVAILABLE


def list_account_tags() -> List[Dict[str, Any]]:
    """Liệt kê account_tag trong videos table + video count."""
    eng = _get_engine()
    if eng is None:
        return []
    try:
        with eng.connect() as conn:
            rows = conn.execute(text(
                "SELECT account_tag, COUNT(*) FROM videos "
                "GROUP BY account_tag ORDER BY COUNT(*) DESC")).fetchall()
        return [{"account_tag": t, "video_count": int(n or 0)} for t, n in rows]
    except Exception:
        return []


def _account_tag_for_channel(channel_id: str) -> Optional[str]:
    """account_tag canonical từ UserCredential theo channel_id — đúng key mà
    cronjob get_data.py dùng để ghi mọi bảng analytics."""
    if not channel_id:
        return None
    try:
        from python_backend.api.auth.database import SessionLocal
        from python_backend.api.auth.models import UserCredential
    except Exception:
        return None
    db = SessionLocal()
    try:
        row = (
            db.query(UserCredential.account_tag)
            .filter(UserCredential.selected_channel_id == channel_id)
            .filter(UserCredential.account_tag.isnot(None))
            .order_by(UserCredential.updated_at.desc())
            .first()
        )
        return row[0] if row and row[0] else None
    except Exception:
        return None
    finally:
        db.close()


def match_account_tag(channel_title: str,
                      channel_id: str = "") -> Optional[str]:
    """Match channel → account_tag trong Postgres.

    Strategy:
    1. UserCredential theo channel_id (canonical, đúng key cronjob ghi).
    2. traffic_source_daily.channel_id.
    3. Match title exact → fuzzy trên videos.account_tag.
    """
    if not channel_title and not channel_id:
        return None

    tag = _account_tag_for_channel(channel_id)
    if tag:
        return tag

    eng = _get_engine()
    if eng is None:
        return None
    try:
        with eng.connect() as conn:
            if channel_id:
                row = conn.execute(text(
                    "SELECT account_tag FROM traffic_source_daily "
                    "WHERE channel_id = :cid LIMIT 1"),
                    {"cid": channel_id}).fetchone()
                if row:
                    return row[0]
            if channel_title:
                tag_guess = re.sub(r"[^A-Za-z0-9]+", "_",
                                   channel_title).strip("_")
                row = conn.execute(text(
                    "SELECT account_tag FROM videos "
                    "WHERE account_tag = :g LIMIT 1"),
                    {"g": tag_guess}).fetchone()
                if row:
                    return row[0]
                title_norm = re.sub(r"[^a-z0-9]", "", channel_title.lower())
                rows = conn.execute(text(
                    "SELECT DISTINCT account_tag FROM videos")).fetchall()
                for (t,) in rows:
                    if re.sub(r"[^a-z0-9]", "", (t or "").lower()) == title_norm:
                        return t
        return None
    except Exception:
        return None


# ============================================================
# 1. CHANNEL SUMMARY — Tổng hợp 1 lần
# ============================================================

def get_channel_inside(account_tag: str,
                       recent_days: int = 30) -> Dict[str, Any]:
    """Trả dict tổng hợp tất cả metrics CỦA kênh trong Postgres.

    Returns:
        {
          'account_tag', 'video_count',
          'demographics': [{gender, age_group, pct}],
          'devices': {device: pct},
          'traffic_sources_recent': [{source, views, pct}],
          'total_views_recent',
          'top_countries': [{country, views, pct}],
          'last_views', 'last_subs_gained', 'last_subs_lost', 'last_subs_net',
          'avg_avd_seconds', 'avg_thumbnail_ctr',
          'daily_metrics_15d': [{day, subs_net, views_daily}],
          'has_data': bool,
        }
    """
    out = {"account_tag": account_tag, "has_data": False}
    if not account_tag:
        return out
    eng = _get_engine()
    if eng is None:
        return out
    try:
        with eng.connect() as conn:
            # 1. Video count
            row = conn.execute(text(
                "SELECT COUNT(*) FROM videos WHERE account_tag = :tag"),
                {"tag": account_tag}).fetchone()
            out["video_count"] = int(row[0] or 0) if row else 0
            if out["video_count"] == 0:
                return out
            out["has_data"] = True

            # 2. Demographics — entry MỚI NHẤT (max end_date)
            rows = conn.execute(text(
                "SELECT gender, age_group, viewer_percentage "
                "FROM audience_demographics "
                "WHERE account_tag = :tag AND end_date = ("
                "  SELECT MAX(end_date) FROM audience_demographics "
                "  WHERE account_tag = :tag) "
                "ORDER BY viewer_percentage DESC"),
                {"tag": account_tag}).fetchall()
            demo = []
            for g, a, pct in rows:
                try:
                    pct_f = float(pct)
                except Exception:
                    continue
                if pct_f > 0:
                    demo.append({"gender": g, "age_group": a, "pct": pct_f})
            out["demographics"] = demo[:15]

            # 3. Devices — entry MỚI NHẤT
            rows = conn.execute(text(
                "SELECT device_type, viewer_percentage FROM audience_devices "
                "WHERE account_tag = :tag AND end_date = ("
                "  SELECT MAX(end_date) FROM audience_devices "
                "  WHERE account_tag = :tag) "
                "ORDER BY viewer_percentage DESC"),
                {"tag": account_tag}).fetchall()
            dev = {}
            for d, pct in rows:
                try:
                    dev[d] = float(pct)
                except Exception:
                    pass
            out["devices"] = dev

            # 4. Traffic sources (recent N days)
            rows = conn.execute(text(
                "SELECT source, SUM(views) FROM traffic_source_daily "
                "WHERE account_tag = :tag "
                "AND day >= CURRENT_DATE - (:days * INTERVAL '1 day') "
                "GROUP BY source ORDER BY SUM(views) DESC"),
                {"tag": account_tag, "days": recent_days}).fetchall()
            ts = []
            total_views = 0
            for source, views in rows:
                v = int(views or 0)
                ts.append([source, v])
                total_views += v
            if total_views > 0:
                ts = [{"source": s, "views": v,
                       "pct": round(100 * v / total_views, 1)}
                      for s, v in ts]
            else:
                ts = []
            out["traffic_sources_recent"] = ts
            out["total_views_recent"] = total_views

            # 5. Top countries — entry mới nhất, GROUP dedup
            rows = conn.execute(text(
                "SELECT country, SUM(views) FROM geography_country_metrics "
                "WHERE account_tag = :tag AND end_date = ("
                "  SELECT MAX(end_date) FROM geography_country_metrics "
                "  WHERE account_tag = :tag) "
                "GROUP BY country ORDER BY SUM(views) DESC LIMIT 10"),
                {"tag": account_tag}).fetchall()
            countries = []
            country_total = 0
            for c, v in rows:
                vi = int(v or 0)
                countries.append([c, vi])
                country_total += vi
            if country_total > 0:
                countries = [{"country": c, "views": v,
                              "pct": round(100 * v / country_total, 1)}
                             for c, v in countries]
            else:
                countries = []
            out["top_countries"] = countries

            # 6. Channel daily metrics (recent N days)
            row = conn.execute(text(
                "SELECT SUM(views), SUM(subscribers_gained), "
                "SUM(subscribers_lost) FROM channel_daily_metrics "
                "WHERE account_tag = :tag "
                "AND day >= CURRENT_DATE - (:days * INTERVAL '1 day')"),
                {"tag": account_tag, "days": recent_days}).fetchone()
            out["last_views"] = int(row[0] or 0) if row and row[0] else 0
            out["last_subs_gained"] = int(row[1] or 0) if row and row[1] else 0
            out["last_subs_lost"] = int(row[2] or 0) if row and row[2] else 0
            out["last_subs_net"] = out["last_subs_gained"] - out["last_subs_lost"]

            # 7. Video overview AVD (avg) — chỉ video > 1K view
            row = conn.execute(text(
                "SELECT AVG(average_view_duration_seconds) FROM video_overview "
                "WHERE account_tag = :tag AND views > 1000"),
                {"tag": account_tag}).fetchone()
            out["avg_avd_seconds"] = float(row[0] or 0) if row and row[0] else 0.0

            # 8. Thumbnail CTR — TB cho video có impressions > 100
            row = conn.execute(text(
                "SELECT AVG(thumbnail_ctr) FROM video_thumbnail_daily "
                "WHERE account_tag = :tag AND thumbnail_impressions > 100"),
                {"tag": account_tag}).fetchone()
            out["avg_thumbnail_ctr"] = float(row[0] or 0) if row and row[0] else 0.0

            # 9. Daily metrics 15 ngày gần nhất (views DELTA — không âm)
            rows = conn.execute(text(
                "SELECT day, subscribers_gained - subscribers_lost AS subs_net, "
                "views AS views_daily FROM channel_daily_metrics "
                "WHERE account_tag = :tag ORDER BY day DESC LIMIT 15"),
                {"tag": account_tag}).fetchall()
            daily = [{"day": _day_str(r[0]), "subs_net": int(r[1] or 0),
                      "views_daily": max(0, int(r[2] or 0))}
                     for r in reversed(rows)]
            out["daily_metrics_15d"] = daily

        return out
    except Exception:
        return out


# ============================================================
# 2. RETENTION CURVES — Top video
# ============================================================

def get_retention_curves(account_tag: str, top_n: int = 5,
                         min_views: int = 5000,
                         order_by: str = "views") -> List[Dict[str, Any]]:
    """Lấy retention curve cho N video.

    order_by:
      - "views" (mặc định): top N nhiều view nhất
      - "published": N video MỚI NHẤT theo published_at (video <48h chưa có
        retention vẫn trả với curve=[] + retention_pending=True)
    """
    eng = _get_engine()
    if eng is None:
        return []
    try:
        with eng.connect() as conn:
            if order_by == "published":
                videos = conn.execute(text(
                    "SELECT video_id, title, views, published_at FROM videos "
                    "WHERE account_tag = :tag AND views >= :mv "
                    "ORDER BY published_at DESC LIMIT :n"),
                    {"tag": account_tag, "mv": min_views,
                     "n": top_n}).fetchall()
            else:
                videos = conn.execute(text(
                    "SELECT DISTINCT ar.video_id, v.title, v.views, "
                    "v.published_at FROM audience_retention ar "
                    "JOIN videos v ON v.video_id = ar.video_id "
                    "WHERE ar.account_tag = :tag AND v.views >= :mv "
                    "ORDER BY v.views DESC LIMIT :n"),
                    {"tag": account_tag, "mv": min_views,
                     "n": top_n}).fetchall()

            out = []
            for vid, title, views, published_at in videos:
                pts = conn.execute(text(
                    "SELECT elapsed_video_time_ratio, audience_watch_ratio, "
                    "relative_retention_performance FROM audience_retention "
                    "WHERE account_tag = :tag AND video_id = :vid "
                    "ORDER BY elapsed_video_time_ratio ASC"),
                    {"tag": account_tag, "vid": vid}).fetchall()
                curve = []
                for e, w, rp in pts:
                    try:
                        curve.append([float(e), float(w),
                                      float(rp) if rp else 0])
                    except Exception:
                        continue
                if not curve:
                    out.append({
                        "video_id": vid,
                        "title": title or "",
                        "views": int(views or 0),
                        "published_at": _day_str(published_at),
                        "curve": [],
                        "avg_retention": 0,
                        "drop_points": [],
                        "n_points": 0,
                        "retention_pending": True,
                    })
                    continue
                avg_r = sum(c[1] for c in curve) / len(curve)
                drops = []
                for i in range(1, len(curve)):
                    d = curve[i - 1][1] - curve[i][1]
                    if d > 0.05:
                        drops.append({
                            "at_pct": round(curve[i][0] * 100, 1),
                            "drop_pct": round(d * 100, 1),
                        })
                out.append({
                    "video_id": vid,
                    "title": title or "",
                    "views": int(views or 0),
                    "published_at": _day_str(published_at),
                    "curve": curve,
                    "avg_retention": round(avg_r * 100, 1),
                    "drop_points": drops[:5],
                    "n_points": len(curve),
                    "retention_pending": False,
                })
            return out
    except Exception:
        return []


# ============================================================
# 3. THUMBNAIL CTR LEADERBOARD
# ============================================================

def get_thumbnail_ctr_top(account_tag: str, top_n: int = 10,
                          min_impressions: int = 500) -> List[Dict[str, Any]]:
    """Top N video theo CTR thumbnail TB.

    alias 'ctr_avg' (KHÔNG dùng 'ctr') vì videos.ctr cũng có cột.
    """
    eng = _get_engine()
    if eng is None:
        return []
    try:
        with eng.connect() as conn:
            rows = conn.execute(text(
                "SELECT vtd.video_id, v.title, "
                "  SUM(vtd.thumbnail_impressions) AS imp, "
                "  AVG(vtd.thumbnail_ctr) AS ctr_avg "
                "FROM video_thumbnail_daily vtd "
                "JOIN videos v ON v.video_id = vtd.video_id "
                "WHERE vtd.account_tag = :tag "
                "GROUP BY vtd.video_id, v.title "
                "HAVING SUM(vtd.thumbnail_impressions) >= :mi "
                "  AND AVG(vtd.thumbnail_ctr) > 0 "
                "ORDER BY ctr_avg DESC LIMIT :n"),
                {"tag": account_tag, "mi": min_impressions,
                 "n": top_n}).fetchall()
        return [{"video_id": vid, "title": title or "",
                 "impressions": int(imp or 0),
                 "ctr": round(float(ctr_avg or 0) * 100, 2)}
                for vid, title, imp, ctr_avg in rows]
    except Exception:
        return []


# ============================================================
# 4. REVENUE — Sensitive, chỉ trả khi gọi rõ ràng
# ============================================================

def get_revenue_summary(account_tag: str,
                        recent_days: int = 30) -> Dict[str, Any]:
    """Tổng hợp revenue. CHỈ gọi khi cần (app desktop, KHÔNG báo cáo public).

    Returns:
        {'total_revenue', 'ad_revenue', 'avg_rpm', 'avg_cpm',
         'monetized_playbacks', 'days_with_data'}
    """
    eng = _get_engine()
    if eng is None:
        return {}
    try:
        with eng.connect() as conn:
            row = conn.execute(text(
                "SELECT SUM(estimated_revenue), SUM(ad_revenue), "
                "AVG(rpm), AVG(cpm), SUM(monetized_playbacks), COUNT(*) "
                "FROM revenue_daily "
                "WHERE account_tag = :tag "
                "AND day >= CURRENT_DATE - (:days * INTERVAL '1 day')"),
                {"tag": account_tag, "days": recent_days}).fetchone()
        if not row or row[0] is None:
            return {}
        return {
            "total_revenue": round(float(row[0] or 0), 2),
            "ad_revenue": round(float(row[1] or 0), 2),
            "avg_rpm": round(float(row[2] or 0), 3),
            "avg_cpm": round(float(row[3] or 0), 3),
            "monetized_playbacks": int(row[4] or 0),
            "days_with_data": int(row[5] or 0),
        }
    except Exception:
        return {}


# ============================================================
# 5. ASSESS — Đánh giá traffic source vs benchmark ngách
# ============================================================

def assess_traffic_source(traffic_sources: list) -> Dict[str, Any]:
    """Đánh giá phân bố traffic source so với benchmark.

    Returns: {'health': 'good'|'warn'|'bad', 'issues': [list str]}
    """
    if not traffic_sources:
        return {"health": "warn", "issues": ["Không có data traffic source"]}
    ts = {item["source"]: item["pct"] for item in traffic_sources}
    issues = []

    search = ts.get("YT_SEARCH", 0)
    if search < 5:
        issues.append(f"YT_SEARCH chỉ {search}% — keyword/title yếu, "
                      "không ranking trên search.")
    elif search > 50:
        issues.append(f"YT_SEARCH {search}% quá cao — kênh phụ thuộc "
                      "search, suggested/browse yếu.")

    suggested = ts.get("RELATED_VIDEO", 0) + ts.get("SUGGESTED", 0)
    if suggested < 15:
        issues.append(f"Suggested chỉ {suggested}% — algorithm không đẩy. "
                      "Cần tăng CTR/AVD để được đề xuất.")

    browse = ts.get("YT_CHANNEL", 0) + ts.get("BROWSE", 0)
    if browse < 5:
        issues.append(f"Browse {browse}% — kênh ít sub loyalty / "
                      "thiếu subscribers active.")

    external = ts.get("EXT_URL", 0) + ts.get("EXTERNAL", 0)
    if external > 30:
        issues.append(f"External {external}% quá cao — kênh phụ thuộc "
                      "traffic ngoài YouTube, organic yếu.")

    end = ts.get("END_SCREEN", 0)
    if end < 1:
        issues.append("END_SCREEN <1% — chưa tận dụng End Screen "
                      "(thiếu link sang video tiếp).")

    shorts = ts.get("SHORTS", 0)
    if shorts > 0 and shorts < 5:
        issues.append(f"Shorts traffic {shorts}% — nên đẩy mạnh Shorts "
                      "để mở rộng audience.")

    if not issues:
        return {"health": "good", "issues": []}
    if len(issues) <= 2:
        return {"health": "warn", "issues": issues}
    return {"health": "bad", "issues": issues}


# ============================================================
# 6. TRAFFIC SOURCE — Trends + Top video per source
# ============================================================

def get_traffic_source_trend(account_tag: str,
                             periods: list = (7, 30, 90)) -> Dict[str, Any]:
    """Trends traffic source — so sánh 7d / 30d / 90d (velocity views/ngày)."""
    eng = _get_engine()
    if eng is None:
        return {}
    try:
        result = {"periods": list(periods), "sources_data": {}}
        with eng.connect() as conn:
            for p in periods:
                rows = conn.execute(text(
                    "SELECT source, SUM(views) FROM traffic_source_daily "
                    "WHERE account_tag = :tag "
                    "AND day >= CURRENT_DATE - (:p * INTERVAL '1 day') "
                    "GROUP BY source"),
                    {"tag": account_tag, "p": p}).fetchall()
                for src, views in rows:
                    v = int(views or 0)
                    if src not in result["sources_data"]:
                        result["sources_data"][src] = {}
                    result["sources_data"][src][f"{p}d"] = v
        result["velocity"] = {}
        for src, vals in result["sources_data"].items():
            result["velocity"][src] = {
                f"{p}d": (vals.get(f"{p}d", 0) / p) for p in periods
            }
        result["trend"] = {}
        for src, vels in result["velocity"].items():
            v7 = vels.get("7d", 0)
            v30 = vels.get("30d", 0)
            result["trend"][src] = round(100 * (v7 - v30) / v30, 1) if v30 > 0 else 0
        return result
    except Exception:
        return {}


def get_top_videos_per_source(account_tag: str,
                              top_n_videos: int = 5,
                              top_n_sources: int = 6,
                              days: int = 30) -> Dict[str, list]:
    """Top sources với total views (traffic_source_daily không có video_id)."""
    eng = _get_engine()
    if eng is None:
        return {}
    try:
        with eng.connect() as conn:
            sources = [r[0] for r in conn.execute(text(
                "SELECT source FROM traffic_source_daily "
                "WHERE account_tag = :tag "
                "AND day >= CURRENT_DATE - (:days * INTERVAL '1 day') "
                "GROUP BY source ORDER BY SUM(views) DESC LIMIT :n"),
                {"tag": account_tag, "days": days,
                 "n": top_n_sources}).fetchall()]
            result = {}
            for src in sources:
                row = conn.execute(text(
                    "SELECT SUM(views) FROM traffic_source_daily "
                    "WHERE account_tag = :tag AND source = :src "
                    "AND day >= CURRENT_DATE - (:days * INTERVAL '1 day')"),
                    {"tag": account_tag, "src": src,
                     "days": days}).fetchone()
                result[src] = int(row[0] or 0) if row and row[0] else 0
        return result
    except Exception:
        return {}


# ============================================================
# 7. RETENTION — Full data + segment analysis
# ============================================================

def get_retention_full(account_tag: str, top_n: int = 5,
                       min_views: int = 50,
                       order_by: str = "published") -> List[Dict[str, Any]]:
    """Retention curve FULL cho N video + meta (like/cmt/ctr) + segment + AI."""
    curves = get_retention_curves(account_tag, top_n=top_n,
                                   min_views=min_views, order_by=order_by)
    if not curves:
        return curves
    eng = _get_engine()
    vids = [c["video_id"] for c in curves]
    if eng is None or not vids:
        for c in curves:
            c["segments"] = _compute_retention_segments(c.get("curve") or [])
            c["ai_analysis"] = _video_retention_ai(c)
        return curves
    try:
        with eng.connect() as conn:
            rows = conn.execute(text(
                "SELECT video_id, likes, comments, duration FROM videos "
                "WHERE account_tag = :tag AND video_id = ANY(:vids)"),
                {"tag": account_tag, "vids": vids}).fetchall()
            meta = {r[0]: {"likes": r[1], "comments": r[2],
                           "duration": r[3]} for r in rows}
            try:
                ctr_rows = conn.execute(text(
                    "SELECT vtd.video_id, "
                    "  SUM(vtd.thumbnail_impressions) AS imp, "
                    "  SUM(vtd.thumbnail_impressions * vtd.thumbnail_ctr) "
                    "  / NULLIF(SUM(vtd.thumbnail_impressions), 0) AS ctr_w "
                    "FROM video_thumbnail_daily vtd "
                    "JOIN videos v ON v.video_id = vtd.video_id "
                    "  AND v.account_tag = vtd.account_tag "
                    "WHERE vtd.account_tag = :tag "
                    "  AND vtd.video_id = ANY(:vids) "
                    "  AND vtd.day >= v.published_at "
                    "GROUP BY vtd.video_id"),
                    {"tag": account_tag, "vids": vids}).fetchall()
                for vid, imp, ctr_w in ctr_rows:
                    imp_val = int(imp or 0)
                    ctr_val = float(ctr_w or 0)
                    if imp_val < 100:
                        imp_val = None
                        ctr_val = None
                    if vid in meta:
                        meta[vid]["impressions"] = imp_val
                        meta[vid]["ctr"] = ctr_val
                    else:
                        meta[vid] = {"impressions": imp_val, "ctr": ctr_val}
            except Exception:
                pass
        for c in curves:
            c.update(meta.get(c["video_id"], {}))
            c["segments"] = _compute_retention_segments(c.get("curve") or [])
            c["ai_analysis"] = _video_retention_ai(c)
        return curves
    except Exception:
        for c in curves:
            c["segments"] = _compute_retention_segments(c.get("curve") or [])
            c["ai_analysis"] = _video_retention_ai(c)
        return curves


def _video_retention_ai(video: Dict[str, Any]) -> str:
    """Sinh AI text rule-based cho 1 video: chẩn đoán retention + action."""
    if video.get("retention_pending"):
        return ("⏳ Retention curve đang được YouTube Analytics process "
                "(video mới <48h). Data đầy đủ sẽ có trong daily run kế "
                "tiếp. View/Like/Cmt đã cập nhật hôm nay từ Data API.")
    segs = video.get("segments") or {}
    avg = video.get("avg_retention", 0) or 0
    views = video.get("views", 0) or 0
    likes = video.get("likes", 0) or 0
    comments = video.get("comments", 0) or 0
    ctr = video.get("ctr", 0) or 0
    drops = video.get("drop_points") or []
    parts = []
    if avg >= 50:
        parts.append("✅ Retention XUẤT SẮC (TB ≥50%) — giữ format hiện tại.")
    elif avg >= 40:
        parts.append("✅ Retention TỐT (TB ≥40%) — đạt mục tiêu YouTube.")
    elif avg >= 25:
        parts.append(f"⚠️ Retention TB {avg}% — dưới mục tiêu 40%, cần "
                     "fix hook hoặc pacing.")
    else:
        parts.append(f"🔴 Retention KÉM {avg}% — viewer bỏ sớm, audit "
                     "URGENT.")
    weak = segs.get("weakest_segment", "")
    weak_map = {
        "hook": "Hook 0-10% YẾU — quay lại intro 10s đầu (test hook động "
                "thay tĩnh).",
        "early": "Early 10-50% drop — pacing chậm, thêm cut nhanh + b-roll.",
        "mid": "Mid 50-90% sag — boost moment ở giữa (reveal/twist/visual).",
    }
    if weak in weak_map:
        parts.append(f"📉 {weak_map[weak]}")
    if ctr > 0:
        ctr_pct = ctr * 100 if ctr < 1 else ctr
        if ctr_pct >= 10:
            parts.append(f"✅ CTR {ctr_pct:.1f}% TỐT (>10%).")
        elif ctr_pct >= 6:
            parts.append(f"⚠️ CTR {ctr_pct:.1f}% TB — thử thumbnail "
                         "face-centered + text 100px.")
        else:
            parts.append(f"🔴 CTR {ctr_pct:.1f}% KÉM — thumbnail KHÔNG "
                         "attract, revamp ngay.")
    if views > 100:
        eng_rate = (likes + comments) * 100 / views
        if eng_rate >= 3:
            parts.append(f"✅ Engagement {eng_rate:.1f}% TỐT (≥3%).")
        elif eng_rate >= 1:
            parts.append(f"⚠️ Engagement {eng_rate:.1f}% TB — thêm CTA cuối "
                         "video (Comment / Like).")
        else:
            parts.append(f"🔴 Engagement {eng_rate:.1f}% RẤT THẤP — viewer "
                         "không tương tác.")
    big_drops = [d for d in drops if (d.get("drop_pct") or 0) >= 10]
    if big_drops:
        d = big_drops[0]
        parts.append(f"⚠️ DROP LỚN tại {d['at_pct']}%: -{d['drop_pct']}% "
                     "— xem moment đó có sai hook/CTA bị skip.")
    return " ".join(parts)


def _compute_retention_segments(curve: list) -> Dict[str, Any]:
    """Phân tích retention curve theo 4 segments (hook/early/mid/outro)."""
    if not curve:
        return {}
    segs = {"hook": [], "early": [], "mid": [], "outro": []}
    for e, w, rp in curve:
        if e <= 0.1:
            segs["hook"].append(w)
        elif e <= 0.5:
            segs["early"].append(w)
        elif e <= 0.9:
            segs["mid"].append(w)
        else:
            segs["outro"].append(w)
    out = {}
    for k, vals in segs.items():
        out[f"{k}_retention"] = (round(100 * sum(vals) / len(vals), 1)
                                 if vals else 0)
    out["hook_drop"] = round(100 - out["hook_retention"], 1)
    seg_score = {k: out[f"{k}_retention"] for k in ["hook", "early", "mid"]}
    out["weakest_segment"] = min(seg_score, key=seg_score.get)
    return out


# ============================================================
# 8. THUMBNAIL CTR — Worst + correlation
# ============================================================

def get_thumbnail_ctr_worst(account_tag: str, top_n: int = 10,
                            min_impressions: int = 500) -> List[Dict[str, Any]]:
    """Worst N video theo CTR thumbnail (CẦN SỬA THUMBNAIL)."""
    eng = _get_engine()
    if eng is None:
        return []
    try:
        with eng.connect() as conn:
            rows = conn.execute(text(
                "SELECT vtd.video_id, v.title, "
                "  SUM(vtd.thumbnail_impressions) AS imp, "
                "  AVG(vtd.thumbnail_ctr) AS ctr_avg "
                "FROM video_thumbnail_daily vtd "
                "JOIN videos v ON v.video_id = vtd.video_id "
                "WHERE vtd.account_tag = :tag "
                "GROUP BY vtd.video_id, v.title "
                "HAVING SUM(vtd.thumbnail_impressions) >= :mi "
                "  AND AVG(vtd.thumbnail_ctr) > 0 "
                "ORDER BY ctr_avg ASC LIMIT :n"),
                {"tag": account_tag, "mi": min_impressions,
                 "n": top_n}).fetchall()
        return [{"video_id": vid, "title": title or "",
                 "impressions": int(imp or 0),
                 "ctr": round(float(ctr_avg or 0) * 100, 2)}
                for vid, title, imp, ctr_avg in rows]
    except Exception:
        return []


def get_ctr_correlation(account_tag: str) -> Dict[str, Any]:
    """Phân tích CTR vs views — có tương quan không?"""
    eng = _get_engine()
    if eng is None:
        return {}
    try:
        with eng.connect() as conn:
            rows = conn.execute(text(
                "SELECT v.video_id, v.views AS views_int, "
                "  AVG(vtd.thumbnail_ctr) AS ctr_avg "
                "FROM videos v "
                "JOIN video_thumbnail_daily vtd ON vtd.video_id = v.video_id "
                "WHERE vtd.account_tag = :tag "
                "GROUP BY v.video_id, v.views "
                "HAVING SUM(vtd.thumbnail_impressions) >= 500 "
                "  AND v.views > 0 AND AVG(vtd.thumbnail_ctr) > 0"),
                {"tag": account_tag}).fetchall()
        if len(rows) < 3:
            return {}
        high_view = sorted(rows, key=lambda x: -x[1])[:max(5, len(rows) // 4)]
        low_view = sorted(rows, key=lambda x: x[1])[:max(5, len(rows) // 4)]
        avg_ctr_high = sum(r[2] for r in high_view) / len(high_view) * 100
        avg_ctr_low = sum(r[2] for r in low_view) / len(low_view) * 100
        total_avg = sum(r[2] for r in rows) / len(rows) * 100
        return {
            "n_videos": len(rows),
            "avg_ctr_all": round(total_avg, 2),
            "avg_ctr_high_view_videos": round(avg_ctr_high, 2),
            "avg_ctr_low_view_videos": round(avg_ctr_low, 2),
            "ctr_lift": round(avg_ctr_high - avg_ctr_low, 2),
        }
    except Exception:
        return {}


# ============================================================
# 9. AUDIENCE — Cross-analysis
# ============================================================

def get_audience_full(account_tag: str) -> Dict[str, Any]:
    """Audience profile đầy đủ + insight."""
    eng = _get_engine()
    if eng is None:
        return {}
    try:
        with eng.connect() as conn:
            rows = conn.execute(text(
                "SELECT gender, age_group, viewer_percentage "
                "FROM audience_demographics "
                "WHERE account_tag = :tag AND end_date = ("
                "  SELECT MAX(end_date) FROM audience_demographics "
                "  WHERE account_tag = :tag) "
                "ORDER BY viewer_percentage DESC"),
                {"tag": account_tag}).fetchall()
            demo = []
            for g, a, p in rows:
                if p and p > 0:
                    demo.append({"gender": g, "age_group": a, "pct": float(p)})

            rows = conn.execute(text(
                "SELECT device_type, viewer_percentage FROM audience_devices "
                "WHERE account_tag = :tag AND end_date = ("
                "  SELECT MAX(end_date) FROM audience_devices "
                "  WHERE account_tag = :tag)"),
                {"tag": account_tag}).fetchall()
            devices = {d: float(p) for d, p in rows if p}

            rows = conn.execute(text(
                "SELECT country, SUM(views) FROM geography_country_metrics "
                "WHERE account_tag = :tag AND end_date = ("
                "  SELECT MAX(end_date) FROM geography_country_metrics "
                "  WHERE account_tag = :tag) "
                "GROUP BY country ORDER BY SUM(views) DESC LIMIT 15"),
                {"tag": account_tag}).fetchall()
            countries = []
            total_v = 0
            for c, v in rows:
                vi = int(v or 0)
                countries.append([c, vi])
                total_v += vi
            if total_v > 0:
                countries = [{"country": c, "views": v,
                              "pct": round(100 * v / total_v, 1)}
                             for c, v in countries]

        insights = []
        if demo:
            by_age = {}
            for d in demo:
                by_age[d["age_group"]] = by_age.get(d["age_group"], 0) + d["pct"]
            top_age = max(by_age.items(), key=lambda x: x[1])
            by_gender = {}
            for d in demo:
                by_gender[d["gender"]] = by_gender.get(d["gender"], 0) + d["pct"]
            top_gender = max(by_gender.items(), key=lambda x: x[1])
            insights.append(
                f"Audience chính: {top_gender[0]} {top_gender[1]:.0f}% + "
                f"độ tuổi {top_age[0]} {top_age[1]:.0f}%."
            )
        if devices.get("MOBILE", 0) > 90:
            insights.append(
                f"MOBILE {devices['MOBILE']:.0f}% — thumbnail/text phải "
                "tối ưu cho màn nhỏ, mặt to, contrast cao.")
        elif devices.get("MOBILE", 0) < 50 and devices:
            insights.append(
                "Mobile <50% — audience xem trên desktop/TV nhiều, "
                "có thể làm video dài hơn.")
        if countries:
            top3_pct = sum(c["pct"] for c in countries[:3])
            if top3_pct > 70:
                insights.append(
                    f"Top 3 quốc gia {countries[0]['country']}/"
                    f"{countries[1]['country']}/"
                    f"{countries[2]['country']} chiếm {top3_pct:.0f}% — "
                    "audience tập trung, dễ target ads + caption đa ngôn ngữ.")
            else:
                insights.append(
                    f"Audience phân tán {len(countries)}+ quốc gia — "
                    "khó target ads, cần multi-language caption.")
            high_cpm = {"US", "GB", "AU", "CA", "DE", "FR", "JP", "KR"}
            cpm_pct = sum(c["pct"] for c in countries if c["country"] in high_cpm)
            if cpm_pct > 30:
                insights.append(
                    f"{cpm_pct:.0f}% view từ countries CPM cao "
                    "(US/EU/JP/KR) → revenue tốt.")
            else:
                insights.append(
                    f"Chỉ {cpm_pct:.0f}% view từ countries CPM cao — "
                    "revenue ngạch thấp dù view nhiều.")

        return {
            "demographics": demo[:15],
            "devices": devices,
            "countries": countries,
            "insights": insights,
        }
    except Exception:
        return {}


# ============================================================
# Original assess_demographics (kept)
# ============================================================

def assess_demographics(demographics: list,
                        persona_age_range: tuple = None) -> Dict[str, Any]:
    """Đánh giá demographics. Trả {'health', 'top_age_group', 'top_gender',
    'note'}."""
    if not demographics:
        return {"health": "warn", "note": "Không có data demographics"}
    by_age = {}
    by_gender = {}
    for d in demographics:
        age = d.get("age_group", "")
        gen = d.get("gender", "")
        pct = d.get("pct", 0)
        by_age[age] = by_age.get(age, 0) + pct
        by_gender[gen] = by_gender.get(gen, 0) + pct
    top_age = max(by_age.items(), key=lambda x: x[1])[0] if by_age else ""
    top_gen = max(by_gender.items(), key=lambda x: x[1])[0] if by_gender else ""
    return {
        "health": "good",
        "top_age_group": top_age,
        "top_age_pct": round(by_age.get(top_age, 0), 1),
        "top_gender": top_gen,
        "top_gender_pct": round(by_gender.get(top_gen, 0), 1),
        "note": f"Top: {top_gen} {top_age} ({by_age.get(top_age, 0):.1f}%)",
    }
