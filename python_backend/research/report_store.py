"""
Report Store - sổ ghi các báo cáo PDF đã tạo, để xem lại trong phần mềm.

Lưu 1 file index JSON ở ~/.youtube_research/pdf_reports.json. File PDF
thật vẫn nằm trong thư mục ket_qua/bao_cao_pdf/. Module này chỉ ghi nhớ
đường dẫn + thông tin để liệt kê lại.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

_LOCK = threading.Lock()
_MAX = 100   # giữ tối đa 100 báo cáo gần nhất trong sổ


def _store_path() -> Path:
    d = Path.home() / ".youtube_research"
    d.mkdir(parents=True, exist_ok=True)
    return d / "pdf_reports.json"


def _load() -> list:
    p = _store_path()
    if not p.exists():
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(items: list) -> None:
    p = _store_path()
    tmp = p.with_suffix(".json.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        os.replace(str(tmp), str(p))
    except Exception:
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def add_report(watchlist_id: str, watchlist_name: str, report_type: str,
               path: str, sent_telegram: bool = False,
               name: str = "") -> str:
    """Ghi 1 báo cáo vào sổ. Trả về id của bản ghi.
    name: tên đầy đủ của báo cáo ('<tên kênh> — <ý nghĩa>')."""
    with _LOCK:
        items = _load()
        rid = "rpt_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        try:
            size = os.path.getsize(path)
        except Exception:
            size = 0
        items.insert(0, {
            "id": rid,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "watchlist_id": watchlist_id or "",
            "watchlist_name": watchlist_name or "",
            "report_type": report_type or "",
            "name": name or "",
            "path": str(path),
            "size": size,
            "sent_telegram": bool(sent_telegram),
        })
        if len(items) > _MAX:
            items = items[:_MAX]
        _save(items)
        return rid


def mark_sent(report_id: str) -> None:
    """Đánh dấu 1 báo cáo đã gửi Telegram thành công."""
    with _LOCK:
        items = _load()
        for it in items:
            if it.get("id") == report_id:
                it["sent_telegram"] = True
                break
        _save(items)


def list_reports(existing_only: bool = True) -> list:
    """List báo cáo, mới nhất ở đầu.
    existing_only=True: bỏ qua bản ghi có file PDF đã bị xoá."""
    items = _load()
    if existing_only:
        valid = [it for it in items
                 if it.get("path") and Path(it["path"]).exists()]
        if len(valid) != len(items):
            with _LOCK:
                _save(valid)
        return valid
    return items


def get_report(report_id: str) -> dict | None:
    """Lấy 1 bản ghi báo cáo theo id."""
    for it in _load():
        if it.get("id") == report_id:
            return it
    return None


def delete_report(report_id: str, delete_file: bool = False) -> bool:
    """Xoá 1 báo cáo khỏi sổ. delete_file=True thì xoá luôn file PDF."""
    with _LOCK:
        items = _load()
        kept = []
        removed = None
        for it in items:
            if it.get("id") == report_id:
                removed = it
            else:
                kept.append(it)
        if removed is None:
            return False
        if delete_file:
            try:
                Path(removed.get("path", "")).unlink(missing_ok=True)
            except Exception:
                pass
        _save(kept)
        return True
