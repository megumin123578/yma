# routes/content.py
import os
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from datetime import date
from sqlalchemy import text
from python_backend.db import engine
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user_optional
from python_backend.api.auth.database import get_db
from python_backend.api.auth.visibility import get_allowed_account_tags, get_hidden_account_tags
from python_backend.module_trafficsource import sanitize_filename  # dùng lại hàm này

router = APIRouter(prefix="/api/content", tags=["content"])

CREDENTIALS_DIR = "./python_backend/credentials"


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
        v.impressions AS impressions,
        v.ctr AS ctr
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
        v.duration
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
