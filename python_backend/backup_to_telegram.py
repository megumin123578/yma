"""Dump Postgres and ship the file to a dedicated Telegram chat.

Usage:
    python -m python_backend.backup_to_telegram

Required env (python_backend/.env):
    PG_URL                       Postgres connection string
    BACKUP_TELEGRAM_BOT_TOKEN    Bot token (separate from TELEGRAM_BOT_TOKEN)
    BACKUP_TELEGRAM_CHAT_ID      Destination chat / channel id

Optional env:
    BACKUP_DIR                   Where dump files are written (default ./backups)
    BACKUP_KEEP                  How many recent local dumps to keep (default 7)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

from python_backend.config import load_env

TELEGRAM_FILE_LIMIT = 49 * 1024 * 1024  # bot upload cap is 50 MB; leave headroom


def _parse_pg_url(url: str) -> dict[str, str]:
    cleaned = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    p = urlparse(cleaned)
    if p.scheme != "postgresql" or not p.hostname or not p.path:
        raise RuntimeError(f"Invalid PG_URL: {url!r}")
    return {
        "host": p.hostname,
        "port": str(p.port or 5432),
        "user": unquote(p.username or ""),
        "password": unquote(p.password or ""),
        "dbname": p.path.lstrip("/"),
    }


def _run_pg_dump(conn: dict[str, str], out_path: Path) -> None:
    env = os.environ.copy()
    if conn["password"]:
        env["PGPASSWORD"] = conn["password"]
    cmd = [
        "pg_dump",
        "-h", conn["host"],
        "-p", conn["port"],
        "-U", conn["user"],
        "-d", conn["dbname"],
        "-F", "c",
        "--no-owner",
        "--no-privileges",
        "-f", str(out_path),
    ]
    print(f"[dump] {' '.join(cmd)}")
    subprocess.run(cmd, env=env, check=True)


def _split_file(path: Path, chunk_size: int) -> list[Path]:
    if path.stat().st_size <= chunk_size:
        return [path]
    parts: list[Path] = []
    with path.open("rb") as src:
        idx = 1
        while True:
            chunk = src.read(chunk_size)
            if not chunk:
                break
            part_path = path.with_suffix(path.suffix + f".part{idx:03d}")
            part_path.write_bytes(chunk)
            parts.append(part_path)
            idx += 1
    return parts


def _send_document(token: str, chat_id: str, path: Path, caption: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    with path.open("rb") as fh:
        r = requests.post(
            url,
            data={"chat_id": chat_id, "caption": caption},
            files={"document": (path.name, fh)},
            timeout=600,
        )
    if not r.ok:
        raise RuntimeError(f"Telegram sendDocument failed [{r.status_code}]: {r.text}")
    print(f"[send] {path.name} ({path.stat().st_size/1024/1024:.1f} MB)")


def _send_text(token: str, chat_id: str, text: str) -> None:
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text},
            timeout=30,
        )
    except Exception:
        pass


def main() -> int:
    load_env()
    pg_url = os.getenv("PG_URL", "").strip()
    bot_token = os.getenv("BACKUP_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("BACKUP_TELEGRAM_CHAT_ID", "").strip()
    if not (pg_url and bot_token and chat_id):
        print(
            "Missing PG_URL / BACKUP_TELEGRAM_BOT_TOKEN / BACKUP_TELEGRAM_CHAT_ID",
            file=sys.stderr,
        )
        return 1

    conn = _parse_pg_url(pg_url)
    backup_dir = Path(os.getenv("BACKUP_DIR", "")).resolve() if os.getenv("BACKUP_DIR") \
        else (Path(__file__).resolve().parent.parent / "backups")
    backup_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dump_path = backup_dir / f"{conn['dbname']}_{stamp}.dump"
    started = time.time()
    parts: list[Path] = []

    try:
        _run_pg_dump(conn, dump_path)
        size_mb = dump_path.stat().st_size / 1024 / 1024
        parts = _split_file(dump_path, TELEGRAM_FILE_LIMIT)

        for i, part in enumerate(parts, 1):
            suffix = f" — part {i}/{len(parts)}" if len(parts) > 1 else ""
            _send_document(
                bot_token,
                chat_id,
                part,
                caption=f"{conn['dbname']} backup {stamp} UTC{suffix}",
            )

        if len(parts) > 1:
            _send_text(
                bot_token,
                chat_id,
                (
                    f"OK. {len(parts)} phần, tổng {size_mb:.1f} MB.\n"
                    f"Khôi phục: copy /b *.part* {dump_path.name} "
                    f"sau đó pg_restore -d <db> {dump_path.name}"
                ),
            )

        print(f"[done] {size_mb:.1f} MB in {time.time()-started:.1f}s, {len(parts)} part(s).")
        return 0

    except subprocess.CalledProcessError as e:
        _send_text(bot_token, chat_id, f"pg_dump FAILED ({conn['dbname']} {stamp}): exit {e.returncode}")
        raise
    except Exception as e:
        _send_text(bot_token, chat_id, f"Backup FAILED ({conn['dbname']} {stamp}): {e}")
        raise
    finally:
        for p in parts:
            if p != dump_path:
                p.unlink(missing_ok=True)
        keep = max(1, int(os.getenv("BACKUP_KEEP", "7") or "7"))
        olds = sorted(backup_dir.glob(f"{conn['dbname']}_*.dump"))
        for old in olds[:-keep]:
            old.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
