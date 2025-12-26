import os
from fastapi import APIRouter, Depends, Query
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user_optional
from python_backend.api.auth.database import get_db
from python_backend.api.auth.visibility import get_allowed_account_tags, get_hidden_account_tags
from python_backend.module_trafficsource import sanitize_filename
from python_backend.module_reach import _ensure_reach_table


router = APIRouter(prefix="/api/reach", tags=["reach"])


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
        _ensure_reach_table(conn)
        rows = conn.execute(
            text(
                """
                SELECT DISTINCT account_tag
                FROM reach_video_metrics
                ORDER BY account_tag
                """
            )
        ).fetchall()
    items = [r[0] for r in rows]
    if allowed is not None:
        items = [acct for acct in items if acct in allowed]
    items = _filter_hidden(items, hidden)
    return {"items": items}


@router.get("/")
def get_reach(
    accountTag: str = Query(None),
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

    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        _ensure_reach_table(conn)
        latest = conn.execute(
            text(
                """
                SELECT start_date, end_date
                FROM reach_video_metrics
                WHERE account_tag = :acct
                ORDER BY end_date DESC, start_date DESC
                LIMIT 1
                """
            ),
            {"acct": safe_tag},
        ).fetchone()
        if not latest:
            return {"rows": [], "start_date": None, "end_date": None}
        start_date, end_date = latest
        rows = conn.execute(
            text(
                """
                SELECT
                    video_id,
                    title,
                    thumbnail,
                    views,
                    estimated_minutes_watched,
                    annotation_impressions,
                    card_impressions,
                    teaser_impressions,
                    total_impressions,
                    annotation_clicks,
                    card_clicks,
                    teaser_clicks,
                    total_clicks,
                    annotation_ctr,
                    card_ctr,
                    teaser_ctr,
                    total_ctr
                FROM reach_video_metrics
                WHERE account_tag = :acct
                  AND start_date = :start
                  AND end_date = :end
                ORDER BY views DESC
                """
            ),
            {"acct": safe_tag, "start": start_date, "end": end_date},
        ).mappings().all()
    return {
        "rows": rows,
        "start_date": str(start_date),
        "end_date": str(end_date),
    }
