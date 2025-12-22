# routes/youtube.py
import os
import re
from typing import Dict, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, Header
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from jose import JWTError, jwt

from python_backend.api.auth.auth_utils import SECRET_KEY, ALGORITHM
from python_backend.api.auth.database import SessionLocal as AuthSessionLocal
from python_backend.api.auth.models import RivalVideo, User

router = APIRouter(prefix="/api/youtube", tags=["youtube"])

CHANNEL_ID_RE = re.compile(r"^UC[a-zA-Z0-9_-]{22}$")


def _normalize_query(raw: str) -> Dict[str, str]:
    q = (raw or "").strip()
    if not q:
        return {}

    if q.startswith("@"):
        return {"forHandle": q[1:]}

    if "youtube.com" in q or "youtu.be" in q:
        if not re.match(r"^https?://", q):
            q = "https://" + q
        parsed = urlparse(q)
        path = parsed.path or ""

        m = re.search(r"/channel/([a-zA-Z0-9_-]{20,})", path)
        if m:
            return {"id": m.group(1)}

        m = re.search(r"/user/([^/]+)", path)
        if m:
            return {"forUsername": m.group(1)}

        m = re.search(r"/@([^/]+)", path)
        if m:
            return {"forHandle": m.group(1)}

        m = re.search(r"/c/([^/]+)", path)
        if m:
            return {"search": m.group(1)}

    if CHANNEL_ID_RE.match(q):
        return {"id": q}

    return {"search": q}


def _fetch_channel(youtube, params: Dict[str, str]) -> Optional[Dict]:
    if not params:
        return None

    if "search" in params:
        search_q = params["search"]
        resp = youtube.search().list(
            part="snippet",
            q=search_q,
            type="channel",
            maxResults=1,
        ).execute() or {}
        items = resp.get("items", [])
        if not items:
            return None
        channel_id = items[0].get("id", {}).get("channelId")
        if not channel_id:
            return None
        params = {"id": channel_id}

    resp = youtube.channels().list(
        part="snippet,statistics,contentDetails",
        **params,
    ).execute() or {}

    items = resp.get("items", [])
    if not items:
        return None

    it = items[0]
    snippet = it.get("snippet", {})
    stats = it.get("statistics", {})
    content = it.get("contentDetails", {})
    uploads = content.get("relatedPlaylists", {}).get("uploads", "")

    return {
        "id": it.get("id", ""),
        "title": snippet.get("title", ""),
        "description": snippet.get("description", ""),
        "customUrl": snippet.get("customUrl", ""),
        "publishedAt": snippet.get("publishedAt", ""),
        "country": snippet.get("country", ""),
        "thumbnails": snippet.get("thumbnails", {}),
        "statistics": stats,
        "uploadsPlaylistId": uploads,
    }


def _enrich_video_stats(youtube, videos):
    if not videos:
        return videos

    id_map = {v["videoId"]: v for v in videos}
    ids = list(id_map.keys())
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        resp = youtube.videos().list(
            part="statistics",
            id=",".join(chunk),
        ).execute() or {}
        for item in resp.get("items", []):
            stats = item.get("statistics", {})
            vid = item.get("id")
            if vid in id_map:
                id_map[vid]["views"] = stats.get("viewCount")
                id_map[vid]["likes"] = stats.get("likeCount")
                id_map[vid]["comments"] = stats.get("commentCount")

    return list(id_map.values())


def _get_user_from_token(authorization: Optional[str]) -> Optional[User]:
    if not authorization:
        return None

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    token = parts[1].strip()
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
    except JWTError:
        return None

    if not username:
        return None

    db = AuthSessionLocal()
    try:
        return db.query(User).filter(User.username == username).first()
    finally:
        db.close()


