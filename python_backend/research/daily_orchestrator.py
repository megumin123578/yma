# -*- coding: utf-8 -*-
"""Daily Run Orchestrator — 7 stage pipeline + state DB.

PHẦN MỀM LÀ GỐC: 1 nút "⚡ DAILY RUN" trong app gọi `run_daily()` → chạy
qua 7 stage cho mỗi WL. Mỗi stage check state DB → skip nếu đã done →
resume khi crash → không sót/lặp.

Stages (mỗi WL):
  1. monitor    — Cào subs + 30 video × (title/desc/tags/like/cmt/view)
                  V2 (CloakBrowser proxy) → V1 fallback (Chrome IP máy)
  2. socialblade — refresh growth 15d (force=True bypass cache)
  3. trends     — Google Trends keyword (force=True)
  4. inside     — YouTube Analytics API (self_channel có OAuth token)
  5. research   — search YouTube top 20 kw → recent/top_by_keyword
  6. keyword    — enrich kw_bank (volume + competition từ harvest tối)
  7. report     — sinh AI (ai_analysis + strategy) → lưu pkl

State DB: ~/.youtube_research/orchestrator.sqlite (table wl_stage_state)
Resume: chạy lại với cùng run_id → skip stage status='done'.
UI live progress: `get_progress(run_id)` trả list (wl_id, stage, status).

USAGE (qua app: nút ⚡ DAILY RUN. Qua CLI debug):
    from .daily_orchestrator import run_daily
    import asyncio
    asyncio.run(run_daily())                          # tất cả 25 WL
    asyncio.run(run_daily(wl_ids=['wl_xxx'],          # 1 WL
                          run_id='run_test'))
    asyncio.run(run_daily(resume='run_20260524_05'))  # resume run cũ
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


_ROOT = Path(__file__).resolve().parent.parent
STATE_DB = Path.home() / ".youtube_research" / "orchestrator.sqlite"


# 2026-06: crawl tools (monitor_batch, discover) đã port vào package
# python_backend/research — spawn qua `-m` từ repo root, KHÔNG còn trỏ YT/project.
_REPO_ROOT = _ROOT.parent  # python_backend -> repo root
# 24/05 (user feedback lần 2): refactor quy trình:
#   - BỎ 'trends' (Google Trends 429 IP nhà liên miên).
#   - BỎ 'research' (search YouTube 20kw/WL — đã trùng với monitor V1 implicit).
#   - THÊM 'discover' NGAY SAU monitor (tìm đối thủ MỚI ngách).
# 2026-06: BỎ 'inside' — Inside kênh chính do cronjob app chính (get_data.py →
# Postgres) sinh; báo cáo đọc thẳng Postgres qua analytics_inside. Tránh fetch
# YouTube Analytics API trùng 2 lần / 2 nơi lưu (SQLite + Postgres).
# Quy trình 5 stage:
#   1. monitor      — Cào 25 WL × 30 video kênh (V1 6 worker)
#   2. discover     — Tìm đối thủ mới chưa có trong WL (1 worker tránh 429)
#   3. socialblade  — Refresh growth 15-30d
#   4. keyword      — Áp kw_bank harvest keywordtool vào pkl
#   5. report       — sinh AI (ai_analysis + strategy) → lưu pkl (serve qua API)
# stage_trends + stage_research vẫn giữ trong code dạng DEPRECATED.
STAGES = ["monitor", "discover", "socialblade", "keyword", "report"]


# ============================================================
# State DB
# ============================================================
def _init_db() -> sqlite3.Connection:
    STATE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(STATE_DB), timeout=30, isolation_level=None)
    conn.execute("""CREATE TABLE IF NOT EXISTS wl_stage_state (
        run_id TEXT NOT NULL,
        wl_id TEXT NOT NULL,
        stage TEXT NOT NULL,
        status TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        error TEXT,
        PRIMARY KEY (run_id, wl_id, stage)
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_run_status
                   ON wl_stage_state(run_id, status)""")
    return conn


def _set_state(conn, run_id: str, wl_id: str, stage: str,
               status: str, error: str = ""):
    """Ghi/update state. status ∈ {pending, running, done, failed, skipped}"""
    now = datetime.now().isoformat(timespec='seconds')
    existing = conn.execute(
        "SELECT started_at FROM wl_stage_state "
        "WHERE run_id=? AND wl_id=? AND stage=?",
        (run_id, wl_id, stage)).fetchone()
    if existing is None:
        conn.execute("""INSERT INTO wl_stage_state
            (run_id, wl_id, stage, status, started_at, finished_at, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (run_id, wl_id, stage, status,
             now if status == "running" else None,
             now if status in ("done", "failed", "skipped") else None,
             error))
    else:
        conn.execute("""UPDATE wl_stage_state
            SET status=?, finished_at=?, error=?
            WHERE run_id=? AND wl_id=? AND stage=?""",
            (status,
             now if status in ("done", "failed", "skipped") else None,
             error, run_id, wl_id, stage))


def _get_state(conn, run_id: str, wl_id: str, stage: str) -> Optional[str]:
    row = conn.execute(
        "SELECT status FROM wl_stage_state "
        "WHERE run_id=? AND wl_id=? AND stage=?",
        (run_id, wl_id, stage)).fetchone()
    return row[0] if row else None


def get_progress(run_id: str) -> list:
    """Return list of (wl_id, stage, status, error) cho UI live progress."""
    conn = _init_db()
    try:
        return conn.execute(
            "SELECT wl_id, stage, status, error FROM wl_stage_state "
            "WHERE run_id=? ORDER BY wl_id, stage", (run_id,)).fetchall()
    finally:
        conn.close()


# ============================================================
# Stages — mỗi stage là 1 function trả {ok: bool, reason?: str}
# ============================================================

async def stage_monitor(wid: str, log_fn) -> dict:
    """V1 monitor — Chrome IP máy + 6 worker ProcessPool.

    24/05 (user chốt): BỎ V2 (CloakBrowser + proxy MKVN) khỏi quy trình
    vì proxy MKVN die liên miên + V2 thất bại nhiều. Chỉ V1 ổn định.
    ~3-5 phút/WL × 25 WL ≈ 1.5-2 giờ tổng. Không cần PREFER_V1 env nữa.
    """
    log_fn(f"    [monitor] V1 — Chrome IP máy, 6 worker...")
    try:
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", "-m",
             "python_backend.research.monitor_batch", wid, "--workers", "6"],
            cwd=str(_REPO_ROOT), capture_output=True, timeout=3600)
        ok = proc.returncode == 0
        log_fn(f"    [monitor] V1 {'OK' if ok else 'FAIL'} (rc={proc.returncode})")
        return {"ok": ok, "via": "v1_6w"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "v1_timeout_1h"}
    except Exception as e:
        return {"ok": False, "reason": f"v1_err: {e}"}


