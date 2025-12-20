# routes/youtube.py
import os
import re
from typing import Dict, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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


def _fetch_uploads(youtube, playlist_id: str, max_items: int = 12):
    if not playlist_id:
        return []

    videos = []
    req = youtube.playlistItems().list(
        part="snippet,contentDetails",
        playlistId=playlist_id,
        maxResults=50,
    )

    while req and len(videos) < max_items:
        resp = req.execute() or {}
        for item in resp.get("items", []):
            snippet = item.get("snippet", {})
            content = item.get("contentDetails", {})
            vid = content.get("videoId")
            if not vid:
                continue
            videos.append({
                "videoId": vid,
                "title": snippet.get("title", ""),
                "publishedAt": snippet.get("publishedAt", ""),
                "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
            })
            if len(videos) >= max_items:
                break
        req = youtube.playlistItems().list_next(req, resp)

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


@router.get("/channel")
def channel_detail(query: str = Query(..., min_length=1)):
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

    videos = _fetch_uploads(youtube, channel.get("uploadsPlaylistId", ""))

    return {
        "channel": channel,
        "videos": videos,
    }
