from fastapi import APIRouter, Depends, Query
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user_optional
from python_backend.api.auth.database import get_db
from python_backend.api.auth.visibility import get_hidden_account_tags
from python_backend.module_trafficsource import sanitize_filename


router = APIRouter(prefix="/api/audience", tags=["audience"])


def _filter_hidden(accounts, hidden):
    hidden_all = set(hidden) | {sanitize_filename(tag) for tag in hidden}
    return [acct for acct in accounts if acct not in hidden_all]


@router.get("/demographics")
def get_demographics(
    accountTag: str = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    hidden = get_hidden_account_tags(db, current_user.id) if current_user else set()
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        return {"availableAccounts": [], "rows": []}
    try:
        pg_engine = create_engine(pg_url, future=True)
        with pg_engine.connect() as conn:
            if not accountTag:
                rows = conn.execute(
                    text("SELECT DISTINCT account_tag FROM audience_demographics ORDER BY account_tag")
                ).fetchall()
                accounts = _filter_hidden([r[0] for r in rows], hidden)
                return {"availableAccounts": accounts, "rows": []}

            safe_tag = sanitize_filename(accountTag)
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
    hidden = get_hidden_account_tags(db, current_user.id) if current_user else set()
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        return {"availableAccounts": [], "videos": [], "rows": []}
    try:
        pg_engine = create_engine(pg_url, future=True)
        with pg_engine.connect() as conn:
            if not accountTag:
                rows = conn.execute(
                    text("SELECT DISTINCT account_tag FROM audience_retention ORDER BY account_tag")
                ).fetchall()
                accounts = _filter_hidden([r[0] for r in rows], hidden)
                return {"availableAccounts": accounts, "videos": [], "rows": []}

            safe_tag = sanitize_filename(accountTag)
            if not videoId:
                rows = conn.execute(
                    text(
                        """
                        SELECT DISTINCT r.video_id, v.title
                        FROM audience_retention r
                        LEFT JOIN videos v
                          ON v.video_id = r.video_id AND v.account_tag = r.account_tag
                        WHERE r.account_tag = :acct
                        ORDER BY v.title NULLS LAST, r.video_id
                        """
                    ),
                    {"acct": safe_tag},
                ).fetchall()
                videos = [{"video_id": r[0], "title": r[1]} for r in rows]
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
