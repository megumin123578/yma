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


def _load_credential_path(account_tag: str):
    if not account_tag:
        return None
    token_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "token"))
    direct = os.path.join(token_dir, f"{account_tag}.pickle")
    if os.path.exists(direct):
        return direct
    safe = sanitize_filename(account_tag)
    if safe != account_tag:
        safe_path = os.path.join(token_dir, f"{safe}.pickle")
        if os.path.exists(safe_path):
            return safe_path
    return None


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
    filtered = []
    for acct in accounts:
        if isinstance(acct, dict):
            value = acct.get("value") or acct.get("label") or ""
            if value in hidden_all:
                continue
            filtered.append(acct)
        else:
            if acct not in hidden_all:
                filtered.append(acct)
    return filtered


@router.get("/channels")
def list_channels(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
    range: str = Query("lifetime"),
    startDate: date = Query(None),
    endDate: date = Query(None),
    include_hidden: bool = Query(False),
):
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        return {"items": []}
    allowed = get_allowed_account_tags(db, current_user)
    hidden = get_hidden_account_tags(db, current_user.id) if current_user else set()
    start_date, end_date = (startDate, endDate)
    if start_date is None and end_date is None:
        start_date, end_date = _range_to_dates(range)
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        _ensure_revenue_table(conn)
        rows = conn.execute(
            text(
                """
                SELECT
                    account_tag,
                    COALESCE(SUM(estimated_revenue), 0) AS estimated_revenue
                FROM revenue_daily
                WHERE (:start_date IS NULL OR day >= :start_date)
                  AND (:end_date IS NULL OR day <= :end_date)
                GROUP BY account_tag
                ORDER BY account_tag
                """
            ),
            {"start_date": start_date, "end_date": end_date},
        ).fetchall()
    items = [
        {
            "value": r[0],
            "label": r[0],
            "estimated_revenue": float(r[1] or 0),
        }
        for r in rows
    ]
    if allowed is not None:
        items = [item for item in items if item["value"] in allowed]
    if not include_hidden:
        items = _filter_hidden(items, hidden)
    items = [item for item in items if _load_credential_path(item["value"])]
    label_map = {}
    if items:
        creds = (
            db.query(UserCredential.account_tag, UserCredential.selected_channel_title)
            .filter(UserCredential.account_tag.in_([item["value"] for item in items]))
            .all()
        )
        label_map = {
            sanitize_filename(row.account_tag): (row.selected_channel_title or row.account_tag)
            for row in creds
            if row.account_tag
        }
    labeled = [
        {
            "value": item["value"],
            "label": label_map.get(item["value"], item["label"]),
            "estimated_revenue": item["estimated_revenue"],
        }
        for item in items
    ]
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
                    estimated_red_partner_revenue,
                    cpm,
                    playback_cpm,
                    rpm,
                    monetized_playbacks,
                    ad_impressions,
                    views
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
