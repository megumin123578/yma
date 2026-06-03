# -*- coding: utf-8 -*-
"""core/local_uploader.py — Lưu báo cáo VÀO MÁY.

API: upload_report, sync_watchlists, count_reports, is_configured.
  - Storage: copy HTML vào <local_data_dir>/reports/<date>/<wl_id>.html
  - DB metadata: SQLite <local_data_dir>/data.db (bảng reports + watchlists)

local_data_dir trỏ về <output_dir>/local_serve/ nếu config trống.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# CẤU HÌNH
# ============================================================

def _cfg() -> dict:
    try:
        try:
            from .config import load_config
        except ImportError:
            from .config import load_config
        return load_config()
    except Exception:
        return {}


def data_dir() -> Path:
    """Thư mục gốc lưu data: <local_data_dir> hoặc <output_dir>/local_serve.

    Tự tạo nếu chưa có. Trả Path tuyệt đối.
    """
    cfg = _cfg()
    d = (cfg.get("local_data_dir") or "").strip()
    if not d:
        out = (cfg.get("output_dir") or "").strip()
        if not out:
            # Fallback: cùng cấp project/ để vẫn chạy được khi chưa cấu hình
            out = str(Path(__file__).resolve().parents[1] / "ket_qua")
        d = str(Path(out) / "local_serve")
    p = Path(d)
    p.mkdir(parents=True, exist_ok=True)
    (p / "reports").mkdir(exist_ok=True)
    return p


def db_path() -> Path:
    return data_dir() / "data.db"


def reports_dir() -> Path:
    return data_dir() / "reports"


def is_configured() -> bool:
    """Local uploader luôn dùng được — chỉ cần ghi được file ra máy."""
    try:
        d = data_dir()
        return d.exists() and os.access(d, os.W_OK)
    except Exception:
        return False


# ============================================================
# SQLITE — schema + connection
# ============================================================

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    doc_id TEXT PRIMARY KEY,
    wl_id TEXT NOT NULL,
    wl_name TEXT,
    channel_title TEXT,
    date TEXT NOT NULL,
    report_type TEXT,
    storage_path TEXT,
    size_bytes INTEGER,
    created_at TEXT,
    report_title TEXT,
    display_time TEXT
);
CREATE INDEX IF NOT EXISTS idx_reports_date ON reports(date);
CREATE INDEX IF NOT EXISTS idx_reports_wl_id ON reports(wl_id);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at);

CREATE TABLE IF NOT EXISTS watchlists (
    wl_id TEXT PRIMARY KEY,
    wl_name TEXT,
    channel_title TEXT,
    sort INTEGER,
    updated_at TEXT
);
"""


