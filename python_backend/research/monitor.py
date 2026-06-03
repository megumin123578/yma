"""
Monitor - pipeline theo dõi watchlist liên tục.

Khác với run_research:
  - KHÔNG nghiên cứu từ khoá (không search YouTube)
  - KHÔNG tải tags từng video (chỉ tags của listing)
  - CHỈ lấy: channel info + 30 video gần nhất + view counts
  - LƯU snapshot vào SQLite → so sánh với snapshot trước → phát hiện sự kiện

Mục đích: chạy nhanh (~30-60s/kênh) hàng đêm hoặc theo giờ → tracking continuous.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from statistics import median
from typing import Callable, Optional

from . import snapshots
from . import watchlist as wl_mod
from .youtube_client import (
    PlaywrightBackend, parse_channel_url,
)


# Thresholds
EARLY_VIRAL_MULTIPLIER = 10.0    # views/h > 10× baseline = early viral
VELOCITY_SURGE_MULTIPLIER = 5.0   # delta views/h vs current = velocity surge
SUBS_SPIKE_HIGH_PCT = 5.0         # +5% subs/week = high
SUBS_SPIKE_MED_PCT = 2.0          # +2% = medium
SUBS_DROP_PCT = -1.0              # -1% = drop event

MILESTONE_LEVELS = [100_000, 500_000, 1_000_000, 5_000_000,
                    10_000_000, 50_000_000, 100_000_000]


class MonitorCancelled(Exception):
    pass


def _try_resolve_channel(client, ch, log_fn):
    """Thử resolve channel với multi URL strategy.
    1. URL gốc user nhập (có thể là handle/custom/channel_id)
    2. Nếu fail và là channel_id → fallback resolve trực tiếp
    Trả None nếu fail hoàn toàn."""
    # Strategy 1: parse URL như user nhập
    src = ch.url or ch.channel_id
    try:
        parsed = parse_channel_url(src)
        channel = client.resolve_channel(parsed)
        if channel and channel.title and channel.subscriber_count > 0:
            return channel
    except Exception as e:
        log_fn(f"    Resolve fail (URL): {e}")

    # Strategy 2: nếu channel_id khác URL, thử trực tiếp
    if ch.channel_id and ch.channel_id.startswith("UC") and src != ch.channel_id:
        try:
            channel = client.resolve_channel(
                {"kind": "id", "value": ch.channel_id})
            if channel and channel.title and channel.subscriber_count > 0:
                return channel
        except Exception as e:
            log_fn(f"    Resolve fail (id): {e}")

    return None


def _compute_baseline_vph(videos: list) -> float:
    """Median views/hour của các video cũ (> 7 ngày tuổi) làm baseline."""
    older = [v for v in videos if v.days_old > 7 and v.view_count > 0]
    if len(older) < 3:
        return 0.0
    vph = [v.view_count / max(v.days_old * 24, 1) for v in older]
    return median(vph)


def _compute_video_velocity(video, baseline_vph: float) -> dict:
    """Tính views_per_hour, viral_score, is_early_viral cho 1 video."""
    if not video.published_at or video.days_old <= 0:
        return {"vph": 0, "score": 0, "is_early_viral": False}
    hours_old = video.days_old * 24
    vph = video.view_count / max(hours_old, 1)
    # Score = bội số so với baseline
    score = vph / baseline_vph if baseline_vph > 0 else 0
    # Early viral: < 7 ngày tuổi, > 6h tuổi (để vph stable), score >= threshold
    is_early = (
        video.days_old < 7 and
        hours_old > 6 and
        score >= EARLY_VIRAL_MULTIPLIER
    )
    return {"vph": vph, "score": score, "is_early_viral": is_early}


def _detect_milestone(prev_subs: int, cur_subs: int) -> Optional[int]:
    """Trả về milestone vừa vượt qua (nếu có)."""
    for level in MILESTONE_LEVELS:
        if prev_subs < level <= cur_subs:
            return level
    return None


def _format_int(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)


def monitor_watchlist(
    watchlist_id: str,
    chrome_mode: str = "headless",
    log_fn: Callable[[str], None] = print,
    progress_fn: Callable[[int, int, str], None] = lambda *_: None,
    cancel_event: Optional[threading.Event] = None,
) -> dict:
    """Chạy monitor 1 watchlist. Trả dict tổng kết."""
    def _check_cancel():
        if cancel_event and cancel_event.is_set():
            raise MonitorCancelled("Cancelled")

    wl = wl_mod.load_watchlist(watchlist_id)
    if not wl:
        raise ValueError(f"Không tìm thấy watchlist: {watchlist_id}")
    if not wl.channels:
        raise ValueError(f"Watchlist '{wl.name}' chưa có kênh nào")

    log_fn(f"Monitor watchlist: {wl.name} ({len(wl.channels)} kênh)")
    snapshots.init_db()

    captured_at = datetime.now().isoformat(timespec="seconds")
    log_fn(f"  Captured at: {captured_at}")

    log_fn("  Khởi tạo Chrome...")
    client = PlaywrightBackend(chrome_mode=chrome_mode, log_fn=log_fn)
    events_created = []
    snapshots_saved = 0

    try:
        total = len(wl.channels)
        for i, ch in enumerate(wl.channels, 1):
            _check_cancel()
            log_fn(f"  ({i}/{total}) {ch.title or ch.channel_id}"
                   f" {'★' if ch.is_self else ''}")
            progress_fn(int(100 * (i - 1) / total), 100,
                        f"({i}/{total}) {ch.title}")
            try:
                events = _monitor_one_channel(
                    client, wl, ch, captured_at, log_fn)
                events_created.extend(events)
                snapshots_saved += 1
            except Exception as e:
                log_fn(f"    LỖI: {e}")
                # Không raise → tiếp tục các kênh khác

        wl_mod.update_last_monitored(watchlist_id, captured_at)
        progress_fn(100, 100, "Hoàn tất")
        log_fn(f"  Done. {snapshots_saved}/{total} snapshots, "
               f"{len(events_created)} events.")
    finally:
        try:
            client.close()
        except Exception:
            pass

    # Tổng kết
    high = sum(1 for e in events_created if e["severity"] == "high")
    med = sum(1 for e in events_created if e["severity"] == "medium")
    low = sum(1 for e in events_created if e["severity"] == "low")
    return {
        "watchlist_id": watchlist_id,
        "watchlist_name": wl.name,
        "captured_at": captured_at,
        "channels_monitored": snapshots_saved,
        "channels_total": total,
        "events": events_created,
        "event_count_high": high,
        "event_count_medium": med,
        "event_count_low": low,
    }


def _monitor_one_channel(client, wl, ch, captured_at: str,
                         log_fn) -> list:
    """Monitor 1 kênh: lấy info + 30 video, save snapshot, detect events.
    Trả list events đã tạo."""
    # 1. Resolve channel - thử URL trước, fallback channel_id
    channel = _try_resolve_channel(client, ch, log_fn)
    if not channel or not channel.title or channel.subscriber_count <= 0:
        # Resolve failed → skip + tạo event để user thấy
        snapshots.save_event(
            watchlist_id=wl.id,
            event_type="resolve_failed",
            severity="medium",
            title=f"⚠ Không truy cập được kênh: {ch.title or ch.channel_id}",
            description=f"Kênh không phản hồi đúng format. URL: {ch.url}. "
                        f"Có thể channel_id bị sai hoặc kênh đã đổi tên/xoá.",
            channel_id=ch.channel_id,
            channel_title=ch.title,
            data={"url": ch.url, "channel_id": ch.channel_id},
            detected_at=captured_at,
        )
        log_fn(f"    ⚠ Bỏ qua: không resolve được kênh")
        return []

    # 2. Lấy 30 video gần nhất (KHÔNG enrich tags để nhanh)
    videos = client.list_channel_videos(channel, limit=30)
    log_fn(f"    {channel.subscriber_count:,} subs, {len(videos)} videos")

    # 3. Tính baseline views/hour
    baseline_vph = _compute_baseline_vph(videos)

    # 4. Save channel snapshot
    # video_count: ưu tiên channel.video_count (từ YouTube metadata),
    # fallback len(videos) — vì YouTube có thể không trả video_count
    vid_count = channel.video_count or len(videos)
    ch_snap_id = snapshots.save_channel_snapshot(
        watchlist_id=wl.id,
        channel_id=channel.channel_id,
        channel_title=channel.title,
        is_self=ch.is_self,
        subscriber_count=channel.subscriber_count,
        video_count=vid_count,
        view_count=channel.view_count,
        captured_at=captured_at,
    )

    # 5. Save từng video snapshot + tính velocity
    early_viral_videos = []
    for v in videos:
        vel = _compute_video_velocity(v, baseline_vph)
        snapshots.save_video_snapshot(
            channel_snapshot_id=ch_snap_id,
            video_id=v.video_id,
            title=v.title,
            published_at=v.published_at,
            view_count=v.view_count,
            like_count=v.like_count,
            comment_count=v.comment_count,
            views_per_hour=vel["vph"],
            viral_score=vel["score"],
            is_early_viral=vel["is_early_viral"],
        )
        if vel["is_early_viral"]:
            early_viral_videos.append((v, vel))

    # 6. Detect events
    events = _detect_events(
        wl, ch, channel, videos, early_viral_videos,
        captured_at, baseline_vph, log_fn,
    )
    return events


def _detect_events(wl, ch, channel, videos, early_viral_videos,
                   captured_at, baseline_vph, log_fn) -> list:
    """Phát hiện sự kiện bằng cách so sánh với snapshot trước."""
    events = []

    # Lấy snapshot trước (cùng watchlist + channel)
    prev = snapshots.get_channel_snapshot_before(
        wl.id, channel.channel_id, captured_at)

    # --- Event 1: Subs spike/drop ---
    if prev:
        prev_subs = prev["subscriber_count"] or 0
        cur_subs = channel.subscriber_count or 0
        if prev_subs > 0:
            delta_pct = (cur_subs - prev_subs) / prev_subs * 100
            delta_abs = cur_subs - prev_subs
            if delta_pct >= SUBS_SPIKE_HIGH_PCT:
                events.append(_save_event(
                    wl.id, "subs_spike", "high",
                    f"🚀 {channel.title}: tăng vọt +{delta_abs:,} subs "
                    f"(+{delta_pct:.1f}%)",
                    f"Subscribers tăng nhanh từ {prev_subs:,} → "
                    f"{cur_subs:,} so với lần đo trước "
                    f"({prev['captured_at']})",
                    channel_id=channel.channel_id,
                    channel_title=channel.title,
                    data={"prev_subs": prev_subs, "cur_subs": cur_subs,
                          "delta_pct": delta_pct},
                    detected_at=captured_at,
                ))
            elif delta_pct >= SUBS_SPIKE_MED_PCT:
                events.append(_save_event(
                    wl.id, "subs_spike", "medium",
                    f"📈 {channel.title}: tăng +{delta_abs:,} subs "
                    f"(+{delta_pct:.1f}%)",
                    f"Subscribers tăng từ {prev_subs:,} → {cur_subs:,}",
                    channel_id=channel.channel_id,
                    channel_title=channel.title,
                    data={"prev_subs": prev_subs, "cur_subs": cur_subs,
                          "delta_pct": delta_pct},
                    detected_at=captured_at,
                ))
            elif delta_pct <= SUBS_DROP_PCT:
                events.append(_save_event(
                    wl.id, "subs_drop", "medium",
                    f"📉 {channel.title}: giảm {delta_abs:,} subs "
                    f"({delta_pct:.1f}%)",
                    f"Subscribers giảm từ {prev_subs:,} → {cur_subs:,}",
                    channel_id=channel.channel_id,
                    channel_title=channel.title,
                    data={"prev_subs": prev_subs, "cur_subs": cur_subs,
                          "delta_pct": delta_pct},
                    detected_at=captured_at,
                ))

        # --- Event 2: Vượt mốc subs (100K, 1M, 10M...) ---
        milestone = _detect_milestone(prev_subs, channel.subscriber_count)
        if milestone:
            events.append(_save_event(
                wl.id, "milestone", "medium",
                f"🎉 {channel.title} vừa vượt mốc "
                f"{_format_int(milestone)} subs",
                f"Kênh vừa vượt qua mốc {milestone:,} subscribers",
                channel_id=channel.channel_id,
                channel_title=channel.title,
                data={"milestone": milestone,
                      "cur_subs": channel.subscriber_count},
                detected_at=captured_at,
            ))

        # --- Event 3: New uploads ---
        # Get previous video ids
        prev_video_ids = set()
        with snapshots._DB_LOCK:
            conn = snapshots._connect()
            try:
                rows = conn.execute("""
                    SELECT v.video_id FROM video_snapshots v
                    WHERE v.channel_snapshot_id=?
                """, (prev["id"],)).fetchall()
                prev_video_ids = {r["video_id"] for r in rows}
            finally:
                conn.close()

        cur_video_ids = {v.video_id for v in videos}
        new_uploads = [v for v in videos
                       if v.video_id not in prev_video_ids]
        if new_uploads:
            # Sort theo published, mới nhất trước
            new_uploads.sort(
                key=lambda v: v.published_at or "", reverse=True)
            # Single event tóm tắt tất cả upload mới
            top = new_uploads[0]
            extra = f" (và {len(new_uploads)-1} video khác)" \
                if len(new_uploads) > 1 else ""
            events.append(_save_event(
                wl.id, "new_upload", "low",
                f"🆕 {channel.title} vừa đăng video mới: "
                f"'{top.title[:60]}'{extra}",
                f"Phát hiện {len(new_uploads)} video mới được đăng kể từ "
                f"lần đo trước ({prev['captured_at']})",
                channel_id=channel.channel_id,
                channel_title=channel.title,
                video_id=top.video_id,
                data={"new_count": len(new_uploads),
                      "videos": [
                          {"video_id": v.video_id, "title": v.title,
                           "views": v.view_count}
                          for v in new_uploads[:10]
                      ]},
                detected_at=captured_at,
            ))

    # --- Event 4: Phát hiện video đang viral sớm ---
    # Dedup: skip nếu video đã có early_viral event trong 48h qua
    recent_early_viral_video_ids = set()
    try:
        recent = snapshots.list_events(
            watchlist_id=wl.id, days_back=2)
        for ev in recent:
            if ev["event_type"] == "early_viral" and ev.get("video_id"):
                recent_early_viral_video_ids.add(ev["video_id"])
    except Exception:
        pass

    for v, vel in early_viral_videos:
        if v.video_id in recent_early_viral_video_ids:
            continue  # đã báo trong 48h qua, skip
        events.append(_save_event(
            wl.id, "early_viral", "high",
            f"🔥 {channel.title}: '{v.title[:60]}' "
            f"đang chạy gấp {vel['score']:.1f} lần mức trung bình kênh",
            f"Video mới ({v.days_old:.1f} ngày tuổi) đang chạy "
            f"{vel['vph']:.0f} views/giờ, gấp {vel['score']:.1f} lần "
            f"mức trung bình của kênh ({baseline_vph:.0f} views/giờ). "
            f"Hiện đã có {v.view_count:,} views.",
            channel_id=channel.channel_id,
            channel_title=channel.title,
            video_id=v.video_id,
            data={
                "title": v.title,
                "views": v.view_count,
                "vph": vel["vph"],
                "score": vel["score"],
                "days_old": v.days_old,
                "baseline_vph": baseline_vph,
                "url": v.url,
            },
            detected_at=captured_at,
        ))

    # --- Event 5: Video cũ đột ngột tăng tốc views ---
    # So sánh views_per_hour hiện tại vs snapshot trước cho từng video
    if prev:
        for v in videos:
            prev_vid = snapshots.get_previous_video_snapshot(
                v.video_id, captured_at)
            if not prev_vid:
                continue
            prev_views = prev_vid["view_count"] or 0
            cur_views = v.view_count
            if prev_views <= 0:
                continue
            try:
                prev_time = datetime.fromisoformat(
                    prev_vid["snapshot_time"])
                cur_time = datetime.fromisoformat(captured_at)
                hours_between = max(
                    1, (cur_time - prev_time).total_seconds() / 3600)
            except Exception:
                continue
            delta_vph = (cur_views - prev_views) / hours_between
            prev_vph_stored = prev_vid["views_per_hour"] or 0
            # Surge nếu delta vph > 5× vph trước đó (đang tăng tốc)
            # và delta_views >= 5000 (tránh noise với video nhỏ)
            if (prev_vph_stored > 0
                    and delta_vph > VELOCITY_SURGE_MULTIPLIER * prev_vph_stored
                    and (cur_views - prev_views) >= 5000):
                events.append(_save_event(
                    wl.id, "velocity_surge", "high",
                    f"⚡ {channel.title}: '{v.title[:55]}' "
                    f"đột ngột tăng tốc {delta_vph:.0f} views/giờ",
                    f"Tăng thêm {cur_views - prev_views:,} views trong "
                    f"{hours_between:.1f} giờ qua "
                    f"({delta_vph:.0f} views/giờ, so với trước đó chỉ "
                    f"{prev_vph_stored:.0f} views/giờ)",
                    channel_id=channel.channel_id,
                    channel_title=channel.title,
                    video_id=v.video_id,
                    data={
                        "title": v.title,
                        "prev_views": prev_views,
                        "cur_views": cur_views,
                        "delta_vph": delta_vph,
                        "prev_vph": prev_vph_stored,
                        "hours_between": hours_between,
                        "url": v.url,
                    },
                    detected_at=captured_at,
                ))

    return events


def detect_events_from_research_result(
    watchlist_id: str, result: dict,
    captured_at: str = "") -> list:
    """
    Sau khi 1 research job xong (queue), gọi hàm này để:
      1. Trích channel + videos từ result
      2. Lưu snapshot vào SQLite
      3. So sánh với snapshot trước để phát hiện sự kiện
      4. Trả về list events đã detect (và lưu vào DB)

    Dùng khi GUI chạy "Monitor ngay" qua queue mode.
    """
    from . import watchlist as wl_mod
    if not captured_at:
        captured_at = datetime.now().isoformat(timespec="seconds")

    channel_obj = result.get("channel")
    videos = result.get("videos") or []
    if not channel_obj or not channel_obj.channel_id:
        return []

    # Tìm WatchedChannel tương ứng để lấy is_self flag
    wl = wl_mod.load_watchlist(watchlist_id)
    if not wl:
        return []
    is_self = False
    matching_ch = None
    for c in wl.channels:
        if c.channel_id == channel_obj.channel_id:
            is_self = c.is_self
            matching_ch = c
            break
    if not matching_ch:
        # Channel không có trong watchlist nữa (đã xoá) → skip
        return []

    # Baseline vph từ videos cũ
    baseline_vph = _compute_baseline_vph(videos)

    # Lưu channel snapshot
    vid_count = channel_obj.video_count or len(videos)
    ch_snap_id = snapshots.save_channel_snapshot(
        watchlist_id=watchlist_id,
        channel_id=channel_obj.channel_id,
        channel_title=channel_obj.title,
        is_self=is_self,
        subscriber_count=channel_obj.subscriber_count,
        video_count=vid_count,
        view_count=channel_obj.view_count,
        captured_at=captured_at,
    )

    # Lưu video snapshots + tính velocity
    early_viral_videos = []
    for v in videos:
        vel = _compute_video_velocity(v, baseline_vph)
        snapshots.save_video_snapshot(
            channel_snapshot_id=ch_snap_id,
            video_id=v.video_id,
            title=v.title,
            published_at=v.published_at,
            view_count=v.view_count,
            like_count=v.like_count,
            comment_count=v.comment_count,
            views_per_hour=vel["vph"],
            viral_score=vel["score"],
            is_early_viral=vel["is_early_viral"],
        )
        if vel["is_early_viral"]:
            early_viral_videos.append((v, vel))

    # Detect events
    events = _detect_events(
        wl, matching_ch, channel_obj, videos, early_viral_videos,
        captured_at, baseline_vph, log_fn=lambda m: None,
    )
    return events


def _save_event(wl_id, event_type, severity, title, desc, **kw):
    """Lưu event xuống DB và trả về dict để aggregate."""
    eid = snapshots.save_event(
        watchlist_id=wl_id,
        event_type=event_type,
        title=title,
        description=desc,
        severity=severity,
        **kw,
    )
    return {
        "id": eid,
        "event_type": event_type,
        "severity": severity,
        "title": title,
        "description": desc,
        **kw,
    }
