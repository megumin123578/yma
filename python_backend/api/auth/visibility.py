from typing import Optional, Set

from sqlalchemy import or_
from sqlalchemy.orm import Session

from python_backend.api.auth.models import User, UserChannelAccess, UserCredential, UserHiddenChannel
from python_backend.module_trafficsource import sanitize_filename


def get_hidden_account_tags(db: Session, user_id: int) -> Set[str]:
    rows = (
        db.query(UserHiddenChannel.account_tag)
        .filter(UserHiddenChannel.user_id == user_id)
        .all()
    )
    return {r[0] for r in rows}


def get_allowed_account_tags(db: Session, user: Optional[User]) -> Optional[Set[str]]:
    if not user:
        return set()
    if bool(getattr(user, "is_admin", False)):
        return None

    def add_tag(out: Set[str], value: str) -> None:
        tag = (value or "").strip()
        if not tag:
            return
        out.add(tag)
        out.add(sanitize_filename(tag))

    allowed: Set[str] = set()
    own_rows = (
        db.query(UserCredential.account_tag)
        .filter(UserCredential.user_id == user.id)
        .all()
    )
    for row in own_rows:
        add_tag(allowed, row[0])

    grants = (
        db.query(UserChannelAccess.scope_type, UserChannelAccess.scope_value)
        .filter(UserChannelAccess.user_id == user.id)
        .all()
    )
    channel_values = [row.scope_value for row in grants if row.scope_type == "channel"]
    project_values = [row.scope_value for row in grants if row.scope_type == "project"]

    if channel_values:
        rows = (
            db.query(UserCredential.account_tag)
            .filter(
                or_(
                    UserCredential.account_tag.in_(channel_values),
                    UserCredential.token_name.in_(channel_values),
                    UserCredential.selected_channel_id.in_(channel_values),
                    UserCredential.selected_channel_title.in_(channel_values),
                )
            )
            .all()
        )
        for row in rows:
            add_tag(allowed, row[0])

    if project_values:
        rows = (
            db.query(UserCredential.account_tag)
            .filter(UserCredential.project_name.in_(project_values))
            .all()
        )
        for row in rows:
            add_tag(allowed, row[0])

    return allowed
