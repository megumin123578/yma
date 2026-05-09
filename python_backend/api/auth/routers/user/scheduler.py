import json
from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user, get_current_user_optional
from python_backend.api.auth.database import SessionLocal, get_db
from python_backend.api.auth.models import User, UserSchedule, UserScheduleRun
from python_backend.progress_state import write_progress
from python_backend.sse_utils import sse_response
from python_backend.token_store import account_tag_from_token_name, token_exists

from .common import (
    router,
    _ALLOWED_RUN_STAGES,
    _is_admin_user,
    _kickoff_get_data,
    _require_admin,
    _run_channel_titles,
    _run_token_names_from_row,
    _safe_token_name,
)


class ScheduleCreate(BaseModel):
    time_of_day: Optional[str] = None
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    enabled: Optional[bool] = None
    time_of_day: Optional[str] = None


@router.get("/schedules")
def list_schedules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Permission Denied")
    rows = (
        db.query(UserSchedule)
        .order_by(UserSchedule.id.desc())
        .all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "time_of_day": r.time_of_day,
                "enabled": bool(r.enabled),
                "last_run_at": r.last_run_at.isoformat() if r.last_run_at else None,
            }
            for r in rows
        ]
    }


@router.get("/schedules/runs")
def list_schedule_runs(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    is_admin = _is_admin_user(current_user)
    if not is_admin:
        raise HTTPException(status_code=403, detail="Permission Denied")
    rows = (
        db.query(UserScheduleRun)
        .order_by(UserScheduleRun.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "schedule_id": r.schedule_id,
                "token_name": r.token_name,
                "token_names": r.token_names,
                "run_type": r.run_type,
                "channel_titles": _run_channel_titles(db, r.user_id, _run_token_names_from_row(r)),
                "status": r.status,
                "processed": r.processed,
                "total": r.total,
                "message": r.message,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in rows
        ]
    }


def _serialize_schedule_runs(limit: int) -> dict:
    db = SessionLocal()
    try:
        rows = (
            db.query(UserScheduleRun)
            .order_by(UserScheduleRun.id.desc())
            .limit(limit)
            .all()
        )
        return {
            "items": [
                {
                    "id": r.id,
                    "schedule_id": r.schedule_id,
                    "token_name": r.token_name,
                    "token_names": r.token_names,
                    "run_type": r.run_type,
                    "channel_titles": _run_channel_titles(db, r.user_id, _run_token_names_from_row(r)),
                    "status": r.status,
                    "processed": r.processed,
                    "total": r.total,
                    "message": r.message,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                }
                for r in rows
            ]
        }
    finally:
        db.close()


@router.get("/schedules/runs/stream")
async def stream_schedule_runs(
    request: Request,
    limit: int = Query(10, ge=1, le=100),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    import asyncio
    import json
    from fastapi.concurrency import run_in_threadpool

    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Permission Denied")

    async def gen():
        last_payload: Optional[str] = None
        elapsed_since_emit = 0.0
        first = True
        while True:
            if await request.is_disconnected():
                return
            try:
                snapshot = await run_in_threadpool(_serialize_schedule_runs, limit)
            except Exception as exc:  # noqa: BLE001
                yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
                return

            payload = json.dumps(snapshot, default=str)
            if first or payload != last_payload:
                last_payload = payload
                elapsed_since_emit = 0.0
                yield f"data: {payload}\n\n"
                first = False

            active = any(
                (item.get("status") or "").lower()
                in ("running", "pending", "queued", "in_progress")
                for item in snapshot.get("items", [])
            )
            interval = 5.0 if active else 30.0
            await asyncio.sleep(interval)
            elapsed_since_emit += interval
            if elapsed_since_emit >= 25.0:
                elapsed_since_emit = 0.0
                yield ": ping\n\n"

    return sse_response(gen())


@router.post("/schedules/runs/{run_id}/stop")
def stop_schedule_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    row = (
        db.query(UserScheduleRun)
        .filter(UserScheduleRun.id == run_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    if row.status not in {"running", "queued"}:
        return {"ok": True, "status": row.status}
    row.status = "stopped"
    row.message = "Stopped by admin"
    row.finished_at = datetime.utcnow()
    db.add(row)
    db.commit()
    return {"ok": True, "status": row.status}


@router.post("/schedules/runs/{run_id}/resume")
def resume_schedule_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    row = (
        db.query(UserScheduleRun)
        .filter(UserScheduleRun.id == run_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    if row.status in {"running", "queued"}:
        return {"ok": True, "status": row.status, "run_id": row.id}

    token_names = _run_token_names_from_row(row)
    if not token_names:
        raise HTTPException(status_code=400, detail="Run has no tokens to resume")

    valid_token_names = []
    for token_name in token_names:
        safe_name = _safe_token_name(str(token_name or "").strip())
        if not safe_name or safe_name != str(token_name or "").strip():
            continue
        if token_exists(safe_name):
            valid_token_names.append(safe_name)
    valid_token_names = sorted(set(valid_token_names))
    if not valid_token_names:
        raise HTTPException(status_code=400, detail="No tokens available to resume")

    run_type = str(row.run_type or "").strip().lower()
    message = "Queued manual refresh"
    total = len(valid_token_names)
    account_tag = ""
    env_extra = {}

    if run_type == "manual_all":
        for token_name in valid_token_names:
            write_progress(account_tag_from_token_name(token_name), "queued", 0, "queued", "Queued manual refresh")
        message = f"Queued manual refresh for {len(valid_token_names)} token(s)"
        new_run = UserScheduleRun(
            user_id=current_user.id,
            schedule_id=None,
            token_name=None,
            token_names=json.dumps(valid_token_names),
            run_type="manual_all",
            status="queued",
            started_at=datetime.utcnow(),
            processed=0,
            total=len(valid_token_names),
            message=message,
        )
        env_extra = {
            "RUN_TOKEN_NAMES": json.dumps(valid_token_names),
        }
    elif run_type.startswith("manual_all_stage:"):
        stage = run_type.split(":", 1)[1].strip().lower()
        if stage not in _ALLOWED_RUN_STAGES:
            raise HTTPException(status_code=400, detail="Run stage cannot be resumed")
        for token_name in valid_token_names:
            write_progress(account_tag_from_token_name(token_name), "queued", 0, "queued", f"Queued manual {stage}")
        message = f"Queued manual {stage} for {len(valid_token_names)} token(s)"
        new_run = UserScheduleRun(
            user_id=current_user.id,
            schedule_id=None,
            token_name=None,
            token_names=json.dumps(valid_token_names),
            run_type=f"manual_all_stage:{stage}",
            status="queued",
            started_at=datetime.utcnow(),
            processed=0,
            total=len(valid_token_names),
            message=message,
        )
        env_extra = {
            "RUN_TOKEN_NAMES": json.dumps(valid_token_names),
            "RUN_STAGE": stage,
        }
    elif run_type == "manual_selected":
        for token_name in valid_token_names:
            write_progress(account_tag_from_token_name(token_name), "queued", 0, "queued", "Queued manual refresh")
        message = f"Queued manual refresh for {len(valid_token_names)} selected token(s)"
        new_run = UserScheduleRun(
            user_id=current_user.id,
            schedule_id=None,
            token_name=None,
            token_names=json.dumps(valid_token_names),
            run_type="manual_selected",
            status="queued",
            started_at=datetime.utcnow(),
            processed=0,
            total=len(valid_token_names),
            message=message,
        )
        env_extra = {
            "RUN_TOKEN_NAMES": json.dumps(valid_token_names),
        }
    elif run_type.startswith("manual_stage:"):
        stage = run_type.split(":", 1)[1].strip().lower()
        if stage not in _ALLOWED_RUN_STAGES:
            raise HTTPException(status_code=400, detail="Run stage cannot be resumed")
        token_name = valid_token_names[0]
        account_tag = account_tag_from_token_name(token_name)
        write_progress(account_tag, "queued", 0, "queued", f"Manual {stage}")
        message = f"Queued manual {stage}"
        new_run = UserScheduleRun(
            user_id=current_user.id,
            schedule_id=None,
            token_name=token_name,
            token_names=json.dumps([token_name]),
            run_type=f"manual_stage:{stage}",
            status="queued",
            started_at=datetime.utcnow(),
            processed=0,
            total=1,
            message=message,
        )
        env_extra = {"RUN_STAGE": stage}
    else:
        token_name = valid_token_names[0]
        account_tag = account_tag_from_token_name(token_name)
        write_progress(account_tag, "queued", 0, "queued", "Manual refresh")
        message = "Queued manual refresh"
        new_run = UserScheduleRun(
            user_id=current_user.id,
            schedule_id=None,
            token_name=token_name,
            token_names=json.dumps([token_name]),
            run_type="manual_single" if run_type in {"manual_single", "scheduled", ""} else (row.run_type or "manual_single"),
            status="queued",
            started_at=datetime.utcnow(),
            processed=0,
            total=7,
            message=message,
        )

    db.add(new_run)
    db.commit()
    db.refresh(new_run)
    env_extra["SCHEDULE_RUN_ID"] = str(new_run.id)
    _kickoff_get_data(account_tag, env_extra=env_extra)
    return {"ok": True, "status": new_run.status, "run_id": new_run.id}

@router.post("/schedules")
def create_schedule(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    if not payload.time_of_day:
        raise HTTPException(status_code=400, detail="time_of_day is required")

    row = UserSchedule(
        user_id=current_user.id,
        mode="daily",
        time_of_day=payload.time_of_day,
        every_minutes=None,
        enabled=1 if payload.enabled else 0,
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.patch("/schedules/{schedule_id}")
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    row = (
        db.query(UserSchedule)
        .filter(
            UserSchedule.user_id == current_user.id,
            UserSchedule.id == schedule_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if payload.enabled is not None:
        row.enabled = 1 if payload.enabled else 0
    if payload.time_of_day is not None:
        row.time_of_day = payload.time_of_day
    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    return {"ok": True}


@router.delete("/schedules/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    row = (
        db.query(UserSchedule)
        .filter(
            UserSchedule.user_id == current_user.id,
            UserSchedule.id == schedule_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


