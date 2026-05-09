from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from python_backend.api.auth import schemas
from python_backend.api.auth.auth_utils import get_current_user, hash_password
from python_backend.api.auth.database import get_db
from python_backend.api.auth.models import (
    LiveCounterSnapshot,
    PasswordChangeRequest,
    RivalChannel,
    RivalChannelGroup,
    RivalGroup,
    SmmstoreAnalyticsCache,
    SmmstoreScheduledOrder,
    TokenProgress,
    User,
    UserCredential,
    UserCredentialGroup,
    UserHiddenChannel,
    UserSchedule,
    UserScheduleRun,
    VideoLiveCounterSnapshot,
)

from .common import router, _is_admin_user, _is_env_admin_username, _require_admin


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


