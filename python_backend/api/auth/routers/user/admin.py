from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from python_backend.api.auth import schemas
from python_backend.api.auth.auth_utils import hash_password
from python_backend.api.auth.permissions import require_permission
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
    UserChannelAccess,
    UserCredential,
    UserCredentialGroup,
    UserHiddenChannel,
    UserSchedule,
    UserScheduleRun,
    VideoLiveCounterSnapshot,
)

from .common import (
    router,
    _is_admin_user,
    _is_env_admin_username,
    _is_owner_user,
    log_permission_audit,
)


@router.get("/admin/users")
def admin_list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_users")),
):
    rows = db.query(User).order_by(User.username.asc(), User.id.asc()).all()
    return {
        "items": [
            {
                "id": row.id,
                "username": row.username,
                "name": row.name or "",
                "is_admin": _is_admin_user(row),
                "is_owner": _is_owner_user(row),
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
    current_user: User = Depends(require_permission("manage_users")),
):
    user_row = db.query(User).filter(User.id == user_id).first()
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    if not (payload.new_password or "").strip():
        raise HTTPException(status_code=400, detail="New password is required")

    user_row.password = hash_password(payload.new_password)
    db.add(user_row)
    db.commit()
    log_permission_audit(
        db,
        actor=current_user,
        action="password_reset",
        target_user_id=user_row.id,
        meta={"target_username": user_row.username},
    )
    return {"ok": True}


@router.post("/admin/users/{user_id}/admin")
def admin_update_user_role(
    user_id: int,
    payload: schemas.AdminUserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_users")),
):
    user_row = db.query(User).filter(User.id == user_id).first()
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    if user_row.id == current_user.id and not payload.is_admin:
        raise HTTPException(status_code=400, detail="You cannot revoke your own admin access")
    if _is_env_admin_username(user_row.username) and not payload.is_admin:
        raise HTTPException(status_code=400, detail="This environment admin cannot be revoked here")
    if _is_owner_user(user_row) and not _is_owner_user(current_user):
        raise HTTPException(
            status_code=403,
            detail="Only an owner can change an owner's admin status.",
        )

    previous_admin = bool(user_row.is_admin)
    user_row.is_admin = bool(payload.is_admin)
    db.add(user_row)
    db.commit()
    db.refresh(user_row)
    log_permission_audit(
        db,
        actor=current_user,
        action="role_change",
        target_user_id=user_row.id,
        meta={
            "previous_is_admin": previous_admin,
            "new_is_admin": bool(user_row.is_admin),
            "target_username": user_row.username,
        },
    )
    return {
        "ok": True,
        "user": {
            "id": user_row.id,
            "username": user_row.username,
            "name": user_row.name or "",
            "is_admin": _is_admin_user(user_row),
            "is_owner": _is_owner_user(user_row),
            "is_admin_via_env": _is_env_admin_username(user_row.username),
            "avatar_url": user_row.avatar_url or "",
        },
    }


def _clean_access_values(values):
    seen = set()
    out = []
    for value in values or []:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


@router.get("/admin/users/{user_id}/access")
def admin_get_user_access(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_users")),
):
    user_row = db.query(User).filter(User.id == user_id).first()
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    rows = (
        db.query(UserChannelAccess)
        .filter(UserChannelAccess.user_id == user_id)
        .order_by(UserChannelAccess.scope_type.asc(), UserChannelAccess.scope_value.asc())
        .all()
    )
    access = {"projects": [], "channels": []}
    for row in rows:
        key = f"{row.scope_type}s"
        if key in access:
            access[key].append(row.scope_value)

    resolved_rows = (
        db.query(UserCredential.account_tag)
        .filter(UserCredential.token_name.isnot(None))
        .all()
    )
    return {
        "user_id": user_id,
        "projects": access["projects"],
        "channels": access["channels"],
        "all_channels": [row[0] for row in resolved_rows if row[0]],
    }


@router.put("/admin/users/{user_id}/access")
def admin_update_user_access(
    user_id: int,
    payload: schemas.AdminUserAccessUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_users")),
):
    user_row = db.query(User).filter(User.id == user_id).first()
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    if _is_admin_user(user_row):
        raise HTTPException(status_code=400, detail="Admin users can access every channel")

    previous_rows = (
        db.query(UserChannelAccess.scope_type, UserChannelAccess.scope_value)
        .filter(UserChannelAccess.user_id == user_id)
        .all()
    )
    previous = {
        "projects": sorted(r.scope_value for r in previous_rows if r.scope_type == "project"),
        "channels": sorted(r.scope_value for r in previous_rows if r.scope_type == "channel"),
    }
    next_projects = _clean_access_values(payload.projects)
    next_channels = _clean_access_values(payload.channels)
    db.query(UserChannelAccess).filter(UserChannelAccess.user_id == user_id).delete()
    for scope_type, values in (
        ("project", next_projects),
        ("channel", next_channels),
    ):
        for value in values:
            db.add(
                UserChannelAccess(
                    user_id=user_id,
                    scope_type=scope_type,
                    scope_value=value,
                )
            )
    db.commit()
    log_permission_audit(
        db,
        actor=current_user,
        action="access_update",
        target_user_id=user_id,
        meta={
            "previous": previous,
            "next": {
                "projects": sorted(next_projects),
                "channels": sorted(next_channels),
            },
            "target_username": user_row.username,
        },
    )
    return {
        "ok": True,
        "user_id": user_id,
        "projects": next_projects,
        "channels": next_channels,
    }


@router.delete("/admin/users/{user_id}")
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_users")),
):
    user_row = db.query(User).filter(User.id == user_id).first()
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    if user_row.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    if _is_env_admin_username(user_row.username):
        raise HTTPException(status_code=400, detail="This environment admin cannot be deleted here")
    if _is_owner_user(user_row):
        raise HTTPException(status_code=403, detail="Owner accounts cannot be deleted here")

    db.query(PasswordChangeRequest).filter(PasswordChangeRequest.user_id == user_row.id).delete()
    db.query(UserChannelAccess).filter(UserChannelAccess.user_id == user_row.id).delete()
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
    target_username = user_row.username
    target_id = user_row.id
    db.delete(user_row)
    db.commit()
    log_permission_audit(
        db,
        actor=current_user,
        action="user_delete",
        target_user_id=target_id,
        meta={"target_username": target_username},
    )
    return {"ok": True}
