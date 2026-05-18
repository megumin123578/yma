import os
import json
import subprocess
import sys
from datetime import datetime, time as dtime, timedelta, timezone
from typing import Optional
from threading import Event, Thread

from sqlalchemy import or_, text, func, tuple_

from python_backend.api.auth.database import SessionLocal
from python_backend.api.auth.models import (
    LiveCounterSnapshot,
    MailAccount,
    TokenProgress,
    VideoLiveCounterSnapshot,
    UserCredential,
    UserSchedule,
    UserScheduleRun,
)
from python_backend.db import engine as analytics_engine
from python_backend.mail_gmail_api import sync_mail_account
from python_backend.progress_state import write_progress
from python_backend.token_store import (
    TokenCredentialsError,
    TokenRefreshFailed,
    account_tag_from_token_name,
    delete_token_credentials,
    list_token_names,
    load_token_credentials as load_stored_token_credentials,
    token_exists,
)
from python_backend.api.auth.models import UserHiddenChannel


_STOP_EVENT = Event()
_THREAD = None


def _env_int(name: str, default: int, minimum: Optional[int] = None) -> int:
    raw = str(os.getenv(name, str(default)) or "").strip()
    try:
        value = int(raw)
    except Exception:
        value = int(default)
    if minimum is not None:
        value = max(value, minimum)
    return value


_RUNS_MAX = int(os.getenv("SCHEDULE_RUNS_MAX", "200"))


def _live_counter_settings() -> dict:
    from python_backend.api.auth.routers.user.scheduler import load_live_counter_setting

    return load_live_counter_setting()


def _cron_schedule_settings() -> dict:
    from python_backend.api.auth.routers.user.scheduler import load_cron_schedule_setting

    return load_cron_schedule_setting()
_TOKEN_PROGRESS_RETENTION_DAYS = int(os.getenv("TOKEN_PROGRESS_RETENTION_DAYS", "10"))
_MAIL_AUTO_SYNC_ENABLED = str(os.getenv("MAIL_AUTO_SYNC_ENABLED", "1")).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_MAIL_AUTO_SYNC_INTERVAL_SECONDS = _env_int(
    "MAIL_AUTO_SYNC_INTERVAL_SECONDS",
    60,
    minimum=1,
)
_MAIL_AUTO_SYNC_FETCH_LIMIT = _env_int(
    "MAIL_AUTO_SYNC_FETCH_LIMIT",
    50,
    minimum=1,
)
_LAST_LIVE_COUNTER_SNAPSHOT_AT = None
_LAST_TOKEN_PROGRESS_CLEANUP_AT = None
SAIGON_TZ = timezone(timedelta(hours=7))
def _now_saigon_naive() -> datetime:
    return datetime.now(SAIGON_TZ).replace(tzinfo=None)


def _utc_naive_to_saigon_naive(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return (
        value.replace(tzinfo=timezone.utc).astimezone(SAIGON_TZ).replace(tzinfo=None)
    )


def _kickoff_get_data(account_tag: Optional[str], env_extra: Optional[dict] = None) -> None:
    script_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "get_data.py")
    )
    if not os.path.exists(script_path):
        script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "python_backend", "get_data.py")
        )
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
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


def _list_schedulable_token_names() -> list[str]:
    return list_token_names()


def _resolve_schedule_token_names(schedule: UserSchedule) -> list[str]:
    token_name = (schedule.token_name or "").strip()
    if token_name:
        return [token_name] if token_exists(token_name) else []
    return _list_schedulable_token_names()


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


def _should_run(schedule: UserSchedule, now_saigon: datetime) -> bool:
    if schedule.enabled != 1:
        return False

    last = _utc_naive_to_saigon_naive(schedule.last_run_at)
    tod = _parse_time_of_day(schedule.time_of_day or "")
    if tod is None:
        return False
    today_at = datetime.combine(now_saigon.date(), tod)
    if now_saigon < today_at:
        return False
    if last is None:
        created_at = _utc_naive_to_saigon_naive(schedule.created_at) or now_saigon
        if created_at >= today_at:
            return False
        return True
    return last.date() < now_saigon.date()


def _should_capture_live_counters(now: datetime) -> bool:
    global _LAST_LIVE_COUNTER_SNAPSHOT_AT
    settings = _live_counter_settings()
    if not settings.get("enabled"):
        return False
    interval = int(settings.get("interval_seconds") or 0)
    if interval <= 0:
        return False
    if _LAST_LIVE_COUNTER_SNAPSHOT_AT is None:
        _LAST_LIVE_COUNTER_SNAPSHOT_AT = now
        return True
    elapsed = (now - _LAST_LIVE_COUNTER_SNAPSHOT_AT).total_seconds()
    if elapsed < interval:
        return False
    _LAST_LIVE_COUNTER_SNAPSHOT_AT = now
    return True


