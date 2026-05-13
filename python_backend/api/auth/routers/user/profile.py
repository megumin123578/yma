from fastapi import Depends
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user
from python_backend.api.auth.database import get_db
from python_backend.api.auth.models import User
from python_backend.api.auth.schemas import UserMe, UserProfileUpdate

from .common import router, _is_admin_user, _is_owner_user


@router.get("/me", response_model=UserMe)
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "name": current_user.name,
        "avatar_url": current_user.avatar_url,
        "smmstore_api_key": current_user.smmstore_api_key,
        "is_admin": _is_admin_user(current_user),
        "is_owner": _is_owner_user(current_user),
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
        "is_owner": _is_owner_user(current_user),
    }


