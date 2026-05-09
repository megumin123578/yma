from typing import List

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from python_backend.api.auth import schemas
from python_backend.api.auth.auth_utils import get_current_user
from python_backend.api.auth.database import get_db
from python_backend.api.auth.models import (
    RivalChannel,
    RivalChannelGroup,
    RivalGroup,
    User,
)

from .common import router


@router.get("/rivals", response_model=List[schemas.RivalChannelOut])
def list_rivals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(RivalChannel)
        .filter(RivalChannel.user_id == current_user.id)
        .order_by(RivalChannel.id.desc())
        .all()
    )
    groups = (
        db.query(RivalChannelGroup)
        .filter(RivalChannelGroup.user_id == current_user.id)
        .all()
    )
    grouped = {}
    for row in groups:
        grouped.setdefault(row.channel_id, []).append(row.group_name)
    items = []
    for row in rows:
        names = sorted(set(grouped.get(row.channel_id, [])))
        items.append(
            {
                "id": row.id,
                "channel_id": row.channel_id,
                "channel_name": row.channel_name,
                "channel_url": row.channel_url,
                "channel_avatar_url": row.channel_avatar_url,
                "group_name": names[0] if names else None,
                "group_names": names,
            }
        )
    return items


@router.post("/rivals", response_model=schemas.RivalChannelOut)
def add_rival(
    data: schemas.RivalChannelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    channel_id = (data.channel_id or "").strip()
    if not channel_id:
        raise HTTPException(status_code=400, detail="channel_id is required")

    row = (
        db.query(RivalChannel)
        .filter(
            RivalChannel.user_id == current_user.id,
            RivalChannel.channel_id == channel_id,
        )
        .first()
    )
    group_names = None
    if data.group_names is not None:
        group_names = [g.strip() for g in data.group_names if g and g.strip()]
    elif data.group_name is not None:
        group_names = [data.group_name.strip()] if data.group_name.strip() else []

    if row:
        if data.channel_name:
            row.channel_name = data.channel_name
        if data.channel_url:
            row.channel_url = data.channel_url
        if data.channel_avatar_url:
            row.channel_avatar_url = data.channel_avatar_url
        if data.group_name is not None:
            row.group_name = data.group_name
        db.add(row)
        db.commit()
        db.refresh(row)
        if group_names is not None:
            (
                db.query(RivalChannelGroup)
                .filter(
                    RivalChannelGroup.user_id == current_user.id,
                    RivalChannelGroup.channel_id == channel_id,
                )
                .delete()
            )
            for name in sorted(set(group_names)):
                db.add(
                    RivalGroup(user_id=current_user.id, group_name=name)
                )
                db.add(
                    RivalChannelGroup(
                        user_id=current_user.id,
                        channel_id=channel_id,
                        group_name=name,
                    )
                )
            db.commit()
        names = sorted(set(group_names or []))
        return {
            "id": row.id,
            "channel_id": row.channel_id,
            "channel_name": row.channel_name,
            "channel_url": row.channel_url,
            "channel_avatar_url": row.channel_avatar_url,
            "group_name": names[0] if names else None,
            "group_names": names,
        }

    row = RivalChannel(
        user_id=current_user.id,
        channel_id=channel_id,
        channel_name=data.channel_name,
        channel_url=data.channel_url,
        channel_avatar_url=data.channel_avatar_url,
        group_name=data.group_name,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    if group_names is not None:
        for name in sorted(set(group_names)):
            db.add(
                RivalGroup(user_id=current_user.id, group_name=name)
            )
            db.add(
                RivalChannelGroup(
                    user_id=current_user.id,
                    channel_id=channel_id,
                    group_name=name,
                )
            )
        db.commit()
    names = sorted(set(group_names or []))
    return {
        "id": row.id,
        "channel_id": row.channel_id,
        "channel_name": row.channel_name,
        "channel_url": row.channel_url,
        "channel_avatar_url": row.channel_avatar_url,
        "group_name": names[0] if names else None,
        "group_names": names,
    }


@router.delete("/rivals/{channel_id}")
def delete_rival(
    channel_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(RivalChannel)
        .filter(
            RivalChannel.user_id == current_user.id,
            RivalChannel.channel_id == channel_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Channel not found")
    db.query(RivalChannelGroup).filter(
        RivalChannelGroup.user_id == current_user.id,
        RivalChannelGroup.channel_id == channel_id,
    ).delete()
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.delete("/rivals/groups/{group_name}")
def delete_rival_group(
    group_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    name = (group_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="group_name is required")
    updated = (
        db.query(RivalChannelGroup)
        .filter(
            RivalChannelGroup.user_id == current_user.id,
            RivalChannelGroup.group_name == name,
        )
        .delete()
    )
    db.query(RivalGroup).filter(
        RivalGroup.user_id == current_user.id,
        RivalGroup.group_name == name,
    ).delete()
    db.commit()
    return {"ok": True, "updated": updated}


@router.get("/rivals/groups")
def list_rival_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(RivalGroup)
        .filter(RivalGroup.user_id == current_user.id)
        .order_by(RivalGroup.group_name.asc())
        .all()
    )
    return {"groups": [r.group_name for r in rows]}


@router.post("/rivals/groups")
def create_rival_group(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    name = (payload.get("group_name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="group_name is required")
    existing = (
        db.query(RivalGroup)
        .filter(
            RivalGroup.user_id == current_user.id,
            RivalGroup.group_name == name,
        )
        .first()
    )
    if existing:
        return {"ok": True, "group_name": name}
    db.add(RivalGroup(user_id=current_user.id, group_name=name))
    db.commit()
    return {"ok": True, "group_name": name}
