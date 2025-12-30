# routes/content.py
import os
import pickle
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from datetime import date
from typing import Optional
from sqlalchemy import text
from python_backend.db import engine
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user_optional
from python_backend.api.auth.database import get_db
from python_backend.api.auth.visibility import get_allowed_account_tags, get_hidden_account_tags
from python_backend.api.auth.models import UserCredential
from python_backend.module_trafficsource import sanitize_filename  # dùng lại hàm này
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request

router = APIRouter(prefix="/api/content", tags=["content"])

CREDENTIALS_DIR = "./python_backend/credentials"
TOKEN_DIR = "./python_backend/token"


# ==============================
# Helper query
# ==============================
def query_all_safe(sql: str, params=None):
    try:
        with engine.begin() as conn:
            rs = conn.execute(text(sql), params or {})
            return rs.mappings().all()
    except Exception as e:
        print("[content.query_all_safe] failed:", e)
        return []


@router.get("/channels")
def list_channels(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    items = []
    try:
        hidden_all = set()
        allowed = get_allowed_account_tags(db, current_user)
        if current_user:
            hidden = get_hidden_account_tags(db, current_user.id)
            hidden_all = hidden | {sanitize_filename(t) for t in hidden}
        for fname in os.listdir(CREDENTIALS_DIR):
            if not fname.endswith(".json"):
                continue

            raw = fname[:-5]               # bỏ .json
            value = sanitize_filename(raw) 
            if allowed is not None and value not in allowed:
                continue
            if hidden_all and (value in hidden_all or raw in hidden_all):
                continue
            items.append({
                "value": value,  
                "label": raw,   
            })
    except Exception as e:
        print("[content.channels] ERROR:", e)

    return {"items": items}


class ContentListRequest(BaseModel):
    start: date
    end: date
    channelId: str


@router.post("/list")
def content_list(
    req: ContentListRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    allowed = get_allowed_account_tags(db, current_user)
    if allowed is not None and req.channelId not in allowed:
        return {"items": []}
    if current_user:
        hidden = get_hidden_account_tags(db, current_user.id)
        hidden_all = hidden | {sanitize_filename(t) for t in hidden}
        if req.channelId in hidden_all:
            return {"items": []}
    sql = """
    SELECT
        v.video_id      AS "videoId",
        v.title,
        v.thumbnail,
        v.published_at  AS "publishedAt",
        v.duration,

        COALESCE(SUM(s.views), 0) AS views,
        COALESCE(SUM(s.estimated_minutes) / 60.0, 0) AS "watchTimeHours",

        COALESCE(SUM(s.likes), 0) AS likes,
        0::numeric AS "estimatedRevenue",
        COALESCE(v.card_impressions, 0) AS "cardImpressions",
        COALESCE(v.ad_impressions, 0) AS "adImpressions",
        COALESCE(v.annotation_impressions, 0) AS "annotationImpressions"
    FROM videos v
    JOIN video_daily_stats s
      ON s.video_id = v.video_id
     AND s.day BETWEEN :start AND :end
    WHERE v.account_tag = :account_tag
    GROUP BY
        v.video_id,
        v.title,
        v.thumbnail,
        v.published_at,
        v.duration,
        v.card_impressions,
        v.ad_impressions,
        v.annotation_impressions
    HAVING SUM(s.views) > 0 
    ORDER BY v.published_at DESC;
"""


    params = {
        "start": req.start,
        "end": req.end,
        "account_tag": req.channelId,
    }

    rows = query_all_safe(sql, params)
    # print("[content.list] rows =", rows[:3])  # debug 
    return {"items": rows}


class TimeSeriesRequest(BaseModel):
    start: date
    end: date
    channelId: str  # = account_tag


class ChannelMetricsRequest(BaseModel):
    start: date
    end: date
    channelId: str


@router.post("/timeseries")
def content_timeseries(
    req: TimeSeriesRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    allowed = get_allowed_account_tags(db, current_user)
    if allowed is not None and req.channelId not in allowed:
        return {"items": []}
    if current_user:
        hidden = get_hidden_account_tags(db, current_user.id)
        hidden_all = hidden | {sanitize_filename(t) for t in hidden}
        if req.channelId in hidden_all:
            return {"items": []}

    sql = """
        SELECT
            s.day                  AS bucket,
            v.video_id             AS "videoId",
            v.title                AS title,

            s.views                AS views,
            (s.estimated_minutes / 60.0) AS watch_hours,

            s.likes                AS likes,
            0::numeric             AS revenue,
            0::bigint              AS impressions
        FROM video_daily_stats s
        JOIN videos v
          ON v.video_id = s.video_id
        WHERE v.account_tag = :account_tag
          AND s.day BETWEEN :start AND :end
        ORDER BY
            bucket ASC,
            "videoId" ASC;
    """

    params = {
        "account_tag": req.channelId,
        "start": req.start,
        "end": req.end,
    }

    rows = query_all_safe(sql, params)
    # print("[content.timeseries] rows (sample) =", rows[:5])  # debug
    return {"items": rows}


def _load_token_credentials(token_name: str):
    token_path = os.path.join(TOKEN_DIR, token_name)
    if not os.path.exists(token_path):
        return None
    try:
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
    except Exception:
        return None
    if not creds:
        return None
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, "wb") as f:
                    pickle.dump(creds, f)
            except Exception:
                return None
        else:
            return None
    return creds


def _find_credential_row(db: Session, account_tag: str) -> Optional[UserCredential]:
    row = (
        db.query(UserCredential)
        .filter(UserCredential.account_tag == account_tag)
        .order_by(UserCredential.updated_at.desc())
        .first()
    )
    if row:
        return row
    rows = (
        db.query(UserCredential)
        .filter(UserCredential.token_name.isnot(None))
        .all()
    )
    for r in rows:
        if sanitize_filename(r.account_tag) == account_tag:
            return r
    return None


@router.post("/channel-metrics")
def channel_metrics(
    req: ChannelMetricsRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    allowed = get_allowed_account_tags(db, current_user)
    if allowed is not None and req.channelId not in allowed:
        return {"impressions": 0, "ctr": None, "supported": False}
    if current_user:
        hidden = get_hidden_account_tags(db, current_user.id)
        hidden_all = hidden | {sanitize_filename(t) for t in hidden}
        if req.channelId in hidden_all:
            return {"impressions": 0, "ctr": None, "supported": False}
    cred_row = _find_credential_row(db, req.channelId)
    if not cred_row or not cred_row.token_name:
        return {"impressions": 0, "ctr": None, "supported": False}
    creds = _load_token_credentials(cred_row.token_name)
    if not creds:
        return {"impressions": 0, "ctr": None, "supported": False}

    yta = build("youtubeAnalytics", "v2", credentials=creds)
    ids = (
        f"channel=={cred_row.selected_channel_id}"
        if cred_row.selected_channel_id
        else "channel==MINE"
    )
    query = {
        "ids": ids,
        "startDate": req.start.isoformat(),
        "endDate": req.end.isoformat(),
        "metrics": "impressions,impressionsClickThroughRate",
    }
    try:
        resp = yta.reports().query(**query).execute() or {}
    except HttpError as e:
        print(f"[content.channel-metrics] WARN: {e}")
        return {"impressions": 0, "ctr": None, "supported": False}

    rows = resp.get("rows") or []
    if not rows:
        return {"impressions": 0, "ctr": None, "supported": True}
    try:
        impressions = int(rows[0][0] or 0)
    except Exception:
        impressions = 0
    try:
        ctr = float(rows[0][1] or 0.0) * 100.0
    except Exception:
        ctr = None
    return {"impressions": impressions, "ctr": ctr, "supported": True}
