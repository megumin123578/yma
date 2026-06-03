"""
Analytics Inside — query SQLite cache (từ dump YouTube Studio Analytics).

Module ĐƯỢC đóng gói vào exe (từ 22/05 — phần mềm tự chạy cho nhân viên).
Cache file: <inside_data_dir>/cache/analytics.db — inside_data_dir đọc
từ config, mặc định D:\\YouTube_Analytics_Inside (máy khác chỉnh lại).
Bản thân file analytics.db (data) vẫn KHÔNG nằm trong exe.

Hàm chính:
- match_account_tag(channel_title) → account_tag tự match theo tên
- get_channel_inside(account_tag) → dict tổng hợp tất cả metrics
- get_retention_curves, get_demographics, get_devices,
  get_traffic_sources, get_top_countries, get_thumbnail_ctr,
  get_video_overview_inside, get_revenue_summary

Quy tắc bảo mật:
- Revenue table CHỈ truy cập qua get_revenue_summary() (kèm warning).
- Báo cáo HTML public KHÔNG nên include revenue.
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any


_DEFAULT_INSIDE_DIR = r"D:\YouTube_Analytics_Inside"


def cache_db() -> Path:
    """Đường dẫn analytics.db — đọc từ config (inside_data_dir).

    Máy khác chỉ cần chỉnh inside_data_dir trong cấu hình là trỏ đúng.
    """
    try:
        try:
            from .config import load_config
        except ImportError:
            from .config import load_config
        d = (load_config().get("inside_data_dir") or "").strip()
        if d:
            return Path(d) / "cache" / "analytics.db"
    except Exception:
        pass
    return Path(_DEFAULT_INSIDE_DIR) / "cache" / "analytics.db"


# Giữ tên cũ cho tương thích ngược (vài chỗ import CACHE_DB)
CACHE_DB = cache_db()


def is_available() -> bool:
    """True nếu cache DB tồn tại."""
    db = cache_db()
    return db.exists() and db.stat().st_size > 0


def _connect():
    db = cache_db()
    if not (db.exists() and db.stat().st_size > 0):
        return None
    return sqlite3.connect(str(db))


def list_account_tags() -> List[Dict[str, Any]]:
    """Liệt kê tất cả account_tag trong videos table + video count."""
    conn = _connect()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute("SELECT account_tag, COUNT(*) FROM videos "
                    "GROUP BY account_tag ORDER BY COUNT(*) DESC")
        return [{"account_tag": t, "video_count": n} for t, n in cur.fetchall()]
    finally:
        conn.close()


def match_account_tag(channel_title: str,
                       channel_id: str = "") -> Optional[str]:
    """Match channel_title hoặc channel_id với account_tag trong dump.

    Strategy:
    1. Match channel_id qua traffic_source_daily (có cột channel_id).
    2. Match exact title → tag (case-insensitive).
    3. Match fuzzy: bỏ space + ký tự đặc biệt.
    """
    if not channel_title and not channel_id:
        return None
    conn = _connect()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        # 1. Match channel_id qua traffic_source_daily
        if channel_id:
            cur.execute(
                "SELECT DISTINCT account_tag FROM traffic_source_daily "
                "WHERE channel_id = ? LIMIT 1", (channel_id,))
            row = cur.fetchone()
            if row:
                return row[0]
        # 2. Match exact title
        if channel_title:
            # account_tag thường là title với space → _, special → _
            tag_guess = re.sub(r"[^A-Za-z0-9]+", "_", channel_title).strip("_")
            cur.execute(
                "SELECT account_tag FROM videos "
                "WHERE account_tag = ? LIMIT 1", (tag_guess,))
            row = cur.fetchone()
            if row:
                return row[0]
            # Fuzzy: normalize cả 2 bên rồi so
            title_norm = re.sub(r"[^a-z0-9]", "", channel_title.lower())
            cur.execute("SELECT DISTINCT account_tag FROM videos")
            for (tag,) in cur.fetchall():
                tag_norm = re.sub(r"[^a-z0-9]", "", tag.lower())
                if tag_norm == title_norm:
                    return tag
        return None
    finally:
        conn.close()


# ============================================================
# 1. CHANNEL SUMMARY — Tổng hợp 1 lần
# ============================================================

def get_channel_inside(account_tag: str,
                        recent_days: int = 30) -> Dict[str, Any]:
    """Trả dict tổng hợp tất cả metrics CỦA kênh trong dump.

    Returns:
        {
          'account_tag', 'video_count',
          'retention_top': [video retention top 5],
          'demographics': {gender_age: pct},
          'devices': {device: pct},
          'traffic_sources_recent': {source: views_pct, source: total},
          'top_countries': [(country, views_pct)],
          'top_videos_ctr': [(title, ctr_avg, impressions)],
          'last_30d_views': int,
          'last_30d_subs_gained': int,
          'last_30d_subs_lost': int,
          'avg_avd_seconds': float,
          'avg_avp_pct': float,
          'has_data': bool,
        }
    """
    out = {"account_tag": account_tag, "has_data": False}
    if not account_tag:
        return out
    conn = _connect()
    if not conn:
        return out
    try:
        cur = conn.cursor()

        # 1. Video count
        cur.execute("SELECT COUNT(*) FROM videos WHERE account_tag = ?",
                    (account_tag,))
        out["video_count"] = int(cur.fetchone()[0] or 0)
        if out["video_count"] == 0:
            return out

        out["has_data"] = True

        # 2. Demographics — lấy entry MỚI NHẤT (max end_date) + dedup
        cur.execute(
            "SELECT gender, age_group, viewer_percentage "
            "FROM audience_demographics "
            "WHERE account_tag = ? AND end_date = ("
            "  SELECT MAX(end_date) FROM audience_demographics "
            "  WHERE account_tag = ?) "
            "ORDER BY (CAST(viewer_percentage AS REAL)) DESC",
            (account_tag, account_tag))
        demo = []
        for g, a, pct in cur.fetchall():
            try:
                pct_f = float(pct)
            except Exception:
                continue
            if pct_f > 0:
                demo.append({"gender": g, "age_group": a, "pct": pct_f})
        out["demographics"] = demo[:15]

        # 3. Devices — lấy entry MỚI NHẤT
        cur.execute(
            "SELECT device_type, viewer_percentage FROM audience_devices "
            "WHERE account_tag = ? AND end_date = ("
            "  SELECT MAX(end_date) FROM audience_devices "
            "  WHERE account_tag = ?) "
            "ORDER BY (CAST(viewer_percentage AS REAL)) DESC",
            (account_tag, account_tag))
        dev = {}
        for d, pct in cur.fetchall():
            try:
                dev[d] = float(pct)
            except Exception:
                pass
        out["devices"] = dev

        # 4. Traffic sources (recent N days)
        cur.execute(
            "SELECT source, SUM(CAST(views AS INTEGER)) FROM traffic_source_daily "
            "WHERE account_tag = ? "
            "AND day >= date('now', ?) "
            "GROUP BY source ORDER BY SUM(CAST(views AS INTEGER)) DESC",
            (account_tag, f"-{recent_days} days"))
        ts = []
        total_views = 0
        for source, views in cur.fetchall():
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

        # 5. Top countries — GROUP để dedup nhiều period
        cur.execute(
            "SELECT country, SUM(CAST(views AS INTEGER)) FROM geography_country_metrics "
            "WHERE account_tag = ? AND end_date = ("
            "  SELECT MAX(end_date) FROM geography_country_metrics "
            "  WHERE account_tag = ?) "
            "GROUP BY country ORDER BY SUM(CAST(views AS INTEGER)) DESC LIMIT 10",
            (account_tag, account_tag))
        countries = []
        country_total = 0
        for c, v in cur.fetchall():
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
        cur.execute(
            "SELECT SUM(CAST(views AS INTEGER)), "
            "SUM(CAST(subscribers_gained AS INTEGER)), "
            "SUM(CAST(subscribers_lost AS INTEGER)) "
            "FROM channel_daily_metrics "
            "WHERE account_tag = ? AND day >= date('now', ?)",
            (account_tag, f"-{recent_days} days"))
        row = cur.fetchone()
        out["last_views"] = int(row[0] or 0) if row[0] else 0
        out["last_subs_gained"] = int(row[1] or 0) if row[1] else 0
        out["last_subs_lost"] = int(row[2] or 0) if row[2] else 0
        out["last_subs_net"] = out["last_subs_gained"] - out["last_subs_lost"]

        # 7. Video overview AVD/AVP (avg recent published) — chỉ video ≥1K view
        cur.execute(
            "SELECT AVG(CAST(average_view_duration_seconds AS REAL)) "
            "FROM video_overview WHERE account_tag = ? "
            "AND CAST(views AS INTEGER) > 1000",
            (account_tag,))
        avd = cur.fetchone()[0]
        out["avg_avd_seconds"] = float(avd or 0)

        # 8. Thumbnail CTR — TB cho video có impressions > 100
        cur.execute(
            "SELECT AVG(CAST(thumbnail_ctr AS REAL)) "
            "FROM video_thumbnail_daily WHERE account_tag = ? "
            "AND CAST(thumbnail_impressions AS INTEGER) > 100",
            (account_tag,))
        ctr = cur.fetchone()[0]
        out["avg_thumbnail_ctr"] = float(ctr or 0)

        # 9. Daily metrics 15 ngày gần nhất (cho bảng "15 ngày SB" tab self)
        # Inside views = views DELTA mỗi ngày (KHÔNG âm — Analytics chính
        # thức), thay SB scrape có thể âm khi kênh ẩn video → recount.
        # Bug A37 (26/05 tối): user catch cột "Xem +/-" có giá trị âm
        # cho kênh chính Show ASMR vì lấy từ SB daily — fix dùng Inside.
        cur.execute(
            "SELECT day, "
            "  CAST(subscribers_gained AS INTEGER) - "
            "  CAST(subscribers_lost AS INTEGER) AS subs_net, "
            "  CAST(views AS INTEGER) AS views_daily "
            "FROM channel_daily_metrics "
            "WHERE account_tag = ? "
            "ORDER BY day DESC LIMIT 15",
            (account_tag,))
        rows = cur.fetchall()
        # Reverse: order ASC theo ngày (cũ → mới) để hiển thị HTML
        daily = [{"day": r[0], "subs_net": int(r[1] or 0),
                  "views_daily": max(0, int(r[2] or 0))}  # clamp ≥0
                 for r in reversed(rows)]
        out["daily_metrics_15d"] = daily

        return out
    finally:
        conn.close()


# ============================================================
# 2. RETENTION CURVES — Top video
# ============================================================

def get_retention_curves(account_tag: str, top_n: int = 5,
                          min_views: int = 5000,
                          order_by: str = "views") -> List[Dict[str, Any]]:
    """Lấy retention curve cho N video.

    order_by:
      - "views" (mặc định): top N có nhiều view nhất
      - "published": N video MỚI NHẤT theo published_at (user xem video mới
        nhất có retention sao — chốt 25/05)

    Returns:
        List of dicts: [
          {'video_id', 'title', 'views', 'published_at',
           'curve': [(elapsed_pct, watch_ratio, relative_perf), ...],
           'avg_retention', 'drop_points': [list of drops > 5%]}
        ]
    """
    conn = _connect()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        # 26/05: KHI order_by='published' → LẤY TỪ videos table thay vì JOIN
        # với audience_retention. Lý do: video MỚI <48h chưa có retention
        # data trong YouTube Analytics → bị skip, làm "video mới nhất" trong
        # báo cáo lệch về quá khứ. Bây giờ: lấy N video mới nhất từ videos,
        # JOIN OUTER với retention (video chưa có retention sẽ trả curve=[]
        # và đánh dấu "retention đang process").
        if order_by == "published":
            cur.execute(
                "SELECT video_id, title, CAST(views AS INTEGER) as v, published_at "
                "FROM videos "
                f"WHERE account_tag = ? AND CAST(views AS INTEGER) >= ? "
                f"ORDER BY published_at DESC LIMIT ?",
                (account_tag, min_views, top_n))
        else:
            cur.execute(
                "SELECT DISTINCT ar.video_id, v.title, "
                "CAST(v.views AS INTEGER) as v, v.published_at "
                "FROM audience_retention ar "
                "JOIN videos v ON v.video_id = ar.video_id "
                f"WHERE ar.account_tag = ? AND CAST(v.views AS INTEGER) >= ? "
                f"ORDER BY v DESC LIMIT ?",
                (account_tag, min_views, top_n))
        videos = cur.fetchall()
        out = []
        for vid, title, views, published_at in videos:
            cur.execute(
                "SELECT elapsed_video_time_ratio, audience_watch_ratio, "
                "relative_retention_performance "
                "FROM audience_retention "
                "WHERE account_tag = ? AND video_id = ? "
                "ORDER BY CAST(elapsed_video_time_ratio AS REAL) ASC",
                (account_tag, vid))
            pts = cur.fetchall()
            curve = []
            for e, w, rp in pts:
                try:
                    curve.append([float(e), float(w),
                                  float(rp) if rp else 0])
                except Exception:
                    continue
            # 26/05: NO LONGER skip nếu chưa có retention (video mới <48h
            # chưa có data). Vẫn add vào output với curve=[], avg_retention=0,
            # drop_points=[] + flag retention_pending=True → tab Inside
            # Retention sẽ hiển thị "Retention đang process (video mới
            # <48h, YouTube Analytics chưa generate)" thay vì skip.
            if not curve:
                out.append({
                    "video_id": vid,
                    "title": title or "",
                    "views": int(views or 0),
                    "published_at": published_at or "",
                    "curve": [],
                    "avg_retention": 0,
                    "drop_points": [],
                    "n_points": 0,
                    "retention_pending": True,
                })
                continue
            # Avg retention (TB watch_ratio toàn curve)
            avg_r = sum(c[1] for c in curve) / len(curve)
            # Drop points: nơi watch_ratio giảm >5% từ điểm trước
            drops = []
            for i in range(1, len(curve)):
                d = curve[i-1][1] - curve[i][1]
                if d > 0.05:
                    drops.append({
                        "at_pct": round(curve[i][0] * 100, 1),
                        "drop_pct": round(d * 100, 1),
                    })
            out.append({
                "video_id": vid,
                "title": title or "",
                "views": int(views or 0),
                "published_at": published_at or "",
                "curve": curve,
                "avg_retention": round(avg_r * 100, 1),
                "drop_points": drops[:5],
                "n_points": len(curve),
                "retention_pending": False,
            })
        return out
    finally:
        conn.close()


# ============================================================
# 3. THUMBNAIL CTR LEADERBOARD
# ============================================================

def get_thumbnail_ctr_top(account_tag: str, top_n: int = 10,
                           min_impressions: int = 500) -> List[Dict[str, Any]]:
    """Top N video theo CTR thumbnail TB.

    LƯU Ý: alias 'ctr_avg' (KHÔNG dùng 'ctr') vì videos.ctr cũng có cột —
    SQLite resolve trùng tên về v.ctr=0.0 → HAVING ctr>0 lọc sạch dữ liệu.
    """
    conn = _connect()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT vtd.video_id, v.title, "
            "  SUM(CAST(vtd.thumbnail_impressions AS INTEGER)) as imp, "
            "  AVG(CAST(vtd.thumbnail_ctr AS REAL)) as ctr_avg "
            "FROM video_thumbnail_daily vtd "
            "JOIN videos v ON v.video_id = vtd.video_id "
            "WHERE vtd.account_tag = ? "
            "GROUP BY vtd.video_id "
            "HAVING imp >= ? AND ctr_avg > 0 "
            "ORDER BY ctr_avg DESC LIMIT ?",
            (account_tag, min_impressions, top_n))
        rows = []
        for vid, title, imp, ctr_avg in cur.fetchall():
            rows.append({
                "video_id": vid,
                "title": title or "",
                "impressions": int(imp or 0),
                "ctr": round(float(ctr_avg or 0) * 100, 2),
            })
        return rows
    finally:
        conn.close()


# ============================================================
# 4. REVENUE — Sensitive, chỉ trả khi gọi rõ ràng
# ============================================================

def get_revenue_summary(account_tag: str,
                         recent_days: int = 30) -> Dict[str, Any]:
    """Tổng hợp revenue. CHỈ gọi khi cần (vd app desktop, KHÔNG báo cáo public).

    Returns:
        {'total_revenue', 'ad_revenue', 'avg_rpm', 'avg_cpm',
         'monetized_playbacks', 'days_with_data'}
    """
    conn = _connect()
    if not conn:
        return {}
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT SUM(CAST(estimated_revenue AS REAL)), "
            "       SUM(CAST(ad_revenue AS REAL)), "
            "       AVG(CAST(rpm AS REAL)), "
            "       AVG(CAST(cpm AS REAL)), "
            "       SUM(CAST(monetized_playbacks AS INTEGER)), "
            "       COUNT(*) "
            "FROM revenue_daily "
            "WHERE account_tag = ? AND day >= date('now', ?)",
            (account_tag, f"-{recent_days} days"))
        row = cur.fetchone()
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
    finally:
        conn.close()


# ============================================================
# 5. ASSESS — Đánh giá traffic source vs benchmark ngách
# ============================================================

def assess_traffic_source(traffic_sources: list) -> Dict[str, Any]:
    """Đánh giá phân bố traffic source so với benchmark.

    Benchmark cho kênh khỏe:
    - YT_SEARCH: 10-25% (tốt nếu cao = đang ranking)
    - SUGGESTED: 30-50% (tốt — algorithm đẩy)
    - BROWSE: 15-30% (sub loyalty + home feed)
    - SHORTS: tùy ngách
    - EXTERNAL: 5-15% (collab + social)
    - END_SCREEN: 2-8% (session boost)

    Returns: {'health': 'good'|'warn'|'bad', 'issues': [list str]}
    """
    if not traffic_sources:
        return {"health": "warn", "issues": ["Không có data traffic source"]}
    # Convert list → dict source: pct
    ts = {item["source"]: item["pct"] for item in traffic_sources}
    issues = []

    # Search check
    search = ts.get("YT_SEARCH", 0)
    if search < 5:
        issues.append(f"YT_SEARCH chỉ {search}% — keyword/title yếu, "
                      "không ranking trên search.")
    elif search > 50:
        issues.append(f"YT_SEARCH {search}% quá cao — kênh phụ thuộc "
                      "search, suggested/browse yếu.")

    # Suggested check
    suggested = ts.get("RELATED_VIDEO", 0) + ts.get("SUGGESTED", 0)
    if suggested < 15:
        issues.append(f"Suggested chỉ {suggested}% — algorithm không đẩy. "
                      "Cần tăng CTR/AVD để được đề xuất.")

    # Browse (home feed)
    browse = ts.get("YT_CHANNEL", 0) + ts.get("BROWSE", 0)
    if browse < 5:
        issues.append(f"Browse {browse}% — kênh ít sub loyalty / "
                      "thiếu subscribers active.")

    # External
    external = ts.get("EXT_URL", 0) + ts.get("EXTERNAL", 0)
    if external > 30:
        issues.append(f"External {external}% quá cao — kênh phụ thuộc "
                      "traffic ngoài YouTube, organic yếu.")

    # End screen
    end = ts.get("END_SCREEN", 0)
    if end < 1:
        issues.append("END_SCREEN <1% — chưa tận dụng End Screen "
                      "(thiếu link sang video tiếp).")

    # Shorts (nếu có)
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
    """Trends traffic source — so sánh 7d / 30d / 90d.

    Returns:
        {
          'periods': [7, 30, 90],
          'sources': {source: [views_7d, views_30d, views_90d]},
          'pct_change': {source: 7d_vs_30d_pct_change}
        }
    """
    conn = _connect()
    if not conn:
        return {}
    try:
        cur = conn.cursor()
        result = {"periods": list(periods), "sources_data": {}}
        for p in periods:
            cur.execute(
                "SELECT source, SUM(CAST(views AS INTEGER)) "
                "FROM traffic_source_daily "
                "WHERE account_tag = ? AND day >= date('now', ?) "
                "GROUP BY source",
                (account_tag, f"-{p} days"))
            for src, views in cur.fetchall():
                v = int(views or 0)
                if src not in result["sources_data"]:
                    result["sources_data"][src] = {}
                result["sources_data"][src][f"{p}d"] = v
        # Tính velocity (views/ngày) cho mỗi period
        result["velocity"] = {}
        for src, vals in result["sources_data"].items():
            result["velocity"][src] = {
                f"{p}d": (vals.get(f"{p}d", 0) / p) for p in periods
            }
        # Trend: so sánh velocity 7d vs 30d (recent vs baseline)
        result["trend"] = {}
        for src, vels in result["velocity"].items():
            v7 = vels.get("7d", 0)
            v30 = vels.get("30d", 0)
            if v30 > 0:
                pct = round(100 * (v7 - v30) / v30, 1)
            else:
                pct = 0
            result["trend"][src] = pct  # >0 = recent đang tăng, <0 = giảm
        return result
    finally:
        conn.close()


def get_top_videos_per_source(account_tag: str,
                               top_n_videos: int = 5,
                               top_n_sources: int = 6,
                               days: int = 30) -> Dict[str, list]:
    """Top N video theo mỗi traffic source — biết video nào ăn từ
    Search, Suggested, Browse...

    Returns:
        {source: [{video_id, title, views_from_source}, ...]}
    """
    conn = _connect()
    if not conn:
        return {}
    try:
        cur = conn.cursor()
        # Top sources
        cur.execute(
            "SELECT source FROM traffic_source_daily "
            "WHERE account_tag = ? AND day >= date('now', ?) "
            "GROUP BY source ORDER BY SUM(CAST(views AS INTEGER)) DESC "
            "LIMIT ?",
            (account_tag, f"-{days} days", top_n_sources))
        sources = [r[0] for r in cur.fetchall()]
        result = {}
        # Lấy video count per source — KHÔNG có cột video_id trong
        # traffic_source_daily, fallback: top video kênh overall
        # (data này không phân tích được per-video traffic source).
        # → trả về: top sources với total views.
        for src in sources:
            cur.execute(
                "SELECT SUM(CAST(views AS INTEGER)) "
                "FROM traffic_source_daily "
                "WHERE account_tag = ? AND source = ? "
                "AND day >= date('now', ?)",
                (account_tag, src, f"-{days} days"))
            row = cur.fetchone()
            result[src] = int(row[0] or 0) if row else 0
        return result
    finally:
        conn.close()


# ============================================================
# 7. RETENTION — Full data + segment analysis
# ============================================================

def get_retention_full(account_tag: str, top_n: int = 5,
                        min_views: int = 50,
                        order_by: str = "published") -> List[Dict[str, Any]]:
    """Lấy retention curve FULL cho N video, kèm phân tích segment + AI text.

    Chốt 25/05 sáng tối: 5 video MỚI NHẤT (giảm từ 10), thêm:
    - Full info từ bảng videos: likes, comments, ctr, impressions, duration
    - AI rule-based phân tích cho mỗi video (weakest segment + action gợi ý)
    - min_views thấp (50) để bắt cả video mới chưa kịp lên view nhiều.
    """
    curves = get_retention_curves(account_tag, top_n=top_n,
                                   min_views=min_views, order_by=order_by)
    # Lấy thêm meta info từ bảng videos
    if not curves:
        return curves
    conn = _connect()
    if not conn:
        for c in curves:
            c["segments"] = _compute_retention_segments(c.get("curve") or [])
            c["ai_analysis"] = _video_retention_ai(c)
        return curves
    try:
        vids = tuple(c["video_id"] for c in curves)
        if not vids:
            return curves
        qs = ",".join(["?"] * len(vids))
        # 1. Meta từ bảng videos (like, cmt, duration)
        rows = conn.execute(
            f"SELECT video_id, likes, comments, duration "
            f"FROM videos WHERE account_tag = ? "
            f"AND video_id IN ({qs})",
            (account_tag,) + vids).fetchall()
        meta = {r[0]: {"likes": r[1], "comments": r[2],
                       "duration": r[3]} for r in rows}
        # 2. CTR + Impressions từ bảng video_thumbnail_daily (per ngày).
        #    AGGREGATE: sum impressions, avg CTR weighted by impressions.
        #    Chỉ tính NGÀY ≥ published_at — bỏ data pre-publish (private
        #    upload test) gây hiểu nhầm (vd Railway 24/05 có 85 imp từ
        #    ngày 21-22/05 do user upload sớm rồi mới public ngày 24/05).
        try:
            ctr_rows = conn.execute(
                f"SELECT vtd.video_id, "
                f"  SUM(CAST(vtd.thumbnail_impressions AS INTEGER)) as imp, "
                f"  SUM(CAST(vtd.thumbnail_impressions AS INTEGER) * "
                f"      CAST(vtd.thumbnail_ctr AS REAL)) /"
                f"  NULLIF(SUM(CAST(vtd.thumbnail_impressions AS INTEGER)),0) "
                f"      as ctr_w "
                f"FROM video_thumbnail_daily vtd "
                f"JOIN videos v ON v.video_id = vtd.video_id "
                f"  AND v.account_tag = vtd.account_tag "
                f"WHERE vtd.account_tag = ? AND vtd.video_id IN ({qs}) "
                f"  AND vtd.day >= SUBSTR(v.published_at, 1, 10) "
                f"GROUP BY vtd.video_id",
                (account_tag,) + vids).fetchall()
            for vid, imp, ctr_w in ctr_rows:
                imp_val = int(imp or 0)
                ctr_val = float(ctr_w or 0)
                # Nếu < 100 impressions sau filter → coi như chưa đủ data
                # (video mới, Reporting API chưa generate xong)
                if imp_val < 100:
                    imp_val = None
                    ctr_val = None
                if vid in meta:
                    meta[vid]["impressions"] = imp_val
                    meta[vid]["ctr"] = ctr_val
                else:
                    meta[vid] = {"impressions": imp_val, "ctr": ctr_val}
        except Exception as e:
            pass  # thumbnail_daily có thể chưa có data
        for c in curves:
            c.update(meta.get(c["video_id"], {}))
            c["segments"] = _compute_retention_segments(c.get("curve") or [])
            c["ai_analysis"] = _video_retention_ai(c)
        return curves
    finally:
        conn.close()


def _video_retention_ai(video: Dict[str, Any]) -> str:
    """Sinh AI text rule-based cho 1 video: chẩn đoán retention + action.

    Phân tích:
    - Avg retention vs mốc 40%/25%
    - Weakest segment (hook/early/mid)
    - Drop points lớn (>10%)
    - CTR vs TB ngành 8-10%
    - Engagement (likes+comments)/views vs 1-3%
    """
    # 26/05: video mới <48h chưa có retention data → trả message PENDING
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
    # 1. Overall verdict
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
    # 2. Weakest segment
    weak = segs.get("weakest_segment", "")
    weak_map = {
        "hook": "Hook 0-10% YẾU — quay lại intro 10s đầu (test hook động "
                "thay tĩnh).",
        "early": "Early 10-50% drop — pacing chậm, thêm cut nhanh + b-roll.",
        "mid": "Mid 50-90% sag — boost moment ở giữa (reveal/twist/visual).",
    }
    if weak in weak_map:
        parts.append(f"📉 {weak_map[weak]}")
    # 3. CTR
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
    # 4. Engagement
    if views > 100:
        eng = (likes + comments) * 100 / views
        if eng >= 3:
            parts.append(f"✅ Engagement {eng:.1f}% TỐT (≥3%).")
        elif eng >= 1:
            parts.append(f"⚠️ Engagement {eng:.1f}% TB — thêm CTA cuối "
                         "video (Comment / Like).")
        else:
            parts.append(f"🔴 Engagement {eng:.1f}% RẤT THẤP — viewer "
                         "không tương tác.")
    # 5. Drop point lớn
    big_drops = [d for d in drops if (d.get("drop_pct") or 0) >= 10]
    if big_drops:
        d = big_drops[0]
        parts.append(f"⚠️ DROP LỚN tại {d['at_pct']}%: -{d['drop_pct']}% "
                     "— xem moment đó có sai hook/CTA bị skip.")
    return " ".join(parts)


def _compute_retention_segments(curve: list) -> Dict[str, Any]:
    """Phân tích retention curve theo 4 segments:
    - 0-10% (hook): nếu drop nhiều ở đây = hook yếu
    - 10-50% (early): drop = pacing chậm
    - 50-90% (mid-late): drop = mất hứng
    - 90-100% (outro): bình thường drop vì CTA kéo dài

    Returns: {hook_retention, early_retention, mid_retention,
              outro_retention, hook_drop, weakest_segment}
    """
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
    # Hook drop: 100% - retention at 10%
    out["hook_drop"] = round(100 - out["hook_retention"], 1)
    # Weakest segment (TB thấp nhất, exclude outro)
    seg_score = {k: out[f"{k}_retention"]
                 for k in ["hook", "early", "mid"]}
    out["weakest_segment"] = min(seg_score, key=seg_score.get)
    return out


# ============================================================
# 8. THUMBNAIL CTR — Worst + correlation
# ============================================================

def get_thumbnail_ctr_worst(account_tag: str, top_n: int = 10,
                              min_impressions: int = 500) -> List[Dict[str, Any]]:
    """Worst N video theo CTR thumbnail (CẦN SỬA THUMBNAIL).

    LƯU Ý: alias 'ctr_avg' (KHÔNG dùng 'ctr') vì videos.ctr cũng có cột.
    """
    conn = _connect()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT vtd.video_id, v.title, "
            "  SUM(CAST(vtd.thumbnail_impressions AS INTEGER)) as imp, "
            "  AVG(CAST(vtd.thumbnail_ctr AS REAL)) as ctr_avg "
            "FROM video_thumbnail_daily vtd "
            "JOIN videos v ON v.video_id = vtd.video_id "
            "WHERE vtd.account_tag = ? "
            "GROUP BY vtd.video_id "
            "HAVING imp >= ? AND ctr_avg > 0 "
            "ORDER BY ctr_avg ASC LIMIT ?",
            (account_tag, min_impressions, top_n))
        return [{"video_id": vid, "title": title or "",
                 "impressions": int(imp or 0),
                 "ctr": round(float(ctr_avg or 0) * 100, 2)}
                for vid, title, imp, ctr_avg in cur.fetchall()]
    finally:
        conn.close()


def get_ctr_correlation(account_tag: str) -> Dict[str, Any]:
    """Phân tích CTR vs views — có tương quan không?

    LƯU Ý: alias 'ctr_avg' (KHÔNG dùng 'ctr') vì videos.ctr cũng có cột.
    """
    conn = _connect()
    if not conn:
        return {}
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT v.video_id, "
            "  CAST(v.views AS INTEGER) as views_int, "
            "  AVG(CAST(vtd.thumbnail_ctr AS REAL)) as ctr_avg "
            "FROM videos v "
            "JOIN video_thumbnail_daily vtd ON vtd.video_id = v.video_id "
            "WHERE vtd.account_tag = ? "
            "GROUP BY v.video_id "
            "HAVING SUM(CAST(vtd.thumbnail_impressions AS INTEGER)) >= 500 "
            "AND views_int > 0 AND ctr_avg > 0",
            (account_tag,))
        rows = cur.fetchall()
        if len(rows) < 3:
            return {}
        # Tính TB CTR theo bin view
        high_view = sorted(rows, key=lambda x: -x[1])[:max(5, len(rows)//4)]
        low_view = sorted(rows, key=lambda x: x[1])[:max(5, len(rows)//4)]
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
    finally:
        conn.close()


# ============================================================
# 9. AUDIENCE — Cross-analysis
# ============================================================

def get_audience_full(account_tag: str) -> Dict[str, Any]:
    """Audience profile đầy đủ + insight."""
    conn = _connect()
    if not conn:
        return {}
    try:
        cur = conn.cursor()
        # Demographics — entry mới nhất
        cur.execute(
            "SELECT gender, age_group, CAST(viewer_percentage AS REAL) "
            "FROM audience_demographics "
            "WHERE account_tag = ? AND end_date = ("
            "  SELECT MAX(end_date) FROM audience_demographics "
            "  WHERE account_tag = ?) "
            "ORDER BY CAST(viewer_percentage AS REAL) DESC",
            (account_tag, account_tag))
        demo = []
        for g, a, p in cur.fetchall():
            if p and p > 0:
                demo.append({"gender": g, "age_group": a, "pct": p})

        # Devices
        cur.execute(
            "SELECT device_type, CAST(viewer_percentage AS REAL) "
            "FROM audience_devices "
            "WHERE account_tag = ? AND end_date = ("
            "  SELECT MAX(end_date) FROM audience_devices "
            "  WHERE account_tag = ?)",
            (account_tag, account_tag))
        devices = {d: p for d, p in cur.fetchall() if p}

        # Countries — total period
        cur.execute(
            "SELECT country, SUM(CAST(views AS INTEGER)) "
            "FROM geography_country_metrics "
            "WHERE account_tag = ? AND end_date = ("
            "  SELECT MAX(end_date) FROM geography_country_metrics "
            "  WHERE account_tag = ?) "
            "GROUP BY country ORDER BY SUM(CAST(views AS INTEGER)) DESC "
            "LIMIT 15",
            (account_tag, account_tag))
        countries = []
        total_v = 0
        for c, v in cur.fetchall():
            vi = int(v or 0)
            countries.append([c, vi])
            total_v += vi
        if total_v > 0:
            countries = [{"country": c, "views": v,
                          "pct": round(100 * v / total_v, 1)}
                         for c, v in countries]

        # Insight
        insights = []
        # Top gender + age
        if demo:
            top_d = demo[0]
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
        # Mobile heavy
        if devices.get("MOBILE", 0) > 90:
            insights.append(
                f"MOBILE {devices['MOBILE']:.0f}% — thumbnail/text phải "
                "tối ưu cho màn nhỏ, mặt to, contrast cao.")
        elif devices.get("MOBILE", 0) < 50:
            insights.append(
                "Mobile <50% — audience xem trên desktop/TV nhiều, "
                "có thể làm video dài hơn.")
        # Geo concentration
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
            # CPM-high countries
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
    finally:
        conn.close()


# ============================================================
# Original assess_demographics (kept)
# ============================================================

def assess_demographics(demographics: list,
                         persona_age_range: tuple = None) -> Dict[str, Any]:
    """Đánh giá demographics. Trả {'health', 'top_age_group', 'top_gender',
    'note'}."""
    if not demographics:
        return {"health": "warn", "note": "Không có data demographics"}
    # Group theo age
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
