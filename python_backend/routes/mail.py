import io
import json
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from python_backend.api.auth.auth_utils import get_current_user
from python_backend.module_mail import (
    get_mail_message_detail,
    get_mail_overview,
    list_mail_messages,
    list_mail_runs,
    save_mail_ingest,
)


router = APIRouter(prefix="/api/mail", tags=["mail"])
AGENT_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "main_agent.py"
AGENT_CONFIG_PATTERN = re.compile(r'(AGENT_CONFIG_JSON\s*=\s*r?""")\n(.*?)\n("""\s*)', re.DOTALL)
PYTHON_INSTALLER_URL = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
AGENT_REQUIREMENTS = "requests>=2.31.0,<3\n"


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
    vps_id: str = Field(min_length=1)
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


def _normalize_agent_vps_id(value: str) -> str:
    normalized = re.sub(r"\s+", " ", str(value or "").strip())
    if not normalized:
        raise HTTPException(status_code=400, detail="VPS name is required.")
    return normalized


def _safe_filename_fragment(value: str) -> str:
    fragment = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip())
    fragment = fragment.strip(".-_")
    return fragment or "mail-agent"


def _render_agent_template(*, vps_id: str, username: str, password: str) -> tuple[str, str]:
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

    normalized_vps_id = _normalize_agent_vps_id(vps_id)
    agent_config["MAIL_AGENT_VPS_ID"] = normalized_vps_id
    agent_config["MAIL_IMAP_USERNAME"] = username.strip()
    agent_config["MAIL_IMAP_PASSWORD"] = password

    rendered_config = json.dumps(agent_config, ensure_ascii=False, indent=2)
    rendered_source = (
        template_source[: match.start()]
        + f"{match.group(1)}\n{rendered_config}\n{match.group(3)}"
        + template_source[match.end() :]
    )
    return rendered_source, normalized_vps_id


def _build_agent_runner_script() -> str:
    return (
        "@echo off\n"
        "setlocal\n"
        'cd /d "%~dp0"\n'
        'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_and_run.ps1"\n'
        'set "EXIT_CODE=%ERRORLEVEL%"\n'
        'if not "%EXIT_CODE%"=="0" (\n'
        "  echo.\n"
        "  echo Mail agent failed with exit code %EXIT_CODE%.\n"
        "  pause\n"
        "  exit /b %EXIT_CODE%\n"
        ")\n"
        "echo.\n"
        "echo Mail agent finished.\n"
        "pause\n"
        "exit /b 0\n"
    )


