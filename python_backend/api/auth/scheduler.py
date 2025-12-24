import os
import subprocess
import sys
from datetime import datetime, time as dtime
from typing import Optional
from threading import Event, Thread

from python_backend.api.auth.database import SessionLocal
from python_backend.api.auth.models import UserSchedule, UserScheduleRun


_STOP_EVENT = Event()
_THREAD = None


def _kickoff_get_data(account_tag: Optional[str], env_extra: Optional[dict] = None) -> None:
    script_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "get_data.py")
    )
    if not os.path.exists(script_path):
        script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "python_backend", "get_data.py")
        )
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
    )
    if not os.path.exists(script_path):
        print(f"[WARN] get_data.py not found: {script_path}")
        return
    try:
        cmd = [sys.executable, script_path]
        if account_tag:
            cmd.append(account_tag)
        env = os.environ.copy()
        if env_extra:
            env.update(env_extra)
        subprocess.Popen(
            cmd,
            cwd=repo_root,
            env=env,
        )
    except Exception as e:
        print(f"[WARN] Failed to start get_data.py: {e}")


def _parse_time_of_day(value: str):
    if not value:
        return None
    try:
        parts = value.split(":")
        if len(parts) < 2:
            return None
        hour = int(parts[0])
        minute = int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        return dtime(hour=hour, minute=minute)
    except Exception:
        return None


def _should_run(schedule: UserSchedule, now: datetime) -> bool:
    if schedule.enabled != 1:
        return False

    last = schedule.last_run_at
    tod = _parse_time_of_day(schedule.time_of_day or "")
    if tod is None:
        return False
    today_at = datetime.combine(now.date(), tod)
    if now < today_at:
        return False
    if last is None:
        return True
    return last.date() < now.date()


def _run_loop():
    while not _STOP_EVENT.is_set():
        now = datetime.now()
        db = SessionLocal()
        try:
            rows = db.query(UserSchedule).all()
            for row in rows:
                if not _should_run(row, now):
                    continue
                token_base = os.path.splitext(os.path.basename(row.token_name or ""))[0]
                if token_base:
                    token_path = os.path.join("python_backend", "token", f"{token_base}.pickle")
                    if not os.path.exists(token_path):
                        continue
                row.last_run_at = now
                row.updated_at = now
                db.add(row)
                db.commit()

                run = UserScheduleRun(
                    user_id=row.user_id,
                    schedule_id=row.id,
                    status="running",
                    started_at=now,
                    processed=0,
                    total=0,
                    message="Started",
                )
                db.add(run)
                db.commit()
                db.refresh(run)
                _kickoff_get_data(
                    token_base or None,
                    env_extra={"SCHEDULE_RUN_ID": str(run.id)},
                )
        except Exception as e:
            print(f"[WARN] scheduler loop failed: {e}")
        finally:
            db.close()

        _STOP_EVENT.wait(30)


def start_scheduler():
    global _THREAD
    if _THREAD and _THREAD.is_alive():
        return
    _THREAD = Thread(target=_run_loop, daemon=True)
    _THREAD.start()


def stop_scheduler():
    _STOP_EVENT.set()
