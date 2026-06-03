# -*- coding: utf-8 -*-
"""CÔNG ĐOẠN 1: Lấy ID (channel_id, video_id) — không tốn API quota.

Pattern (file user dán 24/05 đêm): cào HTML nhẹ để gom ID, sau đó chuyển
sang CÔNG ĐOẠN 2 (data_enricher.py) gọi API videos.list/channels.list
batch 50 ID/request (1 điểm quota/request, 500K video/ngày).

Cách lấy ID:
  - Channel /videos page → parse ytInitialData → list videoId 30+ video
  - Search /results?search_query → parse ytInitialData → list videoId
  - Channel URL/handle → resolve channel_id qua channel page

Tốc độ: 1 navigate Playwright/page ≈ 3-5s. So với V1 enrich 30 /watch
~100s, đây là 20× nhẹ hơn cho mỗi channel.

KHÔNG cần tags/views/likes ở đây — chỉ cần ID. Data full lấy ở enricher.
"""
from __future__ import annotations
import re
from typing import Optional


# ============================================================
# Parse video ID từ ytInitialData (cho /videos hoặc /results page)
# ============================================================
def extract_video_ids_from_data(data: dict, limit: int = 50) -> list:
    """Walk ytInitialData JSON tree, trả list videoId (giữ thứ tự).

    YouTube có nhiều layout: videoRenderer, gridVideoRenderer,
    lockupViewModel (channel /videos page 2024+). Walk hết.
    """
    if not data or not isinstance(data, dict):
        return []
    seen = set()
    out = []

    def walk(node):
        if len(out) >= limit:
            return
        if isinstance(node, dict):
            # Video ID có thể nằm ở:
            # - videoRenderer.videoId
            # - gridVideoRenderer.videoId
            # - lockupViewModel.contentId (channel /videos 2024+)
            # - thumbnailViewModel + có thumbnail.url chứa /vi/<id>/
            vid = (node.get("videoId") or
                   (node.get("contentId") if node.get("contentType") ==
                    "LOCKUP_CONTENT_TYPE_VIDEO" else None))
            if vid and isinstance(vid, str) and len(vid) == 11:
                if vid not in seen:
                    seen.add(vid)
                    out.append(vid)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return out[:limit]


# ============================================================
# Lấy video ID từ kênh /videos page
# ============================================================
def collect_video_ids_from_channel(channel_url: str, limit: int = 30,
                                    log_fn=print) -> list:
    """Navigate channel/videos, scroll, parse ytInitialData → list video_id.

    Dùng Playwright sync nhẹ — chỉ 1 page navigate, không enrich.
    Trả list[str] tối đa `limit` ID, sắp theo thứ tự xuất hiện (mới → cũ).
    """
    from playwright.sync_api import sync_playwright
    url = channel_url.rstrip("/") + "/videos"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
                                     args=["--disable-blink-features="
                                           "AutomationControlled"])
        try:
            ctx = browser.new_context()
            # Pre-set consent cookies
            ctx.add_cookies([
                {"name": "SOCS", "value": "CAI",
                 "domain": ".youtube.com", "path": "/"},
                {"name": "CONSENT", "value": "YES+cb",
                 "domain": ".youtube.com", "path": "/"},
            ])
            page = ctx.new_page()
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            # Scroll để load thêm video (limit / 25 ≈ số scroll)
            scrolls = max(1, (limit + 24) // 25)
            for _ in range(min(scrolls, 5)):
                page.evaluate("window.scrollBy(0, 3000)")
                page.wait_for_timeout(800)
            data = page.evaluate(
                "() => window.ytInitialData || null")
            ids = extract_video_ids_from_data(data, limit=limit) if data else []
            page.close()
            ctx.close()
            return ids
        finally:
            try:
                browser.close()
            except Exception:
                pass


# ============================================================
# Lấy video ID từ search results
# ============================================================
def collect_video_ids_from_search(query: str, limit: int = 30,
                                   log_fn=print) -> list:
    """Cào /results?search_query=... → list videoId top results."""
    from playwright.sync_api import sync_playwright
    import urllib.parse
    q = urllib.parse.quote(query)
    url = f"https://www.youtube.com/results?search_query={q}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
                                     args=["--disable-blink-features="
                                           "AutomationControlled"])
        try:
            ctx = browser.new_context()
            ctx.add_cookies([
                {"name": "SOCS", "value": "CAI",
                 "domain": ".youtube.com", "path": "/"},
                {"name": "CONSENT", "value": "YES+cb",
                 "domain": ".youtube.com", "path": "/"},
            ])
            page = ctx.new_page()
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            scrolls = max(1, (limit + 24) // 25)
            for _ in range(min(scrolls, 3)):
                page.evaluate("window.scrollBy(0, 3000)")
                page.wait_for_timeout(800)
            data = page.evaluate(
                "() => window.ytInitialData || null")
            ids = extract_video_ids_from_data(data, limit=limit) if data else []
            page.close()
            ctx.close()
            return ids
        finally:
            try:
                browser.close()
            except Exception:
                pass


# ============================================================
# Resolve channel URL → channel_id
# ============================================================
_UC_RE = re.compile(r"UC[A-Za-z0-9_-]{22}")


def extract_channel_id_from_url(url: str) -> Optional[str]:
    """Parse /channel/UCxxx... từ URL nếu có, không gọi network."""
    m = _UC_RE.search(url or "")
    return m.group(0) if m else None


def resolve_channel_id(url_or_handle: str, log_fn=print) -> Optional[str]:
    """Trả channel_id (UCxxx). Nếu URL đã có UC → return. Nếu @handle
    hoặc /c/name → navigate page, parse externalId từ ytInitialData."""
    # Path 1: URL chứa UC ID trực tiếp
    cid = extract_channel_id_from_url(url_or_handle)
    if cid:
        return cid

    # Path 2: navigate page → parse meta.externalId
    from playwright.sync_api import sync_playwright
    url = url_or_handle.strip()
    if not url.startswith("http"):
        url = (f"https://www.youtube.com/@{url.lstrip('@')}"
               if not url.startswith("/") else f"https://www.youtube.com{url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
                                     args=["--disable-blink-features="
                                           "AutomationControlled"])
        try:
            ctx = browser.new_context()
            ctx.add_cookies([
                {"name": "SOCS", "value": "CAI",
                 "domain": ".youtube.com", "path": "/"},
                {"name": "CONSENT", "value": "YES+cb",
                 "domain": ".youtube.com", "path": "/"},
            ])
            page = ctx.new_page()
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(1000)
            data = page.evaluate(
                "() => window.ytInitialData || null")
            page.close()
            ctx.close()
            if not data:
                return None
            # ytInitialData.metadata.channelMetadataRenderer.externalId
            try:
                meta = (data.get("metadata", {})
                            .get("channelMetadataRenderer", {}))
                eid = meta.get("externalId") or ""
                if _UC_RE.match(eid):
                    return eid
            except Exception:
                pass
            # Fallback: search UC pattern trong toàn data
            text = str(data)[:50000]
            m = _UC_RE.search(text)
            return m.group(0) if m else None
        finally:
            try:
                browser.close()
            except Exception:
                pass
