import os
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from python_backend.api.auth.database import get_db
from python_backend.api.auth.models import User
from python_backend.api.auth.auth_utils import get_current_user
from python_backend.api.auth import schemas
from python_backend.api.auth.schemas import UserMe


router = APIRouter(prefix="/users", tags=["Users"])

UPLOAD_DIR = "python_backend/api/uploads/avatars"
os.makedirs(UPLOAD_DIR, exist_ok=True)


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

@router.get("/me", response_model=UserMe)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user