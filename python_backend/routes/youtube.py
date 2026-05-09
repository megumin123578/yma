# routes/youtube.py
import os
import re
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

router = APIRouter(prefix="/api/youtube", tags=["youtube"])

CHANNEL_ID_RE = re.compile(r"^UC[a-zA-Z0-9_-]{22}$")
_channel_cache: dict[str, dict] = {}


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


def _prune_cache(day_key: str) -> None:
    stale = [k for k in _channel_cache.keys() if not k.startswith(f"{day_key}:")]
    for key in stale:
        _channel_cache.pop(key, None)


def _get_cache(cache_key: str) -> Optional[Dict]:
    cached = _channel_cache.get(cache_key)
    return cached["data"] if cached else None


def _set_cache(cache_key: str, data: Dict) -> None:
    _channel_cache[cache_key] = {"data": data}


def _is_quota_exceeded(err: HttpError) -> bool:
    try:
        details = err.error_details or []
        for item in details:
            if item.get("reason") == "quotaExceeded":
                return True
    except Exception:
        pass
    return "quotaExceeded" in str(err)


_search_cache: dict[str, dict] = {}


def _prune_search_cache(day_key: str) -> None:
    stale = [k for k in _search_cache.keys() if not k.startswith(f"{day_key}:")]
    for key in stale:
        _search_cache.pop(key, None)


@router.get("/search")
def channel_search(
    q: str = Query(..., min_length=1, max_length=120),
    limit: int = Query(8, ge=1, le=15),
):
    """Search YouTube for channels by free text. Returns up to N matches.

    Why: replaces 'paste a URL/ID' UX with a real search bar. Each call costs
    100 quota units (search.list) + 1 (channels.list); cached per-day per-query.
    """
    api_keys = [
        os.getenv("YOUTUBE_API_KEY1", "").strip(),
        os.getenv("YOUTUBE_API_KEY2", "").strip(),
    ]
    api_keys = [k for k in api_keys if k]
    if not api_keys:
        raise HTTPException(500, "Missing YOUTUBE_API_KEY1 or YOUTUBE_API_KEY2")

    query = q.strip()
    if not query:
        return {"items": []}

    day_key = datetime.utcnow().strftime("%Y-%m-%d")
    _prune_search_cache(day_key)
    cache_key = f"{day_key}:{limit}:{query.lower()}"
    cached = _search_cache.get(cache_key)
    if cached:
        return cached["data"]

    last_error = None
    for api_key in api_keys:
        youtube = build("youtube", "v3", developerKey=api_key)
        try:
            search_resp = youtube.search().list(
                part="snippet",
                q=query,
                type="channel",
                maxResults=limit,
            ).execute() or {}

            channel_ids = []
            preview_by_id = {}
            for item in search_resp.get("items", []):
                cid = item.get("id", {}).get("channelId")
                if not cid or cid in preview_by_id:
                    continue
                snippet = item.get("snippet", {})
                preview_by_id[cid] = {
                    "id": cid,
                    "title": snippet.get("title", "") or snippet.get("channelTitle", ""),
                    "description": snippet.get("description", ""),
                    "thumbnail": (
                        snippet.get("thumbnails", {}).get("medium", {}).get("url")
                        or snippet.get("thumbnails", {}).get("default", {}).get("url")
                        or ""
                    ),
                }
                channel_ids.append(cid)

            if not channel_ids:
                payload = {"items": []}
                _search_cache[cache_key] = {"data": payload}
                return payload

            stats_resp = youtube.channels().list(
                part="snippet,statistics",
                id=",".join(channel_ids),
            ).execute() or {}

            for item in stats_resp.get("items", []):
                cid = item.get("id")
                if not cid or cid not in preview_by_id:
                    continue
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                preview_by_id[cid].update({
                    "title": snippet.get("title") or preview_by_id[cid]["title"],
                    "customUrl": snippet.get("customUrl", ""),
                    "country": snippet.get("country", ""),
                    "subscriberCount": stats.get("subscriberCount"),
                    "videoCount": stats.get("videoCount"),
                    "hiddenSubscriberCount": bool(stats.get("hiddenSubscriberCount")),
                })

            items = [preview_by_id[cid] for cid in channel_ids if cid in preview_by_id]
            payload = {"items": items}
            _search_cache[cache_key] = {"data": payload}
            return payload
        except HttpError as e:
            last_error = e
            if _is_quota_exceeded(e):
                continue
            raise HTTPException(502, f"YouTube API error: {e}")

    if last_error:
        raise HTTPException(502, f"YouTube API error: {last_error}")
    raise HTTPException(502, "YouTube API error")


@router.get("/channel")
def channel_detail(
    query: str = Query(..., min_length=1),
):
    api_keys = [
        os.getenv("YOUTUBE_API_KEY1", "").strip(),
        os.getenv("YOUTUBE_API_KEY2", "").strip(),
    ]
    api_keys = [k for k in api_keys if k]
    if not api_keys:
        raise HTTPException(500, "Missing YOUTUBE_API_KEY1 or YOUTUBE_API_KEY2")

    day_key = datetime.utcnow().strftime("%Y-%m-%d")
    _prune_cache(day_key)
    cache_key = f"{day_key}:{query.strip().lower()}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    last_error = None
    for api_key in api_keys:
        youtube = build("youtube", "v3", developerKey=api_key)
        params = _normalize_query(query)
        try:
            channel = _fetch_channel(youtube, params)
            if not channel:
                raise HTTPException(404, "Channel not found")

            channel_id = channel.get("id", "")
            videos = _fetch_latest_videos(youtube, channel_id, max_items=10)
            shorts = _fetch_latest_shorts(youtube, channel_id, max_items=10)

            for v in videos:
                v["isNew"] = False
            for v in shorts:
                v["isNew"] = False

            payload = {
                "channel": channel,
                "videos": videos,
                "shorts": shorts,
            }
            _set_cache(cache_key, payload)
            return payload
        except HttpError as e:
            last_error = e
            if _is_quota_exceeded(e):
                continue
            raise HTTPException(502, f"YouTube API error: {e}")

    if last_error:
        raise HTTPException(502, f"YouTube API error: {last_error}")
    raise HTTPException(502, "YouTube API error")
