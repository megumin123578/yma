from typing import List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user
from python_backend.api.auth.database import get_db
from python_backend.api.auth.models import Role, RolePermission, User, UserRole
from python_backend.api.auth.permissions import (
    ALL_ACTIONS,
    SCOPE_TYPES,
    require_permission,
    user_permissions,
)

from .common import router, log_permission_audit


# ---------- Schemas ----------


class PermissionEntry(BaseModel):
    action: str
    scope_type: str = "*"
    scope_value: Optional[str] = ""


class RoleCreate(BaseModel):
    name: str
    color: Optional[str] = None
    position: Optional[int] = 0
    is_default: Optional[bool] = False
    permissions: Optional[List[PermissionEntry]] = None


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    position: Optional[int] = None
    is_default: Optional[bool] = None


class RolePermissionsSet(BaseModel):
    permissions: List[PermissionEntry]


class UserRolesSet(BaseModel):
    role_ids: List[int]


# ---------- Helpers ----------


def _serialize_role(db: Session, row: Role) -> dict:
    perms = (
        db.query(RolePermission)
        .filter(RolePermission.role_id == row.id)
        .all()
    )
    member_count = (
        db.query(func.count(UserRole.id)).filter(UserRole.role_id == row.id).scalar() or 0
    )
    return {
        "id": row.id,
        "name": row.name,
        "color": row.color or "",
        "position": int(row.position or 0),
        "is_default": bool(row.is_default),
        "is_system": bool(row.is_system),
        "member_count": int(member_count),
        "permissions": [
            {
                "action": p.action,
                "scope_type": p.scope_type,
                "scope_value": p.scope_value or "",
            }
            for p in perms
        ],
    }


def _validate_permissions(items: List[PermissionEntry]) -> List[dict]:
    cleaned: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items or []:
        action = (item.action or "").strip()
        if action not in ALL_ACTIONS:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
        scope_type = (item.scope_type or "*").strip() or "*"
        if scope_type not in SCOPE_TYPES:
            raise HTTPException(status_code=400, detail=f"Unknown scope_type: {scope_type}")
        scope_value = (item.scope_value or "").strip()
        if scope_type == "*":
            scope_value = ""
        elif not scope_value:
            raise HTTPException(
                status_code=400,
                detail=f"scope_value required for scope_type={scope_type}",
            )
        key = (action, scope_type, scope_value)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(
            {"action": action, "scope_type": scope_type, "scope_value": scope_value}
        )
    return cleaned


def _replace_role_permissions(db: Session, role_id: int, entries: List[dict]) -> None:
    db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
    for entry in entries:
        db.add(
            RolePermission(
                role_id=role_id,
                action=entry["action"],
                scope_type=entry["scope_type"],
                scope_value=entry["scope_value"],
            )
        )


# ---------- Endpoints: roles ----------


@router.get("/admin/roles")
def admin_list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_roles")),
):
    rows = db.query(Role).order_by(Role.position.desc(), Role.name.asc()).all()
    return {"items": [_serialize_role(db, row) for row in rows]}