def _connect() -> sqlite3.Connection:
    """Mở kết nối SQLite + bật WAL (cho phép daily_run ghi trong khi
    FastAPI server đọc cùng lúc không bị khoá).
    """
    conn = sqlite3.connect(str(db_path()), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    return conn


# ============================================================
# UPLOAD — copy file + ghi DB
# ============================================================

def upload_report(wl_id: str, wl_name: str, channel_title: str,
                  html_path: str, date: str = None,
                  report_type: str = "combined", log_fn=None,
                  report_title: str = "",
                  display_time: str = "") -> dict:
    """Lưu 1 báo cáo HTML vào máy + ghi metadata SQLite.

    Trả {ok, reason, url, doc_id, storage_path}. KHÔNG raise.
    """
    def _log(m):
        if log_fn:
            try:
                log_fn(m)
            except Exception:
                pass

    if not (html_path and os.path.exists(html_path)):
        return {"ok": False, "reason": f"không thấy file: {html_path}"}

    date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        size = os.path.getsize(html_path)
        # 1. Copy HTML vào folder local
        rel_path = f"reports/{date}/{wl_id}.html"
        dst = data_dir() / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(html_path, dst)

        # 2. Ghi metadata SQLite (upsert — 1 báo cáo/WL/ngày)
        doc_id = f"{wl_id}__{date}"
        now_iso = datetime.now(timezone.utc).isoformat()
        with _connect() as conn:
            conn.execute("""
                INSERT INTO reports (doc_id, wl_id, wl_name, channel_title,
                    date, report_type, storage_path, size_bytes, created_at,
                    report_title, display_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_id) DO UPDATE SET
                    wl_name = excluded.wl_name,
                    channel_title = excluded.channel_title,
                    report_type = excluded.report_type,
                    storage_path = excluded.storage_path,
                    size_bytes = excluded.size_bytes,
                    created_at = excluded.created_at,
                    report_title = COALESCE(NULLIF(excluded.report_title, ''),
                                            reports.report_title),
                    display_time = COALESCE(NULLIF(excluded.display_time, ''),
                                            reports.display_time)
            """, (doc_id, wl_id, wl_name, channel_title, date, report_type,
                  rel_path, size, now_iso, report_title or None,
                  display_time or None))
            # Đồng thời upsert watchlists (giữ field `sort` nếu đã có)
            conn.execute("""
                INSERT INTO watchlists (wl_id, wl_name, channel_title,
                    updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(wl_id) DO UPDATE SET
                    wl_name = excluded.wl_name,
                    channel_title = excluded.channel_title,
                    updated_at = excluded.updated_at
            """, (wl_id, wl_name, channel_title, now_iso))

        _log(f"  Local: đã lưu báo cáo '{wl_name}' ({date}).")
        return {"ok": True, "reason": "",
                "url": f"/api/reports/{doc_id}/html",
                "doc_id": doc_id, "storage_path": rel_path}
    except Exception as e:
        _log(f"  ! Local upload lỗi: {e}")
        return {"ok": False, "reason": str(e)}


# ============================================================
# SYNC — đồng bộ danh sách watchlist + thứ tự cụm
# ============================================================

def _compute_wl_order() -> dict:
    """Gom cụm watchlist theo ĐỐI THỦ CHUNG → trả {wl_id: sort_index}.

    2 WL cùng cụm nếu chia sẻ >=2 kênh đối thủ (và >=20% so với WL ít
    đối thủ hơn) — gom liên thông bằng union-find. WL cùng cụm được gán
    số thứ tự liền nhau → website xếp gần nhau. Cụm sắp theo tên WL nhỏ
    nhất (a-z); trong cụm sắp theo tên.
    """
    from . import watchlist as wl_mod
    wls = []
    for w in wl_mod.list_watchlists():
        full = wl_mod.load_watchlist(w.id)
        if not full:
            continue
        comp = set(c.channel_id for c in full.competitor_channels
                   if c.channel_id)
        wls.append({"id": full.id, "name": full.name or full.id,
                    "comp": comp})
    n = len(wls)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            ci, cj = wls[i]["comp"], wls[j]["comp"]
            ov = len(ci & cj)
            mn = min(len(ci), len(cj)) or 1
            if ov >= 2 and ov * 100 // mn >= 20:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[rj] = ri

    clusters = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(i)
    cluster_list = []
    for members in clusters.values():
        key = min(wls[m]["name"].lower() for m in members)
        cluster_list.append((key, members))
    cluster_list.sort(key=lambda c: c[0])

    order, idx = {}, 1
    for _key, members in cluster_list:
        for m in sorted(members, key=lambda m: wls[m]["name"].lower()):
            order[wls[m]["id"]] = idx
            idx += 1
    return order


def sync_watchlists(log_fn=None) -> dict:
    """Đẩy danh sách TẤT CẢ watchlist vào SQLite — kèm `sort` (gom cụm
    đối thủ chung). Cho web mới biết tổng số WL + thứ tự hiển thị.
    """
    def _log(m):
        if log_fn:
            try:
                log_fn(m)
            except Exception:
                pass

    if not is_configured():
        return {"ok": False, "reason": "Local data dir không ghi được"}
    try:
        try:
            from . import watchlist as wl_mod
        except ImportError:
            from . import watchlist as wl_mod

        # Tính thứ tự cụm (gom WL chung đối thủ).
        order = {}
        try:
            order = _compute_wl_order()
        except Exception as e:
            _log(f"  ! Tính thứ tự cụm lỗi (bỏ qua): {e}")

        now_iso = datetime.now(timezone.utc).isoformat()
        n = 0
        with _connect() as conn:
            for w in wl_mod.list_watchlists():
                full = wl_mod.load_watchlist(w.id)
                if not full:
                    continue
                sc = full.self_channel
                conn.execute("""
                    INSERT INTO watchlists (wl_id, wl_name, channel_title,
                        sort, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(wl_id) DO UPDATE SET
                        wl_name = excluded.wl_name,
                        channel_title = excluded.channel_title,
                        sort = excluded.sort,
                        updated_at = excluded.updated_at
                """, (w.id, full.name,
                      (sc.title if sc else full.name),
                      order.get(w.id, 9999), now_iso))
                n += 1
        _log(f"  Local: đồng bộ {n} watchlist (kèm thứ tự cụm).")
        return {"ok": True, "count": n}
    except Exception as e:
        return {"ok": False, "reason": str(e)}


# ============================================================
# QUERY — đếm báo cáo theo ngày
# ============================================================

def count_reports(date: str = None) -> int:
    """Đếm số báo cáo đã lưu cho 1 ngày."""
    if not is_configured():
        return 0
    date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM reports WHERE date = ?",
                (date,)).fetchone()
            return int(row["n"]) if row else 0
    except Exception:
        return 0