def _build_agent_bootstrap_script() -> str:
    script = r"""$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Write-Step {
  param([string]$Message)
  Write-Host "[mail-agent] $Message" -ForegroundColor Cyan
}

function Test-PythonExecutable {
  param([string]$PythonPath)
  if (-not $PythonPath) {
    return $false
  }
  if (-not (Test-Path $PythonPath)) {
    return $false
  }
  try {
    & $PythonPath --version *> $null
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  }
}

function Resolve-PythonExecutable {
  param(
    [string]$PythonInstallDir
  )

  $localPython = Join-Path $PythonInstallDir "python.exe"
  if (Test-PythonExecutable $localPython) {
    return $localPython
  }

  $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonCommand -and (Test-PythonExecutable $pythonCommand.Source)) {
    return $pythonCommand.Source
  }

  $installerUrl = "__PYTHON_INSTALLER_URL__"
  $installerPath = Join-Path $env:TEMP "mail-agent-python-installer.exe"

  Write-Step "Downloading Python installer..."
  Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath

  New-Item -ItemType Directory -Force -Path $PythonInstallDir | Out-Null

  Write-Step "Installing Python locally..."
  $process = Start-Process -FilePath $installerPath -ArgumentList @(
    "/quiet",
    "InstallAllUsers=0",
    "Include_pip=1",
    "Include_test=0",
    "Include_launcher=0",
    "SimpleInstall=1",
    "Shortcuts=0",
    "TargetDir=$PythonInstallDir"
  ) -Wait -PassThru

  if ($process.ExitCode -ne 0) {
    throw "Python installer failed with exit code $($process.ExitCode)."
  }

  if (Test-PythonExecutable $localPython) {
    return $localPython
  }

  $fallback = Get-ChildItem -Path $PythonInstallDir -Recurse -Filter python.exe -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty FullName

  if (Test-PythonExecutable $fallback) {
    return $fallback
  }

  throw "Python installation completed but python.exe was not found."
}

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonInstallDir = Join-Path $rootDir ".python"
$venvDir = Join-Path $rootDir ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$requirementsFile = Join-Path $rootDir "requirements.txt"
$agentFile = Join-Path $rootDir "main_agent.py"

if (-not (Test-Path $agentFile)) {
  throw "main_agent.py was not found."
}
if (-not (Test-Path $requirementsFile)) {
  throw "requirements.txt was not found."
}

$pythonExe = Resolve-PythonExecutable -PythonInstallDir $pythonInstallDir

if (-not (Test-PythonExecutable $venvPython)) {
  Write-Step "Creating virtual environment..."
  & $pythonExe -m venv $venvDir
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to create virtual environment."
  }
}

if (-not (Test-PythonExecutable $venvPython)) {
  throw "Virtual environment python.exe was not created."
}

Write-Step "Upgrading pip..."
& $venvPython -m pip install --disable-pip-version-check --upgrade pip
if ($LASTEXITCODE -ne 0) {
  throw "Failed to upgrade pip."
}

Write-Step "Installing dependencies..."
& $venvPython -m pip install --disable-pip-version-check -r $requirementsFile
if ($LASTEXITCODE -ne 0) {
  throw "Failed to install dependencies."
}

Write-Step "Running mail agent..."
& $venvPython $agentFile
if ($LASTEXITCODE -ne 0) {
  throw "main_agent.py exited with code $LASTEXITCODE."
}

Write-Step "Mail agent completed."
"""
    return script.replace("__PYTHON_INSTALLER_URL__", PYTHON_INSTALLER_URL)


def _build_agent_bundle_readme(vps_id: str) -> str:
    return (
        f"Mail agent bundle for {vps_id}\n"
        "\n"
        "1. Extract this zip into its own folder.\n"
        "2. Double-click run_agent.bat.\n"
        "3. The bootstrap script will install Python locally if needed,\n"
        "   create .venv, install dependencies, and run main_agent.py once.\n"
        "\n"
        "Notes:\n"
        "- Internet access is required the first time if Python or dependencies are missing.\n"
        "- main_agent.py is still a one-shot sync. Run the batch file again to sync later.\n"
        "- For periodic sync, schedule run_agent.bat in Windows Task Scheduler.\n"
    )


def _build_agent_bundle(*, agent_source: str, vps_id: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("main_agent.py", agent_source)
        archive.writestr("requirements.txt", AGENT_REQUIREMENTS)
        archive.writestr("install_and_run.ps1", _build_agent_bootstrap_script())
        archive.writestr("run_agent.bat", _build_agent_runner_script())
        archive.writestr("README.txt", _build_agent_bundle_readme(vps_id))
    return buffer.getvalue()


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
        vps_id=payload.vps_id,
        username=payload.username,
        password=payload.password,
    )
    bundle = _build_agent_bundle(agent_source=source, vps_id=vps_id)
    filename = f"mail_agent_{_safe_filename_fragment(vps_id)}.zip"
    return Response(
        content=bundle,
        media_type="application/zip",
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


@router.get("/messages/{message_id}")
def mail_message_detail(
    message_id: int,
    current_user=Depends(get_current_user),
):
    del current_user
    item = get_mail_message_detail(message_id)
    if not item:
        raise HTTPException(status_code=404, detail="Message not found.")
    return item


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
