# get_data.py — PG-only runner
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import sys
import json
import sqlite3
import time
import tempfile
from datetime import datetime
try:
    from python_backend.config import load_env
except ModuleNotFoundError:
    from config import load_env

load_env()

try:
    from python_backend.google_api_quota import enable_google_api_quota_guard
except ModuleNotFoundError:
    from google_api_quota import enable_google_api_quota_guard

enable_google_api_quota_guard()

try:
    from python_backend.progress_state import write_progress
except ModuleNotFoundError:
    from progress_state import write_progress
try:
    from python_backend.token_store import (
        account_tag_from_token_name,
        list_token_names,
        TokenCredentialsError,
        TokenRefreshFailed,
        token_exists,
        token_name_from_ref,
    )
except ModuleNotFoundError:
    from token_store import (
        account_tag_from_token_name,
        list_token_names,
        TokenCredentialsError,
        TokenRefreshFailed,
        token_exists,
        token_name_from_ref,
    )
try:
    from python_backend.module_content import ContentChannelAccessError
except ModuleNotFoundError:
    from module_content import ContentChannelAccessError
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
    from python_backend.module_thumbnail_reach import run_thumbnail_reach_sync
except ModuleNotFoundError:
    from module_thumbnail_reach import run_thumbnail_reach_sync

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
    return token_name_from_ref(name)


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

def _sanitize_lock_name(value: str) -> str:
    raw = os.path.basename((value or "").strip()) or "global"
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in raw)


def _lock_path(account_tag: str = "") -> str:
    lock_dir = os.path.join(tempfile.gettempdir(), "yt_manage_app")
    os.makedirs(lock_dir, exist_ok=True)
    return os.path.join(lock_dir, f"get_data.{_sanitize_lock_name(account_tag)}.lock")


def _max_parallel_workers() -> int:
    raw_value = str(os.getenv("GET_DATA_MAX_PARALLEL", "2") or "").strip()
    try:
        value = int(raw_value)
    except Exception:
        value = 1
    return max(1, min(value, 8))


def _run_db_path() -> str:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.getenv("AUTH_DB_PATH", os.path.join(repo_root, "auth.db"))


