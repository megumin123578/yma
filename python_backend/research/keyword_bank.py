# -*- coding: utf-8 -*-
"""core/keyword_bank.py — Kho từ khoá keywordtool.io.

Lưu từ khoá 3 cấp cho từng kênh chính, tích luỹ qua nhiều ngày.

- Cấp 1: seed ngắn (1-2 từ), lượt tìm kiếm cao.
- Cấp 2: cấp 1 + 1-2 từ.
- Cấp 3: cấp 2 + 1-2 từ (= cấp 1 + 3+ từ).

DB: <data>/keywords.sqlite3 (cùng chỗ snapshots — exe đọc được).
Bảng `seeds`: danh sách seed cấp 1 cần tìm + trạng thái thu hoạch.
Bảng `keywords`: ~1000 từ khoá/seed keywordtool trả về + volume + cạnh tranh.

Module pure-Python (đóng exe được). KHÔNG gọi MCP — việc gọi
keywordtool do Claude làm, rồi nạp kết quả vào đây qua store_result().
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path


def _data_dir() -> Path:
    """Thư mục data người dùng (tôn trọng shared_history_dir nếu có)."""
    try:
        try:
            from .config import load_config
        except ImportError:
            from .config import load_config
        shared = (load_config().get("shared_history_dir") or "").strip()
        if shared:
            d = Path(shared)
            if d.is_file() or d.suffix:
                d = d.parent
            return d
    except Exception:
        pass
    return Path.home() / ".youtube_research"


def db_path() -> Path:
    d = _data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "keywords.sqlite3"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def norm(s: str) -> str:
    """Chuẩn hoá từ khoá để so/dò trùng."""
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def word_count(s: str) -> int:
    return len(re.findall(r"[^\s]+", (s or "").strip()))


def classify_level(keyword: str, seed: str) -> int:
    """Cấp 1/2/3 theo số từ thêm so với seed cấp 1."""
    extra = word_count(keyword) - word_count(seed)
    if extra <= 0:
        return 1
    if extra <= 2:
        return 2
    return 3


# ============================================================
# KHỞI TẠO DB
# ============================================================

def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path()), timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS seeds (
            norm          TEXT PRIMARY KEY,
            seed          TEXT NOT NULL,
            word_count    INTEGER,
            priority      REAL DEFAULT 0,
            channels      TEXT,         -- JSON [{wl_id,channel_id,title,views}]
            status        TEXT DEFAULT 'pending',  -- pending/done/error
            fetched_at    TEXT,
            result_count  INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS keywords (
            norm              TEXT NOT NULL,
            keyword           TEXT NOT NULL,
            seed_norm         TEXT NOT NULL,
            level             INTEGER,
            word_count        INTEGER,
            search_volume     INTEGER,
            competition       REAL,
            competition_label TEXT,
            cpc               REAL,
            trend             REAL,
            fetched_at        TEXT,
            PRIMARY KEY (norm, seed_norm)
        );
        CREATE INDEX IF NOT EXISTS idx_kw_seed ON keywords(seed_norm);
        CREATE INDEX IF NOT EXISTS idx_kw_vol  ON keywords(search_volume);
        CREATE INDEX IF NOT EXISTS idx_kw_norm ON keywords(norm);
        """)
        conn.commit()
    finally:
        conn.close()


# ============================================================
# SEEDS
# ============================================================

