import os
from typing import Optional, Set
from sqlalchemy.orm import Session

from python_backend.api.auth.models import User, UserHiddenChannel, UserCredential
from python_backend.module_trafficsource import sanitize_filename


def get_hidden_account_tags(db: Session, user_id: int) -> Set[str]:
    rows = (
        db.query(UserHiddenChannel.account_tag)
        .filter(UserHiddenChannel.user_id == user_id)
        .all()
    )
    return {r[0] for r in rows}


def get_admin_usernames() -> Set[str]:
    raw = os.getenv("ADMIN_USERNAME", "admin")
    return {u.strip().lower() for u in raw.split(",") if u.strip()}


def is_admin_user(user: Optional[User]) -> bool:
    if not user:
        return False
    return (user.username or "").lower() in get_admin_usernames()


def get_allowed_account_tags(db: Session, user: Optional[User]) -> Optional[Set[str]]:
    if is_admin_user(user):
        return None
    if not user:
        return set()
    rows = (
        db.query(UserCredential.account_tag)
        .filter(
            UserCredential.user_id == user.id,
            UserCredential.token_name.isnot(None),
        )
        .all()
    )
    tags = {r[0] for r in rows}
    tags |= {sanitize_filename(t) for t in tags}
    return tags
