import os
from fastapi import APIRouter, Depends, Query
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user_optional
from python_backend.api.auth.database import get_db
from python_backend.api.auth.visibility import get_allowed_account_tags, get_hidden_account_tags
from python_backend.api.auth.models import UserCredential
from python_backend.module_trafficsource import sanitize_filename
from python_backend.module_reach import _ensure_reach_table


router = APIRouter(prefix="/api/reach", tags=["reach"])

def _is_external_source(source: str) -> bool:
    if not source:
        return False
    upper = source.upper()
    return upper.startswith("EXT") or "EXTERNAL" in upper


def _load_latest_reach_range(conn, account_tag: str):
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
        {"acct": account_tag},
    ).fetchone()
    if not latest:
        return None, None
    return latest


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
                    r.video_id,
                    r.title,
                    r.thumbnail,
                    r.views,
                    r.estimated_minutes_watched,
                    r.annotation_impressions,
                    r.card_impressions,
                    r.teaser_impressions,
                    r.total_impressions,
                    r.annotation_clicks,
                    r.card_clicks,
                    r.teaser_clicks,
                    r.total_clicks,
                    r.annotation_ctr,
                    r.card_ctr,
                    r.teaser_ctr,
                    r.total_ctr
                FROM reach_video_metrics r
                LEFT JOIN videos v
                  ON v.video_id = r.video_id
                 AND v.account_tag = r.account_tag
                WHERE r.account_tag = :acct
                  AND r.start_date = :start
                  AND r.end_date = :end
                ORDER BY v.published_at DESC NULLS LAST, r.views DESC
                LIMIT 20
                """
            ),
            {"acct": safe_tag, "start": start_date, "end": end_date},
        ).mappings().all()
    return {
        "rows": rows,
        "start_date": str(start_date),
        "end_date": str(end_date),
    }


@router.get("/traffic_breakdown")
def reach_traffic_breakdown(
    accountTag: str = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        return {"range": {"start": None, "end": None}, "external": [], "playlist": 0, "suggested": 0, "browse": 0}
    if not accountTag:
        return {"range": {"start": None, "end": None}, "external": [], "playlist": 0, "suggested": 0, "browse": 0}
    allowed = get_allowed_account_tags(db, current_user)
    safe_tag = sanitize_filename(accountTag)
    if allowed is not None and safe_tag not in allowed:
        return {"range": {"start": None, "end": None}, "external": [], "playlist": 0, "suggested": 0, "browse": 0}
    if current_user:
        hidden = get_hidden_account_tags(db, current_user.id)
        hidden_all = hidden | {sanitize_filename(t) for t in hidden}
        if safe_tag in hidden_all:
            return {"range": {"start": None, "end": None}, "external": [], "playlist": 0, "suggested": 0, "browse": 0}

    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        _ensure_reach_table(conn)
        start_date, end_date = _load_latest_reach_range(conn, safe_tag)
        if not start_date or not end_date:
            return {"range": {"start": None, "end": None}, "external": [], "playlist": 0, "suggested": 0, "browse": 0}
        rows = conn.execute(
            text(
                """
                SELECT source, SUM(views)::bigint AS views
                FROM traffic_source_daily
                WHERE account_tag = :acct
                  AND day >= :start
                  AND day <= :end
                GROUP BY source
                ORDER BY views DESC
                """
            ),
            {"acct": safe_tag, "start": start_date, "end": end_date},
        ).fetchall()

    external = []
    playlist = 0
    suggested = 0
    browse = 0
    for src, views in rows:
        src_val = src or ""
        views_val = int(views or 0)
        if _is_external_source(src_val):
            external.append({"source": src_val, "views": views_val})
        src_upper = src_val.upper()
        if "PLAYLIST" in src_upper:
            playlist += views_val
        if src_upper in {"SUGGESTED_VIDEO", "RELATED_VIDEO"}:
            suggested += views_val
        if src_upper in {"BROWSE", "YT_OTHER_PAGE", "YT_HOME"}:
            browse += views_val

    external_sorted = sorted(external, key=lambda x: x["views"], reverse=True)
    return {
        "range": {"start": str(start_date), "end": str(end_date)},
        "external": external_sorted[:5],
        "playlist": playlist,
        "suggested": suggested,
        "browse": browse,
    }
