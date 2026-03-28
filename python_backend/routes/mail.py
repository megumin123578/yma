import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from python_backend.api.auth.auth_utils import get_current_user
from python_backend.module_mail import (
    get_mail_overview,
    get_next_vps_id,
    list_mail_messages,
    list_mail_runs,
    save_mail_ingest,
)


router = APIRouter(prefix="/api/mail", tags=["mail"])
AGENT_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "main_agent.py"
AGENT_CONFIG_PATTERN = re.compile(r'(AGENT_CONFIG_JSON\s*=\s*r?""")\n(.*?)\n("""\s*)', re.DOTALL)


def _allowed_ingest_tokens() -> set[str]:
    raw = os.getenv("MAIL_INGEST_TOKENS", "").strip()
    if raw:
        return {token.strip() for token in raw.split(",") if token.strip()}
    single = os.getenv("MAIL_INGEST_TOKEN", "").strip()
    return {single} if single else set()


def _require_ingest_token(
    x_mail_ingest_token: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> None:
    allowed_tokens = _allowed_ingest_tokens()
    if not allowed_tokens:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MAIL_INGEST_TOKEN is not configured.",
        )

    candidate_tokens = []
    if x_mail_ingest_token:
        candidate_tokens.append(x_mail_ingest_token.strip())
    if authorization and authorization.lower().startswith("bearer "):
        candidate_tokens.append(authorization.split(" ", 1)[1].strip())

    if any(token in allowed_tokens for token in candidate_tokens if token):
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid ingest token.",
    )


class MailMessageIn(BaseModel):
    provider_message_id: Optional[str] = None
    uid: Optional[int] = None
    thread_id: Optional[str] = None
    subject: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    to_email: Optional[str] = None
    received_at: Optional[datetime] = None
    seen: bool = False
    status: Optional[str] = "received"
    matched_rule: Optional[str] = None
    snippet: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)


class MailIngestRequest(BaseModel):
    vps_id: str
    mailbox: str = "INBOX"
    provider: str = "imap"
    agent_version: Optional[str] = None
    run_started_at: Optional[datetime] = None
    run_finished_at: Optional[datetime] = None
    status: str = "ok"
    error_message: Optional[str] = None
    cursor: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    messages: list[MailMessageIn] = Field(default_factory=list)


class MailAgentTemplateRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


def _render_agent_template(*, username: str, password: str) -> tuple[str, str]:
    try:
        template_source = AGENT_TEMPLATE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="Agent template file is missing.") from exc

    match = AGENT_CONFIG_PATTERN.search(template_source)
    if not match:
        raise HTTPException(status_code=500, detail="Cannot locate AGENT_CONFIG_JSON in template.")

    try:
        agent_config = json.loads(match.group(2))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Agent template JSON is invalid.") from exc

    if not isinstance(agent_config, dict):
        raise HTTPException(status_code=500, detail="Agent template JSON must be an object.")

    next_vps_id = get_next_vps_id()
    agent_config["MAIL_AGENT_VPS_ID"] = next_vps_id
    agent_config["MAIL_IMAP_USERNAME"] = username.strip()
    agent_config["MAIL_IMAP_PASSWORD"] = password

    rendered_config = json.dumps(agent_config, ensure_ascii=False, indent=2)
    rendered_source = (
        template_source[: match.start()]
        + f"{match.group(1)}\n{rendered_config}\n{match.group(3)}"
        + template_source[match.end() :]
    )
    return rendered_source, next_vps_id


@router.post("/ingest")
def ingest_mail(
    payload: MailIngestRequest,
    _: None = Depends(_require_ingest_token),
):
    try:
        return save_mail_ingest(payload.dict())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/agent-template")
def download_mail_agent_template(
    payload: MailAgentTemplateRequest,
    current_user=Depends(get_current_user),
):
    del current_user
    source, vps_id = _render_agent_template(
        username=payload.username,
        password=payload.password,
    )
    filename = f"main_agent_{vps_id}.py"
    return Response(
        content=source,
        media_type="text/x-python; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Agent-Vps-Id": vps_id,
        },
    )


@router.get("/overview")
def mail_overview(
    current_user=Depends(get_current_user),
):
    del current_user
    return get_mail_overview()


@router.get("/messages")
def mail_messages(
    vps_id: Optional[str] = Query(default=None),
    mailbox: Optional[str] = Query(default=None),
    status_value: Optional[str] = Query(default=None, alias="status"),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
):
    del current_user
    return list_mail_messages(
        vps_id=vps_id,
        mailbox=mailbox,
        status=status_value,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/runs")
def mail_runs(
    vps_id: Optional[str] = Query(default=None),
    mailbox: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current_user=Depends(get_current_user),
):
    del current_user
    return list_mail_runs(
        vps_id=vps_id,
        mailbox=mailbox,
        limit=limit,
    )