def _compute_view_7d_avg(sb_data: dict) -> float:
    """Trả trung bình views_change 7 ngày gần nhất từ SocialBlade.

    24/05 (user chốt 2 lần):
    1. BỎ ngày views_change ÂM (kênh ẨN video cũ → SB recount âm).
    2. BỎ ngày views_change = 0 Ở VỊ TRÍ CUỐI (SB chưa update hôm nay).
       Pop tail liên tiếp các ngày = 0 trước khi cắt 7 ngày.
       Ngày 0 ở GIỮA vẫn giữ (kênh thực sự không có view ngày đó).

    Nếu pkl không có SB hoặc daily_stats trống → trả 0.
    """
    daily = (sb_data or {}).get("daily_stats") or []
    if not daily:
        return 0.0
    # Pop tail có views_change = 0 (chưa update)
    cleaned = list(daily)
    while cleaned and (cleaned[-1].get("views_change") or 0) == 0:
        cleaned.pop()
    if not cleaned:
        return 0.0
    last7 = cleaned[-7:]
    # Bỏ ngày âm; giữ ngày 0 ở giữa (sự thật — không có view) + dương
    valid = [(d.get("views_change") or 0) for d in last7
             if isinstance(d, dict) and (d.get("views_change") or 0) >= 0]
    return sum(valid) / len(valid) if valid else 0.0


def _trim_wl_to_top10(wid: str, log_fn) -> dict:
    """24/05 (user chốt): mỗi WL chỉ giữ 1 kênh chính + 9 đối thủ TOP
    theo view/day 7d (SocialBlade). Kênh yếu hơn → archived=True (giữ
    pkl history, ẩn khỏi daily run / report).

    Trả dict {kept, archived, removed_titles}.
    """
    from . import watchlist as wl_mod, persistence
    from datetime import datetime as _dt

    wl = wl_mod.load_watchlist(wid)
    if not wl:
        return {"kept": 0, "archived": 0}

    self_cid = wl.self_channel.channel_id if wl.self_channel else None

    # Chỉ xét active channels (đã archived → kệ)
    active = [c for c in wl.channels if not c.archived]

    scored = []
    for c in active:
        if not c.channel_id or not c.channel_id.startswith("UC"):
            scored.append((c, 0.0, "no_cid"))
            continue
        recs = persistence.records_for_channel(c.channel_id)
        if not recs:
            scored.append((c, 0.0, "no_pkl"))
            continue
        ch_pkl = persistence.load_result(recs[0]["id"])
        if ch_pkl is None:
            scored.append((c, 0.0, "pkl_err"))
            continue
        sb = ch_pkl.get("socialblade") or {}
        avg_7d = _compute_view_7d_avg(sb)
        scored.append((c, avg_7d, f"7d_avg={int(avg_7d):,}"))

    # Self pin top, còn lại sort theo avg_7d desc
    self_items = [s for s in scored if s[0].channel_id == self_cid]
    others = [s for s in scored if s[0].channel_id != self_cid]
    others.sort(key=lambda x: x[1], reverse=True)

    keep_list = self_items + others[:9]   # max 10
    # SAFEGUARD 24/05: chỉ archive kênh CÓ SB data thật (avg_7d > 0).
    # Kênh chưa có SB (score=0) → giữ tạm, chờ daily run sau có SB.
    # Tránh archive oan kênh chưa monitor lần nào.
    archive_list = [s for s in others[9:] if s[1] > 0]
    spared_no_sb = [s for s in others[9:] if s[1] == 0]

    log_fn(f"    [trim] GIỮ {len(keep_list)}/{len(active)} kênh:")
    for c, score, info in keep_list:
        mark = " ★ CHÍNH" if c.channel_id == self_cid else ""
        log_fn(f"      ✓ {(c.title or '')[:38]:38}  {info}{mark}")
    if spared_no_sb:
        log_fn(f"    [trim] GIỮ TẠM {len(spared_no_sb)} kênh chưa có SB data:")
        for c, score, info in spared_no_sb:
            log_fn(f"      ⏳ {(c.title or '')[:38]:38}  {info}")

    if not archive_list:
        log_fn(f"    [trim] Không có kênh nào cần archive")
        return {"kept": len(keep_list) + len(spared_no_sb),
                "archived": 0, "removed_titles": []}

    log_fn(f"    [trim] ARCHIVE {len(archive_list)} kênh yếu nhất:")
    archived_titles = []
    archive_cids = {c.channel_id for c, _, _ in archive_list}
    now = _dt.now().isoformat(timespec="seconds")
    for c in wl.channels:
        if c.channel_id in archive_cids and not c.is_self:
            c.archived = True
            c.archived_at = now
            c.archived_reason = "out_of_top10_views_7d"
            archived_titles.append(c.title or c.channel_id)
            log_fn(f"      ✗ {(c.title or '')[:38]:38}  archived")

    wl_mod.save_watchlist(wl)
    return {"kept": len(keep_list), "archived": len(archive_list),
            "removed_titles": archived_titles}


