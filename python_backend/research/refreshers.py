# -*- coding: utf-8 -*-
"""Refresh Social Blade + Google Trends cho các pkl đã save.

Đây là CORE library — đóng gói được vào file .exe nhân viên. Các tool CLI
trong tools/ chỉ là thin wrapper gọi 2 hàm chính ở đây:
  - refresh_socialblade_for_watchlist(wid, delay_sec=3.0)
  - refresh_trends_for_watchlist(wid, delay_sec=4.0)

Cả 2 hàm đều idempotent — skip kênh/keyword đã có data. Cache 6h (SB) +
24h (Trends) built-in trong core/socialblade.py + core/trends.py.
"""
from __future__ import annotations

import os
import pickle
import time


# ============================================================
# Social Blade
# ============================================================

def _get_latest_channel_pkl(channel_id, persistence):
    """Trả đường dẫn pkl mới nhất của 1 kênh, hoặc None."""
    idx = persistence._load_index()
    recs = sorted([e for e in idx if e.get("channel_id") == channel_id
                   and e.get("type") == "channel"],
                  key=lambda e: e["id"], reverse=True)
    return recs[0]["pkl_path"] if recs else None


def _channels_missing_sb(wl, persistence):
    """Trả list (channel_id, title, pkl_path) cho các kênh có pkl mới nhất
    nhưng SocialBlade đang None hoặc có error. Bỏ qua kênh có channel_id
    placeholder (@handle - chưa monitor lần đầu)."""
    out = []
    for c in wl.channels:
        if not c.channel_id or not c.channel_id.startswith("UC"):
            continue
        pkl_path = _get_latest_channel_pkl(c.channel_id, persistence)
        if not pkl_path or not os.path.exists(pkl_path):
            continue
        try:
            with open(pkl_path, "rb") as f:
                r = pickle.load(f)
        except Exception:
            continue
        sb = r.get("socialblade")
        # 21/05 fix: cũng coi là "missing" nếu sb dict có daily_stats rỗng
        # (xảy ra khi cào lần đầu monitor_batch chưa enrich SB → sb được
        # tạo placeholder {error: "", daily_stats: []} → trước đây bị skip).
        if sb is None:
            out.append((c.channel_id, c.title, pkl_path))
        elif isinstance(sb, dict) and sb.get("error"):
            out.append((c.channel_id, c.title, pkl_path))
        elif isinstance(sb, dict) and not (sb.get("daily_stats") or []):
            out.append((c.channel_id, c.title, pkl_path))
    return out


def _fill_sb_in_pkl(pkl_path, sb_data):
    """Ghi sb_data vào res['socialblade']. Dùng pkl_io.safe_update để tránh
    race condition khi pipeline parallel."""
    from .pkl_io import safe_update

    def _patch(data):
        data["socialblade"] = sb_data
    return safe_update(pkl_path, _patch)


