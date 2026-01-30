import os
import json
import sqlite3
from datetime import date
from typing import List, Dict, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import create_engine, text

from module_trafficsource import (
    create_token_from_credentials,
    sanitize_filename,
    TOKEN_FOLDER,
)


def get_upload_playlist_id(credentials, channel_id: Optional[str] = None):
    yt = build("youtube", "v3", credentials=credentials)
    if channel_id:
        resp = yt.channels().list(
            part="contentDetails",
            id=channel_id,
            maxResults=1,
        ).execute()
    else:
        resp = yt.channels().list(
            part="contentDetails",
            mine=True
        ).execute()

    items = resp.get("items", [])
    if not items:
        return None

    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def get_video_list(credentials, playlist_id: str) -> List[str]:
    yt = build("youtube", "v3", credentials=credentials)
    video_ids = []

    req = yt.playlistItems().list(
        part="contentDetails",
        playlistId=playlist_id,
        maxResults=50
    )

    while req:
        resp = req.execute()

        for item in resp.get("items", []):
            video_ids.append(item["contentDetails"]["videoId"])

        req = yt.playlistItems().list_next(req, resp)

    return video_ids


def get_video_metadata(credentials, video_ids: List[str]) -> List[Dict]:
    """
    Lưu ý: YouTube Data API v3 KHÔNG có impressionCount / impressionsClickThroughRate.
    Vì vậy impressions sẽ được fill bằng Analytics ở bước sau.
    """
    yt = build("youtube", "v3", credentials=credentials)
    results = []

    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]

        resp = yt.videos().list(
            part="snippet,contentDetails,statistics",
            id=",".join(chunk)
        ).execute()

        for item in resp.get("items", []):
            stats = item.get("statistics", {})

            results.append({
                "video_id": item["id"],
                "title": item["snippet"]["title"],
                "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"],
                "published_at": item["snippet"]["publishedAt"][:10],
                "duration": item["contentDetails"]["duration"],
                "tags": item["snippet"].get("tags", []),
                "views": int(stats.get("viewCount", 0) or 0),
                "likes": int(stats.get("likeCount", 0) or 0),
                "comments": int(stats.get("commentCount", 0) or 0),

                # reach impressions (filled later)
                "card_impressions": 0,
                "ad_impressions": 0,
                "annotation_impressions": 0,
            })

    return results


def get_video_impressions(
    credentials,
    video_id: str,
    start_date: str,
    end_date: str,
    channel_id: Optional[str] = None,
) -> Dict[str, Optional[float]]:
    """
    Get CTR from YouTube Analytics API (video-level).
    """
    yta = build("youtubeAnalytics", "v2", credentials=credentials)

    try:
        ids = f"channel=={channel_id}" if channel_id else "channel==MINE"
        resp = yta.reports().query(
            ids=ids,
            startDate=start_date,
            endDate=end_date,
            filters=f"video=={video_id}",
            metrics="impressionsClickThroughRate",
        ).execute() or {}
    except HttpError as e:
        print(f"[WARN] Failed impressionsClickThroughRate for {video_id}: {e}")
        return {"impressions": 0, "ctr": None}

    rows = resp.get("rows") or []
    if not rows:
        return {"impressions": 0, "ctr": None}

    try:
        ctr = float(rows[0][0] or 0.0) * 100.0
    except Exception:
        ctr = None
    return {"impressions": 0, "ctr": ctr}


def _auth_db_path() -> str:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.getenv("AUTH_DB_PATH", os.path.join(repo_root, "auth.db"))


