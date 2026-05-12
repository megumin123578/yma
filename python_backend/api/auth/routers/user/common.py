import os
import re
import json
import subprocess
import sys
import time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import HTMLResponse

from python_backend.sse_utils import poll_stream, sse_response
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from sqlalchemy import or_
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from python_backend.api.auth.database import get_db, SessionLocal
from python_backend.api.auth.models import User, RivalChannel, RivalChannelGroup, RivalGroup, UserCredential, UserCredentialProject
from python_backend.api.auth.auth_utils import get_current_user, get_current_user_optional, hash_password
from python_backend.api.auth import schemas
from python_backend.api.auth.schemas import UserMe, UserProfileUpdate
from python_backend.api.auth.models import UserHiddenChannel, UserSchedule, UserScheduleRun, TokenProgress, PasswordChangeRequest, SmmstoreAnalyticsCache, SmmstoreScheduledOrder, LiveCounterSnapshot, VideoLiveCounterSnapshot, OAuthState, MailOAuthState
from python_backend.api.auth.visibility import get_hidden_account_tags
from python_backend.mail_gmail_api import (
    build_mail_oauth_flow,
    deserialize_mail_label_ids,
    fetch_gmail_profile,
    mail_oauth_success_html,
    sync_mail_account,
    upsert_mail_account,
)
from python_backend.module_trafficsource import SCOPES, sanitize_filename
from python_backend.progress_state import write_progress
from python_backend.token_store import (
    account_tag_from_token_name,
    delete_token_credentials,
    list_token_names,
    load_token_credentials as load_stored_token_credentials,
    store_token_credentials,
    token_exists,
)
from pydantic import BaseModel
from datetime import datetime, timedelta

router = APIRouter(prefix="/users", tags=["Users"])

UPLOAD_DIR = "python_backend/api/uploads/avatars"
os.makedirs(UPLOAD_DIR, exist_ok=True)

OAUTH_REDIRECT_URL = os.getenv(
    "OAUTH_REDIRECT_URL",
    "https://4b0de643968e.ngrok-free.app/api/users/credentials/callback",
)
OAUTH_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
_ADMIN_ENV_KEY = "ADMIN_USERNAME"
_OAUTH_STATE_TTL_MINUTES = int(os.getenv("OAUTH_STATE_TTL_MINUTES", "15"))
_UNASSIGNED_PROJECT_GROUP = "__ungrouped__"
_ALLOWED_RUN_STAGES = {
    "content",
    "full_backfill",
    "overview",
    "audience",
    "reach",
    "thumbnail_reach",
    "traffic_source",
    "revenue",
    "subscribers",
}


def _oauth_success_html() -> str:
    return """
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Authorized</title>
    <style>
      body { font-family: Arial, sans-serif; padding: 24px; background: #0f172a; color: #e2e8f0; }
      .card { max-width: 520px; margin: 40px auto; background: #111827; padding: 24px; border-radius: 12px; border: 1px solid #334155; }
      h1 { font-size: 18px; margin: 0 0 12px; }
    </style>
  </head>
  <body>
    <div class="card">
      <h1>Channel connected.</h1>
      <p>Data sync is now running on the server.</p>
    </div>
  </body>
</html>
"""


def _oauth_state_response(row: OAuthState) -> dict:
    return {
        "ready": row.status == "completed",
        "token_name": row.token_name,
        "account_tag": row.final_account_tag or row.account_tag,
    }


def _mark_oauth_state_failed(db: Session, row: OAuthState, message: str) -> None:
    row.status = "failed"
    row.error_message = message
    row.completed_at = datetime.utcnow()
    db.add(row)
    db.commit()


def _mail_oauth_redirect_url() -> str:
    return os.getenv("MAIL_OAUTH_REDIRECT_URL", "").strip() or OAUTH_REDIRECT_URL


def _mark_mail_oauth_state_failed(db: Session, row: MailOAuthState, message: str) -> None:
    row.status = "failed"
    row.error_message = message
    row.completed_at = datetime.utcnow()
    db.add(row)
    db.commit()


