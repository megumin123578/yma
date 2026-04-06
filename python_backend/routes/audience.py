from fastapi import APIRouter, Depends, Query
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user_optional
from python_backend.api.auth.database import get_db
from python_backend.api.auth.visibility import get_allowed_account_tags, get_hidden_account_tags
from python_backend.api.auth.models import UserCredential
from python_backend.module_trafficsource import sanitize_filename
from python_backend.token_store import token_exists


router = APIRouter(prefix="/api/audience", tags=["audience"])


def _filter_hidden(accounts, hidden):
    hidden_all = set(hidden) | {sanitize_filename(tag) for tag in hidden}
    return [acct for acct in accounts if acct not in hidden_all]


def _label_accounts(db: Session, accounts: list) -> list:
    if not accounts:
        return []
    rows = (
        db.query(UserCredential.account_tag, UserCredential.selected_channel_title)
        .filter(UserCredential.account_tag.in_(accounts))
        .all()
    )
    label_map = {
        sanitize_filename(row.account_tag): (row.selected_channel_title or row.account_tag)
        for row in rows
        if row.account_tag
    }
    return [{"value": tag, "label": label_map.get(tag, tag)} for tag in accounts]


def _available_accounts_from_credentials(db: Session, current_user) -> list:
    hidden = get_hidden_account_tags(db, current_user.id) if current_user else set()
    allowed = get_allowed_account_tags(db, current_user)
    rows = (
        db.query(UserCredential)
        .filter(UserCredential.token_name.isnot(None))
        .order_by(UserCredential.updated_at.desc())
        .all()
    )
    seen = set()
    accounts = []
    for row in rows:
        value = sanitize_filename(row.account_tag or "")
        if not value or value in seen:
            continue
        if allowed is not None and value not in allowed:
            continue
        token_name = (row.token_name or "").strip()
        if not token_name:
            continue
        if not token_exists(token_name):
            continue
        seen.add(value)
        accounts.append(value)
    return _filter_hidden(accounts, hidden)


