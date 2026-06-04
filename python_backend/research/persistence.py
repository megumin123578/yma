"""
Lưu/đọc lịch sử kết quả nghiên cứu (snapshot cào) — backend PostgreSQL.

Mọi nơi khác PHẢI dùng API ở đây (save_result/find_previous_for_channel/
records_for_channel/load_result/update_result*/list_history/delete_history).
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Optional


# Giữ tối đa N snapshot/kênh để history không phình vô hạn. Override qua env
# RESEARCH_MAX_SNAPSHOTS_PER_CHANNEL.
MAX_SNAPSHOTS_PER_CHANNEL = max(
    2, int(os.getenv("RESEARCH_MAX_SNAPSHOTS_PER_CHANNEL", "5") or 5))


def _safe(s: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", s or "")
    return s.strip("_")[:50] or "unknown"


def _make_id(target: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{_safe(target)}"


# ============================================================
# Backend (PostgreSQL)
# ============================================================
_SNAP_TRIED = False
_SNAP = None


def _pg():
    """Trả module snapshot_store nếu PG sẵn sàng, else None."""
    global _SNAP_TRIED, _SNAP
    if not _SNAP_TRIED:
        _SNAP_TRIED = True
        try:
            from . import snapshot_store
            _SNAP = snapshot_store
        except Exception:
            _SNAP = None
    if _SNAP is None:
        return None
    try:
        return _SNAP if _SNAP.available() else None
    except Exception:
        return None


def _compute_meta(result: dict) -> dict:
    """Trích metadata (cột index) từ result."""
    has_real_channel = bool(
        result.get("channel") and getattr(result["channel"], "channel_id", ""))
    job_type = "channel" if has_real_channel else "keywords"
    if job_type == "channel":
        target = result.get("channel_title", "") or ""
    else:
        kws = result.get("input_keywords", [])
        target = "+".join(kws[:3]) if kws else "keywords"
    channel_id = ""
    if has_real_channel:
        channel_id = result["channel"].channel_id or ""
    try:
        from .config import load_config
        user_name = (load_config().get("user_name", "").strip()
                     or os.environ.get("USERNAME", ""))
    except Exception:
        user_name = os.environ.get("USERNAME", "")
    return {
        "id": _make_id(target),
        "date": datetime.now().isoformat(timespec="seconds"),
        "type": job_type,
        "target": target,
        "channel_title": result.get("channel_title", "") or "",
        "subscriber_count": result.get("subscriber_count", 0),
        "keyword_count": result.get("keyword_count", 0),
        "video_count": result.get("video_count", 0),
        "xlsx_path": result.get("output_path", ""),
        "days": (result.get("params") or {}).get("days", 0),
        "channel_id": channel_id,
        "input_keywords": (result.get("input_keywords", [])
                           if not has_real_channel else []),
        "user_name": user_name,
    }


# ============================================================
# Public API
# ============================================================

def save_result(result: dict) -> str:
    """Lưu snapshot vào PG. Trả job_id. Raise nếu PG không sẵn sàng."""
    meta = _compute_meta(result)
    pg = _pg()
    if pg is None:
        raise RuntimeError("snapshot_store (PG) khong san sang — khong luu duoc")
    pg.save(meta, result)
    if meta["type"] == "channel" and meta["channel_id"]:
        try:
            pg.prune_channel(meta["channel_id"], meta["user_name"],
                             MAX_SNAPSHOTS_PER_CHANNEL)
        except Exception:
            pass
    return meta["id"]


def records_for_channel(channel_id: str) -> list:
    """Meta snapshot 'channel' của 1 kênh, mới nhất trước."""
    if not channel_id:
        return []
    pg = _pg()
    return pg.records_for_channel(channel_id) if pg is not None else []


def load_result(job_id: str) -> Optional[dict]:
    """Load 1 snapshot. None nếu không tìm thấy."""
    pg = _pg()
    return pg.load(job_id) if pg is not None else None


def find_previous_for_channel(channel_id: str,
                              exclude_id: str = "") -> Optional[dict]:
    """Result snapshot trước đó của 1 kênh (để so delta). None nếu chưa có."""
    if not channel_id:
        return None
    for e in records_for_channel(channel_id):
        if exclude_id and e.get("id") == exclude_id:
            continue
        return load_result(e["id"])
    return None


def find_previous_for_keywords(keywords: list, exclude_id: str = "",
                               min_overlap: float = 0.6) -> Optional[dict]:
    """Result trước với danh sách từ khoá tương tự (≥ overlap %)."""
    if not keywords:
        return None
    pg = _pg()
    return (pg.find_for_keywords(keywords, exclude_id, min_overlap)
            if pg is not None else None)


def list_history() -> list:
    """List entry, mới nhất ở đầu."""
    pg = _pg()
    return pg.list_all() if pg is not None else []


def mutate_result(job_id: str, mutate_fn) -> bool:
    """Read-modify-write 1 snapshot. mutate_fn(data) sửa dict tại chỗ."""
    if not job_id:
        return False
    pg = _pg()
    if pg is None:
        return False
    r = pg.load(job_id)
    if r is None:
        return False
    try:
        mutate_fn(r)
    except Exception:
        return False
    return pg.update(job_id, r)


def update_result(job_id: str, result: dict) -> bool:
    """Ghi đè toàn bộ payload 1 snapshot đã tồn tại."""
    if not job_id:
        return False
    pg = _pg()
    return bool(pg.update(job_id, result)) if pg is not None else False


def update_result_field(job_id: str, field: str, value) -> bool:
    """Sửa 1 field trong snapshot (in-place mutate SB/AI an toàn khi parallel)."""
    return mutate_result(job_id, lambda d: d.__setitem__(field, value))


def delete_history(job_id: str) -> bool:
    """Xoá 1 snapshot. Không xoá Excel."""
    pg = _pg()
    return bool(pg.delete(job_id)) if pg is not None else False


def clear_history() -> int:
    """Xoá toàn bộ lịch sử. Trả số entries đã xoá."""
    pg = _pg()
    if pg is None:
        return 0
    try:
        return pg.clear()
    except Exception:
        return 0
