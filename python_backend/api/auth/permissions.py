"""Permission system: roles, actions, scopes.

Action vocabulary:
- page.*       — sidebar/page visibility
- read/write/run/delete — data ops (require scope)
- manage_*     — admin-only feature management

Scope:
- scope_type='*', scope_value=NULL  → global
- scope_type='project', scope_value=<project_name>
- scope_type='channel', scope_value=<account_tag>

Admin fast-path: user.is_admin=True bypasses every check.
"""
from __future__ import annotations

from typing import Iterable, Optional, Set, Tuple

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user
from python_backend.api.auth.database import get_db
from python_backend.api.auth.models import Role, RolePermission, User, UserRole


PAGE_ACTIONS: Set[str] = {
    "page.dashboard",
    "page.content",
    "page.all_channels",
    "page.channel_compare",
    "page.audience",
    "page.revenue",
    "page.reach",
    "page.traffic",
    "page.geography",
    "page.smmstore",
    "page.mail",
    "page.rivals",
    "page.config",
}

DATA_ACTIONS: Set[str] = {
    "view",
    "view_revenue",
}

ADMIN_ACTIONS: Set[str] = {
    "manage_users",
    "manage_roles",
    "manage_mail",
    "manage_structure",
    "view_all_channels",
}

ALL_ACTIONS: Set[str] = PAGE_ACTIONS | DATA_ACTIONS | ADMIN_ACTIONS

SCOPE_TYPES: Set[str] = {"*", "project", "channel"}


# ---------- Internal: collect raw permission rows for a user ----------


def _collect_user_permission_rows(
    db: Session, user: User
) -> list[Tuple[str, str, Optional[str]]]:
    rows = (
        db.query(RolePermission.action, RolePermission.scope_type, RolePermission.scope_value)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .filter(UserRole.user_id == user.id)
        .all()
    )
    return [(r.action, r.scope_type, r.scope_value) for r in rows]


# ---------- Public helpers ----------


def user_has_permission(
    db: Session,
    user: Optional[User],
    action: str,
    scope: Optional[Tuple[str, Optional[str]]] = None,
) -> bool:
    """Check if user has `action` on the given scope.

    scope = None  → check global (`*`) only.
    scope = ("project", "fmc")  → check project-specific OR `*` OR matching wider scope.

    Admin (`user.is_admin=True`) always returns True.
    """
    if not user:
        return False
    if bool(getattr(user, "is_admin", False)):
        return True

    rows = _collect_user_permission_rows(db, user)
    for r_action, r_scope_type, r_scope_value in rows:
        if r_action != action:
            continue
        if r_scope_type == "*":
            return True
        if scope is None:
            # caller asked global, role has scoped → not enough
            continue
        s_type, s_value = scope
        if r_scope_type == s_type and r_scope_value == s_value:
            return True
    return False


def can_view_revenue(db: Session, user: Optional[User]) -> bool:
    """True if user may see revenue values (admin or granted `view_revenue`)."""
    return user_has_permission(db, user, "view_revenue")


def user_permissions(db: Session, user: Optional[User]) -> list[dict]:
    """Return flat permission list for frontend self endpoint."""
    if not user:
        return []
    if bool(getattr(user, "is_admin", False)):
        # admin sees everything — synthesize a wildcard list for client UX
        return [
            {"action": action, "scope_type": "*", "scope_value": None}
            for action in sorted(ALL_ACTIONS)
        ]
    rows = _collect_user_permission_rows(db, user)
    return [
        {"action": a, "scope_type": s_type, "scope_value": s_value}
        for (a, s_type, s_value) in rows
    ]


def get_allowed_scopes(
    db: Session,
    user: Optional[User],
    action: str,
    scope_type: str = "project",
) -> Optional[Set[str]]:
    """Return set of scope_values user has `action` on, of the given scope_type.

    None = unlimited (global `*` grant or admin).
    Empty set = no access.
    """
    if not user:
        return set()
    if bool(getattr(user, "is_admin", False)):
        return None
    rows = _collect_user_permission_rows(db, user)
    allowed: Set[str] = set()
    for r_action, r_scope_type, r_scope_value in rows:
        if r_action != action:
            continue
        if r_scope_type == "*":
            return None
        if r_scope_type == scope_type and r_scope_value:
            allowed.add(r_scope_value)
    return allowed


def user_role_ids(db: Session, user: User) -> Set[int]:
    rows = db.query(UserRole.role_id).filter(UserRole.user_id == user.id).all()
    return {r.role_id for r in rows}


# ---------- FastAPI dependency factory ----------


def require_permission(action: str, scope_type: str = "*", scope_value: str = ""):
    """Build a Depends factory for an action (optionally scoped).

    Admin users always pass (fast-path). For scoped actions, caller usually
    passes scope=None here and enforces scope inside the route body where
    the path param is known.
    """
    scope_tuple: Optional[Tuple[str, Optional[str]]] = None
    if scope_type != "*":
        scope_tuple = (scope_type, scope_value)

    def _dep(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if not user_has_permission(db, current_user, action, scope_tuple):
            raise HTTPException(
                status_code=403,
                detail=f"Missing permission: {action}",
            )
        return current_user

    return _dep
