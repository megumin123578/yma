from fastapi import APIRouter, Depends
from datetime import datetime, timedelta
from python_backend.module_trafficsource import create_token_from_credentials
from python_backend.module_geography import (
    fetch_geography,
    load_geography_from_postgres,
    save_geography_to_postgres,
)

import os
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user_optional
from python_backend.api.auth.database import get_db
from python_backend.api.auth.visibility import get_allowed_account_tags, get_hidden_account_tags
from python_backend.api.auth.models import UserCredential
from python_backend.module_trafficsource import sanitize_filename

router = APIRouter(prefix="/api/geography")

TOKEN_DIR = "./python_backend/token"


def load_all_credentials(db: Session):
    creds = {}
    labels = {}
    rows = (
        db.query(UserCredential)
        .filter(UserCredential.token_name.isnot(None))
        .all()
    )
    for row in rows:
        token_name = row.token_name
        if not token_name:
            continue
        token_path = os.path.join(TOKEN_DIR, token_name)
        if not os.path.exists(token_path):
            continue
        account_tag = row.account_tag or ""
        if not account_tag:
            continue
        creds[account_tag] = token_path
        labels[account_tag] = row.selected_channel_title or account_tag
    return creds, labels


def _label_channels(db: Session, channels: list) -> list:
    if not channels:
        return []
    rows = (
        db.query(UserCredential.account_tag, UserCredential.selected_channel_title)
        .filter(UserCredential.account_tag.in_(channels))
        .all()
    )
    label_map = {
        sanitize_filename(row.account_tag): (row.selected_channel_title or row.account_tag)
        for row in rows
        if row.account_tag
    }
    return [{"value": tag, "label": label_map.get(tag, tag)} for tag in channels]


def get_range_dates(range_key: str):
    today = datetime.today().date()

    if range_key == "7d":   return today - timedelta(days=6), today
    if range_key == "28d":  return today - timedelta(days=27), today
    if range_key == "90d":  return today - timedelta(days=89), today
    if range_key == "365d": return today - timedelta(days=364), today
    if range_key == "lifetime":
        return datetime(2005, 2, 14).date(), today

    if range_key.isdigit():
        year = int(range_key)
        return datetime(year, 1, 1).date(), datetime(year, 12, 31).date()

    return None


@router.get("/")
def api_geography(
    range: str = None,
    month: str = None,
    start: str = None,
    end: str = None,
    channel: str = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    CHANNEL_CREDENTIALS, CHANNEL_LABELS = load_all_credentials(db)
    allowed = get_allowed_account_tags(db, current_user)
    if allowed is not None:
        CHANNEL_CREDENTIALS = {
            k: v for k, v in CHANNEL_CREDENTIALS.items() if sanitize_filename(k) in allowed
        }
        CHANNEL_LABELS = {k: v for k, v in CHANNEL_LABELS.items() if k in CHANNEL_CREDENTIALS}
    if current_user:
        hidden = get_hidden_account_tags(db, current_user.id)
        hidden_all = hidden | {sanitize_filename(t) for t in hidden}
        CHANNEL_CREDENTIALS = {
            k: v for k, v in CHANNEL_CREDENTIALS.items() if k not in hidden_all
        }
        CHANNEL_LABELS = {k: v for k, v in CHANNEL_LABELS.items() if k in CHANNEL_CREDENTIALS}

    # Nếu channel = None → không chọn gì → trả về availableChannels
    if not channel:
        available = list(CHANNEL_CREDENTIALS.keys())
        return {
            "start": None,
            "end": None,
            "channel": None,
            "rows": [],
            "availableChannels": [
                {"value": tag, "label": CHANNEL_LABELS.get(tag, tag)} for tag in available
            ],
        }

    if channel not in CHANNEL_CREDENTIALS:
        available = list(CHANNEL_CREDENTIALS.keys())
        return {
            "start": None,
            "end": None,
            "channel": channel,
            "rows": [],
            "availableChannels": [
                {"value": tag, "label": CHANNEL_LABELS.get(tag, tag)} for tag in available
            ],
        }

    cred_file = CHANNEL_CREDENTIALS[channel]

    try:
        creds = create_token_from_credentials(cred_file)
    except Exception as e:
        return {
            "start": None,
            "end": None,
            "channel": channel,
            "rows": [],
            "error": "invalid_credentials",
            "availableChannels": [
                {"value": tag, "label": CHANNEL_LABELS.get(tag, tag)}
                for tag in list(CHANNEL_CREDENTIALS.keys())
            ],
        }

    # ========= date range logic =========
    if range:
        s, e = get_range_dates(range)
    elif month:
        y, m = map(int, month.split("-"))
        s = datetime(y, m, 1).date()
        if m == 12:
            e = datetime(y, 12, 31).date()
        else:
            e = (datetime(y, m + 1, 1) - timedelta(days=1)).date()
    else:
        s = datetime.strptime(start, "%Y-%m-%d").date()
        e = datetime.strptime(end, "%Y-%m-%d").date()
    try:
        rows = load_geography_from_postgres(channel, s.isoformat(), e.isoformat())
    except Exception as e:
        print(f"[WARN] Geography DB load failed: {e}")
        rows = []
    if not rows:
        # ========= Fetch data from YouTube =========
        try:
            rows = fetch_geography(creds, s.isoformat(), e.isoformat())
        except Exception:
            # Channel hop le nhung khong co data xac minh
            rows = []
        try:
            save_geography_to_postgres(rows, channel, s.isoformat(), e.isoformat())
        except Exception as e:
            print(f"[WARN] Geography DB save failed: {e}")

    return {
        "start": s.isoformat(),
        "end": e.isoformat(),
        "channel": channel,
        "rows": rows,
        "availableChannels": list(CHANNEL_CREDENTIALS.keys()),
    }
