"""
Lưu/đọc lịch sử kết quả nghiên cứu (snapshot cào).

Backend: PostgreSQL (snapshot_store) nếu sẵn sàng, fallback file pkl + index.json.
Trong lúc chuyển (dual-read): ghi mới vào PG, đọc PG trước rồi mới tới pkl cũ.
Mọi nơi khác PHẢI dùng API ở đây (save_result/find_previous_for_channel/
records_for_channel/load_result/update_result*/list_history/delete_history)
— không đọc _load_index()/pkl_path trực tiếp.
"""

from __future__ import annotations

import json
import os
import pickle
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional


# Lock cho thao tác trên index.json để tránh race khi nhiều user ghi cùng lúc
# (nếu share folder qua mạng/OneDrive)
_INDEX_LOCK = threading.Lock()

# Giữ tối đa N snapshot/kênh để history không phình vô hạn (mỗi lần cào đẻ 1
# file/row). Override qua env RESEARCH_MAX_SNAPSHOTS_PER_CHANNEL.
MAX_SNAPSHOTS_PER_CHANNEL = max(
    2, int(os.getenv("RESEARCH_MAX_SNAPSHOTS_PER_CHANNEL", "5") or 5))


def history_dir() -> Path:
    """Thư mục lịch sử pkl. Override qua config 'shared_history_dir'."""
    try:
        from .config import load_config
        cfg = load_config()
        shared = cfg.get("shared_history_dir", "").strip()
        if shared:
            d = Path(shared)
            d.mkdir(parents=True, exist_ok=True)
            return d
    except Exception:
        pass
    d = Path.home() / ".youtube_research" / "history"
    d.mkdir(parents=True, exist_ok=True)
    return d


def index_path() -> Path:
    return history_dir() / "index.json"


