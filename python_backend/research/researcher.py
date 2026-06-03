"""
Researcher - pipeline nghiên cứu YouTube với callback báo tiến trình.
Sử dụng PlaywrightBackend (browser automation).
"""

from __future__ import annotations

import os
import re
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Callable, Optional

from .youtube_client import (
    PlaywrightBackend, parse_channel_url, ChannelInfo, VideoInfo,
    get_youtube_search_result_count, get_youtube_autosuggest,
)
from .keyword_extractor import extract_keywords, KeywordEntry
from .excel_exporter import build_workbook
from . import trending as trending_mod
from . import trends as trends_mod
from . import tag_analyzer
from . import search_cache


def safe_filename(s: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", s)
    return s.strip("_") or "kenh"


class ResearchCancelled(Exception):
    """Người dùng đã huỷ tác vụ."""
    pass


def _compute_tag_metrics(keywords: list, videos: list, log_fn,
                         progress_fn=None, base_pct: int = 88,
                         cancel_event=None) -> dict:
    """Tính competition + trend + autosuggest cho mỗi từ khoá, và SEO score
    cho video kênh seed. Trả dict 'tag_metrics' để gắn vào result."""
    def _check():
        if cancel_event and cancel_event.is_set():
            raise ResearchCancelled("Cancelled")

    log_fn("📊 Tính chỉ số nâng cao (competition + trends + autosuggest)...")

    per_kw_metrics = {}
    total_kw = len(keywords)
    for i, kw in enumerate(keywords, 1):
        _check()
        keyword_str = kw.keyword if hasattr(kw, "keyword") else str(kw)
        # Competition: check cache trước
        cached_rc = search_cache.get_result_count(keyword_str)
        if cached_rc is not None:
            rc = cached_rc
        else:
            try:
                rc = get_youtube_search_result_count(keyword_str)
                search_cache.set_result_count(keyword_str, rc)
            except Exception:
                rc = 0
        comp = tag_analyzer.classify_competition(rc)
        # Autosuggest - check cache trước
        cached_sugs = search_cache.get_autosuggest(keyword_str)
        if cached_sugs is not None:
            sugs = cached_sugs[:8]
        else:
            try:
                sugs = get_youtube_autosuggest(keyword_str)[:8]
                search_cache.set_autosuggest(keyword_str, sugs)
            except Exception:
                sugs = []
        per_kw_metrics[keyword_str] = {
            "competition": comp,
            "autosuggest": sugs,
        }
        if progress_fn:
            pct = base_pct + int(2 * i / max(total_kw, 1))
            progress_fn(pct, 100, f"Competition: {i}/{total_kw}")

    # Google Trends ĐÃ TÁCH RA `tools/trends_refresh.py` để tránh HTTP 429
    # khi cào song song nhiều luồng. Pkl KHÔNG ĐẶT key "trend" ở đây, sau
    # khi monitor xong gọi tools/trends_refresh.py <wid> để fill trend
    # (1 worker, delay 4s/keyword, cache 24h chia sẻ giữa các kênh cùng ngách).
    # KHÔNG đặt trend=None vì các chỗ code dùng .get("trend",{}).get(...)
    # sẽ crash khi trend=None (None.get không tồn tại). Bỏ qua key hoàn toàn
    # → .get("trend",{}) trả {} đúng như mong đợi.
    _check()
    log_fn("    [Google Trends sẽ được fill bởi tools/trends_refresh.py]")

    # SEO score cho video kênh seed
    seo_summary = {}
    if videos:
        log_fn(f"    Tính SEO score cho {len(videos)} video kênh...")
        try:
            seo_summary = tag_analyzer.compute_channel_seo_summary(videos)
            log_fn(f"    SEO trung bình: {seo_summary.get('avg_score', 0)}/100")
        except Exception as e:
            log_fn(f"    ⚠ SEO score lỗi: {e}")

    return {
        "per_keyword": per_kw_metrics,
        "seo_summary": seo_summary,
    }


def _download_analyze_thumbnails(recent_by_keyword: dict, log_fn,
                                 channel_videos: Optional[list] = None) -> dict:
    """Tự động chọn video tiêu biểu → tải thumbnail → phân tích màu sắc.

    - Ngách: chọn video tiêu biểu từ recent_by_keyword.
    - Kênh chính: phân tích thumbnail video của chính kênh (nếu truyền
      channel_videos).
    - So sánh kênh vs ngách bằng compare_channel_vs_niche.

    Trả dict {thumbnail_videos, thumbnail_analysis,
    channel_thumbnail_analysis, thumbnail_comparison}. Không bắt buộc —
    lỗi thì trả rỗng, pipeline vẫn chạy bình thường."""
    empty = {"thumbnail_videos": [], "thumbnail_analysis": None,
             "channel_thumbnail_analysis": None,
             "thumbnail_comparison": None}
    try:
        from . import thumbnails as _th
        from . import thumbnail_analyzer as _ta
    except Exception:
        return empty
    try:
        # --- Thumbnail ngách (đối thủ trong ngách) ---
        vids = _th.pick_videos_for_thumbnails(recent_by_keyword, limit=30)
        analysis = None
        if vids:
            log_fn(f"  → Đang tải + phân tích {len(vids)} thumbnail ngách...")
            items = []
            for v in vids:
                p = _th.download_thumbnail(v.video_id, "mqdefault")
                if p:
                    items.append({"view_count": v.view_count, "path": p,
                                  "title": v.title,
                                  "video_id": v.video_id})
            analysis = _ta.analyze_set(items)
            log_fn(f"  → Đã phân tích màu {analysis.get('count', 0)} "
                   f"thumbnail ngách")

        # --- Thumbnail kênh chính ---
        channel_analysis = None
        ch_vids = channel_videos or []
        if ch_vids:
            log_fn(f"  → Đang tải + phân tích {len(ch_vids)} thumbnail "
                   f"video của kênh chính...")
            ch_items = []
            for v in ch_vids:
                vid = getattr(v, "video_id", "")
                if not vid:
                    continue
                p = _th.download_thumbnail(vid, "mqdefault")
                if p:
                    ch_items.append({
                        "view_count": getattr(v, "view_count", 0),
                        "path": p, "title": getattr(v, "title", ""),
                        "video_id": vid})
            if ch_items:
                channel_analysis = _ta.analyze_set(ch_items)
                log_fn(f"  → Đã phân tích màu "
                       f"{channel_analysis.get('count', 0)} thumbnail "
                       f"của kênh chính")

        # --- So sánh kênh vs ngách ---
        comparison = None
        if channel_analysis and analysis:
            try:
                comparison = _ta.compare_channel_vs_niche(
                    channel_analysis, analysis)
                if comparison:
                    log_fn("  → Đã so sánh thumbnail kênh chính với ngách")
            except Exception as e:
                log_fn(f"  ⚠ So sánh thumbnail lỗi (bỏ qua): {e}")

        return {"thumbnail_videos": vids,
                "thumbnail_analysis": analysis,
                "channel_thumbnail_analysis": channel_analysis,
                "thumbnail_comparison": comparison}
    except Exception as e:
        log_fn(f"  ⚠ Thumbnail lỗi (bỏ qua): {e}")
        return empty


def run_research(
    channel_url: str,
    output_path: str,
    days: int = 30,
    top_keywords: int = 20,
    per_keyword: int = 25,
    max_channel_videos: int = 30,
    chrome_mode: str = "show",
    region: Optional[str] = None,
    log_fn: Callable[[str], None] = print,
    progress_fn: Callable[[int, int, str], None] = lambda *_: None,
    cancel_event: Optional[threading.Event] = None,
    cdp_url: str = "",
) -> dict:
    """
    Chạy pipeline nghiên cứu đầy đủ bằng Playwright (mở Chrome).

    cdp_url: nếu set (vd "http://127.0.0.1:9222") → connect_over_cdp đến
             cloakbrowser pool (IPv6 + fingerprint fake) thay vì launch
             Chrome IP máy. Mặc định rỗng → giữ behavior V1.
    """

    def _check_cancel():
        if cancel_event and cancel_event.is_set():
            raise ResearchCancelled("Người dùng đã huỷ tác vụ")

    if cdp_url:
        log_fn(f"Bước 1/5: Connect CDP cloakbrowser {cdp_url}...")
    else:
        log_fn("Bước 1/5: Khởi tạo Chrome...")
    progress_fn(0, 100, "Khởi tạo trình duyệt")
    client = PlaywrightBackend(chrome_mode=chrome_mode, log_fn=log_fn,
                                cdp_url=cdp_url)
    backend_name = "cloak_cdp" if cdp_url else "browser"
    if cdp_url:
        log_fn(f"  → Connected cloakbrowser CDP (IPv6 fake)")
    else:
        log_fn(f"  → Đã mở Chrome (mô phỏng người dùng)")
    _check_cancel()

    try:
        # Resolve channel
        parsed = parse_channel_url(channel_url)
        log_fn(f"  → Đang tìm kênh ({parsed['kind']}: {parsed['value']})...")
        channel = client.resolve_channel(parsed)
        log_fn(f"  → Kênh: {channel.title} ({channel.subscriber_count:,} subs)")
        progress_fn(10, 100, "Đã tìm thấy kênh")
        _check_cancel()

        # Social Blade ĐÃ TÁCH RA `tools/socialblade_refresh.py` (giống
        # Google Trends) để tránh rate limit khi nhiều worker đồng thời
        # hit socialblade.com. Pkl lưu socialblade=None ở đây, sau khi
        # monitor xong gọi tools/socialblade_refresh.py <wid> để fill
        # (1 worker, delay 3s/kênh, cache 6h built-in chia sẻ).
        socialblade_data = None
        log_fn("  → [Social Blade sẽ fill bởi tools/socialblade_refresh.py]")
        _check_cancel()

        # Channel videos
        log_fn(f"Bước 2/5: Lấy tối đa {max_channel_videos} video của kênh...")
        videos = client.list_channel_videos(channel, limit=max_channel_videos)
        log_fn(f"  → Đã lấy {len(videos)} video. Đang trích tags chi tiết...")
        # Enrich: vào từng trang video lấy tags + description đầy đủ
        # (Listing /videos không có tags - phải vào watch page)
        client.enrich_videos_with_tags(
            videos, log_fn=log_fn, progress_fn=progress_fn,
            base_pct=22, cancel_event=cancel_event,
        )
        tag_total = sum(len(v.tags) for v in videos)
        log_fn(f"  → Đã trích {tag_total} tags từ {len(videos)} video "
               f"(TB {tag_total // max(len(videos), 1)} tags/video)")
        progress_fn(30, 100, f"Đã có {len(videos)} video + tags")
        _check_cancel()

        # Keyword extraction
        log_fn("Bước 3/5: Trích xuất từ khoá...")
        keywords = extract_keywords(
            channel_keywords=channel.keywords,
            video_tags=[v.tags for v in videos],
            video_titles=[v.title for v in videos],
            video_descriptions=[v.description for v in videos],
            top_n=top_keywords,
        )
        if not keywords:
            log_fn("  ⚠ Cảnh báo: không trích được từ khoá nào.")
        else:
            log_fn(f"  → Đã trích được {len(keywords)} từ khoá.")
            if len(keywords) <= 12:
                shown = ", ".join(k.keyword for k in keywords)
                log_fn(f"     Danh sách: {shown}")
            else:
                top10 = ", ".join(k.keyword for k in keywords[:10])
                log_fn(f"     10 từ khoá điểm cao nhất: {top10}, ...")
        progress_fn(35, 100, f"Đã trích {len(keywords)} từ khoá")
        _check_cancel()

        # Search per keyword
        log_fn(f"Bước 4/5: Tìm trên YouTube cho từng từ khoá: "
               f"top view + video MỚI nhiều view (trong {days} ngày)...")
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        top_by_keyword = {}
        recent_by_keyword = {}

        total_kw = len(keywords)
        for i, kw in enumerate(keywords, start=1):
            _check_cancel()
            log_fn(f"  ({i}/{total_kw}) '{kw.keyword}'")
            # Top (no time filter) - check cache trước
            cached_top = search_cache.get_search(kw.keyword, None, region)
            if cached_top is not None:
                top = cached_top[:per_keyword]
                log_fn("        [cache] top reuse")
            else:
                try:
                    top = client.search(
                        kw.keyword,
                        max_results=per_keyword,
                        order="viewCount",
                        region_code=region,
                    )
                    search_cache.set_search(kw.keyword, None, region, top)
                except Exception as e:
                    log_fn(f"    ⚠ Lỗi tìm top: {e}")
                    top = []
            _check_cancel()
            # Recent (with time filter) - check cache theo days
            cached_recent = search_cache.get_search(kw.keyword, days, region)
            if cached_recent is not None:
                recent = cached_recent[:per_keyword]
                log_fn(f"        [cache] recent {days}d reuse")
            else:
                try:
                    recent = client.search(
                        kw.keyword,
                        max_results=per_keyword,
                        order="viewCount",
                        published_after=cutoff,
                        region_code=region,
                    )
                    search_cache.set_search(kw.keyword, days, region, recent)
                except Exception as e:
                    log_fn(f"    ⚠ Lỗi tìm video mới nhiều view: {e}")
                    recent = []
            top_by_keyword[kw.keyword] = top
            recent_by_keyword[kw.keyword] = recent

            pct = 35 + int(55 * i / max(total_kw, 1))
            progress_fn(pct, 100, f"Tìm kiếm: {i}/{total_kw} từ khoá")

        # Tính trending score cho mỗi video
        partial = {
            "channel": channel, "videos": videos,
            "recent_by_keyword": recent_by_keyword,
            "top_by_keyword": top_by_keyword,
        }
        trending_mod.annotate_result(partial)
        viral_count = sum(
            1 for vids in recent_by_keyword.values()
            for v in vids if getattr(v, "trending_score", 0) >= trending_mod.VIRAL_THRESHOLD)
        if viral_count:
            log_fn(f"  🔥 Phát hiện {viral_count} video VIRAL "
                   f"(views/ngày >= 3× mức bình thường của kênh)")

        # Tag metrics: competition + trends + autosuggest + SEO
        tag_metrics = _compute_tag_metrics(
            keywords, videos, log_fn, progress_fn,
            base_pct=90, cancel_event=cancel_event,
        )

        # Tự động tải + phân tích thumbnail (không cần AI — đo pixel)
        # Phân tích cả thumbnail ngách lẫn thumbnail của kênh chính,
        # rồi so sánh hai bên.
        thumb_data = _download_analyze_thumbnails(
            recent_by_keyword, log_fn, channel_videos=videos)
        _check_cancel()

        # Excel export
        log_fn("Bước 5/5: Đang xuất file Excel...")
        progress_fn(92, 100, "Xuất Excel")

        final_path = output_path
        if not final_path:
            final_path = f"youtube_research_{safe_filename(channel.title)}.xlsx"
        final_path = str(Path(final_path).resolve())
        os.makedirs(os.path.dirname(final_path) or ".", exist_ok=True)

        run_params = {
            "backend": backend_name,
            "days": days,
            "top_keywords": top_keywords,
            "per_keyword": per_keyword,
            "region": region,
        }
        build_workbook(
            channel=channel,
            channel_videos=videos,
            keywords=keywords,
            top_by_keyword=top_by_keyword,
            recent_by_keyword=recent_by_keyword,
            run_params=run_params,
            output_path=final_path,
            tag_metrics=tag_metrics,
        )
        log_fn(f"  → Đã lưu: {final_path}")
        progress_fn(100, 100, "Hoàn tất")

        return {
            "output_path": final_path,
            "channel_title": channel.title,
            "backend": backend_name,
            "subscriber_count": channel.subscriber_count,
            "video_count": len(videos),
            "keyword_count": len(keywords),
            "top_keywords": [k.keyword for k in keywords[:10]],
            "channel": channel,
            "videos": videos,
            "keywords": keywords,
            "top_by_keyword": top_by_keyword,
            "recent_by_keyword": recent_by_keyword,
            "params": run_params,
            "tag_metrics": tag_metrics,
            "socialblade": socialblade_data,
            "thumbnail_videos": thumb_data.get("thumbnail_videos", []),
            "thumbnail_analysis": thumb_data.get("thumbnail_analysis"),
            "channel_thumbnail_analysis": thumb_data.get(
                "channel_thumbnail_analysis"),
            "thumbnail_comparison": thumb_data.get("thumbnail_comparison"),
        }
    finally:
        # Luôn đóng Chrome
        try:
            client.close()
            log_fn("  → Đã đóng Chrome")
        except Exception:
            pass


def run_research_keywords(
    keywords_list: list,
    output_path: str,
    days: int = 30,
    per_keyword: int = 25,
    chrome_mode: str = "show",
    region: Optional[str] = None,
    log_fn: Callable[[str], None] = print,
    progress_fn: Callable[[int, int, str], None] = lambda *_: None,
    cancel_event: Optional[threading.Event] = None,
) -> dict:
    """
    Chạy pipeline KHÔNG có kênh - chỉ với danh sách từ khoá user cung cấp.
    """

    def _check_cancel():
        if cancel_event and cancel_event.is_set():
            raise ResearchCancelled("Người dùng đã huỷ tác vụ")

    # Làm sạch keywords
    clean_kws = []
    seen = set()
    for kw in keywords_list:
        kw = (kw or "").strip()
        kl = kw.lower()
        if kw and kl not in seen:
            seen.add(kl)
            clean_kws.append(kw)
    if not clean_kws:
        raise ValueError("Danh sách từ khoá rỗng")

    log_fn(f"Bước 1/3: Khởi tạo Chrome cho {len(clean_kws)} từ khoá...")
    progress_fn(0, 100, "Khởi tạo trình duyệt")
    client = PlaywrightBackend(chrome_mode=chrome_mode, log_fn=log_fn)
    backend_name = "browser"
    log_fn("  → Đã mở Chrome (mô phỏng người dùng)")
    _check_cancel()

    try:
        # Tạo KeywordEntry mặc định cho mỗi từ khoá user nhập
        keyword_entries = [
            KeywordEntry(keyword=kw, score=1.0, sources={"user"},
                         channel_video_count=0)
            for kw in clean_kws
        ]
        progress_fn(5, 100, f"Có {len(keyword_entries)} từ khoá")

        # Tìm trên YouTube
        log_fn(f"Bước 2/3: Tìm trên YouTube cho từng từ khoá: "
               f"top view + video MỚI nhiều view (trong {days} ngày)...")
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        top_by_keyword = {}
        recent_by_keyword = {}

        total_kw = len(keyword_entries)
        for i, kw in enumerate(keyword_entries, start=1):
            _check_cancel()
            log_fn(f"  ({i}/{total_kw}) '{kw.keyword}'")
            # Top - check cache
            cached_top = search_cache.get_search(kw.keyword, None, region)
            if cached_top is not None:
                top = cached_top[:per_keyword]
                log_fn("        [cache] top reuse")
            else:
                try:
                    top = client.search(
                        kw.keyword,
                        max_results=per_keyword,
                        order="viewCount",
                        region_code=region,
                    )
                    search_cache.set_search(kw.keyword, None, region, top)
                except Exception as e:
                    log_fn(f"    ⚠ Lỗi tìm top: {e}")
                    top = []
            _check_cancel()
            # Recent - check cache
            cached_recent = search_cache.get_search(kw.keyword, days, region)
            if cached_recent is not None:
                recent = cached_recent[:per_keyword]
                log_fn(f"        [cache] recent {days}d reuse")
            else:
                try:
                    recent = client.search(
                        kw.keyword,
                        max_results=per_keyword,
                        order="viewCount",
                        published_after=cutoff,
                        region_code=region,
                    )
                    search_cache.set_search(kw.keyword, days, region, recent)
                except Exception as e:
                    log_fn(f"    ⚠ Lỗi tìm video mới: {e}")
                    recent = []
            top_by_keyword[kw.keyword] = top
            recent_by_keyword[kw.keyword] = recent

            pct = 5 + int(85 * i / max(total_kw, 1))
            progress_fn(pct, 100, f"Tìm kiếm: {i}/{total_kw} từ khoá")

        # Tạo channel "ảo" cho excel export
        fake_channel = ChannelInfo(
            channel_id="",
            title=f"Danh sách {len(clean_kws)} từ khoá",
            handle="",
            description="(Mode danh sách từ khoá - không có kênh seed)",
            subscriber_count=0,
            view_count=0,
            video_count=0,
            keywords=clean_kws,
            url="",
        )

        # Tính trending score
        trending_mod.annotate_result({
            "channel": fake_channel, "videos": [],
            "recent_by_keyword": recent_by_keyword,
            "top_by_keyword": top_by_keyword,
        })

        # Tag metrics: competition + trends + autosuggest (không có SEO vì không có video kênh)
        tag_metrics = _compute_tag_metrics(
            keyword_entries, [], log_fn, progress_fn,
            base_pct=90, cancel_event=cancel_event,
        )

        # Tự động tải + phân tích thumbnail
        thumb_data = _download_analyze_thumbnails(recent_by_keyword, log_fn)
        _check_cancel()

        # Export Excel
        log_fn("Bước 3/3: Đang xuất file Excel...")
        progress_fn(92, 100, "Xuất Excel")

        final_path = output_path
        if not final_path:
            final_path = f"youtube_research_keywords_{safe_filename(clean_kws[0])}.xlsx"
        final_path = str(Path(final_path).resolve())
        os.makedirs(os.path.dirname(final_path) or ".", exist_ok=True)

        run_params = {
            "backend": backend_name,
            "days": days,
            "top_keywords": len(keyword_entries),
            "per_keyword": per_keyword,
            "region": region,
            "mode": "keywords",
        }
        build_workbook(
            channel=fake_channel,
            channel_videos=[],
            keywords=keyword_entries,
            top_by_keyword=top_by_keyword,
            recent_by_keyword=recent_by_keyword,
            run_params=run_params,
            output_path=final_path,
        )
        log_fn(f"  → Đã lưu: {final_path}")
        progress_fn(100, 100, "Hoàn tất")

        return {
            "output_path": final_path,
            "channel_title": fake_channel.title,
            "backend": backend_name,
            "subscriber_count": 0,
            "video_count": 0,
            "keyword_count": len(keyword_entries),
            "top_keywords": clean_kws[:10],
            "input_keywords": clean_kws,
            "channel": fake_channel,
            "videos": [],
            "keywords": keyword_entries,
            "top_by_keyword": top_by_keyword,
            "recent_by_keyword": recent_by_keyword,
            "params": run_params,
            "tag_metrics": tag_metrics,
            "thumbnail_videos": thumb_data.get("thumbnail_videos", []),
            "thumbnail_analysis": thumb_data.get("thumbnail_analysis"),
            "channel_thumbnail_analysis": thumb_data.get(
                "channel_thumbnail_analysis"),
            "thumbnail_comparison": thumb_data.get("thumbnail_comparison"),
        }
    finally:
        try:
            client.close()
            log_fn("  → Đã đóng Chrome")
        except Exception:
            pass
