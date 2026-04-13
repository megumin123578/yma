import os
import re
import json
import subprocess
import sys
import time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from sqlalchemy import or_
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from python_backend.api.auth.database import get_db
from python_backend.api.auth.models import User, RivalChannel, RivalChannelGroup, RivalGroup, UserCredential, UserCredentialGroup, UserCredentialProject
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
_TOKEN_GROUP_COLORS = [
    "#2563eb",
    "#16a34a",
    "#dc2626",
    "#ea580c",
    "#9333ea",
    "#0891b2",
    "#d97706",
    "#db2777",
    "#4f46e5",
    "#0f766e",
]
_UNASSIGNED_PROJECT_GROUP = "__ungrouped__"
_ALLOWED_RUN_STAGES = {
    "content",
    "content_full",
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

def _pick_token_group_color(group_name: str, existing_colors: Optional[set[str]] = None) -> str:
    existing = {
        (color or "").strip().lower()
        for color in (existing_colors or set())
        if (color or "").strip()
    }
    for color in _TOKEN_GROUP_COLORS:
        if color.lower() not in existing:
            return color
    seed = sum(ord(ch) for ch in (group_name or "group"))
    hue = seed % 360
    return f"hsl({hue}, 70%, 45%)"


def _get_global_token_group_color_map(db: Session) -> dict[str, str]:
    rows = (
        db.query(UserCredentialGroup.group_name, UserCredentialGroup.color)
        .order_by(UserCredentialGroup.id.asc())
        .all()
    )
    color_by_group: dict[str, str] = {}
    used_colors: set[str] = set()

    for row in rows:
        name = (row.group_name or "").strip()
        color = (row.color or "").strip()
        if not name or name in color_by_group:
            continue
        if color:
            color_by_group[name] = color
            used_colors.add(color.lower())

    assigned_names = {
        (row[0] or "").strip()
        for row in db.query(UserCredential.group_name)
        .filter(UserCredential.group_name.isnot(None))
        .all()
        if (row[0] or "").strip()
    }
    for name in sorted(assigned_names, key=str.lower):
        if name in color_by_group:
            continue
        color = _pick_token_group_color(name, used_colors)
        color_by_group[name] = color
        used_colors.add(color.lower())

    return color_by_group


def _normalize_project_group_name(group_name: Optional[str]) -> str:
    name = (group_name or "").strip()
    return name if name else _UNASSIGNED_PROJECT_GROUP


def _serialize_project_group_name(group_name: Optional[str]) -> Optional[str]:
    name = (group_name or "").strip()
    if not name or name == _UNASSIGNED_PROJECT_GROUP:
        return None
    return name


def _list_token_projects(db: Session) -> list[dict]:
    project_map: dict[str, str] = {}

    rows = (
        db.query(UserCredentialProject.project_name, UserCredentialProject.group_name)
        .order_by(UserCredentialProject.project_name.asc())
        .all()
    )
    for row in rows:
        project_name = (row.project_name or "").strip()
        if not project_name or project_name in project_map:
            continue
        project_map[project_name] = _normalize_project_group_name(row.group_name)

    assigned_rows = (
        db.query(UserCredential.project_name, UserCredential.group_name)
        .filter(UserCredential.project_name.isnot(None))
        .all()
    )
    for row in assigned_rows:
        project_name = (row.project_name or "").strip()
        if not project_name or project_name in project_map:
            continue
        project_map[project_name] = _normalize_project_group_name(row.group_name)

    return [
        {
            "project_name": project_name,
            "group_name": _serialize_project_group_name(group_name),
        }
        for project_name, group_name in sorted(project_map.items(), key=lambda item: item[0].lower())
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


@router.post("/avatar")
def upload_avatar(
    avatar: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if avatar.content_type not in ["image/png", "image/jpeg"]:
        raise HTTPException(status_code=400, detail="Invalid image type")

    filename = f"user_{current_user.id}.{avatar.filename.split('.')[-1]}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as f:
        f.write(avatar.file.read())

    avatar_url = f"/uploads/avatars/{filename}"

    current_user.avatar_url = avatar_url
    db.add(current_user)    
    db.commit()
    db.refresh(current_user)

    return {"avatarUrl": avatar_url}


@router.post("/credentials")
def start_oauth(
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    owner_user = _resolve_oauth_owner_user(db, current_user)
    auto_name = True
    account_tag = f"pending_{owner_user.id}_{int(time.time() * 1000)}"

    cred_row = (
        db.query(UserCredential)
        .filter(
            UserCredential.user_id == owner_user.id,
            UserCredential.account_tag == account_tag,
        )
        .first()
    )
    if cred_row:
        cred_row.updated_at = datetime.utcnow()
        cred_row.token_name = None
        db.add(cred_row)
    else:
        db.add(
            UserCredential(
                user_id=owner_user.id,
                account_tag=account_tag,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
    db.commit()

    flow = _build_oauth_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="false",
    )
    now = datetime.utcnow()
    db.add(
        OAuthState(
            state=state,
            user_id=owner_user.id,
            account_tag=account_tag,
            auto_name=auto_name,
            status="pending",
            created_at=now,
            expires_at=now + timedelta(minutes=_OAUTH_STATE_TTL_MINUTES),
        )
    )
    db.commit()

    return {"account_tag": "", "auth_url": auth_url, "state": state}


@router.get("/credentials/callback", response_class=HTMLResponse)
def credentials_callback(
    state: str = "",
    code: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    row = db.query(OAuthState).filter(OAuthState.state == state).first()
    if not row:
        mail_row = db.query(MailOAuthState).filter(MailOAuthState.state == state).first()
        if mail_row:
            return _complete_mail_oauth_from_shared_callback(db, mail_row, code=code, error=error)

    if error:
        if row:
            _mark_oauth_state_failed(db, row, f"Authorization failed: {error}")
        raise HTTPException(status_code=400, detail=f"Authorization failed: {error}")

    if not row:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    now = datetime.utcnow()
    if row.status == "completed":
        return _oauth_success_html()
    if row.expires_at and row.expires_at < now:
        row.status = "expired"
        row.completed_at = now
        db.add(row)
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    if row.status == "failed":
        raise HTTPException(status_code=400, detail=row.error_message or "OAuth flow failed")

    account_tag = row.account_tag or ""
    flow = _build_oauth_flow()
    try:
        flow.fetch_token(code=code)
    except Exception as e:
        _mark_oauth_state_failed(db, row, f"Failed to fetch token: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to fetch token: {e}")

    token_filename = account_tag
    token_name = token_filename

    user_id = row.user_id
    cred_row = None
    if user_id is not None:
        cred_row = (
            db.query(UserCredential)
            .filter(
                UserCredential.user_id == user_id,
                UserCredential.account_tag == account_tag,
            )
            .first()
        )
        if cred_row:
            cred_row.token_name = token_filename
            cred_row.updated_at = datetime.utcnow()
            db.add(cred_row)
        else:
            db.add(
                UserCredential(
                    user_id=user_id,
                    account_tag=account_tag,
                    token_name=token_filename,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
        db.commit()
        if cred_row is None:
            cred_row = (
                db.query(UserCredential)
                .filter(
                    UserCredential.user_id == user_id,
                    UserCredential.account_tag == account_tag,
                )
                .first()
            )
    channel_id, title = _pick_primary_channel(flow.credentials)
    if not channel_id:
        _mark_oauth_state_failed(db, row, "No YouTube channel found for this account")
        raise HTTPException(status_code=400, detail="No YouTube channel found for this account")

    duplicate_query = db.query(UserCredential).filter(UserCredential.selected_channel_id == channel_id)
    if cred_row is not None:
        duplicate_query = duplicate_query.filter(UserCredential.id != cred_row.id)
    duplicate_channel_row = duplicate_query.order_by(UserCredential.id.asc()).first()
    reused_existing_channel = duplicate_channel_row is not None

    if duplicate_channel_row is not None:
        canonical_tag = duplicate_channel_row.account_tag or sanitize_filename(title) or account_tag
        canonical_token_name = duplicate_channel_row.token_name or canonical_tag
        token_name = canonical_token_name
        account_tag = canonical_tag
        cred_row.token_name = None
        db.delete(cred_row)
        cred_row = duplicate_channel_row

    if row.auto_name and not reused_existing_channel:
        new_tag = sanitize_filename(title) or account_tag
        if new_tag:
            existing = (
                db.query(UserCredential)
                .filter(
                    UserCredential.user_id == user_id,
                    UserCredential.account_tag == new_tag,
                )
                .first()
            )
            if existing and existing.id != cred_row.id:
                base = new_tag
                counter = 2
                while True:
                    candidate = f"{base}_{counter}"
                    existing = (
                        db.query(UserCredential)
                        .filter(
                            UserCredential.user_id == user_id,
                            UserCredential.account_tag == candidate,
                        )
                        .first()
                    )
                    if not existing:
                        new_tag = candidate
                        break
                    counter += 1
        if new_tag and new_tag != account_tag:
            new_token_name = new_tag
            account_tag = new_tag
            token_name = new_token_name

    if cred_row is None:
        _mark_oauth_state_failed(db, row, "OAuth state is missing the user credential record")
        raise HTTPException(status_code=400, detail="OAuth state is missing the user credential record")

    store_token_credentials(token_name, flow.credentials)
    meta = _fetch_selected_channel_metadata(flow.credentials, channel_id=channel_id)
    cred_row.selected_channel_id = meta["channel_id"] or channel_id
    cred_row.selected_channel_title = meta["title"] or title
    cred_row.selected_channel_avatar = meta["avatar"] or cred_row.selected_channel_avatar
    cred_row.account_tag = account_tag
    cred_row.token_name = token_name
    cred_row.updated_at = datetime.utcnow()
    db.add(cred_row)
    row.status = "completed"
    row.token_name = token_name
    row.final_account_tag = account_tag
    row.error_message = None
    row.consumed_at = row.consumed_at or now
    row.completed_at = datetime.utcnow()
    db.add(row)
    db.commit()
    write_progress(account_tag, "queued", 0, "queued", "Queued after authorization")
    _kickoff_get_data(account_tag)

    return _oauth_success_html()


@router.get("/credentials/state/{state}")
def oauth_state(state: str, db: Session = Depends(get_db)):
    row = db.query(OAuthState).filter(OAuthState.state == state).first()
    if not row:
        return {"ready": False}
    if row.expires_at and row.expires_at < datetime.utcnow() and row.status == "pending":
        row.status = "expired"
        row.completed_at = datetime.utcnow()
        db.add(row)
        db.commit()
        return {"ready": False}
    if row.status == "completed":
        return _oauth_state_response(row)
    return {"ready": False}


@router.get("/tokens")
def list_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_admin = _is_admin_user(current_user)
    hidden = get_hidden_account_tags(db, current_user.id)
    group_color_map = _get_global_token_group_color_map(db)
    labels = {}
    avatars = {}
    owned_names = set()
    rows = (
        db.query(
            UserCredential.token_name,
            UserCredential.user_id,
            UserCredential.selected_channel_title,
            UserCredential.account_tag,
            UserCredential.selected_channel_id,
            UserCredential.selected_channel_avatar,
            UserCredential.group_name,
            UserCredential.project_name,
        )
        .filter(UserCredential.token_name.isnot(None))
        .all()
    )
    labels = {
        row.token_name: (row.selected_channel_title or row.account_tag or "")
        for row in rows
        if row.token_name
    }
    avatar_by_token_name = {}
    avatar_by_channel_id = {}
    for row in rows:
        avatar = (row.selected_channel_avatar or "").strip()
        if avatar and row.selected_channel_id and row.selected_channel_id not in avatar_by_channel_id:
            avatar_by_channel_id[row.selected_channel_id] = avatar
        if avatar and row.token_name and row.token_name not in avatar_by_token_name:
            avatar_by_token_name[row.token_name] = avatar
    avatars = {}
    for row in rows:
        if not row.token_name:
            continue
        avatars[row.token_name] = (
            (row.selected_channel_avatar or "").strip()
            or avatar_by_channel_id.get(row.selected_channel_id or "", "")
            or avatar_by_token_name.get(row.token_name, "")
        )
    groups = {}
    projects = {}
    for row in rows:
        if not row.token_name:
            continue
        next_group = (row.group_name or "").strip()
        next_project = (row.project_name or "").strip()
        current_group = groups.get(row.token_name, "")
        if next_group or not current_group:
            groups[row.token_name] = next_group
        current_project = projects.get(row.token_name, "")
        if next_project or not current_project:
            projects[row.token_name] = next_project
    group_colors = {
        token_name: group_color_map.get(group_name, "")
        for token_name, group_name in groups.items()
        if group_name
    }
    if is_admin:
        owned_names = {row.token_name for row in rows if row.token_name}
    else:
        owned_names = {
            row.token_name for row in rows if row.token_name and row.user_id == current_user.id
        }

    files = []
    for name in list_token_names():
        if str(name or "").strip().lower().startswith("mail__"):
            continue
        base = account_tag_from_token_name(name)
        files.append(
            {
                "name": name,
                "hidden": base in hidden,
                "label": labels.get(name, ""),
                "avatar": avatars.get(name, ""),
                "group_name": groups.get(name, ""),
                "project_name": projects.get(name, ""),
                "group_color": group_colors.get(name, ""),
                "owned": name in owned_names,
            }
        )
    files.sort(key=lambda x: x["name"])
    return {"tokens": files}


@router.get("/tokens/progress")
def list_token_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_admin = _is_admin_user(current_user)
    q = db.query(TokenProgress)
    if not is_admin:
        q = q.filter(TokenProgress.user_id == current_user.id)
    rows = q.order_by(TokenProgress.updated_at.desc(), TokenProgress.id.desc()).all()
    return {
        "items": [
            {
                "token_name": row.token_name,
                "account_tag": row.account_tag,
                "run_id": row.run_id or "",
                "status": row.status,
                "percent": row.percent,
                "stage": row.stage or "",
                "message": row.message or "",
                "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else "",
                "started_at": row.started_at.isoformat() + "Z" if row.started_at else "",
                "finished_at": row.finished_at.isoformat() + "Z" if row.finished_at else "",
            }
            for row in rows
        ]
    }


class TokenVisibilityUpdate(BaseModel):
    token: str
    hidden: bool


class TokenGroupUpdate(BaseModel):
    group_name: Optional[str] = None


class TokenProjectUpdate(BaseModel):
    group_name: Optional[str] = None
    project_name: Optional[str] = None


@router.post("/tokens/visibility")
def set_token_visibility(
    payload: TokenVisibilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    token_name = _require_valid_token_name(payload.token)
    base_name = account_tag_from_token_name(token_name)
    token_row = (
        db.query(UserCredential)
        .filter(UserCredential.token_name == token_name)
        .first()
    )
    if not token_row:
        raise HTTPException(status_code=404, detail="Token not found")
    row = (
        db.query(UserHiddenChannel)
        .filter(
            UserHiddenChannel.user_id == current_user.id,
            UserHiddenChannel.account_tag == base_name,
        )
        .first()
    )
    if payload.hidden:
        if not row:
            db.add(UserHiddenChannel(user_id=current_user.id, account_tag=base_name))
            db.commit()
    else:
        if row:
            db.delete(row)
            db.commit()
    return {"ok": True, "hidden": payload.hidden}


@router.get("/tokens/groups")
def list_token_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    color_by_group = _get_global_token_group_color_map(db)
    return {
        "groups": [
            {"group_name": name, "color": color_by_group[name]}
            for name in sorted(color_by_group.keys(), key=str.lower)
        ]
    }


@router.get("/tokens/projects")
def list_token_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    return {"projects": _list_token_projects(db)}


@router.post("/tokens/groups")
def create_token_group(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    name = (payload.get("group_name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="group_name is required")
    color_by_group = _get_global_token_group_color_map(db)
    if name in color_by_group:
        return {"ok": True, "group_name": name, "color": color_by_group[name]}
    color = _pick_token_group_color(name, set(color.lower() for color in color_by_group.values()))
    db.add(UserCredentialGroup(user_id=current_user.id, group_name=name, color=color))
    db.commit()
    return {"ok": True, "group_name": name, "color": color}


@router.post("/tokens/projects")
def create_token_project(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    project_name = (payload.get("project_name") or "").strip()
    if not project_name:
        raise HTTPException(status_code=400, detail="project_name is required")
    existing = {item["project_name"] for item in _list_token_projects(db)}
    if project_name in existing:
        return {"ok": True, "group_name": None, "project_name": project_name}
    db.add(
        UserCredentialProject(
            user_id=current_user.id,
            group_name=_UNASSIGNED_PROJECT_GROUP,
            project_name=project_name,
        )
    )
    db.commit()
    return {"ok": True, "group_name": None, "project_name": project_name}


@router.patch("/tokens/groups/{group_name}")
def rename_token_group(
    group_name: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    current_name = (group_name or "").strip()
    next_name = (payload.get("group_name") or "").strip()
    if not current_name:
        raise HTTPException(status_code=400, detail="group_name is required")
    if not next_name:
        raise HTTPException(status_code=400, detail="New group_name is required")
    if current_name == next_name:
        return {"ok": True, "group_name": next_name}
    color_by_group = _get_global_token_group_color_map(db)
    if next_name in color_by_group:
        raise HTTPException(status_code=400, detail="Group name already exists")
    color = color_by_group.get(current_name, "")
    if not color:
        raise HTTPException(status_code=404, detail="Group not found")
    rows = (
        db.query(UserCredentialGroup)
        .filter(UserCredentialGroup.group_name == current_name)
        .all()
    )
    for row in rows:
        row.group_name = next_name
        row.color = color
        db.add(row)
    if not rows:
        db.add(UserCredentialGroup(user_id=current_user.id, group_name=next_name, color=color))
    project_rows = (
        db.query(UserCredentialProject)
        .filter(UserCredentialProject.group_name == current_name)
        .all()
    )
    for row in project_rows:
        row.group_name = next_name
        db.add(row)
    (
        db.query(UserCredential)
        .filter(UserCredential.group_name == current_name)
        .update({"group_name": next_name}, synchronize_session=False)
    )
    db.commit()
    return {"ok": True, "group_name": next_name, "color": color}


@router.patch("/tokens/projects/{project_name}")
def rename_token_project(
    project_name: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    current_name = (project_name or "").strip()
    next_name = (payload.get("project_name") or "").strip()
    if not current_name:
        raise HTTPException(status_code=400, detail="project_name is required")
    if not next_name:
        raise HTTPException(status_code=400, detail="New project_name is required")
    if current_name == next_name:
        row = (
            db.query(UserCredentialProject)
            .filter(UserCredentialProject.project_name == current_name)
            .first()
        )
        return {
            "ok": True,
            "group_name": _serialize_project_group_name(getattr(row, "group_name", None)),
            "project_name": next_name,
        }
    existing = {item["project_name"] for item in _list_token_projects(db)}
    if next_name in existing:
        raise HTTPException(status_code=400, detail="Project name already exists")
    rows = (
        db.query(UserCredentialProject)
        .filter(
            UserCredentialProject.project_name == current_name,
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Project not found")
    stored_group_name = _normalize_project_group_name(rows[0].group_name)
    for row in rows:
        row.project_name = next_name
        db.add(row)
    (
        db.query(UserCredential)
        .filter(
            UserCredential.project_name == current_name,
        )
        .update({"project_name": next_name}, synchronize_session=False)
    )
    db.commit()
    return {
        "ok": True,
        "group_name": _serialize_project_group_name(stored_group_name),
        "project_name": next_name,
    }


@router.delete("/tokens/groups/{group_name}")
def delete_token_group(
    group_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    name = (group_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="group_name is required")
    color_by_group = _get_global_token_group_color_map(db)
    if name not in color_by_group:
        raise HTTPException(status_code=404, detail="Group not found")
    (
        db.query(UserCredential)
        .filter(UserCredential.group_name == name)
        .update({"group_name": None, "project_name": None}, synchronize_session=False)
    )
    (
        db.query(UserCredentialProject)
        .filter(UserCredentialProject.group_name == name)
        .delete()
    )
    deleted = (
        db.query(UserCredentialGroup)
        .filter(UserCredentialGroup.group_name == name)
        .delete()
    )
    db.commit()
    return {"ok": True, "deleted": deleted}


@router.delete("/tokens/projects/{project_name}")
def delete_token_project(
    project_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    current_name = (project_name or "").strip()
    if not current_name:
        raise HTTPException(status_code=400, detail="project_name is required")
    (
        db.query(UserCredential)
        .filter(
            UserCredential.project_name == current_name,
        )
        .update({"project_name": None}, synchronize_session=False)
    )
    deleted = (
        db.query(UserCredentialProject)
        .filter(
            UserCredentialProject.project_name == current_name,
        )
        .delete()
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    db.commit()
    return {"ok": True, "deleted": deleted}


@router.post("/tokens/projects/{project_name}/group")
def assign_project_group(
    project_name: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    current_name = (project_name or "").strip()
    group_name = (payload.get("group_name") or "").strip()
    if not current_name:
        raise HTTPException(status_code=400, detail="project_name is required")
    if group_name:
        color_by_group = _get_global_token_group_color_map(db)
        if group_name not in color_by_group:
            raise HTTPException(status_code=404, detail="Group not found")
    row = (
        db.query(UserCredentialProject)
        .filter(UserCredentialProject.project_name == current_name)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    row.group_name = _normalize_project_group_name(group_name)
    db.add(row)
    (
        db.query(UserCredential)
        .filter(UserCredential.project_name == current_name)
        .update({"group_name": group_name or None}, synchronize_session=False)
    )
    db.commit()
    return {"ok": True, "project_name": current_name, "group_name": group_name or None}


@router.post("/tokens/{token_name}/group")
def assign_token_group(
    token_name: str,
    payload: TokenGroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    safe_name = _require_valid_token_name(token_name)
    owned = _find_owned_credential_by_identifier(
        db,
        current_user.id,
        safe_name,
        allow_all_users=_is_admin_user(current_user),
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")
    group_name = (payload.group_name or "").strip()
    color_by_group = _get_global_token_group_color_map(db)
    group_color = color_by_group.get(group_name, "") if group_name else ""
    if group_name:
        if not group_color:
            group_color = _pick_token_group_color(
                group_name,
                set(color.lower() for color in color_by_group.values()),
            )
            db.add(UserCredentialGroup(user_id=current_user.id, group_name=group_name, color=group_color))
    now = datetime.utcnow()
    current_row = owned
    current_project_name = (current_row.project_name or "").strip() if current_row else ""
    next_project_name = current_project_name if current_row and (current_row.group_name or "").strip() == group_name else ""
    (
        db.query(UserCredential)
        .filter(UserCredential.id == owned.id)
        .update(
            {
                "group_name": group_name or None,
                "project_name": next_project_name or None,
                "updated_at": now,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return {
        "ok": True,
        "group_name": group_name or None,
        "project_name": next_project_name or None,
        "group_color": group_color,
    }


@router.post("/token/{token_name}/project")
@router.post("/tokens/{token_name}/project")
def assign_token_project(
    token_name: str,
    payload: TokenProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    safe_name = _require_valid_token_name(token_name)
    owned = _find_owned_credential_by_identifier(
        db,
        current_user.id,
        safe_name,
        allow_all_users=_is_admin_user(current_user),
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")
    group_name = (payload.group_name or "").strip()
    project_name = (payload.project_name or "").strip()
    current_group_name = (owned.group_name or "").strip()
    current_project_name = (owned.project_name or "").strip()
    if group_name:
        color_by_group = _get_global_token_group_color_map(db)
        if group_name not in color_by_group:
            raise HTTPException(status_code=404, detail="Group not found")
    if (
        project_name
        and current_project_name
        and (
            current_project_name != project_name
            or current_group_name != group_name
        )
    ):
        raise HTTPException(
            status_code=409,
            detail="Channel already belongs to another project. Remove it there first.",
        )
    if project_name:
        project_row = (
            db.query(UserCredentialProject)
            .filter(UserCredentialProject.project_name == project_name)
            .first()
        )
        if project_row:
            project_row.group_name = _normalize_project_group_name(group_name)
            db.add(project_row)
        else:
            db.add(
                UserCredentialProject(
                    user_id=current_user.id,
                    group_name=_normalize_project_group_name(group_name),
                    project_name=project_name,
                )
            )
    now = datetime.utcnow()
    (
        db.query(UserCredential)
        .filter(UserCredential.id == owned.id)
        .update(
            {
                "group_name": group_name or None,
                "project_name": project_name or None,
                "updated_at": now,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return {
        "ok": True,
        "group_name": group_name or None,
        "project_name": project_name or None,
    }


class RunAllTokensPayload(BaseModel):
    stage: Optional[str] = None


@router.post("/tokens/run-all")
def run_all_tokens(
    payload: Optional[RunAllTokensPayload] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stage = ((payload.stage if payload else "") or "").strip().lower()
    if stage and stage not in _ALLOWED_RUN_STAGES:
        raise HTTPException(status_code=400, detail="Invalid stage")

    is_admin = _is_admin_user(current_user)
    token_names = []
    if is_admin:
        token_names = list_token_names()
    else:
        hidden = get_hidden_account_tags(db, current_user.id)
        rows = (
            db.query(UserCredential.token_name, UserCredential.account_tag)
            .filter(
                UserCredential.user_id == current_user.id,
                UserCredential.token_name.isnot(None),
            )
            .all()
        )
        for row in rows:
            if not row.token_name:
                continue
            if (row.account_tag or "") in hidden:
                continue
            if not token_exists(row.token_name):
                continue
            token_names.append(row.token_name)
        token_names = sorted(set(token_names))

    if not token_names:
        raise HTTPException(status_code=400, detail="No tokens available to run")

    queued_progress_message = "Queued manual refresh" if not stage else f"Queued manual {stage}"
    for token_name in token_names:
        account_tag = account_tag_from_token_name(token_name)
        write_progress(account_tag, "queued", 0, "queued", queued_progress_message)

    run_type = "manual_all" if not stage else f"manual_all_stage:{stage}"
    if not stage:
        run_message = f"Queued manual refresh for {len(token_names)} token(s)"
    else:
        run_message = f"Queued manual {stage} for {len(token_names)} token(s)"

    run = UserScheduleRun(
        user_id=current_user.id,
        schedule_id=None,
        token_name=None,
        token_names=json.dumps(token_names),
        run_type=run_type,
        status="queued",
        started_at=datetime.utcnow(),
        processed=0,
        total=len(token_names),
        message=run_message,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    env_extra = {
        "SCHEDULE_RUN_ID": str(run.id),
        "RUN_TOKEN_NAMES": json.dumps(token_names),
    }
    if stage:
        env_extra["RUN_STAGE"] = stage
    _kickoff_get_data(
        "",
        env_extra=env_extra,
    )
    return {"ok": True, "run_id": run.id, "token_names": token_names, "stage": stage}


@router.get("/tokens/{token_name}/channels")
def list_token_channels(
    token_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_name = _require_valid_token_name(token_name)

    owned = (
        db.query(UserCredential)
        .filter(
            UserCredential.user_id == current_user.id,
            UserCredential.token_name == token_name,
        )
        .first()
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")

    creds = _load_token_credentials(safe_name)
    yt = build("youtube", "v3", credentials=creds)
    req = yt.channels().list(part="snippet,contentDetails", mine=True, maxResults=50)
    channels = []
    while req is not None:
        resp = req.execute() or {}
        for item in resp.get("items", []):
            snippet = item.get("snippet", {})
            content = item.get("contentDetails", {})
            channels.append(
                {
                    "id": item.get("id", ""),
                    "title": snippet.get("title", ""),
                    "customUrl": snippet.get("customUrl", ""),
                    "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                    "uploadsPlaylistId": content.get("relatedPlaylists", {}).get("uploads", ""),
                }
            )
        req = yt.channels().list_next(req, resp)

    return {
        "channels": channels,
        "selected_channel_id": owned.selected_channel_id,
        "selected_channel_title": owned.selected_channel_title,
    }


@router.post("/tokens/{token_name}/channel")
def set_token_channel(
    token_name: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_name = _require_valid_token_name(token_name)

    owned = (
        db.query(UserCredential)
        .filter(
            UserCredential.user_id == current_user.id,
            UserCredential.token_name == token_name,
        )
        .first()
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")

    channel_id = (payload.get("channel_id") or "").strip()
    if not channel_id:
        raise HTTPException(status_code=400, detail="channel_id is required")

    creds = _load_token_credentials(safe_name)
    meta = _fetch_selected_channel_metadata(creds, channel_id=channel_id)
    owned.selected_channel_id = meta["channel_id"] or channel_id
    owned.selected_channel_title = meta["title"]
    owned.selected_channel_avatar = meta["avatar"] or None
    owned.updated_at = datetime.utcnow()
    db.add(owned)
    db.commit()
    account_tag = account_tag_from_token_name(safe_name)
    write_progress(account_tag, "queued", 0, "queued", "Queued after authorization")
    _kickoff_get_data(account_tag)
    return {
        "ok": True,
        "selected_channel_id": owned.selected_channel_id,
        "selected_channel_title": owned.selected_channel_title,
        "selected_channel_avatar": owned.selected_channel_avatar,
    }


@router.post("/tokens/{token_name}/refresh-avatar")
def refresh_token_avatar(
    token_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_name = _require_valid_token_name(token_name)

    is_admin = _is_admin_user(current_user)
    q = db.query(UserCredential).filter(UserCredential.token_name == token_name)
    if not is_admin:
        q = q.filter(UserCredential.user_id == current_user.id)
    owned = q.first()
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")

    creds = _load_token_credentials(safe_name)
    meta = _fetch_selected_channel_metadata(creds, channel_id=owned.selected_channel_id or None)

    owned.selected_channel_id = meta["channel_id"] or owned.selected_channel_id
    owned.selected_channel_title = meta["title"] or owned.selected_channel_title
    owned.selected_channel_avatar = meta["avatar"] or None
    owned.updated_at = datetime.utcnow()
    db.add(owned)
    db.commit()

    return {
        "ok": True,
        "selected_channel_id": owned.selected_channel_id,
        "selected_channel_title": owned.selected_channel_title,
        "selected_channel_avatar": owned.selected_channel_avatar,
    }


@router.get("/tokens/{token_name}/progress")
def get_token_progress(
    token_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_name = _require_valid_token_name(token_name)

    account_tag = account_tag_from_token_name(safe_name)
    is_admin = _is_admin_user(current_user)
    q = db.query(UserCredential).filter(UserCredential.token_name == token_name)
    if not is_admin:
        q = q.filter(UserCredential.user_id == current_user.id)
    owned = q.first()
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")
    progress_row = (
        db.query(TokenProgress)
        .filter(
            TokenProgress.user_id == owned.user_id,
            TokenProgress.token_name == token_name,
        )
        .first()
    )
    if progress_row:
        return {
            "account_tag": progress_row.account_tag,
            "status": progress_row.status,
            "percent": progress_row.percent,
            "stage": progress_row.stage or "",
            "message": progress_row.message or "",
            "run_id": progress_row.run_id or "",
            "updated_at": progress_row.updated_at.isoformat() + "Z" if progress_row.updated_at else "",
            "started_at": progress_row.started_at.isoformat() + "Z" if progress_row.started_at else "",
            "finished_at": progress_row.finished_at.isoformat() + "Z" if progress_row.finished_at else "",
        }
    return {"status": "idle", "percent": 0}


@router.post("/tokens/{token_name}/run")
def run_token(
    token_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_name = _require_valid_token_name(token_name)

    account_tag = account_tag_from_token_name(safe_name)
    is_admin = _is_admin_user(current_user)
    q = db.query(UserCredential).filter(UserCredential.token_name == token_name)
    if not is_admin:
        q = q.filter(UserCredential.user_id == current_user.id)
    owned = q.first()
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")

    if not token_exists(safe_name):
        raise HTTPException(status_code=404, detail="Token not found")

    write_progress(account_tag, "queued", 0, "queued", "Manual refresh")
    run = UserScheduleRun(
        user_id=owned.user_id,
        schedule_id=None,
        token_name=safe_name,
        token_names=json.dumps([safe_name]),
        run_type="manual_single",
        status="queued",
        started_at=datetime.utcnow(),
        processed=0,
        total=7,
        message="Queued manual refresh",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    _kickoff_get_data(account_tag, env_extra={"SCHEDULE_RUN_ID": str(run.id)})
    return {"ok": True, "run_id": run.id}


class RunStagePayload(BaseModel):
    stage: str


class RunSelectedTokensPayload(BaseModel):
    token_names: List[str]


@router.post("/tokens/run-selected")
def run_selected_tokens(
    payload: RunSelectedTokensPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    requested_token_names = [
        _safe_token_name(str(name or "").strip())
        for name in (payload.token_names or [])
    ]
    requested_token_names = [
        name
        for name in requested_token_names
        if name
        and name == _safe_token_name(name)
    ]
    requested_token_names = sorted(set(requested_token_names))
    if not requested_token_names:
        raise HTTPException(status_code=400, detail="No tokens selected")

    is_admin = _is_admin_user(current_user)
    token_names = []
    if is_admin:
        for token_name in requested_token_names:
            if token_exists(token_name):
                token_names.append(token_name)
    else:
        hidden = get_hidden_account_tags(db, current_user.id)
        rows = (
            db.query(UserCredential.token_name, UserCredential.account_tag)
            .filter(
                UserCredential.user_id == current_user.id,
                UserCredential.token_name.in_(requested_token_names),
            )
            .all()
        )
        for row in rows:
            if not row.token_name:
                continue
            if (row.account_tag or "") in hidden:
                continue
            if not token_exists(row.token_name):
                continue
            token_names.append(row.token_name)
        token_names = sorted(set(token_names))

    if not token_names:
        raise HTTPException(status_code=400, detail="No selected tokens available to run")

    for token_name in token_names:
        account_tag = account_tag_from_token_name(token_name)
        write_progress(account_tag, "queued", 0, "queued", "Queued manual refresh")

    run = UserScheduleRun(
        user_id=current_user.id,
        schedule_id=None,
        token_name=None,
        token_names=json.dumps(token_names),
        run_type="manual_selected",
        status="queued",
        started_at=datetime.utcnow(),
        processed=0,
        total=len(token_names),
        message=f"Queued manual refresh for {len(token_names)} selected token(s)",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    _kickoff_get_data(
        "",
        env_extra={
            "SCHEDULE_RUN_ID": str(run.id),
            "RUN_TOKEN_NAMES": json.dumps(token_names),
        },
    )
    return {"ok": True, "run_id": run.id, "token_names": token_names}


@router.post("/tokens/{token_name}/run-stage")
def run_token_stage(
    token_name: str,
    payload: RunStagePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_name = _require_valid_token_name(token_name)

    stage = (payload.stage or "").strip().lower()
    if stage not in _ALLOWED_RUN_STAGES:
        raise HTTPException(status_code=400, detail="Invalid stage")

    is_admin = _is_admin_user(current_user)
    q = db.query(UserCredential).filter(UserCredential.token_name == token_name)
    if not is_admin:
        q = q.filter(UserCredential.user_id == current_user.id)
    owned = q.first()
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")

    if not token_exists(safe_name):
        raise HTTPException(status_code=404, detail="Token not found")

    account_tag = account_tag_from_token_name(safe_name)
    write_progress(account_tag, "queued", 0, "queued", f"Manual {stage}")
    run = UserScheduleRun(
        user_id=owned.user_id,
        schedule_id=None,
        token_name=safe_name,
        token_names=json.dumps([safe_name]),
        run_type=f"manual_stage:{stage}",
        status="queued",
        started_at=datetime.utcnow(),
        processed=0,
        total=1,
        message=f"Queued manual {stage}",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    _kickoff_get_data(
        account_tag,
        env_extra={"SCHEDULE_RUN_ID": str(run.id), "RUN_STAGE": stage},
    )
    return {"ok": True, "run_id": run.id}


@router.delete("/tokens/{token_name}")
def delete_token(
    token_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    safe_name = _require_valid_token_name(token_name)

    row = (
        db.query(UserCredential)
        .filter(
            UserCredential.token_name == token_name,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Token not found")
    base_name = account_tag_from_token_name(safe_name)
    delete_token_credentials(safe_name)
    db.query(UserHiddenChannel).filter(
        UserHiddenChannel.account_tag == base_name,
    ).delete()
    db.query(UserCredential).filter(
        UserCredential.token_name == token_name,
    ).delete()
    db.query(TokenProgress).filter(
        TokenProgress.token_name == token_name,
    ).delete()
    db.commit()
    _purge_postgres_account(base_name)
    return {"ok": True}


class ScheduleCreate(BaseModel):
    time_of_day: Optional[str] = None
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    enabled: Optional[bool] = None
    time_of_day: Optional[str] = None


@router.get("/schedules")
def list_schedules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Permission Denied")
    rows = (
        db.query(UserSchedule)
        .order_by(UserSchedule.id.desc())
        .all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "time_of_day": r.time_of_day,
                "enabled": bool(r.enabled),
                "last_run_at": r.last_run_at.isoformat() if r.last_run_at else None,
            }
            for r in rows
        ]
    }


@router.get("/schedules/runs")
def list_schedule_runs(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    is_admin = _is_admin_user(current_user)
    if not is_admin:
        raise HTTPException(status_code=403, detail="Permission Denied")
    rows = (
        db.query(UserScheduleRun)
        .order_by(UserScheduleRun.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "schedule_id": r.schedule_id,
                "token_name": r.token_name,
                "token_names": r.token_names,
                "run_type": r.run_type,
                "channel_titles": _run_channel_titles(db, r.user_id, _run_token_names_from_row(r)),
                "status": r.status,
                "processed": r.processed,
                "total": r.total,
                "message": r.message,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in rows
        ]
    }


@router.post("/schedules/runs/{run_id}/stop")
def stop_schedule_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    row = (
        db.query(UserScheduleRun)
        .filter(UserScheduleRun.id == run_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    if row.status not in {"running", "queued"}:
        return {"ok": True, "status": row.status}
    row.status = "stopped"
    row.message = "Stopped by admin"
    row.finished_at = datetime.utcnow()
    db.add(row)
    db.commit()
    return {"ok": True, "status": row.status}


@router.post("/schedules/runs/{run_id}/resume")
def resume_schedule_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    row = (
        db.query(UserScheduleRun)
        .filter(UserScheduleRun.id == run_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    if row.status in {"running", "queued"}:
        return {"ok": True, "status": row.status, "run_id": row.id}

    token_names = _run_token_names_from_row(row)
    if not token_names:
        raise HTTPException(status_code=400, detail="Run has no tokens to resume")

    valid_token_names = []
    for token_name in token_names:
        safe_name = _safe_token_name(str(token_name or "").strip())
        if not safe_name or safe_name != str(token_name or "").strip():
            continue
        if token_exists(safe_name):
            valid_token_names.append(safe_name)
    valid_token_names = sorted(set(valid_token_names))
    if not valid_token_names:
        raise HTTPException(status_code=400, detail="No tokens available to resume")

    run_type = str(row.run_type or "").strip().lower()
    message = "Queued manual refresh"
    total = len(valid_token_names)
    account_tag = ""
    env_extra = {}

    if run_type == "manual_all":
        for token_name in valid_token_names:
            write_progress(account_tag_from_token_name(token_name), "queued", 0, "queued", "Queued manual refresh")
        message = f"Queued manual refresh for {len(valid_token_names)} token(s)"
        new_run = UserScheduleRun(
            user_id=current_user.id,
            schedule_id=None,
            token_name=None,
            token_names=json.dumps(valid_token_names),
            run_type="manual_all",
            status="queued",
            started_at=datetime.utcnow(),
            processed=0,
            total=len(valid_token_names),
            message=message,
        )
        env_extra = {
            "RUN_TOKEN_NAMES": json.dumps(valid_token_names),
        }
    elif run_type.startswith("manual_all_stage:"):
        stage = run_type.split(":", 1)[1].strip().lower()
        if stage not in _ALLOWED_RUN_STAGES:
            raise HTTPException(status_code=400, detail="Run stage cannot be resumed")
        for token_name in valid_token_names:
            write_progress(account_tag_from_token_name(token_name), "queued", 0, "queued", f"Queued manual {stage}")
        message = f"Queued manual {stage} for {len(valid_token_names)} token(s)"
        new_run = UserScheduleRun(
            user_id=current_user.id,
            schedule_id=None,
            token_name=None,
            token_names=json.dumps(valid_token_names),
            run_type=f"manual_all_stage:{stage}",
            status="queued",
            started_at=datetime.utcnow(),
            processed=0,
            total=len(valid_token_names),
            message=message,
        )
        env_extra = {
            "RUN_TOKEN_NAMES": json.dumps(valid_token_names),
            "RUN_STAGE": stage,
        }
    elif run_type == "manual_selected":
        for token_name in valid_token_names:
            write_progress(account_tag_from_token_name(token_name), "queued", 0, "queued", "Queued manual refresh")
        message = f"Queued manual refresh for {len(valid_token_names)} selected token(s)"
        new_run = UserScheduleRun(
            user_id=current_user.id,
            schedule_id=None,
            token_name=None,
            token_names=json.dumps(valid_token_names),
            run_type="manual_selected",
            status="queued",
            started_at=datetime.utcnow(),
            processed=0,
            total=len(valid_token_names),
            message=message,
        )
        env_extra = {
            "RUN_TOKEN_NAMES": json.dumps(valid_token_names),
        }
    elif run_type.startswith("manual_stage:"):
        stage = run_type.split(":", 1)[1].strip().lower()
        if stage not in _ALLOWED_RUN_STAGES:
            raise HTTPException(status_code=400, detail="Run stage cannot be resumed")
        token_name = valid_token_names[0]
        account_tag = account_tag_from_token_name(token_name)
        write_progress(account_tag, "queued", 0, "queued", f"Manual {stage}")
        message = f"Queued manual {stage}"
        new_run = UserScheduleRun(
            user_id=current_user.id,
            schedule_id=None,
            token_name=token_name,
            token_names=json.dumps([token_name]),
            run_type=f"manual_stage:{stage}",
            status="queued",
            started_at=datetime.utcnow(),
            processed=0,
            total=1,
            message=message,
        )
        env_extra = {"RUN_STAGE": stage}
    else:
        token_name = valid_token_names[0]
        account_tag = account_tag_from_token_name(token_name)
        write_progress(account_tag, "queued", 0, "queued", "Manual refresh")
        message = "Queued manual refresh"
        new_run = UserScheduleRun(
            user_id=current_user.id,
            schedule_id=None,
            token_name=token_name,
            token_names=json.dumps([token_name]),
            run_type="manual_single" if run_type in {"manual_single", "scheduled", ""} else (row.run_type or "manual_single"),
            status="queued",
            started_at=datetime.utcnow(),
            processed=0,
            total=7,
            message=message,
        )

    db.add(new_run)
    db.commit()
    db.refresh(new_run)
    env_extra["SCHEDULE_RUN_ID"] = str(new_run.id)
    _kickoff_get_data(account_tag, env_extra=env_extra)
    return {"ok": True, "status": new_run.status, "run_id": new_run.id}

@router.post("/schedules")
def create_schedule(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    if not payload.time_of_day:
        raise HTTPException(status_code=400, detail="time_of_day is required")

    row = UserSchedule(
        user_id=current_user.id,
        mode="daily",
        time_of_day=payload.time_of_day,
        every_minutes=None,
        enabled=1 if payload.enabled else 0,
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.patch("/schedules/{schedule_id}")
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    row = (
        db.query(UserSchedule)
        .filter(
            UserSchedule.user_id == current_user.id,
            UserSchedule.id == schedule_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if payload.enabled is not None:
        row.enabled = 1 if payload.enabled else 0
    if payload.time_of_day is not None:
        row.time_of_day = payload.time_of_day
    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    return {"ok": True}


@router.delete("/schedules/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    row = (
        db.query(UserSchedule)
        .filter(
            UserSchedule.user_id == current_user.id,
            UserSchedule.id == schedule_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/admin/users")
def admin_list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    rows = db.query(User).order_by(User.username.asc(), User.id.asc()).all()
    return {
        "items": [
            {
                "id": row.id,
                "username": row.username,
                "name": row.name or "",
                "is_admin": _is_admin_user(row),
                "is_admin_via_env": _is_env_admin_username(row.username),
                "avatar_url": row.avatar_url or "",
            }
            for row in rows
        ]
    }


@router.post("/admin/users/{user_id}/reset-password")
def admin_reset_user_password(
    user_id: int,
    payload: schemas.AdminResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    user_row = db.query(User).filter(User.id == user_id).first()
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    if not (payload.new_password or "").strip():
        raise HTTPException(status_code=400, detail="New password is required")

    user_row.password = hash_password(payload.new_password)
    db.add(user_row)
    db.commit()
    return {"ok": True}


@router.post("/admin/users/{user_id}/admin")
def admin_update_user_role(
    user_id: int,
    payload: schemas.AdminUserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    user_row = db.query(User).filter(User.id == user_id).first()
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    if user_row.id == current_user.id and not payload.is_admin:
        raise HTTPException(status_code=400, detail="You cannot revoke your own admin access")
    if _is_env_admin_username(user_row.username) and not payload.is_admin:
        raise HTTPException(status_code=400, detail="This environment admin cannot be revoked here")

    user_row.is_admin = bool(payload.is_admin)
    db.add(user_row)
    db.commit()
    db.refresh(user_row)
    return {
        "ok": True,
        "user": {
            "id": user_row.id,
            "username": user_row.username,
            "name": user_row.name or "",
            "is_admin": _is_admin_user(user_row),
            "is_admin_via_env": _is_env_admin_username(user_row.username),
            "avatar_url": user_row.avatar_url or "",
        },
    }


@router.delete("/admin/users/{user_id}")
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    user_row = db.query(User).filter(User.id == user_id).first()
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    if user_row.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    if _is_env_admin_username(user_row.username):
        raise HTTPException(status_code=400, detail="This environment admin cannot be deleted here")

    db.query(PasswordChangeRequest).filter(PasswordChangeRequest.user_id == user_row.id).delete()
    db.query(UserHiddenChannel).filter(UserHiddenChannel.user_id == user_row.id).delete()
    db.query(UserScheduleRun).filter(UserScheduleRun.user_id == user_row.id).delete()
    db.query(UserSchedule).filter(UserSchedule.user_id == user_row.id).delete()
    db.query(TokenProgress).filter(TokenProgress.user_id == user_row.id).delete()
    db.query(UserCredentialGroup).filter(UserCredentialGroup.user_id == user_row.id).delete()
    db.query(UserCredential).filter(UserCredential.user_id == user_row.id).delete()
    db.query(RivalChannelGroup).filter(RivalChannelGroup.user_id == user_row.id).delete()
    db.query(RivalChannel).filter(RivalChannel.user_id == user_row.id).delete()
    db.query(RivalGroup).filter(RivalGroup.user_id == user_row.id).delete()
    db.query(SmmstoreScheduledOrder).filter(SmmstoreScheduledOrder.user_id == user_row.id).delete()
    db.query(SmmstoreAnalyticsCache).filter(SmmstoreAnalyticsCache.user_id == user_row.id).delete()
    db.query(VideoLiveCounterSnapshot).filter(VideoLiveCounterSnapshot.user_id == user_row.id).delete()
    db.query(LiveCounterSnapshot).filter(LiveCounterSnapshot.user_id == user_row.id).delete()
    db.delete(user_row)
    db.commit()
    return {"ok": True}


@router.get("/me", response_model=UserMe)
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "name": current_user.name,
        "avatar_url": current_user.avatar_url,
        "smmstore_api_key": current_user.smmstore_api_key,
        "is_admin": _is_admin_user(current_user),
    }


@router.put("/profile", response_model=UserMe)
def update_profile(
    data: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.name is not None:
        current_user.name = data.name
    if data.smmstore_api_key is not None:
        current_user.smmstore_api_key = data.smmstore_api_key

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return {
        "id": current_user.id,
        "username": current_user.username,
        "name": current_user.name,
        "avatar_url": current_user.avatar_url,
        "smmstore_api_key": current_user.smmstore_api_key,
        "is_admin": _is_admin_user(current_user),
    }


@router.get("/rivals", response_model=List[schemas.RivalChannelOut])
def list_rivals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(RivalChannel)
        .filter(RivalChannel.user_id == current_user.id)
        .order_by(RivalChannel.id.desc())
        .all()
    )
    groups = (
        db.query(RivalChannelGroup)
        .filter(RivalChannelGroup.user_id == current_user.id)
        .all()
    )
    grouped = {}
    for row in groups:
        grouped.setdefault(row.channel_id, []).append(row.group_name)
    items = []
    for row in rows:
        names = sorted(set(grouped.get(row.channel_id, [])))
        items.append(
            {
                "id": row.id,
                "channel_id": row.channel_id,
                "channel_name": row.channel_name,
                "channel_url": row.channel_url,
                "channel_avatar_url": row.channel_avatar_url,
                "group_name": names[0] if names else None,
                "group_names": names,
            }
        )
    return items


@router.post("/rivals", response_model=schemas.RivalChannelOut)
def add_rival(
    data: schemas.RivalChannelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    channel_id = (data.channel_id or "").strip()
    if not channel_id:
        raise HTTPException(status_code=400, detail="channel_id is required")

    row = (
        db.query(RivalChannel)
        .filter(
            RivalChannel.user_id == current_user.id,
            RivalChannel.channel_id == channel_id,
        )
        .first()
    )
    group_names = None
    if data.group_names is not None:
        group_names = [g.strip() for g in data.group_names if g and g.strip()]
    elif data.group_name is not None:
        group_names = [data.group_name.strip()] if data.group_name.strip() else []

    if row:
        if data.channel_name:
            row.channel_name = data.channel_name
        if data.channel_url:
            row.channel_url = data.channel_url
        if data.channel_avatar_url:
            row.channel_avatar_url = data.channel_avatar_url
        if data.group_name is not None:
            row.group_name = data.group_name
        db.add(row)
        db.commit()
        db.refresh(row)
        if group_names is not None:
            (
                db.query(RivalChannelGroup)
                .filter(
                    RivalChannelGroup.user_id == current_user.id,
                    RivalChannelGroup.channel_id == channel_id,
                )
                .delete()
            )
            for name in sorted(set(group_names)):
                db.add(
                    RivalGroup(user_id=current_user.id, group_name=name)
                )
                db.add(
                    RivalChannelGroup(
                        user_id=current_user.id,
                        channel_id=channel_id,
                        group_name=name,
                    )
                )
            db.commit()
        names = sorted(set(group_names or []))
        return {
            "id": row.id,
            "channel_id": row.channel_id,
            "channel_name": row.channel_name,
            "channel_url": row.channel_url,
            "channel_avatar_url": row.channel_avatar_url,
            "group_name": names[0] if names else None,
            "group_names": names,
        }

    row = RivalChannel(
        user_id=current_user.id,
        channel_id=channel_id,
        channel_name=data.channel_name,
        channel_url=data.channel_url,
        channel_avatar_url=data.channel_avatar_url,
        group_name=data.group_name,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    if group_names is not None:
        for name in sorted(set(group_names)):
            db.add(
                RivalGroup(user_id=current_user.id, group_name=name)
            )
            db.add(
                RivalChannelGroup(
                    user_id=current_user.id,
                    channel_id=channel_id,
                    group_name=name,
                )
            )
        db.commit()
    names = sorted(set(group_names or []))
    return {
        "id": row.id,
        "channel_id": row.channel_id,
        "channel_name": row.channel_name,
        "channel_url": row.channel_url,
        "channel_avatar_url": row.channel_avatar_url,
        "group_name": names[0] if names else None,
        "group_names": names,
    }


@router.delete("/rivals/{channel_id}")
def delete_rival(
    channel_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(RivalChannel)
        .filter(
            RivalChannel.user_id == current_user.id,
            RivalChannel.channel_id == channel_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Channel not found")
    db.query(RivalChannelGroup).filter(
        RivalChannelGroup.user_id == current_user.id,
        RivalChannelGroup.channel_id == channel_id,
    ).delete()
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.delete("/rivals/groups/{group_name}")
def delete_rival_group(
    group_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    name = (group_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="group_name is required")
    updated = (
        db.query(RivalChannelGroup)
        .filter(
            RivalChannelGroup.user_id == current_user.id,
            RivalChannelGroup.group_name == name,
        )
        .delete()
    )
    db.query(RivalGroup).filter(
        RivalGroup.user_id == current_user.id,
        RivalGroup.group_name == name,
    ).delete()
    db.commit()
    return {"ok": True, "updated": updated}


@router.get("/rivals/groups")
def list_rival_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(RivalGroup)
        .filter(RivalGroup.user_id == current_user.id)
        .order_by(RivalGroup.group_name.asc())
        .all()
    )
    return {"groups": [r.group_name for r in rows]}


@router.post("/rivals/groups")
def create_rival_group(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    name = (payload.get("group_name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="group_name is required")
    existing = (
        db.query(RivalGroup)
        .filter(
            RivalGroup.user_id == current_user.id,
            RivalGroup.group_name == name,
        )
        .first()
    )
    if existing:
        return {"ok": True, "group_name": name}
    db.add(RivalGroup(user_id=current_user.id, group_name=name))
    db.commit()
    return {"ok": True, "group_name": name}
