# get_data.py — PG-only runner
import os
import sys
import json
import sqlite3
import time
import tempfile
from datetime import datetime
from module_trafficsource import *
from module_content import *
from module_overall import *
from module_audience import run_audience_analytics
from module_reach import run_reach_analytics
from module_revenue import run_revenue_analytics
try:
    from python_backend.module_channel_daily import run_channel_daily
except ModuleNotFoundError:
    from module_channel_daily import run_channel_daily

try:
    import msvcrt
except ImportError:
    msvcrt = None

try:
    import fcntl
except ImportError:
    fcntl = None

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_TOKEN = os.path.join(REPO_ROOT, "python_backend", "token")

if os.path.exists(DEFAULT_TOKEN):
    TOKEN_FOLDER = DEFAULT_TOKEN

if not os.path.exists(TOKEN_FOLDER):
    fallback_token = os.path.join(os.path.dirname(__file__), "token")
    if os.path.exists(fallback_token):
        TOKEN_FOLDER = fallback_token


def _resolve_token_file(name: str) -> str:
    base = os.path.basename(name or "")
    if base.lower().endswith(".json"):
        base = base[:-5]
    if not base.lower().endswith(".pickle"):
        base = f"{base}.pickle"
    return base


def _resolve_token_list(raw_value: str):
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
        if isinstance(parsed, list):
            return [_resolve_token_file(str(item)) for item in parsed if str(item).strip()]
    except Exception:
        pass
    return [_resolve_token_file(item.strip()) for item in raw_value.split(",") if item.strip()]


def _progress_path(account_tag: str) -> str:
    progress_dir = os.path.join("python_backend", "progress")
    os.makedirs(progress_dir, exist_ok=True)
    return os.path.join(progress_dir, f"{account_tag}.json")


def _lock_path() -> str:
    lock_dir = os.path.join(tempfile.gettempdir(), "yt_manage_app")
    os.makedirs(lock_dir, exist_ok=True)
    return os.path.join(lock_dir, "get_data.lock")


