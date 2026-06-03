# -*- coding: utf-8 -*-
"""YouTube Data API v3 wrapper — fast bulk enrichment thay enrich HTML.

Pattern (file user dán 24/05 đêm):
  - search.list = 100 điểm/request (đắt, dùng tiết kiệm)
  - videos.list = 1 điểm/request, batch ≤50 ID → 500K video/ngày free
  - channels.list = 1 điểm/request, batch ≤50 ID → 500K channel/ngày
  - Quota mặc định: 10,000 điểm/ngày, reset 14:00 giờ VN (00:00 PST)

Khác V1 enrich_videos_with_tags (30 navigate /watch ~100s):
  - 1 API videos.list batch 30 ID = 0.5s (175× nhanh hơn)
  - Data ĐẦY ĐỦ + sạch hơn (comment_count V1 không cào được, API trả đủ)

Usage:
    from .youtube_api import videos_list, channels_list
    items = videos_list(["v2DP2_ak9mI", "ZN0jkJ1vUhQ", ...])
    info = channels_list(["UC574pFBByogKF5GIj4rAkTA"])
"""
from __future__ import annotations
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# ============================================================
# Quota tracker (in-memory, reset mỗi process)
# ============================================================
_QUOTA_LOCK = threading.Lock()
_QUOTA_STATE = {
    "used_today": 0,
    "last_reset": None,  # datetime — chỉ reset khi qua 00:00 PST
    "limit_daily": 10000,
}

# Cost mỗi method (theo doc YouTube Data API v3)
QUOTA_COST = {
    "videos.list": 1,
    "channels.list": 1,
    "search.list": 100,
    "playlistItems.list": 1,
    "commentThreads.list": 1,
}


def _maybe_reset_quota():
    """Reset counter nếu qua nửa đêm PST (= 14:00 giờ VN)."""
    now = datetime.now(timezone.utc)
    last = _QUOTA_STATE.get("last_reset")
    if last is None or (now.date() != last.date()
                        and now.hour >= 7):  # 7 UTC = 14h VN ≈ 00 PST
        _QUOTA_STATE["used_today"] = 0
        _QUOTA_STATE["last_reset"] = now


def _add_quota(method: str, n: int = 1):
    with _QUOTA_LOCK:
        _maybe_reset_quota()
        cost = QUOTA_COST.get(method, 1) * n
        _QUOTA_STATE["used_today"] += cost


def quota_used() -> int:
    """Số điểm quota đã dùng trong process này."""
    with _QUOTA_LOCK:
        _maybe_reset_quota()
        return _QUOTA_STATE["used_today"]


def quota_remaining() -> int:
    with _QUOTA_LOCK:
        return max(0,
                   _QUOTA_STATE["limit_daily"] - _QUOTA_STATE["used_today"])


# ============================================================
# Low-level HTTP wrapper
# ============================================================
def _get_api_key() -> str:
    """Lấy YouTube Data API v3 key từ config."""
    try:
        from .config import load_config
        return (load_config().get("youtube_data_api_key", "") or "").strip()
    except Exception:
        return ""


def _http_get(url: str, timeout: int = 15, retries: int = 2) -> dict:
    """HTTP GET với retry. Trả dict JSON hoặc raise."""
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            last_err = RuntimeError(
                f"HTTP {e.code} {e.reason}: {body[:200]}")
            # Quota exceeded / forbidden — KHÔNG retry
            if e.code in (403, 400):
                raise last_err
        except Exception as e:
            last_err = e
        if attempt < retries:
            time.sleep(1 + attempt)
    raise last_err or RuntimeError("HTTP fail unknown")


# ============================================================
# Key rotation — xoay tua YOUTUBE_API_KEY1/2/3 khi gặp quota/403
# ============================================================
_KEY_LOCK = threading.Lock()
_key_idx = 0


def _api_keys() -> list:
    """Danh sách key xoay tua (YOUTUBE_API_KEY1/2/3 từ .env)."""
    try:
        from .config import youtube_api_keys
        keys = youtube_api_keys()
        if keys:
            return keys
    except Exception:
        pass
    k = _get_api_key()
    return [k] if k else []


