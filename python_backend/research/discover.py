# -*- coding: utf-8 -*-
"""BƯỚC 2: phát hiện & kết nạp đối thủ mới cho 1 watchlist. Bản port vào
python_backend/research (dùng research.discovery + research.persistence=PG).
KHÔNG còn phụ thuộc YT/project.

Dùng: python -m python_backend.research.discover <watchlist_id> [...]
(spawn từ repo root để python_backend importable).
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def discover_one(watchlist_id: str) -> dict:
    """Phát hiện & kết nạp đối thủ cho 1 watchlist. Trả dict (added/scanned/...)."""
    from python_backend.research import watchlist as wl_mod
    from python_backend.research import discovery
    from python_backend.research.config import load_config
    from python_backend.research.persistence import find_previous_for_channel

    wl = wl_mod.load_watchlist(watchlist_id)
    if not wl:
        print(f"  ! Khong tim thay watchlist {watchlist_id}")
        return {"added": [], "scanned": 0, "candidates": 0}
    self_ch = wl.self_channel
    if not self_ch:
        print(f"  ! Watchlist '{wl.name}' chua co kenh chinh")
        return {"added": [], "scanned": 0, "candidates": 0}
    main_result = find_previous_for_channel(self_ch.channel_id)
    if not main_result:
        print(f"  ! Chua co du lieu kenh chinh '{wl.name}' "
              f"- hay giam sat truoc.")
        return {"added": [], "scanned": 0, "candidates": 0}

    cfg = load_config()
    if not cfg.get("auto_discover_competitors", True):
        print("  ! Tinh nang phat hien doi thu dang TAT trong cau hinh.")
        return {"added": [], "scanned": 0, "candidates": 0}
    try:
        threshold = float(cfg.get("auto_discover_threshold", 50))
    except Exception:
        threshold = 50.0
    try:
        max_add = int(cfg.get("auto_discover_max", 5))
    except Exception:
        max_add = 5
    base_dir = cfg.get("output_dir") or str(_REPO_ROOT / "ket_qua")
    out_dir = str(Path(base_dir) / "giam_sat" / "doi_thu_moi")

    print(f"=== Phat hien doi thu: {wl.name} "
          f"(nguong trung {threshold:.0f}%) ===", flush=True)
    res = discovery.discover_and_recruit(
        watchlist_id, main_result, out_dir,
        chrome_mode=cfg.get("chrome_mode", "headless"),
        threshold_pct=threshold, max_add=max_add,
        max_scan=max(max_add * 2, 10),
        days=cfg.get("days", 7),
        top_keywords=cfg.get("top_keywords", 20),
        per_keyword=cfg.get("per_keyword", 10),
        max_channel_videos=cfg.get("max_channel_videos", 30),
        region=cfg.get("region") or None,
        log_fn=lambda m: print(f"  {m}", flush=True),
        cancel_event=None)
    added = res.get("added", [])
    if added:
        print(f"  => KET NAP {len(added)} kenh moi vao '{wl.name}':",
              flush=True)
        for a in added:
            print(f"     - {a['title']}  (channel_id={a['channel_id']}, "
                  f"trung {a['overlap_pct']:.0f}%)", flush=True)
    else:
        print("  => Khong kenh nao dat nguong - khong ket nap lan nay.",
              flush=True)
    return res


def main():
    if len(sys.argv) < 2:
        print("Dung: python -m python_backend.research.discover <watchlist_id> [...]")
        return
    for wid in sys.argv[1:]:
        discover_one(wid)
        print(flush=True)


if __name__ == "__main__":
    main()
