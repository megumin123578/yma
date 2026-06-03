# -*- coding: utf-8 -*-
"""Bộ nhớ phụ — cache channel discovery per WL.

Chốt 24/05 đêm muộn (user dặn): mỗi WL lưu danh sách channel đã từng
phát hiện qua discover, kèm trạng thái (kết nạp / bị loại). Hôm sau
discover: skip channel đã loại nhiều lần (tiết kiệm thời gian + tránh
re-check kênh không thuộc ngách).

Cache file: ~/.youtube_research/wl_cache.sqlite3

Pattern dùng:
    from .wl_cache import record_seen, is_already_rejected
    # Sau discover 1 channel candidate:
    record_seen(wl_id, channel_id, accepted=True, overlap=0.65)
    # Trước discover hôm sau:
    if is_already_rejected(wl_id, channel_id, threshold=3):
        skip  # Đã bị loại 3+ lần, không cần check lại
"""
from __future__ import annotations
import sqlite3
import threading
from datetime import datetime
from pathlib import Path


CACHE_DB = Path.home() / ".youtube_research" / "wl_cache.sqlite3"
_LOCK = threading.Lock()


def init_db() -> sqlite3.Connection:
    CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CACHE_DB), timeout=30,
                            isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS wl_channels_seen (
        wl_id TEXT NOT NULL,
        channel_id TEXT NOT NULL,
        first_seen_at TEXT NOT NULL,
        last_checked_at TEXT,
        accepted INTEGER DEFAULT 0,
        overlap_score REAL DEFAULT 0,
        times_checked INTEGER DEFAULT 1,
        times_rejected INTEGER DEFAULT 0,
        notes TEXT,
        PRIMARY KEY (wl_id, channel_id)
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_wl_channels_wl
                    ON wl_channels_seen(wl_id)""")
    return conn


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ============================================================
# Public API
# ============================================================
def record_seen(wl_id: str, channel_id: str,
                accepted: bool = False, overlap: float = 0.0,
                notes: str = "") -> None:
    """Ghi 1 channel đã thấy qua discover. Upsert: tăng times_checked +
    cập nhật trạng thái mới nhất."""
    if not (wl_id and channel_id):
        return
    now = _now()
    with _LOCK:
        conn = init_db()
        try:
            conn.execute(
                """INSERT INTO wl_channels_seen
                   (wl_id, channel_id, first_seen_at, last_checked_at,
                    accepted, overlap_score, times_checked, times_rejected, notes)
                   VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                   ON CONFLICT(wl_id, channel_id) DO UPDATE SET
                     last_checked_at = excluded.last_checked_at,
                     accepted = excluded.accepted,
                     overlap_score = excluded.overlap_score,
                     times_checked = times_checked + 1,
                     times_rejected = times_rejected + (CASE WHEN excluded.accepted=0 THEN 1 ELSE 0 END),
                     notes = excluded.notes""",
                (wl_id, channel_id, now, now,
                 1 if accepted else 0, float(overlap),
                 0 if accepted else 1, notes))
        finally:
            conn.close()


def is_already_rejected(wl_id: str, channel_id: str,
                         threshold: int = 3) -> bool:
    """Channel đã bị loại ≥threshold lần → skip discover lần này."""
    with _LOCK:
        conn = init_db()
        try:
            r = conn.execute(
                "SELECT times_rejected, accepted FROM wl_channels_seen "
                "WHERE wl_id = ? AND channel_id = ?",
                (wl_id, channel_id)).fetchone()
            if not r:
                return False
            times_rejected, accepted = r
            # Nếu lần cuối được kết nạp → KHÔNG skip (có thể vẫn relevant)
            if accepted:
                return False
            return (times_rejected or 0) >= threshold
        finally:
            conn.close()


def get_accepted_channels(wl_id: str) -> list:
    """List channel_id đã kết nạp gần nhất vào WL."""
    with _LOCK:
        conn = init_db()
        try:
            rows = conn.execute(
                "SELECT channel_id, overlap_score, last_checked_at "
                "FROM wl_channels_seen "
                "WHERE wl_id = ? AND accepted = 1 "
                "ORDER BY overlap_score DESC",
                (wl_id,)).fetchall()
            return [{"channel_id": r[0], "overlap": r[1] or 0,
                     "last_checked": r[2]} for r in rows]
        finally:
            conn.close()


def get_seen_count(wl_id: str) -> dict:
    """Thống kê cho 1 WL. Trả {total_seen, accepted, rejected, skipped_recently}."""
    with _LOCK:
        conn = init_db()
        try:
            r = conn.execute(
                "SELECT COUNT(*), SUM(accepted), "
                "SUM(CASE WHEN times_rejected >= 3 THEN 1 ELSE 0 END) "
                "FROM wl_channels_seen WHERE wl_id = ?",
                (wl_id,)).fetchone()
            return {
                "total_seen": r[0] or 0,
                "accepted": r[1] or 0,
                "skipped_recently": r[2] or 0,
            }
        finally:
            conn.close()


def stats() -> dict:
    """Stats toàn cache."""
    with _LOCK:
        conn = init_db()
        try:
            r = conn.execute(
                "SELECT COUNT(*), COUNT(DISTINCT wl_id), "
                "COUNT(DISTINCT channel_id) FROM wl_channels_seen"
            ).fetchone()
            return {
                "total_entries": r[0] or 0,
                "total_wls": r[1] or 0,
                "total_unique_channels": r[2] or 0,
            }
        finally:
            conn.close()
