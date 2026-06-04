# -*- coding: utf-8 -*-
"""BƯỚC 1 (gộp nhiều WL): giám sát đầy đủ nhiều watchlist trong 1 pool worker
song song. Bản port vào python_backend/research (ghi snapshot qua
research.persistence = Postgres). KHÔNG còn phụ thuộc YT/project.

Dùng: python -m python_backend.research.monitor_batch <wid_1> ... [--workers N]
(spawn từ repo root để python_backend importable trong process con).
"""
import os
import sys
import threading
import time
import traceback
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# research -> python_backend -> repo_root (cho process con của ProcessPool)
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def research_one(args):
    """Process con: nghiên cứu đầy đủ 1 kênh + lưu snapshot. args=(wid, idx, url, params)."""
    wid, idx, url, params = args
    try:
        from python_backend.research.researcher import run_research, safe_filename
        from python_backend.research.persistence import (
            save_result, find_previous_for_channel)
        from python_backend.research.delta import compute_delta
        out_dir = params["out_dir"]
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(
            out_dir, f"wl_{safe_filename(url)[:30]}_{ts}.xlsx")
        result = run_research(
            channel_url=url, output_path=out_path,
            days=params["days"], top_keywords=params["top_keywords"],
            per_keyword=params["per_keyword"],
            max_channel_videos=params["max_channel_videos"],
            chrome_mode=params["chrome_mode"], region=params["region"],
            log_fn=lambda m: None, progress_fn=lambda *a: None)
        ch = result.get("channel")
        cid = getattr(ch, "channel_id", "") if ch else ""
        try:
            prev = find_previous_for_channel(cid) if cid else None
            if prev:
                result["delta"] = compute_delta(result, prev)
        except Exception:
            pass
        job_id = save_result(result)
        return {"ok": True, "wid": wid, "idx": idx, "url": url,
                "job_id": job_id, "channel_id": cid,
                "title": getattr(ch, "title", "") if ch else "",
                "subs": getattr(ch, "subscriber_count", 0) if ch else 0}
    except Exception as e:
        return {"ok": False, "wid": wid, "idx": idx, "url": url,
                "error": f"{e}", "tb": traceback.format_exc()}


