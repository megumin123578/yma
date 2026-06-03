# -*- coding: utf-8 -*-
"""Worker process — chạy daily_orchestrator (data collection) NGOÀI process FastAPI.

Gộp yt_manage_app 2026-06 (Phase 3): API spawn module này như subprocess riêng
để cách ly asyncio + Chrome khỏi web server. Tiến trình ghi state vào
~/.youtube_research/orchestrator.sqlite; API đọc lại qua get_progress(run_id).

Chạy:
    python -m python_backend.research.run_pipeline --run-id run_xxx [--wl id1,id2] [--resume run_xxx]
Không có --wl  -> tất cả WL chưa paused.
"""
import argparse
import asyncio
import sys

from python_backend.research.daily_orchestrator import run_ai_only, run_daily


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--wl", default="", help="danh sách wl_id, phân tách dấu phẩy")
    ap.add_argument("--resume", default=None)
    ap.add_argument("--ai-only", action="store_true",
                    help="chỉ sinh AI (không monitor/Chrome) cho các WL")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    wl_ids = [s.strip() for s in args.wl.split(",") if s.strip()] or None
    if args.ai_only:
        run_id = asyncio.run(run_ai_only(wl_ids=wl_ids, run_id=args.run_id))
    else:
        run_id = asyncio.run(run_daily(wl_ids=wl_ids, run_id=args.run_id,
                                       resume=args.resume))
    print(f"PIPELINE_DONE run_id={run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
