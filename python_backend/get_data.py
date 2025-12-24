# get_data.py — PG-only runner
import os
import sys
import json
from datetime import datetime
from module_trafficsource import *
from module_content import *
from module_overall import *

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


def _run_for_credential(cred_file: str) -> None:
    account_tag = os.path.splitext(os.path.basename(cred_file))[0]
    _write_progress(account_tag, "traffic_source", 5, "running", "Starting traffic source")
    process_one(cred_file)
    _write_progress(account_tag, "content", 45, "running", "Starting content fetch")
    process_content(cred_file)
    _write_progress(account_tag, "overview", 80, "running", "Starting overview")
    process_overall(cred_file)
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
            _run_for_credential(cred_file)
        except Exception as e:
            _write_progress(account_tag, "error", 0, "error", str(e))
            raise
        return

    token_set = {os.path.splitext(t)[0] for t in token_files}
    runnable = [f for f in files if os.path.splitext(f)[0] in token_set]

    if not runnable:
        print("No credentials have tokens. Nothing to process.")
        return

    print(f"Processing {len(runnable)} account(s) with tokens...")
    for cred_file in runnable:
        try:
            _run_for_credential(cred_file)
        except Exception as e:
            account_tag = os.path.splitext(os.path.basename(cred_file))[0]
            _write_progress(account_tag, "error", 0, "error", str(e))

if __name__ == "__main__":
    main()
