import json
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, HTTPException
from googleapiclient.discovery import build
from pydantic import BaseModel
from sqlalchemy.orm import Session

from python_backend.api.auth.auth_utils import get_current_user
from python_backend.api.auth.database import get_db
from python_backend.api.auth.models import (
    TokenProgress,
    User,
    UserCredential,
    UserCredentialGroup,
    UserCredentialProject,
    UserHiddenChannel,
    UserScheduleRun,
)
from python_backend.api.auth.visibility import get_allowed_account_tags, get_hidden_account_tags
from python_backend.progress_state import write_progress
from python_backend.token_store import (
    account_tag_from_token_name,
    delete_token_credentials,
    list_token_names,
    token_exists,
)

from .common import (
    router,
    _ALLOWED_RUN_STAGES,
    _UNASSIGNED_PROJECT_GROUP,
    _fetch_selected_channel_metadata,
    _find_owned_credential_by_identifier,
    _get_global_token_group_color_map,
    _is_admin_user,
    _kickoff_get_data,
    _list_token_projects,
    _load_token_credentials,
    _normalize_project_group_name,
    _pick_token_group_color,
    _purge_postgres_account,
    _require_admin,
    _require_valid_token_name,
    _safe_token_name,
    _serialize_project_group_name,
)


@router.get("/tokens")
def list_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_admin = _is_admin_user(current_user)
    allowed = get_allowed_account_tags(db, current_user)
    hidden = get_hidden_account_tags(db, current_user.id)
    group_color_map = _get_global_token_group_color_map(db)
    labels = {}
    avatars = {}
    owned_names = set()
    rows = (
        db.query(
            UserCredential.token_name,
            UserCredential.user_id,
            UserCredential.selected_channel_title,
            UserCredential.account_tag,
            UserCredential.selected_channel_id,
            UserCredential.selected_channel_avatar,
            UserCredential.group_name,
            UserCredential.project_name,
        )
        .filter(UserCredential.token_name.isnot(None))
        .all()
    )
    labels = {
        row.token_name: (row.selected_channel_title or row.account_tag or "")
        for row in rows
        if row.token_name
    }
    avatar_by_token_name = {}
    avatar_by_channel_id = {}
    for row in rows:
        avatar = (row.selected_channel_avatar or "").strip()
        if avatar and row.selected_channel_id and row.selected_channel_id not in avatar_by_channel_id:
            avatar_by_channel_id[row.selected_channel_id] = avatar
        if avatar and row.token_name and row.token_name not in avatar_by_token_name:
            avatar_by_token_name[row.token_name] = avatar
    avatars = {}
    for row in rows:
        if not row.token_name:
            continue
        avatars[row.token_name] = (
            (row.selected_channel_avatar or "").strip()
            or avatar_by_channel_id.get(row.selected_channel_id or "", "")
            or avatar_by_token_name.get(row.token_name, "")
        )
    groups = {}
    projects = {}
    for row in rows:
        if not row.token_name:
            continue
        next_group = (row.group_name or "").strip()
        next_project = (row.project_name or "").strip()
        current_group = groups.get(row.token_name, "")
        if next_group or not current_group:
            groups[row.token_name] = next_group
        current_project = projects.get(row.token_name, "")
        if next_project or not current_project:
            projects[row.token_name] = next_project
    group_colors = {
        token_name: group_color_map.get(group_name, "")
        for token_name, group_name in groups.items()
        if group_name
    }
    if is_admin:
        owned_names = {row.token_name for row in rows if row.token_name}
    else:
        owned_names = {
            row.token_name for row in rows if row.token_name and row.user_id == current_user.id
        }

    files = []
    for name in list_token_names():
        if str(name or "").strip().lower().startswith("mail__"):
            continue
        base = account_tag_from_token_name(name)
        if allowed is not None and base not in allowed:
            continue
        files.append(
            {
                "name": name,
                "hidden": base in hidden,
                "label": labels.get(name, ""),
                "avatar": avatars.get(name, ""),
                "group_name": groups.get(name, ""),
                "project_name": projects.get(name, ""),
                "group_color": group_colors.get(name, ""),
                "owned": name in owned_names,
            }
        )
    files.sort(key=lambda x: x["name"])
    return {"tokens": files}


