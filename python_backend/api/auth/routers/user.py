import os
import json
import re
import time
import pickle
import subprocess
import sys
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from python_backend.api.auth.database import get_db
from python_backend.api.auth.models import User, RivalChannel, RivalChannelGroup, RivalGroup, UserCredential
from python_backend.api.auth.auth_utils import get_current_user, get_current_user_optional
from python_backend.api.auth import schemas
from python_backend.api.auth.schemas import UserMe, UserProfileUpdate
from python_backend.api.auth.models import UserHiddenChannel, UserSchedule, UserScheduleRun
from python_backend.api.auth.visibility import get_hidden_account_tags
from python_backend.module_trafficsource import SCOPES, sanitize_filename
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/users", tags=["Users"])

UPLOAD_DIR = "python_backend/api/uploads/avatars"
os.makedirs(UPLOAD_DIR, exist_ok=True)

CREDENTIALS_DIR = "python_backend/credentials"
os.makedirs(CREDENTIALS_DIR, exist_ok=True)

TOKEN_DIR = "python_backend/token"
os.makedirs(TOKEN_DIR, exist_ok=True)

PROGRESS_DIR = "python_backend/progress"
os.makedirs(PROGRESS_DIR, exist_ok=True)

OAUTH_REDIRECT_URL = os.getenv(
    "OAUTH_REDIRECT_URL",
    "https://77d8302dfd4c.ngrok-free.app/api/users/credentials/callback",
)

PENDING_OAUTH = {}
_ADMIN_ENV_KEY = "ADMIN_USERNAME"


def _safe_filename(name: str) -> str:
    base = os.path.basename(name or "")
    if not base:
        return "credentials.json"
    return re.sub(r"[^A-Za-z0-9_.-]", "_", base)


def _safe_token_filename(name: str) -> str:
    return os.path.basename(name or "")


def _load_token_credentials(token_name: str):
    token_path = os.path.join(TOKEN_DIR, token_name)
    if not os.path.exists(token_path):
        raise HTTPException(status_code=404, detail="Token not found")
    try:
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to read token")
    if not creds:
        raise HTTPException(status_code=400, detail="Invalid token")
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, "wb") as f:
                    pickle.dump(creds, f)
            except Exception:
                raise HTTPException(status_code=400, detail="Failed to refresh token")
        else:
            raise HTTPException(status_code=400, detail="Token is not valid")
    return creds


def _require_admin(current_user: User) -> None:
    if (current_user.username or "").lower() not in _get_admin_users():
        raise HTTPException(status_code=403, detail="Admin access required")


def _get_admin_users() -> set:
    raw = os.getenv(_ADMIN_ENV_KEY, "admin")
    return {u.strip().lower() for u in raw.split(",") if u.strip()}