def refresh_socialblade_for_watchlist(wid, delay_sec=3.0, log_fn=print,
                                       force=False):
    """Refresh SocialBlade cho 1 watchlist. Trả tuple (n_total, n_cache,
    n_fetched, n_error, elapsed_sec).

    Args:
        force: True → bỏ qua check 'đã có SB', fetch lại TẤT CẢ kênh
            (data fresh — dùng cho daily run khi user yêu cầu mới
            hoàn toàn, không dùng cache cũ).
    """
    from . import watchlist as wl_mod, persistence
    from . import socialblade as sb_mod

    wl = wl_mod.load_watchlist(wid)
    if not wl:
        log_fn(f"  ! Khong tim thay watchlist {wid}")
        return None

    log_fn(f"\n=== Refresh SocialBlade: {wl.name} ({wid})"
           f"{' [FORCE]' if force else ''} ===")

    # Quy trình mới 26/05: kênh chính dùng Inside (YouTube Analytics API)
    # thay SB. Stage SB chỉ chạy cho ĐỐI THỦ. Skip self_channel khỏi list.
    self_cid = (wl.self_channel.channel_id
                if wl.self_channel else None)

    if force:
        # Build list tất cả channel có pkl mới nhất (bypass missing check)
        missing = []
        for c in wl.channels:
            if not c.channel_id or not c.channel_id.startswith("UC"):
                continue
            if self_cid and c.channel_id == self_cid:
                continue  # skip self → Inside-first
            pkl_path = _get_latest_channel_pkl(c.channel_id, persistence)
            if not pkl_path or not os.path.exists(pkl_path):
                continue
            missing.append((c.channel_id, c.title, pkl_path))
        log_fn(f"  FORCE: fetch lại tất cả {len(missing)} kênh đối thủ "
               f"(bỏ cache, skip self)")
        # Clear cache file để bắt buộc fetch web
        for cid, _, _ in missing:
            try:
                cache_p = sb_mod._cache_path(cid)
                if cache_p.exists():
                    cache_p.unlink()
            except Exception:
                pass
    else:
        missing = _channels_missing_sb(wl, persistence)
        # Skip self khỏi missing list nếu có
        if self_cid:
            missing = [m for m in missing if m[0] != self_cid]
        if not missing:
            log_fn(f"  Tat ca {len(wl.channels)-1} kenh doi thu da co SB "
                   f"(skip self) - bo qua.")
            return (len(wl.channels), 0, 0, 0, 0)

    log_fn(f"  Can fill: {len(missing)} kenh")

    t0 = time.time()
    n_cache = 0
    n_fetched = 0
    n_error = 0
    consecutive_errors = 0
    EARLY_STOP = 8
    early_stopped = False

    for i, (cid, ctitle, pkl_path) in enumerate(missing, 1):
        cached = sb_mod._load_cache(cid)
        if cached:
            _fill_sb_in_pkl(pkl_path, cached)
            n_cache += 1
            consecutive_errors = 0
            log_fn(f"  ({i}/{len(missing)}) [CACHE] {ctitle}")
            continue

        sb_data = sb_mod.get_channel_growth(cid)
        err = (sb_data or {}).get("error", "")
        if err:
            n_error += 1
            consecutive_errors += 1
            _fill_sb_in_pkl(pkl_path, sb_data)
            log_fn(f"  ({i}/{len(missing)}) [ERR{consecutive_errors}] "
                   f"{ctitle}: {err[:60]}")
            if consecutive_errors >= EARLY_STOP:
                log_fn(f"\n  !! {EARLY_STOP} kenh loi lien tiep - IP co "
                       f"the bi ban. DUNG som.")
                early_stopped = True
                break
        else:
            n_fetched += 1
            consecutive_errors = 0
            _fill_sb_in_pkl(pkl_path, sb_data)
            days = (sb_data.get("summary") or {}).get("total_days", 0)
            log_fn(f"  ({i}/{len(missing)}) [OK] {ctitle}: {days} days")

        if i < len(missing):
            time.sleep(delay_sec)

    elapsed = time.time() - t0
    status = "DUNG SOM" if early_stopped else "XONG"
    log_fn(f"=== {status} {wl.name}: cache={n_cache}, fetch={n_fetched}, "
           f"err={n_error}, {elapsed:.0f}s ===")
    return (len(missing), n_cache, n_fetched, n_error, elapsed)


# ============================================================
# Google Trends
# ============================================================

def _channels_missing_trend(wl, persistence):
    """Trả list (channel_id, title, pkl_path, set(missing_keywords)) cho
    các kênh có pkl mới nhất nhưng trend cho 1 số keyword đang None/error."""
    out = []
    for c in wl.channels:
        pkl_path = _get_latest_channel_pkl(c.channel_id, persistence)
        if not pkl_path or not os.path.exists(pkl_path):
            continue
        try:
            with open(pkl_path, "rb") as f:
                r = pickle.load(f)
        except Exception:
            continue
        per = (r.get("tag_metrics") or {}).get("per_keyword") or {}
        missing = set()
        for kw, m in per.items():
            tr = m.get("trend")
            if tr is None:
                missing.add(kw)
            elif isinstance(tr, dict) and tr.get("error"):
                missing.add(kw)
        if missing:
            out.append((c.channel_id, c.title, pkl_path, missing))
    return out


def _fill_trend_in_pkl(pkl_path, trend_map):
    """Ghi trend vào per_keyword[kw]['trend']. Trả số keyword đã fill."""
    from .pkl_io import safe_update

    counter = {"n": 0}

    def _patch(data):
        tm = data.get("tag_metrics") or {}
        per = tm.get("per_keyword") or {}
        for kw, td in trend_map.items():
            if kw in per:
                per[kw]["trend"] = td
                counter["n"] += 1
        tm["per_keyword"] = per
        data["tag_metrics"] = tm

    if safe_update(pkl_path, _patch):
        return counter["n"]
    return 0


