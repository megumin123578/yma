# routes/traffic_timeseries.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import date
from sqlalchemy import text
from python_backend.db import engine 
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user_optional
from python_backend.api.auth.database import get_db
from python_backend.api.auth.visibility import get_allowed_account_tags, get_hidden_account_tags
from python_backend.module_trafficsource import sanitize_filename


def query_all_safe(sql: str, params=None):
    try:
        with engine.begin() as conn:
            rs = conn.execute(text(sql), params or {})
            return rs.mappings().all()
    except Exception as e:
        print("[query_all_safe] failed:", e)
        return []

router = APIRouter(prefix="/api/traffic_source", tags=["traffic_source"])

def resolve_channel(channel_root: str):
    if "__" in channel_root:
        account_tag, channel_id = channel_root.split("__", 1)
        channel_id = channel_id.strip() or None
    else:
        account_tag, channel_id = channel_root.strip(), None
    return {"account_tag": account_tag, "channel_id": channel_id}

@router.get("/channels")
def list_channels(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    rows_acc = query_all_safe("""
        SELECT DISTINCT
            account_tag,
            account_tag AS label
        FROM traffic_source_daily
        WHERE account_tag IS NOT NULL AND account_tag <> ''
        ORDER BY 2;
    """)
    items = [{"value": r["account_tag"], "label": r["account_tag"]} for r in rows_acc]
    allowed = get_allowed_account_tags(db, current_user)
    if allowed is not None:
        items = [r for r in items if r["value"] in allowed]
    if current_user:
        hidden = get_hidden_account_tags(db, current_user.id)
        hidden_all = hidden | {sanitize_filename(t) for t in hidden}
        items = [r for r in items if r["value"] not in hidden_all]
    return {"items": items}



class TSRequest(BaseModel):
    start: date
    end: date
    channelRoot: str
    interval: str  # daily | weekly | monthly | yearly

@router.post("/timeseries")
def timeseries(
    req: TSRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    interval_map = {"daily": "day", "weekly": "week", "monthly": "month", "yearly": "year"}
    if req.interval not in interval_map:
        raise HTTPException(400, "interval phải là daily/weekly/monthly/yearly")

    ch = resolve_channel(req.channelRoot)
    allowed = get_allowed_account_tags(db, current_user)
    if allowed is not None and ch["account_tag"] not in allowed:
        return []
    if current_user:
        hidden = get_hidden_account_tags(db, current_user.id)
        hidden_all = hidden | {sanitize_filename(t) for t in hidden}
        if ch["account_tag"] in hidden_all:
            return []
    cond_channel = "AND channel_id = :channel_id" if ch["channel_id"] is not None else ""

    sql = text(f"""
        SELECT
          date_trunc(:bucket, day)::date AS bucket,
          source,
          SUM(views)::bigint AS "views",
          SUM(estimated_minutes_watched)::bigint AS "estimatedMinutesWatched",
          SUM(engaged_views)::bigint AS "engagedViews",
          CASE WHEN SUM(views) > 0
               THEN SUM(average_view_duration * views)::float / SUM(views)
               ELSE 0 END AS "averageViewDuration",
          CASE WHEN SUM(views) > 0
               THEN SUM(average_view_percentage * views)::float / SUM(views)
               ELSE 0 END AS "averageViewPercentage"
        FROM traffic_source_daily
        WHERE account_tag = :account_tag
          {cond_channel}
          AND day BETWEEN :start AND :end
        GROUP BY bucket, source
        ORDER BY bucket ASC, source ASC
    """)

    params = {
        "bucket": interval_map[req.interval],
        "account_tag": ch["account_tag"],
        "start": req.start,
        "end": req.end,
    }
    if ch["channel_id"] is not None:
        params["channel_id"] = ch["channel_id"]

    with engine.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

    return rows


class RangeRequest(BaseModel):
    start: date
    end: date
    channelRoot: str

@router.post("/range")
def range_aggregate(
    req: RangeRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    ch = resolve_channel(req.channelRoot)
    allowed = get_allowed_account_tags(db, current_user)
    if allowed is not None and ch["account_tag"] not in allowed:
        return []
    if current_user:
        hidden = get_hidden_account_tags(db, current_user.id)
        hidden_all = hidden | {sanitize_filename(t) for t in hidden}
        if ch["account_tag"] in hidden_all:
            return []
    cond_channel = "AND channel_id = :channel_id" if ch["channel_id"] is not None else ""

    sql = text(f"""
        SELECT
          source,
          SUM(views)::bigint AS "views",
          SUM(estimated_minutes_watched)::bigint AS "estimatedMinutesWatched",
          SUM(engaged_views)::bigint AS "engagedViews",
          CASE WHEN SUM(views) > 0
               THEN SUM(average_view_duration * views)::float / SUM(views)
               ELSE 0 END AS "averageViewDuration",
          CASE WHEN SUM(views) > 0
               THEN SUM(average_view_percentage * views)::float / SUM(views)
               ELSE 0 END AS "averageViewPercentage"
        FROM traffic_source_daily
        WHERE account_tag = :account_tag
          {cond_channel}
          AND day BETWEEN :start AND :end
        GROUP BY source
        ORDER BY "views" DESC
    """)

    params = {
        "account_tag": ch["account_tag"],
        "start": req.start,
        "end": req.end,
    }
    if ch["channel_id"] is not None:
        params["channel_id"] = ch["channel_id"]

    with engine.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

    return [{"id": r["source"], "label": r["source"], **r} for r in rows]
