# get_data.py — PG-only runner
import os
import sys
from module_trafficsource import *
from module_content import *
from module_overall import *


def _resolve_credential_file(name: str) -> str:
    base = os.path.basename(name or "")
    if base.lower().endswith(".pickle"):
        base = base[:-7]
    if base.lower().endswith(".json"):
        base = base[:-5]
    return f"{base}.json"


def _run_for_credential(cred_file: str) -> None:
    process_one(cred_file)
    process_content(cred_file)
    process_overall(cred_file)


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
        if not os.path.exists(cred_path):
            print(f"Credential file not found: {cred_file}")
            return
        _run_for_credential(cred_file)
        return

    token_set = {os.path.splitext(t)[0] for t in token_files}
    runnable = [f for f in files if os.path.splitext(f)[0] in token_set]

    if not runnable:
        print("No credentials have tokens. Nothing to process.")
        return

    print(f"Processing {len(runnable)} account(s) with tokens...")
    for cred_file in runnable:
        _run_for_credential(cred_file)

if __name__ == "__main__":
    main()
