import os
from datetime import datetime
from typing import Optional

try:
    from python_backend.api.auth.database import SessionLocal
    from python_backend.api.auth.models import TokenProgress, UserCredential
except ModuleNotFoundError:
    from api.auth.database import SessionLocal
    from api.auth.models import TokenProgress, UserCredential

def write_progress(
    account_tag: str,
    stage: str,
    percent: int,
    status: str,
    message: str = "",
    run_id: Optional[str] = None,
) -> None:
    if not account_tag:
        return
    resolved_run_id = str(run_id or os.getenv("SCHEDULE_RUN_ID") or "").strip()
    _write_progress_db(
        account_tag=account_tag,
        stage=stage,
        percent=percent,
        status=status,
        message=message,
        run_id=resolved_run_id or None,
    )


def _write_progress_db(
    account_tag: str,
    stage: str,
    percent: int,
    status: str,
    message: str = "",
    run_id: Optional[str] = None,
) -> None:
    db = SessionLocal()
    try:
        cred = (
            db.query(UserCredential)
            .filter(UserCredential.account_tag == account_tag)
            .order_by(UserCredential.updated_at.desc(), UserCredential.id.desc())
            .first()
        )
        if not cred or not cred.user_id or not cred.token_name:
            return
        row = (
            db.query(TokenProgress)
            .filter(
                TokenProgress.user_id == cred.user_id,
                TokenProgress.token_name == cred.token_name,
            )
            .first()
        )
        now = datetime.utcnow()
        if row is None:
            row = TokenProgress(
                user_id=cred.user_id,
                token_name=cred.token_name,
                account_tag=account_tag,
                started_at=now if status in {"queued", "running"} else None,
            )
        row.account_tag = account_tag
        row.run_id = run_id
        row.status = status
        row.stage = stage
        row.percent = int(percent or 0)
        row.message = message
        if row.started_at is None and status in {"queued", "running"}:
            row.started_at = now
        if status in {"done", "error", "stopped", "empty"}:
            row.finished_at = now
        else:
            row.finished_at = None
        row.updated_at = now
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