def _http_get_rotating(base_url: str, forced_key: str = "") -> dict:
    """GET base_url (đã có '?...', CHƯA có &key). Xoay tua các key: gặp
    403/429/quota → thử key kế; nhớ key vừa chạy được làm ưu tiên lần sau
    (sticky). Raise khi mọi key đều lỗi quota, hoặc lỗi khác (vd 400).
    """
    global _key_idx
    keys = [forced_key.strip()] if forced_key.strip() else _api_keys()
    if not keys:
        raise RuntimeError("Chưa có YOUTUBE_API_KEY1/2/3 trong .env")
    n = len(keys)
    with _KEY_LOCK:
        start = _key_idx % n
    last_err = None
    for off in range(n):
        ki = (start + off) % n
        try:
            data = _http_get(f"{base_url}&key={keys[ki]}")
            with _KEY_LOCK:
                _key_idx = ki  # key này OK → ưu tiên cho request sau
            return data
        except RuntimeError as e:
            msg = str(e).lower()
            quota_like = any(s in msg for s in
                             ("403", "429", "quota", "ratelimit", "dailylimit"))
            if quota_like and off < n - 1:
                last_err = e
                continue
            raise
    raise last_err or RuntimeError("Tất cả YOUTUBE_API_KEY đều lỗi quota")


# ============================================================
# videos.list — batch ≤50 ID
# ============================================================
def videos_list(
    ids: list,
    parts: tuple = ("snippet", "statistics", "contentDetails"),
    api_key: str = "",
) -> list:
    """Lấy chi tiết nhiều video. Tự batch 50 ID/request.

    Trả list dict raw từ API (item.id + item.snippet + item.statistics + ...).
    """
    if not ids:
        return []
    parts_str = ",".join(parts)
    items = []
    # Dedup + giữ thứ tự
    seen = set()
    uniq = []
    for vid in ids:
        if vid and vid not in seen:
            seen.add(vid)
            uniq.append(vid)
    for i in range(0, len(uniq), 50):
        batch = uniq[i:i + 50]
        base = (
            "https://www.googleapis.com/youtube/v3/videos"
            f"?part={parts_str}"
            f"&id={','.join(batch)}"
            f"&maxResults=50"
        )
        data = _http_get_rotating(base, forced_key=api_key)
        items.extend(data.get("items", []) or [])
        _add_quota("videos.list", 1)
    return items


# ============================================================
# channels.list — batch ≤50 ID
# ============================================================
def channels_list(
    ids: list,
    parts: tuple = ("snippet", "statistics", "brandingSettings",
                    "contentDetails"),
    api_key: str = "",
) -> list:
    """Lấy chi tiết nhiều kênh. Tự batch 50 ID/request."""
    if not ids:
        return []
    parts_str = ",".join(parts)
    items = []
    seen = set()
    uniq = []
    for cid in ids:
        if cid and cid not in seen:
            seen.add(cid)
            uniq.append(cid)
    for i in range(0, len(uniq), 50):
        batch = uniq[i:i + 50]
        base = (
            "https://www.googleapis.com/youtube/v3/channels"
            f"?part={parts_str}"
            f"&id={','.join(batch)}"
            f"&maxResults=50"
        )
        data = _http_get_rotating(base, forced_key=api_key)
        items.extend(data.get("items", []) or [])
        _add_quota("channels.list", 1)
    return items


# ============================================================
# Helpers parse ISO 8601 duration → seconds
# ============================================================
_ISO_DUR_RE = re.compile(
    r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def iso_duration_to_seconds(iso: str) -> int:
    """PT1H5M33S → 3933 (giây). PT0S → 0. PT7M5S → 425."""
    if not iso:
        return 0
    m = _ISO_DUR_RE.match(iso.strip())
    if not m:
        return 0
    h = int(m.group(1) or 0)
    mi = int(m.group(2) or 0)
    s = int(m.group(3) or 0)
    return h * 3600 + mi * 60 + s


def parse_iso8601_datetime(s: str):
    """'2024-01-15T10:30:00Z' → datetime aware UTC."""
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


# ============================================================
# Self-test (gọi nhanh để verify)
# ============================================================
def selftest() -> dict:
    """Test API key + connectivity. Trả {ok, message, quota_used}."""
    try:
        # Test với 1 video YouTube nổi tiếng (Rick Astley)
        items = videos_list(["dQw4w9WgXcQ"], parts=("snippet",))
        if not items:
            return {"ok": False, "message": "API trả rỗng"}
        title = items[0].get("snippet", {}).get("title", "?")
        return {
            "ok": True,
            "message": f"OK — fetched: {title[:50]}",
            "quota_used": quota_used(),
        }
    except Exception as e:
        return {"ok": False, "message": f"Lỗi: {e}"}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("=== YouTube Data API selftest ===")
    r = selftest()
    print(f"  ok: {r['ok']}")
    print(f"  message: {r['message']}")
    print(f"  quota used: {r.get('quota_used', 0)} điểm")