def _get_wl_channel_ids(wid: str) -> set:
    """Trả set channel_id hiện có trong WL."""
    from . import watchlist as wl_mod
    wl = wl_mod.load_watchlist(wid)
    if not wl:
        return set()
    return {c.channel_id for c in wl.channels if c.channel_id}


def _save_discover_candidates(anchor_wid: str, candidates: list) -> None:
    """Ghi list channel_id mới được anchor discover ra file → member copy."""
    import json as _json
    p = (Path.home() / ".youtube_research" / "discover_candidates"
         / f"{anchor_wid}.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_json.dumps(candidates), encoding="utf-8")


def _load_discover_candidates(anchor_wid: str) -> list:
    """Đọc list channel_id từ anchor discover. Trả [] nếu chưa có."""
    import json as _json
    p = (Path.home() / ".youtube_research" / "discover_candidates"
         / f"{anchor_wid}.json")
    if not p.exists():
        return []
    try:
        return _json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def _add_channels_to_wl(wid: str, channel_ids: list, log_fn=print) -> int:
    """Thêm channel mới vào WL (nếu chưa có). Copy info từ pkl của
    channel đó nếu pkl tồn tại. Trả số channel đã add."""
    from . import watchlist as wl_mod, persistence
    from .watchlist import WatchedChannel
    from datetime import datetime as _dt

    wl = wl_mod.load_watchlist(wid)
    if not wl:
        return 0

    existing = {c.channel_id for c in wl.channels}
    added = 0
    now = _dt.now().isoformat(timespec="seconds")

    for cid in channel_ids:
        if not cid or cid in existing:
            continue
        # Tìm title từ pkl gần nhất (anchor đã cào kênh này)
        title = cid
        url = f"https://www.youtube.com/channel/{cid}"
        recs = persistence.records_for_channel(cid)
        if recs:
            d = persistence.load_result(recs[0]["id"])
            if d:
                title = d.get("channel_title", cid)

        new_ch = WatchedChannel(
            channel_id=cid, title=title, url=url,
            is_self=False, added_at=now,
            auto_added=True, auto_added_pct=50.0,  # placeholder
        )
        wl.channels.append(new_ch)
        added += 1

    if added > 0:
        wl_mod.save_watchlist(wl)
    return added


def stage_discover(wid: str, log_fn) -> dict:
    """24/05: Phát hiện đối thủ MỚI ngách + cluster-aware + trim top 10.

    A. Đọc anchor map (compute_anchor_map đã chạy ở đầu run_daily).
    B. Nếu wid là ANCHOR cụm → chạy discover.py + lưu list candidate.
       Nếu wid là MEMBER → copy candidate từ anchor (skip discover.py).
    C. Trim WL về top 10 theo SB view 7d.

    Tiết kiệm: cụm 4 WL chỉ chạy discover 1 lần thay 4 lần.
    """
    from .wl_clustering import load_anchor_map

    anchor_map = load_anchor_map()
    my_anchor = anchor_map.get(wid, wid)
    is_anchor = (my_anchor == wid)

    added = 0
    via = "anchor" if is_anchor else "member"

    if is_anchor:
        # ANCHOR: chạy discover.py thật
        # 24/05 (user chốt): timeout 60p (3600s) — discover chạy 1 browser/lần,
        # gặp 5-7 kênh mới phải cào sâu (50 video/kênh + trích keyword) →
        # 15p không đủ. 60p an toàn.
        before = _get_wl_channel_ids(wid)
        try:
            proc = subprocess.run(
                [sys.executable, "-X", "utf8", "-m",
                 "python_backend.research.discover", wid],
                cwd=str(_REPO_ROOT), capture_output=True, timeout=3600)
            ok_dis = proc.returncode == 0
            out = proc.stdout.decode("utf-8", errors="ignore")
            if "KET NAP" in out:
                import re
                m = re.search(r"KET NAP (\d+) kenh moi", out)
                if m:
                    added = int(m.group(1))
            log_fn(f"    [discover] ANCHOR {'OK' if ok_dis else 'FAIL'}"
                   f" — kết nạp {added} kênh mới")
        except subprocess.TimeoutExpired:
            log_fn(f"    [discover] anchor_timeout_60p (quá lâu — skip)")
        except Exception as e:
            log_fn(f"    [discover] anchor_err: {e}")

        # Snapshot sau → lưu candidates cho members
        after = _get_wl_channel_ids(wid)
        new_ids = list(after - before)
        _save_discover_candidates(wid, new_ids)
    else:
        # MEMBER: copy từ anchor
        candidates = _load_discover_candidates(my_anchor)
        if not candidates:
            log_fn(f"    [discover] MEMBER (anchor={my_anchor[:24]}…) — "
                   f"anchor chưa discover xong, skip copy")
        else:
            added = _add_channels_to_wl(wid, candidates, log_fn=log_fn)
            log_fn(f"    [discover] MEMBER (anchor={my_anchor[:24]}…) — "
                   f"copy {added}/{len(candidates)} kênh từ anchor")

    # C. Trim WL về top 10 theo SB 7d
    try:
        trim_res = _trim_wl_to_top10(wid, log_fn)
        return {"ok": True, "added": added, "via": via,
                "trimmed": trim_res["archived"],
                "kept": trim_res["kept"]}
    except Exception as e:
        log_fn(f"    [trim] err: {e}")
        return {"ok": True, "added": added, "via": via,
                "trim_err": str(e)[:100]}


def stage_socialblade(wid: str, log_fn) -> dict:
    """K8: force=True, fetch FRESH (bypass cache)."""
    try:
        from .refreshers import refresh_socialblade_for_watchlist
        r = refresh_socialblade_for_watchlist(
            wid, log_fn=lambda s: None, force=True)
        if r is None:
            return {"ok": False, "reason": "wl_not_found"}
        n_total, n_cache, n_fetched, n_err, _ = r
        log_fn(f"    [SB] fetched={n_fetched} err={n_err}/{n_total}")
        return {"ok": n_err < n_total}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:200]}


