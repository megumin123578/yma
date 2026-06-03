"""
Snapshots - lưu time-series subs/views theo từng kênh và video.
Dùng SQLite để query nhanh theo date range.

Schema:
  - channel_snapshots: 1 row / channel / monitor run → subs, video_count, view_count
  - video_snapshots: latest 30 videos snapshot mỗi monitor run → views, likes...
  - events: sự kiện phát hiện được (early viral, subs spike, new upload...)
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


_DB_LOCK = threading.RLock()


def db_path() -> Path:
    """Path SQLite. Tôn trọng shared folder nếu có."""
    try:
        from .config import load_config
        cfg = load_config()
        shared = cfg.get("shared_history_dir", "").strip()
        if shared:
            d = Path(shared).parent / "snapshots"
            d.mkdir(parents=True, exist_ok=True)
            return d / "snapshots.sqlite3"
    except Exception:
        pass
    d = Path.home() / ".youtube_research"
    d.mkdir(parents=True, exist_ok=True)
    return d / "snapshots.sqlite3"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path()), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Tạo schema nếu chưa có. Idempotent."""
    with _DB_LOCK:
        conn = _connect()
        try:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS channel_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watchlist_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                channel_title TEXT,
                is_self INTEGER DEFAULT 0,
                subscriber_count INTEGER DEFAULT 0,
                video_count INTEGER DEFAULT 0,
                view_count INTEGER DEFAULT 0,
                captured_at TEXT NOT NULL,
                UNIQUE(watchlist_id, channel_id, captured_at)
            );

            CREATE INDEX IF NOT EXISTS idx_chsnap_channel
                ON channel_snapshots(channel_id, captured_at);
            CREATE INDEX IF NOT EXISTS idx_chsnap_watchlist
                ON channel_snapshots(watchlist_id, captured_at);

            CREATE TABLE IF NOT EXISTS video_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_snapshot_id INTEGER NOT NULL,
                video_id TEXT NOT NULL,
                title TEXT,
                published_at TEXT,
                view_count INTEGER DEFAULT 0,
                like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                views_per_hour REAL DEFAULT 0,
                viral_score REAL DEFAULT 0,
                is_early_viral INTEGER DEFAULT 0,
                FOREIGN KEY (channel_snapshot_id)
                    REFERENCES channel_snapshots(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_vidsnap_video
                ON video_snapshots(video_id);
            CREATE INDEX IF NOT EXISTS idx_vidsnap_parent
                ON video_snapshots(channel_snapshot_id);

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watchlist_id TEXT NOT NULL,
                channel_id TEXT,
                channel_title TEXT,
                video_id TEXT,
                event_type TEXT NOT NULL,
                severity TEXT DEFAULT 'medium',
                title TEXT NOT NULL,
                description TEXT,
                data_json TEXT,
                detected_at TEXT NOT NULL,
                acknowledged INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_events_watchlist
                ON events(watchlist_id, detected_at);
            CREATE INDEX IF NOT EXISTS idx_events_unack
                ON events(acknowledged, detected_at);

            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT,
                video_id TEXT NOT NULL,
                comment_key TEXT NOT NULL,
                author TEXT,
                text TEXT,
                like_count INTEGER DEFAULT 0,
                time_text TEXT,
                fetched_at TEXT,
                UNIQUE(video_id, comment_key)
            );

            CREATE INDEX IF NOT EXISTS idx_comments_video
                ON comments(video_id);
            CREATE INDEX IF NOT EXISTS idx_comments_channel
                ON comments(channel_id);
            """)
        finally:
            conn.close()


# ============================================================
# Channel snapshots
# ============================================================

def save_channel_snapshot(
    watchlist_id: str,
    channel_id: str,
    channel_title: str,
    is_self: bool,
    subscriber_count: int,
    video_count: int,
    view_count: int,
    captured_at: str = "",
) -> int:
    """Lưu 1 snapshot kênh. Trả về row id."""
    init_db()
    if not captured_at:
        captured_at = datetime.now().isoformat(timespec="seconds")
    with _DB_LOCK:
        conn = _connect()
        try:
            cur = conn.execute("""
                INSERT INTO channel_snapshots
                    (watchlist_id, channel_id, channel_title, is_self,
                     subscriber_count, video_count, view_count, captured_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(watchlist_id, channel_id, captured_at)
                DO UPDATE SET
                    subscriber_count=excluded.subscriber_count,
                    video_count=excluded.video_count,
                    view_count=excluded.view_count,
                    channel_title=excluded.channel_title,
                    is_self=excluded.is_self
            """, (watchlist_id, channel_id, channel_title, 1 if is_self else 0,
                  subscriber_count, video_count, view_count, captured_at))
            return cur.lastrowid
        finally:
            conn.close()


def get_latest_channel_snapshot(watchlist_id: str,
                                channel_id: str) -> Optional[dict]:
    """Lấy snapshot kênh gần nhất."""
    init_db()
    with _DB_LOCK:
        conn = _connect()
        try:
            row = conn.execute("""
                SELECT * FROM channel_snapshots
                WHERE watchlist_id=? AND channel_id=?
                ORDER BY captured_at DESC LIMIT 1
            """, (watchlist_id, channel_id)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def get_channel_snapshot_before(watchlist_id: str, channel_id: str,
                                 before_time: str) -> Optional[dict]:
    """Snapshot ngay trước thời điểm before_time. Dùng để tính delta."""
    init_db()
    with _DB_LOCK:
        conn = _connect()
        try:
            row = conn.execute("""
                SELECT * FROM channel_snapshots
                WHERE watchlist_id=? AND channel_id=? AND captured_at < ?
                ORDER BY captured_at DESC LIMIT 1
            """, (watchlist_id, channel_id, before_time)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def get_channel_history(watchlist_id: str, channel_id: str,
                        days_back: int = 90) -> list:
    """Lấy tất cả snapshots của 1 kênh trong N ngày qua. Sort theo time ASC."""
    init_db()
    cutoff = (datetime.now() - timedelta(days=days_back)).isoformat(
        timespec="seconds")
    with _DB_LOCK:
        conn = _connect()
        try:
            rows = conn.execute("""
                SELECT * FROM channel_snapshots
                WHERE watchlist_id=? AND channel_id=? AND captured_at >= ?
                ORDER BY captured_at ASC
            """, (watchlist_id, channel_id, cutoff)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


# ============================================================
# Video snapshots
# ============================================================

def save_video_snapshot(
    channel_snapshot_id: int,
    video_id: str,
    title: str,
    published_at: str,
    view_count: int,
    like_count: int,
    comment_count: int,
    views_per_hour: float = 0.0,
    viral_score: float = 0.0,
    is_early_viral: bool = False,
) -> int:
    """Lưu 1 snapshot video."""
    init_db()
    with _DB_LOCK:
        conn = _connect()
        try:
            cur = conn.execute("""
                INSERT INTO video_snapshots
                    (channel_snapshot_id, video_id, title, published_at,
                     view_count, like_count, comment_count, views_per_hour,
                     viral_score, is_early_viral)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (channel_snapshot_id, video_id, title, published_at,
                  view_count, like_count, comment_count, views_per_hour,
                  viral_score, 1 if is_early_viral else 0))
            return cur.lastrowid
        finally:
            conn.close()