def _complete_mail_oauth_from_shared_callback(
    db: Session,
    row: MailOAuthState,
    code: str = "",
    error: str = "",
) -> str:
    if error:
        _mark_mail_oauth_state_failed(db, row, f"Authorization failed: {error}")
        raise HTTPException(status_code=400, detail=f"Authorization failed: {error}")

    now = datetime.utcnow()
    if row.expires_at and row.expires_at < now:
        row.status = "expired"
        row.completed_at = now
        db.add(row)
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    if row.status == "completed":
        return mail_oauth_success_html()
    if row.status == "failed":
        raise HTTPException(status_code=400, detail=row.error_message or "OAuth flow failed")

    flow = build_mail_oauth_flow(_mail_oauth_redirect_url())
    try:
        flow.fetch_token(code=code)
    except Exception as exc:
        _mark_mail_oauth_state_failed(db, row, f"Failed to fetch token: {exc}")
        raise HTTPException(status_code=400, detail=f"Failed to fetch token: {exc}")

    try:
        profile = fetch_gmail_profile(flow.credentials)
        account = upsert_mail_account(
            db,
            user_id=row.user_id,
            account_email=profile["email"],
            creds=flow.credentials,
            label_ids=deserialize_mail_label_ids(row.label_ids_json),
        )
        row.status = "completed"
        row.account_email = account.account_email
        row.token_name = account.token_name
        row.error_message = None
        row.completed_at = datetime.utcnow()
        row.consumed_at = row.consumed_at or now
        db.add(row)
        db.commit()

        try:
            sync_mail_account(db, account)
        except Exception as sync_exc:
            row.error_message = str(sync_exc)
            db.add(row)
            db.commit()
    except Exception as exc:
        _mark_mail_oauth_state_failed(db, row, str(exc))
        raise HTTPException(status_code=400, detail=str(exc))

    return mail_oauth_success_html()


def _safe_token_name(name: str) -> str:
    return os.path.basename(name or "")


def _require_valid_token_name(token_name: str) -> str:
    safe_name = _safe_token_name(token_name)
    if not safe_name or safe_name != token_name:
        raise HTTPException(status_code=400, detail="Invalid token name")
    return safe_name


def _load_token_credentials(token_name: str):
    try:
        return load_stored_token_credentials(token_name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Token not found")
    except ValueError:
        raise HTTPException(status_code=400, detail="Token is not valid")
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to read token")


def _find_owned_credential_by_identifier(
    db: Session,
    user_id: int,
    identifier: str,
    allow_all_users: bool = False,
) -> Optional[UserCredential]:
    ident = str(identifier or "").strip()
    if not ident:
        return None
    query = db.query(UserCredential)
    if not allow_all_users:
        query = query.filter(UserCredential.user_id == user_id)
    return (
        query.filter(
            or_(
                UserCredential.token_name == ident,
                UserCredential.account_tag == ident,
                UserCredential.selected_channel_id == ident,
                UserCredential.selected_channel_title == ident,
            )
        )
        .order_by(UserCredential.id.asc())
        .first()
    )


def _fetch_selected_channel_metadata(creds, channel_id: Optional[str] = None) -> dict:
    yt = build("youtube", "v3", credentials=creds)
    if channel_id:
        resp = yt.channels().list(
            part="snippet",
            id=channel_id,
            maxResults=1,
        ).execute() or {}
    else:
        resp = yt.channels().list(
            part="snippet",
            mine=True,
            maxResults=1,
        ).execute() or {}

    items = resp.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="Channel not found for this token")

    item = items[0]
    snippet = item.get("snippet", {}) or {}
    thumbs = snippet.get("thumbnails", {}) or {}
    avatar = (
        thumbs.get("medium", {}).get("url")
        or thumbs.get("default", {}).get("url")
        or thumbs.get("high", {}).get("url")
        or ""
    )
    return {
        "channel_id": item.get("id") or channel_id or "",
        "title": snippet.get("title", "") or "",
        "avatar": avatar,
    }


