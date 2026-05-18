import json
import os
import random
import sqlite3
import threading
import time
from typing import Callable, Iterable, Optional

from googleapiclient.errors import HttpError


_PATCH_LOCK = threading.Lock()
_DB_INIT_LOCK = threading.Lock()
_PATCHED = False
_DB_READY = False
_ORIGINAL_EXECUTE = None


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _quota_db_path() -> str:
    raw = str(os.getenv("GOOGLE_API_QPM_DB_PATH", "") or "").strip()
    if raw:
        return raw
    return os.path.join(_repo_root(), "python_backend", "quota_state.db")


def _quota_scope() -> str:
    return str(os.getenv("GOOGLE_API_QPM_SCOPE", "google_api") or "google_api").strip()


def _quota_window_seconds() -> float:
    raw = str(os.getenv("GOOGLE_API_QPM_WINDOW_SECONDS", "60") or "").strip()
    try:
        value = float(raw)
    except Exception:
        value = 60.0
    return max(1.0, min(value, 3600.0))


def _quota_limit() -> int:
    raw = (
        str(os.getenv("GOOGLE_API_QPM_LIMIT", "") or "").strip()
        or str(os.getenv("YOUTUBE_API_QPM_LIMIT", "") or "").strip()
        or "720"
    )
    try:
        value = int(raw)
    except Exception:
        value = 720
    return max(1, min(value, 100000))


def _retry_attempts() -> int:
    raw = str(os.getenv("GOOGLE_API_QUOTA_RETRY_ATTEMPTS", "5") or "").strip()
    try:
        value = int(raw)
    except Exception:
        value = 5
    return max(1, min(value, 10))


def _retry_base_seconds() -> float:
    raw = str(os.getenv("GOOGLE_API_QUOTA_RETRY_BASE_SECONDS", "5") or "").strip()
    try:
        value = float(raw)
    except Exception:
        value = 5.0
    return max(0.5, min(value, 60.0))


def _retry_cap_seconds() -> float:
    raw = str(os.getenv("GOOGLE_API_QUOTA_RETRY_CAP_SECONDS", "90") or "").strip()
    try:
        value = float(raw)
    except Exception:
        value = 90.0
    return max(1.0, min(value, 600.0))


