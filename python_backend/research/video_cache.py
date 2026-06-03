# -*- coding: utf-8 -*-
"""Bộ nhớ phụ — cache video ID + field cố định.

Chốt 24/05 đêm muộn (user dặn): khi daily run, chỉ enrich video MỚI qua
API (tiết kiệm quota); video CŨ dùng cache field cố định (title,
published_at, duration_seconds, tags, description). Field động
(view/like/comment) vẫn enrich lại từ API.

Cache file: ~/.youtube_research/video_cache.sqlite3
- Concurrent safe (1 writer + N reader OK với WAL mode)
- Index: channel_id để query nhanh "videos của kênh này"

Pattern dùng:
    from .video_cache import (find_new_video_ids, upsert_videos,
                                   get_cached_video_meta)
    # 1. Sau khi list ID từ /videos page:
    new_ids, old_ids = find_new_video_ids(channel_id, all_ids)
    # 2. Enrich new_ids qua API:
    new_videos = enrich_videos(new_ids)
    # 3. Lấy old từ cache + enrich SỐ động:
    old_videos = get_cached_video_meta(old_ids)
    refresh_videos = enrich_videos(old_ids)  # update view/like động
    merge_meta_with_dynamic(old_videos, refresh_videos)
    # 4. Upsert toàn bộ vào cache:
    upsert_videos(channel_id, new_videos + refresh_videos)
"""
from __future__ import annotations
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional


CACHE_DB = Path.home() / ".youtube_research" / "video_cache.sqlite3"
_LOCK = threading.Lock()


def init_db() -> sqlite3.Connection:
    CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CACHE_DB), timeout=30,
                            isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS videos (
        video_id TEXT PRIMARY KEY,
        channel_id TEXT,
        first_seen_at TEXT,
        last_enriched_at TEXT,
        title TEXT,
        published_at TEXT,
        duration_seconds INTEGER,
        tags_json TEXT,
        description TEXT
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_videos_channel
                    ON videos(channel_id)""")
    return conn


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ============================================================
# Public API
# ============================================================
def find_new_video_ids(channel_id: str, all_ids: list) -> tuple:
    """Diff list ID với cache. Trả (new_ids, old_ids).
    new_ids = chưa có trong cache (cần enrich full lần đầu).
    old_ids = đã có (skip cache lookup nếu chỉ cần meta cố định)."""
    if not all_ids:
        return [], []
    with _LOCK:
        conn = init_db()
        try:
            # SQL IN với placeholder
            placeholders = ",".join("?" * len(all_ids))
            rows = conn.execute(
                f"SELECT video_id FROM videos WHERE video_id IN ({placeholders})",
                all_ids
            ).fetchall()
            cached = {r[0] for r in rows}
        finally:
            conn.close()
    new_ids = [v for v in all_ids if v not in cached]
    old_ids = [v for v in all_ids if v in cached]
    return new_ids, old_ids


def get_cached_video_meta(video_ids: list) -> dict:
    """Lấy field cố định từ cache. Trả dict {video_id: {title, published_at,
    duration_seconds, tags, description}}. Bỏ qua field động (view/like/cmt)."""
    if not video_ids:
        return {}
    out = {}
    with _LOCK:
        conn = init_db()
        try:
            placeholders = ",".join("?" * len(video_ids))
            rows = conn.execute(
                f"SELECT video_id, title, published_at, duration_seconds, "
                f"tags_json, description FROM videos "
                f"WHERE video_id IN ({placeholders})",
                video_ids
            ).fetchall()
            for r in rows:
                vid, title, pub, dur, tags_j, desc = r
                tags = []
                try:
                    tags = json.loads(tags_j) if tags_j else []
                except Exception:
                    pass
                out[vid] = {
                    "title": title or "",
                    "published_at": pub or "",
                    "duration_seconds": dur or 0,
                    "tags": tags,
                    "description": desc or "",
                }
        finally:
            conn.close()
    return out


def upsert_videos(channel_id: str, video_objs: list) -> int:
    """Lưu video vào cache. video_objs: list VideoInfo hoặc dict.
    Field cố định ghi đè (in case API trả khác lần đầu). Field động không lưu.
    Trả số rows upserted."""
    if not video_objs:
        return 0
    rows = []
    now = _now()
    for v in video_objs:
        # Support cả VideoInfo dataclass và dict
        if hasattr(v, "video_id"):
            vid = v.video_id
            title = v.title or ""
            pub = v.published_at or ""
            dur = v.duration_seconds or 0
            tags = v.tags or []
            desc = v.description or ""
            cid = (v.channel_id or channel_id) or ""
        elif isinstance(v, dict):
            vid = v.get("video_id") or v.get("id", "")
            title = v.get("title", "")
            pub = v.get("published_at", "")
            dur = v.get("duration_seconds", 0)
            tags = v.get("tags", []) or []
            desc = v.get("description", "")
            cid = v.get("channel_id") or channel_id
        else:
            continue
        if not vid:
            continue
        tags_j = json.dumps(tags, ensure_ascii=False) if tags else "[]"
        rows.append((vid, cid, now, now, title, pub, dur, tags_j, desc))

    if not rows:
        return 0
    with _LOCK:
        conn = init_db()
        try:
            # Upsert: nếu đã có thì update last_enriched_at + các field cố định,
            # KHÔNG đè first_seen_at (giữ ngày đầu phát hiện).
            conn.executemany(
                """INSERT INTO videos
                   (video_id, channel_id, first_seen_at, last_enriched_at,
                    title, published_at, duration_seconds, tags_json, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(video_id) DO UPDATE SET
                     last_enriched_at = excluded.last_enriched_at,
                     title = excluded.title,
                     published_at = excluded.published_at,
                     duration_seconds = excluded.duration_seconds,
                     tags_json = excluded.tags_json,
                     description = excluded.description""",
                rows)
        finally:
            conn.close()
    return len(rows)


def stats() -> dict:
    """Thống kê cache. Trả {total_videos, total_channels, oldest_first_seen}."""
    with _LOCK:
        conn = init_db()
        try:
            r = conn.execute(
                "SELECT COUNT(*), COUNT(DISTINCT channel_id), "
                "MIN(first_seen_at) FROM videos").fetchone()
            return {
                "total_videos": r[0] or 0,
                "total_channels": r[1] or 0,
                "oldest_first_seen": r[2] or "",
            }
        finally:
            conn.close()


def get_channel_video_count(channel_id: str) -> int:
    """Số video đã cache của 1 channel."""
    with _LOCK:
        conn = init_db()
        try:
            r = conn.execute(
                "SELECT COUNT(*) FROM videos WHERE channel_id = ?",
                (channel_id,)).fetchone()
            return r[0] or 0
        finally:
            conn.close()
