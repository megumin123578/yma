import json
import os
from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user, get_current_user_optional
from python_backend.api.auth.database import SessionLocal, get_db
from python_backend.api.auth.models import (
    AppSetting,
    LiveCounterSnapshot,
    User,
    UserCredential,
    UserSchedule,
    UserScheduleRun,
    VideoLiveCounterSnapshot,
)
from sqlalchemy import func
from python_backend.api.auth.permissions import require_permission
from python_backend.progress_state import write_progress
from python_backend.sse_utils import sse_response
from python_backend.token_store import account_tag_from_token_name, list_token_names, token_exists
from python_backend.google_api_quota import get_quota_state
from python_backend.api.auth.scheduler import _now_saigon_naive, mark_channel_active

from .common import (
    router,
    _ALLOWED_RUN_STAGES,
    _is_admin_user,
    _kickoff_get_data,
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
    current_user: User = Depends(require_permission("manage_structure")),
):
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
    row.finished_at = _now_saigon_naive()
    db.add(row)
    db.commit()
    return {"ok": True, "status": row.status}


@router.post("/schedules/runs/{run_id}/resume")
def resume_schedule_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_structure")),
):
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
            started_at=_now_saigon_naive(),
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
            started_at=_now_saigon_naive(),
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
            started_at=_now_saigon_naive(),
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
            started_at=_now_saigon_naive(),
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
            started_at=_now_saigon_naive(),
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
    current_user: User = Depends(require_permission("manage_structure")),
):
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
    current_user: User = Depends(require_permission("manage_structure")),
):
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
    current_user: User = Depends(require_permission("manage_structure")),
):
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


LIVE_COUNTER_SETTING_KEY = "live_counter_snapshots"
LIVE_COUNTER_INTERVAL_MIN = 60
LIVE_COUNTER_INTERVAL_MAX = 24 * 60 * 60
LIVE_COUNTER_INTERVAL_DEFAULT = 60
LIVE_COUNTER_RETENTION_DAYS = 2

CRON_SCHEDULE_SETTING_KEY = "cron_schedule"


def _load_cron_schedule_setting(db: Session) -> dict:
    row = db.query(AppSetting).filter(AppSetting.key == CRON_SCHEDULE_SETTING_KEY).first()
    if row and row.value:
        try:
            data = json.loads(row.value)
        except Exception:
            data = {}
    else:
        data = {}
    return {
        "enabled": bool(data.get("enabled", True)),
        "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
    }


def load_cron_schedule_setting() -> dict:
    db = SessionLocal()
    try:
        return _load_cron_schedule_setting(db)
    finally:
        db.close()


class CronScheduleSettingUpdate(BaseModel):
    enabled: bool


