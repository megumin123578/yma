import os
import re
from datetime import datetime, timedelta
from html import unescape
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user, get_current_user_optional
from python_backend.api.auth.database import get_db, SessionLocal
from python_backend.api.auth.models import MailAccount, MailOAuthState, User
from python_backend.sse_utils import poll_stream, sse_response
from python_backend.mail_gmail_api import (
    MAIL_OAUTH_TTL_MINUTES,
    build_mail_oauth_flow,
    delete_mail_account_integration,
    deserialize_mail_label_ids,
    fetch_gmail_profile,
    mail_oauth_success_html,
    normalize_mail_label_ids,
    serialize_mail_label_ids,
    sync_all_mail_accounts,
    sync_mail_account,
    upsert_mail_account,
)
from python_backend.module_mail import (
    build_telegram_match_alert_payload,
    get_mail_message_detail,
    get_mail_overview,
    list_mail_messages,
    list_mail_runs,
    send_test_telegram_notification,
)


router = APIRouter(prefix="/api/mail", tags=["mail"])
_ADMIN_ENV_KEY = "ADMIN_USERNAME"


class MailAccountOAuthStartRequest(BaseModel):
    label_ids: list[str] = Field(default_factory=lambda: ["INBOX"])


class MailAccountUpdateRequest(BaseModel):
    label_ids: Optional[list[str]] = None
    enabled: Optional[bool] = None
    channel_name: Optional[str] = None


def _get_admin_users() -> set[str]:
    raw = os.getenv(_ADMIN_ENV_KEY, "admin")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _get_admin_usernames_in_order() -> list[str]:
    raw = os.getenv(_ADMIN_ENV_KEY, "admin")
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def _is_admin_user(current_user) -> bool:
    return bool(getattr(current_user, "is_admin", False))


def _require_mail_admin_user(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from python_backend.api.auth.permissions import user_has_permission

    if user_has_permission(db, current_user, "manage_mail"):
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required.",
    )


def _get_mail_admin_user_optional(current_user=Depends(get_current_user_optional)):
    if _is_admin_user(current_user):
        return current_user
    return None


def _resolve_mail_owner_user(db: Session, current_user: User | None) -> User:
    if current_user:
        return current_user

    for username in _get_admin_usernames_in_order():
        owner = db.query(User).filter(User.username.ilike(username)).first()
        if owner:
            return owner

    owner = db.query(User).filter(User.is_admin.is_(True)).order_by(User.id.asc()).first()
    if owner:
        return owner

    raise HTTPException(status_code=503, detail="No admin user configured for public Gmail OAuth.")


def _list_mail_account_emails_for_user(
    db: Session, user_id: int, *, all_users: bool = False
) -> list[str]:
    query = db.query(MailAccount.account_email)
    if not all_users:
        query = query.filter(MailAccount.user_id == user_id)
    rows = query.order_by(MailAccount.account_email.asc()).all()
    return [str(row[0] or "").strip().lower() for row in rows if str(row[0] or "").strip()]


def _resolve_mail_oauth_redirect_url(request: Request) -> str:
    configured = os.getenv("MAIL_OAUTH_REDIRECT_URL", "").strip()
    if configured:
        return configured
    shared_google_redirect = os.getenv("OAUTH_REDIRECT_URL", "").strip()
    if shared_google_redirect:
        return shared_google_redirect
    return f"{str(request.base_url).rstrip('/')}/api/mail/accounts/oauth/callback"


def _mark_mail_oauth_state_failed(db: Session, row: MailOAuthState, message: str) -> None:
    row.status = "failed"
    row.error_message = message
    row.completed_at = datetime.utcnow()
    db.add(row)
    db.commit()


def _serialize_mail_account(row: MailAccount) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "account_email": row.account_email,
        "channel_name": row.channel_name,
        "provider": row.provider,
        "token_name": row.token_name,
        "label_ids": deserialize_mail_label_ids(row.label_ids_json),
        "history_id": row.history_id,
        "enabled": bool(row.enabled),
        "last_sync_status": row.last_sync_status,
        "last_error_message": row.last_error_message,
        "last_synced_at": row.last_synced_at.isoformat() if row.last_synced_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _mail_oauth_state_response(row: MailOAuthState) -> dict[str, Any]:
    return {
        "ready": row.status == "completed",
        "status": row.status,
        "account_email": row.account_email,
        "error_message": row.error_message,
    }