def _write_progress_file(account_tag: str, status: str, percent: int, stage: str, message: str = "") -> None:
    payload = {
        "account_tag": account_tag,
        "status": status,
        "percent": percent,
        "stage": stage,
        "message": message,
        "updated_at": time.time(),
    }
    try:
        with open(os.path.join(PROGRESS_DIR, f"{account_tag}.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception:
        pass


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
                    text("DELETE FROM reach_video_metrics WHERE account_tag = :acct"),
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
def upload_credentials(
    credentials: UploadFile = File(...),
    filename: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base_name = filename if filename is not None else credentials.filename
    filename = _safe_filename(base_name)
    if not filename.lower().endswith(".json"):
        filename = f"{filename}.json"
    if not filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Credentials must be a .json file")

    content = credentials.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty credentials file")

    try:
        json.loads(content.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    file_path = os.path.join(CREDENTIALS_DIR, filename)
    progress_path = os.path.join(PROGRESS_DIR, f"{os.path.splitext(filename)[0]}.json")
    if os.path.exists(progress_path):
        try:
            os.remove(progress_path)
        except Exception:
            pass

    with open(file_path, "wb") as f:
        f.write(content)

    account_tag = os.path.splitext(os.path.basename(filename))[0]
    cred_row = (
        db.query(UserCredential)
        .filter(
            UserCredential.user_id == current_user.id,
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
                user_id=current_user.id,
                account_tag=account_tag,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
    db.commit()

    flow = InstalledAppFlow.from_client_secrets_file(file_path, SCOPES)
    flow.redirect_uri = OAUTH_REDIRECT_URL
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )
    PENDING_OAUTH[state] = {
        "cred_path": file_path,
        "created_at": time.time(),
        "user_id": current_user.id,
        "account_tag": account_tag,
    }

    return {"filename": filename, "auth_url": auth_url, "state": state}


@router.get("/credentials/callback", response_class=HTMLResponse)
def credentials_callback(
    state: str = "",
    code: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    if error:
        raise HTTPException(status_code=400, detail=f"Authorization failed: {error}")

    pending = PENDING_OAUTH.get(state)
    if not pending:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    cred_path = pending["cred_path"]
    flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
    flow.redirect_uri = OAUTH_REDIRECT_URL
    try:
        flow.fetch_token(code=code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch token: {e}")

    account_tag = pending.get("account_tag") or os.path.splitext(os.path.basename(cred_path))[0]
    token_filename = os.path.splitext(os.path.basename(cred_path))[0] + ".pickle"
    token_path = os.path.join(TOKEN_DIR, token_filename)
    with open(token_path, "wb") as f:
        pickle.dump(flow.credentials, f)

    user_id = pending.get("user_id")
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
    pending["token_name"] = token_filename
    pending["account_tag"] = account_tag
    _write_progress_file(
        account_tag,
        "waiting_channel",
        0,
        "idle",
        "Select a channel to start.",
    )
    yt = build("youtube", "v3", credentials=flow.credentials)
    req = yt.channels().list(part="snippet", mine=True, maxResults=50)
    channels = []
    while req is not None:
        resp = req.execute() or {}
        for item in resp.get("items", []):
            snippet = item.get("snippet", {})
            channels.append(
                {
                    "id": item.get("id", ""),
                    "title": snippet.get("title", "") or item.get("id", ""),
                }
            )
        req = yt.channels().list_next(req, resp)

    options = "\n".join(
        f'<option value="{c["id"]}">{c["title"]}</option>' for c in channels if c["id"]
    )
    return f"""
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Select channel</title>
    <style>
      body {{ font-family: Arial, sans-serif; padding: 24px; background: #0f172a; color: #e2e8f0; }}
      .card {{ max-width: 520px; margin: 40px auto; background: #111827; padding: 24px; border-radius: 12px; border: 1px solid #334155; }}
      h1 {{ font-size: 18px; margin: 0 0 12px; }}
      select, button {{ width: 100%; padding: 10px; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: #e2e8f0; }}
      button {{ margin-top: 12px; background: #22c55e; color: #052e16; font-weight: 700; cursor: pointer; }}
    </style>
  </head>
  <body>
    <div class="card">
      <h1>Select a channel for this credential</h1>
      <form method="post" action="/api/users/credentials/select-channel">
        <input type="hidden" name="state" value="{state}" />
        <select name="channel_id" required>
          {options}
        </select>
        <button type="submit">Confirm</button>
      </form>
    </div>
  </body>
</html>
"""


@router.post("/credentials/select-channel", response_class=HTMLResponse)
def select_channel_after_auth(
    state: str = Form(""),
    channel_id: str = Form(""),
    db: Session = Depends(get_db),
):
    pending = PENDING_OAUTH.get(state)
    if not pending:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    token_name = pending.get("token_name")
    user_id = pending.get("user_id")
    account_tag = pending.get("account_tag")
    if not token_name or not user_id or not account_tag:
        raise HTTPException(status_code=400, detail="Invalid auth state")
    channel_id = (channel_id or "").strip()
    if not channel_id:
        raise HTTPException(status_code=400, detail="channel_id is required")

    creds = _load_token_credentials(token_name)
    yt = build("youtube", "v3", credentials=creds)
    resp = yt.channels().list(part="snippet", id=channel_id, maxResults=1).execute() or {}
    items = resp.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="Channel not found for this token")
    title = items[0].get("snippet", {}).get("title", "")

    cred_row = (
        db.query(UserCredential)
        .filter(
            UserCredential.user_id == user_id,
            UserCredential.account_tag == account_tag,
        )
        .first()
    )
    if not cred_row:
        raise HTTPException(status_code=404, detail="Credential not found")
    cred_row.selected_channel_id = channel_id
    cred_row.selected_channel_title = title
    cred_row.updated_at = datetime.utcnow()
    db.add(cred_row)
    db.commit()

    PENDING_OAUTH.pop(state, None)
    _write_progress_file(account_tag, "queued", 0, "queued", "Queued after channel selection")
    _kickoff_get_data(account_tag)

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
      <h1>Channel selected. You can close this tab.</h1>
      <p>Data sync is now running on the server.</p>
    </div>
  </body>
</html>
"""


@router.get("/tokens")
def list_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_admin = (current_user.username or "").lower() in _get_admin_users()
    hidden = set()
    allowed = None
    if not is_admin:
        hidden = get_hidden_account_tags(db, current_user.id)
        allowed = {
            row.token_name
            for row in db.query(UserCredential.token_name)
            .filter(
                UserCredential.user_id == current_user.id,
                UserCredential.token_name.isnot(None),
            )
            .all()
            if row.token_name
        }

    if not os.path.exists(TOKEN_DIR):
        return {"tokens": []}

    files = []
    for name in os.listdir(TOKEN_DIR):
        if not name.lower().endswith(".pickle"):
            continue
        if allowed is not None and name not in allowed:
            continue
        token_path = os.path.join(TOKEN_DIR, name)
        if not os.path.exists(token_path):
            continue
        base = os.path.splitext(name)[0]
        files.append({"name": name, "hidden": base in hidden})
    files.sort(key=lambda x: x["name"])
    return {"tokens": files}


class TokenVisibilityUpdate(BaseModel):
    token: str
    hidden: bool


@router.post("/tokens/visibility")
def set_token_visibility(
    payload: TokenVisibilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    token_name = _safe_token_filename(payload.token)
    if token_name != payload.token or ".." in token_name:
        raise HTTPException(status_code=400, detail="Invalid token filename")

    base_name = os.path.splitext(token_name)[0]
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


@router.get("/tokens/{token_name}/channels")
def list_token_channels(
    token_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_name = _safe_token_filename(token_name)
    if safe_name != token_name or ".." in safe_name or not safe_name.lower().endswith(".pickle"):
        raise HTTPException(status_code=400, detail="Invalid token filename")

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
    safe_name = _safe_token_filename(token_name)
    if safe_name != token_name or ".." in safe_name or not safe_name.lower().endswith(".pickle"):
        raise HTTPException(status_code=400, detail="Invalid token filename")

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
    yt = build("youtube", "v3", credentials=creds)
    resp = yt.channels().list(part="snippet", id=channel_id, maxResults=1).execute() or {}
    items = resp.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="Channel not found for this token")

    title = items[0].get("snippet", {}).get("title", "")
    owned.selected_channel_id = channel_id
    owned.selected_channel_title = title
    owned.updated_at = datetime.utcnow()
    db.add(owned)
    db.commit()
    account_tag = os.path.splitext(safe_name)[0]
    _write_progress_file(account_tag, "queued", 0, "queued", "Queued after channel selection")
    _kickoff_get_data(account_tag)
    return {"ok": True, "selected_channel_id": channel_id, "selected_channel_title": title}


@router.get("/tokens/{token_name}/progress")
def get_token_progress(
    token_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_name = _safe_token_filename(token_name)
    if safe_name != token_name or ".." in safe_name or not safe_name.lower().endswith(".pickle"):
        raise HTTPException(status_code=400, detail="Invalid token filename")

    account_tag = os.path.splitext(safe_name)[0]
    is_admin = (current_user.username or "").lower() in _get_admin_users()
    q = db.query(UserCredential).filter(UserCredential.token_name == token_name)
    if not is_admin:
        q = q.filter(UserCredential.user_id == current_user.id)
    owned = q.first()
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")
    progress_path = os.path.join(PROGRESS_DIR, f"{account_tag}.json")
    if not os.path.exists(progress_path):
        return {"status": "idle", "percent": 0}
    try:
        with open(progress_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to read progress")


@router.post("/tokens/{token_name}/run")
def run_token(
    token_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_name = _safe_token_filename(token_name)
    if safe_name != token_name or ".." in safe_name or not safe_name.lower().endswith(".pickle"):
        raise HTTPException(status_code=400, detail="Invalid token filename")

    account_tag = os.path.splitext(safe_name)[0]
    is_admin = (current_user.username or "").lower() in _get_admin_users()
    q = db.query(UserCredential).filter(UserCredential.token_name == token_name)
    if not is_admin:
        q = q.filter(UserCredential.user_id == current_user.id)
    owned = q.first()
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")

    token_path = os.path.join(TOKEN_DIR, safe_name)
    if not os.path.exists(token_path):
        raise HTTPException(status_code=404, detail="Token not found")

    _write_progress_file(account_tag, "queued", 0, "queued", "Manual refresh")
    run = UserScheduleRun(
        user_id=owned.user_id,
        schedule_id=None,
        status="running",
        started_at=datetime.utcnow(),
        processed=0,
        total=6,
        message="Manual refresh",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    _kickoff_get_data(account_tag, env_extra={"SCHEDULE_RUN_ID": str(run.id)})
    return {"ok": True, "run_id": run.id}


class RunStagePayload(BaseModel):
    stage: str


@router.post("/tokens/{token_name}/run-stage")
def run_token_stage(
    token_name: str,
    payload: RunStagePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_name = _safe_token_filename(token_name)
    if safe_name != token_name or ".." in safe_name or not safe_name.lower().endswith(".pickle"):
        raise HTTPException(status_code=400, detail="Invalid token filename")

    stage = (payload.stage or "").strip().lower()
    if stage not in {"content", "overview", "audience", "reach"}:
        raise HTTPException(status_code=400, detail="Invalid stage")

    is_admin = (current_user.username or "").lower() in _get_admin_users()
    q = db.query(UserCredential).filter(UserCredential.token_name == token_name)
    if not is_admin:
        q = q.filter(UserCredential.user_id == current_user.id)
    owned = q.first()
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")

    token_path = os.path.join(TOKEN_DIR, safe_name)
    if not os.path.exists(token_path):
        raise HTTPException(status_code=404, detail="Token not found")

    account_tag = os.path.splitext(safe_name)[0]
    _write_progress_file(account_tag, "queued", 0, "queued", f"Manual {stage}")
    run = UserScheduleRun(
        user_id=owned.user_id,
        schedule_id=None,
        status="running",
        started_at=datetime.utcnow(),
        processed=0,
        total=1,
        message=f"Manual {stage}",
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
    safe_name = _safe_token_filename(token_name)
    if safe_name != token_name or ".." in safe_name or not safe_name.lower().endswith(".pickle"):
        raise HTTPException(status_code=400, detail="Invalid token filename")

    token_path = os.path.join(TOKEN_DIR, safe_name)
    if not os.path.exists(token_path):
        raise HTTPException(status_code=404, detail="Token not found")

    os.remove(token_path)
    base_name = os.path.splitext(safe_name)[0]
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
    cred_path = os.path.join(CREDENTIALS_DIR, f"{base_name}.json")
    if os.path.exists(cred_path):
        os.remove(cred_path)
    progress_path = os.path.join(PROGRESS_DIR, f"{base_name}.json")
    if os.path.exists(progress_path):
        try:
            os.remove(progress_path)
        except Exception:
            pass
    db.query(UserHiddenChannel).filter(
        UserHiddenChannel.user_id == current_user.id,
        UserHiddenChannel.account_tag == base_name,
    ).delete()
    db.query(UserCredential).filter(
        UserCredential.user_id == current_user.id,
        UserCredential.token_name == token_name,
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
    current_user: Optional[User] = Depends(get_current_user_optional),
):
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
    is_admin = bool(current_user and (current_user.username or "").lower() in _get_admin_users())
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
    if row.status != "running":
        return {"ok": True, "status": row.status}
    row.status = "stopping"
    row.message = "Stop requested by admin"
    db.add(row)
    db.commit()
    return {"ok": True, "status": row.status}


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

@router.get("/me", response_model=UserMe)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


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

    return current_user


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
