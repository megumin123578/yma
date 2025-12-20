# routes/channel_compare.py
from datetime import date, timedelta
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from python_backend.db import engine

router = APIRouter(prefix="/api/channel_compare", tags=["channel_compare"])


class CompareRequest(BaseModel):
    start: date
    end: date
    metric: str = "views"
    limit: int = 20


_ALLOWED_METRICS = {
    "views",
    "estimatedMinutesWatched",
    "averageViewDuration",
    "averageViewPercentage",
    "engagedViews",
}


def _agg_range(start: date, end: date):
    sql = text(
        """
        SELECT
          account_tag,
          SUM(views)::bigint AS views,
          SUM(estimated_minutes_watched)::bigint AS "estimatedMinutesWatched",
          SUM(engaged_views)::bigint AS "engagedViews",
          CASE WHEN SUM(views) > 0
               THEN SUM(average_view_duration * views)::float / SUM(views)
               ELSE 0 END AS "averageViewDuration",
          CASE WHEN SUM(views) > 0
               THEN SUM(average_view_percentage * views)::float / SUM(views)
               ELSE 0 END AS "averageViewPercentage"
        FROM traffic_source_daily
        WHERE account_tag IS NOT NULL AND account_tag <> ''
          AND day BETWEEN :start AND :end
        GROUP BY account_tag
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(sql, {"start": start, "end": end}).mappings().all()
    return {r["account_tag"]: dict(r) for r in rows}


@router.post("/rank")
def compare_rank(req: CompareRequest):
    if req.metric not in _ALLOWED_METRICS:
        raise HTTPException(400, "metric khong hop le")

    if req.end < req.start:
        raise HTTPException(400, "end phai >= start")

    period_days = (req.end - req.start).days + 1
    prev_end = req.start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days - 1)

    cur = _agg_range(req.start, req.end)
    prev = _agg_range(prev_start, prev_end)

    items: List[dict] = []
    keys = set(cur.keys()) | set(prev.keys())

    for account_tag in keys:
        cur_row = cur.get(account_tag, {})
        prev_row = prev.get(account_tag, {})

        current_value = float(cur_row.get(req.metric, 0) or 0)
        previous_value = float(prev_row.get(req.metric, 0) or 0)
        delta = current_value - previous_value

        if previous_value == 0:
            delta_pct = None
            trend = "new" if current_value > 0 else "flat"
        else:
            delta_pct = (delta / previous_value) * 100
            if delta > 0:
                trend = "up"
            elif delta < 0:
                trend = "down"
            else:
                trend = "flat"

        items.append(
            {
                "accountTag": account_tag,
                "current": cur_row,
                "previous": prev_row,
                "currentValue": current_value,
                "previousValue": previous_value,
                "delta": delta,
                "deltaPct": delta_pct,
                "trend": trend,
            }
        )

    items.sort(key=lambda x: x.get("currentValue", 0), reverse=True)
    limit = max(1, min(int(req.limit or 20), 200))

    return {
        "start": req.start.isoformat(),
        "end": req.end.isoformat(),
        "prev_start": prev_start.isoformat(),
        "prev_end": prev_end.isoformat(),
        "metric": req.metric,
        "items": items[:limit],
    }