def get_video_reach_impressions_bulk(
    credentials,
    video_ids: List[str],
    start_date: str,
    end_date: str,
    channel_id: Optional[str] = None,
    chunk_size: int = 50,
) -> Optional[Dict[str, Dict[str, int]]]:
    if not video_ids:
        return {}

    yta = build("youtubeAnalytics", "v2", credentials=credentials)
    ids = f"channel=={channel_id}" if channel_id else "channel==MINE"
    out: Dict[str, Dict[str, int]] = {}
    any_success = False

    for chunk in _chunked_ids(video_ids, chunk_size):
        query = {
            "ids": ids,
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": "video",
            "filters": f"video=={','.join(chunk)}",
            "metrics": "cardImpressions,cardTeaserImpressions,annotationImpressions",
        }
        try:
            resp = yta.reports().query(**query).execute() or {}
        except HttpError as e:
            print(f"[WARN] Bulk reach impressions failed for chunk: {e}")
            query["metrics"] = "cardImpressions,cardTeaserImpressions"
            try:
                resp = yta.reports().query(**query).execute() or {}
            except HttpError as e2:
                print(f"[WARN] Bulk reach fallback failed for chunk: {e2}")
                continue

        rows = resp.get("rows") or []
        headers = resp.get("columnHeaders", []) or []
        if not rows or not headers:
            continue

        idx = {h["name"]: i for i, h in enumerate(headers)}
        i_video = idx.get("video")
        i_card = idx.get("cardImpressions")
        i_teaser = idx.get("cardTeaserImpressions")
        i_anno = idx.get("annotationImpressions")
        if i_video is None or i_card is None or i_teaser is None:
            continue

        for row in rows:
            vid = row[i_video]
            try:
                card = int(row[i_card] or 0)
            except Exception:
                card = 0
            try:
                teaser = int(row[i_teaser] or 0)
            except Exception:
                teaser = 0
            try:
                anno = int(row[i_anno] or 0) if i_anno is not None else 0
            except Exception:
                anno = 0
            out[vid] = {
                "card_impressions": card,
                "ad_impressions": teaser,
                "annotation_impressions": anno,
            }
        any_success = True

    if not any_success:
        return None

    return out


def _stop_requested() -> bool:
    run_id = os.getenv("SCHEDULE_RUN_ID")
    if not run_id:
        return False
    try:
        conn = sqlite3.connect(_auth_db_path())
        cur = conn.cursor()
        cur.execute(
            "SELECT status FROM user_schedule_runs WHERE id = ?",
            (int(run_id),),
        )
        row = cur.fetchone()
        conn.close()
        return bool(row and row[0] in {"stopping", "stopped", "canceled"})
    except Exception:
        return False


def _chunked_ids(video_ids: List[str], size: int) -> List[List[str]]:
    return [video_ids[i:i + size] for i in range(0, len(video_ids), size)]


def get_video_impressions_bulk(
    credentials,
    video_ids: List[str],
    start_date: str,
    end_date: str,
    channel_id: Optional[str] = None,
    chunk_size: int = 50,
) -> Optional[Dict[str, Dict[str, Optional[float]]]]:
    if not video_ids:
        return {}

    yta = build("youtubeAnalytics", "v2", credentials=credentials)
    ids = f"channel=={channel_id}" if channel_id else "channel==MINE"
    out: Dict[str, Dict[str, Optional[float]]] = {}
    any_success = False

    for chunk in _chunked_ids(video_ids, chunk_size):
        query = {
            "ids": ids,
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": "video",
            "filters": f"video=={','.join(chunk)}",
            "metrics": "impressionsClickThroughRate",
        }
        try:
            resp = yta.reports().query(**query).execute() or {}
        except HttpError as e:
            print(f"[WARN] Bulk impressionsClickThroughRate failed for chunk: {e}")
            continue

        rows = resp.get("rows") or []
        headers = resp.get("columnHeaders", []) or []
        if not rows or not headers:
            continue

        idx = {h["name"]: i for i, h in enumerate(headers)}
        i_video = idx.get("video")
        i_ctr = idx.get("impressionsClickThroughRate")
        if i_video is None or i_ctr is None:
            continue

        for row in rows:
            vid = row[i_video]
            try:
                ctr = float(row[i_ctr] or 0.0) * 100.0
            except Exception:
                ctr = None
            out[vid] = {"impressions": 0, "ctr": ctr}
        any_success = True

    if not any_success:
        return None

    return out


