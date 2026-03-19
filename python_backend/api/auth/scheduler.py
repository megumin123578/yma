import os
import json
import subprocess
import sys
from datetime import datetime, time as dtime, timedelta, timezone
from typing import Optional
from threading import Event, Thread

from googleapiclient.errors import HttpError
from sqlalchemy import text

from python_backend.api.auth.database import SessionLocal
from python_backend.api.auth.models import (
    LiveCounterSnapshot,
    VideoLiveCounterSnapshot,
    UserCredential,
    UserSchedule,
    UserScheduleRun,
)
from python_backend.db import engine as analytics_engine


_STOP_EVENT = Event()
_THREAD = None
_RUNS_MAX = int(os.getenv("SCHEDULE_RUNS_MAX", "200"))
_LIVE_COUNTER_SNAPSHOT_INTERVAL_SECONDS = int(
    os.getenv("LIVE_COUNTER_SNAPSHOT_INTERVAL_SECONDS", str(5 * 60))
)
_LIVE_COUNTER_RETENTION_DAYS = int(os.getenv("LIVE_COUNTER_RETENTION_DAYS", "7"))
_LAST_LIVE_COUNTER_SNAPSHOT_AT = None
SAIGON_TZ = timezone(timedelta(hours=7))


def _now_saigon_naive() -> datetime:
    return datetime.now(SAIGON_TZ).replace(tzinfo=None)


def _kickoff_get_data(account_tag: Optional[str], env_extra: Optional[dict] = None) -> None:
    script_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "get_data.py")
    )
    if not os.path.exists(script_path):
        script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "python_backend", "get_data.py")
        )
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
    )
    if not os.path.exists(script_path):
        print(f"[WARN] get_data.py not found: {script_path}")
        return
    try:
        cmd = [sys.executable, script_path]
        if account_tag:
            cmd.append(account_tag)
        env = os.environ.copy()
        if env_extra:
            env.update(env_extra)
        subprocess.Popen(
            cmd,
            cwd=repo_root,
            env=env,
        )
    except Exception as e:
        print(f"[WARN] Failed to start get_data.py: {e}")


def _parse_time_of_day(value: str):
    if not value:
        return None
    try:
        parts = value.split(":")
        if len(parts) < 2:
            return None
        hour = int(parts[0])
        minute = int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        return dtime(hour=hour, minute=minute)
    except Exception:
        return None


def _should_run(schedule: UserSchedule, now: datetime) -> bool:
    if schedule.enabled != 1:
        return False

    last = schedule.last_run_at
    tod = _parse_time_of_day(schedule.time_of_day or "")
    if tod is None:
        return False
    today_at = datetime.combine(now.date(), tod)
    if now < today_at:
        return False
    if last is None:
        created_at = schedule.created_at or now
        if created_at.date() == now.date() and now >= today_at:
            return False
        return True
    return last.date() < now.date()


def _should_capture_live_counters(now: datetime) -> bool:
    global _LAST_LIVE_COUNTER_SNAPSHOT_AT
    if _LIVE_COUNTER_SNAPSHOT_INTERVAL_SECONDS <= 0:
        return False
    if _LAST_LIVE_COUNTER_SNAPSHOT_AT is None:
        _LAST_LIVE_COUNTER_SNAPSHOT_AT = now
        return True
    elapsed = (now - _LAST_LIVE_COUNTER_SNAPSHOT_AT).total_seconds()
    if elapsed < _LIVE_COUNTER_SNAPSHOT_INTERVAL_SECONDS:
        return False
    _LAST_LIVE_COUNTER_SNAPSHOT_AT = now
    return True


def _get_youtube_api_keys() -> list[str]:
    keys = [
        os.getenv("YOUTUBE_API_KEY1", "").strip(),
        os.getenv("YOUTUBE_API_KEY2", "").strip(),
        os.getenv("YOUTUBE_API_KEY", "").strip(),
    ]
    return [key for key in keys if key]


def _is_quota_exceeded(err) -> bool:
    try:
        details = getattr(err, "error_details", None) or []
        for item in details:
            if item.get("reason") == "quotaExceeded":
                return True
    except Exception:
        pass
    return "quotaExceeded" in str(err)


