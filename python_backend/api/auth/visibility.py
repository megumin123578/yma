from typing import Optional, Set
from sqlalchemy.orm import Session

from python_backend.api.auth.models import User, UserHiddenChannel


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
    return None