# ============================
# DAILY METRICS (ANALYTICS API)
# ============================

def get_video_daily_analytics(
    credentials,
    video_id: str,
    start_date: str,
    end_date: str,
    channel_id: Optional[str] = None,
) -> List[Dict]:

    yta = build("youtubeAnalytics", "v2", credentials=credentials)

    ids = f"channel=={channel_id}" if channel_id else "channel==MINE"
    q = {
        "ids": ids,
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": "day",
        "filters": f"video=={video_id}",
        "metrics": ",".join([
            "views",
            "estimatedMinutesWatched",
            "averageViewDuration",
            "likes",
        ]),
        "sort": "day"
    }

    try:
        resp = yta.reports().query(**q).execute() or {}
    except Exception as e:
        print(f"[ERROR] Failed daily analytics for {video_id}: {e}")
        return []

    rows = resp.get("rows") or []
    if not rows:
        return []

    col = {c["name"]: i for i, c in enumerate(resp["columnHeaders"])}

    i_day = col["day"]
    i_views = col["views"]
    i_emw = col["estimatedMinutesWatched"]
    i_avd = col["averageViewDuration"]
    i_likes = col["likes"]

    results = []
    for r in rows:
        results.append({
            "video_id": video_id,
            "day": r[i_day],
            "views": int(r[i_views] or 0),
            "estimated_minutes": int(r[i_emw] or 0),
            "average_view_duration": int(r[i_avd] or 0),
            "likes": int(r[i_likes] or 0),
        })

    return results


def save_metadata(videos, account_tag: str, pg_url: str):
    engine = create_engine(pg_url, future=True)

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                account_tag TEXT NOT NULL,
                title TEXT,
                thumbnail TEXT,
                published_at DATE,
                duration TEXT,
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                card_impressions BIGINT DEFAULT 0,
                ad_impressions BIGINT DEFAULT 0,
                annotation_impressions BIGINT DEFAULT 0,
                tags TEXT,
                ctr NUMERIC DEFAULT 0
            );
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_videos_account_tag ON videos(account_tag);"))
        conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS tags TEXT;"))
        conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS card_impressions BIGINT DEFAULT 0;"))
        conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS ad_impressions BIGINT DEFAULT 0;"))
        conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS annotation_impressions BIGINT DEFAULT 0;"))

        for v in videos:
            conn.execute(text("""
                INSERT INTO videos
                    (video_id, account_tag, title, thumbnail,
                     published_at, duration, views, likes, comments,
                     card_impressions, ad_impressions, annotation_impressions, tags, ctr)
                VALUES
                    (:id, :acct, :title, :thumb, :pub, :duration,
                     :views, :likes, :comments,
                     :card, :ad, :anno, :tags, :ctr)
                ON CONFLICT(video_id)
                DO UPDATE SET
                    views = EXCLUDED.views,
                    likes = EXCLUDED.likes,
                    comments = EXCLUDED.comments,
                    card_impressions = EXCLUDED.card_impressions,
                    ad_impressions = EXCLUDED.ad_impressions,
                    annotation_impressions = EXCLUDED.annotation_impressions,
                    tags = EXCLUDED.tags,
                    ctr = EXCLUDED.ctr;
            """), {
                "id": v["video_id"],
                "acct": account_tag,
                "title": v["title"],
                "thumb": v["thumbnail"],
                "pub": v["published_at"],
                "duration": v["duration"],
                "views": v["views"],
                "likes": v["likes"],
                "comments": v["comments"],
                "card": v.get("card_impressions", 0),
                "ad": v.get("ad_impressions", 0),
                "anno": v.get("annotation_impressions", 0),
                "tags": json.dumps(v.get("tags") or []),
                "ctr": v.get("ctr", 0.0),
            })