@router.get("/app_settings/cron_schedule")
def get_cron_schedule_setting(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Permission Denied")
    return _load_cron_schedule_setting(db)


@router.patch("/app_settings/cron_schedule")
def update_cron_schedule_setting(
    payload: CronScheduleSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_structure")),
):
    value = json.dumps({"enabled": bool(payload.enabled)})
    row = db.query(AppSetting).filter(AppSetting.key == CRON_SCHEDULE_SETTING_KEY).first()
    if row is None:
        row = AppSetting(key=CRON_SCHEDULE_SETTING_KEY, value=value, updated_at=datetime.utcnow())
        db.add(row)
    else:
        row.value = value
        row.updated_at = datetime.utcnow()
    db.commit()
    return _load_cron_schedule_setting(db)


BACKUP_SETTING_KEY = "backup_telegram"
BACKUP_DEFAULT_TIME = "02:00"


def _validate_backup_time_of_day(value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="time_of_day required")
    try:
        h_str, m_str = value.split(":")
        h, m = int(h_str), int(m_str)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
    except Exception:
        raise HTTPException(status_code=400, detail="time_of_day must be HH:MM (00:00-23:59)")
    return f"{h:02d}:{m:02d}"


def _load_backup_setting(db: Session) -> dict:
    row = db.query(AppSetting).filter(AppSetting.key == BACKUP_SETTING_KEY).first()
    if row and row.value:
        try:
            data = json.loads(row.value)
        except Exception:
            data = {}
    else:
        data = {}
    return {
        "enabled": bool(data.get("enabled", False)),
        "time_of_day": str(data.get("time_of_day") or BACKUP_DEFAULT_TIME),
        "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
    }


def load_backup_setting() -> dict:
    db = SessionLocal()
    try:
        return _load_backup_setting(db)
    finally:
        db.close()


class BackupSettingUpdate(BaseModel):
    enabled: Optional[bool] = None
    time_of_day: Optional[str] = None


@router.get("/app_settings/backup_telegram")
def get_backup_setting(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Permission Denied")
    return _load_backup_setting(db)


@router.patch("/app_settings/backup_telegram")
def update_backup_setting(
    payload: BackupSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_structure")),
):
    current = _load_backup_setting(db)
    if payload.enabled is not None:
        current["enabled"] = bool(payload.enabled)
    if payload.time_of_day is not None:
        current["time_of_day"] = _validate_backup_time_of_day(payload.time_of_day)

    value = json.dumps({
        "enabled": current["enabled"],
        "time_of_day": current["time_of_day"],
    })
    row = db.query(AppSetting).filter(AppSetting.key == BACKUP_SETTING_KEY).first()
    if row is None:
        row = AppSetting(key=BACKUP_SETTING_KEY, value=value, updated_at=datetime.utcnow())
        db.add(row)
    else:
        row.value = value
        row.updated_at = datetime.utcnow()
    db.commit()
    return _load_backup_setting(db)


@router.post("/app_settings/backup_telegram/run")
def run_backup_now(
    current_user: User = Depends(require_permission("manage_structure")),
):
    if not os.getenv("BACKUP_TELEGRAM_BOT_TOKEN", "").strip() or \
       not os.getenv("BACKUP_TELEGRAM_CHAT_ID", "").strip():
        raise HTTPException(
            status_code=400,
            detail="Missing BACKUP_TELEGRAM_BOT_TOKEN or BACKUP_TELEGRAM_CHAT_ID in backend env.",
        )
    from python_backend.api.auth.scheduler import kickoff_backup

    kickoff_backup()
    return {"ok": True, "message": "Backup started in background."}


def _load_live_counter_setting(db: Session) -> dict:
    row = db.query(AppSetting).filter(AppSetting.key == LIVE_COUNTER_SETTING_KEY).first()
    if row and row.value:
        try:
            data = json.loads(row.value)
        except Exception:
            data = {}
    else:
        data = {}
    enabled = bool(data.get("enabled", False))
    interval = int(data.get("interval_seconds") or LIVE_COUNTER_INTERVAL_DEFAULT)
    interval = max(LIVE_COUNTER_INTERVAL_MIN, min(LIVE_COUNTER_INTERVAL_MAX, interval))
    return {
        "enabled": enabled,
        "interval_seconds": interval,
        "retention_days": LIVE_COUNTER_RETENTION_DAYS,
        "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
    }


def load_live_counter_setting() -> dict:
    db = SessionLocal()
    try:
        return _load_live_counter_setting(db)
    finally:
        db.close()


class LiveCounterSettingUpdate(BaseModel):
    enabled: Optional[bool] = None
    interval_seconds: Optional[int] = None


@router.get("/app_settings/live_counter")
def get_live_counter_setting(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Permission Denied")
    return _load_live_counter_setting(db)


@router.patch("/app_settings/live_counter")
def update_live_counter_setting(
    payload: LiveCounterSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_structure")),
):
    current = _load_live_counter_setting(db)
    if payload.enabled is not None:
        current["enabled"] = bool(payload.enabled)
    if payload.interval_seconds is not None:
        if not (LIVE_COUNTER_INTERVAL_MIN <= payload.interval_seconds <= LIVE_COUNTER_INTERVAL_MAX):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"interval_seconds must be between {LIVE_COUNTER_INTERVAL_MIN} "
                    f"and {LIVE_COUNTER_INTERVAL_MAX}"
                ),
            )
        current["interval_seconds"] = int(payload.interval_seconds)

    value = json.dumps(
        {
            "enabled": current["enabled"],
            "interval_seconds": current["interval_seconds"],
        }
    )
    row = db.query(AppSetting).filter(AppSetting.key == LIVE_COUNTER_SETTING_KEY).first()
    if row is None:
        row = AppSetting(key=LIVE_COUNTER_SETTING_KEY, value=value, updated_at=datetime.utcnow())
        db.add(row)
    else:
        row.value = value
        row.updated_at = datetime.utcnow()
    db.commit()
    return _load_live_counter_setting(db)


class LiveCounterHeartbeat(BaseModel):
    account_tag: str


@router.post("/live_counter/heartbeat")
def live_counter_heartbeat(
    payload: LiveCounterHeartbeat,
    current_user: User = Depends(get_current_user_optional),
):
    tag = (payload.account_tag or "").strip()
    if not tag:
        raise HTTPException(status_code=400, detail="Missing account_tag")
    mark_channel_active(tag)
    return {"ok": True}


@router.get("/app_settings/google_api_quota")
def get_google_api_quota(
    current_user: User = Depends(get_current_user),
):
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Permission Denied")
    return get_quota_state()


@router.get("/app_settings/live_counter/latest")
def list_latest_live_counter_snapshots(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Permission Denied")

    live_tokens = set(list_token_names())
    if not live_tokens:
        return {"items": []}

    items = []
    for tag in sorted(live_tokens):
        rows = (
            db.query(LiveCounterSnapshot)
            .filter(LiveCounterSnapshot.account_tag == tag)
            .order_by(
                LiveCounterSnapshot.captured_at.desc(),
                LiveCounterSnapshot.id.desc(),
            )
            .limit(2)
            .all()
        )
        if not rows:
            continue
        latest = rows[0]
        prev = rows[1] if len(rows) > 1 else None
        items.append((tag, latest, prev))

    tags = {tag for tag, _, _ in items}
    titles = {}
    if tags:
        cred_rows = (
            db.query(UserCredential.account_tag, UserCredential.selected_channel_title)
            .filter(UserCredential.account_tag.in_(tags))
            .all()
        )
        for tag, title in cred_rows:
            if tag and title:
                titles[tag] = title

    def _diff(curr, prev_value):
        if prev_value is None:
            return None
        return int(curr or 0) - int(prev_value or 0)

    def _video_view_delta(tag, latest_snap, prev_snap):
        if prev_snap is None or latest_snap is None:
            return None
        if latest_snap.captured_at is None or prev_snap.captured_at is None:
            return None
        video_rows = (
            db.query(VideoLiveCounterSnapshot.video_id,
                     VideoLiveCounterSnapshot.view_count,
                     VideoLiveCounterSnapshot.captured_at)
            .filter(
                VideoLiveCounterSnapshot.account_tag == tag,
                VideoLiveCounterSnapshot.captured_at.in_(
                    [latest_snap.captured_at, prev_snap.captured_at]
                ),
            )
            .all()
        )
        latest_by_vid: dict[str, int] = {}
        prev_by_vid: dict[str, int] = {}
        for vid, vc, cap in video_rows:
            if not vid:
                continue
            value = int(vc or 0)
            if cap == latest_snap.captured_at:
                latest_by_vid[vid] = value
            elif cap == prev_snap.captured_at:
                prev_by_vid[vid] = value
        if not latest_by_vid or not prev_by_vid:
            return _diff(latest_snap.view_count, prev_snap.view_count)
        total = 0
        for vid, latest_val in latest_by_vid.items():
            prev_val = prev_by_vid.get(vid)
            if prev_val is None:
                continue
            total += max(0, latest_val - prev_val)
        return total

    return {
        "items": [
            {
                "account_tag": tag,
                "channel_title": titles.get(tag, tag),
                "subscriber_count": int(latest.subscriber_count or 0),
                "view_count": int(latest.view_count or 0),
                "video_count": int(latest.video_count or 0),
                "captured_at": latest.captured_at.isoformat() if latest.captured_at else None,
                "diff": {
                    "view_count": _video_view_delta(tag, latest, prev),
                    "subscriber_count": _diff(
                        latest.subscriber_count, prev.subscriber_count if prev else None
                    ),
                    "video_count": _diff(latest.video_count, prev.video_count if prev else None),
                    "previous_captured_at": (
                        prev.captured_at.isoformat() if prev and prev.captured_at else None
                    ),
                },
            }
            for tag, latest, prev in items
        ]
    }