def _build_oauth_flow() -> Flow:
    if not OAUTH_CLIENT_ID or not OAUTH_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET",
        )
    client_config = {
        "web": {
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [OAUTH_REDIRECT_URL],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = OAUTH_REDIRECT_URL
    return flow


def _require_admin(current_user: User) -> None:
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")


def _get_admin_users() -> set:
    raw = os.getenv(_ADMIN_ENV_KEY, "admin")
    return {u.strip().lower() for u in raw.split(",") if u.strip()}


def _get_admin_usernames_in_order() -> list[str]:
    raw = os.getenv(_ADMIN_ENV_KEY, "admin")
    return [u.strip().lower() for u in raw.split(",") if u.strip()]


def _is_env_admin_username(username: str | None) -> bool:
    return (username or "").lower() in _get_admin_users()


def _is_admin_user(user: User | None) -> bool:
    if not user:
        return False
    return bool(getattr(user, "is_admin", False) or _is_env_admin_username(user.username))


def _resolve_oauth_owner_user(db: Session, current_user: User | None) -> User:
    if current_user:
        return current_user

    for username in _get_admin_usernames_in_order():
        owner = db.query(User).filter(User.username.ilike(username)).first()
        if owner:
            return owner

    owner = db.query(User).filter(User.is_admin.is_(True)).order_by(User.id.asc()).first()
    if owner:
        return owner

    raise HTTPException(status_code=503, detail="No owner user configured for public OAuth")

def _list_token_projects(db: Session) -> list[dict]:
    project_names: set[str] = set()

    rows = (
        db.query(UserCredentialProject.project_name)
        .order_by(UserCredentialProject.project_name.asc())
        .all()
    )
    for row in rows:
        project_name = (row.project_name or "").strip()
        if project_name:
            project_names.add(project_name)

    assigned_rows = (
        db.query(UserCredential.project_name)
        .filter(UserCredential.project_name.isnot(None))
        .all()
    )
    for row in assigned_rows:
        project_name = (row.project_name or "").strip()
        if project_name:
            project_names.add(project_name)

    return [
        {"project_name": project_name}
        for project_name in sorted(project_names, key=lambda item: item.lower())
    ]


def _purge_postgres_account(account_tag: str) -> None:
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        return

    engine = create_engine(pg_url, future=True)
    tags = {account_tag, sanitize_filename(account_tag)}
    with engine.begin() as conn:
        for tag in tags:
            try:
                conn.execute(
                    text("""
                        DELETE FROM video_daily_stats
                        WHERE video_id IN (
                            SELECT video_id FROM videos WHERE account_tag = :acct
                        )
                    """),
                    {"acct": tag},
                )
            except Exception:
                pass
            try:
                conn.execute(
                    text("DELETE FROM videos WHERE account_tag = :acct"),
                    {"acct": tag},
                )
            except Exception:
                pass
            try:
                conn.execute(
                    text("DELETE FROM video_overview WHERE account_tag = :acct"),
                    {"acct": tag},
                )
            except Exception:
                pass
            try:
                conn.execute(
                    text("DELETE FROM traffic_source_daily WHERE account_tag = :acct"),
                    {"acct": tag},
                )
            except Exception:
                pass
            try:
                conn.execute(
                    text("DELETE FROM audience_demographics WHERE account_tag = :acct"),
                    {"acct": tag},
                )
            except Exception:
                pass
            try:
                conn.execute(
                    text("DELETE FROM audience_retention WHERE account_tag = :acct"),
                    {"acct": tag},
                )
            except Exception:
                pass
            try:
                conn.execute(
                    text("DELETE FROM audience_devices WHERE account_tag = :acct"),
                    {"acct": tag},
                )
            except Exception:
                pass
            try:
                conn.execute(
                    text("DELETE FROM audience_viewer_types WHERE account_tag = :acct"),
                    {"acct": tag},
                )
            except Exception:
                pass
            try:
                conn.execute(
                    text("DELETE FROM reach_video_metrics WHERE account_tag = :acct"),
                    {"acct": tag},
                )
            except Exception:
                pass
            try:
                conn.execute(
                    text("DELETE FROM video_thumbnail_daily WHERE account_tag = :acct"),
                    {"acct": tag},
                )
            except Exception:
                pass
            try:
                conn.execute(
                    text("DELETE FROM youtube_reporting_processed_reports WHERE account_tag = :acct"),
                    {"acct": tag},
                )
            except Exception:
                pass
            try:
                conn.execute(
                    text("DELETE FROM youtube_reporting_jobs WHERE account_tag = :acct"),
                    {"acct": tag},
                )
            except Exception:
                pass
            try:
                conn.execute(
                    text("DELETE FROM channel_daily_metrics WHERE account_tag = :acct"),
                    {"acct": tag},
                )
            except Exception:
                pass


def _kickoff_get_data(account_tag: str, env_extra: Optional[dict] = None) -> None:
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
        env = os.environ.copy()
        if env_extra:
            env.update(env_extra)
        subprocess.Popen(
            [sys.executable, script_path, account_tag],
            cwd=repo_root,
            env=env,
        )
    except Exception as e:
        print(f"[WARN] Failed to start get_data.py: {e}")


def _run_token_names_from_row(row: UserScheduleRun) -> List[str]:
    raw = (row.token_names or "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass
    if row.token_name:
        return [row.token_name]
    return []


def _run_channel_titles(db: Session, user_id: int, token_names: List[str]) -> List[str]:
    if not token_names:
        return []
    rows = (
        db.query(UserCredential.token_name, UserCredential.selected_channel_title, UserCredential.account_tag)
        .filter(
            UserCredential.user_id == user_id,
            UserCredential.token_name.in_(token_names),
        )
        .all()
    )
    title_map = {
        row.token_name: (row.selected_channel_title or row.account_tag or row.token_name or "")
        for row in rows
        if row.token_name
    }
    out = []
    for token_name in token_names:
        title = title_map.get(token_name, account_tag_from_token_name(token_name))
        if title:
            out.append(title)
    return out


def _pick_primary_channel(credentials):
    yt = build("youtube", "v3", credentials=credentials)
    req = yt.channels().list(part="snippet", mine=True, maxResults=50)
    while req is not None:
        resp = req.execute() or {}
        items = resp.get("items", [])
        if items:
            item = items[0]
            channel_id = item.get("id", "") or ""
            snippet = item.get("snippet", {}) or {}
            title = snippet.get("title", "") or channel_id
            return channel_id, title
        req = yt.channels().list_next(req, resp)
    return "", ""


__all__ = [name for name in globals() if not name.startswith("__")]
