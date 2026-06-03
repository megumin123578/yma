"""
Google Trends integration - miễn phí qua pytrends.
Trả về trend score 0-100 + history 12 tháng cho mỗi từ khoá.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional


# Cache để giảm rate limit
_CACHE_DIR = Path.home() / ".youtube_research" / "trends_cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_CACHE_TTL_HOURS = 24  # cache 1 ngày


def _cache_path(keyword: str) -> Path:
    import hashlib
    h = hashlib.md5(keyword.encode("utf-8")).hexdigest()[:16]
    return _CACHE_DIR / f"{h}.json"


def _load_cache(keyword: str) -> Optional[dict]:
    p = _cache_path(keyword)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        age_h = (time.time() - data.get("ts", 0)) / 3600
        if age_h > _CACHE_TTL_HOURS:
            return None
        return data
    except Exception:
        return None


def _save_cache(keyword: str, data: dict) -> None:
    p = _cache_path(keyword)
    try:
        out = dict(data)
        out["ts"] = time.time()
        out["keyword"] = keyword
        p.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _direction_from_history(history: list) -> str:
    """Phát hiện rising/stable/declining từ list điểm theo thời gian."""
    if not history or len(history) < 4:
        return "unknown"
    # Tính trung bình 1/3 đầu vs 1/3 cuối
    third = len(history) // 3
    first = sum(history[:third]) / max(third, 1)
    last = sum(history[-third:]) / max(third, 1)
    if last > first * 1.2:
        return "rising"
    if last < first * 0.8:
        return "declining"
    return "stable"


def _sparkline(history: list) -> str:
    """Convert list số (0-100) thành chuỗi sparkline (▁▂▃▄▅▆▇█)."""
    if not history:
        return ""
    bars = "▁▂▃▄▅▆▇█"
    max_v = max(history) or 1
    out = []
    for v in history:
        idx = int((v / max_v) * (len(bars) - 1))
        out.append(bars[max(0, min(idx, len(bars) - 1))])
    return "".join(out)


def get_trend(keyword: str, timeframe: str = "today 12-m") -> dict:
    """Lấy trend cho 1 từ khoá. Trả dict {score, history, direction, sparkline, error}.

    Có cache 24h để không gọi lại nhiều lần.
    """
    if not keyword:
        return {"score": 0, "history": [], "direction": "unknown",
                "sparkline": "", "error": "empty keyword"}

    cached = _load_cache(keyword)
    if cached:
        return cached

    try:
        from pytrends.request import TrendReq
    except ImportError:
        return {"score": 0, "history": [], "direction": "unknown",
                "sparkline": "", "error": "pytrends chưa cài"}

    # Wrap toàn bộ call pytrends trong ThreadPoolExecutor với hard timeout
    # để không bị stuck vô hạn khi Google Trends throttle nặng.
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as _TOE

    def _do_fetch():
        # retries=0 để pytrends không tự retry với backoff dài; timeout
        # ngắn (5s connect / 10s read) để fail nhanh.
        pytrends = TrendReq(hl="en-US", tz=420, timeout=(5, 10), retries=0)
        pytrends.build_payload([keyword], timeframe=timeframe)
        df = pytrends.interest_over_time()
        if df is None or df.empty or keyword not in df.columns:
            return {"score": 0, "history": [], "direction": "unknown",
                    "sparkline": "", "error": "no data"}
        history = [int(v) for v in df[keyword].tolist()]
        recent = history[-13:] if len(history) > 13 else history
        score = int(sum(recent) / len(recent)) if recent else 0
        direction = _direction_from_history(history)
        spark = _sparkline(history)
        return {"score": score, "history": history,
                "direction": direction, "sparkline": spark, "error": ""}

    HARD_TIMEOUT = 20  # giây - dừng chắc chắn không stuck quá lâu
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_do_fetch)
            try:
                result = future.result(timeout=HARD_TIMEOUT)
            except _TOE:
                result = {"score": 0, "history": [], "direction": "unknown",
                          "sparkline": "",
                          "error": f"hard timeout {HARD_TIMEOUT}s"}
        # Cache cả thành công lẫn no-data (KHÔNG cache lỗi mạng/timeout)
        if not result.get("error") or result.get("error") == "no data":
            _save_cache(keyword, result)
        return result
    except Exception as e:
        msg = str(e)[:100]
        return {"score": 0, "history": [], "direction": "unknown",
                "sparkline": "", "error": msg}


def get_trends_batch(keywords: list, delay_sec: float = 1.0,
                     log_fn=lambda *_: None) -> dict:
    """Lấy trend cho nhiều keywords. Delay giữa các call để tránh rate limit.
    Trả dict {keyword: trend_data}."""
    out = {}
    for i, kw in enumerate(keywords):
        log_fn(f"    Trends {i+1}/{len(keywords)}: {kw}")
        out[kw] = get_trend(kw)
        if i < len(keywords) - 1:
            time.sleep(delay_sec)
    return out
