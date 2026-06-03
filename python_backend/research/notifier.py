"""
Notifier - desktop notifications + daily digest.

Windows: dùng plyer (nếu có) hoặc fallback toast qua win32api.
Cross-platform fallback: chỉ log ra console.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


_PLYER_AVAILABLE = None


def _check_plyer() -> bool:
    """Kiểm tra plyer có khả dụng không. Cache kết quả."""
    global _PLYER_AVAILABLE
    if _PLYER_AVAILABLE is not None:
        return _PLYER_AVAILABLE
    try:
        from plyer import notification  # noqa
        _PLYER_AVAILABLE = True
    except Exception:
        _PLYER_AVAILABLE = False
    return _PLYER_AVAILABLE


def _icon_path() -> Optional[str]:
    """Path icon .ico để hiển thị trong notification."""
    # Khi packaged bằng PyInstaller, dùng sys._MEIPASS
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))
    p = Path(base) / "icon.ico"
    return str(p) if p.exists() else None


def notify(title: str, message: str, severity: str = "medium",
           timeout: int = 10) -> bool:
    """Show desktop notification. Trả True nếu thành công.
    severity = 'high' | 'medium' | 'low' (chỉ ảnh hưởng prefix emoji)."""
    if severity == "high":
        title = "🔥 " + title
    elif severity == "medium":
        title = "📊 " + title
    # low: no prefix

    # Truncate
    if len(title) > 80:
        title = title[:77] + "..."
    if len(message) > 240:
        message = message[:237] + "..."

    if _check_plyer():
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message,
                app_name="Funtime YouTube Research",
                app_icon=_icon_path(),
                timeout=timeout,
            )
            return True
        except Exception as e:
            print(f"[notifier] plyer failed: {e}", file=sys.stderr)

    # Fallback: log console only
    print(f"[NOTIFY {severity.upper()}] {title}: {message}")
    return False


def notify_digest(watchlist_name: str, events: list) -> bool:
    """Send 1 summary notification cho cả digest. Nếu nhiều event,
    chỉ show event severity cao nhất + count tổng."""
    if not events:
        return False
    # Sort severity high > medium > low
    rank = {"high": 0, "medium": 1, "low": 2}
    events = sorted(events, key=lambda e: rank.get(e["severity"], 9))
    top = events[0]
    n_high = sum(1 for e in events if e["severity"] == "high")
    n_med = sum(1 for e in events if e["severity"] == "medium")
    n_low = sum(1 for e in events if e["severity"] == "low")

    title = f"{watchlist_name}: {len(events)} sự kiện mới"
    parts = []
    if n_high:
        parts.append(f"{n_high} cao")
    if n_med:
        parts.append(f"{n_med} TB")
    if n_low:
        parts.append(f"{n_low} thấp")
    summary = " · ".join(parts) if parts else ""
    top_msg = top["title"]
    if len(top_msg) > 150:
        top_msg = top_msg[:147] + "..."
    message = f"{summary}\n→ {top_msg}"
    return notify(title, message,
                  severity=top["severity"] if events else "low", timeout=15)


def format_digest_text(watchlist_name: str, events: list) -> str:
    """Format events thành text digest cho hiển thị / log."""
    if not events:
        return f"[{watchlist_name}] Không có sự kiện đáng chú ý."
    rank = {"high": 0, "medium": 1, "low": 2}
    events = sorted(events, key=lambda e: rank.get(e["severity"], 9))
    lines = [f"📋 Báo cáo động tĩnh thị trường — {watchlist_name}",
             f"   Tổng {len(events)} sự kiện",
             ""]
    cur_sev = None
    for e in events:
        if e["severity"] != cur_sev:
            cur_sev = e["severity"]
            label = {"high": "🔴 ƯU TIÊN CAO",
                     "medium": "🟡 TRUNG BÌNH",
                     "low": "🟢 THẤP"}.get(cur_sev, cur_sev)
            lines.append(f"\n{label}:")
        lines.append(f"  • {e['title']}")
        if e.get("description"):
            lines.append(f"    {e['description']}")
    return "\n".join(lines)