@router.get("/demographics")
def get_demographics(
    accountTag: str = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    allowed = get_allowed_account_tags(db, current_user)
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        return {"availableAccounts": [], "rows": []}
    try:
        pg_engine = create_engine(pg_url, future=True)
        with pg_engine.connect() as conn:
            if not accountTag:
                accounts = _available_accounts_from_credentials(db, current_user)
                return {"availableAccounts": _label_accounts(db, accounts), "rows": []}

            safe_tag = sanitize_filename(accountTag)
            if allowed is not None and safe_tag not in allowed:
                return {"availableAccounts": [], "rows": []}
            latest = conn.execute(
                text(
                    """
                    SELECT start_date, end_date
                    FROM audience_demographics
                    WHERE account_tag = :acct
                    ORDER BY end_date DESC, start_date DESC
                    LIMIT 1
                    """
                ),
                {"acct": safe_tag},
            ).fetchone()
            if not latest:
                return {"availableAccounts": [], "rows": []}
            start_date, end_date = latest
            rows = conn.execute(
                text(
                    """
                    SELECT gender, age_group, viewer_percentage
                    FROM audience_demographics
                    WHERE account_tag = :acct AND start_date = :start AND end_date = :end
                    ORDER BY gender, age_group
                    """
                ),
                {"acct": safe_tag, "start": start_date, "end": end_date},
            ).fetchall()
            payload = [
                {
                    "gender": r[0],
                    "age_group": r[1],
                    "viewer_percentage": float(r[2] or 0),
                }
                for r in rows
            ]
            return {
                "accountTag": safe_tag,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "rows": payload,
            }
    except Exception:
        return {"availableAccounts": [], "rows": []}


@router.get("/retention")
def get_retention(
    accountTag: str = Query(None),
    videoId: str = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    allowed = get_allowed_account_tags(db, current_user)
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        return {"availableAccounts": [], "videos": [], "rows": []}
    try:
        pg_engine = create_engine(pg_url, future=True)
        with pg_engine.connect() as conn:
            if not accountTag:
                accounts = _available_accounts_from_credentials(db, current_user)
                return {"availableAccounts": _label_accounts(db, accounts), "videos": [], "rows": []}

            safe_tag = sanitize_filename(accountTag)
            if allowed is not None and safe_tag not in allowed:
                return {"accountTag": safe_tag, "videos": [], "rows": []}
            if not videoId:
                rows = conn.execute(
                    text(
                        """
                        SELECT DISTINCT r.video_id, v.title, v.thumbnail
                        FROM audience_retention r
                        LEFT JOIN videos v
                          ON v.video_id = r.video_id AND v.account_tag = r.account_tag
                        WHERE r.account_tag = :acct
                        ORDER BY v.title NULLS LAST, r.video_id
                        """
                    ),
                    {"acct": safe_tag},
                ).fetchall()
                videos = [
                    {"video_id": r[0], "title": r[1], "thumbnail": r[2]}
                    for r in rows
                ]
                return {"accountTag": safe_tag, "videos": videos, "rows": []}

            latest = conn.execute(
                text(
                    """
                    SELECT start_date, end_date
                    FROM audience_retention
                    WHERE account_tag = :acct AND video_id = :vid
                    ORDER BY end_date DESC, start_date DESC
                    LIMIT 1
                    """
                ),
                {"acct": safe_tag, "vid": videoId},
            ).fetchone()
            if not latest:
                return {"accountTag": safe_tag, "videos": [], "rows": []}
            start_date, end_date = latest
            rows = conn.execute(
                text(
                    """
                    SELECT elapsed_video_time_ratio, audience_watch_ratio, relative_retention_performance
                    FROM audience_retention
                    WHERE account_tag = :acct AND video_id = :vid
                      AND start_date = :start AND end_date = :end
                    ORDER BY elapsed_video_time_ratio
                    """
                ),
                {"acct": safe_tag, "vid": videoId, "start": start_date, "end": end_date},
            ).fetchall()
            payload = [
                {
                    "elapsed_video_time_ratio": float(r[0] or 0),
                    "audience_watch_ratio": float(r[1] or 0),
                    "relative_retention_performance": float(r[2] or 0)
                    if r[2] is not None
                    else None,
                }
                for r in rows
            ]
            return {
                "accountTag": safe_tag,
                "videoId": videoId,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "rows": payload,
            }
    except Exception:
        return {"availableAccounts": [], "videos": [], "rows": []}


@router.get("/devices")
def get_devices(
    accountTag: str = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    allowed = get_allowed_account_tags(db, current_user)
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        return {"availableAccounts": [], "rows": []}
    try:
        pg_engine = create_engine(pg_url, future=True)
        with pg_engine.connect() as conn:
            if not accountTag:
                accounts = _available_accounts_from_credentials(db, current_user)
                return {"availableAccounts": _label_accounts(db, accounts), "rows": []}

            safe_tag = sanitize_filename(accountTag)
            if allowed is not None and safe_tag not in allowed:
                return {"availableAccounts": [], "rows": []}
            latest = conn.execute(
                text(
                    """
                    SELECT start_date, end_date
                    FROM audience_devices
                    WHERE account_tag = :acct
                    ORDER BY end_date DESC, start_date DESC
                    LIMIT 1
                    """
                ),
                {"acct": safe_tag},
            ).fetchone()
            if not latest:
                return {"availableAccounts": [], "rows": []}
            start_date, end_date = latest
            rows = conn.execute(
                text(
                    """
                    SELECT device_type, viewer_percentage
                    FROM audience_devices
                    WHERE account_tag = :acct AND start_date = :start AND end_date = :end
                    ORDER BY viewer_percentage DESC
                    """
                ),
                {"acct": safe_tag, "start": start_date, "end": end_date},
            ).fetchall()
            payload = [
                {"device_type": r[0], "viewer_percentage": float(r[1] or 0)}
                for r in rows
            ]
            return {
                "accountTag": safe_tag,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "rows": payload,
            }
    except Exception:
        return {"availableAccounts": [], "rows": []}


@router.get("/viewer_types")
def get_viewer_types(
    accountTag: str = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    allowed = get_allowed_account_tags(db, current_user)
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        return {"availableAccounts": [], "rows": []}
    try:
        pg_engine = create_engine(pg_url, future=True)
        with pg_engine.connect() as conn:
            if not accountTag:
                accounts = _available_accounts_from_credentials(db, current_user)
                return {"availableAccounts": _label_accounts(db, accounts), "rows": []}

            safe_tag = sanitize_filename(accountTag)
            if allowed is not None and safe_tag not in allowed:
                return {"availableAccounts": [], "rows": []}
            latest = conn.execute(
                text(
                    """
                    SELECT start_date, end_date
                    FROM audience_viewer_types
                    WHERE account_tag = :acct
                    ORDER BY end_date DESC, start_date DESC
                    LIMIT 1
                    """
                ),
                {"acct": safe_tag},
            ).fetchone()
            if not latest:
                return {"availableAccounts": [], "rows": []}
            start_date, end_date = latest
            rows = conn.execute(
                text(
                    """
                    SELECT viewer_type, viewer_percentage
                    FROM audience_viewer_types
                    WHERE account_tag = :acct AND start_date = :start AND end_date = :end
                    ORDER BY viewer_percentage DESC
                    """
                ),
                {"acct": safe_tag, "start": start_date, "end": end_date},
            ).fetchall()
            payload = [
                {"viewer_type": r[0], "viewer_percentage": float(r[1] or 0)}
                for r in rows
            ]
            return {
                "accountTag": safe_tag,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "rows": payload,
            }
    except Exception:
        return {"availableAccounts": [], "rows": []}
