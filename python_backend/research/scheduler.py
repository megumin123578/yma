"""
Tích hợp Windows Task Scheduler để chạy phần mềm tự động theo lịch.

Mỗi schedule = 1 Windows Task có tên dạng "FuntimeYouTubeResearch_<id>".
Khi đến giờ, Windows tự khởi động .exe với argument --run-schedule <id>.
Phần mềm khi khởi động thấy argument này sẽ chạy job được lưu trong schedule.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


TASK_PREFIX = "FuntimeYouTubeResearch_"


def schedules_dir() -> Path:
    d = Path.home() / ".youtube_research" / "schedules"
    d.mkdir(parents=True, exist_ok=True)
    return d


def schedules_index() -> Path:
    return schedules_dir() / "index.json"


def _load_index() -> list:
    p = schedules_index()
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_index(items: list) -> None:
    schedules_index().write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def list_schedules() -> list:
    return _load_index()


def _get_exe_path() -> str:
    """Trả đường dẫn .exe hoặc Python script để Task Scheduler gọi."""
    if getattr(sys, "frozen", False):
        return sys.executable
    # Dev mode: dùng pythonw + app.py
    app_py = str(Path(__file__).resolve().parent.parent / "app.py")
    pyw = sys.executable.replace("python.exe", "pythonw.exe")
    if not Path(pyw).exists():
        pyw = sys.executable
    return f'"{pyw}" "{app_py}"'


def _make_id(label: str) -> str:
    import re
    safe = re.sub(r"[^\w]+", "_", label).strip("_") or "task"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{safe[:30]}_{ts}"


def create_schedule(label: str, jobs: list, frequency: str,
                    time_hhmm: str, day_of_week: Optional[str] = None) -> str:
    """
    Tạo 1 schedule mới.
    frequency: "DAILY" hoặc "WEEKLY"
    time_hhmm: "07:30"
    day_of_week: "MON", "TUE", ... (chỉ dùng khi WEEKLY)

    Trả schedule_id.
    """
    sid = _make_id(label)
    pkl_path = schedules_dir() / f"{sid}.json"

    # Lưu cấu hình job
    cfg = {
        "id": sid,
        "label": label,
        "frequency": frequency,
        "time": time_hhmm,
        "day_of_week": day_of_week,
        "created": datetime.now().isoformat(timespec="seconds"),
        "jobs": jobs,  # list of job dicts {mode, display, params}
    }
    pkl_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2,
                                    default=str), encoding="utf-8")

    # Tạo Windows Task
    task_name = TASK_PREFIX + sid
    exe = _get_exe_path()
    # Argument để app biết là đang chạy theo schedule
    args = f' --run-schedule "{sid}"'
    if exe.startswith('"'):
        cmd = exe + args
    else:
        cmd = f'"{exe}"{args}'

    # schtasks /Create /TN ... /TR ... /SC DAILY /ST 07:30
    schtasks_args = [
        "schtasks", "/Create", "/F",  # /F = force overwrite
        "/TN", task_name,
        "/TR", cmd,
        "/SC", frequency,
        "/ST", time_hhmm,
    ]
    if frequency == "WEEKLY" and day_of_week:
        schtasks_args.extend(["/D", day_of_week])

    try:
        result = subprocess.run(schtasks_args, capture_output=True, text=True,
                                creationflags=0x08000000)  # no console window
        if result.returncode != 0:
            raise RuntimeError(
                f"schtasks lỗi: {result.stderr or result.stdout}")
    except FileNotFoundError:
        raise RuntimeError("Không tìm thấy schtasks - chỉ hỗ trợ Windows")

    # Thêm vào index
    items = _load_index()
    items.insert(0, {
        "id": sid, "label": label, "task_name": task_name,
        "frequency": frequency, "time": time_hhmm,
        "day_of_week": day_of_week,
        "job_count": len(jobs),
        "created": cfg["created"],
    })
    _save_index(items)
    return sid


def delete_schedule(sid: str) -> bool:
    """Xoá schedule + Windows task."""
    task_name = TASK_PREFIX + sid
    try:
        subprocess.run(["schtasks", "/Delete", "/F", "/TN", task_name],
                       capture_output=True, creationflags=0x08000000)
    except Exception:
        pass

    items = [e for e in _load_index() if e.get("id") != sid]
    _save_index(items)
    try:
        (schedules_dir() / f"{sid}.json").unlink(missing_ok=True)
    except Exception:
        pass
    return True


def load_schedule_jobs(sid: str) -> Optional[list]:
    """Đọc cấu hình job từ file."""
    p = schedules_dir() / f"{sid}.json"
    if not p.exists():
        return None
    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
        return cfg.get("jobs", [])
    except Exception:
        return None


def load_schedule_config(sid: str) -> Optional[dict]:
    """Đọc full config của 1 schedule (bao gồm watchlist_id nếu là monitor)."""
    p = schedules_dir() / f"{sid}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def create_monitor_schedule(label: str, watchlist_id: str,
                            watchlist_name: str,
                            frequency: str, time_hhmm: str,
                            day_of_week: Optional[str] = None) -> str:
    """
    Tạo schedule chạy MONITOR cho 1 watchlist.
    Khác create_schedule (research): dùng arg --monitor <wl_id>.

    Trả schedule_id.
    """
    sid = _make_id(label)
    cfg = {
        "id": sid,
        "type": "monitor",  # phân biệt với "research" mặc định
        "label": label,
        "watchlist_id": watchlist_id,
        "watchlist_name": watchlist_name,
        "frequency": frequency,
        "time": time_hhmm,
        "day_of_week": day_of_week,
        "created": datetime.now().isoformat(timespec="seconds"),
        "jobs": [],  # monitor không có jobs, chỉ có watchlist_id
    }
    (schedules_dir() / f"{sid}.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8")

    task_name = TASK_PREFIX + sid
    exe = _get_exe_path()
    args = f' --monitor "{watchlist_id}"'
    if exe.startswith('"'):
        cmd = exe + args
    else:
        cmd = f'"{exe}"{args}'

    schtasks_args = [
        "schtasks", "/Create", "/F",
        "/TN", task_name,
        "/TR", cmd,
        "/SC", frequency,
        "/ST", time_hhmm,
    ]
    if frequency == "WEEKLY" and day_of_week:
        schtasks_args.extend(["/D", day_of_week])

    try:
        result = subprocess.run(schtasks_args, capture_output=True, text=True,
                                creationflags=0x08000000)
        if result.returncode != 0:
            raise RuntimeError(
                f"schtasks lỗi: {result.stderr or result.stdout}")
    except FileNotFoundError:
        raise RuntimeError("Không tìm thấy schtasks - chỉ hỗ trợ Windows")

    # Thêm vào index với type='monitor'
    items = _load_index()
    items.insert(0, {
        "id": sid, "label": label, "task_name": task_name,
        "type": "monitor",
        "watchlist_id": watchlist_id,
        "watchlist_name": watchlist_name,
        "frequency": frequency, "time": time_hhmm,
        "day_of_week": day_of_week,
        "job_count": 1,  # 1 monitor job
        "created": cfg["created"],
    })
    _save_index(items)
    return sid
