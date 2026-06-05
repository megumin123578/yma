# -*- coding: utf-8 -*-
"""Báo cáo SEO do Claude CLI viết cho người mới — lưu lịch sử theo ngày.

Mỗi watchlist có 1 file JSON chứa list bản ghi (mới nhất ở đầu):
  {id, date, generated_at, model, content}
Trang Seo dùng dropdown date để xem báo cáo theo từng thời điểm sinh.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

_MAX_HISTORY = 60


def _dir() -> Path:
    d = Path.home() / ".youtube_research" / "seo_reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(wid: str) -> Path:
    return _dir() / f"{wid}.json"


def _read(wid: str) -> list:
    p = _path(wid)
    if not p.exists():
        return []
    try:
        items = json.loads(p.read_text(encoding="utf-8"))
        return items if isinstance(items, list) else []
    except Exception:
        return []


def list_reports(wid: str) -> list:
    """Metadata các báo cáo (không kèm content) — mới nhất trước."""
    return [{k: it.get(k) for k in ("id", "date", "generated_at", "model")}
            for it in _read(wid)]


def get_report(wid: str, report_id: str = "") -> Optional[dict]:
    """Báo cáo đầy đủ (kèm content). report_id rỗng → bản mới nhất."""
    items = _read(wid)
    if not items:
        return None
    if not report_id:
        return items[0]
    for it in items:
        if it.get("id") == report_id:
            return it
    return None


def save_report(wid: str, content: str, model: str = "") -> dict:
    items = _read(wid)
    now = datetime.now()
    entry = {
        "id": "seo_" + now.strftime("%Y%m%d_%H%M%S"),
        "date": now.strftime("%Y-%m-%d %H:%M"),
        "generated_at": now.isoformat(timespec="seconds"),
        "model": model,
        "content": content,
    }
    items.insert(0, entry)
    _path(wid).write_text(
        json.dumps(items[:_MAX_HISTORY], ensure_ascii=False, indent=2),
        encoding="utf-8")
    return entry


def generate(wid: str, log_fn=None) -> Optional[dict]:
    """Sinh báo cáo SEO mới bằng Claude CLI rồi lưu. Trả entry hoặc None.

    Cần claude.exe (gói subscription). Thiếu → trả None, không raise.
    """
    from . import watchlist as wl_mod, ai_insights

    def _log(m):
        if log_fn:
            try:
                log_fn(m)
            except Exception:
                pass

    if not ai_insights.cli_available():
        _log("Báo cáo SEO: không tìm thấy claude.exe — bỏ qua.")
        return None
    wl = wl_mod.load_watchlist(wid)
    if not wl:
        return None
    channels_data = ai_insights.collect_watchlist_data(wl)
    text = ai_insights.analyze_seo_report(wl, channels_data)
    if not text or not text.strip():
        _log("Báo cáo SEO: AI trả về rỗng.")
        return None
    entry = save_report(wid, text.strip(), model=ai_insights._cli_config()[2])
    _log("Báo cáo SEO: đã sinh.")
    return entry