def _connect_auth_db():
    conn = sqlite3.connect(_run_db_path(), timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn

def _get_selected_channel_id(account_tag: str) -> str:
    try:
        conn = _connect_auth_db()
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
    attempts = 3
    final_statuses = {"done", "error", "empty", "stopped", "canceled"}
    for attempt in range(attempts):
        conn = None
        try:
            conn = _connect_auth_db()
            cur = conn.cursor()
            cur.execute(
                "SELECT status FROM user_schedule_runs WHERE id = ?",
                (int(run_id),),
            )
            row = cur.fetchone()
            current_status = str(row[0] or "").strip().lower() if row else ""
            next_status = str(status or "").strip().lower()
            if current_status in final_statuses and current_status != next_status:
                return

            finished_at = None
            if next_status in final_statuses:
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
            return
        except Exception as exc:
            message_text = str(exc).lower()
            if "locked" in message_text and attempt < attempts - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            return
        finally:
            if conn is not None:
                conn.close()


def _has_aggregate_token_scope() -> bool:
    return bool(_resolve_token_list(os.getenv("RUN_TOKEN_NAMES", "")))


def _stop_requested() -> bool:
    run_id = os.getenv("SCHEDULE_RUN_ID")
    if not run_id:
        return False
    try:
        conn = _connect_auth_db()
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
    write_progress(account_tag, stage, 0, "stopped", "Stopped by admin")
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
        self.handle = open(_lock_path(self.account_tag), "a+", encoding="utf-8")
        self.handle.seek(0, os.SEEK_END)
        if self.handle.tell() == 0:
            self.handle.write(" ")
            self.handle.flush()
        poll_seconds = float(os.getenv("GET_DATA_LOCK_POLL_SECONDS", "2"))
        wait_message = (
            f"Waiting for current run of {self.account_tag} to finish"
            if self.account_tag
            else "Waiting for current run to finish"
        )
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
                write_progress(self.account_tag, "queued", 0, "queued", wait_message)
            _update_schedule_run("queued", None, None, wait_message)
            if _stop_requested():
                if self.account_tag:
                    write_progress(self.account_tag, "stopped", 0, "stopped", "Stopped by admin")
                _update_schedule_run("stopped", None, None, "Stopped by admin")
                raise RuntimeError("Stop requested")
            time.sleep(poll_seconds)

    def __exit__(self, exc_type, exc, tb):
        if self.handle is not None:
            _unlock_handle(self.handle)
            self.handle.close()


def _run_credential_with_lock(cred_file: str) -> str:
    account_tag = account_tag_from_token_name(cred_file)
    with _RunLock(account_tag):
        _run_for_credential(cred_file)
    return account_tag

def _run_for_credential(cred_file: str) -> None:
    account_tag = account_tag_from_token_name(cred_file)
    aggregate_run = _has_aggregate_token_scope()
    channel_id = _get_selected_channel_id(account_tag)
    if not channel_id:
        write_progress(
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
        _update_schedule_run(
            "running",
            None if aggregate_run else 0,
            None if aggregate_run else 1,
            f"Starting {stage}{f' ({account_tag})' if aggregate_run else ''}",
        )
        write_progress(account_tag, stage, 10, "running", f"Starting {stage}")
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
        elif stage == "thumbnail_reach":
            pg_url = os.getenv("PG_URL")
            if not pg_url:
                raise RuntimeError("Missing PG_URL env var")
            creds = create_token_from_credentials(os.path.join(TOKEN_FOLDER, cred_file))
            run_thumbnail_reach_sync(
                creds,
                account_tag,
                pg_url,
                channel_id=channel_id,
                token_name=cred_file,
            )
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
        _update_schedule_run(
            "running",
            None if aggregate_run else 1,
            None if aggregate_run else 1,
            f"Completed {stage}{f' ({account_tag})' if aggregate_run else ''}",
        )
        write_progress(account_tag, "done", 100, "done", f"Completed {stage}")
        return
    _raise_if_stop_requested(account_tag, "stopped")
    write_progress(account_tag, "traffic_source", 5, "running", "Starting traffic source")
    _update_schedule_run(
        "running",
        None if aggregate_run else 0,
        None if aggregate_run else 8,
        f"Traffic source{f' ({account_tag})' if aggregate_run else ''}",
    )
    process_one(cred_file, channel_id=channel_id)
    _update_schedule_run(
        "running",
        None if aggregate_run else 1,
        None if aggregate_run else 8,
        f"Traffic source{f' ({account_tag})' if aggregate_run else ''}",
    )
    _raise_if_stop_requested(account_tag, "stopped")
    write_progress(account_tag, "content", 35, "running", "Starting content fetch")
    _update_schedule_run(
        "running",
        None if aggregate_run else 1,
        None if aggregate_run else 8,
        f"Content{f' ({account_tag})' if aggregate_run else ''}",
    )
    process_content(cred_file, channel_id=channel_id)
    _update_schedule_run(
        "running",
        None if aggregate_run else 2,
        None if aggregate_run else 8,
        f"Content{f' ({account_tag})' if aggregate_run else ''}",
    )
    _raise_if_stop_requested(account_tag, "stopped")
    write_progress(account_tag, "thumbnail_reach", 55, "running", "Starting thumbnail reach")
    _update_schedule_run(
        "running",
        None if aggregate_run else 2,
        None if aggregate_run else 8,
        f"Thumbnail reach{f' ({account_tag})' if aggregate_run else ''}",
    )
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        raise RuntimeError("Missing PG_URL env var")
    creds = create_token_from_credentials(os.path.join(TOKEN_FOLDER, cred_file))
    run_thumbnail_reach_sync(
        creds,
        account_tag,
        pg_url,
        channel_id=channel_id,
        token_name=cred_file,
    )
    _update_schedule_run(
        "running",
        None if aggregate_run else 3,
        None if aggregate_run else 8,
        f"Thumbnail reach{f' ({account_tag})' if aggregate_run else ''}",
    )
    _raise_if_stop_requested(account_tag, "stopped")
    write_progress(account_tag, "overview", 60, "running", "Starting overview")
    _update_schedule_run(
        "running",
        None if aggregate_run else 3,
        None if aggregate_run else 8,
        f"Overview{f' ({account_tag})' if aggregate_run else ''}",
    )
    process_overall(cred_file, channel_id=channel_id)
    _update_schedule_run(
        "running",
        None if aggregate_run else 4,
        None if aggregate_run else 8,
        f"Overview{f' ({account_tag})' if aggregate_run else ''}",
    )
    _raise_if_stop_requested(account_tag, "stopped")
    write_progress(account_tag, "audience", 80, "running", "Starting audience analytics")
    _update_schedule_run(
        "running",
        None if aggregate_run else 4,
        None if aggregate_run else 8,
        f"Audience{f' ({account_tag})' if aggregate_run else ''}",
    )
    run_audience_analytics(creds, account_tag, pg_url, channel_id=channel_id)
    _update_schedule_run(
        "running",
        None if aggregate_run else 5,
        None if aggregate_run else 8,
        f"Audience{f' ({account_tag})' if aggregate_run else ''}",
    )
    _raise_if_stop_requested(account_tag, "stopped")
    write_progress(account_tag, "reach", 90, "running", "Starting reach analytics")
    _update_schedule_run(
        "running",
        None if aggregate_run else 5,
        None if aggregate_run else 8,
        f"Reach{f' ({account_tag})' if aggregate_run else ''}",
    )
    run_reach_analytics(creds, account_tag, pg_url, channel_id=channel_id)
    _update_schedule_run(
        "running",
        None if aggregate_run else 6,
        None if aggregate_run else 8,
        f"Reach{f' ({account_tag})' if aggregate_run else ''}",
    )
    _raise_if_stop_requested(account_tag, "stopped")
    write_progress(account_tag, "revenue", 95, "running", "Starting revenue analytics")
    _update_schedule_run(
        "running",
        None if aggregate_run else 6,
        None if aggregate_run else 8,
        f"Revenue{f' ({account_tag})' if aggregate_run else ''}",
    )
    run_revenue_analytics(creds, account_tag, pg_url, channel_id=channel_id)
    _update_schedule_run(
        "running",
        None if aggregate_run else 7,
        None if aggregate_run else 8,
        f"Revenue{f' ({account_tag})' if aggregate_run else ''}",
    )
    _raise_if_stop_requested(account_tag, "stopped")
    write_progress(account_tag, "subscribers", 98, "running", "Starting subscriber analytics")
    _update_schedule_run(
        "running",
        None if aggregate_run else 7,
        None if aggregate_run else 8,
        f"Subscribers{f' ({account_tag})' if aggregate_run else ''}",
    )
    run_channel_daily(creds, account_tag, pg_url, channel_id=channel_id)
    _update_schedule_run(
        "running",
        None if aggregate_run else 8,
        None if aggregate_run else 8,
        f"Subscribers{f' ({account_tag})' if aggregate_run else ''}",
    )
    write_progress(account_tag, "done", 100, "done", "Completed")


def main():
    os.makedirs(TOKEN_FOLDER, exist_ok=True)

    target_arg = sys.argv[1] if len(sys.argv) > 1 else ""
    env_token_names = _resolve_token_list(os.getenv("RUN_TOKEN_NAMES", ""))

    token_files = list_token_names()
    if env_token_names:
        token_files = [name for name in env_token_names if name in token_files]

    if target_arg:
        cred_file = _resolve_token_file(target_arg)
        account_tag = account_tag_from_token_name(cred_file)
        if not token_exists(cred_file):
            write_progress(account_tag, "error", 0, "error", "Token not found")
            print(f"Token not found: {cred_file}")
            return
        try:
            _update_schedule_run("running", 0, 1, "Processing 1 account")
            _run_credential_with_lock(cred_file)
            _update_schedule_run("done", 1, 1, "Completed")
        except ContentChannelAccessError as e:
            message = str(e)
            write_progress(account_tag, "error", 0, "error", message)
            _update_schedule_run("error", 0, 1, message)
            print(message)
        except TokenRefreshFailed as e:
            message = str(e)
            write_progress(account_tag, "error", 0, "error", message)
            _update_schedule_run("error", 0, 1, message)
            print(message)
        except TokenCredentialsError as e:
            message = str(e)
            write_progress(account_tag, "error", 0, "error", message)
            _update_schedule_run("error", 0, 1, message)
            print(message)
        except Exception as e:
            if str(e) == "Stop requested":
                write_progress(account_tag, "stopped", 0, "stopped", "Stopped by admin")
                _update_schedule_run("stopped", 0, 1, "Stopped by admin")
                return
            write_progress(account_tag, "error", 0, "error", str(e))
            _update_schedule_run("error", 0, 1, str(e))
            raise
        return

    if not token_files:
        print("No tokens found. Nothing to process.")
        _update_schedule_run("empty", 0, 0, "No tokens found.")
        return

    total = len(token_files)
    ok = 0
    failures = []
    stopped = False
    max_workers = min(_max_parallel_workers(), total)
    print(f"Processing {total} token(s) with max_parallel={max_workers}...")
    _update_schedule_run("running", 0, total, f"Processed {ok}/{total} channel(s)")

    if max_workers == 1:
        for token_file in token_files:
            account_tag = account_tag_from_token_name(token_file)
            cred_file = _resolve_token_file(token_file)
            try:
                _run_credential_with_lock(cred_file)
                ok += 1
                _update_schedule_run("running", ok, total, f"Processed {ok}/{total} channel(s)")
            except Exception as e:
                if str(e) == "Stop requested":
                    stopped = True
                    write_progress(account_tag, "stopped", 0, "stopped", "Stopped by admin")
                    break
                write_progress(account_tag, "error", 0, "error", str(e))
                failures.append((account_tag, str(e)))
    else:
        future_to_token = {}
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="get-data") as executor:
            for token_file in token_files:
                cred_file = _resolve_token_file(token_file)
                future = executor.submit(_run_credential_with_lock, cred_file)
                future_to_token[future] = token_file

            for future in as_completed(future_to_token):
                token_file = future_to_token[future]
                account_tag = account_tag_from_token_name(token_file)
                try:
                    future.result()
                    ok += 1
                    _update_schedule_run("running", ok, total, f"Processed {ok}/{total} channel(s)")
                except Exception as e:
                    if str(e) == "Stop requested":
                        stopped = True
                        write_progress(account_tag, "stopped", 0, "stopped", "Stopped by admin")
                        for pending_future, pending_token_file in future_to_token.items():
                            if pending_future.done():
                                continue
                            if pending_future.cancel():
                                pending_account_tag = account_tag_from_token_name(pending_token_file)
                                write_progress(
                                    pending_account_tag,
                                    "stopped",
                                    0,
                                    "stopped",
                                    "Stopped by admin",
                                )
                        break
                    write_progress(account_tag, "error", 0, "error", str(e))
                    failures.append((account_tag, str(e)))

    if stopped:
        _update_schedule_run("stopped", ok, total, "Stopped by admin")
    elif failures:
        account_tag, error_message = failures[0]
        _update_schedule_run("error", ok, total, f"{account_tag}: {error_message}")
    elif ok == total:
        _update_schedule_run("done", ok, total, "Completed")

if __name__ == "__main__":
    main()