@router.get("/accounts")
def list_mail_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(MailAccount)
    if not _is_admin_user(current_user):
        query = query.filter(MailAccount.user_id == current_user.id)
    rows = query.order_by(MailAccount.account_email.asc()).all()
    return {"items": [_serialize_mail_account(row) for row in rows]}


@router.post("/accounts/oauth/start")
def start_mail_oauth(
    payload: MailAccountOAuthStartRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    owner_user = _resolve_mail_owner_user(db, current_user)
    flow = build_mail_oauth_flow(_resolve_mail_oauth_redirect_url(request))
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="false",
    )

    now = datetime.utcnow()
    db.add(
        MailOAuthState(
            state=state,
            user_id=owner_user.id,
            status="pending",
            label_ids_json=serialize_mail_label_ids(payload.label_ids),
            created_at=now,
            expires_at=now + timedelta(minutes=MAIL_OAUTH_TTL_MINUTES),
        )
    )
    db.commit()
    return {"auth_url": auth_url, "state": state}


@router.get("/accounts/oauth/callback", response_class=HTMLResponse)
def complete_mail_oauth(
    request: Request,
    state: str = "",
    code: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    row = db.query(MailOAuthState).filter(MailOAuthState.state == state).first()
    if error:
        if row:
            _mark_mail_oauth_state_failed(db, row, f"Authorization failed: {error}")
        raise HTTPException(status_code=400, detail=f"Authorization failed: {error}")

    if not row:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    now = datetime.utcnow()
    if row.expires_at and row.expires_at < now:
        row.status = "expired"
        row.completed_at = now
        db.add(row)
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    if row.status == "completed":
        return mail_oauth_success_html()
    if row.status == "failed":
        raise HTTPException(status_code=400, detail=row.error_message or "OAuth flow failed")

    flow = build_mail_oauth_flow(_resolve_mail_oauth_redirect_url(request))
    try:
        flow.fetch_token(code=code)
    except Exception as exc:
        _mark_mail_oauth_state_failed(db, row, f"Failed to fetch token: {exc}")
        raise HTTPException(status_code=400, detail=f"Failed to fetch token: {exc}")

    try:
        profile = fetch_gmail_profile(flow.credentials)
        account = upsert_mail_account(
            db,
            user_id=row.user_id,
            account_email=profile["email"],
            creds=flow.credentials,
            label_ids=deserialize_mail_label_ids(row.label_ids_json),
        )
        row.status = "completed"
        row.account_email = account.account_email
        row.token_name = account.token_name
        row.error_message = None
        row.completed_at = datetime.utcnow()
        row.consumed_at = row.consumed_at or now
        db.add(row)
        db.commit()

        try:
            sync_mail_account(db, account)
        except Exception as sync_exc:
            row.error_message = str(sync_exc)
            db.add(row)
            db.commit()
    except Exception as exc:
        _mark_mail_oauth_state_failed(db, row, str(exc))
        raise HTTPException(status_code=400, detail=str(exc))

    return mail_oauth_success_html()


@router.get("/accounts/oauth/state/{state}")
def get_mail_oauth_state(
    state: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(MailOAuthState).filter(MailOAuthState.state == state).first()
    if not row:
        return {"ready": False}
    if row.user_id != getattr(current_user, "id", None) and not _is_admin_user(current_user):
        return {"ready": False}
    if row.expires_at and row.expires_at < datetime.utcnow() and row.status == "pending":
        row.status = "expired"
        row.completed_at = datetime.utcnow()
        db.add(row)
        db.commit()
        return {"ready": False}
    return _mail_oauth_state_response(row)


def _fetch_mail_oauth_state_snapshot(state: str, user_id: int, is_admin: bool) -> dict:
    db = SessionLocal()
    try:
        row = db.query(MailOAuthState).filter(MailOAuthState.state == state).first()
        if not row:
            return {"ready": False, "status": "missing"}
        if row.user_id != user_id and not is_admin:
            return {"ready": False, "status": "missing"}
        if row.expires_at and row.expires_at < datetime.utcnow() and row.status == "pending":
            row.status = "expired"
            row.completed_at = datetime.utcnow()
            db.add(row)
            db.commit()
            return {"ready": False, "status": "expired"}
        return _mail_oauth_state_response(row)
    finally:
        db.close()


@router.get("/accounts/oauth/state/{state}/stream")
async def stream_mail_oauth_state(
    state: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    user_id = getattr(current_user, "id", None)
    is_admin = _is_admin_user(current_user)

    def is_terminal(snap: dict) -> bool:
        return snap.get("status") in ("completed", "expired", "failed", "missing")

    return sse_response(
        poll_stream(
            request,
            lambda: _fetch_mail_oauth_state_snapshot(state, user_id, is_admin),
            interval_seconds=2.0,
            heartbeat_seconds=20.0,
            is_terminal=is_terminal,
        )
    )


@router.patch("/accounts/{account_id}")
def update_mail_account(
    account_id: int,
    payload: MailAccountUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(MailAccount).filter(MailAccount.id == account_id)
    if not _is_admin_user(current_user):
        query = query.filter(MailAccount.user_id == current_user.id)
    row = query.first()
    if not row:
        raise HTTPException(status_code=404, detail="Mail account not found.")

    payload_data = payload.dict(exclude_unset=True)

    if "label_ids" in payload_data:
        row.label_ids_json = serialize_mail_label_ids(payload.label_ids)
    if "enabled" in payload_data:
        row.enabled = bool(payload.enabled)
    if "channel_name" in payload_data:
        normalized_channel_name = str(payload.channel_name or "").strip()
        row.channel_name = normalized_channel_name or None
    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"account": _serialize_mail_account(row)}


@router.post("/accounts/{account_id}/sync")
def sync_one_mail_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(MailAccount).filter(MailAccount.id == account_id)
    if not _is_admin_user(current_user):
        query = query.filter(MailAccount.user_id == current_user.id)
    row = query.first()
    if not row:
        raise HTTPException(status_code=404, detail="Mail account not found.")

    try:
        return sync_mail_account(db, row)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/sync")
def sync_mail_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_id = None if _is_admin_user(current_user) else current_user.id
    return sync_all_mail_accounts(db, user_id=user_id)


@router.get("/overview")
def mail_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_mail_overview(
        account_emails=_list_mail_account_emails_for_user(
            db, current_user.id, all_users=_is_admin_user(current_user)
        )
    )


@router.get("/messages")
def mail_messages(
    account_email: Optional[str] = Query(default=None),
    mailbox: Optional[str] = Query(default=None),
    status_value: Optional[str] = Query(default=None, alias="status"),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    per_account_limit: Optional[int] = Query(default=None, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_mail_messages(
        account_email=account_email,
        account_emails=_list_mail_account_emails_for_user(
            db, current_user.id, all_users=_is_admin_user(current_user)
        ),
        mailbox=mailbox,
        status=status_value,
        search=search,
        limit=limit,
        offset=offset,
        per_account_limit=per_account_limit,
    )


def _fetch_mail_messages_snapshot(
    user_id: int,
    account_email: Optional[str],
    mailbox: Optional[str],
    status_value: Optional[str],
    search: Optional[str],
    limit: int,
    offset: int,
    per_account_limit: Optional[int],
    *,
    is_admin: bool = False,
) -> dict:
    db = SessionLocal()
    try:
        account_emails = _list_mail_account_emails_for_user(
            db, user_id, all_users=is_admin
        )
        return list_mail_messages(
            account_email=account_email,
            account_emails=account_emails,
            mailbox=mailbox,
            status=status_value,
            search=search,
            limit=limit,
            offset=offset,
            per_account_limit=per_account_limit,
        )
    finally:
        db.close()


@router.get("/messages/stream")
async def stream_mail_messages(
    request: Request,
    account_email: Optional[str] = Query(default=None),
    mailbox: Optional[str] = Query(default=None),
    status_value: Optional[str] = Query(default=None, alias="status"),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    per_account_limit: Optional[int] = Query(default=None, ge=1, le=500),
    current_user: User = Depends(get_current_user),
):
    user_id = getattr(current_user, "id", None)
    is_admin = _is_admin_user(current_user)

    return sse_response(
        poll_stream(
            request,
            lambda: _fetch_mail_messages_snapshot(
                user_id,
                account_email,
                mailbox,
                status_value,
                search,
                limit,
                offset,
                per_account_limit,
                is_admin=is_admin,
            ),
            interval_seconds=30.0,
            heartbeat_seconds=25.0,
        )
    )


@router.get("/messages/{message_id}")
def mail_message_detail(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = get_mail_message_detail(
        message_id,
        account_emails=_list_mail_account_emails_for_user(
            db, current_user.id, all_users=_is_admin_user(current_user)
        ),
    )
    if not item:
        raise HTTPException(status_code=404, detail="Message not found.")
    return item


@router.get("/runs")
def mail_runs(
    account_email: Optional[str] = Query(default=None),
    mailbox: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_mail_runs(
        account_email=account_email,
        account_emails=_list_mail_account_emails_for_user(
            db, current_user.id, all_users=_is_admin_user(current_user)
        ),
        mailbox=mailbox,
        limit=limit,
    )


@router.delete("/accounts/{account_id}")
def remove_mail_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(MailAccount).filter(MailAccount.id == account_id)
    if not _is_admin_user(current_user):
        query = query.filter(MailAccount.user_id == current_user.id)
    row = query.first()
    if not row:
        raise HTTPException(status_code=404, detail="Mail account not found.")
    delete_mail_account_integration(db, row)
    return {"ok": True, "account_id": account_id}


@router.post("/test-telegram")
def mail_test_telegram(
    _: object = Depends(_require_mail_admin_user),
):
    try:
        return send_test_telegram_notification()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Telegram send failed: {exc}")


@router.post("/test-log")
def mail_test_log(
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_mail_admin_user),
):
    mail_accounts = (
        db.query(MailAccount)
        .order_by(MailAccount.account_email.asc())
        .all()
    )
    account_emails = _list_mail_account_emails_for_user(
        db, current_user.id, all_users=True
    )
    latest_result = list_mail_messages(
        account_emails=account_emails,
        status="matched",
        limit=1,
    )
    latest_items = latest_result.get("items") or []
    latest_item = latest_items[0] if latest_items else None

    used_sample = False
    if latest_item:
        account_email = str(latest_item.get("account_email") or "").strip() or "-"
        account_row = next(
            (row for row in mail_accounts if str(row.account_email or "").strip().lower() == account_email.lower()),
            None,
        )
        channel_name = str(getattr(account_row, "channel_name", "") or "").strip() or None
        mailbox = str(latest_item.get("mailbox") or "").strip() or "INBOX"
        matched_result = list_mail_messages(
            account_email=account_email,
            account_emails=account_emails,
            mailbox=mailbox,
            status="matched",
            limit=5,
        )
        matched_messages = matched_result.get("items") or []
    else:
        used_sample = True
        sample_account = mail_accounts[0] if mail_accounts else None
        account_email = str(getattr(sample_account, "account_email", "") or "onechampvexhp@gmail.com").strip()
        channel_name = str(getattr(sample_account, "channel_name", "") or "").strip() or None
        mailbox = "INBOX"
        matched_messages = [
            {
                "from_name": "YouTube Shopping",
                "subject": "Earn a performance bonus from YouTube Shopping",
            }
        ]

    payload = build_telegram_match_alert_payload(
        account_email=account_email,
        channel_name=channel_name,
        mailbox=mailbox,
        matched_messages=matched_messages,
    )
    rendered_text = unescape(re.sub(r"</?[^>]+>", "", payload["text"]))
    print("[MAIL][TEST_LOG] BEGIN")
    print(rendered_text)
    print("[MAIL][TEST_LOG] END")
    return {
        "ok": True,
        "message": "Backend logged the exact Telegram alert preview.",
        "used_sample": used_sample,
    }
