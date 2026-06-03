"""
Cache kết quả AI Compare để tái sử dụng - không phải gọi lại API nếu đã có.
Khoá theo tập hợp source_ids (sorted) → analysis text.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


def cache_path() -> Path:
    d = Path.home() / ".youtube_research"
    d.mkdir(parents=True, exist_ok=True)
    return d / "compare_cache.json"


def _key(source_ids: list) -> str:
    return "|".join(sorted(source_ids))


def _load() -> dict:
    p = cache_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    p = cache_path()
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                 encoding="utf-8")


def get_cached(source_ids: list) -> Optional[str]:
    """Trả về analysis text nếu đã cache, hoặc None."""
    if not source_ids:
        return None
    data = _load()
    entry = data.get(_key(source_ids))
    if entry:
        return entry.get("analysis")
    return None


def save_cache(source_ids: list, analysis: str, model: str = "") -> None:
    if not source_ids or not analysis:
        return
    data = _load()
    data[_key(source_ids)] = {
        "source_ids": sorted(source_ids),
        "analysis": analysis,
        "model": model,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    _save(data)


def list_cached() -> list:
    """Trả về list các entry đã cache."""
    return list(_load().values())


def clear_cache() -> int:
    data = _load()
    n = len(data)
    _save({})
    return n