def main():
    if len(sys.argv) < 2:
        print("Dung: python -m python_backend.research.monitor_batch "
              "<wid_1> [wid_2 ...] [--workers N]")
        return
    args = sys.argv[1:]
    n_workers = 6
    if "--workers" in args:
        i = args.index("--workers")
        try:
            n_workers = int(args[i + 1])
            del args[i:i + 2]
        except (IndexError, ValueError):
            print("LOI: --workers can theo so nguyen")
            return
    wids = args
    if not wids:
        print("LOI: phai co it nhat 1 watchlist_id")
        return

    from python_backend.research.config import load_config
    from python_backend.research import watchlist as wl_mod
    from python_backend.research import monitor as monitor_mod
    from python_backend.research import persistence
    from python_backend.research import refreshers
    from python_backend.research.daily_orchestrator import _compute_view_7d_avg
    cfg = load_config()
    params = {
        "days": cfg.get("days", 7),
        "top_keywords": cfg.get("top_keywords", 20),
        "per_keyword": cfg.get("per_keyword", 10),
        "max_channel_videos": cfg.get("max_channel_videos", 30),
        "chrome_mode": cfg.get("chrome_mode", "headless"),
        "region": cfg.get("region") or None,
        "out_dir": cfg.get("output_dir") or "ket_qua",
    }

    # GỘP CHUNG kênh tất cả WL vào 1 pool DEDUP (1 channel ở nhiều WL → cào 1
    # lần). Priority: kênh thuộc WL có self_channel view/7d cao nhất xếp đầu.
    wl_map = {}
    channel_to_wls = {}
    channel_to_cid = {}
    wl_priority = {}

    print("=== Cac watchlist se giam sat ===", flush=True)
    for wid in wids:
        wl = wl_mod.load_watchlist(wid)
        if not wl or not wl.channels:
            print(f"  ! {wid} rong/khong ton tai - bo qua")
            continue
        wl_map[wid] = wl
        try:
            sc = wl.self_channel
            v7 = 0.0
            if sc and sc.channel_id:
                recs = persistence.records_for_channel(sc.channel_id)
                if recs:
                    d = persistence.load_result(recs[0]["id"])
                    if d:
                        v7 = _compute_view_7d_avg(d.get("socialblade") or {})
            wl_priority[wid] = v7
        except Exception:
            wl_priority[wid] = 0.0
        active_chs = wl.active_channels
        n_dup = 0
        for c in active_chs:
            if c.url in channel_to_wls:
                channel_to_wls[c.url].append(wid)
                n_dup += 1
            else:
                channel_to_wls[c.url] = [wid]
                channel_to_cid[c.url] = c.channel_id
        n_arch = len(wl.channels) - len(active_chs)
        notes = []
        if n_arch:
            notes.append(f"+{n_arch} archived")
        if n_dup:
            notes.append(f"+{n_dup} dup")
        note_s = f" ({', '.join(notes)})" if notes else ""
        print(f"  - {wl.name} ({len(active_chs)} kenh active{note_s}) "
              f"prio_view7d={int(wl_priority[wid]):,}", flush=True)

    if not channel_to_wls:
        print("Khong co task nao de chay")
        return

    def _ch_prio(url):
        return max(wl_priority.get(w, 0) for w in channel_to_wls[url])
    sorted_urls = sorted(channel_to_wls.keys(), key=lambda u: -_ch_prio(u))

    tasks = []
    for i, url in enumerate(sorted_urls):
        primary_wid = channel_to_wls[url][0]
        tasks.append((primary_wid, i, url, params))
    total_chans = len(tasks)
    total_dup = sum(len(wls) - 1 for wls in channel_to_wls.values())
    print(f"\n=== DEDUP: {total_chans} kenh unique "
          f"(tiet kiem {total_dup} lan cao trung) ===", flush=True)
    print(f"\n=== Giam sat GOI: {len(wl_map)} watchlist, "
          f"{total_chans} kenh, {n_workers} luong ===", flush=True)
    t0 = time.time()

    # Thread phụ SocialBlade SONG SONG với YouTube monitor (Trends chạy sau).
    stop_event = threading.Event()

    def _sb_loop():
        while not stop_event.is_set():
            for wid in list(wl_map.keys()):
                if stop_event.is_set():
                    break
                try:
                    refreshers.refresh_socialblade_for_watchlist(
                        wid, log_fn=lambda m: None)
                except Exception as e:
                    print(f"  [SB-thread] {wid} LOI: {e}", flush=True)
            if stop_event.wait(20):
                break

    sb_thread = threading.Thread(target=_sb_loop, daemon=True,
                                 name="sb-refresh-batch")
    sb_thread.start()
    print("  [parallel] Spawn 1 thread phu SocialBlade song song", flush=True)

    results_by_wid = defaultdict(list)
    done = 0
    with ProcessPoolExecutor(max_workers=n_workers) as ex:
        futs = {ex.submit(research_one, t): t for t in tasks}
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            wname = (wl_map[r["wid"]].name
                     if r["wid"] in wl_map else r["wid"])
            if r["ok"]:
                print(f"  ({done}/{total_chans}) OK [{wname}]: "
                      f"{r['title']} ({r['subs']:,} subs)", flush=True)
            else:
                print(f"  ({done}/{total_chans}) LOI [{wname}] "
                      f"{r['url']}: {r['error']}", flush=True)
            wls_using = channel_to_wls.get(r["url"], [r["wid"]])
            cid = r.get("channel_id") or channel_to_cid.get(r["url"], "")
            print(f"CHANNEL_DONE cid={cid}|url={r['url']}|"
                  f"wls={','.join(wls_using)}|ok={int(bool(r['ok']))}",
                  flush=True)
            for w in wls_using:
                results_by_wid[w].append(r)

    print("\n--- Phat hien su kien + cap nhat tung WL ---", flush=True)
    for wid, results in results_by_wid.items():
        wl = wl_map.get(wid)
        if not wl:
            continue
        n_ev = 0
        for r in results:
            if not r["ok"] or not r.get("channel_id"):
                continue
            try:
                res = persistence.load_result(r["job_id"])
                if res:
                    ev = monitor_mod.detect_events_from_research_result(wid, res)
                    n_ev += len(ev or [])
            except Exception as e:
                print(f"  ! detect events loi [{wl.name}]: {e}", flush=True)
        wl_mod.update_last_monitored(wid)
        try:
            title_map = {r["channel_id"]: r["title"] for r in results
                         if r.get("ok") and r.get("channel_id") and r.get("title")}
            wl2 = wl_mod.load_watchlist(wid)
            changed = False
            for c in wl2.channels:
                nt = title_map.get(c.channel_id)
                if nt and nt != c.title:
                    c.title = nt
                    changed = True
            sc = wl2.self_channel
            if sc and sc.title and wl2.name != sc.title:
                print(f"  doi ten WL: {wl2.name} -> {sc.title}", flush=True)
                wl2.name = sc.title
                changed = True
            if changed:
                wl_mod.save_watchlist(wl2)
        except Exception as e:
            print(f"  ! cap nhat ten loi: {e}", flush=True)
        ok_count = sum(1 for r in results if r["ok"])
        print(f"  '{wl.name}': {ok_count}/{len(results)} OK, {n_ev} su kien",
              flush=True)

    elapsed = time.time() - t0
    total_ok = sum(1 for rs in results_by_wid.values() for r in rs if r["ok"])
    total_fail = total_chans - total_ok
    print(f"\n=== TONG: {total_ok}/{total_chans} kenh OK, {total_fail} loi, "
          f"{elapsed:.0f}s (~{elapsed/60:.1f} phut) ===", flush=True)

    print("\n--- Stop SB background thread ---", flush=True)
    stop_event.set()
    sb_thread.join(timeout=10)

    print(f"\n=== FINAL PASS: FILL SOCIAL BLADE ({len(wl_map)} WL) ===",
          flush=True)
    for wid in wl_map:
        try:
            refreshers.refresh_socialblade_for_watchlist(
                wid, log_fn=lambda m: None)
        except Exception as e:
            print(f"  ! SocialBlade {wid} loi: {e}", flush=True)

    grand_total = time.time() - t0
    print(f"\n=== GRAND TOTAL: {grand_total:.0f}s "
          f"(~{grand_total/60:.1f} phut) ===", flush=True)


if __name__ == "__main__":
    main()
