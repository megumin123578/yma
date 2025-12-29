import os
import json
import re
import time
import pickle
import subprocess
import sys
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from google_auth_oauthlib.flow import InstalledAppFlow
from python_backend.api.auth.database import get_db
from python_backend.api.auth.models import User, RivalChannel, RivalChannelGroup, RivalGroup
from python_backend.api.auth.auth_utils import get_current_user, get_current_user_optional
from python_backend.api.auth import schemas
from python_backend.api.auth.schemas import UserMe, UserProfileUpdate
from python_backend.api.auth.models import UserHiddenChannel, UserSchedule, UserScheduleRun, UserCredential
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
    "http://localhost:8000/api/users/credentials/callback",
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


def _kickoff_get_data(account_tag: str) -> None:
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
        subprocess.Popen(
            [sys.executable, script_path, account_tag],
            cwd=repo_root,
            env=os.environ.copy(),
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


@router.get("/credentials/callback")
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

    PENDING_OAUTH.pop(state, None)
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
    _write_progress_file(account_tag, "queued", 0, "queued", "Waiting to start")
    _kickoff_get_data(account_tag)
    return {"ok": True, "token": token_filename}


@router.get("/tokens")
def list_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    hidden = get_hidden_account_tags(db, current_user.id)
    rows = (
        db.query(UserCredential)
        .filter(
            UserCredential.user_id == current_user.id,
            UserCredential.token_name.isnot(None),
        )
        .all()
    )
    files = []
    for row in rows:
        name = row.token_name or ""
        if not name or not name.lower().endswith(".pickle"):
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

    token_path = os.path.join(TOKEN_DIR, safe_name)
    if not os.path.exists(token_path):
        raise HTTPException(status_code=404, detail="Token not found")

    _write_progress_file(account_tag, "queued", 0, "queued", "Manual refresh")
    _kickoff_get_data(account_tag)
    return {"ok": True}


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
