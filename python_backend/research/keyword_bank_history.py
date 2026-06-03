# -*- coding: utf-8 -*-
"""core/keyword_bank_history.py — Snapshot + diff lịch sử kho từ khoá.

Track theo MỖI LẦN CHẠY (phương án B + A combo, user chốt 26/05 chiều):

- `kw_bank_snapshot` (FULL, giữ 90 ngày, rotate sau): mỗi lần chạy
  daily_run → 1 row/WL → lưu top_golden + niche_clusters + coverage_gap.
- `kw_bank_diff` (DIFF, vĩnh viễn): so với snapshot trước → lưu
  {new, lost, changed} top vàng.

DB: cùng `keywords.sqlite3` (đặt cạnh seeds + keywords).

Hook:
- `take_snapshot(wid, bank_data)` — gọi trong stage_keyword sau khi
  `get_channel_kw_bank()` trả data
- `compute_and_save_diff(wid, current_bank, snapshot_id)` — so với snapshot
  trước (cùng wl_id) → save diff JSON
- `get_history(wid, days)` — lấy snapshots + diffs N ngày qua để render
  tab HTML "Lịch sử kho từ khoá"
- `rotate_old_snapshots(keep_days)` — xoá snapshot > 90 ngày
  (diff vẫn giữ)

Threshold:
- "Đổi mạnh" = volume đổi ≥ 20% HOẶC comp đổi ≥ 0.15
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

try:
    from . import keyword_bank
except ImportError:
    from . import keyword_bank


VOLUME_CHANGE_PCT_THRESHOLD = 0.20  # 20%
COMP_CHANGE_THRESHOLD = 0.15
TOP_GOLDEN_FOR_DIFF = 100  # so sánh top 100 vàng


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _gen_snapshot_id(wid: str) -> str:
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{wid}"


def init_history_db() -> None:
    """Tạo 2 bảng + index nếu chưa có."""
    conn = keyword_bank.connect()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kw_bank_snapshot (
                snapshot_id TEXT PRIMARY KEY,
                wl_id TEXT NOT NULL,
                channel_id TEXT,
                channel_title TEXT,
                taken_at TEXT NOT NULL,
                kw_total INTEGER,
                kw_golden_count INTEGER,
                seeds_done INTEGER,
                seeds_total INTEGER,
                status TEXT,
                top_golden_json TEXT,
                niche_clusters_json TEXT,
                coverage_gap_json TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kbs_wlid "
                     "ON kw_bank_snapshot(wl_id, taken_at DESC)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kw_bank_diff (
                diff_id TEXT PRIMARY KEY,
                wl_id TEXT NOT NULL,
                channel_id TEXT,
                taken_at TEXT NOT NULL,
                vs_snapshot_id TEXT,
                new_count INTEGER,
                lost_count INTEGER,
                changed_count INTEGER,
                changes_json TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kbd_wlid "
                     "ON kw_bank_diff(wl_id, taken_at DESC)")
        conn.commit()
    finally:
        conn.close()


def take_snapshot(wid: str, bank_data: dict,
                  channel_id: str = "",
                  channel_title: str = "") -> Optional[str]:
    """Lưu snapshot FULL kho từ khoá cho 1 WL.

    Returns snapshot_id hoặc None nếu bank_data rỗng.
    """
    if not bank_data:
        return None
    init_history_db()
    snapshot_id = _gen_snapshot_id(wid)
    top_golden = bank_data.get("top_golden") or bank_data.get("top_vang") or []
    niche_clusters = bank_data.get("niche_clusters") or []
    coverage_gap = bank_data.get("coverage_gap") or []
    conn = keyword_bank.connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO kw_bank_snapshot "
            "(snapshot_id, wl_id, channel_id, channel_title, taken_at, "
            " kw_total, kw_golden_count, seeds_done, seeds_total, status, "
            " top_golden_json, niche_clusters_json, coverage_gap_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (snapshot_id, wid, channel_id, channel_title, _now(),
             int(bank_data.get("kw_total") or 0),
             int(bank_data.get("kw_golden") or len(top_golden) or 0),
             int(bank_data.get("seeds_done") or 0),
             int(bank_data.get("seeds_total") or 0),
             str(bank_data.get("status") or ""),
             json.dumps(top_golden, ensure_ascii=False),
             json.dumps(niche_clusters, ensure_ascii=False),
             json.dumps(coverage_gap, ensure_ascii=False)))
        conn.commit()
    finally:
        conn.close()
    return snapshot_id


def get_latest_snapshot(wid: str,
                        before_id: Optional[str] = None) -> Optional[dict]:
    """Lấy snapshot mới nhất của WL. Nếu before_id, lấy snapshot trước id đó."""
    conn = keyword_bank.connect()
    try:
        if before_id:
            row = conn.execute(
                "SELECT snapshot_id, wl_id, channel_id, channel_title, "
                "taken_at, kw_total, kw_golden_count, seeds_done, "
                "seeds_total, status, top_golden_json, niche_clusters_json, "
                "coverage_gap_json "
                "FROM kw_bank_snapshot WHERE wl_id = ? AND snapshot_id < ? "
                "ORDER BY snapshot_id DESC LIMIT 1",
                (wid, before_id)).fetchone()
        else:
            row = conn.execute(
                "SELECT snapshot_id, wl_id, channel_id, channel_title, "
                "taken_at, kw_total, kw_golden_count, seeds_done, "
                "seeds_total, status, top_golden_json, niche_clusters_json, "
                "coverage_gap_json "
                "FROM kw_bank_snapshot WHERE wl_id = ? "
                "ORDER BY snapshot_id DESC LIMIT 1",
                (wid,)).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "snapshot_id": row[0],
        "wl_id": row[1],
        "channel_id": row[2],
        "channel_title": row[3],
        "taken_at": row[4],
        "kw_total": row[5],
        "kw_golden_count": row[6],
        "seeds_done": row[7],
        "seeds_total": row[8],
        "status": row[9],
        "top_golden": json.loads(row[10] or "[]"),
        "niche_clusters": json.loads(row[11] or "[]"),
        "coverage_gap": json.loads(row[12] or "[]"),
    }


def compute_diff(prev_top_golden: list,
                 curr_top_golden: list) -> dict:
    """So sánh 2 list top_golden. Trả dict {new, lost, changed}."""
    prev_map = {k.get("keyword", "").lower(): k for k in prev_top_golden
                if k.get("keyword")}
    curr_map = {k.get("keyword", "").lower(): k for k in curr_top_golden
                if k.get("keyword")}
    prev_keys = set(prev_map.keys())
    curr_keys = set(curr_map.keys())
    new_keys = curr_keys - prev_keys
    lost_keys = prev_keys - curr_keys
    common = prev_keys & curr_keys

    new_items = [curr_map[k] for k in new_keys]
    new_items.sort(key=lambda x: x.get("volume", 0) or 0, reverse=True)

    lost_items = [prev_map[k] for k in lost_keys]
    lost_items.sort(key=lambda x: x.get("volume", 0) or 0, reverse=True)

    changed_items = []
    for k in common:
        p = prev_map[k]
        c = curr_map[k]
        p_vol = int(p.get("volume") or 0)
        c_vol = int(c.get("volume") or 0)
        p_comp = float(p.get("comp") or 0)
        c_comp = float(c.get("comp") or 0)
        vol_pct = (c_vol - p_vol) / max(p_vol, 1)
        comp_delta = c_comp - p_comp
        if (abs(vol_pct) >= VOLUME_CHANGE_PCT_THRESHOLD
                or abs(comp_delta) >= COMP_CHANGE_THRESHOLD):
            changed_items.append({
                "keyword": c.get("keyword"),
                "old_volume": p_vol, "new_volume": c_vol,
                "vol_pct": round(vol_pct * 100, 1),
                "old_comp": round(p_comp, 3),
                "new_comp": round(c_comp, 3),
                "comp_delta": round(comp_delta, 3),
                "score": c.get("score", 0),
            })
    changed_items.sort(key=lambda x: abs(x.get("vol_pct", 0)), reverse=True)
    return {"new": new_items[:50],
            "lost": lost_items[:50],
            "changed": changed_items[:50]}


def compute_and_save_diff(wid: str, channel_id: str,
                          curr_snapshot_id: str,
                          curr_top_golden: list) -> Optional[dict]:
    """So với snapshot trước (cùng wid), save diff. Trả diff dict."""
    init_history_db()
    prev = get_latest_snapshot(wid, before_id=curr_snapshot_id)
    if not prev:
        return None  # lần đầu — không có diff
    diff = compute_diff(prev["top_golden"], curr_top_golden)
    diff_id = curr_snapshot_id  # 1-1 mapping
    conn = keyword_bank.connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO kw_bank_diff "
            "(diff_id, wl_id, channel_id, taken_at, vs_snapshot_id, "
            " new_count, lost_count, changed_count, changes_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (diff_id, wid, channel_id, _now(), prev["snapshot_id"],
             len(diff["new"]), len(diff["lost"]), len(diff["changed"]),
             json.dumps(diff, ensure_ascii=False)))
        conn.commit()
    finally:
        conn.close()
    return {**diff, "vs_snapshot_id": prev["snapshot_id"],
            "vs_taken_at": prev["taken_at"]}


def get_history(wid: str, days: int = 30) -> dict:
    """Lấy lịch sử N ngày qua: timeline + diffs + latest snapshot.

    Output:
    {
        "wl_id": "...",
        "timeline": [{taken_at, kw_total, kw_golden_count, status}, ...],
        "latest_diff": {new: [...], lost: [...], changed: [...], ...},
        "latest_snapshot": {...},
        "diff_history": [{taken_at, new_count, lost_count, changed_count}, ...]
    }
    """
    init_history_db()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = keyword_bank.connect()
    try:
        snaps = conn.execute(
            "SELECT taken_at, kw_total, kw_golden_count, status, "
            "seeds_done, seeds_total "
            "FROM kw_bank_snapshot WHERE wl_id = ? AND taken_at >= ? "
            "ORDER BY taken_at ASC", (wid, cutoff)).fetchall()
        diffs = conn.execute(
            "SELECT taken_at, new_count, lost_count, changed_count, "
            "vs_snapshot_id "
            "FROM kw_bank_diff WHERE wl_id = ? AND taken_at >= ? "
            "ORDER BY taken_at ASC", (wid, cutoff)).fetchall()
        latest_diff_row = conn.execute(
            "SELECT changes_json, vs_snapshot_id, taken_at "
            "FROM kw_bank_diff WHERE wl_id = ? "
            "ORDER BY taken_at DESC LIMIT 1", (wid,)).fetchone()
    finally:
        conn.close()

    timeline = [{"taken_at": r[0], "kw_total": r[1],
                 "kw_golden_count": r[2], "status": r[3],
                 "seeds_done": r[4], "seeds_total": r[5]} for r in snaps]
    diff_history = [{"taken_at": r[0], "new_count": r[1],
                     "lost_count": r[2], "changed_count": r[3],
                     "vs_snapshot_id": r[4]} for r in diffs]
    latest_diff = None
    if latest_diff_row:
        latest_diff = json.loads(latest_diff_row[0] or "{}")
        latest_diff["taken_at"] = latest_diff_row[2]
        latest_diff["vs_snapshot_id"] = latest_diff_row[1]
    return {
        "wl_id": wid,
        "timeline": timeline,
        "diff_history": diff_history,
        "latest_diff": latest_diff,
        "snapshot_count": len(timeline),
    }


def rotate_old_snapshots(keep_days: int = 90) -> int:
    """Xoá snapshot cũ hơn N ngày (diff giữ vĩnh viễn). Trả số rows xoá."""
    init_history_db()
    cutoff = (datetime.now() - timedelta(days=keep_days)).isoformat()
    conn = keyword_bank.connect()
    try:
        cur = conn.execute(
            "DELETE FROM kw_bank_snapshot WHERE taken_at < ?", (cutoff,))
        n = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return n


if __name__ == "__main__":
    # CLI test
    import sys
    init_history_db()
    print(f"DB init OK at {keyword_bank.db_path()}")
    if len(sys.argv) > 1 and sys.argv[1] == "rotate":
        n = rotate_old_snapshots(90)
        print(f"Rotated {n} old snapshots")