@router.post("/admin/roles")
def admin_create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_roles")),
):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    existing = db.query(Role).filter(Role.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Role name already exists")
    entries = _validate_permissions(payload.permissions or [])

    role = Role(
        name=name,
        color=payload.color or None,
        position=int(payload.position or 0),
        is_default=bool(payload.is_default),
        is_system=False,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    _replace_role_permissions(db, role.id, entries)
    db.commit()
    log_permission_audit(
        db,
        actor=current_user,
        action="role_create",
        meta={"role_id": role.id, "role_name": role.name, "permissions": entries},
    )
    return {"ok": True, "role": _serialize_role(db, role)}


@router.patch("/admin/roles/{role_id}")
def admin_update_role(
    role_id: int,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_roles")),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system and payload.name and payload.name.strip() != role.name:
        raise HTTPException(status_code=400, detail="Cannot rename system role")

    changes: dict = {}
    if payload.name is not None:
        next_name = payload.name.strip()
        if not next_name:
            raise HTTPException(status_code=400, detail="name is required")
        if next_name != role.name:
            clash = db.query(Role).filter(Role.name == next_name, Role.id != role.id).first()
            if clash:
                raise HTTPException(status_code=400, detail="Role name already exists")
            changes["name"] = {"from": role.name, "to": next_name}
            role.name = next_name
    if payload.color is not None:
        new_color = payload.color or None
        if new_color != role.color:
            changes["color"] = {"from": role.color, "to": new_color}
            role.color = new_color
    if payload.position is not None:
        new_pos = int(payload.position)
        if new_pos != role.position:
            changes["position"] = {"from": role.position, "to": new_pos}
            role.position = new_pos
    if payload.is_default is not None:
        new_default = bool(payload.is_default)
        if new_default != bool(role.is_default):
            changes["is_default"] = {"from": bool(role.is_default), "to": new_default}
            role.is_default = new_default

    db.add(role)
    db.commit()
    db.refresh(role)
    if changes:
        log_permission_audit(
            db,
            actor=current_user,
            action="role_update",
            meta={"role_id": role.id, "role_name": role.name, "changes": changes},
        )
    return {"ok": True, "role": _serialize_role(db, role)}


@router.delete("/admin/roles/{role_id}")
def admin_delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_roles")),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=400, detail="System role cannot be deleted")

    role_name = role.name
    db.query(UserRole).filter(UserRole.role_id == role_id).delete()
    db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
    db.delete(role)
    db.commit()
    log_permission_audit(
        db,
        actor=current_user,
        action="role_delete",
        meta={"role_id": role_id, "role_name": role_name},
    )
    return {"ok": True, "deleted": role_id}


@router.put("/admin/roles/{role_id}/permissions")
def admin_set_role_permissions(
    role_id: int,
    payload: RolePermissionsSet,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_roles")),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=400, detail="System role permissions are fixed")

    previous_rows = (
        db.query(RolePermission)
        .filter(RolePermission.role_id == role_id)
        .all()
    )
    previous = [
        {
            "action": p.action,
            "scope_type": p.scope_type,
            "scope_value": p.scope_value or "",
        }
        for p in previous_rows
    ]
    entries = _validate_permissions(payload.permissions)
    _replace_role_permissions(db, role_id, entries)
    db.commit()
    log_permission_audit(
        db,
        actor=current_user,
        action="role_permissions_update",
        meta={
            "role_id": role.id,
            "role_name": role.name,
            "previous": previous,
            "next": entries,
        },
    )
    return {"ok": True, "role": _serialize_role(db, role)}


# ---------- Endpoints: user roles ----------


@router.get("/admin/users/{user_id}/roles")
def admin_get_user_roles(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_roles")),
):
    user_row = db.query(User).filter(User.id == user_id).first()
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    rows = (
        db.query(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user_id)
        .order_by(Role.position.desc(), Role.name.asc())
        .all()
    )
    return {
        "user_id": user_id,
        "roles": [_serialize_role(db, row) for row in rows],
    }


@router.put("/admin/users/{user_id}/roles")
def admin_set_user_roles(
    user_id: int,
    payload: UserRolesSet,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_roles")),
):
    user_row = db.query(User).filter(User.id == user_id).first()
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    requested_ids = list({int(rid) for rid in payload.role_ids or []})
    if requested_ids:
        existing_ids = {
            r.id for r in db.query(Role.id).filter(Role.id.in_(requested_ids)).all()
        }
        missing = set(requested_ids) - existing_ids
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown role_ids: {sorted(missing)}",
            )

    previous = sorted(
        r.role_id for r in db.query(UserRole.role_id).filter(UserRole.user_id == user_id).all()
    )
    db.query(UserRole).filter(UserRole.user_id == user_id).delete()
    for rid in requested_ids:
        db.add(
            UserRole(
                user_id=user_id,
                role_id=rid,
                assigned_by=current_user.id,
            )
        )
    db.commit()
    log_permission_audit(
        db,
        actor=current_user,
        action="user_roles_update",
        target_user_id=user_id,
        meta={
            "target_username": user_row.username,
            "previous": previous,
            "next": sorted(requested_ids),
        },
    )
    rows = (
        db.query(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user_id)
        .order_by(Role.position.desc(), Role.name.asc())
        .all()
    )
    return {
        "ok": True,
        "user_id": user_id,
        "roles": [_serialize_role(db, row) for row in rows],
    }


# ---------- Endpoint: current user permissions ----------


@router.get("/me/permissions")
def me_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == current_user.id)
        .order_by(Role.position.desc(), Role.name.asc())
        .all()
    )
    return {
        "is_admin": bool(getattr(current_user, "is_admin", False)),
        "roles": [
            {
                "id": r.id,
                "name": r.name,
                "color": r.color or "",
                "position": int(r.position or 0),
            }
            for r in rows
        ],
        "permissions": user_permissions(db, current_user),
    }
