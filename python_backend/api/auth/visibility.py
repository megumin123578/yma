from typing import Set
from sqlalchemy.orm import Session

from python_backend.api.auth.models import UserHiddenChannel


def get_hidden_account_tags(db: Session, user_id: int) -> Set[str]:
    rows = (
        db.query(UserHiddenChannel.account_tag)
        .filter(UserHiddenChannel.user_id == user_id)
        .all()
    )
    return {r[0] for r in rows}
