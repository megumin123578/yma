"""
YouTube client dùng Playwright + Chrome (browser automation).

Mô phỏng người dùng thật: mở Chrome → vào youtube.com → tìm kiếm → cuộn → scrape.
Không cần API key, không bị quota.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import quote


# -------------------- Data classes (giữ nguyên schema cũ) --------------------

@dataclass
class ChannelInfo:
    channel_id: str
    title: str
    handle: str = ""
    description: str = ""
    subscriber_count: int = 0
    view_count: int = 0
    video_count: int = 0
    keywords: list = field(default_factory=list)
    uploads_playlist_id: str = ""
    url: str = ""


@dataclass
class VideoInfo:
    video_id: str
    title: str
    channel_title: str = ""
    channel_id: str = ""
    description: str = ""
    tags: list = field(default_factory=list)
    published_at: str = ""
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    duration_seconds: int = 0
    url: str = ""

    @property
    def days_old(self) -> float:
        if not self.published_at:
            return 0.0
        try:
            dt = datetime.fromisoformat(self.published_at.replace("Z", "+00:00"))
            return max(0.001, (datetime.now(timezone.utc) - dt).total_seconds() / 86400)
        except Exception:
            return 0.0

    @property
    def views_per_day(self) -> float:
        d = self.days_old
        return self.view_count / d if d > 0 else 0.0


# -------------------- URL parsing --------------------

_CHANNEL_ID_RE = re.compile(r"(UC[0-9A-Za-z_-]{22})")
_HANDLE_RE = re.compile(r"@([A-Za-z0-9._-]+)")


def parse_channel_url(url_or_handle: str) -> dict:
    s = url_or_handle.strip()
    if s.startswith("@"):
        return {"kind": "handle", "value": s[1:]}
    m = _CHANNEL_ID_RE.search(s)
    if m and "/channel/" in s:
        return {"kind": "id", "value": m.group(1)}
    if m and m.group(0) == s:
        return {"kind": "id", "value": m.group(1)}
    mh = _HANDLE_RE.search(s)
    if mh and "/@" in s:
        return {"kind": "handle", "value": mh.group(1)}
    mc = re.search(r"/c/([^/?#]+)", s)
    if mc:
        return {"kind": "custom", "value": mc.group(1)}
    mu = re.search(r"/user/([^/?#]+)", s)
    if mu:
        return {"kind": "user", "value": mu.group(1)}
    return {"kind": "custom", "value": s}


# -------------------- Parsers cho ytInitialData --------------------

_VIEW_RE = re.compile(r"([\d.,]+)\s*([KMB])?\s*views?", re.IGNORECASE)
_VIEW_RE_VI = re.compile(r"([\d.,]+)\s*([KMB])?\s*l[ưu][ơo]?t\s*xem", re.IGNORECASE)
# 24/05 BUGFIX A6: thêm suffix tiếng VIỆT (Tr=triệu, N=nghìn, T=tỷ).
# YouTube đổi locale → "7,49 Tr người đăng ký" thay "7.49M subscribers".
# Suffix order: Tr/triệu/nghìn/tỷ trước T (để không bị greedy).
# 24/05 BUGFIX A25 (chiều): thêm `\b` boundary sau suffix để KHÔNG match
# chữ "n" trong "người", "t" trong "tháng", "tr" trong "triệu" (nếu đứng
# riêng lẻ chứ không phải full word). Hỗ trợ full word "triệu/nghìn/tỷ"
# để parse "1 triệu người đăng ký" → 1000000 đúng.
_COUNT_RE = re.compile(
    r"([\d.,]+)\s*(?:(triệu|nghìn|tỷ|Tr|tr|N|n|T|t|[KMBkmb])\b)?",
    re.IGNORECASE)

_TIME_PATTERNS = [
    (re.compile(r"(\d+)\s*second", re.I), 1 / 86400),
    (re.compile(r"(\d+)\s*minute", re.I), 1 / 1440),
    (re.compile(r"(\d+)\s*hour", re.I), 1 / 24),
    (re.compile(r"(\d+)\s*day", re.I), 1.0),
    (re.compile(r"(\d+)\s*week", re.I), 7.0),
    (re.compile(r"(\d+)\s*month", re.I), 30.4375),
    (re.compile(r"(\d+)\s*year", re.I), 365.25),
    # Vietnamese
    (re.compile(r"(\d+)\s*giây", re.I), 1 / 86400),
    (re.compile(r"(\d+)\s*phút", re.I), 1 / 1440),
    (re.compile(r"(\d+)\s*giờ", re.I), 1 / 24),
    (re.compile(r"(\d+)\s*ngày", re.I), 1.0),
    (re.compile(r"(\d+)\s*tuần", re.I), 7.0),
    (re.compile(r"(\d+)\s*tháng", re.I), 30.4375),
    (re.compile(r"(\d+)\s*năm", re.I), 365.25),
]


def _parse_count(text: str) -> int:
    """Parse subs/views với cả format Anh và Việt.

    EN: '1.2M views', '1,234,567 views', '1.5K subscribers' (comma=hàng nghìn, dot=thập phân)
    VN: '1,2 Tr người đăng ký', '1.234.567 lượt xem', '1,5 N người đăng ký' (comma=thập phân, dot=hàng nghìn)

    24/05 BUGFIX A6: thêm suffix VN (Tr=triệu, N=nghìn, T=tỷ) — trước
    đây chỉ K/M/B → "7,49 Tr" → 7 (sai). Giờ ra 7,490,000.
    """
    if not text:
        return 0
    t = text.replace("\xa0", " ").strip()
    m = _COUNT_RE.search(t)
    if not m:
        return 0
    num_str = m.group(1)
    suffix = (m.group(2) or "").lower()

    # Determine locale: VN suffix → comma=thập phân, EN suffix → comma=hàng nghìn
    if suffix in ("tr", "triệu"):
        mult, is_vn = 1_000_000, True
    elif suffix in ("n", "nghìn"):
        mult, is_vn = 1_000, True
    elif suffix in ("t", "tỷ"):
        mult, is_vn = 1_000_000_000, True
    elif suffix == "k":
        mult, is_vn = 1_000, False
    elif suffix == "m":
        mult, is_vn = 1_000_000, False
    elif suffix == "b":
        mult, is_vn = 1_000_000_000, False
    else:
        # No suffix — plain number. Bỏ tất cả comma + dot (cả 2 đều là
        # phân cách hàng nghìn trong số plain). "1,234,567" → 1234567.
        s = num_str.replace(",", "").replace(".", "")
        try:
            return int(s)
        except Exception:
            return 0

    # Có suffix: convert num_str theo locale
    if is_vn:
        # VN: dot là phân cách 1000, comma là thập phân
        # "7,49" → 7.49; "1.234,5" → 1234.5
        s = num_str.replace(".", "").replace(",", ".")
    else:
        # EN: comma là phân cách 1000, dot là thập phân
        # "7.49" → 7.49; "1,234.5" → 1234.5
        s = num_str.replace(",", "")
    try:
        n = float(s)
    except Exception:
        return 0
    return int(n * mult)


def _parse_view_count(text: str) -> int:
    """'1,234,567 views' or '1.2M views' or '1.234.567 lượt xem' -> int."""
    if not text:
        return 0
    return _parse_count(text)


def _parse_published_time_to_days(text: str) -> float:
    """'2 days ago' -> 2.0; '3 hours ago' -> 0.125; '1 week ago' -> 7.0."""
    if not text:
        return 0.0
    for regex, unit_days in _TIME_PATTERNS:
        m = regex.search(text)
        if m:
            try:
                return float(m.group(1)) * unit_days
            except Exception:
                pass
    return 0.0


def _days_to_iso(days: float) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_duration_text(text: str) -> int:
    """'12:34' -> 754; '1:02:03' -> 3723."""
    if not text:
        return 0
    parts = text.strip().split(":")
    try:
        nums = [int(p) for p in parts]
    except Exception:
        return 0
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return 0


def _is_shorts(navigation_url: str, duration_seconds: int) -> bool:
    """Phát hiện video Shorts qua URL /shorts/ hoặc thời lượng ≤ 60 giây."""
    if navigation_url and "/shorts/" in navigation_url:
        return True
    if 0 < duration_seconds <= 60:
        return True
    return False


def _video_renderer_to_info(vr: dict) -> Optional[VideoInfo]:
    """Convert một videoRenderer dict thành VideoInfo. Trả None nếu là Shorts hoặc thiếu video_id."""
    vid = vr.get("videoId")
    if not vid:
        return None

    # Phát hiện Shorts qua URL điều hướng
    nav = vr.get("navigationEndpoint", {})
    url_path = nav.get("commandMetadata", {}).get("webCommandMetadata", {}).get("url", "")

    title_runs = vr.get("title", {}).get("runs") or []
    title = title_runs[0].get("text", "") if title_runs else \
        vr.get("title", {}).get("simpleText", "")

    ch_runs = vr.get("longBylineText", {}).get("runs") or []
    ch_title = ch_runs[0].get("text", "") if ch_runs else ""
    ch_id = ""
    if ch_runs:
        ch_nav = ch_runs[0].get("navigationEndpoint", {})
        ch_id = (
            ch_nav.get("browseEndpoint", {}).get("browseId", "")
            or ch_nav.get("commandMetadata", {}).get("webCommandMetadata", {}).get("url", "")
        )
        if ch_id.startswith("/channel/"):
            ch_id = ch_id[len("/channel/"):]

    views_text = vr.get("viewCountText", {}).get("simpleText", "") or \
        " ".join(r.get("text", "") for r in vr.get("viewCountText", {}).get("runs", []))
    view_count = _parse_view_count(views_text)

    pub_text = vr.get("publishedTimeText", {}).get("simpleText", "")
    days_old = _parse_published_time_to_days(pub_text)
    published_at = _days_to_iso(days_old) if days_old > 0 else ""

    duration_text = vr.get("lengthText", {}).get("simpleText", "")
    duration_seconds = _parse_duration_text(duration_text)

    # Lọc Shorts
    if _is_shorts(url_path, duration_seconds):
        return None

    # Description snippet
    desc = ""
    snippet = vr.get("detailedMetadataSnippets") or []
    if snippet:
        desc = " ".join(
            r.get("text", "") for r in snippet[0].get("snippetText", {}).get("runs", [])
        )
    if not desc:
        desc = " ".join(
            r.get("text", "") for r in vr.get("descriptionSnippet", {}).get("runs", [])
        )

    return VideoInfo(
        video_id=vid,
        title=title,
        channel_title=ch_title,
        channel_id=ch_id,
        description=desc,
        tags=[],
        published_at=published_at,
        view_count=view_count,
        like_count=0,  # không có trong search result
        comment_count=0,  # không có trong search result
        duration_seconds=duration_seconds,
        url=f"https://www.youtube.com/watch?v={vid}",
    )


def _lockup_to_info(lvm: dict) -> Optional[VideoInfo]:
    """Parse cấu trúc lockupViewModel mới của YouTube /videos tab.
    Trả None nếu là Shorts hoặc không phải video.
    """
    vid = lvm.get("contentId")
    if not vid:
        return None
    content_type = lvm.get("contentType", "")
    # LOCKUP_CONTENT_TYPE_SHORTS = Shorts → lọc bỏ
    if "SHORT" in content_type.upper():
        return None
    if content_type != "LOCKUP_CONTENT_TYPE_VIDEO":
        if "VIDEO" not in content_type:
            return None

    meta = lvm.get("metadata", {}).get("lockupMetadataViewModel", {})
    title = meta.get("title", {}).get("content", "")

    view_count = 0
    days_old = 0.0
    duration_seconds = 0

    rows = meta.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
    for row in rows:
        for part in row.get("metadataParts", []):
            text = part.get("text", {}).get("content", "")
            if not text:
                continue
            tl = text.lower()
            if "view" in tl or "xem" in tl:
                view_count = _parse_view_count(text)
            elif "ago" in tl or "trước" in tl:
                days_old = _parse_published_time_to_days(text)

    # Duration nằm trong contentImage overlays
    overlays = lvm.get("contentImage", {}).get("thumbnailViewModel", {}).get("overlays", [])
    for ov in overlays:
        bottom = ov.get("thumbnailBottomOverlayViewModel", {})
        for badge in bottom.get("badges", []):
            text = badge.get("thumbnailBadgeViewModel", {}).get("text", "")
            if text and ":" in text:
                duration_seconds = _parse_duration_text(text)
                break
        if duration_seconds:
            break

    # Lọc Shorts theo duration (≤60s)
    if 0 < duration_seconds <= 60:
        return None

    published_at = _days_to_iso(days_old) if days_old > 0 else ""

    return VideoInfo(
        video_id=vid,
        title=title,
        channel_title="",
        channel_id="",
        description="",
        tags=[],
        published_at=published_at,
        view_count=view_count,
        like_count=0,
        comment_count=0,
        duration_seconds=duration_seconds,
        url=f"https://www.youtube.com/watch?v={vid}",
    )


def _walk_video_renderers(data: dict, limit: Optional[int] = None) -> list:
    """Đệ quy tìm tất cả video trong ytInitialData (hỗ trợ cả format cũ và mới)."""
    out = []
    seen = set()

    def walk(obj):
        if limit and len(out) >= limit:
            return
        if isinstance(obj, dict):
            # Format cũ: videoRenderer
            vr = obj.get("videoRenderer")
            if vr and vr.get("videoId") and vr["videoId"] not in seen:
                seen.add(vr["videoId"])
                info = _video_renderer_to_info(vr)
                if info:
                    out.append(info)
            # Format cũ khác: gridVideoRenderer (legacy channel page)
            gvr = obj.get("gridVideoRenderer")
            if gvr and gvr.get("videoId") and gvr["videoId"] not in seen:
                seen.add(gvr["videoId"])
                info = _video_renderer_to_info(gvr)
                if info:
                    out.append(info)
            # Format mới: lockupViewModel (channel /videos tab 2024+)
            lvm = obj.get("lockupViewModel")
            if lvm and lvm.get("contentId") and lvm["contentId"] not in seen:
                seen.add(lvm["contentId"])
                info = _lockup_to_info(lvm)
                if info:
                    out.append(info)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(data)
    return out


# -------------------- sp= codes cho YouTube search filter --------------------

# Encoded protobuf cho filter "Upload date":
SP_DATE_HOUR = "EgIIAQ%3D%3D"
SP_DATE_TODAY = "EgIIAg%3D%3D"
SP_DATE_WEEK = "EgIIAw%3D%3D"
SP_DATE_MONTH = "EgIIBA%3D%3D"
SP_DATE_YEAR = "EgIIBQ%3D%3D"


def _sp_for_days(days: int) -> str:
    """Chọn filter URL gần nhất bao trùm số ngày."""
    if days <= 0:
        return ""
    if days <= 1:
        return SP_DATE_TODAY
    if days <= 7:
        return SP_DATE_WEEK
    if days <= 30:
        return SP_DATE_MONTH
    if days <= 365:
        return SP_DATE_YEAR
    return ""  # > 1 năm: không filter


# -------------------- PlaywrightBackend --------------------

def _extract_like_count(init_data: dict) -> int:
    """Trích like count từ ytInitialData.

    Pattern tin cậy nhất: accessibilityText = "like this video along with N other people"
    hoặc tiếng Việt "thích video này cùng với N người khác".
    """
    found = []

    def walk(obj):
        if isinstance(obj, dict):
            # Pattern 1: accessibilityText
            label = obj.get("accessibilityText")
            if isinstance(label, str) and label:
                low = label.lower()
                if "like this video" in low or "thích video này" in low:
                    m = re.search(r"([\d,.]+)\s*(?:other|người|người khác)", label)
                    if m:
                        try:
                            n = int(m.group(1).replace(",", "").replace(".", ""))
                            found.append(n)
                        except Exception:
                            pass
            # Pattern 2: aria-label trong accessibility.accessibilityData
            access = obj.get("accessibility")
            if isinstance(access, dict):
                ad = access.get("accessibilityData", {})
                if isinstance(ad, dict):
                    label2 = ad.get("label", "")
                    if isinstance(label2, str) and (
                        "like this video" in label2.lower()
                        or "thích video này" in label2.lower()
                    ):
                        m = re.search(r"([\d,.]+)\s*(?:other|người)", label2)
                        if m:
                            try:
                                n = int(m.group(1).replace(",", "").replace(".", ""))
                                found.append(n)
                            except Exception:
                                pass
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(init_data)
    return max(found) if found else 0


def _extract_comment_count(init_data: dict) -> int:
    """Trích comment count từ ytInitialData (commentCount header)."""
    found = []

    def walk(obj):
        if isinstance(obj, dict):
            # Pattern: countText.simpleText "1,234 Comments"
            for key in ("commentCount", "countText"):
                v = obj.get(key)
                text = ""
                if isinstance(v, dict):
                    text = v.get("simpleText") or v.get("content", "")
                elif isinstance(v, str):
                    text = v
                if text and (
                    "comment" in text.lower() or "bình luận" in text.lower()
                ):
                    m = re.search(r"([\d,.]+)", text)
                    if m:
                        try:
                            n = int(m.group(1).replace(",", "").replace(".", ""))
                            found.append(n)
                        except Exception:
                            pass
            # Pattern: commentsEntryPointHeaderRenderer.commentCount
            cph = obj.get("commentsEntryPointHeaderRenderer")
            if isinstance(cph, dict):
                cc = cph.get("commentCount", {})
                if isinstance(cc, dict):
                    text = cc.get("simpleText") or cc.get("content", "")
                    if text:
                        m = re.search(r"([\d,.]+)", text)
                        if m:
                            try:
                                n = int(m.group(1).replace(",", "").replace(".", ""))
                                found.append(n)
                            except Exception:
                                pass
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(init_data)
    return max(found) if found else 0


class PlaywrightBackend:
    """Mô phỏng người dùng: mở Chrome, vào youtube.com, tìm kiếm.

    chrome_mode:
      - "show": hiện cửa sổ trên màn hình (mặc định)
      - "minimized": chạy thu nhỏ xuống taskbar (không che màn hình)
      - "headless": ẩn hoàn toàn (nhanh nhất, không có cửa sổ)
    """

    def __init__(self, chrome_mode: str = "show", log_fn=print,
                 cdp_url: str = ""):
        """
        cdp_url: nếu set (vd "http://127.0.0.1:9222") → connect_over_cdp
                 đến cloakbrowser pool (IPv6 fake, anti-bot). Khi đó
                 chrome_mode bị bỏ qua (browser do IPv6 Tool quản lý headless).
                 Mặc định rỗng → launch Chrome IP máy như cũ.
        """
        self.chrome_mode = chrome_mode if chrome_mode in ("show", "minimized", "headless") else "show"
        self.log_fn = log_fn
        self.cdp_url = (cdp_url or "").strip()
        self._pw = None
        self._browser = None
        self._ctx = None
        self._page = None
        self._is_cloak = bool(self.cdp_url)
        self._start()

    def _start(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "Chưa cài Playwright. Chạy: pip install playwright && python -m playwright install chromium"
            ) from e

        # Tránh lỗi spawn UNKNOWN khi cwd có ký tự Unicode
        self._orig_cwd = os.getcwd()
        try:
            os.chdir(tempfile.gettempdir())
        except Exception:
            pass

        self._pw = sync_playwright().start()

        # CLOAK MODE: connect_over_cdp đến browser pool IPv6 — KHÔNG launch
        # Chrome riêng, KHÔNG cần stealth (cloakbrowser tự fake fingerprint).
        # Cloakbrowser launched headless bởi IPv6 Tool → window không hiện.
        if self._is_cloak:
            try:
                self._browser = self._pw.chromium.connect_over_cdp(
                    self.cdp_url, timeout=15000)
                # cloakbrowser dùng launch_persistent_context → contexts[0]
                self._ctx = (self._browser.contexts[0]
                             if self._browser.contexts
                             else self._browser.new_context())
                self._page = self._ctx.new_page()
                return  # Bỏ qua launch logic phía dưới
            except Exception as e:
                self.log_fn(f"  [cloak] connect CDP {self.cdp_url} LOI: {e}")
                raise

        # V1 mode: stealth + launch Chrome IP máy
        # Stealth: patch ngầm playwright để mọi browser/context/page tạo
        # sau đây tự động có chống bot detection (ẩn navigator.webdriver,
        # giả plugins, fake canvas fingerprint, etc.). Có thể tắt bằng
        # biến môi trường YT_STEALTH=0 nếu cần debug.
        if os.environ.get("YT_STEALTH", "1") != "0":
            try:
                from playwright_stealth import Stealth
                Stealth().hook_playwright_context(self._pw)
            except ImportError:
                self.log_fn("  [stealth] playwright_stealth chua cai - bo qua")
            except Exception as e:
                self.log_fn(f"  [stealth] LOI: {e} - bo qua")

        # Cấu hình launch theo chrome_mode
        # 24/05 đêm BUGFIX: env YT_FORCE_HEADLESS=1 hoặc biến môi trường
        # spawned từ ProcessPool worker → FORCE headless dù chrome_mode
        # là gì. Lý do: monitor_batch_cloak.py worker SUBPROCESS có thể có
        # code path tạo PlaywrightBackend không qua cdp_url → fallback
        # launch Chrome/Edge SHOW. Force headless tránh hiện window khi
        # chạy 20 worker song song (user khó chịu).
        force_headless = (
            os.environ.get("YT_FORCE_HEADLESS", "0") == "1"
            or self.chrome_mode == "headless")
        args = ["--disable-blink-features=AutomationControlled"]
        if not force_headless:
            if self.chrome_mode == "minimized":
                args.append("--start-minimized")
            elif self.chrome_mode == "show":
                args.append("--window-position=200,100")

        launch_kwargs = {
            "headless": force_headless,
            "args": args,
        }
        if force_headless and self.chrome_mode != "headless":
            self.log_fn(f"  [force-headless] YT_FORCE_HEADLESS=1 → "
                        f"override chrome_mode={self.chrome_mode}")
        try:
            self._browser = self._pw.chromium.launch(channel="chrome", **launch_kwargs)
        except Exception as e:
            self.log_fn(f"  Chrome không khả dụng ({e}); thử Chromium bundled...")
            try:
                self._browser = self._pw.chromium.launch(**launch_kwargs)
            except Exception:
                self._browser = self._pw.chromium.launch(channel="msedge", **launch_kwargs)

        # Random hoá MỖI WORKER để YouTube không nhận diện "đàn bot giống hệt".
        # Mỗi process Chromium con sẽ có UA/viewport/locale/timezone khác nhau.
        import random as _rnd
        _UAS = [
            # Chrome trên Windows (versions khác nhau)
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            # Edge (Chromium-based - vẫn nhìn như Chrome thật)
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
            # Chrome trên Mac
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        ]
        _VIEWPORTS = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1440, "height": 900},
            {"width": 1536, "height": 864},
            {"width": 1600, "height": 900},
            {"width": 1280, "height": 720},
        ]
        _LOCALES = ["en-US", "en-GB"]
        _TIMEZONES = [
            "America/New_York", "America/Los_Angeles", "America/Chicago",
            "Europe/London", "Asia/Singapore",
        ]

        self._ctx = self._browser.new_context(
            viewport=_rnd.choice(_VIEWPORTS),
            user_agent=_rnd.choice(_UAS),
            locale=_rnd.choice(_LOCALES),
            timezone_id=_rnd.choice(_TIMEZONES),
        )
        # Pre-set consent cookies để bỏ qua dialog
        self._ctx.add_cookies([
            {"name": "SOCS", "value": "CAI", "domain": ".youtube.com", "path": "/"},
            {"name": "CONSENT", "value": "YES+cb", "domain": ".youtube.com", "path": "/"},
        ])
        self._page = self._ctx.new_page()

    def close(self):
        # CLOAK MODE: chỉ disconnect CDP, KHÔNG kill cloakbrowser subprocess
        # (IPv6 Tool sẽ quản lý). Trong V1, close = kill Chrome subprocess.
        try:
            if self._page:
                self._page.close()
        except Exception:
            pass
        try:
            if self._ctx and not self._is_cloak:
                # Cloak: context shared, KHÔNG close. V1: ctx riêng, close.
                self._ctx.close()
        except Exception:
            pass
        try:
            if self._browser:
                self._browser.close()  # cloak: disconnect; v1: kill
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        try:
            if hasattr(self, "_orig_cwd"):
                os.chdir(self._orig_cwd)
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ----- helpers -----

    def _goto(self, url: str, wait_ms: int = 2500):
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            self.log_fn(f"  Lỗi điều hướng {url}: {e}")
            return False
        self._page.wait_for_timeout(wait_ms)
        return True

    def _get_data(self) -> dict:
        try:
            data = self._page.evaluate("() => window.ytInitialData")
            return data or {}
        except Exception:
            return {}

    def _scroll_to_load(self, steps: int = 5, delay_ms: int = 800):
        for _ in range(steps):
            try:
                self._page.evaluate("window.scrollBy(0, 1200)")
            except Exception:
                break
            self._page.wait_for_timeout(delay_ms)

    # ----- public methods -----

    def resolve_channel(self, parsed: dict) -> ChannelInfo:
        kind, value = parsed["kind"], parsed["value"]
        if kind == "id":
            url = f"https://www.youtube.com/channel/{value}"
        elif kind == "handle":
            url = f"https://www.youtube.com/@{value}"
        elif kind == "user":
            url = f"https://www.youtube.com/user/{value}"
        else:
            url = f"https://www.youtube.com/c/{value}"

        if not self._goto(url, wait_ms=3000):
            raise ValueError(f"Không truy cập được kênh: {value}")

        data = self._get_data()
        if not data:
            raise ValueError(f"Không lấy được dữ liệu kênh: {value}")

        # Header có thể là c4TabbedHeaderRenderer (kênh cũ) hoặc pageHeaderRenderer (mới)
        header = data.get("header", {})
        c4 = header.get("c4TabbedHeaderRenderer", {}) or {}
        page_hdr = header.get("pageHeaderRenderer", {}) or {}

        meta = data.get("metadata", {}).get("channelMetadataRenderer", {}) or {}
        micro = data.get("microformat", {}).get("microformatDataRenderer", {}) or {}

        title = (
            meta.get("title")
            or c4.get("title")
            or page_hdr.get("pageTitle")
            or ""
        )
        channel_id = (
            meta.get("externalId")
            or c4.get("channelId")
            or ""
        )
        description = (
            meta.get("description")
            or micro.get("description")
            or ""
        )
        keywords_str = meta.get("keywords", "") or ""
        keywords = _split_channel_keywords(keywords_str)

        # Subscribers
        sub_text = ""
        sub_text = (
            c4.get("subscriberCountText", {}).get("simpleText", "")
            or c4.get("subscriberCountText", {}).get("accessibility", {})
                  .get("accessibilityData", {}).get("label", "")
        )
        # Trên pageHeader phiên bản mới
        if not sub_text:
            ph_content = page_hdr.get("content", {}).get("pageHeaderViewModel", {})
            md = ph_content.get("metadata", {}).get("contentMetadataViewModel", {})
            for row in md.get("metadataRows", []):
                for part in row.get("metadataParts", []):
                    text = part.get("text", {}).get("content", "")
                    if "subscriber" in text.lower() or "người" in text.lower():
                        sub_text = text
                        break
                if sub_text:
                    break
        sub_count = _parse_count(sub_text)

        # Channel handle
        handle = ""
        if kind == "handle":
            handle = value
        elif "channelHandleText" in (c4 or {}):
            handle = c4.get("channelHandleText", {}).get("runs", [{}])[0].get("text", "")
            handle = handle.lstrip("@")
        elif micro.get("urlCanonical", "").startswith("https://www.youtube.com/@"):
            handle = micro["urlCanonical"].split("/@")[-1]

        return ChannelInfo(
            channel_id=channel_id,
            title=title,
            handle=handle,
            description=description,
            subscriber_count=sub_count,
            view_count=0,
            video_count=0,
            keywords=keywords,
            uploads_playlist_id="",
            url=f"https://www.youtube.com/channel/{channel_id}" if channel_id else url,
        )

    def list_channel_videos(self, channel: ChannelInfo, limit: int = 50) -> list:
        """Lấy danh sách video gần đây của kênh từ tab /videos."""
        base = channel.url.rstrip("/")
        url = base + "/videos"
        if not self._goto(url, wait_ms=2500):
            return []

        # Cuộn để load thêm video
        scrolls_needed = max(1, (limit + 24) // 25)  # ~30 video/page load
        self._scroll_to_load(steps=min(scrolls_needed, 10), delay_ms=900)

        data = self._get_data()
        # _walk_video_renderers tự xử lý cả 3 format:
        # - videoRenderer (search results)
        # - gridVideoRenderer (channel page cũ)
        # - lockupViewModel (channel /videos 2024+)
        videos = _walk_video_renderers(data, limit=limit)

        # Bổ sung channel_title (lockupViewModel không có)
        for v in videos:
            if not v.channel_title:
                v.channel_title = channel.title
                v.channel_id = channel.channel_id

        return videos[:limit]

    def get_video_full_details(self, video_id: str) -> dict:
        """Vào trang video lấy tags + description + likes + comments.

        Tags: từ ytInitialPlayerResponse.videoDetails.keywords
        Likes: từ accessibilityText "like this video along with N other people"
               trong ytInitialData
        Comments: từ commentCount/headerText nếu có
        """
        if not video_id:
            return {}
        url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=20000)
            self._page.wait_for_timeout(800)
            # Scroll multi-step để trigger comment section render
            try:
                for y in (800, 1600, 2200):
                    self._page.evaluate(f"window.scrollTo(0, {y})")
                    self._page.wait_for_timeout(700)
            except Exception:
                pass
            player = self._page.evaluate("() => window.ytInitialPlayerResponse")
            init = self._page.evaluate("() => window.ytInitialData")
        except Exception:
            return {}
        if not player:
            return {}

        try:
            vd = player.get("videoDetails", {}) or {}
            mf = player.get("microformat", {}).get(
                "playerMicroformatRenderer", {}) or {}
            result = {
                "tags": vd.get("keywords") or [],
                "description": vd.get("shortDescription") or "",
                "category": mf.get("category", ""),
                "publish_date": mf.get("publishDate", ""),
                "view_count": int(vd.get("viewCount") or 0),
                "length_seconds": int(vd.get("lengthSeconds") or 0),
                "like_count": 0,
                "comment_count": 0,
            }
        except Exception:
            return {}

        # Like + comment count từ ytInitialData
        if init:
            try:
                result["like_count"] = _extract_like_count(init)
            except Exception:
                pass
            try:
                result["comment_count"] = _extract_comment_count(init)
            except Exception:
                pass

        # Fallback comment count từ DOM (sau khi scroll)
        if result["comment_count"] == 0:
            try:
                # Chờ comment header xuất hiện (lazy load)
                self._page.wait_for_selector(
                    "ytd-comments-header-renderer", timeout=5000)
                self._page.wait_for_timeout(500)
                # Lấy text từ h2 hoặc whole renderer
                for selector in (
                    "ytd-comments-header-renderer h2 yt-formatted-string",
                    "ytd-comments-header-renderer h2",
                    "ytd-comments-header-renderer #count",
                    "ytd-comments-header-renderer",
                ):
                    try:
                        el = self._page.locator(selector).first
                        text = el.text_content(timeout=1500) or ""
                        if text.strip():
                            m = re.search(r"([\d,.]+)", text)
                            if m:
                                n = int(m.group(1).replace(",", "").replace(".", ""))
                                if n > 0:
                                    result["comment_count"] = n
                                    break
                    except Exception:
                        continue
            except Exception:
                pass

        return result

    def enrich_videos_with_tags(self, videos: list,
                                 log_fn=lambda *_: None,
                                 progress_fn=None,
                                 base_pct: int = 25,
                                 cancel_event=None) -> None:
        """Vào từng trang video lấy tags + description đầy đủ.
        Cập nhật videos in-place. Bỏ qua video lỗi.

        24/05 đêm muộn — FAST MODE: nếu config có `youtube_data_api_key`
        → dùng API videos.list batch 50 ID (1 điểm/request, ~0.5s tổng
        cho 30 video) thay vì 30 navigate /watch (~100s). Speedup ~175×,
        data đầy đủ + có comment_count. Fallback Playwright nếu API fail
        hoặc không có key.
        """
        if not videos:
            return
        total = len(videos)

        # --- FAST PATH: API videos.list ---
        try:
            from .config import load_config
            api_key = (load_config().get("youtube_data_api_key", "") or "").strip()
        except Exception:
            api_key = ""
        if api_key:
            try:
                from .data_enricher import enrich_videos as _api_enrich
                vids_with_id = [v for v in videos if v.video_id]
                ids = [v.video_id for v in vids_with_id]
                log_fn(f"    [API mode] Enrich {len(ids)} video qua "
                       f"videos.list batch (1 điểm quota)")
                enriched = _api_enrich(ids, log_fn=None)
                emap = {ev.video_id: ev for ev in enriched}
                n_updated = 0
                for v in vids_with_id:
                    ev = emap.get(v.video_id)
                    if not ev:
                        continue
                    if ev.tags:
                        v.tags = ev.tags
                    if ev.description and len(ev.description) > len(v.description or ""):
                        v.description = ev.description
                    if ev.view_count > v.view_count:
                        v.view_count = ev.view_count
                    if not v.duration_seconds and ev.duration_seconds:
                        v.duration_seconds = ev.duration_seconds
                    if ev.like_count > v.like_count:
                        v.like_count = ev.like_count
                    if ev.comment_count > v.comment_count:
                        v.comment_count = ev.comment_count
                    if ev.published_at and not v.published_at:
                        v.published_at = ev.published_at
                    n_updated += 1
                log_fn(f"    [API mode] OK — enriched {n_updated}/{total} video")
                # 24/05 đêm muộn: lưu vào video_cache (bộ nhớ phụ) cho
                # tracking video MỚI vs CŨ + meta cố định (title, duration,
                # tags, published_at). Dùng cho audit + report ngày sau.
                try:
                    from .video_cache import (upsert_videos,
                                               find_new_video_ids)
                    if vids_with_id:
                        cid = (vids_with_id[0].channel_id or "") if vids_with_id else ""
                        all_ids = [v.video_id for v in vids_with_id]
                        new_ids, old_ids = find_new_video_ids(cid, all_ids)
                        upsert_videos(cid, vids_with_id)
                        log_fn(f"    [cache] saved {len(vids_with_id)} video, "
                               f"new={len(new_ids)} re-enrich={len(old_ids)}")
                except Exception as ce:
                    log_fn(f"    [cache] skip ({ce})")
                if progress_fn:
                    progress_fn(base_pct + 7, 100,
                                f"API enrich xong {n_updated} video")
                return
            except Exception as e:
                log_fn(f"    [API mode] LỖI ({e}) — fallback Playwright")
                # Tiếp xuống slow path

        # --- SLOW PATH: navigate /watch từng video (V1 cũ) ---
        log_fn(f"    Đang trích tags + mô tả đầy đủ từ {total} trang video...")
        for i, v in enumerate(videos, 1):
            if cancel_event and cancel_event.is_set():
                return
            details = self.get_video_full_details(v.video_id)
            if details:
                if details.get("tags"):
                    v.tags = details["tags"]
                desc = details.get("description") or ""
                if desc and len(desc) > len(v.description or ""):
                    v.description = desc
                if details.get("view_count") and details["view_count"] > v.view_count:
                    v.view_count = details["view_count"]
                if not v.duration_seconds and details.get("length_seconds"):
                    v.duration_seconds = details["length_seconds"]
                # Like + Comment counts
                if details.get("like_count"):
                    v.like_count = details["like_count"]
                if details.get("comment_count"):
                    v.comment_count = details["comment_count"]
            if i % 3 == 0 or i == total:
                log_fn(f"      Tags {i}/{total} ({v.title[:40]}...)")
            if progress_fn:
                pct = base_pct + int(7 * i / total)
                progress_fn(pct, 100, f"Trích tags: {i}/{total}")

    def search(
        self,
        keyword: str,
        max_results: int = 25,
        order: str = "viewCount",
        published_after: Optional[datetime] = None,
        region_code: Optional[str] = None,
    ) -> list:
        """Tìm kiếm YouTube, lọc theo ngày, sort theo lượt xem.

        Cách hoạt động:
        1. Vào youtube.com/results?search_query=KEYWORD&sp=<filter date>
        2. Scroll để load nhiều kết quả
        3. Parse ytInitialData, lấy tất cả videoRenderer
        4. Lọc nghiêm ngặt theo days_old <= N
        5. Sort theo view_count (nếu order='viewCount') hoặc published_at (nếu 'date')
        """
        days = None
        if published_after:
            delta = datetime.now(timezone.utc) - published_after
            days = max(1, int(delta.total_seconds() / 86400))

        sp = _sp_for_days(days) if days else ""
        url = f"https://www.youtube.com/results?search_query={quote(keyword)}"
        if sp:
            url += f"&sp={sp}"

        if not self._goto(url, wait_ms=2800):
            return []

        # Scroll để load thêm kết quả
        self._scroll_to_load(steps=3, delay_ms=800)

        data = self._get_data()
        # Lấy nhiều hơn cần thiết để có room sau khi filter
        videos = _walk_video_renderers(data, limit=max_results * 3)

        # Filter theo days nghiêm ngặt
        if days:
            videos = [v for v in videos if v.days_old <= days]

        # Sort
        if order == "viewCount":
            videos.sort(key=lambda v: v.view_count, reverse=True)
        elif order == "date":
            videos.sort(key=lambda v: v.published_at, reverse=True)

        results = videos[:max_results]

        # PHASE 4 (24/05 đêm muộn): enrich search results qua API videos.list
        # nếu có youtube_data_api_key. Cách B file user dán: cào HTML lấy ID
        # (FREE) → API enrich (1 điểm/batch 50). Tăng data quality (tags,
        # comment_count, duration chuẩn) — KHÔNG dùng search.list API (đắt).
        try:
            from .config import load_config
            api_key = (load_config().get("youtube_data_api_key", "")
                       or "").strip()
            if api_key and results:
                from .data_enricher import enrich_videos
                ids = [v.video_id for v in results if v.video_id]
                if ids:
                    enriched = enrich_videos(ids, log_fn=None)
                    emap = {ev.video_id: ev for ev in enriched}
                    for v in results:
                        ev = emap.get(v.video_id)
                        if not ev:
                            continue
                        # Upgrade các field thiếu/rough từ HTML
                        if ev.tags:
                            v.tags = ev.tags
                        if (ev.description and
                                len(ev.description) > len(v.description or "")):
                            v.description = ev.description
                        if ev.view_count > 0:
                            v.view_count = ev.view_count
                        if ev.like_count > v.like_count:
                            v.like_count = ev.like_count
                        if ev.comment_count > v.comment_count:
                            v.comment_count = ev.comment_count
                        if ev.duration_seconds and not v.duration_seconds:
                            v.duration_seconds = ev.duration_seconds
                        if ev.published_at and not v.published_at:
                            v.published_at = ev.published_at
                        if ev.channel_id and not v.channel_id:
                            v.channel_id = ev.channel_id
                        if ev.channel_title and not v.channel_title:
                            v.channel_title = ev.channel_title
        except Exception:
            # Silent fail — kết quả V1 từ HTML vẫn OK
            pass

        return results

    def get_video_comments(self, video_id: str,
                           max_comments: int = 3000,
                           log_fn=None) -> list:
        """Cào TOÀN BỘ bình luận của 1 video — gồm cả bình luận gốc và
        các trả lời (replies).

        Trả list dict {comment_id, comment_key, author, text,
                       like_count, time_text, is_reply}.
        comment_key dò trùng: ưu tiên comment_id (lc=), fallback hash.
        """
        log = log_fn or self.log_fn
        pg = self._page
        url = f"https://www.youtube.com/watch?v={video_id}"
        if not self._goto(url, wait_ms=3000):
            return []
        # Cuộn xuống kích hoạt phần bình luận (dùng wheel — sự kiện thật)
        for _ in range(4):
            try:
                pg.mouse.wheel(0, 1100)
            except Exception:
                pass
            pg.wait_for_timeout(900)
        try:
            pg.wait_for_selector("ytd-comment-thread-renderer",
                                 timeout=9000)
        except Exception:
            return []  # video tắt bình luận hoặc chưa có

        # 1) Cuộn tải hết bình luận GỐC
        last, stable = 0, 0
        for _ in range(300):
            try:
                pg.mouse.wheel(0, 3000)
            except Exception:
                break
            pg.wait_for_timeout(1100)
            try:
                cnt = pg.evaluate(
                    "document.querySelectorAll("
                    "'ytd-comment-thread-renderer').length")
            except Exception:
                cnt = last
            if cnt >= max_comments:
                break
            if cnt == last:
                stable += 1
                if stable >= 6:
                    break
            else:
                stable = 0
            last = cnt

        # 2) Mở rộng tất cả TRẢ LỜI (replies) — bấm nút "X replies"
        #    + "Show more replies", lặp tới khi không còn nút nào
        expand_js = r"""
        () => {
          let clicked = 0;
          // Nút mở/hiện thêm trả lời
          const sels = [
            'ytd-comment-thread-renderer #more-replies button',
            'ytd-comment-replies-renderer #more-replies button',
            'ytd-comment-replies-renderer '
              + 'ytd-continuation-item-renderer button',
          ];
          for (const s of sels) {
            document.querySelectorAll(s).forEach(b => {
              try {
                if (b.offsetParent !== null) { b.click(); clicked++; }
              } catch (e) {}
            });
          }
          return clicked;
        }
        """
        for _ in range(15):
            try:
                clicked = pg.evaluate(expand_js)
            except Exception:
                clicked = 0
            if not clicked:
                break
            pg.wait_for_timeout(1300)
            # cuộn nhẹ để continuation trả lời tải
            try:
                pg.mouse.wheel(0, 600)
            except Exception:
                pass
            pg.wait_for_timeout(500)

        # 3) Trích TẤT CẢ bình luận (gốc + trả lời) qua view-model
        extract_js = r"""
        () => {
          const out = [];
          const items = document.querySelectorAll(
              'ytd-comment-view-model');
          for (const it of items) {
            const textEl = it.querySelector('#content-text');
            const authorEl = it.querySelector('#author-text');
            const likeEl = it.querySelector('#vote-count-middle');
            let timeText = '', lc = '';
            const timeA = it.querySelector(
                '.published-time-text a, #published-time-text a');
            if (timeA) {
              timeText = (timeA.innerText || '').trim();
              const href = timeA.getAttribute('href') || '';
              const m = href.match(/[?&]lc=([^&]+)/);
              if (m) lc = m[1];
            }
            const isReply = !!it.closest(
                'ytd-comment-replies-renderer');
            out.push({
              text: textEl ? (textEl.innerText || '').trim() : '',
              author: authorEl ? (authorEl.innerText || '').trim() : '',
              likes: likeEl ? (likeEl.innerText || '').trim() : '',
              time_text: timeText,
              comment_id: lc,
              is_reply: isReply,
            });
          }
          return out;
        }
        """
        try:
            raw = pg.evaluate(extract_js)
        except Exception as e:
            log(f"    Lỗi trích bình luận: {e}")
            raw = []

        import hashlib
        out = []
        seen = set()
        for r in (raw or [])[:max_comments]:
            text = (r.get("text") or "").strip()
            if not text:
                continue
            author = (r.get("author") or "").strip()
            cid = r.get("comment_id") or ""
            if cid:
                key = cid
            else:
                key = hashlib.md5(
                    (author + "|" + text).encode(
                        "utf-8", errors="ignore")).hexdigest()[:20]
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "comment_id": cid,
                "comment_key": key,
                "author": author,
                "text": text,
                "like_count": _parse_count(r.get("likes", "")),
                "time_text": r.get("time_text", ""),
                "is_reply": bool(r.get("is_reply")),
            })
        return out


def _split_channel_keywords(blob: str) -> list:
    if not blob:
        return []
    out = []
    tokens = re.findall(r'"([^"]+)"|(\S+)', blob)
    for quoted, single in tokens:
        v = (quoted or single).strip()
        if v:
            out.append(v)
    return out


# -------------------- Factory --------------------

def get_client(chrome_mode: str = "show", log_fn=print):
    """Trả về (PlaywrightBackend, 'browser')."""
    return PlaywrightBackend(chrome_mode=chrome_mode, log_fn=log_fn), "browser"


# ====================================================================
# YouTube competition (số kết quả) + autosuggest — không cần Playwright
# Gọi HTTP trực tiếp, nhẹ và nhanh.
# ====================================================================

import urllib.request
import urllib.parse
import urllib.error


def get_youtube_search_result_count(keyword: str, timeout: int = 8) -> int:
    """Đếm số video YouTube trả về cho 1 từ khoá (proxy 'competition').

    YouTube không có endpoint chính thức, nhưng trang search page có nhúng
    `estimatedResults` trong ytInitialData. Đọc qua HTTP request đơn giản.
    """
    if not keyword:
        return 0
    try:
        url = (f"https://www.youtube.com/results?search_query="
               f"{urllib.parse.quote(keyword)}")
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Cookie": "SOCS=CAI; CONSENT=YES+cb",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return 0

    # Tìm "estimatedResults":"123456"
    m = re.search(r'"estimatedResults":"(\d+)"', html)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass
    return 0


def get_youtube_autosuggest(keyword: str, timeout: int = 5,
                            region: str = "VN") -> list:
    """Lấy autosuggest từ YouTube cho 1 từ khoá. Trả list các gợi ý."""
    if not keyword:
        return []
    try:
        # YouTube autosuggest endpoint (public, no key needed)
        url = (
            "https://suggestqueries-clients6.youtube.com/complete/search"
            f"?client=youtube&ds=yt&q={urllib.parse.quote(keyword)}"
            f"&gl={region.lower()}&hl=en"
        )
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "*/*",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    # YouTube trả về JSONP: window.google.ac.h(["query", [["sug1"], ...], ...])
    # Hoặc JSON thuần. Bóc list gợi ý.
    try:
        # Tìm JSON array đầu tiên
        start = text.find("[")
        end = text.rfind("]")
        if start < 0 or end <= start:
            return []
        # Parse như json
        data = json.loads(text[start:end + 1])
        # Format: [query, [["sug1", ...], ["sug2", ...]], ...]
        if len(data) >= 2 and isinstance(data[1], list):
            suggestions = []
            for item in data[1]:
                if isinstance(item, list) and item:
                    s = item[0]
                    if isinstance(s, str):
                        suggestions.append(s)
            return suggestions
    except Exception:
        pass
    return []


import json as _json_for_autosuggest  # alias để dùng json trong hàm trên
json = _json_for_autosuggest
