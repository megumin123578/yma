import json
import os
import sqlite3
from datetime import datetime
from typing import Optional

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DEFAULT_AUTH_DB = os.path.join(_REPO_ROOT, "auth.db")


class TokenCredentialsError(ValueError):
    pass


class TokenRefreshFailed(TokenCredentialsError):
    pass


def get_auth_db_path() -> str:
    return os.getenv("AUTH_DB_PATH", _DEFAULT_AUTH_DB)


def normalize_token_name(token_name: str) -> str:
    return os.path.basename((token_name or "").strip())


def token_name_from_ref(value: str) -> str:
    base = normalize_token_name(value)
    if base.lower().endswith(".json"):
        return base[:-5]
    return base


def account_tag_from_token_name(token_name: str) -> str:
    return normalize_token_name(token_name)


def _connect_auth_db() -> sqlite3.Connection:
    conn = sqlite3.connect(get_auth_db_path(), timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def _parse_scopes(info: dict) -> Optional[list[str]]:
    raw_scopes = info.get("scopes")
    if isinstance(raw_scopes, list):
        return [str(scope).strip() for scope in raw_scopes if str(scope).strip()]
    if isinstance(raw_scopes, str):
        values = [scope.strip() for scope in raw_scopes.replace(",", " ").split()]
        return [scope for scope in values if scope]

    raw_scope = info.get("scope")
    if isinstance(raw_scope, str):
        values = [scope.strip() for scope in raw_scope.replace(",", " ").split()]
        return [scope for scope in values if scope]
    return None


def _deserialize_credentials(payload: str):
    try:
        info = json.loads(payload or "")
    except Exception:
        return None
    if not isinstance(info, dict):
        return None
    try:
        return Credentials.from_authorized_user_info(info, scopes=_parse_scopes(info))
    except Exception:
        return None


def store_token_credentials(token_name: str, creds) -> None:
    normalized = normalize_token_name(token_name)
    if not normalized:
        raise ValueError("Missing token name")
    if creds is None:
        raise ValueError(f"Missing credentials for token: {normalized}")

    payload = creds.to_json()
    now = datetime.utcnow().isoformat()
    conn = _connect_auth_db()
    try:
        conn.execute(
            """
            INSERT INTO oauth_tokens (token_name, credentials_json, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(token_name) DO UPDATE SET
                credentials_json = excluded.credentials_json,
                updated_at = excluded.updated_at
            """,
            (normalized, payload, now, now),
        )
        conn.commit()
    finally:
        conn.close()


def store_token_credentials_raw(
    token_name: str,
    credentials_json: str,
    created_at: Optional[str] = None,
    updated_at: Optional[str] = None,
) -> str:
    normalized = normalize_token_name(token_name)
    if not normalized:
        raise ValueError("Missing token name")
    if not credentials_json or not str(credentials_json).strip():
        raise ValueError("Missing credentials_json")
    try:
        json.loads(credentials_json)
    except Exception as exc:
        raise ValueError(f"credentials_json is not valid JSON: {exc}") from exc
    now = datetime.utcnow().isoformat()
    conn = _connect_auth_db()
    try:
        conn.execute(
            """
            INSERT INTO oauth_tokens (token_name, credentials_json, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(token_name) DO UPDATE SET
                credentials_json = excluded.credentials_json,
                updated_at = excluded.updated_at
            """,
            (normalized, credentials_json, created_at or now, updated_at or now),
        )
        conn.commit()
    finally:
        conn.close()
    return normalized


def rename_token_credentials(old_token_name: str, new_token_name: str) -> None:
    old_name = normalize_token_name(old_token_name)
    new_name = normalize_token_name(new_token_name)
    if not old_name or not new_name or old_name == new_name:
        return
    conn = _connect_auth_db()
    try:
        row = conn.execute(
            "SELECT credentials_json, created_at FROM oauth_tokens WHERE token_name = ?",
            (old_name,),
        ).fetchone()
        if not row:
            return
        now = datetime.utcnow().isoformat()
        conn.execute(
            """
            INSERT INTO oauth_tokens (token_name, credentials_json, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(token_name) DO UPDATE SET
                credentials_json = excluded.credentials_json,
                updated_at = excluded.updated_at
            """,
            (new_name, row[0], row[1] or now, now),
        )
        conn.execute("DELETE FROM oauth_tokens WHERE token_name = ?", (old_name,))
        conn.commit()
    finally:
        conn.close()


def delete_token_credentials(token_name: str) -> None:
    normalized = normalize_token_name(token_name)
    if not normalized:
        return
    conn = _connect_auth_db()
    try:
        conn.execute("DELETE FROM oauth_tokens WHERE token_name = ?", (normalized,))
        conn.commit()
    finally:
        conn.close()


def has_stored_token(token_name: str) -> bool:
    normalized = normalize_token_name(token_name)
    if not normalized:
        return False
    conn = _connect_auth_db()
    try:
        row = conn.execute(
            """
            SELECT 1
            FROM oauth_tokens
            WHERE token_name = ?
              AND credentials_json IS NOT NULL
              AND TRIM(credentials_json) != ''
            LIMIT 1
            """,
            (normalized,),
        ).fetchone()
        return bool(row)
    finally:
        conn.close()


def token_exists(token_name: str) -> bool:
    return has_stored_token(token_name)


def list_token_names() -> list[str]:
    conn = _connect_auth_db()
    try:
        rows = conn.execute(
            """
            SELECT token_name
            FROM oauth_tokens
            WHERE credentials_json IS NOT NULL
              AND TRIM(credentials_json) != ''
            ORDER BY token_name COLLATE NOCASE ASC
            """
        ).fetchall()
        return [normalize_token_name(row[0]) for row in rows if row and row[0]]
    finally:
        conn.close()


def load_token_credentials(token_name: str, refresh: bool = True):
    normalized = normalize_token_name(token_name)
    if not normalized:
        raise ValueError("Missing token name")

    conn = _connect_auth_db()
    try:
        row = conn.execute(
            "SELECT credentials_json FROM oauth_tokens WHERE token_name = ? LIMIT 1",
            (normalized,),
        ).fetchone()
    finally:
        conn.close()

    creds = _deserialize_credentials(row[0]) if row and row[0] else None
    if creds is None:
        raise FileNotFoundError(f"Token not found: {normalized}")

    if refresh and not getattr(creds, "valid", False):
        if getattr(creds, "expired", False) and getattr(creds, "refresh_token", None):
            try:
                creds.refresh(Request())
            except RefreshError as exc:
                detail = ""
                if len(exc.args) > 1 and isinstance(exc.args[1], dict):
                    error_code = str(exc.args[1].get("error") or "").strip()
                    error_desc = str(exc.args[1].get("error_description") or "").strip()
                    detail = ": ".join(part for part in (error_code, error_desc) if part)
                message = f"Token refresh failed for {normalized}. Reconnect this account."
                if detail:
                    message = f"{message} ({detail})"
                raise TokenRefreshFailed(message) from exc
            store_token_credentials(normalized, creds)
        else:
            raise TokenCredentialsError(f"Token is not valid: {normalized}")

    return creds