def stage_trends(wid: str, log_fn) -> dict:
    """DEPRECATED 24/05: bỏ Google Trends khỏi quy trình daily run.

    Lý do: 429 rate-limit IP nhà liên miên + dữ liệu kém tin cậy hơn
    keywordtool. Đã thay bằng keywordtool.enrich_keywords (volume +
    competition) trong stage 'keyword' / kw_bank_analysis. Function giữ
    lại cho compatibility — KHÔNG còn nằm trong STAGES.
    """
    try:
        from .refreshers import refresh_trends_for_watchlist
        r = refresh_trends_for_watchlist(
            wid, log_fn=lambda s: None, force=True, max_rotations=0)
        if r is None:
            return {"ok": False, "reason": "wl_not_found"}
        log_fn(f"    [Trends] {r[0]} channels, {r[1]} kw")
        return {"ok": True}
    except Exception as e:
        err = str(e)[:200]
        if "429" in err or "rate" in err.lower():
            log_fn(f"    [Trends] 429 rate-limit → SKIP (user dặn 24/05)")
            return {"ok": False, "reason": "rate_limit_429_skip"}
        return {"ok": False, "reason": err}


async def stage_research(wid: str, log_fn) -> dict:
    """DEPRECATED 24/05 (user feedback lần 2): BỎ stage 'research'
    khỏi STAGES. Lý do: trùng với monitor V1 implicit (đã cào
    recent_by_keyword sẵn) → vô nghĩa khi chạy thêm. Function giữ
    cho compatibility nếu state DB cũ có stage này.
    """
    log_fn(f"    [research] DEPRECATED — bỏ khỏi quy trình 24/05")
    return {"ok": True, "via": "deprecated"}