def save_daily_stats(daily_rows, pg_url: str):
    engine = create_engine(pg_url, future=True)

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_daily_stats (
                video_id TEXT NOT NULL,
                day DATE NOT NULL,
                views INTEGER,
                estimated_minutes INTEGER,
                average_view_duration INTEGER,
                likes INTEGER,
                PRIMARY KEY (video_id, day)
            );
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_vds_day ON video_daily_stats(day);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_vds_day_video ON video_daily_stats(day, video_id);"))

        for r in daily_rows:
            conn.execute(text("""
                INSERT INTO video_daily_stats
                    (video_id, day, views, estimated_minutes, average_view_duration, likes)
                VALUES
                    (:id, :day, :views, :emw, :avd, :likes)
                ON CONFLICT (video_id, day)
                DO UPDATE SET
                    views = EXCLUDED.views,
                    estimated_minutes = EXCLUDED.estimated_minutes,
                    average_view_duration = EXCLUDED.average_view_duration,
                    likes = EXCLUDED.likes;
            """), {
                "id": r["video_id"],
                "day": r["day"],
                "views": r["views"],
                "emw": r["estimated_minutes"],
                "avd": r["average_view_duration"],
                "likes": r["likes"],
            })


# ===== Cache invalidation =====
def invalidate_content_timeseries_cache(pg_url: str, account_tag: str) -> None:
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS content_timeseries_cache (
                account_tag TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                payload JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (account_tag, start_date, end_date)
            );
        """))
        conn.execute(text("""
            DELETE FROM content_timeseries_cache
            WHERE account_tag = :tag;
        """), {"tag": account_tag})


# ============================
# RUNNER
# ============================

def run_content_v3_hybrid(credentials, account_tag, pg_url, channel_id: Optional[str] = None):
    playlist_id = get_upload_playlist_id(credentials, channel_id=channel_id)
    if not playlist_id:
        print("Không tìm thấy uploads playlist.")
        return

    end_date = date.today().isoformat()

    print("→ Fetching video list...")
    video_ids = get_video_list(credentials, playlist_id)
    print(f"→ Found {len(video_ids)} videos")

    print("→ Fetching video metadata...")
    videos = get_video_metadata(credentials, video_ids)
    start_date_min = min((v["published_at"] for v in videos if v.get("published_at")), default=end_date)
    reach_map = get_video_reach_impressions_bulk(
        credentials, video_ids, start_date_min, end_date, channel_id=channel_id
    )

    print("→ Fetching reach impressions via YouTube Analytics API...")
    for v in videos:
        if _stop_requested():
            raise RuntimeError("Stop requested")
        video_id = v["video_id"]
        metrics = reach_map.get(video_id, {}) if reach_map is not None else {}
        v["card_impressions"] = int(metrics.get("card_impressions", 0) or 0)
        v["ad_impressions"] = int(metrics.get("ad_impressions", 0) or 0)
        v["annotation_impressions"] = int(metrics.get("annotation_impressions", 0) or 0)

    print("→ Saving metadata to PostgreSQL...")
    save_metadata(videos, account_tag, pg_url)

    print("→ Fetching DAILY analytics via YouTube Analytics API...")
    daily_rows = []

    for v in videos:
        if _stop_requested():
            raise RuntimeError("Stop requested")
        video_id = v["video_id"]
        print(f"[INFO] [content] Daily video: {video_id}")
        start_date = v["published_at"]
        d = get_video_daily_analytics(
            credentials, video_id, start_date, end_date, channel_id=channel_id
        )
        daily_rows.extend(d)

    print("→ Saving daily stats...")
    save_daily_stats(daily_rows, pg_url)
    invalidate_content_timeseries_cache(pg_url, account_tag)

    print("[DONE] Metadata + DAILY stats saved successfully")


def process_content(cred_file: str, channel_id: Optional[str] = None):
    cred_path = os.path.join(TOKEN_FOLDER, cred_file)
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        raise RuntimeError("Missing PG_URL env var")

    credentials = create_token_from_credentials(cred_path)
    account_tag = sanitize_filename(os.path.splitext(cred_file)[0])

    run_content_v3_hybrid(credentials, account_tag, pg_url, channel_id=channel_id)