def _capture_live_counter_snapshots(db, now: datetime) -> None:
    from googleapiclient.discovery import build

    api_keys = _get_youtube_api_keys()
    if not api_keys:
        print("[WARN] live counter snapshot skipped: missing YOUTUBE_API_KEY1/2 or YOUTUBE_API_KEY")
        return

    rows = (
        db.query(UserCredential)
        .filter(UserCredential.token_name.isnot(None))
        .filter(UserCredential.selected_channel_id.isnot(None))
        .all()
    )
    if not rows:
        print("[INFO] live counter snapshot skipped: no eligible accounts")
        return

    print(f"[INFO] live counter snapshot started: accounts={len(rows)}")
    channel_snapshots = []
    latest_video_snapshots = {}
    processed_accounts = 0
    failed_accounts = 0
    for row in rows:
        token_name = os.path.basename(row.token_name or "").strip()
        if not token_name:
            continue
        if not (row.selected_channel_id or "").strip():
            continue
        try:
            last_error = None
            handled = False
            for api_key in api_keys:
                try:
                    youtube = build("youtube", "v3", developerKey=api_key)
                    query = {"part": "snippet,statistics", "id": row.selected_channel_id}
                    resp = youtube.channels().list(**query).execute() or {}
                    items = resp.get("items") or []
                    if not items:
                        handled = True
                        break
                    channel_snippet = items[0].get("snippet", {}) or {}
                    stats = (items[0].get("statistics") or {})
                    channel_id = row.selected_channel_id or items[0].get("id") or None
                    channel_name = (
                        channel_snippet.get("title")
                        or row.selected_channel_title
                        or row.account_tag
                    )
                    current_view_count = int(stats.get("viewCount", 0) or 0)
                    latest_channel_snapshot = (
                        db.query(LiveCounterSnapshot)
                        .filter(
                            LiveCounterSnapshot.user_id == row.user_id,
                            LiveCounterSnapshot.account_tag == row.account_tag,
                        )
                        .order_by(LiveCounterSnapshot.captured_at.desc(), LiveCounterSnapshot.id.desc())
                        .first()
                    )
                    if latest_channel_snapshot and latest_channel_snapshot.view_count is not None:
                        current_view_count = max(
                            current_view_count,
                            int(latest_channel_snapshot.view_count or 0),
                        )
                    channel_snapshot = LiveCounterSnapshot(
                        user_id=row.user_id,
                        account_tag=row.account_tag,
                        channel_id=channel_id,
                        subscriber_count=int(stats.get("subscriberCount", 0) or 0),
                        view_count=current_view_count,
                        video_count=int(stats.get("videoCount", 0) or 0),
                        captured_at=now,
                    )
                    recent_video_rows = _load_recent_video_rows(row.account_tag)
                    video_ids = [
                        str(video_row.get("video_id") or "").strip()
                        for video_row in recent_video_rows
                        if video_row.get("video_id")
                    ]
                    account_video_snapshots = []
                    if video_ids:
                        videos_resp = youtube.videos().list(
                            part="snippet,statistics",
                            id=",".join(video_ids),
                        ).execute() or {}
                        videos_by_id = {
                            item.get("id"): item
                            for item in (videos_resp.get("items") or [])
                            if item.get("id")
                        }
                        for position, video_row in enumerate(recent_video_rows, start=1):
                            video_id = str(video_row.get("video_id") or "").strip()
                            if not video_id:
                                continue
                            item = videos_by_id.get(video_id, {})
                            stats = item.get("statistics", {}) or {}
                            snippet = item.get("snippet", {}) or {}
                            thumbs = snippet.get("thumbnails", {}) or {}
                            published_at = _parse_published_at(
                                snippet.get("publishedAt") or video_row.get("publish_date")
                            )
                            account_video_snapshots.append(
                                VideoLiveCounterSnapshot(
                                    user_id=row.user_id,
                                    account_tag=row.account_tag,
                                    channel_id=channel_id,
                                    channel_name=channel_name,
                                    video_id=video_id,
                                    title=snippet.get("title") or video_row.get("title") or video_id,
                                    thumbnail=(
                                        (thumbs.get("medium") or {}).get("url")
                                        or (thumbs.get("default") or {}).get("url")
                                        or video_row.get("thumbnail")
                                        or ""
                                    ),
                                    published_at=published_at,
                                    position=position,
                                    view_count=int(stats.get("viewCount", 0) or 0),
                                    like_count=int(stats.get("likeCount", 0) or 0),
                                    comment_count=int(stats.get("commentCount", 0) or 0),
                                    captured_at=now,
                                    )
                                )
                    channel_snapshots.append(channel_snapshot)
                    latest_video_snapshots[(row.user_id, row.account_tag)] = account_video_snapshots
                    handled = True
                    processed_accounts += 1
                    break
                except HttpError as e:
                    last_error = e
                    if _is_quota_exceeded(e):
                        continue
                    raise
            if not handled and last_error is not None:
                raise last_error
        except Exception as e:
            failed_accounts += 1
            print(
                f"[WARN] live counter snapshot failed for {row.account_tag}: {e}"
            )

    if channel_snapshots:
        db.add_all(channel_snapshots)
    for (user_id, account_tag), snapshots in latest_video_snapshots.items():
        db.query(VideoLiveCounterSnapshot).filter(
            VideoLiveCounterSnapshot.user_id == user_id,
            VideoLiveCounterSnapshot.account_tag == account_tag,
        ).delete(synchronize_session=False)
        if snapshots:
            db.add_all(snapshots)
    if channel_snapshots or latest_video_snapshots:
        db.commit()

    if _LIVE_COUNTER_RETENTION_DAYS > 0:
        cutoff = now - timedelta(days=_LIVE_COUNTER_RETENTION_DAYS)
        db.query(LiveCounterSnapshot).filter(
            LiveCounterSnapshot.captured_at < cutoff
        ).delete(synchronize_session=False)
        db.query(VideoLiveCounterSnapshot).filter(
            VideoLiveCounterSnapshot.captured_at < cutoff
        ).delete(synchronize_session=False)
        db.commit()

    print(
        "[INFO] live counter snapshot finished: "
        f"processed={processed_accounts}, failed={failed_accounts}, "
        f"saved_channel={len(channel_snapshots)}, saved_video_groups={len(latest_video_snapshots)}"
    )