@router.get("/tokens/progress")
def list_token_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_admin = _is_admin_user(current_user)
    q = db.query(TokenProgress)
    if not is_admin:
        q = q.filter(TokenProgress.user_id == current_user.id)
    rows = q.order_by(TokenProgress.updated_at.desc(), TokenProgress.id.desc()).all()
    return {
        "items": [
            {
                "token_name": row.token_name,
                "account_tag": row.account_tag,
                "run_id": row.run_id or "",
                "status": row.status,
                "percent": row.percent,
                "stage": row.stage or "",
                "message": row.message or "",
                "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else "",
                "started_at": row.started_at.isoformat() + "Z" if row.started_at else "",
                "finished_at": row.finished_at.isoformat() + "Z" if row.finished_at else "",
            }
            for row in rows
        ]
    }


class TokenVisibilityUpdate(BaseModel):
    token: str
    hidden: bool


class TokenGroupUpdate(BaseModel):
    group_name: Optional[str] = None


class TokenProjectUpdate(BaseModel):
    group_name: Optional[str] = None
    project_name: Optional[str] = None


@router.post("/tokens/visibility")
def set_token_visibility(
    payload: TokenVisibilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    token_name = _require_valid_token_name(payload.token)
    base_name = account_tag_from_token_name(token_name)
    token_row = (
        db.query(UserCredential)
        .filter(UserCredential.token_name == token_name)
        .first()
    )
    if not token_row:
        raise HTTPException(status_code=404, detail="Token not found")
    row = (
        db.query(UserHiddenChannel)
        .filter(
            UserHiddenChannel.user_id == current_user.id,
            UserHiddenChannel.account_tag == base_name,
        )
        .first()
    )
    if payload.hidden:
        if not row:
            db.add(UserHiddenChannel(user_id=current_user.id, account_tag=base_name))
            db.commit()
    else:
        if row:
            db.delete(row)
            db.commit()
    return {"ok": True, "hidden": payload.hidden}


@router.get("/tokens/groups")
def list_token_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    color_by_group = _get_global_token_group_color_map(db)
    return {
        "groups": [
            {"group_name": name, "color": color_by_group[name]}
            for name in sorted(color_by_group.keys(), key=str.lower)
        ]
    }


@router.get("/tokens/projects")
def list_token_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    return {"projects": _list_token_projects(db)}


@router.post("/tokens/groups")
def create_token_group(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    name = (payload.get("group_name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="group_name is required")
    color_by_group = _get_global_token_group_color_map(db)
    if name in color_by_group:
        return {"ok": True, "group_name": name, "color": color_by_group[name]}
    color = _pick_token_group_color(name, set(color.lower() for color in color_by_group.values()))
    db.add(UserCredentialGroup(user_id=current_user.id, group_name=name, color=color))
    db.commit()
    return {"ok": True, "group_name": name, "color": color}


@router.post("/tokens/projects")
def create_token_project(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    project_name = (payload.get("project_name") or "").strip()
    if not project_name:
        raise HTTPException(status_code=400, detail="project_name is required")
    existing = {item["project_name"] for item in _list_token_projects(db)}
    if project_name in existing:
        return {"ok": True, "group_name": None, "project_name": project_name}
    db.add(
        UserCredentialProject(
            user_id=current_user.id,
            group_name=_UNASSIGNED_PROJECT_GROUP,
            project_name=project_name,
        )
    )
    db.commit()
    return {"ok": True, "group_name": None, "project_name": project_name}


@router.patch("/tokens/groups/{group_name}")
def rename_token_group(
    group_name: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    current_name = (group_name or "").strip()
    next_name = (payload.get("group_name") or "").strip()
    if not current_name:
        raise HTTPException(status_code=400, detail="group_name is required")
    if not next_name:
        raise HTTPException(status_code=400, detail="New group_name is required")
    if current_name == next_name:
        return {"ok": True, "group_name": next_name}
    color_by_group = _get_global_token_group_color_map(db)
    if next_name in color_by_group:
        raise HTTPException(status_code=400, detail="Group name already exists")
    color = color_by_group.get(current_name, "")
    if not color:
        raise HTTPException(status_code=404, detail="Group not found")
    rows = (
        db.query(UserCredentialGroup)
        .filter(UserCredentialGroup.group_name == current_name)
        .all()
    )
    for row in rows:
        row.group_name = next_name
        row.color = color
        db.add(row)
    if not rows:
        db.add(UserCredentialGroup(user_id=current_user.id, group_name=next_name, color=color))
    project_rows = (
        db.query(UserCredentialProject)
        .filter(UserCredentialProject.group_name == current_name)
        .all()
    )
    for row in project_rows:
        row.group_name = next_name
        db.add(row)
    (
        db.query(UserCredential)
        .filter(UserCredential.group_name == current_name)
        .update({"group_name": next_name}, synchronize_session=False)
    )
    db.commit()
    return {"ok": True, "group_name": next_name, "color": color}


@router.patch("/tokens/projects/{project_name}")
def rename_token_project(
    project_name: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    current_name = (project_name or "").strip()
    next_name = (payload.get("project_name") or "").strip()
    if not current_name:
        raise HTTPException(status_code=400, detail="project_name is required")
    if not next_name:
        raise HTTPException(status_code=400, detail="New project_name is required")
    if current_name == next_name:
        row = (
            db.query(UserCredentialProject)
            .filter(UserCredentialProject.project_name == current_name)
            .first()
        )
        return {
            "ok": True,
            "group_name": _serialize_project_group_name(getattr(row, "group_name", None)),
            "project_name": next_name,
        }
    existing = {item["project_name"] for item in _list_token_projects(db)}
    if next_name in existing:
        raise HTTPException(status_code=400, detail="Project name already exists")
    rows = (
        db.query(UserCredentialProject)
        .filter(
            UserCredentialProject.project_name == current_name,
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Project not found")
    stored_group_name = _normalize_project_group_name(rows[0].group_name)
    for row in rows:
        row.project_name = next_name
        db.add(row)
    (
        db.query(UserCredential)
        .filter(
            UserCredential.project_name == current_name,
        )
        .update({"project_name": next_name}, synchronize_session=False)
    )
    db.commit()
    return {
        "ok": True,
        "group_name": _serialize_project_group_name(stored_group_name),
        "project_name": next_name,
    }


@router.delete("/tokens/groups/{group_name}")
def delete_token_group(
    group_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    name = (group_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="group_name is required")
    color_by_group = _get_global_token_group_color_map(db)
    if name not in color_by_group:
        raise HTTPException(status_code=404, detail="Group not found")
    (
        db.query(UserCredential)
        .filter(UserCredential.group_name == name)
        .update({"group_name": None, "project_name": None}, synchronize_session=False)
    )
    (
        db.query(UserCredentialProject)
        .filter(UserCredentialProject.group_name == name)
        .delete()
    )
    deleted = (
        db.query(UserCredentialGroup)
        .filter(UserCredentialGroup.group_name == name)
        .delete()
    )
    db.commit()
    return {"ok": True, "deleted": deleted}


@router.delete("/tokens/projects/{project_name}")
def delete_token_project(
    project_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    current_name = (project_name or "").strip()
    if not current_name:
        raise HTTPException(status_code=400, detail="project_name is required")
    (
        db.query(UserCredential)
        .filter(
            UserCredential.project_name == current_name,
        )
        .update({"project_name": None}, synchronize_session=False)
    )
    deleted = (
        db.query(UserCredentialProject)
        .filter(
            UserCredentialProject.project_name == current_name,
        )
        .delete()
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    db.commit()
    return {"ok": True, "deleted": deleted}


@router.post("/tokens/projects/{project_name}/group")
def assign_project_group(
    project_name: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    current_name = (project_name or "").strip()
    group_name = (payload.get("group_name") or "").strip()
    if not current_name:
        raise HTTPException(status_code=400, detail="project_name is required")
    if group_name:
        color_by_group = _get_global_token_group_color_map(db)
        if group_name not in color_by_group:
            raise HTTPException(status_code=404, detail="Group not found")
    row = (
        db.query(UserCredentialProject)
        .filter(UserCredentialProject.project_name == current_name)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    row.group_name = _normalize_project_group_name(group_name)
    db.add(row)
    (
        db.query(UserCredential)
        .filter(UserCredential.project_name == current_name)
        .update({"group_name": group_name or None}, synchronize_session=False)
    )
    db.commit()
    return {"ok": True, "project_name": current_name, "group_name": group_name or None}


@router.post("/tokens/{token_name}/group")
def assign_token_group(
    token_name: str,
    payload: TokenGroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    safe_name = _require_valid_token_name(token_name)
    owned = _find_owned_credential_by_identifier(
        db,
        current_user.id,
        safe_name,
        allow_all_users=_is_admin_user(current_user),
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")
    group_name = (payload.group_name or "").strip()
    color_by_group = _get_global_token_group_color_map(db)
    group_color = color_by_group.get(group_name, "") if group_name else ""
    if group_name:
        if not group_color:
            group_color = _pick_token_group_color(
                group_name,
                set(color.lower() for color in color_by_group.values()),
            )
            db.add(UserCredentialGroup(user_id=current_user.id, group_name=group_name, color=group_color))
    now = datetime.utcnow()
    current_row = owned
    current_project_name = (current_row.project_name or "").strip() if current_row else ""
    next_project_name = current_project_name if current_row and (current_row.group_name or "").strip() == group_name else ""
    (
        db.query(UserCredential)
        .filter(UserCredential.id == owned.id)
        .update(
            {
                "group_name": group_name or None,
                "project_name": next_project_name or None,
                "updated_at": now,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return {
        "ok": True,
        "group_name": group_name or None,
        "project_name": next_project_name or None,
        "group_color": group_color,
    }


@router.post("/token/{token_name}/project")
@router.post("/tokens/{token_name}/project")
def assign_token_project(
    token_name: str,
    payload: TokenProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    safe_name = _require_valid_token_name(token_name)
    owned = _find_owned_credential_by_identifier(
        db,
        current_user.id,
        safe_name,
        allow_all_users=_is_admin_user(current_user),
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")
    group_name = (payload.group_name or "").strip()
    project_name = (payload.project_name or "").strip()
    current_group_name = (owned.group_name or "").strip()
    current_project_name = (owned.project_name or "").strip()
    if group_name:
        color_by_group = _get_global_token_group_color_map(db)
        if group_name not in color_by_group:
            raise HTTPException(status_code=404, detail="Group not found")
    if (
        project_name
        and current_project_name
        and (
            current_project_name != project_name
            or current_group_name != group_name
        )
    ):
        raise HTTPException(
            status_code=409,
            detail="Channel already belongs to another project. Remove it there first.",
        )
    if project_name:
        project_row = (
            db.query(UserCredentialProject)
            .filter(UserCredentialProject.project_name == project_name)
            .first()
        )
        if project_row:
            project_row.group_name = _normalize_project_group_name(group_name)
            db.add(project_row)
        else:
            db.add(
                UserCredentialProject(
                    user_id=current_user.id,
                    group_name=_normalize_project_group_name(group_name),
                    project_name=project_name,
                )
            )
    now = datetime.utcnow()
    (
        db.query(UserCredential)
        .filter(UserCredential.id == owned.id)
        .update(
            {
                "group_name": group_name or None,
                "project_name": project_name or None,
                "updated_at": now,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return {
        "ok": True,
        "group_name": group_name or None,
        "project_name": project_name or None,
    }


class RunAllTokensPayload(BaseModel):
    stage: Optional[str] = None


@router.post("/tokens/run-all")
def run_all_tokens(
    payload: Optional[RunAllTokensPayload] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stage = ((payload.stage if payload else "") or "").strip().lower()
    if stage and stage not in _ALLOWED_RUN_STAGES:
        raise HTTPException(status_code=400, detail="Invalid stage")

    is_admin = _is_admin_user(current_user)
    token_names = []
    if is_admin:
        token_names = list_token_names()
    else:
        hidden = get_hidden_account_tags(db, current_user.id)
        rows = (
            db.query(UserCredential.token_name, UserCredential.account_tag)
            .filter(
                UserCredential.user_id == current_user.id,
                UserCredential.token_name.isnot(None),
            )
            .all()
        )
        for row in rows:
            if not row.token_name:
                continue
            if (row.account_tag or "") in hidden:
                continue
            if not token_exists(row.token_name):
                continue
            token_names.append(row.token_name)
        token_names = sorted(set(token_names))

    if not token_names:
        raise HTTPException(status_code=400, detail="No tokens available to run")

    queued_progress_message = "Queued manual refresh" if not stage else f"Queued manual {stage}"
    for token_name in token_names:
        account_tag = account_tag_from_token_name(token_name)
        write_progress(account_tag, "queued", 0, "queued", queued_progress_message)

    run_type = "manual_all" if not stage else f"manual_all_stage:{stage}"
    if not stage:
        run_message = f"Queued manual refresh for {len(token_names)} token(s)"
    else:
        run_message = f"Queued manual {stage} for {len(token_names)} token(s)"

    run = UserScheduleRun(
        user_id=current_user.id,
        schedule_id=None,
        token_name=None,
        token_names=json.dumps(token_names),
        run_type=run_type,
        status="queued",
        started_at=datetime.utcnow(),
        processed=0,
        total=len(token_names),
        message=run_message,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    env_extra = {
        "SCHEDULE_RUN_ID": str(run.id),
        "RUN_TOKEN_NAMES": json.dumps(token_names),
    }
    if stage:
        env_extra["RUN_STAGE"] = stage
    _kickoff_get_data(
        "",
        env_extra=env_extra,
    )
    return {"ok": True, "run_id": run.id, "token_names": token_names, "stage": stage}


@router.get("/tokens/{token_name}/channels")
def list_token_channels(
    token_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_name = _require_valid_token_name(token_name)

    owned = (
        db.query(UserCredential)
        .filter(
            UserCredential.user_id == current_user.id,
            UserCredential.token_name == token_name,
        )
        .first()
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")

    creds = _load_token_credentials(safe_name)
    yt = build("youtube", "v3", credentials=creds)
    req = yt.channels().list(part="snippet,contentDetails", mine=True, maxResults=50)
    channels = []
    while req is not None:
        resp = req.execute() or {}
        for item in resp.get("items", []):
            snippet = item.get("snippet", {})
            content = item.get("contentDetails", {})
            channels.append(
                {
                    "id": item.get("id", ""),
                    "title": snippet.get("title", ""),
                    "customUrl": snippet.get("customUrl", ""),
                    "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                    "uploadsPlaylistId": content.get("relatedPlaylists", {}).get("uploads", ""),
                }
            )
        req = yt.channels().list_next(req, resp)

    return {
        "channels": channels,
        "selected_channel_id": owned.selected_channel_id,
        "selected_channel_title": owned.selected_channel_title,
    }


@router.post("/tokens/{token_name}/channel")
def set_token_channel(
    token_name: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_name = _require_valid_token_name(token_name)

    owned = (
        db.query(UserCredential)
        .filter(
            UserCredential.user_id == current_user.id,
            UserCredential.token_name == token_name,
        )
        .first()
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")

    channel_id = (payload.get("channel_id") or "").strip()
    if not channel_id:
        raise HTTPException(status_code=400, detail="channel_id is required")

    creds = _load_token_credentials(safe_name)
    meta = _fetch_selected_channel_metadata(creds, channel_id=channel_id)
    owned.selected_channel_id = meta["channel_id"] or channel_id
    owned.selected_channel_title = meta["title"]
    owned.selected_channel_avatar = meta["avatar"] or None
    owned.updated_at = datetime.utcnow()
    db.add(owned)
    db.commit()
    account_tag = account_tag_from_token_name(safe_name)
    write_progress(account_tag, "queued", 0, "queued", "Queued after authorization")
    _kickoff_get_data(account_tag)
    return {
        "ok": True,
        "selected_channel_id": owned.selected_channel_id,
        "selected_channel_title": owned.selected_channel_title,
        "selected_channel_avatar": owned.selected_channel_avatar,
    }


@router.post("/tokens/{token_name}/refresh-avatar")
def refresh_token_avatar(
    token_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_name = _require_valid_token_name(token_name)

    is_admin = _is_admin_user(current_user)
    q = db.query(UserCredential).filter(UserCredential.token_name == token_name)
    if not is_admin:
        q = q.filter(UserCredential.user_id == current_user.id)
    owned = q.first()
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")

    creds = _load_token_credentials(safe_name)
    meta = _fetch_selected_channel_metadata(creds, channel_id=owned.selected_channel_id or None)

    owned.selected_channel_id = meta["channel_id"] or owned.selected_channel_id
    owned.selected_channel_title = meta["title"] or owned.selected_channel_title
    owned.selected_channel_avatar = meta["avatar"] or None
    owned.updated_at = datetime.utcnow()
    db.add(owned)
    db.commit()

    return {
        "ok": True,
        "selected_channel_id": owned.selected_channel_id,
        "selected_channel_title": owned.selected_channel_title,
        "selected_channel_avatar": owned.selected_channel_avatar,
    }


@router.get("/tokens/{token_name}/progress")
def get_token_progress(
    token_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_name = _require_valid_token_name(token_name)

    account_tag = account_tag_from_token_name(safe_name)
    is_admin = _is_admin_user(current_user)
    q = db.query(UserCredential).filter(UserCredential.token_name == token_name)
    if not is_admin:
        q = q.filter(UserCredential.user_id == current_user.id)
    owned = q.first()
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")
    progress_row = (
        db.query(TokenProgress)
        .filter(
            TokenProgress.user_id == owned.user_id,
            TokenProgress.token_name == token_name,
        )
        .first()
    )
    if progress_row:
        return {
            "account_tag": progress_row.account_tag,
            "status": progress_row.status,
            "percent": progress_row.percent,
            "stage": progress_row.stage or "",
            "message": progress_row.message or "",
            "run_id": progress_row.run_id or "",
            "updated_at": progress_row.updated_at.isoformat() + "Z" if progress_row.updated_at else "",
            "started_at": progress_row.started_at.isoformat() + "Z" if progress_row.started_at else "",
            "finished_at": progress_row.finished_at.isoformat() + "Z" if progress_row.finished_at else "",
        }
    return {"status": "idle", "percent": 0}


@router.post("/tokens/{token_name}/run")
def run_token(
    token_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_name = _require_valid_token_name(token_name)

    account_tag = account_tag_from_token_name(safe_name)
    is_admin = _is_admin_user(current_user)
    q = db.query(UserCredential).filter(UserCredential.token_name == token_name)
    if not is_admin:
        q = q.filter(UserCredential.user_id == current_user.id)
    owned = q.first()
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")

    if not token_exists(safe_name):
        raise HTTPException(status_code=404, detail="Token not found")

    write_progress(account_tag, "queued", 0, "queued", "Manual refresh")
    run = UserScheduleRun(
        user_id=owned.user_id,
        schedule_id=None,
        token_name=safe_name,
        token_names=json.dumps([safe_name]),
        run_type="manual_single",
        status="queued",
        started_at=datetime.utcnow(),
        processed=0,
        total=7,
        message="Queued manual refresh",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    _kickoff_get_data(account_tag, env_extra={"SCHEDULE_RUN_ID": str(run.id)})
    return {"ok": True, "run_id": run.id}


class RunStagePayload(BaseModel):
    stage: str


class RunSelectedTokensPayload(BaseModel):
    token_names: List[str]


@router.post("/tokens/run-selected")
def run_selected_tokens(
    payload: RunSelectedTokensPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    requested_token_names = [
        _safe_token_name(str(name or "").strip())
        for name in (payload.token_names or [])
    ]
    requested_token_names = [
        name
        for name in requested_token_names
        if name
        and name == _safe_token_name(name)
    ]
    requested_token_names = sorted(set(requested_token_names))
    if not requested_token_names:
        raise HTTPException(status_code=400, detail="No tokens selected")

    is_admin = _is_admin_user(current_user)
    token_names = []
    if is_admin:
        for token_name in requested_token_names:
            if token_exists(token_name):
                token_names.append(token_name)
    else:
        hidden = get_hidden_account_tags(db, current_user.id)
        rows = (
            db.query(UserCredential.token_name, UserCredential.account_tag)
            .filter(
                UserCredential.user_id == current_user.id,
                UserCredential.token_name.in_(requested_token_names),
            )
            .all()
        )
        for row in rows:
            if not row.token_name:
                continue
            if (row.account_tag or "") in hidden:
                continue
            if not token_exists(row.token_name):
                continue
            token_names.append(row.token_name)
        token_names = sorted(set(token_names))

    if not token_names:
        raise HTTPException(status_code=400, detail="No selected tokens available to run")

    for token_name in token_names:
        account_tag = account_tag_from_token_name(token_name)
        write_progress(account_tag, "queued", 0, "queued", "Queued manual refresh")

    run = UserScheduleRun(
        user_id=current_user.id,
        schedule_id=None,
        token_name=None,
        token_names=json.dumps(token_names),
        run_type="manual_selected",
        status="queued",
        started_at=datetime.utcnow(),
        processed=0,
        total=len(token_names),
        message=f"Queued manual refresh for {len(token_names)} selected token(s)",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    _kickoff_get_data(
        "",
        env_extra={
            "SCHEDULE_RUN_ID": str(run.id),
            "RUN_TOKEN_NAMES": json.dumps(token_names),
        },
    )
    return {"ok": True, "run_id": run.id, "token_names": token_names}


@router.post("/tokens/{token_name}/run-stage")
def run_token_stage(
    token_name: str,
    payload: RunStagePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_name = _require_valid_token_name(token_name)

    stage = (payload.stage or "").strip().lower()
    if stage not in _ALLOWED_RUN_STAGES:
        raise HTTPException(status_code=400, detail="Invalid stage")

    is_admin = _is_admin_user(current_user)
    q = db.query(UserCredential).filter(UserCredential.token_name == token_name)
    if not is_admin:
        q = q.filter(UserCredential.user_id == current_user.id)
    owned = q.first()
    if not owned:
        raise HTTPException(status_code=404, detail="Token not found")

    if not token_exists(safe_name):
        raise HTTPException(status_code=404, detail="Token not found")

    account_tag = account_tag_from_token_name(safe_name)
    write_progress(account_tag, "queued", 0, "queued", f"Manual {stage}")
    run = UserScheduleRun(
        user_id=owned.user_id,
        schedule_id=None,
        token_name=safe_name,
        token_names=json.dumps([safe_name]),
        run_type=f"manual_stage:{stage}",
        status="queued",
        started_at=datetime.utcnow(),
        processed=0,
        total=1,
        message=f"Queued manual {stage}",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    _kickoff_get_data(
        account_tag,
        env_extra={"SCHEDULE_RUN_ID": str(run.id), "RUN_STAGE": stage},
    )
    return {"ok": True, "run_id": run.id}


@router.delete("/tokens/{token_name}")
def delete_token(
    token_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    safe_name = _require_valid_token_name(token_name)

    row = (
        db.query(UserCredential)
        .filter(
            UserCredential.token_name == token_name,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Token not found")
    base_name = account_tag_from_token_name(safe_name)
    delete_token_credentials(safe_name)
    db.query(UserHiddenChannel).filter(
        UserHiddenChannel.account_tag == base_name,
    ).delete()
    db.query(UserCredential).filter(
        UserCredential.token_name == token_name,
    ).delete()
    db.query(TokenProgress).filter(
        TokenProgress.token_name == token_name,
    ).delete()
    db.commit()
    _purge_postgres_account(base_name)
    return {"ok": True}