def stage_keyword(wid: str, log_fn) -> dict:
    """Enrich kw_bank từ harvest tối + snapshot history (A43, 26/05 chiều).

    Track theo mỗi lần chạy: lưu snapshot FULL (90 ngày rotate) + diff
    so với lần chạy trước (vĩnh viễn). Phục vụ tab HTML "📈 Lịch sử
    kho từ khoá" — show từ vàng mới xuất hiện / mất / đổi mạnh.
    """
    try:
        from . import watchlist as wl_mod
        w = wl_mod.load_watchlist(wid)
        if not w or not w.self_channel:
            return {"ok": False, "reason": "no_self"}
        from .keyword_bank_analysis import get_channel_kw_bank
        from . import keyword_bank_history as kbh
        bank = get_channel_kw_bank(
            w.self_channel.channel_id, w.self_channel.title)
        if bank:
            top_vang = bank.get("top_vang") or bank.get("top_golden") or []
            log_fn(f"    [keyword] kw_bank: top {len(top_vang)} vàng")
            # A43: take snapshot + compute diff
            try:
                snap_id = kbh.take_snapshot(
                    wid, bank,
                    channel_id=w.self_channel.channel_id,
                    channel_title=w.self_channel.title)
                if snap_id:
                    diff = kbh.compute_and_save_diff(
                        wid, w.self_channel.channel_id, snap_id, top_vang)
                    if diff:
                        log_fn(f"    [keyword] history: snapshot+diff (mới "
                               f"{len(diff['new'])}, mất {len(diff['lost'])}, "
                               f"đổi {len(diff['changed'])})")
                    else:
                        log_fn(f"    [keyword] history: snapshot baseline "
                               f"(lần đầu, chưa có diff)")
            except Exception as e:
                log_fn(f"    [keyword] history skip: {str(e)[:120]}")
            return {"ok": True}
        log_fn(f"    [keyword] kw_bank rỗng (chưa harvest seed cho WL này)")
        return {"ok": True, "reason": "empty_bank"}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:200]}


def stage_report(wid: str, log_fn, api_key: str = "",
                 token: str = "", chat: str = "") -> dict:
    """Khâu AI (gộp yt_manage_app 2026-06, Phase 5).

    Báo cáo serve ON-DEMAND qua API (build_data → JSON → React). Stage này
    chỉ còn nhiệm vụ SINH AI:
    - ai_analysis từng kênh (self 6 mục + đối thủ 3 mục) → lưu pkl.
    - strategy cho WL → wl.save_analysis.
    build_data đọc lại (self.ai / strategy) → tab "Kênh chính"/"Đối thủ"/
    "Chiến lược AI"/"Phản hồi AI".

    AI backend: Claude Code CLI (gói subscription, Opus — K9). Không tìm
    thấy claude.exe → skip, báo cáo vẫn serve data đã thu thập.
    """
    try:
        from . import watchlist as wl_mod, ai_insights
        from .auto_pipeline import generate_missing_ai, generate_strategy
        w = wl_mod.load_watchlist(wid)
        if not w:
            return {"ok": False, "reason": "wl_not_found"}
        if not ai_insights.cli_available():
            log_fn("    [ai] KHÔNG tìm thấy Claude CLI (claude.exe) — skip "
                   "khâu AI (báo cáo vẫn serve data đã thu thập).")
            return {"ok": True, "reason": "no_ai_backend"}
        cfg_api, model = "", ""

        # need_fresh = tất cả kênh active (self + đối thủ) → sinh AI tươi
        need = []
        sc = w.self_channel
        if sc:
            need.append({"channel_id": sc.channel_id, "title": sc.title,
                         "is_self": True, "previous_ai": ""})
        for c in w.competitor_channels:
            need.append({"channel_id": c.channel_id, "title": c.title,
                         "is_self": False, "previous_ai": ""})

        n = generate_missing_ai(need, cfg_api, model,
                                log_fn=lambda s: log_fn(f"      {s[:120]}"))
        generate_strategy(wid, cfg_api, model,
                          log_fn=lambda s: log_fn(f"      {s[:120]}"))
        try:
            from . import seo_report
            seo_report.generate(wid, log_fn=lambda s: log_fn(f"      {s[:120]}"))
        except Exception as e:
            log_fn(f"      ! Báo cáo SEO lỗi (skip): {str(e)[:120]}")
        log_fn(f"    [ai] OK — sinh AI {n}/{len(need)} kênh + strategy + SEO")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:200]}


# ============================================================
# Orchestrator
# ============================================================

async def process_one_wl(wid: str, run_id: str, conn,
                          api_key: str, token: str, chat: str,
                          log_fn=print):
    """5 stage cho 1 WL. Mỗi stage check state — skip nếu done."""
    from . import watchlist as wl_mod
    w = wl_mod.load_watchlist(wid)
    if not w:
        log_fn(f"❌ WL {wid} không tồn tại — skip")
        return
    log_fn(f"\n>>> [{w.name[:30]}] BẮT ĐẦU 5 stage <<<")
    t_wl = time.time()

    for stage in STAGES:
        st = _get_state(conn, run_id, wid, stage)
        # BUGFIX 24/05: "skipped" phải treat như "done" — không thì resume lần 2
        # sẽ re-run stage đã skip (đã có data trong pkl, mất công chạy lại).
        # Stage chỉ chạy lại khi state ∈ {None (chưa có), failed, running (treo)}
        if st in ("done", "skipped"):
            log_fn(f"  [{stage}] SKIP (state={st})")
            continue
        _set_state(conn, run_id, wid, stage, "running")
        try:
            if stage == "monitor":
                r = await stage_monitor(wid, log_fn)
            elif stage == "discover":
                r = stage_discover(wid, log_fn)
            elif stage == "socialblade":
                r = stage_socialblade(wid, log_fn)
            elif stage == "keyword":
                r = stage_keyword(wid, log_fn)
            elif stage == "report":
                r = stage_report(wid, log_fn, api_key, token, chat)
            else:
                r = {"ok": False, "reason": f"unknown_stage: {stage}"}
            status = "done" if r.get("ok") else "failed"
            _set_state(conn, run_id, wid, stage, status,
                       error=r.get("reason", ""))
        except Exception as e:
            _set_state(conn, run_id, wid, stage, "failed",
                       error=f"exception: {e}")
            log_fn(f"  [{stage}] ❌ EXCEPTION: {e}")
    log_fn(f">>> [{w.name[:30]}] XONG ({time.time()-t_wl:.0f}s) <<<")


