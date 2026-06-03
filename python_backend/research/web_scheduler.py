# -*- coding: utf-8 -*-
"""Scheduler nền nhẹ cho research pipeline (gộp yt_manage_app, Phase 6).

Thay Windows Task Scheduler (scheduler.py — chạy .exe desktop) bằng 1 thread
nền trong FastAPI: mỗi 30s kiểm tra lịch JSON, đến giờ thì spawn worker chạy
daily run. Self-contained, không đụng scheduler auth có sẵn.

Lịch lưu ~/.youtube_research/web_schedule.json:
  {enabled, time:"HH:MM" (giờ máy), wlIds:[]|null, aiOnly:bool, lastRunDate}
"""
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

SCHED_FILE = Path.home() / ".youtube_research" / "web_schedule.json"

_DEFAULT = {"enabled": False, "time": "04:00", "wlIds": None,
            "aiOnly": False, "lastRunDate": ""}

_stop = threading.Event()
_thread: Optional[threading.Thread] = None


def load_schedule() -> dict:
    if SCHED_FILE.exists():
        try:
            d = json.loads(SCHED_FILE.read_text(encoding="utf-8"))
            return {**_DEFAULT, **d}
        except Exception:
            pass
    return dict(_DEFAULT)


def save_schedule(d: dict) -> dict:
    SCHED_FILE.parent.mkdir(parents=True, exist_ok=True)
    cur = load_schedule()
    cur.update({k: v for k, v in d.items() if k in _DEFAULT})
    SCHED_FILE.write_text(json.dumps(cur, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    return cur


def _loop(spawn_fn: Callable):
    while not _stop.wait(30):
        try:
            s = load_schedule()
            if not s.get("enabled"):
                continue
            now = datetime.now()
            if s.get("time") == now.strftime("%H:%M") and \
                    s.get("lastRunDate") != now.strftime("%Y-%m-%d"):
                save_schedule({"lastRunDate": now.strftime("%Y-%m-%d")})
                try:
                    spawn_fn(wl_ids=s.get("wlIds") or None,
                             ai_only=bool(s.get("aiOnly")))
                    print(f"[research scheduler] triggered daily run @ "
                          f"{s.get('time')}")
                except Exception as e:  # noqa: BLE001
                    print(f"[research scheduler] spawn loi: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"[research scheduler] loop loi: {e}")


def start(spawn_fn: Callable):
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, args=(spawn_fn,), daemon=True)
    _thread.start()


def stop():
    _stop.set()