def _fetch_existing_rival_ids(user_id: int, video_ids):
    if not video_ids:
        return set()

    db = AuthSessionLocal()
    try:
        rows = (
            db.query(RivalVideo.video_id)
            .filter(RivalVideo.user_id == user_id, RivalVideo.video_id.in_(video_ids))
            .all()
        )
        return {row[0] for row in rows}
    except Exception as e:
        print("[DB ERROR] Failed to check rival videos:", e)
        return set()
    finally:
        db.close()


def _save_rival_videos(user_id: int, channel_id: str, videos, is_short: bool):
    if not videos:
        return

    ids = [v.get("videoId") for v in videos if v.get("videoId")]
    if not ids:
        return

    db = AuthSessionLocal()
    try:
        existing = (
            db.query(RivalVideo.video_id)
            .filter(RivalVideo.user_id == user_id, RivalVideo.video_id.in_(ids))
            .all()
        )
        existing_ids = {row[0] for row in existing}

        for v in videos:
            vid = v.get("videoId")
            if not vid or vid in existing_ids:
                continue
            row = RivalVideo(
                user_id=user_id,
                channel_id=channel_id or "",
                video_id=vid,
                title=v.get("title") or "",
                published_at=v.get("publishedAt") or "",
                is_short=is_short,
                views=int(v.get("views") or 0),
                likes=int(v.get("likes") or 0),
                comments=int(v.get("comments") or 0),
            )
            db.add(row)
        db.commit()
    except Exception as e:
        print("[DB ERROR] Failed to save rival videos:", e)
        db.rollback()
    finally:
        db.close()


def _fetch_latest_videos(youtube, channel_id: str, max_items: int = 10):
    if not channel_id:
        return []

    resp = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        order="date",
        type="video",
        maxResults=max_items,
    ).execute() or {}

    videos = []
    for item in resp.get("items", []):
        vid = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        if not vid:
            continue
        videos.append({
            "videoId": vid,
            "title": snippet.get("title", ""),
            "publishedAt": snippet.get("publishedAt", ""),
            "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
        })

    return _enrich_video_stats(youtube, videos)


def _fetch_latest_shorts(youtube, channel_id: str, max_items: int = 10):
    if not channel_id:
        return []

    resp = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        order="date",
        type="video",
        videoDuration="short",
        maxResults=max_items,
    ).execute() or {}

    videos = []
    for item in resp.get("items", []):
        vid = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        if not vid:
            continue
        videos.append({
            "videoId": vid,
            "title": snippet.get("title", ""),
            "publishedAt": snippet.get("publishedAt", ""),
            "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
        })

    return _enrich_video_stats(youtube, videos)


@router.get("/channel")
def channel_detail(
    query: str = Query(..., min_length=1),
    authorization: Optional[str] = Header(default=None),
):
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(500, "Missing YOUTUBE_API_KEY")

    youtube = build("youtube", "v3", developerKey=api_key)
    params = _normalize_query(query)

    try:
        channel = _fetch_channel(youtube, params)
    except HttpError as e:
        raise HTTPException(502, f"YouTube API error: {e}")

    if not channel:
        raise HTTPException(404, "Channel not found")

    channel_id = channel.get("id", "")
    videos = _fetch_latest_videos(youtube, channel_id, max_items=10)
    shorts = _fetch_latest_shorts(youtube, channel_id, max_items=10)

    user = _get_user_from_token(authorization)
    if user:
        all_ids = [v.get("videoId") for v in videos] + [s.get("videoId") for s in shorts]
        existing_ids = _fetch_existing_rival_ids(user.id, [vid for vid in all_ids if vid])
        for v in videos:
            v["isNew"] = v.get("videoId") not in existing_ids
        for v in shorts:
            v["isNew"] = v.get("videoId") not in existing_ids
        _save_rival_videos(user.id, channel_id, videos, is_short=False)
        _save_rival_videos(user.id, channel_id, shorts, is_short=True)
    else:
        for v in videos:
            v["isNew"] = False
        for v in shorts:
            v["isNew"] = False

    return {
        "channel": channel,
        "videos": videos,
        "shorts": shorts,
    }