async def _run_streaming_pipeline(wl_ids, run_id, conn, api_key, token, chat,
                                    anchor_map, log_fn):
    """24/05 STREAMING: spawn monitor_batch 1 lần cho all wls (dedup +
    priority) + watcher parse CHANNEL_DONE. Khi 1 WL đủ kênh xong →
    spawn post-monitor pipeline (discover→SB→inside→keyword→report).
    Pipeline song song giữa các WL — không phải chờ cả 25 WL monitor xong.

    Sort WL theo VIEW/NGÀY TB 7d của kênh chính (cao → thấp). Kênh
    quan trọng (nhiều view/ngày) chạy trước → báo cáo sớm cho user
    tier 1-2 (chốt 25/05 chiều). Anchor cụm vẫn ưu tiên trước member
    cùng cụm để discover share candidates.
    """
    import subprocess
    import asyncio as _asyncio
    from . import watchlist as wl_mod
    from .wl_clustering import _view_7d_for_wl

    # Cache view/7d cho mọi wl_id (gọi 1 lần)
    view_cache = {wid: _view_7d_for_wl(wid) for wid in wl_ids}

    # Sort: (-view/day kênh chính, 0 anchor / 1 member, wid)
    # → WL nhiều view nhất chạy trước, trong cùng cụm thì anchor trước
    def _sort_key(wid):
        anchor = anchor_map.get(wid, wid)
        is_anchor = (anchor == wid)
        # Cluster priority = max(view) của all WL trong cụm
        cluster_view = max(
            view_cache.get(w, 0) for w in wl_ids
            if anchor_map.get(w, w) == anchor)
        return (-cluster_view, 0 if is_anchor else 1, -view_cache.get(wid, 0), wid)
    wl_ids = sorted(wl_ids, key=_sort_key)
    log_fn(f"  Sort WL theo view/ngày kênh chính (top 5):")
    for wid in wl_ids[:5]:
        w = wl_mod.load_watchlist(wid)
        name = w.name if w else wid
        log_fn(f"    {name}: {view_cache.get(wid, 0):,.0f} view/day")

    # Build set channel_id cho mỗi WL → để track WL_READY
    wl_remaining = {}  # wid → set(channel_id) còn cần monitor
    for wid in wl_ids:
        wl = wl_mod.load_watchlist(wid)
        if not wl:
            continue
        wl_remaining[wid] = {c.channel_id for c in wl.active_channels
                             if c.channel_id}

    log_fn(f"\n=== STREAMING MODE — {len(wl_ids)} WL, "
           f"{sum(len(s) for s in wl_remaining.values())} channel tasks ===")

    # Spawn monitor_batch subprocess (background, capture stdout streaming)
    cmd = [sys.executable, "-X", "utf8", "-m",
           "python_backend.research.monitor_batch", "--workers", "6"] + wl_ids
    log_fn(f"Spawning monitor_batch dedup 6 worker...")
    proc = await _asyncio.create_subprocess_exec(
        *cmd, cwd=str(_REPO_ROOT),
        stdout=_asyncio.subprocess.PIPE,
        stderr=_asyncio.subprocess.STDOUT)

    # Track post-monitor tasks per WL
    pm_tasks = {}  # wid → asyncio.Task

    async def _post_monitor_for_wl(wid):
        """Pipeline sau monitor: discover → SB → inside → keyword → report.

        BUGFIX 24/05: WRAP stage_fn với asyncio.to_thread để KHÔNG block
        event loop. Trước đây subprocess.run trong stage_discover block
        15 phút → event loop kẹt → 2 WL khác không trigger WL_READY song
        song. Giờ mỗi stage chạy trong thread riêng → multiple WL có
        thể chạy post-monitor song song thật sự.
        """
        log_fn(f"\n>>> [POST-MONITOR] {wid}")
        _set_state(conn, run_id, wid, "monitor", "done")
        for stage_name, stage_fn in [
            ("discover", lambda: stage_discover(wid, log_fn)),
            ("socialblade", lambda: stage_socialblade(wid, log_fn)),
            ("keyword", lambda: stage_keyword(wid, log_fn)),
            ("report", lambda: stage_report(wid, log_fn,
                                            api_key, token, chat)),
        ]:
            st = _get_state(conn, run_id, wid, stage_name)
            if st in ("done", "skipped"):
                log_fn(f"  [{stage_name}] SKIP (state={st})")
                continue
            _set_state(conn, run_id, wid, stage_name, "running")
            try:
                # WRAP with to_thread — KHÔNG block event loop khi
                # stage_fn chạy subprocess.run synchronous
                r = await _asyncio.to_thread(stage_fn)
                status = "done" if r.get("ok") else "failed"
                _set_state(conn, run_id, wid, stage_name, status,
                           error=r.get("reason", ""))
            except Exception as e:
                _set_state(conn, run_id, wid, stage_name, "failed",
                           error=f"exception: {e}")

    # Parse monitor stdout streaming
    import re
    line_re = re.compile(
        r"CHANNEL_DONE cid=([^|]*)\|url=[^|]*\|wls=([^|]*)\|ok=(\d)")
    async for line_bytes in proc.stdout:
        line = line_bytes.decode("utf-8", errors="ignore").rstrip()
        if not line:
            continue
        # Echo log
        if "OK [" in line or "LOI [" in line or "===" in line[:5]:
            log_fn(f"  [mon] {line[:140]}")
        # Detect CHANNEL_DONE
        m = line_re.search(line)
        if m:
            cid, wls_str, ok = m.group(1), m.group(2), m.group(3)
            wls_of_ch = [w for w in wls_str.split(",") if w]
            # Mark monitor done for các WL chứa channel này
            for w in wls_of_ch:
                if w not in wl_remaining:
                    continue
                wl_remaining[w].discard(cid)
                if not wl_remaining[w] and w not in pm_tasks:
                    # WL đã đủ kênh xong → spawn post-monitor pipeline
                    log_fn(f"\n>>> [WL_READY] {w} (đủ kênh, "
                           f"spawn post-monitor)")
                    pm_tasks[w] = _asyncio.create_task(
                        _post_monitor_for_wl(w))

    # Đợi monitor subprocess xong
    rc = await proc.wait()
    log_fn(f"\nmonitor_batch finished rc={rc}")

    # Sau khi monitor xong, các WL còn lại (chưa đủ kênh do channel fail)
    # vẫn cần process — spawn post-monitor cho các WL chưa start
    for w in wl_ids:
        if w not in pm_tasks:
            log_fn(f">>> [WL_LATE] {w} (monitor không đủ — vẫn chạy "
                   f"post-monitor với data hiện có)")
            pm_tasks[w] = _asyncio.create_task(_post_monitor_for_wl(w))

    # Đợi tất cả post-monitor tasks
    if pm_tasks:
        await _asyncio.gather(*pm_tasks.values(), return_exceptions=True)
    log_fn(f"\n=== STREAMING DONE — {len(pm_tasks)} WL processed ===")


