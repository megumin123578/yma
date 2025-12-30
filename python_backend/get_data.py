# get_data.py — PG-only runner
import os
import sys
import json
import sqlite3
from datetime import datetime
from module_trafficsource import *
from module_content import *
from module_overall import *
from module_audience import run_audience_analytics
from module_reach import run_reach_analytics
try:
    from python_backend.module_channel_daily import run_channel_daily
except ModuleNotFoundError:
    from module_channel_daily import run_channel_daily

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_CREDENTIALS = os.path.join(REPO_ROOT, "python_backend", "credentials")
DEFAULT_TOKEN = os.path.join(REPO_ROOT, "python_backend", "token")

if os.path.exists(DEFAULT_CREDENTIALS):
    CREDENTIALS_FOLDER = DEFAULT_CREDENTIALS
if os.path.exists(DEFAULT_TOKEN):
    TOKEN_FOLDER = DEFAULT_TOKEN

if not os.path.exists(CREDENTIALS_FOLDER):
    fallback_credentials = os.path.join(os.path.dirname(__file__), "credentials")
    if os.path.exists(fallback_credentials):
        CREDENTIALS_FOLDER = fallback_credentials

if not os.path.exists(TOKEN_FOLDER):
    fallback_token = os.path.join(os.path.dirname(__file__), "token")
    if os.path.exists(fallback_token):
        TOKEN_FOLDER = fallback_token


def _resolve_credential_file(name: str) -> str:
    base = os.path.basename(name or "")
    if base.lower().endswith(".pickle"):
        base = base[:-7]
    if base.lower().endswith(".json"):
        base = base[:-5]
    return f"{base}.json"


def _progress_path(account_tag: str) -> str:
    progress_dir = os.path.join("python_backend", "progress")
    os.makedirs(progress_dir, exist_ok=True)
    return os.path.join(progress_dir, f"{account_tag}.json")


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

def _update_schedule_run(status: str, processed: int, total: int, message: str = "") -> None:
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
            SET status = ?, processed = ?, total = ?, message = ?, finished_at = COALESCE(?, finished_at)
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
        elif stage == "overview":
            process_overall(cred_file, channel_id=channel_id)
        elif stage == "audience":
            pg_url = os.getenv("PG_URL")
            if not pg_url:
                raise RuntimeError("Missing PG_URL env var")
            creds = create_token_from_credentials(os.path.join(CREDENTIALS_FOLDER, cred_file))
            run_audience_analytics(creds, account_tag, pg_url, channel_id=channel_id)
        elif stage == "reach":
            pg_url = os.getenv("PG_URL")
            if not pg_url:
                raise RuntimeError("Missing PG_URL env var")
            creds = create_token_from_credentials(os.path.join(CREDENTIALS_FOLDER, cred_file))
            run_reach_analytics(creds, account_tag, pg_url, channel_id=channel_id)
        else:
            raise RuntimeError(f"Unsupported stage: {stage}")
        _raise_if_stop_requested(account_tag, "stopped")
        _update_schedule_run("running", 1, 1, f"Completed {stage}")
        _write_progress(account_tag, "done", 100, "done", f"Completed {stage}")
        return
    _raise_if_stop_requested(account_tag, "stopped")
    _write_progress(account_tag, "traffic_source", 5, "running", "Starting traffic source")
    process_one(cred_file, channel_id=channel_id)
    _update_schedule_run("running", 1, 6, "Traffic source done")
    _raise_if_stop_requested(account_tag, "stopped")
    _write_progress(account_tag, "content", 35, "running", "Starting content fetch")
    process_content(cred_file, channel_id=channel_id)
    _update_schedule_run("running", 2, 6, "Content done")
    _raise_if_stop_requested(account_tag, "stopped")
    _write_progress(account_tag, "overview", 60, "running", "Starting overview")
    process_overall(cred_file, channel_id=channel_id)
    _update_schedule_run("running", 3, 6, "Overview done")
    _raise_if_stop_requested(account_tag, "stopped")
    _write_progress(account_tag, "audience", 80, "running", "Starting audience analytics")
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        raise RuntimeError("Missing PG_URL env var")
    creds = create_token_from_credentials(os.path.join(CREDENTIALS_FOLDER, cred_file))
    run_audience_analytics(creds, account_tag, pg_url, channel_id=channel_id)
    _update_schedule_run("running", 4, 6, "Audience done")
    _raise_if_stop_requested(account_tag, "stopped")
    _write_progress(account_tag, "reach", 90, "running", "Starting reach analytics")
    run_reach_analytics(creds, account_tag, pg_url, channel_id=channel_id)
    _update_schedule_run("running", 5, 6, "Reach done")
    _raise_if_stop_requested(account_tag, "stopped")
    _write_progress(account_tag, "subscribers", 95, "running", "Starting subscriber analytics")
    run_channel_daily(creds, account_tag, pg_url, channel_id=channel_id)
    _update_schedule_run("running", 6, 6, "Subscribers done")
    _write_progress(account_tag, "done", 100, "done", "Completed")


def main():
    if not os.path.exists(CREDENTIALS_FOLDER):
        print(f"Credentials folder '{CREDENTIALS_FOLDER}' does not exist.")
        return

    os.makedirs(TOKEN_FOLDER, exist_ok=True)

    target_arg = sys.argv[1] if len(sys.argv) > 1 else ""

    files = [f for f in os.listdir(CREDENTIALS_FOLDER) if f.endswith(".json")]
    if not files:
        print(f"No credentials files found in {CREDENTIALS_FOLDER}.")
        return

    token_files = [f for f in os.listdir(TOKEN_FOLDER) if f.endswith(".pickle")]

    if target_arg:
        cred_file = _resolve_credential_file(target_arg)
        cred_path = os.path.join(CREDENTIALS_FOLDER, cred_file)
        account_tag = os.path.splitext(os.path.basename(cred_file))[0]
        if not os.path.exists(cred_path):
            _write_progress(account_tag, "error", 0, "error", "Credential file not found")
            print(f"Credential file not found: {cred_file}")
            return
        try:
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
    _update_schedule_run("running", 0, total, "Processing tokens")
    for token_file in token_files:
        account_tag = os.path.splitext(os.path.basename(token_file))[0]
        cred_file = _resolve_credential_file(token_file)
        cred_path = os.path.join(CREDENTIALS_FOLDER, cred_file)
        if not os.path.exists(cred_path):
            _write_progress(account_tag, "error", 0, "error", "Credential file not found")
            _update_schedule_run(
                "running", ok, total, f"Missing credentials for {account_tag}"
            )
            continue
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
