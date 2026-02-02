import os
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user_optional
from python_backend.api.auth.database import get_db
from python_backend.api.auth.visibility import get_allowed_account_tags, get_hidden_account_tags
from python_backend.api.auth.models import UserCredential
from python_backend.module_trafficsource import sanitize_filename
from python_backend.module_revenue import _ensure_revenue_table


router = APIRouter(prefix="/api/revenue", tags=["revenue"])


def _range_to_dates(range_key: str):
    today = date.today()
    if range_key == "7d":
        return today - timedelta(days=6), today
    if range_key == "28d":
        return today - timedelta(days=27), today
    if range_key == "90d":
        return today - timedelta(days=89), today
    if range_key == "365d":
        return today - timedelta(days=364), today
    if range_key == "lifetime":
        return None, None
    return today - timedelta(days=27), today


def _filter_hidden(accounts, hidden):
    hidden_all = set(hidden) | {sanitize_filename(tag) for tag in hidden}
    return [acct for acct in accounts if acct not in hidden_all]


@router.get("/channels")
def list_channels(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        return {"items": []}
    allowed = get_allowed_account_tags(db, current_user)
    hidden = get_hidden_account_tags(db, current_user.id) if current_user else set()
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        _ensure_revenue_table(conn)
        rows = conn.execute(
            text(
                """
                SELECT DISTINCT account_tag
                FROM revenue_daily
                ORDER BY account_tag
                """
            )
        ).fetchall()
    items = [r[0] for r in rows]
    if allowed is not None:
        items = [acct for acct in items if acct in allowed]
    items = _filter_hidden(items, hidden)
    label_map = {}
    if items:
        creds = (
            db.query(UserCredential.account_tag, UserCredential.selected_channel_title)
            .filter(UserCredential.account_tag.in_(items))
            .all()
        )
        label_map = {
            sanitize_filename(row.account_tag): (row.selected_channel_title or row.account_tag)
            for row in creds
            if row.account_tag
        }
    labeled = [{"value": tag, "label": label_map.get(tag, tag)} for tag in items]
    return {"items": labeled}


@router.get("/")
def get_revenue(
    accountTag: str = Query(None),
    range: str = Query("28d"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        return {"rows": [], "start_date": None, "end_date": None}
    if not accountTag:
        return {"rows": [], "start_date": None, "end_date": None}
    allowed = get_allowed_account_tags(db, current_user)
    safe_tag = sanitize_filename(accountTag)
    if allowed is not None and safe_tag not in allowed:
        return {"rows": [], "start_date": None, "end_date": None}
    if current_user:
        hidden = get_hidden_account_tags(db, current_user.id)
        hidden_all = hidden | {sanitize_filename(t) for t in hidden}
        if safe_tag in hidden_all:
            return {"rows": [], "start_date": None, "end_date": None}

    start_date, end_date = _range_to_dates(range)
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        _ensure_revenue_table(conn)
        rows = conn.execute(
            text(
                """
                SELECT
                    day,
                    estimated_revenue,
                    ad_revenue,
                    gross_revenue,
                    cpm,
                    playback_cpm,
                    rpm,
                    monetized_playbacks
                FROM revenue_daily
                WHERE account_tag = :acct
                  AND (:start_date IS NULL OR day >= :start_date)
                  AND (:end_date IS NULL OR day <= :end_date)
                ORDER BY day ASC
                """
            ),
            {"acct": safe_tag, "start_date": start_date, "end_date": end_date},
        ).mappings().all()
    return {
        "rows": rows,
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
    }