async def run_daily(wl_ids: Optional[list] = None,
                    run_id: Optional[str] = None,
                    resume: Optional[str] = None,
                    log_fn=print) -> str:
    """Main entry. Trả run_id để UI track progress.

    Args:
        wl_ids: list WL id. None = tất cả 25 WL.
        run_id: ID cho run này. None = tự sinh từ timestamp.
        resume: run_id cũ để resume. None = run mới.
    """
    from . import watchlist as wl_mod
    # Bỏ Telegram + API key: khâu AI dùng Claude CLI, báo cáo serve JSON.
    # Giữ 3 biến rỗng vì còn truyền xuống process_one_wl / streaming.
    api_key = token = chat = ""

    if wl_ids is None:
        # 25/05: skip WL paused (kênh chưa upload / chưa OAuth / tạm dừng)
        all_wls = wl_mod.list_watchlists()
        wl_ids = [w.id for w in all_wls if not getattr(w, "paused", False)]
        paused_n = sum(1 for w in all_wls if getattr(w, "paused", False))
        if paused_n > 0:
            print(f"  Skip {paused_n} WL paused (xem WL.paused=True trong "
                  f"JSON config).")
    if resume:
        run_id = resume
        log_fn(f"=== DAILY RUN RESUME: {run_id} ===")
    else:
        if run_id is None:
            run_id = "run_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        log_fn(f"=== DAILY RUN MỚI: {run_id}, {len(wl_ids)} WL ===")
    # Khâu AI mặc định dùng Claude Code CLI (gói subscription).
    try:
        from . import ai_insights
        _cli_on = ai_insights.cli_available()
    except Exception:
        _cli_on = False
    if _cli_on:
        log_fn(f"  Khâu AI: Claude CLI (Opus, gói subscription) — TỰ ĐỘNG")
    else:
        log_fn(f"  Khâu AI: KHÔNG tìm thấy claude.exe → skip sinh AI")

    # 24/05: gom cụm WL → discover anchor + member copy
    try:
        from .wl_clustering import compute_anchor_map, save_anchor_map
        anchor_map = compute_anchor_map()
        save_anchor_map(anchor_map)
        n_clusters = len(set(anchor_map.values()))
        log_fn(f"  Cụm WL: {len(anchor_map)} WL → {n_clusters} cụm "
               f"(stage discover sẽ chỉ chạy {n_clusters} lần)")
    except Exception as e:
        log_fn(f"  ⚠ Cluster compute err (skip): {e}")
        anchor_map = {}

    # Tùy chọn: harvest Keywordtool TRƯỚC runall (config run_keywordtool).
    try:
        from .config import load_config as _lc
        if _lc().get("run_keywordtool"):
            import asyncio as _aio
            from . import keyword_fetch
            log_fn("  [keywordtool] Harvest seed pending trước runall...")
            res = await _aio.to_thread(
                keyword_fetch.harvest_pending, 50,
                lambda m: log_fn(f"    {m}"))
            log_fn(f"  [keywordtool] Xong: {res.get('done', 0)} seed, "
                   f"+{res.get('keywords', 0)} từ khoá.")
    except Exception as e:
        log_fn(f"  [keywordtool] LỖI (skip): {str(e)[:160]}")

    t0 = time.time()
    conn = _init_db()
    try:
        # 24/05 BUGFIX: detect RESUME mode + all WL đã monitor xong
        # → đi path tuần tự (process_one_wl) để KHÔNG chạy lại monitor.
        # Streaming mode chỉ dùng khi MỚI bắt đầu (chưa có monitor done).
        all_monitored = all(
            _get_state(conn, run_id, wid, "monitor") in ("done", "skipped")
            for wid in wl_ids
        ) if resume else False

        if resume and all_monitored:
            log_fn(f"  RESUME mode + tất cả WL đã monitor done → chạy "
                   f"tuần tự per-WL (skip streaming monitor_batch)")
            for wid in wl_ids:
                await process_one_wl(wid, run_id, conn,
                                      api_key, token, chat, log_fn)
        else:
            # NEW RUN hoặc RESUME mà có WL chưa monitor → STREAMING
            # 1. Spawn monitor_batch DEDUP + PRIORITY
            # 2. Parse CHANNEL_DONE → trigger WL_READY
            # 3. asyncio.gather tất cả post-monitor tasks song song
            await _run_streaming_pipeline(
                wl_ids, run_id, conn, api_key, token, chat,
                anchor_map, log_fn)
        # Summary
        cur = conn.execute(
            """SELECT stage, status, COUNT(*) FROM wl_stage_state
               WHERE run_id=? GROUP BY stage, status
               ORDER BY stage, status""", (run_id,))
        log_fn(f"\n=== SUMMARY {run_id} ({time.time()-t0:.0f}s) ===")
        for stage, status, n in cur:
            log_fn(f"  {stage:12s} {status:8s} {n:>3}")

        # Snapshot báo cáo tổng hợp cuối run → lưu lịch sử (UI chọn date).
        # Dựng cho TẤT CẢ WL chưa paused để khớp view live, không chỉ wl_ids.
        try:
            from . import summary_report
            active = [w.id for w in wl_mod.list_watchlists()
                      if not getattr(w, "paused", False)]
            snap = summary_report.build_and_save_snapshot(active)
            log_fn(f"  [summary] Đã lưu snapshot báo cáo tổng hợp: {snap['id']}")
        except Exception as e:
            log_fn(f"  [summary] Lỗi lưu snapshot (skip): {str(e)[:160]}")

    finally:
        conn.close()
    return run_id