def _write_progress(account_tag: str, stage: str, percent: int, status: str, message: str = "") -> None:
    payload = {
        "account_tag": account_tag,
        "stage": stage,
        "percent": percent,
        "status": status,
        "message": message,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    with open(_progress_path(account_tag), "w", encoding="utf-8") as f:
        json.dump(payload, f)


def _run_db_path() -> str:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.getenv("AUTH_DB_PATH", os.path.join(repo_root, "auth.db"))

def _get_selected_channel_id(account_tag: str) -> str:
    try:
        conn = sqlite3.connect(_run_db_path())
        cur = conn.cursor()
        cur.execute(
            """
            SELECT selected_channel_id
            FROM user_credentials
            WHERE account_tag = ? AND selected_channel_id IS NOT NULL AND selected_channel_id != ''
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (account_tag,),
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                """
                SELECT selected_channel_id
                FROM user_credentials
                WHERE account_tag = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (account_tag,),
            )
            row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return str(row[0])
    except Exception:
        pass
    return ""

def _update_schedule_run(status: str, processed=None, total=None, message: str = "") -> None:
    run_id = os.getenv("SCHEDULE_RUN_ID")
    if not run_id:
        return
    try:
        conn = sqlite3.connect(_run_db_path())
        cur = conn.cursor()
        finished_at = None
        if status in {"done", "error", "empty", "stopped"}:
            finished_at = datetime.now().isoformat(sep=" ")
        cur.execute(
            """
            UPDATE user_schedule_runs
            SET status = ?,
                processed = COALESCE(?, processed),
                total = COALESCE(?, total),
                message = ?,
                finished_at = COALESCE(?, finished_at)
            WHERE id = ?
            """,
            (status, processed, total, message, finished_at, int(run_id)),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _stop_requested() -> bool:
    run_id = os.getenv("SCHEDULE_RUN_ID")
    if not run_id:
        return False
    try:
        conn = sqlite3.connect(_run_db_path())
        cur = conn.cursor()
        cur.execute(
            "SELECT status FROM user_schedule_runs WHERE id = ?",
            (int(run_id),),
        )
        row = cur.fetchone()
        conn.close()
        if row and row[0] in {"stopping", "stopped", "canceled"}:
            return True
    except Exception:
        return False
    return False


def _raise_if_stop_requested(account_tag: str, stage: str) -> None:
    if not _stop_requested():
        return
    _write_progress(account_tag, stage, 0, "stopped", "Stopped by admin")
    _update_schedule_run("stopped", 0, 0, "Stopped by admin")
    raise RuntimeError("Stop requested")


def _try_lock_handle(handle) -> bool:
    try:
        if msvcrt is not None:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
    except OSError:
        return False
    return True


def _unlock_handle(handle) -> None:
    try:
        if msvcrt is not None:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


class _RunLock:
    def __init__(self, account_tag: str):
        self.account_tag = account_tag
        self.handle = None

    def __enter__(self):
        self.handle = open(_lock_path(), "a+", encoding="utf-8")
        self.handle.seek(0, os.SEEK_END)
        if self.handle.tell() == 0:
            self.handle.write(" ")
            self.handle.flush()
        poll_seconds = float(os.getenv("GET_DATA_LOCK_POLL_SECONDS", "2"))
        wait_message = "Waiting for current run to finish"
        while True:
            if _try_lock_handle(self.handle):
                self.handle.seek(0)
                self.handle.truncate()
                json.dump(
                    {
                        "pid": os.getpid(),
                        "account_tag": self.account_tag,
                        "run_id": os.getenv("SCHEDULE_RUN_ID"),
                        "locked_at": datetime.utcnow().isoformat() + "Z",
                    },
                    self.handle,
                )
                self.handle.flush()
                return self
            if self.account_tag:
                _write_progress(self.account_tag, "queued", 0, "queued", wait_message)
            _update_schedule_run("queued", None, None, wait_message)
            if _stop_requested():
                if self.account_tag:
                    _write_progress(self.account_tag, "stopped", 0, "stopped", "Stopped by admin")
                _update_schedule_run("stopped", None, None, "Stopped by admin")
                raise RuntimeError("Stop requested")
            time.sleep(poll_seconds)

    def __exit__(self, exc_type, exc, tb):
        if self.handle is not None:
            _unlock_handle(self.handle)
            self.handle.close()

def _run_for_credential(cred_file: str) -> None:
    account_tag = os.path.splitext(os.path.basename(cred_file))[0]
    channel_id = _get_selected_channel_id(account_tag)
    if not channel_id:
        _write_progress(
            account_tag,
            "waiting_channel",
            0,
            "idle",
            "Select a channel before running.",
        )
        return
    stage = (os.getenv("RUN_STAGE") or "").strip().lower()
    if stage:
        _raise_if_stop_requested(account_tag, "stopped")
        _update_schedule_run("running", 0, 1, f"Starting {stage}")
        _write_progress(account_tag, stage, 10, "running", f"Starting {stage}")
        if stage == "content":
            process_content(cred_file, channel_id=channel_id)
        elif stage == "content_full":
            process_content(cred_file, channel_id=channel_id, force_full_backfill=True)
        elif stage == "overview":
            process_overall(cred_file, channel_id=channel_id)
        elif stage == "audience":
            pg_url = os.getenv("PG_URL")
            if not pg_url:
                raise RuntimeError("Missing PG_URL env var")
            creds = create_token_from_credentials(os.path.join(TOKEN_FOLDER, cred_file))
            run_audience_analytics(creds, account_tag, pg_url, channel_id=channel_id)
        elif stage == "reach":
            pg_url = os.getenv("PG_URL")
            if not pg_url:
                raise RuntimeError("Missing PG_URL env var")
            creds = create_token_from_credentials(os.path.join(TOKEN_FOLDER, cred_file))
            run_reach_analytics(creds, account_tag, pg_url, channel_id=channel_id)
        elif stage == "traffic_source":
            process_one(cred_file, channel_id=channel_id)
        elif stage == "revenue":
            pg_url = os.getenv("PG_URL")
            if not pg_url:
                raise RuntimeError("Missing PG_URL env var")
            creds = create_token_from_credentials(os.path.join(TOKEN_FOLDER, cred_file))
            run_revenue_analytics(creds, account_tag, pg_url, channel_id=channel_id)
        elif stage == "subscribers":
            pg_url = os.getenv("PG_URL")
            if not pg_url:
                raise RuntimeError("Missing PG_URL env var")
            creds = create_token_from_credentials(os.path.join(TOKEN_FOLDER, cred_file))
            run_channel_daily(creds, account_tag, pg_url, channel_id=channel_id)
        else:
            raise RuntimeError(f"Unsupported stage: {stage}")
        _raise_if_stop_requested(account_tag, "stopped")
        _update_schedule_run("running", 1, 1, f"Completed {stage}")
        _write_progress(account_tag, "done", 100, "done", f"Completed {stage}")
        return
    _raise_if_stop_requested(account_tag, "stopped")
    _write_progress(account_tag, "traffic_source", 5, "running", "Starting traffic source")
    _update_schedule_run("running", 0, 6, "Traffic source")
    process_one(cred_file, channel_id=channel_id)
    _update_schedule_run("running", 1, 6, "Traffic source")
    _raise_if_stop_requested(account_tag, "stopped")
    _write_progress(account_tag, "content", 35, "running", "Starting content fetch")
    _update_schedule_run("running", 1, 6, "Content")
    process_content(cred_file, channel_id=channel_id)
    _update_schedule_run("running", 2, 6, "Content")
    _raise_if_stop_requested(account_tag, "stopped")
    _write_progress(account_tag, "overview", 60, "running", "Starting overview")
    _update_schedule_run("running", 2, 6, "Overview")
    process_overall(cred_file, channel_id=channel_id)
    _update_schedule_run("running", 3, 6, "Overview")
    _raise_if_stop_requested(account_tag, "stopped")
    _write_progress(account_tag, "audience", 80, "running", "Starting audience analytics")
    _update_schedule_run("running", 3, 7, "Audience")
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        raise RuntimeError("Missing PG_URL env var")
    creds = create_token_from_credentials(os.path.join(TOKEN_FOLDER, cred_file))
    run_audience_analytics(creds, account_tag, pg_url, channel_id=channel_id)
    _update_schedule_run("running", 4, 7, "Audience")
    _raise_if_stop_requested(account_tag, "stopped")
    _write_progress(account_tag, "reach", 90, "running", "Starting reach analytics")
    _update_schedule_run("running", 4, 7, "Reach")
    run_reach_analytics(creds, account_tag, pg_url, channel_id=channel_id)
    _update_schedule_run("running", 5, 7, "Reach")
    _raise_if_stop_requested(account_tag, "stopped")
    _write_progress(account_tag, "revenue", 95, "running", "Starting revenue analytics")
    _update_schedule_run("running", 5, 7, "Revenue")
    run_revenue_analytics(creds, account_tag, pg_url, channel_id=channel_id)
    _update_schedule_run("running", 6, 7, "Revenue")
    _raise_if_stop_requested(account_tag, "stopped")
    _write_progress(account_tag, "subscribers", 98, "running", "Starting subscriber analytics")
    _update_schedule_run("running", 6, 7, "Subscribers")
    run_channel_daily(creds, account_tag, pg_url, channel_id=channel_id)
    _update_schedule_run("running", 7, 7, "Subscribers")
    _write_progress(account_tag, "done", 100, "done", "Completed")


def main():
    os.makedirs(TOKEN_FOLDER, exist_ok=True)

    target_arg = sys.argv[1] if len(sys.argv) > 1 else ""
    env_token_names = _resolve_token_list(os.getenv("RUN_TOKEN_NAMES", ""))

    token_files = [f for f in os.listdir(TOKEN_FOLDER) if f.endswith(".pickle")]
    if env_token_names:
        token_files = [name for name in env_token_names if name in token_files]

    if target_arg:
        cred_file = _resolve_token_file(target_arg)
        token_path = os.path.join(TOKEN_FOLDER, cred_file)
        account_tag = os.path.splitext(os.path.basename(cred_file))[0]
        if not os.path.exists(token_path):
            _write_progress(account_tag, "error", 0, "error", "Token not found")
            print(f"Token not found: {cred_file}")
            return
        try:
            with _RunLock(account_tag):
                _update_schedule_run("running", 0, 1, "Processing 1 account")
                _run_for_credential(cred_file)
                _update_schedule_run("done", 1, 1, "Completed")
        except Exception as e:
            if str(e) == "Stop requested":
                _write_progress(account_tag, "stopped", 0, "stopped", "Stopped by admin")
                _update_schedule_run("stopped", 0, 1, "Stopped by admin")
                return
            _write_progress(account_tag, "error", 0, "error", str(e))
            _update_schedule_run("error", 0, 1, str(e))
            raise
        return

    if not token_files:
        print("No tokens found. Nothing to process.")
        _update_schedule_run("empty", 0, 0, "No tokens found.")
        return

    total = len(token_files)
    ok = 0
    print(f"Processing {total} token(s)...")
    first_account_tag = os.path.splitext(os.path.basename(token_files[0]))[0]
    with _RunLock(first_account_tag):
        _update_schedule_run("running", 0, total, "Processing tokens")
        for token_file in token_files:
            account_tag = os.path.splitext(os.path.basename(token_file))[0]
            cred_file = _resolve_token_file(token_file)
            try:
                _run_for_credential(cred_file)
                ok += 1
                _update_schedule_run("running", ok, total, f"Processed {ok}/{total}")
            except Exception as e:
                if str(e) == "Stop requested":
                    _write_progress(account_tag, "stopped", 0, "stopped", "Stopped by admin")
                    _update_schedule_run("stopped", ok, total, "Stopped by admin")
                    break
                _write_progress(account_tag, "error", 0, "error", str(e))
                _update_schedule_run("error", ok, total, str(e))
                break
        if ok == total:
            _update_schedule_run("done", ok, total, "Completed")

if __name__ == "__main__":
    main()