def get_previous_video_snapshot(video_id: str,
                                before_time: str) -> Optional[dict]:
    """Snapshot video trước thời điểm before_time. Dùng để tính delta views."""
    init_db()
    with _DB_LOCK:
        conn = _connect()
        try:
            row = conn.execute("""
                SELECT v.*, c.captured_at as snapshot_time
                FROM video_snapshots v
                JOIN channel_snapshots c ON v.channel_snapshot_id = c.id
                WHERE v.video_id=? AND c.captured_at < ?
                ORDER BY c.captured_at DESC LIMIT 1
            """, (video_id, before_time)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def get_video_history(video_id: str) -> list:
    """Time-series view count cho 1 video. Trả list dict sort time ASC."""
    init_db()
    with _DB_LOCK:
        conn = _connect()
        try:
            rows = conn.execute("""
                SELECT v.*, c.captured_at as snapshot_time
                FROM video_snapshots v
                JOIN channel_snapshots c ON v.channel_snapshot_id = c.id
                WHERE v.video_id=?
                ORDER BY c.captured_at ASC
            """, (video_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


# ============================================================
# Events
# ============================================================

def save_event(
    watchlist_id: str,
    event_type: str,
    title: str,
    description: str = "",
    severity: str = "medium",
    channel_id: str = "",
    channel_title: str = "",
    video_id: str = "",
    data: Optional[dict] = None,
    detected_at: str = "",
) -> int:
    """Lưu 1 sự kiện."""
    init_db()
    if not detected_at:
        detected_at = datetime.now().isoformat(timespec="seconds")
    data_json = json.dumps(data or {}, ensure_ascii=False)
    with _DB_LOCK:
        conn = _connect()
        try:
            cur = conn.execute("""
                INSERT INTO events
                    (watchlist_id, channel_id, channel_title, video_id,
                     event_type, severity, title, description, data_json,
                     detected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (watchlist_id, channel_id, channel_title, video_id,
                  event_type, severity, title, description, data_json,
                  detected_at))
            return cur.lastrowid
        finally:
            conn.close()


def list_events(watchlist_id: str = "", days_back: int = 7,
                only_unacknowledged: bool = False,
                severity: str = "") -> list:
    """List events, mới nhất trước."""
    init_db()
    cutoff = (datetime.now() - timedelta(days=days_back)).isoformat(
        timespec="seconds")
    sql = "SELECT * FROM events WHERE detected_at >= ?"
    params = [cutoff]
    if watchlist_id:
        sql += " AND watchlist_id=?"
        params.append(watchlist_id)
    if only_unacknowledged:
        sql += " AND acknowledged=0"
    if severity:
        sql += " AND severity=?"
        params.append(severity)
    sql += " ORDER BY detected_at DESC"
    with _DB_LOCK:
        conn = _connect()
        try:
            rows = conn.execute(sql, params).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                try:
                    d["data"] = json.loads(d.get("data_json") or "{}")
                except Exception:
                    d["data"] = {}
                out.append(d)
            return out
        finally:
            conn.close()


def get_subscriber_history(watchlist_id: str, max_dates: int = 8) -> dict:
    """Lịch sử người đăng ký các kênh trong watchlist qua các kỳ giám sát.

    Gom snapshot theo NGÀY (mỗi ngày lấy bản mới nhất của mỗi kênh).
    Trả dict {dates: [...], channels: [{channel_id, title, is_self,
    subs: {date: count}}]}.
    """
    init_db()
    with _DB_LOCK:
        conn = _connect()
        try:
            rows = conn.execute("""
                SELECT channel_id, channel_title, is_self,
                       subscriber_count, captured_at
                FROM channel_snapshots
                WHERE watchlist_id=?
                ORDER BY captured_at ASC
            """, (watchlist_id,)).fetchall()
        finally:
            conn.close()
    per_ch = {}
    all_dates = set()
    for r in rows:
        cid = r["channel_id"]
        date = (r["captured_at"] or "")[:10]
        if not cid or not date:
            continue
        all_dates.add(date)
        ent = per_ch.setdefault(cid, {
            "channel_id": cid, "title": r["channel_title"] or cid,
            "is_self": False, "subs": {}})
        if r["channel_title"]:
            ent["title"] = r["channel_title"]
        if r["is_self"]:
            ent["is_self"] = True
        # rows sort tăng dần => bản sau (mới hơn trong ngày) ghi đè
        ent["subs"][date] = r["subscriber_count"] or 0
    dates = sorted(all_dates)[-max_dates:]
    channels = sorted(
        per_ch.values(),
        key=lambda c: (not c["is_self"],
                       -(max(c["subs"].values()) if c["subs"] else 0)))
    return {"dates": dates, "channels": channels}


def acknowledge_event(event_id: int) -> None:
    init_db()
    with _DB_LOCK:
        conn = _connect()
        try:
            conn.execute("UPDATE events SET acknowledged=1 WHERE id=?",
                         (event_id,))
        finally:
            conn.close()


def acknowledge_all(watchlist_id: str = "") -> int:
    init_db()
    sql = "UPDATE events SET acknowledged=1 WHERE acknowledged=0"
    params = []
    if watchlist_id:
        sql += " AND watchlist_id=?"
        params.append(watchlist_id)
    with _DB_LOCK:
        conn = _connect()
        try:
            cur = conn.execute(sql, params)
            return cur.rowcount
        finally:
            conn.close()


# ============================================================
# Comments (bình luận khán giả)
# ============================================================

def save_comments(channel_id: str, video_id: str,
                  comments: list) -> int:
    """Lưu bình luận của 1 video. INSERT OR IGNORE → tự bỏ bình luận
    trùng (theo comment_key). Trả về SỐ bình luận MỚI được thêm.

    comments: list dict {comment_key, author, text, like_count,
                          time_text}
    """
    init_db()
    if not comments:
        return 0
    now = datetime.now().isoformat(timespec="seconds")
    new_count = 0
    with _DB_LOCK:
        conn = _connect()
        try:
            for c in comments:
                key = c.get("comment_key", "")
                if not key:
                    continue
                cur = conn.execute("""
                    INSERT OR IGNORE INTO comments
                        (channel_id, video_id, comment_key, author, text,
                         like_count, time_text, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (channel_id, video_id, key,
                      c.get("author", ""), c.get("text", ""),
                      c.get("like_count", 0), c.get("time_text", ""),
                      now))
                if cur.rowcount > 0:
                    new_count += 1
            return new_count
        finally:
            conn.close()


def get_comment_keys(video_id: str) -> set:
    """Trả set comment_key đã lưu của 1 video (để biết cái nào đã có)."""
    init_db()
    with _DB_LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT comment_key FROM comments WHERE video_id=?",
                (video_id,)).fetchall()
            return {r["comment_key"] for r in rows}
        finally:
            conn.close()


def get_comments(channel_id: str = "", video_id: str = "") -> list:
    """Lấy bình luận đã lưu. Lọc theo channel_id hoặc video_id."""
    init_db()
    sql = "SELECT * FROM comments WHERE 1=1"
    params = []
    if channel_id:
        sql += " AND channel_id=?"
        params.append(channel_id)
    if video_id:
        sql += " AND video_id=?"
        params.append(video_id)
    sql += " ORDER BY like_count DESC"
    with _DB_LOCK:
        conn = _connect()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()


def count_comments(channel_id: str = "", video_id: str = "") -> int:
    """Đếm số bình luận đã lưu."""
    init_db()
    sql = "SELECT COUNT(*) FROM comments WHERE 1=1"
    params = []
    if channel_id:
        sql += " AND channel_id=?"
        params.append(channel_id)
    if video_id:
        sql += " AND video_id=?"
        params.append(video_id)
    with _DB_LOCK:
        conn = _connect()
        try:
            return conn.execute(sql, params).fetchone()[0]
        finally:
            conn.close()


# ============================================================
# Stats / cleanup
# ============================================================

def stats() -> dict:
    """Số liệu tổng quan database."""
    init_db()
    with _DB_LOCK:
        conn = _connect()
        try:
            ch_count = conn.execute(
                "SELECT COUNT(*) FROM channel_snapshots").fetchone()[0]
            vid_count = conn.execute(
                "SELECT COUNT(*) FROM video_snapshots").fetchone()[0]
            ev_count = conn.execute(
                "SELECT COUNT(*) FROM events").fetchone()[0]
            ev_unack = conn.execute(
                "SELECT COUNT(*) FROM events WHERE acknowledged=0").fetchone()[0]
            return {
                "channel_snapshots": ch_count,
                "video_snapshots": vid_count,
                "events": ev_count,
                "events_unacknowledged": ev_unack,
            }
        finally:
            conn.close()


def cleanup_old(days_keep: int = 180) -> int:
    """Xoá snapshots cũ hơn N ngày. Giữ events. Trả về số row đã xoá."""
    init_db()
    cutoff = (datetime.now() - timedelta(days=days_keep)).isoformat(
        timespec="seconds")
    with _DB_LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                "DELETE FROM channel_snapshots WHERE captured_at < ?",
                (cutoff,))
            return cur.rowcount
        finally:
            conn.close()