async def run_ai_only(wl_ids: Optional[list] = None,
                      run_id: Optional[str] = None,
                      log_fn=print) -> str:
    """Chỉ chạy khâu AI (stage_report) cho WL đã có data — KHÔNG monitor/Chrome.

    Gộp yt_manage_app 2026-06 (Phase 5): cho phép (tái) sinh AI cho 1 WL on-demand
    qua API mà không phải chạy lại full pipeline. Ghi state stage 'report' vào
    orchestrator.sqlite để UI theo dõi như run thường.
    """
    from . import watchlist as wl_mod
    if wl_ids is None:
        wl_ids = [w.id for w in wl_mod.list_watchlists()
                  if not getattr(w, "paused", False)]
    if run_id is None:
        run_id = "ai_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    log_fn(f"=== AI-ONLY RUN: {run_id}, {len(wl_ids)} WL ===")
    conn = _init_db()
    try:
        for wid in wl_ids:
            _set_state(conn, run_id, wid, "report", "running")
            try:
                r = stage_report(wid, log_fn)
                _set_state(conn, run_id, wid, "report",
                           "done" if r.get("ok") else "failed",
                           error=r.get("reason", ""))
            except Exception as e:
                _set_state(conn, run_id, wid, "report", "failed",
                           error=f"exception: {e}")
    finally:
        conn.close()
    return run_id


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = sys.argv[1:]
    resume = None
    wids = []
    for a in args:
        if a.startswith("--resume="):
            resume = a[9:]
        elif a.startswith("wl_"):
            wids.append(a)
    asyncio.run(run_daily(wl_ids=wids if wids else None, resume=resume))
