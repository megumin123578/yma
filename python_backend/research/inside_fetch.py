# -*- coding: utf-8 -*-
"""core/inside_fetch.py — Lấy data YouTube Analytics Inside qua API.

Refactor từ tools/fetch_youtube_api.py để IMPORT được (đóng gói vào exe,
`auto_pipeline` gọi trực tiếp sau giám sát). `tools/fetch_youtube_api.py`
giờ chỉ là CLI wrapper mỏng gọi `inside_fetch.main()`.

Dùng OAuth token (refresh_token) các kênh chính từ token_store CHUNG của app
(auth.db, gộp yt_manage_app 2026-06 — KHÔNG còn oauth_tokens.json) → YouTube
Analytics API v2 → ghi SQLite <inside_data_dir>/cache/analytics.db.

Degrade AN TOÀN: thiếu thư viện Google → AVAILABLE=False, mọi hàm fetch
trả thất bại nhẹ nhàng, KHÔNG crash phần mềm.

Lấy ĐỦ data cho báo cáo, KHÔNG thừa: videos + overview, channel_daily,
demographics, devices, traffic, geography, revenue, video_daily_stats,
retention (top 15 video). Data public (video list, views, tags...) lấy
từ pkl monitor — KHÔNG tốn quota API.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

# --- Thư viện Google API — degrade nhẹ nhàng nếu thiếu ---
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    AVAILABLE = True
    _IMPORT_ERR = ""
except Exception as _e:  # ImportError hoặc lỗi phụ thuộc
    AVAILABLE = False
    _IMPORT_ERR = str(_e)
    Credentials = None
    Request = None
    build = None

    class HttpError(Exception):
        """Placeholder khi thiếu googleapiclient."""
        pass


# Số ngày lùi cho bảng DAILY (đủ báo cáo 7/30/90d + buffer)
DAILY_LOOKBACK = 120
# Toàn bộ lịch sử cho aggregate
LIFETIME_START = "2005-02-14"
# Retention chỉ lấy top N video nhiều view nhất (chốt với user 22/05)
RETENTION_TOP_N = 15
# Đường dẫn mặc định (máy hiện tại) — máy khác chỉnh trong config
_DEFAULT_INSIDE_DIR = r"D:\YouTube_Analytics_Inside"

# log callback (auto_pipeline truyền vào); None = print stdout
_LOG = None


def _emit(msg: str) -> None:
    if _LOG is not None:
        try:
            _LOG(msg)
            return
        except Exception:
            pass
    print(msg, flush=True)


# ============================================================
# ĐƯỜNG DẪN — đọc từ config (máy khác trỏ lại được)
# ============================================================

def _inside_dir() -> Path:
    try:
        try:
            from .config import load_config
        except ImportError:
            from .config import load_config
        d = (load_config().get("inside_data_dir") or "").strip()
        if d:
            return Path(d)
    except Exception:
        pass
    return Path(_DEFAULT_INSIDE_DIR)


def cache_db() -> Path:
    return _inside_dir() / "cache" / "analytics.db"


# ============================================================
# TOKEN — UNIFIED: đọc từ token_store (auth.db) của app chính
# (gộp yt_manage_app 2026-06: BỎ HẲN oauth_tokens.json — 1 kho token duy nhất).
# token_name == account_tag; channel_id/title lấy từ bảng UserCredential.
# ============================================================

def load_tokens() -> dict:
    """Trả {token_name: {credentials, channel_id, title}} từ token_store.

    Thay oauth_tokens.json: token OAuth + channel_id/title lấy từ kho chung
    (token_store.oauth_tokens + UserCredential) — kết nối kênh 1 lần ở app
    chính là pipeline Inside dùng được luôn. Bỏ kênh mail__.
    """
    from python_backend.token_store import list_token_names, load_token_credentials
    from python_backend.api.auth.database import SessionLocal
    from python_backend.api.auth.models import UserCredential

    db = SessionLocal()
    try:
        meta = {}
        for tag, cid, title in db.query(
            UserCredential.account_tag,
            UserCredential.selected_channel_id,
            UserCredential.selected_channel_title,
        ).all():
            if tag and tag not in meta:
                meta[tag] = (cid or "", title or "")
    finally:
        db.close()

    out = {}
    for name in list_token_names():
        if str(name or "").lower().startswith("mail__"):
            continue
        try:
            creds = load_token_credentials(name, refresh=False)
        except Exception:
            continue
        if not creds:
            continue
        cid, title = meta.get(name, ("", ""))
        out[name] = {
            "credentials": json.loads(creds.to_json()),
            "channel_id": cid,
            "title": title or name,
        }
    return out


def get_credentials(token_name: str, tokens: dict = None):
    """Lấy Credentials từ token_store (tự refresh + lưu DB). `tokens` chỉ để
    tương thích chữ ký cũ, không dùng."""
    from python_backend.token_store import load_token_credentials
    creds = load_token_credentials(token_name, refresh=True)
    if not creds:
        raise RuntimeError(f"Token {token_name} không có trong token_store")
    return creds


def find_token_by_channel_id(channel_id: str, tokens: dict = None):
    """Tìm token_name theo channel_id. Trả (token_name|None, tokens)."""
    if tokens is None:
        try:
            tokens = load_tokens()
        except Exception:
            return None, {}
    for tn, entry in tokens.items():
        if entry.get("channel_id") == channel_id:
            return tn, tokens
    return None, tokens


def has_token(channel_id: str) -> bool:
    """True nếu channel_id có token API (kênh chính Funtime)."""
    tn, _ = find_token_by_channel_id(channel_id)
    return tn is not None


# ============================================================
# SQLITE — kết nối
# ============================================================

# 26/05 bug fix: 4 stage_inside song song cùng DELETE/INSERT vào DB → SQLite
# chỉ chịu 1 writer/lúc → busy_timeout 30s không đủ (stage_inside chạy 5+p).
# Global lock buộc các fetch_channel chạy TUẦN TỰ (sequential) — chậm hơn
# 1 chút nhưng tránh corrupt + lost data.
import threading as _threading
_DB_WRITE_LOCK = _threading.RLock()


def _connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(cache_db()), timeout=120)
    conn.execute("PRAGMA busy_timeout = 120000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _now() -> str:
    return datetime.utcnow().isoformat()


def _daily_start() -> str:
    return (datetime.utcnow().date()
            - timedelta(days=DAILY_LOOKBACK)).isoformat()


def _today() -> str:
    return datetime.utcnow().date().isoformat()


def _iso_dur_to_sec(iso: str) -> int:
    """PT5M30S → 330 giây."""
    if not iso or not iso.startswith("PT"):
        return 0
    h = re.search(r"(\d+)H", iso)
    m = re.search(r"(\d+)M", iso)
    s = re.search(r"(\d+)S", iso)
    return ((int(h.group(1)) if h else 0) * 3600
            + (int(m.group(1)) if m else 0) * 60
            + (int(s.group(1)) if s else 0))


def _analytics_query(yta, **kwargs) -> dict:
    """Gọi Analytics reports.query, trả {} nếu lỗi."""
    try:
        return yta.reports().query(**kwargs).execute() or {}
    except HttpError as e:
        _emit(f"    [WARN] Analytics query lỗi: {e}")
        return {}


def _rows_idx(resp: dict):
    rows = resp.get("rows") or []
    headers = [h["name"] for h in resp.get("columnHeaders", [])]
    idx = {h: i for i, h in enumerate(headers)}
    return rows, idx


# ============================================================
# FETCH 1 — Video list từ PKL monitor + Overview (CHỈ Analytics)
# ============================================================

def _video_list_from_pkl(channel_id: str) -> dict:
    """Đọc video list public từ pkl monitor. Returns {video_id: meta}."""
    try:
        try:
            from . import persistence
        except ImportError:
            from . import persistence
    except Exception:
        return {}
    res = persistence.find_previous_for_channel(channel_id)
    if not res:
        return {}
    vmeta = {}
    for v in res.get("videos") or []:
        vid = getattr(v, "video_id", "")
        if not vid:
            continue
        tags = getattr(v, "tags", []) or []
        vmeta[vid] = {
            "title": getattr(v, "title", "") or "",
            "thumbnail": getattr(v, "thumbnail_url", "")
            or getattr(v, "thumbnail", "") or "",
            "published_at": getattr(v, "published_at", "") or "",
            "duration": int(getattr(v, "duration_seconds", 0) or 0),
            "views": int(getattr(v, "view_count", 0) or 0),
            "likes": int(getattr(v, "like_count", 0) or 0),
            "comments": int(getattr(v, "comment_count", 0) or 0),
            "tags": json.dumps(list(tags), ensure_ascii=False),
            "privacy_status": "",
        }
    return vmeta


def fetch_videos_overview(creds, tag: str, channel_id: str, conn) -> list:
    """Video list lấy từ pkl monitor (public). API chỉ query Analytics
    aggregate (Inside fields). Returns: list video_id sort views desc."""
    yta = build("youtubeAnalytics", "v2", credentials=creds)

    vmeta = _video_list_from_pkl(channel_id)
    if not vmeta:
        _emit(f"    [WARN] Chưa có pkl monitor cho {channel_id} — "
              f"chạy monitor trước. Bỏ qua video-level Inside.")
        return []
    video_ids = list(vmeta.keys())

    ana = {}
    metrics = ("views,likes,comments,dislikes,shares,engagedViews,"
               "averageViewDuration,subscribersGained,subscribersLost,"
               "annotationClickThroughRate,annotationCloseRate")
    for i in range(0, len(video_ids), 200):
        batch = video_ids[i:i + 200]
        resp = _analytics_query(
            yta, ids=f"channel=={channel_id}",
            startDate=LIFETIME_START, endDate="2099-01-01",
            metrics=metrics, dimensions="video",
            filters="video==" + ",".join(batch),
            maxResults=200)
        rows, idx = _rows_idx(resp)
        iv = idx.get("video")
        for row in rows:
            if iv is None:
                continue
            vid = row[iv]
            ana[vid] = {m: row[idx[m]] for m in idx if m != "video"}

    cur = conn.cursor()
    now = _now()
    # A35 fix (26/05): bỏ DELETE+INSERT pattern (nguy cơ mất data khi API
    # thiếu/lỗi giữa chừng). Dùng INSERT OR REPLACE với UNIQUE INDEX
    # uniq_videos_a35 (account_tag, video_id) và uniq_video_overview_a35
    for vid in video_ids:
        meta = vmeta.get(vid, {})
        a = ana.get(vid, {})
        cur.execute(
            "INSERT OR REPLACE INTO videos (video_id, account_tag, title, thumbnail, "
            " published_at, duration, views, likes, comments, tags, "
            " privacy_status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (vid, tag, meta.get("title"), meta.get("thumbnail"),
             meta.get("published_at"), meta.get("duration"),
             meta.get("views", 0), meta.get("likes", 0),
             meta.get("comments", 0), meta.get("tags"),
             meta.get("privacy_status")))
        cur.execute(
            "INSERT OR REPLACE INTO video_overview (account_tag, video_id, title, "
            " thumbnail, publish_date, views, likes, comments, dislikes, "
            " engaged_views, annotation_click_through_rate, "
            " annotation_close_rate, average_view_duration_seconds, shares, "
            " subscribers_gained, subscribers_lost, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tag, vid, meta.get("title"), meta.get("thumbnail"),
             meta.get("published_at"),
             a.get("views") or meta.get("views", 0),
             a.get("likes") or meta.get("likes", 0),
             a.get("comments") or meta.get("comments", 0),
             a.get("dislikes"), a.get("engagedViews"),
             a.get("annotationClickThroughRate"),
             a.get("annotationCloseRate"), a.get("averageViewDuration"),
             a.get("shares"), a.get("subscribersGained"),
             a.get("subscribersLost"), now))
    conn.commit()

    video_ids.sort(key=lambda v: vmeta.get(v, {}).get("views", 0),
                   reverse=True)
    _emit(f"    videos: {len(video_ids)} video")
    return video_ids


# ============================================================
# FETCH 2 — Channel daily metrics
# ============================================================

def fetch_channel_daily(creds, tag: str, channel_id: str, conn):
    yta = build("youtubeAnalytics", "v2", credentials=creds)
    resp = _analytics_query(
        yta, ids=f"channel=={channel_id}",
        startDate=_daily_start(), endDate=_today(),
        dimensions="day", metrics="subscribersGained,subscribersLost,views",
        sort="day")
    rows, idx = _rows_idx(resp)
    cur = conn.cursor()
    # A35: INSERT OR REPLACE (UNIQUE INDEX uniq_channel_daily_metric_a35 trên account_tag+day)
    n = 0
    for row in rows:
        day = row[idx["day"]]
        cur.execute(
            "INSERT OR REPLACE INTO channel_daily_metrics (account_tag, day, "
            " subscribers_gained, subscribers_lost, views, updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (tag, day, int(row[idx["subscribersGained"]] or 0),
             int(row[idx["subscribersLost"]] or 0),
             int(row[idx["views"]] or 0), _now()))
        n += 1
    conn.commit()
    _emit(f"    channel_daily_metrics: {n} ngày")


# ============================================================
# FETCH 3 — Demographics + Devices
# ============================================================

def fetch_demographics(creds, tag: str, channel_id: str, conn):
    yta = build("youtubeAnalytics", "v2", credentials=creds)
    sd, ed = LIFETIME_START, _today()
    resp = _analytics_query(
        yta, ids=f"channel=={channel_id}", startDate=sd, endDate=ed,
        dimensions="gender,ageGroup", metrics="viewerPercentage",
        sort="gender,ageGroup")
    rows, idx = _rows_idx(resp)
    cur = conn.cursor()
    # A35: INSERT OR REPLACE (UNIQUE INDEX uniq_audience_demographi_a35)
    for row in rows:
        cur.execute(
            "INSERT OR REPLACE INTO audience_demographics (account_tag, start_date, "
            " end_date, gender, age_group, viewer_percentage, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (tag, sd, ed, row[idx["gender"]], row[idx["ageGroup"]],
             float(row[idx["viewerPercentage"]] or 0), _now()))
    conn.commit()
    _emit(f"    demographics: {len(rows)} dòng")


def fetch_devices(creds, tag: str, channel_id: str, conn):
    yta = build("youtubeAnalytics", "v2", credentials=creds)
    sd, ed = LIFETIME_START, _today()
    resp = _analytics_query(
        yta, ids=f"channel=={channel_id}", startDate=sd, endDate=ed,
        dimensions="deviceType", metrics="views", sort="-views")
    rows, idx = _rows_idx(resp)
    total = sum(int(r[idx["views"]] or 0) for r in rows) or 1
    cur = conn.cursor()
    # A35: INSERT OR REPLACE (UNIQUE INDEX uniq_audience_devices_a35)
    for row in rows:
        v = int(row[idx["views"]] or 0)
        cur.execute(
            "INSERT OR REPLACE INTO audience_devices (account_tag, start_date, "
            " end_date, device_type, viewer_percentage, updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (tag, sd, ed, row[idx["deviceType"]],
             v / total * 100, _now()))
    conn.commit()
    _emit(f"    devices: {len(rows)} dòng")


# ============================================================
# FETCH 4 — Traffic source daily
# ============================================================

def fetch_traffic(creds, tag: str, channel_id: str, conn):
    yta = build("youtubeAnalytics", "v2", credentials=creds)
    resp = _analytics_query(
        yta, ids=f"channel=={channel_id}",
        startDate=_daily_start(), endDate=_today(),
        dimensions="insightTrafficSourceType,day",
        metrics="views,estimatedMinutesWatched,engagedViews,"
                "averageViewDuration,averageViewPercentage",
        sort="day,insightTrafficSourceType")
    rows, idx = _rows_idx(resp)
    cur = conn.cursor()
    # A35: INSERT OR REPLACE (UNIQUE INDEX uniq_traffic_source_dai_a35)
    for row in rows:
        cur.execute(
            "INSERT OR REPLACE INTO traffic_source_daily (account_tag, channel_id, "
            " day, source, views, estimated_minutes_watched, "
            " average_view_duration, average_view_percentage, engaged_views) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (tag, channel_id, row[idx["day"]],
             row[idx["insightTrafficSourceType"]],
             int(row[idx["views"]] or 0),
             int(row[idx["estimatedMinutesWatched"]] or 0),
             float(row[idx["averageViewDuration"]] or 0),
             float(row[idx["averageViewPercentage"]] or 0),
             int(row[idx["engagedViews"]] or 0)))
    conn.commit()
    _emit(f"    traffic_source_daily: {len(rows)} dòng")


# ============================================================
# FETCH 5 — Geography
# ============================================================

def fetch_geography(creds, tag: str, channel_id: str, conn):
    yta = build("youtubeAnalytics", "v2", credentials=creds)
    sd, ed = LIFETIME_START, _today()
    resp = _analytics_query(
        yta, ids=f"channel=={channel_id}", startDate=sd, endDate=ed,
        dimensions="country",
        metrics="views,estimatedMinutesWatched,engagedViews,"
                "averageViewDuration,averageViewPercentage",
        sort="-views")
    rows, idx = _rows_idx(resp)
    cur = conn.cursor()
    # A35: INSERT OR REPLACE (UNIQUE INDEX uniq_geography_country__a35)
    for row in rows:
        cur.execute(
            "INSERT OR REPLACE INTO geography_country_metrics (account_tag, start_date, "
            " end_date, country, views, estimated_minutes_watched, "
            " engaged_views, average_view_duration, average_view_percentage, "
            " updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (tag, sd, ed, row[idx["country"]],
             int(row[idx["views"]] or 0),
             int(row[idx["estimatedMinutesWatched"]] or 0),
             int(row[idx["engagedViews"]] or 0),
             float(row[idx["averageViewDuration"]] or 0),
             float(row[idx["averageViewPercentage"]] or 0), _now()))
    conn.commit()
    _emit(f"    geography: {len(rows)} quốc gia")


# ============================================================
# FETCH 6 — Revenue daily (cần monetary scope)
# ============================================================

_REVENUE_METRICS = ["estimatedRevenue", "estimatedAdRevenue",
                    "grossRevenue", "cpm", "playbackBasedCpm",
                    "monetizedPlaybacks", "adImpressions", "views"]


def fetch_revenue(creds, tag: str, channel_id: str, conn):
    yta = build("youtubeAnalytics", "v2", credentials=creds)
    daily = {}
    for metric in _REVENUE_METRICS:
        resp = _analytics_query(
            yta, ids=f"channel=={channel_id}",
            startDate=_daily_start(), endDate=_today(),
            dimensions="day", metrics=metric, sort="day")
        rows, idx = _rows_idx(resp)
        di, mi = idx.get("day"), idx.get(metric)
        if di is None or mi is None:
            continue
        for row in rows:
            daily.setdefault(row[di], {})[metric] = row[mi]
    cur = conn.cursor()
    # A35: INSERT OR REPLACE (UNIQUE INDEX uniq_revenue_daily_a35)
    for day, m in daily.items():
        cur.execute(
            "INSERT OR REPLACE INTO revenue_daily (account_tag, channel_id, day, "
            " estimated_revenue, ad_revenue, gross_revenue, cpm, "
            " playback_cpm, monetized_playbacks, ad_impressions, views, "
            " updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (tag, channel_id, day,
             float(m.get("estimatedRevenue") or 0),
             float(m.get("estimatedAdRevenue") or 0),
             float(m.get("grossRevenue") or 0),
             float(m.get("cpm") or 0),
             float(m.get("playbackBasedCpm") or 0),
             int(m.get("monetizedPlaybacks") or 0),
             int(m.get("adImpressions") or 0),
             int(m.get("views") or 0), _now()))
    conn.commit()
    _emit(f"    revenue_daily: {len(daily)} ngày")


# ============================================================
# FETCH 7 — Video daily stats (TOP video)
# ============================================================

def fetch_video_daily(creds, tag: str, channel_id: str,
                      video_ids: list, conn, top_n: int = 40):
    """video_daily_stats cho top N video (per-day)."""
    yta = build("youtubeAnalytics", "v2", credentials=creds)
    cur = conn.cursor()
    sd, ed = _daily_start(), _today()
    n_vds = 0
    sel_vids = video_ids[:top_n]
    # A35: bỏ DELETE — INSERT OR REPLACE với UNIQUE INDEX
    # uniq_video_daily_stats_a35 (video_id, day)
    for vid in sel_vids:
        resp = _analytics_query(
            yta, ids=f"channel=={channel_id}", startDate=sd, endDate=ed,
            dimensions="day",
            metrics="views,estimatedMinutesWatched,averageViewDuration,"
                    "averageViewPercentage,likes,subscribersGained",
            filters=f"video=={vid}", sort="day")
        rows, idx = _rows_idx(resp)
        for row in rows:
            cur.execute(
                "INSERT OR REPLACE INTO video_daily_stats (video_id, day, views, "
                " estimated_minutes, average_view_duration, "
                " average_view_percentage, likes, subscribers_gained) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (vid, row[idx["day"]], int(row[idx["views"]] or 0),
                 int(row[idx["estimatedMinutesWatched"]] or 0),
                 int(row[idx["averageViewDuration"]] or 0),
                 float(row[idx["averageViewPercentage"]] or 0),
                 int(row[idx["likes"]] or 0),
                 int(row[idx["subscribersGained"]] or 0)))
            n_vds += 1
    conn.commit()
    _emit(f"    video_daily_stats: {n_vds} dòng ({len(sel_vids)} video)")


# ============================================================
# FETCH 8 — Retention (TOP 15 video)
# ============================================================

def fetch_retention(creds, tag: str, channel_id: str,
                    video_ids: list, conn):
    yta = build("youtubeAnalytics", "v2", credentials=creds)
    cur = conn.cursor()
    # A35: KHÔNG DELETE — INSERT OR REPLACE với UNIQUE INDEX
    # uniq_audience_retention_a35 (account_tag, video_id, elapsed_video_time_ratio)
    sd, ed = LIFETIME_START, _today()
    # 26/05 bug A34: TOP 15 by view + 5 mới nhất by published_at (union).
    # Lý do: video_ids sort by view desc → video MỚI view thấp (vd HP Mini
    # Dragon Fruit 47K, Treasure 38K) ngoài top 15 → audience_retention
    # không có → tab Inside Retention hiển thị "đang process" sai. User
    # muốn 5 video MỚI NHẤT đều có retention để đánh giá performance gần.
    recent_ids = []
    try:
        rs = cur.execute(
            "SELECT video_id FROM videos WHERE account_tag = ? "
            "ORDER BY published_at DESC LIMIT 5", (tag,)).fetchall()
        recent_ids = [r[0] for r in rs]
    except Exception:
        pass
    fetch_ids = list(dict.fromkeys(video_ids[:RETENTION_TOP_N] + recent_ids))
    n = 0
    for vid in fetch_ids:
        resp = _analytics_query(
            yta, ids=f"channel=={channel_id}", startDate=sd, endDate=ed,
            dimensions="elapsedVideoTimeRatio",
            metrics="audienceWatchRatio,relativeRetentionPerformance",
            filters=f"video=={vid}", sort="elapsedVideoTimeRatio")
        rows, idx = _rows_idx(resp)
        for row in rows:
            rel_i = idx.get("relativeRetentionPerformance")
            cur.execute(
                "INSERT OR REPLACE INTO audience_retention (account_tag, video_id, "
                " start_date, end_date, elapsed_video_time_ratio, "
                " audience_watch_ratio, relative_retention_performance, "
                " updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (tag, vid, sd, ed,
                 float(row[idx["elapsedVideoTimeRatio"]] or 0),
                 float(row[idx["audienceWatchRatio"]] or 0),
                 (float(row[rel_i]) if rel_i is not None
                  and row[rel_i] is not None else None),
                 _now()))
            n += 1
    conn.commit()
    _emit(f"    audience_retention: {n} dòng ({len(fetch_ids)} video — "
          f"top {min(RETENTION_TOP_N, len(video_ids))} view + 5 mới nhất)")


# ============================================================
# FETCH 9 — Thumbnail CTR + Impressions (per video per day)
# YouTube REPORTING API — channel_reach_basic_a1 report
# Columns CSV: date, channel_id, video_id,
#              video_thumbnail_impressions, video_thumbnail_impressions_ctr
# Cập nhật 25/05 tối: YouTube Analytics API v2 KHÔNG có metric này,
# nhưng YouTube Reporting API CÓ qua daily report job. Lag 1-2 ngày.
# ============================================================

REACH_REPORT_TYPE = "channel_reach_basic_a1"


def _ensure_reach_job(creds) -> str:
    """Tìm hoặc tạo job channel_reach_basic_a1, trả job_id."""
    yr = build("youtubereporting", "v1", credentials=creds)
    try:
        jobs = yr.jobs().list().execute().get("jobs", [])
        for j in jobs:
            if j.get("reportTypeId") == REACH_REPORT_TYPE:
                return j["id"]
    except Exception as e:
        _emit(f"    [WARN] list reach jobs: {e}")
    # Chưa có → tạo
    try:
        job = yr.jobs().create(body={
            "reportTypeId": REACH_REPORT_TYPE,
            "name": "thumbnail_reach_daily",
        }).execute()
        return job["id"]
    except Exception as e:
        _emit(f"    [WARN] create reach job: {e}")
        return ""


def fetch_video_thumbnail_daily(creds, tag: str, channel_id: str,
                                  video_ids: list, conn, top_n: int = 40):
    """Fetch CTR thumbnail + impressions per video qua YouTube Reporting API.

    Download daily reports mới nhất (1 report = 1 ngày data) + INSERT OR
    REPLACE vào video_thumbnail_daily. KHÔNG DELETE — giữ data Studio dump cũ.
    """
    import csv
    import requests
    job_id = _ensure_reach_job(creds)
    if not job_id:
        _emit(f"    [WARN] không có reach job → skip")
        return
    yr = build("youtubereporting", "v1", credentials=creds)
    # List reports — lấy 30 ngày gần nhất
    try:
        reports = yr.jobs().reports().list(jobId=job_id).execute().get(
            "reports", [])
    except Exception as e:
        _emit(f"    [WARN] list reports: {e}")
        return
    if not reports:
        _emit(f"    [WARN] reach reports rỗng (job vừa tạo, "
              f"YouTube cần 24-48h để generate)")
        return
    # Sort theo startTime DESC, lấy 30 báo cáo gần nhất (1 mỗi ngày)
    reports.sort(key=lambda r: r.get("startTime", ""), reverse=True)
    # Lấy theo MỖI ngày 1 báo cáo mới nhất (theo createTime)
    by_day = {}
    for r in reports:
        d = r.get("startTime", "")[:10]
        if d and d not in by_day:
            by_day[d] = r
    sel_reports = sorted(by_day.values(),
                          key=lambda r: r.get("startTime", ""),
                          reverse=True)[:30]
    cur = conn.cursor()
    # Set ID video kênh chính cần insert
    sel_vids = set(video_ids[:top_n]) if video_ids else None
    n_rows_total = 0
    n_days = 0
    for rep in sel_reports:
        url = rep.get("downloadUrl", "")
        if not url:
            continue
        try:
            resp = requests.get(url, headers={
                "Authorization": f"Bearer {creds.token}"})
            if resp.status_code != 200:
                continue
            lines = resp.text.splitlines()
            if not lines:
                continue
            rdr = csv.DictReader(lines)
            n_rows = 0
            for row in rdr:
                vid = row.get("video_id", "")
                if sel_vids is not None and vid not in sel_vids:
                    continue
                # date format YYYYMMDD → YYYY-MM-DD
                day_raw = row.get("date", "")
                day = (f"{day_raw[:4]}-{day_raw[4:6]}-{day_raw[6:8]}"
                       if len(day_raw) == 8 else day_raw)
                try:
                    imp = int(row.get("video_thumbnail_impressions", 0) or 0)
                    ctr = float(row.get(
                        "video_thumbnail_impressions_ctr", 0) or 0)
                except (ValueError, TypeError):
                    continue
                if imp <= 0:
                    continue
                # INSERT OR REPLACE — UNIQUE key (account_tag, video_id, day)
                cur.execute(
                    "INSERT OR REPLACE INTO video_thumbnail_daily "
                    "(account_tag, channel_id, video_id, day, "
                    " thumbnail_impressions, thumbnail_ctr, report_id, "
                    " updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (tag, channel_id, vid, day, imp, ctr,
                     f"reporting_api_{rep['id']}", _now()))
                n_rows += 1
            n_rows_total += n_rows
            if n_rows > 0:
                n_days += 1
        except Exception as e:
            _emit(f"    [WARN] fetch report {rep.get('id','?')}: {e}")
            continue
    conn.commit()
    _emit(f"    video_thumbnail_daily: {n_rows_total} dòng "
          f"({n_days} ngày, top {len(sel_vids) if sel_vids else 'all'} video)")


# ============================================================
# FETCH 1 KÊNH
# ============================================================

def fetch_channel(token_name: str, tokens: dict, log_fn=None) -> bool:
    """Lấy đủ data Inside 1 kênh theo token_name. Trả True nếu OK."""
    global _LOG
    if log_fn is not None:
        _LOG = log_fn
    if not AVAILABLE:
        _emit(f"  [LỖI] Thiếu thư viện Google API: {_IMPORT_ERR}")
        return False
    entry = tokens.get(token_name)
    if not entry:
        _emit(f"[SKIP] {token_name}: không có token")
        return False
    channel_id = entry.get("channel_id", "")
    title = entry.get("title", token_name)
    if not channel_id:
        _emit(f"[SKIP] {token_name}: thiếu channel_id")
        return False

    _emit(f"=== Inside: {title} ({token_name}) ===")
    t0 = time.time()
    try:
        creds = get_credentials(token_name, tokens)
    except Exception as e:
        _emit(f"  [LỖI TOKEN] {e}")
        return False

    # 26/05: GLOBAL LOCK — chỉ 1 fetch_channel chạy lúc (tránh DB locked)
    with _DB_WRITE_LOCK:
        conn = _connect_db()
        try:
            video_ids = fetch_videos_overview(creds, token_name, channel_id, conn)
            fetch_channel_daily(creds, token_name, channel_id, conn)
            fetch_demographics(creds, token_name, channel_id, conn)
            fetch_devices(creds, token_name, channel_id, conn)
            fetch_traffic(creds, token_name, channel_id, conn)
            fetch_geography(creds, token_name, channel_id, conn)
            try:
                fetch_revenue(creds, token_name, channel_id, conn)
            except Exception as e:
                _emit(f"    [WARN] revenue skip: {e}")
            if video_ids:
                fetch_video_daily(creds, token_name, channel_id, video_ids, conn)
                fetch_retention(creds, token_name, channel_id, video_ids, conn)
                # 25/05 tối: dùng YouTube REPORTING API
                # (channel_reach_basic_a1) — API chính thức cho thumbnail
                # impressions + CTR. Daily report, lag 1-2 ngày.
                try:
                    fetch_video_thumbnail_daily(
                        creds, token_name, channel_id, video_ids, conn)
                except Exception as e:
                    _emit(f"    [WARN] thumbnail_daily skip: {e}")
            _emit(f"  XONG Inside {title} ({time.time() - t0:.0f}s)")
            return True
        except Exception as e:
            import traceback
            _emit(f"  [LỖI] {e}")
            traceback.print_exc()
            return False
        finally:
            conn.close()


def fetch_for_channel(channel_id: str, log_fn=None) -> dict:
    """Lấy data Inside cho 1 kênh theo channel_id (dùng từ auto_pipeline).

    Trả {ok: bool, reason: str}. KHÔNG raise — degrade an toàn.
    """
    if not AVAILABLE:
        return {"ok": False,
                "reason": f"thiếu thư viện Google API ({_IMPORT_ERR})"}
    try:
        tokens = load_tokens()
    except Exception as e:
        return {"ok": False, "reason": f"lỗi đọc token: {e}"}
    token_name, tokens = find_token_by_channel_id(channel_id, tokens)
    if not token_name:
        return {"ok": False, "reason": "kênh không có token API"}
    db = cache_db()
    if not db.exists():
        return {"ok": False, "reason": f"không có analytics.db: {db}"}
    try:
        ok = fetch_channel(token_name, tokens, log_fn=log_fn)
    except Exception as e:
        return {"ok": False, "reason": f"lỗi fetch: {e}"}
    return {"ok": bool(ok), "reason": "" if ok else "fetch thất bại"}


# ============================================================
# CLI
# ============================================================

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Lấy data YouTube Analytics Inside qua API")
    ap.add_argument("--list", action="store_true", help="Liệt kê token")
    ap.add_argument("--channel", help="Fetch 1 kênh (token_name)")
    ap.add_argument("--all", action="store_true", help="Fetch tất cả kênh")
    args = ap.parse_args(argv)

    if not AVAILABLE:
        print(f"LỖI: thiếu thư viện Google API ({_IMPORT_ERR}). "
              f"Cài: pip install google-api-python-client google-auth")
        return 1

    try:
        tokens = load_tokens()
    except Exception as e:
        print(f"LỖI: {e}")
        return 1

    if args.list:
        print(f"Có {len(tokens)} token kênh:")
        for tn, d in tokens.items():
            print(f"  {tn:30s} {d.get('channel_id', ''):26s} "
                  f"{d.get('title', '')}")
        return 0

    if args.channel:
        if args.channel not in tokens:
            print(f"Không có token: {args.channel}")
            return 1
        ok = fetch_channel(args.channel, tokens)
        return 0 if ok else 1

    if args.all:
        ok = fail = 0
        for tn in list(tokens.keys()):
            if fetch_channel(tn, tokens):
                ok += 1
            else:
                fail += 1
        print(f"\n=== KẾT QUẢ: OK={ok}  FAIL={fail} ===")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
