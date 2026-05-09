import os
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user, get_current_user_optional
from python_backend.api.auth.database import SessionLocal, get_db
from python_backend.api.auth.models import (
    MailOAuthState,
    OAuthState,
    User,
    UserCredential,
)
from python_backend.module_trafficsource import sanitize_filename
from python_backend.progress_state import write_progress
from python_backend.sse_utils import poll_stream, sse_response
from python_backend.token_store import store_token_credentials

from .common import (
    router,
    UPLOAD_DIR,
    _OAUTH_STATE_TTL_MINUTES,
    _build_oauth_flow,
    _complete_mail_oauth_from_shared_callback,
    _fetch_selected_channel_metadata,
    _kickoff_get_data,
    _mark_oauth_state_failed,
    _oauth_state_response,
    _oauth_success_html,
    _pick_primary_channel,
    _resolve_oauth_owner_user,
)


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


def _fetch_oauth_state_snapshot(state: str) -> dict:
    db = SessionLocal()
    try:
        row = db.query(OAuthState).filter(OAuthState.state == state).first()
        if not row:
            return {"ready": False, "status": "missing"}
        if row.expires_at and row.expires_at < datetime.utcnow() and row.status == "pending":
            row.status = "expired"
            row.completed_at = datetime.utcnow()
            db.add(row)
            db.commit()
            return {"ready": False, "status": "expired"}
        if row.status == "completed":
            data = _oauth_state_response(row)
            data["status"] = "completed"
            return data
        return {"ready": False, "status": row.status or "pending"}
    finally:
        db.close()


@router.get("/credentials/state/{state}/stream")
async def stream_oauth_state(state: str, request: Request):
    def is_terminal(snap: dict) -> bool:
        return snap.get("status") in ("completed", "expired", "failed", "missing")

    return sse_response(
        poll_stream(
            request,
            lambda: _fetch_oauth_state_snapshot(state),
            interval_seconds=2.0,
            heartbeat_seconds=20.0,
            is_terminal=is_terminal,
        )
    )