def add_or_update_seeds(seed_dicts: list) -> int:
    """Thêm/cập nhật seed. seed_dicts: [{seed, priority, channels}].
    KHÔNG reset trạng thái seed đã 'done'. Trả số seed mới thêm."""
    init_db()
    conn = connect()
    added = 0
    try:
        cur = conn.cursor()
        for d in seed_dicts:
            s = (d.get("seed") or "").strip()
            if not s:
                continue
            n = norm(s)
            ch = json.dumps(d.get("channels") or [], ensure_ascii=False)
            row = cur.execute(
                "SELECT status FROM seeds WHERE norm=?", (n,)).fetchone()
            if row:
                # cập nhật priority + channels, GIỮ status
                cur.execute(
                    "UPDATE seeds SET seed=?, word_count=?, priority=?, "
                    "channels=? WHERE norm=?",
                    (s, word_count(s), float(d.get("priority") or 0),
                     ch, n))
            else:
                cur.execute(
                    "INSERT INTO seeds (norm, seed, word_count, priority, "
                    "channels, status) VALUES (?,?,?,?,?,'pending')",
                    (n, s, word_count(s), float(d.get("priority") or 0),
                     ch))
                added += 1
        conn.commit()
    finally:
        conn.close()
    return added


def pending_seeds(limit: int = 0) -> list:
    """Seed chưa thu hoạch, ưu tiên cao trước. limit=0 = tất cả."""
    init_db()
    conn = connect()
    try:
        q = ("SELECT norm, seed, priority, channels FROM seeds "
             "WHERE status='pending' ORDER BY priority DESC, seed ASC")
        if limit and limit > 0:
            q += f" LIMIT {int(limit)}"
        rows = conn.execute(q).fetchall()
    finally:
        conn.close()
    return [{"norm": r[0], "seed": r[1], "priority": r[2],
             "channels": json.loads(r[3] or "[]")} for r in rows]


def mark_seed(seed_norm: str, status: str, result_count: int = 0) -> None:
    conn = connect()
    try:
        conn.execute(
            "UPDATE seeds SET status=?, fetched_at=?, result_count=? "
            "WHERE norm=?", (status, _now(), result_count, seed_norm))
        conn.commit()
    finally:
        conn.close()


# ============================================================
# KEYWORDS — nạp kết quả keywordtool
# ============================================================

def store_result(seed: str, keyword_rows: list) -> int:
    """Nạp danh sách từ khoá keywordtool trả về cho 1 seed.

    keyword_rows: [{keyword, search_volume, competition,
    competition_label, cpc, trend}]. Trả số dòng đã ghi.
    """
    init_db()
    seed_n = norm(seed)
    conn = connect()
    n = 0
    try:
        cur = conn.cursor()
        now = _now()
        for r in keyword_rows:
            kw = (r.get("keyword") or "").strip()
            if not kw:
                continue
            kn = norm(kw)
            cur.execute(
                "INSERT OR REPLACE INTO keywords (norm, keyword, seed_norm, "
                "level, word_count, search_volume, competition, "
                "competition_label, cpc, trend, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (kn, kw, seed_n, classify_level(kw, seed), word_count(kw),
                 _as_int(r.get("search_volume")),
                 _as_float(r.get("competition")),
                 (r.get("competition_label") or ""),
                 _as_float(r.get("cpc")),
                 _as_float(r.get("trend")), now))
            n += 1
        conn.commit()
    finally:
        conn.close()
    return n


def _as_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _as_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ============================================================
# THỐNG KÊ + TRUY VẤN
# ============================================================

def stats() -> dict:
    init_db()
    conn = connect()
    try:
        c = conn.cursor()
        seeds_total = c.execute("SELECT COUNT(*) FROM seeds").fetchone()[0]
        seeds_done = c.execute(
            "SELECT COUNT(*) FROM seeds WHERE status='done'").fetchone()[0]
        kw_total = c.execute("SELECT COUNT(*) FROM keywords").fetchone()[0]
        kw_uniq = c.execute(
            "SELECT COUNT(DISTINCT norm) FROM keywords").fetchone()[0]
    finally:
        conn.close()
    return {"seeds_total": seeds_total, "seeds_done": seeds_done,
            "seeds_pending": seeds_total - seeds_done,
            "keywords_total": kw_total, "keywords_unique": kw_uniq}


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    init_db()
    print("keywords.sqlite3:", db_path())
    print("stats:", stats())