def _load_recent_video_rows(account_tag: str, limit: int = 3):
    if not account_tag or limit <= 0:
        return []
    try:
        with analytics_engine.begin() as conn:
            rs = conn.execute(
                text(
                    """
                    SELECT video_id, title, thumbnail, publish_date
                    FROM video_overview
                    WHERE account_tag = :tag
                      AND video_id IS NOT NULL
                      AND video_id != ''
                    ORDER BY publish_date DESC
                    LIMIT :limit
                    """
                ),
                {"tag": account_tag, "limit": limit},
            )
            return rs.mappings().all()
    except Exception as e:
        print(f"[WARN] recent video lookup failed for {account_tag}: {e}")
        return []


def _parse_published_at(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text_value = str(value).strip()
    if not text_value:
        return None
    for candidate in (
        text_value,
        text_value.replace("Z", "+00:00"),
        f"{text_value}T00:00:00",
    ):
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
        except ValueError:
            continue
    return None


def _run_loop():
    from python_backend.routes.smmstore import process_due_smmstore_orders

    while not _STOP_EVENT.is_set():
        now = datetime.now()
        db = SessionLocal()
        try:
            rows = db.query(UserSchedule).all()
            for row in rows:
                if not _should_run(row, now):
                    continue
                token_base = os.path.splitext(os.path.basename(row.token_name or ""))[0]
                if token_base:
                    token_path = os.path.join("python_backend", "token", f"{token_base}.pickle")
                    if not os.path.exists(token_path):
                        continue
                row.last_run_at = now
                row.updated_at = now
                db.add(row)
                db.commit()

                run = UserScheduleRun(
                    user_id=row.user_id,
                    schedule_id=row.id,
                    token_name=row.token_name,
                    token_names=json.dumps([row.token_name]) if row.token_name else None,
                    run_type="scheduled",
                    status="queued",
                    started_at=now,
                    processed=0,
                    total=0,
                    message="Queued by scheduler",
                )
                db.add(run)
                db.commit()
                db.refresh(run)
                if _RUNS_MAX > 0:
                    cutoff = (
                        db.query(UserScheduleRun.id)
                        .order_by(UserScheduleRun.id.desc())
                        .offset(_RUNS_MAX)
                        .all()
                    )
                    if cutoff:
                        ids = [r[0] for r in cutoff]
                        db.query(UserScheduleRun).filter(UserScheduleRun.id.in_(ids)).delete(
                            synchronize_session=False
                        )
                        db.commit()
                _kickoff_get_data(
                    token_base or None,
                    env_extra={"SCHEDULE_RUN_ID": str(run.id)},
                )
            snapshot_now = _now_saigon_naive()
            if _should_capture_live_counters(snapshot_now):
                _capture_live_counter_snapshots(db, snapshot_now)
        except Exception as e:
            print(f"[WARN] scheduler loop failed: {e}")
        finally:
            db.close()

        try:
            process_due_smmstore_orders()
        except Exception as e:
            print(f"[WARN] smmstore scheduler failed: {e}")

        _STOP_EVENT.wait(30)


def start_scheduler():
    global _THREAD
    if _THREAD and _THREAD.is_alive():
        return
    _THREAD = Thread(target=_run_loop, daemon=True)
    _THREAD.start()


def stop_scheduler():
    _STOP_EVENT.set()
