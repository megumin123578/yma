"""
In-memory cache cho search/result_count/autosuggest TRONG MỘT QUEUE RUN.
Reset trước mỗi queue → tránh dữ liệu cũ.

Mục đích: khi chạy nhiều kênh cùng lúc (queue), nếu nhiều kênh chia sẻ
từ khoá giống nhau (cùng ngách) → reuse kết quả → tiết kiệm thời gian.

Cache scope: per-queue (in-memory, không persist). Đảm bảo data fresh
cho mỗi lần chạy queue mới.
"""

from __future__ import annotations

from typing import Optional


# Module-level state
_search_cache: dict = {}       # (kw_lower, days_or_'top', region) → list[VideoInfo]
_result_count_cache: dict = {}  # kw_lower → int
_autosuggest_cache: dict = {}   # kw_lower → list[str]
_stats: dict = {"search_hits": 0, "search_misses": 0,
                "rc_hits": 0, "rc_misses": 0,
                "sug_hits": 0, "sug_misses": 0}


def clear() -> None:
    """Xoá toàn bộ cache. Gọi trước mỗi queue run."""
    _search_cache.clear()
    _result_count_cache.clear()
    _autosuggest_cache.clear()
    for k in _stats:
        _stats[k] = 0


def stats() -> dict:
    """Trả về số liệu hit/miss."""
    return dict(_stats)


def summary_str() -> str:
    """Mô tả ngắn để log."""
    sh, sm = _stats["search_hits"], _stats["search_misses"]
    rh, rm = _stats["rc_hits"], _stats["rc_misses"]
    ah, am = _stats["sug_hits"], _stats["sug_misses"]
    if sh + sm == 0:
        return "(cache chưa dùng)"
    return (f"search {sh}/{sh+sm} ({100*sh/(sh+sm):.0f}%) hit, "
            f"competition {rh}/{rh+rm}, autosuggest {ah}/{ah+am}")


# -------------------- Search cache --------------------

def _search_key(keyword: str, days: Optional[int], region: Optional[str]):
    return (
        (keyword or "").lower().strip(),
        days if days else "top",
        region or "",
    )


def get_search(keyword: str, days: Optional[int],
               region: Optional[str] = None) -> Optional[list]:
    key = _search_key(keyword, days, region)
    val = _search_cache.get(key)
    if val is not None:
        _stats["search_hits"] += 1
        return val
    _stats["search_misses"] += 1
    return None


def set_search(keyword: str, days: Optional[int],
               region: Optional[str], videos: list) -> None:
    if videos is None:
        return
    key = _search_key(keyword, days, region)
    _search_cache[key] = videos


# -------------------- Result count cache --------------------

def get_result_count(keyword: str) -> Optional[int]:
    val = _result_count_cache.get((keyword or "").lower().strip())
    if val is not None:
        _stats["rc_hits"] += 1
        return val
    _stats["rc_misses"] += 1
    return None


def set_result_count(keyword: str, count: int) -> None:
    _result_count_cache[(keyword or "").lower().strip()] = count


# -------------------- Autosuggest cache --------------------

def get_autosuggest(keyword: str) -> Optional[list]:
    val = _autosuggest_cache.get((keyword or "").lower().strip())
    if val is not None:
        _stats["sug_hits"] += 1
        return val
    _stats["sug_misses"] += 1
    return None


def set_autosuggest(keyword: str, sugs: list) -> None:
    _autosuggest_cache[(keyword or "").lower().strip()] = sugs


# -------------------- Pre-populate from existing results --------------------

def warm_from_results(results: list) -> int:
    """Nạp cache từ list các result đã có (vd: từ history).
    Trả số entries đã nạp."""
    count = 0
    for r in results or []:
        if not r:
            continue
        params = r.get("params") or {}
        days = params.get("days") or 0
        region = params.get("region") or ""

        for kw, vids in (r.get("top_by_keyword") or {}).items():
            if vids:
                set_search(kw, None, region, vids)
                count += 1
        for kw, vids in (r.get("recent_by_keyword") or {}).items():
            if vids:
                set_search(kw, int(days) if days else None, region, vids)
                count += 1

        tm = r.get("tag_metrics") or {}
        for kw, m in (tm.get("per_keyword") or {}).items():
            comp = m.get("competition") or {}
            if "result_count" in comp:
                set_result_count(kw, comp["result_count"])
                count += 1
            sugs = m.get("autosuggest") or []
            if sugs:
                set_autosuggest(kw, sugs)
                count += 1
    return count