def _safe(s: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", s or "")
    return s.strip("_")[:50] or "unknown"


def _make_id(target: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{_safe(target)}"


# ============================================================
# pkl index helpers (fallback backend)
# ============================================================

def _load_index() -> list:
    p = index_path()
    if not p.exists():
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_index(items: list) -> None:
    """Atomic write index.json (giảm rủi ro corrupt khi share folder)."""
    p = index_path()
    tmp = p.with_suffix(".json.tmp")
    with _INDEX_LOCK:
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            os.replace(str(tmp), str(p))
        except Exception:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass


def _merge_external_index(local_items: list) -> list:
    """Shared folder: hợp nhất entries mới do user khác thêm (đọc lại trước ghi)."""
    p = index_path()
    if not p.exists():
        return local_items
    try:
        with open(p, "r", encoding="utf-8") as f:
            disk = json.load(f)
    except Exception:
        return local_items
    local_ids = {e.get("id") for e in local_items}
    extras = [e for e in disk if e.get("id") not in local_ids]
    if extras:
        merged = local_items + extras
        merged.sort(key=lambda e: e.get("date", ""), reverse=True)
        return merged
    return local_items


def _prune_channel_snapshots(channel_id: str, user_name: str,
                             keep: int = MAX_SNAPSHOTS_PER_CHANNEL) -> int:
    """(pkl) Giữ `keep` snapshot mới nhất của 1 kênh — xoá pkl + entry cũ."""
    if not channel_id or keep <= 0:
        return 0
    items = _load_index()
    mine = [e for e in items
            if e.get("type") == "channel"
            and e.get("channel_id") == channel_id
            and (e.get("user_name") or "") == (user_name or "")]
    if len(mine) <= keep:
        return 0
    mine.sort(key=lambda e: e.get("date", ""), reverse=True)
    stale_ids = {e.get("id") for e in mine[keep:]}
    for e in mine[keep:]:
        try:
            Path(e.get("pkl_path", "")).unlink(missing_ok=True)
        except Exception:
            pass
    _save_index([e for e in items if e.get("id") not in stale_ids])
    return len(stale_ids)


def _rewrite_pkl(path, new_data=None, mutate_fn=None) -> bool:
    """Ghi đè pkl an toàn: khoá (serialize read-modify-write) + atomic
    (tmp + os.replace) → reader không bao giờ thấy file ghi dở."""
    if not path:
        return False
    try:
        from .pkl_io import _LOCK
    except Exception:
        _LOCK = _INDEX_LOCK
    with _LOCK:
        try:
            if mutate_fn is not None:
                with open(path, "rb") as f:
                    data = pickle.load(f)
                mutate_fn(data)
            else:
                data = new_data
            tmp = str(path) + ".tmp"
            with open(tmp, "wb") as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp, str(path))
            return True
        except Exception:
            return False


# ============================================================
# Backend selector
# ============================================================
_SNAP_TRIED = False
_SNAP = None


def _pg():
    """Trả module snapshot_store nếu PG sẵn sàng, else None (→ fallback pkl)."""
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
    """Trích metadata (cột index) từ result. Dùng chung PG + pkl."""
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
    """Lưu snapshot (PG nếu sẵn sàng, else pkl). Trả về job_id."""
    meta = _compute_meta(result)
    pg = _pg()
    if pg is not None:
        try:
            pg.save(meta, result)
            if meta["type"] == "channel" and meta["channel_id"]:
                try:
                    pg.prune_channel(meta["channel_id"], meta["user_name"],
                                     MAX_SNAPSHOTS_PER_CHANNEL)
                except Exception:
                    pass
            return meta["id"]
        except Exception:
            pass  # PG lỗi giữa chừng → fallback pkl
    _save_result_pkl(meta, result)
    return meta["id"]


def _save_result_pkl(meta: dict, result: dict) -> None:
    pkl_path = history_dir() / f"{meta['id']}.pkl"
    _rewrite_pkl(pkl_path, new_data=result)  # atomic
    entry = dict(meta)
    entry["pkl_path"] = str(pkl_path)
    items = _load_index()
    items.insert(0, entry)
    items = _merge_external_index(items)
    _save_index(items)
    if meta["type"] == "channel" and meta["channel_id"]:
        try:
            _prune_channel_snapshots(meta["channel_id"], meta["user_name"])
        except Exception:
            pass


def records_for_channel(channel_id: str) -> list:
    """Meta snapshot 'channel' của 1 kênh, mới nhất trước (PG + pkl gộp)."""
    if not channel_id:
        return []
    pg = _pg()
    pg_recs = pg.records_for_channel(channel_id) if pg is not None else []
    seen = {r.get("id") for r in pg_recs}
    merged = pg_recs + [r for r in _pkl_records_for_channel(channel_id)
                        if r.get("id") not in seen]
    merged.sort(key=lambda e: e.get("id", ""), reverse=True)
    return merged


def _pkl_records_for_channel(channel_id: str) -> list:
    return sorted(
        [e for e in _load_index()
         if e.get("channel_id") == channel_id and e.get("type") == "channel"],
        key=lambda e: e.get("id", ""), reverse=True)


def load_result(job_id: str) -> Optional[dict]:
    """Load 1 snapshot (PG trước, pkl sau). None nếu không tìm thấy."""
    pg = _pg()
    if pg is not None:
        r = pg.load(job_id)
        if r is not None:
            return r
    return _pkl_load_result(job_id)


def _pkl_load_result(job_id: str) -> Optional[dict]:
    for e in _load_index():
        if e.get("id") == job_id:
            try:
                with open(e["pkl_path"], "rb") as f:
                    return pickle.load(f)
            except Exception:
                return None
    return None


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
    if pg is not None:
        r = pg.find_for_keywords(keywords, exclude_id, min_overlap)
        if r is not None:
            return r
    return _pkl_find_previous_for_keywords(keywords, exclude_id, min_overlap)


def _pkl_find_previous_for_keywords(keywords, exclude_id="",
                                    min_overlap=0.6) -> Optional[dict]:
    kw_set = {k.lower().strip() for k in keywords if k}
    if not kw_set:
        return None
    for e in _load_index():
        if e.get("type") != "keywords":
            continue
        if exclude_id and e.get("id") == exclude_id:
            continue
        prev_kws = {k.lower().strip() for k in e.get("input_keywords", []) if k}
        if not prev_kws:
            continue
        overlap = len(kw_set & prev_kws) / max(len(kw_set), len(prev_kws))
        if overlap >= min_overlap:
            return _pkl_load_result(e["id"])
    return None


def list_history() -> list:
    """List entry, mới nhất ở đầu (PG + pkl gộp, dedup theo id)."""
    pg = _pg()
    pg_items = pg.list_all() if pg is not None else []
    seen = {e.get("id") for e in pg_items}
    merged = pg_items + [e for e in _pkl_list_history()
                         if e.get("id") not in seen]
    merged.sort(key=lambda e: e.get("id", ""), reverse=True)
    return merged


def _pkl_list_history() -> list:
    items = _load_index()
    valid = [e for e in items if Path(e.get("pkl_path", "")).exists()]
    if len(valid) != len(items):
        _save_index(valid)
    return valid


def mutate_result(job_id: str, mutate_fn) -> bool:
    """Read-modify-write 1 snapshot. mutate_fn(data) sửa dict tại chỗ."""
    if not job_id:
        return False
    pg = _pg()
    if pg is not None:
        r = pg.load(job_id)
        if r is not None:
            try:
                mutate_fn(r)
            except Exception:
                return False
            return pg.update(job_id, r)
    return _pkl_mutate_result(job_id, mutate_fn)


def update_result(job_id: str, result: dict) -> bool:
    """Ghi đè toàn bộ payload 1 snapshot đã tồn tại."""
    if not job_id:
        return False
    pg = _pg()
    if pg is not None and pg.update(job_id, result):
        return True
    return _pkl_update_result(job_id, result)


def update_result_field(job_id: str, field: str, value) -> bool:
    """Sửa 1 field trong snapshot (in-place mutate SB/AI an toàn khi parallel)."""
    return mutate_result(job_id, lambda d: d.__setitem__(field, value))


def _pkl_mutate_result(job_id, mutate_fn) -> bool:
    for e in _load_index():
        if e.get("id") == job_id:
            return _rewrite_pkl(e.get("pkl_path", ""), mutate_fn=mutate_fn)
    return False


def _pkl_update_result(job_id, result) -> bool:
    for e in _load_index():
        if e.get("id") == job_id:
            return _rewrite_pkl(e.get("pkl_path", ""), new_data=result)
    return False


def delete_history(job_id: str) -> bool:
    """Xoá 1 snapshot (PG + pkl). Không xoá Excel."""
    pg = _pg()
    ok_pg = pg.delete(job_id) if pg is not None else False
    return _pkl_delete_history(job_id) or ok_pg


def _pkl_delete_history(job_id: str) -> bool:
    items = _load_index()
    new_items = []
    deleted = False
    for e in items:
        if e["id"] == job_id:
            try:
                Path(e["pkl_path"]).unlink(missing_ok=True)
            except Exception:
                pass
            deleted = True
        else:
            new_items.append(e)
    if deleted:
        _save_index(new_items)
    return deleted


def clear_history() -> int:
    """Xoá toàn bộ lịch sử (PG + pkl). Trả số entries đã xoá."""
    pg = _pg()
    n_pg = 0
    if pg is not None:
        try:
            n_pg = pg.clear()
        except Exception:
            n_pg = 0
    return n_pg + _pkl_clear_history()


def _pkl_clear_history() -> int:
    items = _load_index()
    for e in items:
        try:
            Path(e["pkl_path"]).unlink(missing_ok=True)
        except Exception:
            pass
    _save_index([])
    return len(items)