def _should_cleanup_token_progress(now: datetime) -> bool:
    global _LAST_TOKEN_PROGRESS_CLEANUP_AT
    if _TOKEN_PROGRESS_RETENTION_DAYS <= 0:
        return False
    if _LAST_TOKEN_PROGRESS_CLEANUP_AT is None:
        _LAST_TOKEN_PROGRESS_CLEANUP_AT = now
        return True
    elapsed = (now - _LAST_TOKEN_PROGRESS_CLEANUP_AT).total_seconds()
    if elapsed < 24 * 60 * 60:
        return False
    _LAST_TOKEN_PROGRESS_CLEANUP_AT = now
    return True


def _cleanup_token_progress(db, now: datetime) -> None:
    if _TOKEN_PROGRESS_RETENTION_DAYS <= 0:
        return
    cutoff = now - timedelta(days=_TOKEN_PROGRESS_RETENTION_DAYS)
    (
        db.query(TokenProgress)
        .filter(TokenProgress.updated_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()


def _sync_due_mail_accounts(db, now_utc: datetime) -> None:
    if not _MAIL_AUTO_SYNC_ENABLED or _MAIL_AUTO_SYNC_INTERVAL_SECONDS <= 0:
        return

    cutoff = now_utc - timedelta(seconds=_MAIL_AUTO_SYNC_INTERVAL_SECONDS)
    rows = (
        db.query(MailAccount)
        .filter(MailAccount.enabled.is_(True))
        .filter(
            or_(
                MailAccount.last_synced_at.is_(None),
                MailAccount.last_synced_at <= cutoff,
            )
        )
        .order_by(MailAccount.account_email.asc())
        .all()
    )
    if not rows:
        return

    print(
        f"[INFO] auto-syncing {len(rows)} Gmail account(s) "
        f"every {_MAIL_AUTO_SYNC_INTERVAL_SECONDS}s"
    )
    for row in rows:
        try:
            sync_mail_account(db, row, fetch_limit=_MAIL_AUTO_SYNC_FETCH_LIMIT)
        except Exception as exc:
            print(f"[WARN] mail auto-sync failed for {row.account_email}: {exc}")


def _load_scheduler_token_credentials(token_name: str):
    token_base = os.path.basename(token_name or "").strip()
    if not token_base:
        raise ValueError("Missing token name")
    try:
        return load_stored_token_credentials(token_base)
    except FileNotFoundError:
        raise FileNotFoundError(f"Token file not found: {token_base}")
    except TokenRefreshFailed:
        raise
    except TokenCredentialsError:
        raise
    except ValueError:
        raise TokenCredentialsError(f"Token is not valid: {token_base}")


def _cleanup_missing_token_credentials(db) -> int:
    rows = (
        db.query(UserCredential.id, UserCredential.token_name)
        .filter(UserCredential.token_name.isnot(None))
        .all()
    )
    stale_ids = []
    for row_id, token_name in rows:
        token_base = os.path.basename(token_name or "").strip()
        if not token_base:
            stale_ids.append(row_id)
            continue
        if not token_exists(token_base):
            stale_ids.append(row_id)
    if not stale_ids:
        return 0
    (
        db.query(UserCredential)
        .filter(UserCredential.id.in_(stale_ids))
        .delete(synchronize_session=False)
    )
    db.commit()
    return len(stale_ids)


def _is_youtube_signup_required_error(exc: Exception) -> bool:
    try:
        from googleapiclient.errors import HttpError
    except Exception:
        return False
    if not isinstance(exc, HttpError):
        return False
    status = getattr(getattr(exc, "resp", None), "status", None)
    if status != 401:
        return False
    text = str(exc).lower()
    return "youtubesignuprequired" in text or "youtube signup required" in text


def _purge_dead_token(db, token_name: str, account_tag: str, reason: str) -> None:
    base = (token_name or "").strip()
    tag = (account_tag or "").strip()
    if not base and not tag:
        return
    candidates = {value for value in (base, tag, account_tag_from_token_name(base)) if value}
    try:
        if base:
            delete_token_credentials(base)
    except Exception as e:
        print(f"[WARN] purge dead token {base}: delete_token_credentials failed: {e}")
    if candidates:
        db.query(UserCredential).filter(
            UserCredential.token_name.in_(candidates)
        ).delete(synchronize_session=False)
        db.query(UserHiddenChannel).filter(
            UserHiddenChannel.account_tag.in_(candidates)
        ).delete(synchronize_session=False)
        db.query(LiveCounterSnapshot).filter(
            LiveCounterSnapshot.account_tag.in_(candidates)
        ).delete(synchronize_session=False)
        db.query(VideoLiveCounterSnapshot).filter(
            VideoLiveCounterSnapshot.account_tag.in_(candidates)
        ).delete(synchronize_session=False)
        db.commit()
    print(f"[INFO] purged dead token {base or tag}: {reason}")


def _cleanup_orphan_live_counter_snapshots(db) -> None:
    live_tokens = set(list_token_names())
    if not live_tokens:
        deleted_channel = db.query(LiveCounterSnapshot).delete(synchronize_session=False)
        deleted_video = db.query(VideoLiveCounterSnapshot).delete(synchronize_session=False)
        if deleted_channel or deleted_video:
            db.commit()
            print(
                f"[INFO] live counter snapshot orphan cleanup: "
                f"channel={deleted_channel} video={deleted_video} (no live tokens)"
            )
        return

    deleted_channel = (
        db.query(LiveCounterSnapshot)
        .filter(LiveCounterSnapshot.account_tag.notin_(live_tokens))
        .delete(synchronize_session=False)
    )
    deleted_video = (
        db.query(VideoLiveCounterSnapshot)
        .filter(VideoLiveCounterSnapshot.account_tag.notin_(live_tokens))
        .delete(synchronize_session=False)
    )
    if deleted_channel or deleted_video:
        db.commit()
        print(
            f"[INFO] live counter snapshot orphan cleanup: "
            f"channel={deleted_channel} video={deleted_video}"
        )


def _resolve_live_counter_credentials(db) -> list[UserCredential]:
    token_names = _list_schedulable_token_names()
    if not token_names:
        return []
    rows = (
        db.query(UserCredential)
        .filter(UserCredential.token_name.in_(token_names))
        .filter(UserCredential.selected_channel_id.isnot(None))
        .order_by(UserCredential.updated_at.desc(), UserCredential.id.desc())
        .all()
    )
    resolved_rows = []
    seen_channel_ids = set()
    for row in rows:
        token_name = os.path.basename(row.token_name or "").strip()
        channel_id = (row.selected_channel_id or "").strip()
        if not token_name or not channel_id:
            continue
        if channel_id in seen_channel_ids:
            continue
        seen_channel_ids.add(channel_id)
        resolved_rows.append(row)
    return resolved_rows


def _capture_live_counter_snapshots(db, now: datetime) -> None:
    from googleapiclient.discovery import build

    deleted_credentials = _cleanup_missing_token_credentials(db)
    if deleted_credentials:
        print(
            f"[INFO] live counter snapshot cleanup: removed_missing_token_credentials={deleted_credentials}"
        )

    _cleanup_orphan_live_counter_snapshots(db)

    rows = _resolve_live_counter_credentials(db)
    if not rows:
        print("[INFO] live counter snapshot skipped: no eligible accounts")
        return

    print(f"[INFO] live counter snapshot started: accounts={len(rows)}")

    row_data = [
        {
            "user_id": r.user_id,
            "account_tag": r.account_tag,
            "token_name": r.token_name,
            "selected_channel_id": r.selected_channel_id,
            "selected_channel_title": r.selected_channel_title,
        }
        for r in rows
    ]

    pairs = list({(d["user_id"], d["account_tag"]) for d in row_data})
    latest_view_counts: dict[tuple, int] = {}
    if pairs:
        max_rows = (
            db.query(
                LiveCounterSnapshot.user_id,
                LiveCounterSnapshot.account_tag,
                func.max(LiveCounterSnapshot.view_count),
            )
            .filter(
                tuple_(LiveCounterSnapshot.user_id, LiveCounterSnapshot.account_tag).in_(pairs)
            )
            .group_by(LiveCounterSnapshot.user_id, LiveCounterSnapshot.account_tag)
            .all()
        )
        for uid, tag, mv in max_rows:
            latest_view_counts[(uid, tag)] = int(mv or 0)

    db.rollback()

    channel_snapshots = []
    latest_video_snapshots = {}
    pending_purges: list[tuple[str, str, str]] = []
    processed_accounts = 0
    failed_accounts = 0
    for data in row_data:
        token_name = os.path.basename(data["token_name"] or "").strip()
        if not token_name:
            continue
        if not (data["selected_channel_id"] or "").strip():
            continue
        try:
            creds = _load_scheduler_token_credentials(token_name)
            youtube = build("youtube", "v3", credentials=creds)
            query = {"part": "snippet,statistics", "id": data["selected_channel_id"]}
            resp = youtube.channels().list(**query).execute() or {}
            items = resp.get("items") or []
            if not items:
                processed_accounts += 1
                continue
            channel_snippet = items[0].get("snippet", {}) or {}
            stats = (items[0].get("statistics") or {})
            channel_id = data["selected_channel_id"] or items[0].get("id") or None
            channel_name = (
                channel_snippet.get("title")
                or data["selected_channel_title"]
                or data["account_tag"]
            )
            current_view_count = int(stats.get("viewCount", 0) or 0)
            prev = latest_view_counts.get((data["user_id"], data["account_tag"]))
            if prev is not None:
                current_view_count = max(current_view_count, prev)
            channel_snapshot = LiveCounterSnapshot(
                user_id=data["user_id"],
                account_tag=data["account_tag"],
                channel_id=channel_id,
                subscriber_count=int(stats.get("subscriberCount", 0) or 0),
                view_count=current_view_count,
                video_count=int(stats.get("videoCount", 0) or 0),
                captured_at=now,
            )
            recent_video_rows = _load_recent_video_rows(data["account_tag"])
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
                            user_id=data["user_id"],
                            account_tag=data["account_tag"],
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
            latest_video_snapshots[(data["user_id"], data["account_tag"])] = account_video_snapshots
            processed_accounts += 1
        except Exception as e:
            failed_accounts += 1
            permanent = (
                isinstance(e, (TokenCredentialsError, TokenRefreshFailed, FileNotFoundError))
                or _is_youtube_signup_required_error(e)
            )
            if permanent:
                pending_purges.append((token_name, data["account_tag"], str(e)))
            else:
                print(
                    f"[WARN] live counter snapshot failed for {data['account_tag']}: {e}"
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

    for token_name, account_tag, reason in pending_purges:
        try:
            _purge_dead_token(db, token_name, account_tag, reason=reason)
        except Exception as purge_exc:
            print(
                f"[WARN] purge dead token failed for {account_tag}: {purge_exc}"
            )

    retention_days = int(_live_counter_settings().get("retention_days") or 0)
    if retention_days > 0:
        cutoff = now - timedelta(days=retention_days)
        db.query(LiveCounterSnapshot).filter(
            LiveCounterSnapshot.captured_at < cutoff
        ).delete(synchronize_session=False)
        db.query(VideoLiveCounterSnapshot).filter(
            VideoLiveCounterSnapshot.captured_at < cutoff
        ).delete(synchronize_session=False)
        db.commit()

    total_channel_views = sum(int(snapshot.view_count or 0) for snapshot in channel_snapshots)
    total_video_views = sum(
        int(snapshot.view_count or 0)
        for snapshots in latest_video_snapshots.values()
        for snapshot in snapshots
    )
    print(
        "[INFO] live counter snapshot finished: "
        f"processed={processed_accounts}, failed={failed_accounts}, "
        f"saved_channel={len(channel_snapshots)}, saved_video_groups={len(latest_video_snapshots)}, "
        f"channel_views={total_channel_views}, video_views={total_video_views}"
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
        now_utc = datetime.utcnow()
        now_saigon = _now_saigon_naive()
        db = SessionLocal()
        try:
            _sync_due_mail_accounts(db, now_utc)
            cron_enabled = bool(_cron_schedule_settings().get("enabled", True))
            rows = db.query(UserSchedule).all() if cron_enabled else []
            for row in rows:
                if not _should_run(row, now_saigon):
                    continue
                token_names = _resolve_schedule_token_names(row)
                if not token_names:
                    continue
                row.last_run_at = now_utc
                row.updated_at = now_utc
                db.add(row)
                db.commit()

                run = UserScheduleRun(
                    user_id=row.user_id,
                    schedule_id=row.id,
                    token_name=token_names[0] if len(token_names) == 1 else None,
                    token_names=json.dumps(token_names),
                    run_type="scheduled",
                    status="queued",
                    started_at=now_utc,
                    processed=0,
                    total=len(token_names),
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
                for token_name in token_names:
                    account_tag = account_tag_from_token_name(token_name)
                    try:
                        write_progress(account_tag, "queued", 0, "queued", "Queued by scheduler")
                    except Exception as e:
                        print(f"[WARN] failed to write schedule progress for {account_tag}: {e}")
                _kickoff_get_data(
                    account_tag_from_token_name(token_names[0]) if len(token_names) == 1 else None,
                    env_extra={
                        "SCHEDULE_RUN_ID": str(run.id),
                        "RUN_TOKEN_NAMES": json.dumps(token_names),
                    },
                )
            if _should_capture_live_counters(now_saigon):
                _capture_live_counter_snapshots(db, now_saigon)
            if _should_cleanup_token_progress(now_saigon):
                _cleanup_token_progress(db, now_saigon)
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
    _STOP_EVENT.clear()
    _THREAD = Thread(target=_run_loop, daemon=True)
    _THREAD.start()


def stop_scheduler():
    global _THREAD
    _STOP_EVENT.set()
    if _THREAD and _THREAD.is_alive():
        _THREAD.join(timeout=5)
    _THREAD = None
