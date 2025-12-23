import os
import json
import re
import time
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from python_backend.api.auth.database import get_db
from python_backend.api.auth.models import User, RivalChannel
from python_backend.api.auth.auth_utils import get_current_user
from python_backend.api.auth import schemas
from python_backend.api.auth.schemas import UserMe, UserProfileUpdate


router = APIRouter(prefix="/users", tags=["Users"])

UPLOAD_DIR = "python_backend/api/uploads/avatars"
os.makedirs(UPLOAD_DIR, exist_ok=True)

CREDENTIALS_DIR = "python_backend/credentials"
os.makedirs(CREDENTIALS_DIR, exist_ok=True)


def _safe_filename(name: str) -> str:
    base = os.path.basename(name or "")
    if not base:
        return "credentials.json"
    return re.sub(r"[^A-Za-z0-9_.-]", "_", base)


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
    current_user: User = Depends(get_current_user),
):
    filename = _safe_filename(credentials.filename)
    if not filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Credentials must be a .json file")

    content = credentials.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty credentials file")

    try:
        json.loads(content.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    stamped = f"user_{current_user.id}_{int(time.time())}_{filename}"
    file_path = os.path.join(CREDENTIALS_DIR, stamped)

    with open(file_path, "wb") as f:
        f.write(content)

    return {"filename": stamped}

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
    return rows


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
    if row:
        if data.channel_name:
            row.channel_name = data.channel_name
        if data.channel_url:
            row.channel_url = data.channel_url
        if data.channel_avatar_url:
            row.channel_avatar_url = data.channel_avatar_url
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    row = RivalChannel(
        user_id=current_user.id,
        channel_id=channel_id,
        channel_name=data.channel_name,
        channel_url=data.channel_url,
        channel_avatar_url=data.channel_avatar_url,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


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
    db.delete(row)
    db.commit()
    return {"ok": True}