def _sqlite_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_quota_db_path(), timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _ensure_db_ready(conn: sqlite3.Connection) -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _DB_INIT_LOCK:
        if _DB_READY:
            return
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS google_api_quota_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL,
                ts REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_google_api_quota_events_scope_ts
            ON google_api_quota_events(scope, ts)
            """
        )
        conn.commit()
        _DB_READY = True


def _reserve_rate_slot() -> None:
    limit = _quota_limit()
    scope = _quota_scope()
    window_seconds = _quota_window_seconds()
    while True:
        now = time.time()
        cutoff = now - window_seconds
        wait_seconds = 0.0
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = _sqlite_connect()
            _ensure_db_ready(conn)
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "DELETE FROM google_api_quota_events WHERE scope = ? AND ts < ?",
                (scope, cutoff),
            )
            row = conn.execute(
                "SELECT COUNT(1), MIN(ts) FROM google_api_quota_events WHERE scope = ?",
                (scope,),
            ).fetchone()
            current_count = int((row or (0, None))[0] or 0)
            oldest_ts = (row or (0, None))[1]
            if current_count < limit:
                conn.execute(
                    "INSERT INTO google_api_quota_events(scope, ts) VALUES (?, ?)",
                    (scope, now),
                )
                conn.commit()
                return
            conn.commit()
            wait_seconds = max(
                0.25,
                ((float(oldest_ts or now) + window_seconds) - now) + 0.05,
            )
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            if "locked" in message:
                wait_seconds = 0.25
            else:
                raise
        finally:
            if conn is not None:
                conn.close()
        time.sleep(wait_seconds)


def _http_error_payload(exc: HttpError) -> dict:
    content = getattr(exc, "content", b"") or b""
    if not content:
        return {}
    if isinstance(content, bytes):
        try:
            return json.loads(content.decode("utf-8", errors="ignore"))
        except Exception:
            return {}
    try:
        return json.loads(str(content))
    except Exception:
        return {}


def _iter_http_error_reasons(payload: dict) -> Iterable[str]:
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return []
    errors = error.get("errors")
    if isinstance(errors, list):
        return [
            str(item.get("reason") or "").strip()
            for item in errors
            if isinstance(item, dict) and str(item.get("reason") or "").strip()
        ]
    details = error.get("details")
    if isinstance(details, list):
        return [
            str(item.get("reason") or "").strip()
            for item in details
            if isinstance(item, dict) and str(item.get("reason") or "").strip()
        ]
    return []


def _is_retryable_quota_error(exc: HttpError) -> bool:
    try:
        status = int(getattr(getattr(exc, "resp", None), "status", 0) or 0)
    except Exception:
        status = 0
    if status == 429:
        return True
    payload = _http_error_payload(exc)
    reasons = {reason.lower() for reason in _iter_http_error_reasons(payload)}
    if reasons & {
        "userratelimitexceeded",
        "ratelimitexceeded",
        "quotaexceeded",
    }:
        return True
    message = json.dumps(payload, ensure_ascii=False).lower() if payload else str(exc).lower()
    return any(
        key in message
        for key in (
            "quotaexceeded",
            "userratelimitexceeded",
            "ratelimitexceeded",
            "too many requests",
            "queries per minute",
        )
    )


def _retry_after_seconds(exc: HttpError) -> Optional[float]:
    resp = getattr(exc, "resp", None)
    if resp is None:
        return None
    raw = None
    try:
        raw = resp.get("retry-after")
    except Exception:
        raw = None
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except Exception:
        return None


def _backoff_seconds(attempt: int, exc: HttpError) -> float:
    retry_after = _retry_after_seconds(exc)
    if retry_after is not None:
        return retry_after
    base = _retry_base_seconds()
    cap = _retry_cap_seconds()
    wait = min(cap, base * (2 ** attempt))
    jitter = random.uniform(0.0, min(base, wait))
    return min(cap, wait + jitter)


def execute_with_quota_guard(
    invoker: Callable[[], object],
    label: str = "",
):
    attempts = _retry_attempts()
    for attempt in range(attempts):
        _reserve_rate_slot()
        try:
            return invoker()
        except HttpError as exc:
            if not _is_retryable_quota_error(exc) or attempt >= attempts - 1:
                raise
            wait_seconds = _backoff_seconds(attempt, exc)
            if label:
                print(
                    f"[WARN] Google API quota hit for {label}. "
                    f"Retrying in {wait_seconds:.1f}s "
                    f"({attempt + 2}/{attempts})"
                )
            else:
                print(
                    f"[WARN] Google API quota hit. "
                    f"Retrying in {wait_seconds:.1f}s "
                    f"({attempt + 2}/{attempts})"
                )
            time.sleep(wait_seconds)
    return invoker()


def get_quota_state() -> dict:
    limit = _quota_limit()
    scope = _quota_scope()
    window_seconds = _quota_window_seconds()
    now = time.time()
    cutoff = now - window_seconds
    used = 0
    oldest_ts: Optional[float] = None
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _sqlite_connect()
        _ensure_db_ready(conn)
        row = conn.execute(
            "SELECT COUNT(1), MIN(ts) FROM google_api_quota_events WHERE scope = ? AND ts >= ?",
            (scope, cutoff),
        ).fetchone()
        if row:
            used = int(row[0] or 0)
            oldest_ts = float(row[1]) if row[1] is not None else None
    except sqlite3.OperationalError:
        used = 0
        oldest_ts = None
    finally:
        if conn is not None:
            conn.close()
    reset_in = 0.0
    if oldest_ts is not None:
        reset_in = max(0.0, (oldest_ts + window_seconds) - now)
    percent = round((used / limit) * 100.0, 1) if limit > 0 else 0.0
    return {
        "scope": scope,
        "used": used,
        "limit": limit,
        "window_seconds": int(window_seconds),
        "percent": percent,
        "reset_in_seconds": round(reset_in, 1),
    }


def enable_google_api_quota_guard() -> None:
    global _PATCHED, _ORIGINAL_EXECUTE
    if _PATCHED:
        return
    with _PATCH_LOCK:
        if _PATCHED:
            return
        from googleapiclient.http import HttpRequest

        _ORIGINAL_EXECUTE = HttpRequest.execute

        def _patched_execute(self, *args, **kwargs):
            label = str(getattr(self, "uri", "") or "").strip()
            return execute_with_quota_guard(
                lambda: _ORIGINAL_EXECUTE(self, *args, **kwargs),
                label=label,
            )

        HttpRequest.execute = _patched_execute
        _PATCHED = True