def _rotate_vpn_for_fresh_ip(log_fn):
    """Đổi IP qua Cloudflare WARP - mỗi lần connect cho IP Cloudflare mới.
    Trả True nếu đổi được, False nếu WARP không khả dụng."""
    try:
        from . import warp
    except ImportError:
        return False
    if not warp.is_available():
        log_fn("    [VPN] Cloudflare WARP khong cai - khong rotate duoc")
        return False
    try:
        if warp.is_connected():
            log_fn("    [VPN] Disconnect WARP de doi IP...")
            warp.disconnect()
            time.sleep(2)
        log_fn("    [VPN] Connect WARP voi IP moi...")
        if warp.connect(wait_sec=15):
            time.sleep(3)  # Đợi mạng ổn định
            new_ip = warp.current_ip()
            log_fn(f"    [VPN] OK - IP moi: {new_ip}")
            return True
        log_fn("    [VPN] Connect FAIL")
        return False
    except Exception as e:
        log_fn(f"    [VPN] LOI rotate: {e}")
        return False


def refresh_trends_for_watchlist(wid, delay_sec=5.0, log_fn=print,
                                 max_rotations=0, force=False):
    """Refresh Google Trends cho 1 watchlist.

    Quan trọng: Google Trends rate limit per-IP rất nhạy. Khi gặp nhiều 429
    liên tiếp, hàm này TỰ ĐỘNG bật Cloudflare WARP + rotate IP để tiếp tục
    cào. WARP CHỈ BẬT KHI CẦN (lazy) — không bật ngay đầu function. Sau
    khi function kết thúc, nếu WARP được bật ở đây (không phải user bật
    sẵn) → tự DISCONNECT để trả về IP nhà.

    Args:
        delay_sec: delay giữa keyword (mặc định 5s)
        max_rotations: số lần tối đa rotate VPN
        force: True → bỏ qua check 'đã có trend', fetch lại TẤT CẢ keyword
            (data fresh — dùng cho daily run khi user yêu cầu mới).

    Trả tuple (n_channels, n_keywords_unique, n_fetched, n_filled, elapsed)."""
    from . import watchlist as wl_mod, persistence
    from . import trends as trends_mod

    # Ghi nhớ trạng thái WARP ban đầu để biết có cần disconnect cuối hay không
    warp_was_off_initially = True
    try:
        from . import warp
        if warp.is_available():
            warp_was_off_initially = not warp.is_connected()
    except Exception:
        pass

    wl = wl_mod.load_watchlist(wid)
    if not wl:
        log_fn(f"  ! Khong tim thay watchlist {wid}")
        return None

    log_fn(f"\n=== Refresh trend: {wl.name} ({wid}) ===")

    missing_per_channel = _channels_missing_trend(wl, persistence)

    if force:
        # Lấy TẤT CẢ channel + keywords (không filter missing)
        from . import trends as trends_mod
        import pickle as _pickle
        all_channels = []
        for c in wl.channels:
            if not c.channel_id or not c.channel_id.startswith("UC"):
                continue
            pkl_path = _get_latest_channel_pkl(c.channel_id, persistence)
            if not pkl_path or not os.path.exists(pkl_path):
                continue
            try:
                with open(pkl_path, "rb") as f:
                    r = _pickle.load(f)
                kws = set()
                for kw_obj in (r.get("keywords") or [])[:15]:
                    kw_text = (kw_obj.keyword
                               if hasattr(kw_obj, "keyword")
                               else str(kw_obj))
                    if kw_text:
                        kws.add(kw_text)
                if kws:
                    all_channels.append((c.channel_id, c.title, pkl_path, kws))
            except Exception:
                continue
        missing_per_channel = all_channels
        # Clear trend cache để force fetch
        all_kw_clear = set()
        for _, _, _, kws in all_channels:
            all_kw_clear |= kws
        for kw in all_kw_clear:
            try:
                cp = trends_mod._cache_path(kw)
                if cp.exists():
                    cp.unlink()
            except Exception:
                pass
        log_fn(f"  FORCE: clear cache + fetch lại "
               f"{len(missing_per_channel)} kênh × {len(all_kw_clear)} kw")
    elif not missing_per_channel:
        log_fn(f"  Tat ca {len(wl.channels)} kenh da co trend - bo qua.")
        return (len(wl.channels), 0, 0, 0, 0)

    all_kw = set()
    for _, _, _, kws in missing_per_channel:
        all_kw |= kws
    all_kw_list = sorted(all_kw)

    log_fn(f"  Can fill: {len(missing_per_channel)} kenh, "
           f"{len(all_kw_list)} keyword unique")

    t0 = time.time()
    n_from_cache = 0
    n_fetched = 0
    n_error = 0
    consecutive_errors = 0
    ROTATE_THRESHOLD = 5   # 5 lỗi liên tiếp → rotate VPN
    rotations_done = 0
    trend_map = {}
    early_stopped = False

    for i, kw in enumerate(all_kw_list, 1):
        cached = trends_mod._load_cache(kw)
        if cached:
            trend_map[kw] = cached
            n_from_cache += 1
            consecutive_errors = 0
            log_fn(f"  ({i}/{len(all_kw_list)}) [CACHE] {kw}")
            continue

        td = trends_mod.get_trend(kw)
        trend_map[kw] = td

        # Phân loại lỗi: 429 → có thể fix bằng rotate IP. "no data" → không fix.
        err = td.get("error", "")
        is_rate_limit = "429" in err or "Too Many" in err

        if err:
            n_error += 1
            if is_rate_limit:
                consecutive_errors += 1
            log_fn(f"  ({i}/{len(all_kw_list)}) [ERR{consecutive_errors}] "
                   f"{kw} -> {err[:60]}")

            # Khi 5 lỗi 429 liên tiếp + còn rotate được → đổi VPN
            if (consecutive_errors >= ROTATE_THRESHOLD
                    and rotations_done < max_rotations):
                rotations_done += 1
                log_fn(f"\n  !! {ROTATE_THRESHOLD} loi lien tiep - rotate "
                       f"VPN lan {rotations_done}/{max_rotations}...")
                if _rotate_vpn_for_fresh_ip(log_fn):
                    consecutive_errors = 0
                    time.sleep(2)
                    # Retry keyword này sau khi rotate
                    log_fn(f"    Retry sau rotate...")
                    td = trends_mod.get_trend(kw)
                    trend_map[kw] = td
                    if not td.get("error"):
                        n_fetched += 1
                        n_error -= 1  # Sửa lại đếm
                        log_fn(f"    Retry OK score={td.get('score',0)}")
                    else:
                        log_fn(f"    Retry van loi: "
                               f"{td.get('error','')[:50]}")
                else:
                    # Rotate fail → chịu, dừng sớm
                    log_fn(f"  !! Rotate VPN fail, DUNG som.")
                    early_stopped = True
                    break
            elif (consecutive_errors >= ROTATE_THRESHOLD
                    and rotations_done >= max_rotations):
                log_fn(f"\n  !! Da rotate VPN {max_rotations} lan ma van "
                       f"bi 429 - DUNG som.")
                early_stopped = True
                break
        else:
            n_fetched += 1
            consecutive_errors = 0
            log_fn(f"  ({i}/{len(all_kw_list)}) [OK] {kw} "
                   f"score={td.get('score',0)} dir={td.get('direction','')}")

        if i < len(all_kw_list):
            time.sleep(delay_sec)

    # Ghi vào pkl mỗi kênh
    n_filled_total = 0
    for cid, ctitle, pkl_path, kws in missing_per_channel:
        sub_map = {kw: trend_map[kw] for kw in kws if kw in trend_map}
        n = _fill_trend_in_pkl(pkl_path, sub_map)
        n_filled_total += n
        log_fn(f"    Ghi {n}/{len(kws)} trend -> {ctitle}")

    elapsed = time.time() - t0
    status = "DUNG SOM" if early_stopped else "XONG"
    log_fn(f"=== {status} {wl.name}: cache={n_from_cache}, fetch={n_fetched}, "
           f"err={n_error}, rotate={rotations_done}, filled={n_filled_total}, "
           f"{elapsed:.0f}s ===")

    # Cleanup: nếu function này đã bật WARP (qua rotate) mà ban đầu WARP
    # đang tắt → tự DISCONNECT để trả IP nhà. Tôn trọng nếu user bật sẵn.
    if warp_was_off_initially and rotations_done > 0:
        try:
            from . import warp
            if warp.is_connected():
                log_fn("  [WARP] Tu disconnect (tra IP nha)...")
                warp.disconnect()
                log_fn(f"  [WARP] IP hien tai: {warp.current_ip()}")
        except Exception as e:
            log_fn(f"  [WARP] disconnect loi: {e}")

    return (len(missing_per_channel), len(all_kw_list), n_fetched,
            n_filled_total, elapsed)
