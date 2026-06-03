"""
Watchlist - quản lý nhiều danh sách kênh để theo dõi liên tục.

Mỗi watchlist:
  - Đại diện 1 ngách / loại nội dung (vd: "JCB Toy Niche", "Tractor DIY")
  - Chứa N kênh: kênh của user (is_self=True) + kênh đối thủ (is_self=False)
  - Có thể chạy monitor riêng → so sánh kênh user vs đối thủ trong cùng ngách

Storage: JSON files trong ~/.youtube_research/watchlists/<id>.json
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


def watchlist_dir() -> Path:
    """Thư mục lưu các watchlist. Tôn trọng shared_history_dir nếu có."""
    try:
        from .config import load_config
        cfg = load_config()
        shared = cfg.get("shared_history_dir", "").strip()
        if shared:
            d = Path(shared).parent / "watchlists"
            d.mkdir(parents=True, exist_ok=True)
            return d
    except Exception:
        pass
    d = Path.home() / ".youtube_research" / "watchlists"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class WatchedChannel:
    channel_id: str               # UCxxxx
    title: str                    # display name (cached)
    url: str                      # full URL
    is_self: bool = False         # True = kênh của user
    added_at: str = ""            # ISO timestamp
    auto_added: bool = False      # True = phần mềm tự phát hiện & kết nạp
    auto_added_pct: float = 0.0   # % trùng từ khoá khi được kết nạp
    # 24/05: archived kênh yếu (không thuộc top 10 view 7d). Giữ pkl
    # history, không tham gia daily run / report. Có thể un-archive sau.
    archived: bool = False
    archived_at: str = ""         # ISO timestamp khi archive
    archived_reason: str = ""     # vd "out_of_top10_views_7d"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "WatchedChannel":
        return cls(
            channel_id=d.get("channel_id", ""),
            title=d.get("title", ""),
            url=d.get("url", ""),
            is_self=bool(d.get("is_self", False)),
            added_at=d.get("added_at", ""),
            auto_added=bool(d.get("auto_added", False)),
            auto_added_pct=float(d.get("auto_added_pct", 0) or 0),
            archived=bool(d.get("archived", False)),
            archived_at=d.get("archived_at", ""),
            archived_reason=d.get("archived_reason", ""),
        )


@dataclass
class Watchlist:
    id: str
    name: str
    description: str = ""
    channels: list = field(default_factory=list)
    created_at: str = ""
    last_monitored: str = ""       # ISO timestamp lần monitor gần nhất
    # Multi-tenant (chốt 23/05): mỗi WL thuộc 1 team / business unit.
    # Default "default" = team chính. Để mở rộng đa team sau, không break WL cũ.
    team_id: str = "default"
    analyses: list = field(default_factory=list)
    # analyses: list of dict {id, analyzed_at, analyzed_by, content}
    # Mới nhất ở đầu (index 0). Giữ tối đa 20 báo cáo gần nhất.

    # Legacy fields (deprecated, giữ để load file cũ)
    last_analysis: str = ""
    last_analyzed_at: str = ""
    last_analyzed_by: str = ""

    # Báo cáo phân tích bình luận khán giả (kênh chính của danh sách)
    comment_report: str = ""
    comment_report_at: str = ""

    # 25/05: pause WL khỏi daily run (kênh chưa upload video, chưa setup
    # OAuth, hoặc tạm dừng theo dõi). WL paused VẪN hiển thị trong list
    # cho user thấy, nhưng skip toàn bộ 6 stage daily run + summary.
    # Bật/tắt trong app: bấm dropdown chọn kênh ở top bar tab Watchlist —
    # mỗi dòng có checkbox (tích = chạy, bỏ tích = tạm dừng, lưu ngay) +
    # tên bấm để xem. Gộp chung dropdown chọn kênh — 30/05. Vẫn có thể
    # edit JSON file trực tiếp nếu cần.
    paused: bool = False
    paused_at: str = ""           # ISO timestamp khi pause
    paused_reason: str = ""       # vd "no_video_upload" / "no_oauth"

    @property
    def latest_analysis(self) -> Optional[dict]:
        """Báo cáo AI gần nhất (dict {id, analyzed_at, analyzed_by, content}).
        Trả None nếu chưa có báo cáo."""
        if self.analyses:
            return self.analyses[0]
        # Fallback legacy
        if self.last_analysis:
            return {
                "id": "legacy",
                "analyzed_at": self.last_analyzed_at,
                "analyzed_by": self.last_analyzed_by,
                "content": self.last_analysis,
            }
        return None

    @property
    def previous_analysis(self) -> Optional[dict]:
        """Báo cáo AI thứ 2 mới nhất (để diff). Trả None nếu chỉ có 1 báo cáo."""
        if len(self.analyses) >= 2:
            return self.analyses[1]
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "channels": [c.to_dict() for c in self.channels],
            "created_at": self.created_at,
            "last_monitored": self.last_monitored,
            "analyses": self.analyses,
            "comment_report": self.comment_report,
            "comment_report_at": self.comment_report_at,
            # Legacy: giữ tương thích ngược
            "last_analysis": self.last_analysis,
            "last_analyzed_at": self.last_analyzed_at,
            "last_analyzed_by": self.last_analyzed_by,
            "paused": self.paused,
            "paused_at": self.paused_at,
            "paused_reason": self.paused_reason,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Watchlist":
        # Migration: nếu file cũ có last_analysis mà không có analyses list
        # → tự động đẩy vào analyses[0]
        analyses = d.get("analyses", []) or []
        legacy_last = d.get("last_analysis", "")
        if legacy_last and not analyses:
            analyses = [{
                "id": "legacy_" + (d.get("last_analyzed_at", "") or "")[:19],
                "analyzed_at": d.get("last_analyzed_at", ""),
                "analyzed_by": d.get("last_analyzed_by", "AI"),
                "content": legacy_last,
            }]
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
            channels=[WatchedChannel.from_dict(c)
                      for c in d.get("channels", [])],
            created_at=d.get("created_at", ""),
            last_monitored=d.get("last_monitored", ""),
            analyses=analyses,
            comment_report=d.get("comment_report", ""),
            comment_report_at=d.get("comment_report_at", ""),
            last_analysis=legacy_last,  # giữ cho tương thích
            last_analyzed_at=d.get("last_analyzed_at", ""),
            last_analyzed_by=d.get("last_analyzed_by", ""),
            paused=bool(d.get("paused", False)),
            paused_at=d.get("paused_at", ""),
            paused_reason=d.get("paused_reason", ""),
        )

    @property
    def self_channel(self) -> Optional[WatchedChannel]:
        """Kênh user (is_self=True) đầu tiên. Trả None nếu chưa set.
        KHÔNG filter archived — kênh chính luôn active."""
        for c in self.channels:
            if c.is_self:
                return c
        return None

    @property
    def active_channels(self) -> list:
        """Channels CHƯA archived (24/05). Dùng cho daily run / monitor /
        discover / report. Self channel luôn active dù bị archive."""
        return [c for c in self.channels
                if (not c.archived) or c.is_self]

    @property
    def archived_channels(self) -> list:
        """Channels đã archived (loại khỏi top 10 SB 7d)."""
        return [c for c in self.channels if c.archived and not c.is_self]

    @property
    def competitor_channels(self) -> list:
        """Đối thủ ACTIVE (không phải kênh user, chưa archived).
        24/05: tự động bỏ archived — daily run + report dùng property này."""
        return [c for c in self.channels
                if not c.is_self and not c.archived]


# ============================================================
# CRUD
# ============================================================

def _safe_filename(s: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", s or "")
    return s.strip("_")[:40] or "watchlist"


def _file_path(watchlist_id: str) -> Path:
    return watchlist_dir() / f"{watchlist_id}.json"


def create_watchlist(name: str, description: str = "") -> Watchlist:
    """Tạo watchlist mới với ID auto-generated. Lưu xuống disk ngay."""
    wid = f"wl_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    wl = Watchlist(
        id=wid,
        name=name.strip() or "Watchlist mới",
        description=description.strip(),
        channels=[],
        created_at=datetime.now().isoformat(timespec="seconds"),
        last_monitored="",
    )
    save_watchlist(wl)
    return wl


def save_watchlist(wl: Watchlist) -> None:
    """Ghi watchlist xuống disk (atomic)."""
    p = _file_path(wl.id)
    tmp = p.with_suffix(".json.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(wl.to_dict(), f, ensure_ascii=False, indent=2)
        tmp.replace(p)
    except Exception:
        # Fallback: ghi trực tiếp
        with open(p, "w", encoding="utf-8") as f:
            json.dump(wl.to_dict(), f, ensure_ascii=False, indent=2)
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def load_watchlist(watchlist_id: str) -> Optional[Watchlist]:
    """Load 1 watchlist. Trả None nếu không tồn tại."""
    p = _file_path(watchlist_id)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return Watchlist.from_dict(json.load(f))
    except Exception:
        return None


def list_watchlists() -> list:
    """List tất cả watchlists, sort theo created_at desc."""
    d = watchlist_dir()
    items = []
    for p in d.glob("wl_*.json"):
        if p.name.endswith(".tmp.json"):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                items.append(Watchlist.from_dict(json.load(f)))
        except Exception:
            continue
    items.sort(key=lambda w: w.created_at, reverse=True)
    return items


def delete_watchlist(watchlist_id: str) -> bool:
    """Xoá watchlist. Không xoá snapshots/events liên quan
    (giữ historical data, user có thể recreate cùng id)."""
    p = _file_path(watchlist_id)
    if not p.exists():
        return False
    try:
        p.unlink()
        return True
    except Exception:
        return False


# ============================================================
# Channel management within a watchlist
# ============================================================

def add_channel(watchlist_id: str, channel: WatchedChannel) -> bool:
    """Thêm kênh vào watchlist. Trả False nếu kênh đã có (dò theo channel_id)."""
    wl = load_watchlist(watchlist_id)
    if not wl:
        return False
    for c in wl.channels:
        if c.channel_id and c.channel_id == channel.channel_id:
            return False
    if not channel.added_at:
        channel.added_at = datetime.now().isoformat(timespec="seconds")
    wl.channels.append(channel)
    save_watchlist(wl)
    return True


def remove_channel(watchlist_id: str, channel_id: str) -> bool:
    wl = load_watchlist(watchlist_id)
    if not wl:
        return False
    n_before = len(wl.channels)
    wl.channels = [c for c in wl.channels if c.channel_id != channel_id]
    if len(wl.channels) == n_before:
        return False
    save_watchlist(wl)
    return True


def mark_as_self(watchlist_id: str, channel_id: str) -> bool:
    """Đánh dấu 1 kênh là kênh user (is_self=True).
    Mỗi watchlist chỉ nên có 1 kênh self → tự động unmark các kênh khác."""
    wl = load_watchlist(watchlist_id)
    if not wl:
        return False
    found = False
    for c in wl.channels:
        if c.channel_id == channel_id:
            c.is_self = True
            found = True
        else:
            c.is_self = False
    if found:
        save_watchlist(wl)
    return found


def unmark_self(watchlist_id: str, channel_id: str) -> bool:
    wl = load_watchlist(watchlist_id)
    if not wl:
        return False
    for c in wl.channels:
        if c.channel_id == channel_id:
            c.is_self = False
            save_watchlist(wl)
            return True
    return False


def update_last_monitored(watchlist_id: str, when: str = "") -> None:
    """Set last_monitored timestamp. Gọi sau mỗi lần monitor xong."""
    wl = load_watchlist(watchlist_id)
    if not wl:
        return
    wl.last_monitored = when or datetime.now().isoformat(timespec="seconds")
    save_watchlist(wl)


def save_analysis(watchlist_id: str, analysis_text: str,
                  analyzed_by: str = "AI",
                  max_history: int = 20) -> bool:
    """Lưu kết quả phân tích chiến lược AI vào watchlist.
    APPEND vào lịch sử (analyses list), KHÔNG overwrite.
    Giữ tối đa max_history báo cáo gần nhất.
    Trả True nếu lưu thành công."""
    wl = load_watchlist(watchlist_id)
    if not wl:
        return False
    now = datetime.now().isoformat(timespec="seconds")
    new_entry = {
        "id": f"ana_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "analyzed_at": now,
        "analyzed_by": analyzed_by,
        "content": analysis_text,
    }
    wl.analyses.insert(0, new_entry)  # mới nhất ở đầu
    if len(wl.analyses) > max_history:
        wl.analyses = wl.analyses[:max_history]
    # Cập nhật legacy fields để tương thích
    wl.last_analysis = analysis_text
    wl.last_analyzed_at = now
    wl.last_analyzed_by = analyzed_by
    save_watchlist(wl)
    return True


def save_comment_report(watchlist_id: str, report_text: str) -> bool:
    """Lưu báo cáo phân tích bình luận khán giả vào watchlist."""
    wl = load_watchlist(watchlist_id)
    if not wl:
        return False
    wl.comment_report = report_text
    wl.comment_report_at = datetime.now().isoformat(timespec="seconds")
    save_watchlist(wl)
    return True


def list_analyses(watchlist_id: str) -> list:
    """List tất cả báo cáo AI của watchlist, mới nhất ở đầu.
    Mỗi item: {id, analyzed_at, analyzed_by, content_preview}.
    content_preview = 200 ký tự đầu để hiện trong UI dropdown."""
    wl = load_watchlist(watchlist_id)
    if not wl:
        return []
    out = []
    for a in wl.analyses:
        content = a.get("content", "")
        out.append({
            "id": a.get("id", ""),
            "analyzed_at": a.get("analyzed_at", ""),
            "analyzed_by": a.get("analyzed_by", ""),
            "content_preview": content[:200],
            "content_length": len(content),
        })
    return out


def load_analysis(watchlist_id: str, analysis_id: str) -> Optional[dict]:
    """Load 1 báo cáo cụ thể theo id. Trả None nếu không tìm thấy."""
    wl = load_watchlist(watchlist_id)
    if not wl:
        return None
    for a in wl.analyses:
        if a.get("id") == analysis_id:
            return a
    return None


def delete_analysis(watchlist_id: str, analysis_id: str) -> bool:
    """Xoá 1 báo cáo khỏi lịch sử."""
    wl = load_watchlist(watchlist_id)
    if not wl:
        return False
    n_before = len(wl.analyses)
    wl.analyses = [a for a in wl.analyses if a.get("id") != analysis_id]
    if len(wl.analyses) == n_before:
        return False
    # Update legacy fields nếu xoá báo cáo mới nhất
    if wl.analyses:
        wl.last_analysis = wl.analyses[0].get("content", "")
        wl.last_analyzed_at = wl.analyses[0].get("analyzed_at", "")
        wl.last_analyzed_by = wl.analyses[0].get("analyzed_by", "")
    else:
        wl.last_analysis = ""
        wl.last_analyzed_at = ""
        wl.last_analyzed_by = ""
    save_watchlist(wl)
    return True
