import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from python_backend.api.auth.database import get_db
from python_backend.api.auth.models import User, PasswordChangeRequest
from python_backend.api.auth.auth_utils import (
    hash_password,
    verify_password,
    create_access_token,
)
from python_backend.api.auth.schemas import (
    UserCreate,
    UserLogin,
    ChangePassword,
    TokenWithUser,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    PasswordChangeRequestOut,
)
from python_backend.api.auth.auth_utils import get_current_user
from python_backend.api.auth.permissions import require_permission

router = APIRouter(
    prefix="/api/auth",
    tags=["Auth"]
)

_ADMIN_ENV_KEY = "ADMIN_USERNAME"


def _get_admin_users() -> set[str]:
    raw = os.getenv(_ADMIN_ENV_KEY, "admin")
    return {
        item.strip().lower()
        for item in str(raw).split(",")
        if item and item.strip()
    }


def _is_admin_user(user: User | None) -> bool:
    if not user:
        return False
    return bool(getattr(user, "is_admin", False))


def _require_admin(current_user: User) -> None:
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")


def _serialize_password_change_request(row: PasswordChangeRequest) -> PasswordChangeRequestOut:
    return PasswordChangeRequestOut(
        id=row.id,
        user_id=row.user_id,
        requested_by=row.requested_by,
        status=row.status,
        admin_user_id=row.admin_user_id,
        admin_username=row.admin_username,
        requested_at=row.requested_at.isoformat() + "Z" if row.requested_at else None,
        decided_at=row.decided_at.isoformat() + "Z" if row.decided_at else None,
    )


@router.post("/register")
def register(data: UserCreate, db: Session = Depends(get_db)):
    print("REGISTER DATA:", data)

    user = db.query(User).filter(User.username == data.username).first()
    if user:
        return {
            "success": False,
            "message": "User already existed!!!"
        }

    new_user = User(
        username=data.username,
        password=hash_password(data.password),
        name=data.username,  # default display name
        is_admin=(data.username or "").lower() in _get_admin_users(),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "success": True,
        "message": "Register success"
    }



@router.post("/login", response_model=TokenWithUser)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()

    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user.username})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user, 
    }
    
@router.post("/change-password")
def change_password(
    data: ChangePassword,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(data.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    existing_pending = (
        db.query(PasswordChangeRequest)
        .filter(
            PasswordChangeRequest.user_id == current_user.id,
            PasswordChangeRequest.status == "pending",
        )
        .order_by(PasswordChangeRequest.id.desc())
        .first()
    )
    if existing_pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a pending password change request",
        )

    row = PasswordChangeRequest(
        user_id=current_user.id,
        requested_by=current_user.username,
        new_password_hash=hash_password(data.new_password),
        status="pending",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "message": "Password change request submitted. It will be applied after admin approval.",
        "request": _serialize_password_change_request(row),
    }


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    return {
        "message": "Self-service password reset is disabled. Please sign in and submit a password change request for admin approval."
    }


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Direct password reset is disabled. Please use the password change request flow.",
    )


@router.get("/password-change-requests")
def list_password_change_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_admin = _is_admin_user(current_user)
    q = db.query(PasswordChangeRequest)
    if not is_admin:
        q = q.filter(PasswordChangeRequest.user_id == current_user.id)
    rows = q.order_by(PasswordChangeRequest.requested_at.desc(), PasswordChangeRequest.id.desc()).all()
    return {"items": [_serialize_password_change_request(row).model_dump() for row in rows]}


@router.post("/password-change-requests/{request_id}/approve")
def approve_password_change_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_users")),
):
    row = db.query(PasswordChangeRequest).filter(PasswordChangeRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="Request is no longer pending")

    user = db.query(User).filter(User.id == row.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.utcnow()
    user.password = row.new_password_hash
    row.status = "approved"
    row.admin_user_id = current_user.id
    row.admin_username = current_user.username
    row.decided_at = now
    db.add(user)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "message": "Password change approved",
        "request": _serialize_password_change_request(row).model_dump(),
    }


@router.post("/password-change-requests/{request_id}/reject")
def reject_password_change_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_users")),
):
    row = db.query(PasswordChangeRequest).filter(PasswordChangeRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="Request is no longer pending")

    row.status = "rejected"
    row.admin_user_id = current_user.id
    row.admin_username = current_user.username
    row.decided_at = datetime.utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "message": "Password change rejected",
        "request": _serialize_password_change_request(row).model_dump(),
    }

