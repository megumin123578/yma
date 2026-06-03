"""
Lưu/đọc lịch sử kết quả nghiên cứu.
Mỗi job được pickle thành 1 file + 1 entry trong index.json.
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


def history_dir() -> Path:
    """Thư mục lịch sử. Có thể override qua config 'shared_history_dir' để team
    nhiều người cùng dùng chung (shared folder mạng / OneDrive / Drive)."""
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
            # fallback nếu replace lỗi (file đang bị mở...)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass


def _merge_external_index(local_items: list) -> list:
    """Khi dùng shared folder: hợp nhất entries mới do user khác thêm vào.
    Cụ thể: đọc lại file ngay trước khi ghi để không ghi đè entries mới."""
    p = index_path()
    if not p.exists():
        return local_items
    try:
        with open(p, "r", encoding="utf-8") as f:
            disk = json.load(f)
    except Exception:
        return local_items
    # Index local thường đã có disk + 1 mới ở đầu. Nếu disk có entry không có trong local
    # → là entries của user khác → cần merge.
    local_ids = {e.get("id") for e in local_items}
    extras = [e for e in disk if e.get("id") not in local_ids]
    if extras:
        # Trộn vào, sort theo date desc
        merged = local_items + extras
        merged.sort(key=lambda e: e.get("date", ""), reverse=True)
        return merged
    return local_items


def save_result(result: dict) -> str:
    """Pickle result + thêm entry vào index. Trả về job_id."""
    # Phát hiện mode: nếu có channel object với channel_id thực sự (không phải fake) → channel
    has_real_channel = bool(
        result.get("channel") and getattr(result["channel"], "channel_id", "")
    )
    job_type = "channel" if has_real_channel else "keywords"
    if job_type == "channel":
        target = result["channel_title"]
    else:
        kws = result.get("input_keywords", [])
        target = "+".join(kws[:3]) if kws else "keywords"

    job_id = _make_id(target)
    pkl_path = history_dir() / f"{job_id}.pkl"

    with open(pkl_path, "wb") as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Đánh dấu để dò trùng khi chạy lại (delta tracking)
    channel_id = ""
    if has_real_channel:
        channel_id = result["channel"].channel_id or ""

    # Lấy user_name từ config (cho multi-user)
    user_name = ""
    try:
        from .config import load_config
        user_name = load_config().get("user_name", "").strip() or os.environ.get("USERNAME", "")
    except Exception:
        import os as _os
        user_name = _os.environ.get("USERNAME", "")

    entry = {
        "id": job_id,
        "date": datetime.now().isoformat(timespec="seconds"),
        "type": job_type,
        "target": target,
        "subscriber_count": result.get("subscriber_count", 0),
        "keyword_count": result.get("keyword_count", 0),
        "video_count": result.get("video_count", 0),
        "pkl_path": str(pkl_path),
        "xlsx_path": result.get("output_path", ""),
        "days": result.get("params", {}).get("days", 0),
        # Dùng cho delta tracking
        "channel_id": channel_id,
        "input_keywords": result.get("input_keywords", []) if not has_real_channel else [],
        # Multi-user
        "user_name": user_name,
    }

    items = _load_index()
    items.insert(0, entry)  # mới nhất ở đầu
    # Merge với disk để tránh ghi đè entries của user khác trong shared folder
    items = _merge_external_index(items)
    _save_index(items)
    return job_id


def find_previous_for_channel(channel_id: str, exclude_id: str = "") -> dict | None:
    """Tìm result trước đó cùng channel_id để so sánh delta. Trả None nếu chưa có."""
    if not channel_id:
        return None
    for e in _load_index():
        if e.get("type") != "channel":
            continue
        if e.get("channel_id") != channel_id:
            continue
        if exclude_id and e.get("id") == exclude_id:
            continue
        return load_result(e["id"])
    return None


def find_previous_for_keywords(keywords: list, exclude_id: str = "",
                                min_overlap: float = 0.6) -> dict | None:
    """Tìm result trước đó với danh sách từ khoá tương tự (≥ overlap %)."""
    if not keywords:
        return None
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
            return load_result(e["id"])
    return None


def list_history() -> list:
    """Trả về list entry, mới nhất ở đầu. Loại bỏ entries có file đã mất."""
    items = _load_index()
    valid = [e for e in items if Path(e.get("pkl_path", "")).exists()]
    if len(valid) != len(items):
        _save_index(valid)
    return valid


def load_result(job_id: str) -> Optional[dict]:
    """Load 1 result từ pickle. Trả None nếu không tìm thấy."""
    items = _load_index()
    for e in items:
        if e["id"] == job_id:
            try:
                with open(e["pkl_path"], "rb") as f:
                    return pickle.load(f)
            except Exception:
                return None
    return None


def delete_history(job_id: str) -> bool:
    """Xoá entry + file pickle. Không xoá Excel."""
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
    """Xoá toàn bộ lịch sử. Trả về số entries đã xoá."""
    items = _load_index()
    for e in items:
        try:
            Path(e["pkl_path"]).unlink(missing_ok=True)
        except Exception:
            pass
    _save_index([])
    return len(items)
