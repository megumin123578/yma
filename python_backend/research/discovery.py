"""
Discovery - tự phát hiện & kết nạp kênh đối thủ mới.

Sau mỗi lần giám sát, quét các kênh xuất hiện trong kết quả tìm kiếm
ngách của kênh chính. Kênh nào có vốn từ (chủ đề) trùng với kênh chính
đủ cao thì tự thêm vào danh sách theo dõi + nghiên cứu đầy đủ ngay.

Quy trình 2 bước cho mỗi kênh ứng viên:
  1. Quét NHẸ (resolve + lấy ~25 video) → so khớp từ khoá nhanh.
  2. Kênh đạt ngưỡng → nghiên cứu ĐẦY ĐỦ (run_research) + thêm vào
     watchlist.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Callable, Optional


# Từ dừng: chỉ loại từ ngữ pháp / quá chung. GIỮ các từ ngách
# (tractor, mini, diy, construction...) vì đó chính là tín hiệu chủ đề.
_STOP = {
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for",
    "with", "from", "by", "is", "are", "was", "this", "that", "it", "as",
    "my", "your", "our", "his", "her", "you", "we", "they", "i",
    "how", "what", "when", "why", "who", "new", "best", "top", "all",
    "video", "videos", "youtube", "shorts", "short", "full", "part",
    "episode", "ep", "vs", "ft", "feat", "official", "channel",
    "make", "making", "made", "build", "builds",
    "va", "cua", "cho", "mot", "cac", "nhat", "nhung", "trong", "voi",
}


def _words(text: str) -> set:
    """Tách tập từ có nghĩa từ 1 chuỗi (chữ thường, bỏ từ dừng/số)."""
    out = set()
    for w in re.split(r"[^\w]+", (text or "").lower(), flags=re.UNICODE):
        if len(w) >= 3 and w not in _STOP and not w.isdigit():
            out.add(w)
    return out


def _video_word_counter(videos) -> Counter:
    """Đếm tần suất từ trong tiêu đề các video."""
    c = Counter()
    for v in videos or []:
        for w in _words(getattr(v, "title", "")):
            c[w] += 1
    return c


def _main_vocabulary(main_result: dict) -> set:
    """Vốn từ chủ đề của kênh chính (từ tiêu đề video + từ khoá)."""
    vocab = set(_video_word_counter(main_result.get("videos") or []))
    ch = main_result.get("channel")
    for kw in (getattr(ch, "keywords", None) or []):
        vocab |= _words(kw)
    for k in (main_result.get("keywords") or []):
        vocab |= _words(getattr(k, "keyword", str(k)))
    return vocab


def collect_candidates(main_result: dict, watchlist,
                       top_per_keyword: int = 5,
                       min_keywords: int = 2) -> list:
    """Gom kênh ứng viên từ các VIDEO NHIỀU LƯỢT XEM NHẤT trong kết quả
    tìm kiếm ngách (đúng tab 'Video mới nhiều lượt xem').

    Chỉ xét top `top_per_keyword` video (theo lượt xem) của mỗi từ khoá
    — tức chỉ những kênh thực sự CÓ video nổi bật trong ngách.

    min_keywords: kênh phải lọt top video nhiều view ở ÍT NHẤT bấy
    nhiêu từ khoá khác nhau mới tính là ứng viên — lọc bỏ kênh chỉ xuất
    hiện 1 lần kiểu ăn may (thường là kênh NGOÀI ngách lọt vào do trùng
    từ khoá chung chung), đỡ tốn thời gian quét vô ích.

    Trả list dict {channel_id, title, url, freq, best_views} — xếp theo
    lượt xem video tốt nhất giảm dần (kênh mạnh lên đầu).
    """
    exclude = {c.channel_id for c in watchlist.channels if c.channel_id}
    main_ch = main_result.get("channel")
    if main_ch and getattr(main_ch, "channel_id", ""):
        exclude.add(main_ch.channel_id)

    freq = {}          # cid -> số từ khoá kênh lọt top
    best_views = {}    # cid -> lượt xem video cao nhất
    info = {}          # cid -> title
    for _kw, vids in (main_result.get("recent_by_keyword") or {}).items():
        top = sorted(vids,
                     key=lambda v: getattr(v, "view_count", 0) or 0,
                     reverse=True)[:top_per_keyword]
        seen = set()
        for v in top:
            cid = getattr(v, "channel_id", "") or ""
            if not cid or cid in exclude or cid in seen:
                continue
            seen.add(cid)
            freq[cid] = freq.get(cid, 0) + 1
            vc = getattr(v, "view_count", 0) or 0
            if vc > best_views.get(cid, 0):
                best_views[cid] = vc
            if cid not in info:
                info[cid] = getattr(v, "channel_title", "") or cid
    out = [{
        "channel_id": cid,
        "title": title,
        "url": f"https://www.youtube.com/channel/{cid}",
        "freq": freq.get(cid, 0),
        "best_views": best_views.get(cid, 0),
    } for cid, title in info.items()
        if freq.get(cid, 0) >= min_keywords]
    out.sort(key=lambda d: (d["best_views"], d["freq"]), reverse=True)
    return out


def _scan_channel_light(client, channel_id: str, log_fn) -> tuple:
    """Quét nhẹ 1 kênh: resolve + lấy ~25 video. Trả (channel, videos)."""
    from .youtube_client import parse_channel_url
    try:
        parsed = parse_channel_url(
            f"https://www.youtube.com/channel/{channel_id}")
        ch = client.resolve_channel(parsed)
        if not ch:
            return None, []
        vids = client.list_channel_videos(ch, limit=25)
        return ch, vids
    except Exception as e:
        log_fn(f"      quét nhẹ lỗi: {e}")
        return None, []


def _main_core(main_result: dict) -> set:
    """Vốn từ NGÁCH CỐT LÕI của kênh chính: token 12 từ khoá NỔI BẬT
    NHẤT (yake xếp hạng giảm dần), BỎ token tên kênh. Đây là chữ ký
    ngách SẠCH nhất — đối thủ cùng ngách phủ phần lớn tập này dù tiêu
    đề video dùng từ ngữ khác nhau (vd nhạc thiếu nhi: mỗi bài 1 tên).

    KHÔNG gộp toàn bộ từ khoá / từ tiêu đề — vì chúng lẫn nhiều chủ đề
    RIÊNG của kênh (tên bài hát, sự kiện...) làm loãng tín hiệu ngách."""
    ch = main_result.get("channel")
    name_tok = _words(main_result.get("channel_title")
                      or getattr(ch, "title", "") or "")
    core = set()
    for k in (main_result.get("keywords") or [])[:12]:
        core |= _words(getattr(k, "keyword", str(k)))
    if not core:  # fallback: từ khoá khai báo của kênh
        for kw in (getattr(ch, "keywords", None) or [])[:12]:
            core |= _words(kw)
    return core - name_tok


def _overlap_pct(main_vocab: set, cand_videos: list,
                 main_core: set = None) -> float:
    """Điểm CÙNG NGÁCH (0-100). Lấy MAX 2 chiều — tránh phạt oan kênh
    đối thủ có tiêu đề đa dạng (vd nhạc thiếu nhi: mỗi bài 1 tên riêng
    nên ít từ lặp, nhưng vẫn cùng ngách):

      - Chiều ĐỐI THỦ: % từ tín hiệu của đối thủ nằm trong vốn từ kênh
        chính (đối thủ chuyên ngách hẹp → điểm cao).
      - Chiều KÊNH CHÍNH: % vốn từ ngách CỐT LÕI của kênh chính mà đối
        thủ phủ được (overlap coefficient — chia cho tập nhỏ hơn). Bắt
        được đối thủ lớn nội dung đa dạng nhưng phủ trọn ngách của ta.
    """
    counter = _video_word_counter(cand_videos)
    cand_top = {w for w, _ in counter.most_common(40)}
    if not cand_top:
        return 0.0
    pct_cand = len(cand_top & main_vocab) / len(cand_top) * 100.0
    pct_main = 0.0
    if main_core:
        denom = min(len(cand_top), len(main_core))
        if denom:
            pct_main = len(cand_top & main_core) / denom * 100.0
    return max(pct_cand, pct_main)


def discover_and_recruit(
    watchlist_id: str, main_result: dict, output_dir: str,
    chrome_mode: str = "headless",
    threshold_pct: float = 60.0, max_add: int = 5, max_scan: int = 10,
    days: int = 7, top_keywords: int = 20, per_keyword: int = 10,
    max_channel_videos: int = 30, region: Optional[str] = None,
    log_fn: Callable[[str], None] = print,
    cancel_event=None,
) -> dict:
    """Phát hiện + kết nạp đối thủ mới cho 1 watchlist.

    Trả dict {added: [{channel_id, title, overlap_pct}], scanned: int,
    candidates: int}.
    """
    from . import watchlist as wl_mod
    from .youtube_client import PlaywrightBackend
    from .researcher import run_research, safe_filename
    from .persistence import save_result, find_previous_for_channel
    from .delta import compute_delta
    from . import monitor as monitor_mod
    from pathlib import Path

    def _cancelled():
        return cancel_event is not None and cancel_event.is_set()

    wl = wl_mod.load_watchlist(watchlist_id)
    if not wl:
        return {"added": [], "scanned": 0, "candidates": 0}

    candidates = collect_candidates(main_result, wl)
    if not candidates:
        log_fn("  Không có kênh ứng viên mới trong kết quả ngách.")
        return {"added": [], "scanned": 0, "candidates": 0}

    main_vocab = _main_vocabulary(main_result)
    main_core = _main_core(main_result)
    log_fn(f"  Tìm thấy {len(candidates)} kênh có video nổi bật trong "
           f"ngách (chưa theo dõi). Quét {min(len(candidates), max_scan)} "
           f"kênh nhiều lượt xem nhất (ngưỡng trùng "
           f"{threshold_pct:.0f}%)...")

    # --- Bước 1: quét nhẹ + so khớp ---
    qualified = []
    scanned = 0
    client = PlaywrightBackend(chrome_mode=chrome_mode,
                               log_fn=lambda m: None)
    try:
        for cand in candidates[:max_scan]:
            if _cancelled() or len(qualified) >= max_add:
                break
            scanned += 1
            ch, vids = _scan_channel_light(
                client, cand["channel_id"], log_fn)
            if not vids:
                log_fn(f"    ({scanned}) {cand['title'][:34]}: "
                       f"không quét được, bỏ qua")
                continue
            pct = _overlap_pct(main_vocab, vids, main_core)
            mark = "ĐẠT" if pct >= threshold_pct else "không đạt"
            bv = cand.get("best_views", 0)
            log_fn(f"    ({scanned}) {cand['title'][:30]} "
                   f"(video cao nhất {bv:,} view): trùng {pct:.0f}% "
                   f"— {mark}")
            if pct >= threshold_pct:
                cand["overlap_pct"] = pct
                cand["resolved_title"] = getattr(ch, "title",
                                                 cand["title"])
                qualified.append(cand)
    finally:
        try:
            client.close()
        except Exception:
            pass

    if not qualified:
        log_fn("  Không có kênh nào đạt ngưỡng — không kết nạp kênh "
               "nào lần này.")
        return {"added": [], "scanned": scanned,
                "candidates": len(candidates)}

    # --- Bước 2: nghiên cứu đầy đủ + kết nạp ---
    out_dir = Path(output_dir) if output_dir else Path(".")
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    added = []
    for cand in qualified[:max_add]:
        if _cancelled():
            break
        nm = cand["resolved_title"]
        log_fn(f"  → Kết nạp '{nm}' (trùng {cand['overlap_pct']:.0f}%) "
               f"— đang nghiên cứu đầy đủ...")
        try:
            out_path = str(out_dir / f"doithu_moi_"
                                     f"{safe_filename(nm)}_{ts}.xlsx")
            result = run_research(
                channel_url=cand["url"], output_path=out_path,
                days=days, top_keywords=top_keywords,
                per_keyword=per_keyword,
                max_channel_videos=max_channel_videos,
                chrome_mode=chrome_mode, region=region,
                log_fn=lambda m: None,
                progress_fn=lambda *a: None,
                cancel_event=cancel_event)
        except Exception as e:
            log_fn(f"    ⚠ Nghiên cứu '{nm}' lỗi, bỏ qua: {e}")
            continue

        ch_obj = result.get("channel")
        cid = (getattr(ch_obj, "channel_id", "")
               or cand["channel_id"])
        # Delta (nếu kênh từng được nghiên cứu trước đó)
        try:
            prev = find_previous_for_channel(cid)
            if prev:
                result["delta"] = compute_delta(result, prev)
        except Exception:
            pass
        try:
            save_result(result)
        except Exception as e:
            log_fn(f"    ⚠ Lưu kết quả '{nm}' lỗi: {e}")
        # Thêm vào watchlist (đánh dấu auto_added)
        wc = wl_mod.WatchedChannel(
            channel_id=cid,
            title=getattr(ch_obj, "title", nm),
            url=getattr(ch_obj, "url", cand["url"]),
            is_self=False,
            added_at=datetime.now().isoformat(timespec="seconds"),
            auto_added=True,
            auto_added_pct=round(cand["overlap_pct"], 1))
        if wl_mod.add_channel(watchlist_id, wc):
            try:
                monitor_mod.detect_events_from_research_result(
                    watchlist_id, result)
            except Exception:
                pass
            added.append({"channel_id": cid, "title": wc.title,
                           "overlap_pct": cand["overlap_pct"]})
            log_fn(f"    ✓ Đã kết nạp đối thủ mới: {wc.title}")
        else:
            log_fn(f"    (kênh '{nm}' đã có trong danh sách, bỏ qua)")

    log_fn(f"  Phát hiện đối thủ: quét {scanned} kênh, kết nạp "
           f"{len(added)} kênh mới.")
    return {"added": added, "scanned": scanned,
            "candidates": len(candidates)}
