import os
import sqlite3
from typing import List, Dict, Optional, Iterable

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from sqlalchemy import create_engine, text

from module_trafficsource import create_token_from_credentials, CREDENTIALS_FOLDER
from module_content import get_upload_playlist_id, get_video_list


# ======================================================================
# ANALYTICS METRICS LẤY TỪ YT ANALYTICS
# ======================================================================
ANALYTICS_METRICS = [
    "annotationClickThroughRate",
    "annotationCloseRate",
    "averageViewDuration",
    "comments",
    "dislikes",
    "engagedViews",
    "likes",
    "shares",
    "subscribersGained",
    "subscribersLost",
    "views",
]


# ======================================================================
# YOUTUBE ANALYTICS AGGREGATE QUERY
# ======================================================================
def get_yt_analytics(credentials, video_id: str, channel_id: Optional[str] = None) -> Dict:
    yta = build("youtubeAnalytics", "v2", credentials=credentials)
    ids = f"channel=={channel_id}" if channel_id else "channel==MINE"

    query = {
        "ids": ids,
        "startDate": "2000-01-01",
        "endDate": "2099-01-01",
        "metrics": ",".join(ANALYTICS_METRICS),
        "filters": f"video=={video_id}",
    }

    try:
        resp = yta.reports().query(**query).execute()
    except HttpError as e:
        print(f"[ERROR] Analytics failed for {video_id}:", e)
        return {}

    rows = resp.get("rows", [])
    headers = resp.get("columnHeaders", [])

    if not rows:
        return {}

    row = rows[0]

    idx = {h["name"]: i for i, h in enumerate(headers)}

    out: Dict[str, float | None] = {}
    for m in ANALYTICS_METRICS:
        i = idx.get(m)
        if i is not None:
            try:
                out[m] = float(row[i])
            except Exception:
                out[m] = None

    return out


def _auth_db_path() -> str:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.getenv("AUTH_DB_PATH", os.path.join(repo_root, "auth.db"))


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


def _chunked(seq: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def get_yt_analytics_bulk(
    credentials,
    video_ids: List[str],
    channel_id: Optional[str] = None,
    chunk_size: int = 50,
) -> Dict[str, Dict]:
    if not video_ids:
        return {}

    yta = build("youtubeAnalytics", "v2", credentials=credentials)
    ids = f"channel=={channel_id}" if channel_id else "channel==MINE"
    metrics = ",".join(ANALYTICS_METRICS)

    out: Dict[str, Dict] = {}
    for chunk in _chunked(video_ids, chunk_size):
        query = {
            "ids": ids,
            "startDate": "2000-01-01",
            "endDate": "2099-01-01",
            "metrics": metrics,
            "dimensions": "video",
            "filters": f"video=={','.join(chunk)}",
        }
        try:
            resp = yta.reports().query(**query).execute()
        except HttpError as e:
            print(f"[ERROR] Bulk analytics failed for chunk: {e}")
            for vid in chunk:
                out[vid] = get_yt_analytics(credentials, vid, channel_id=channel_id)
            continue

        rows = resp.get("rows", [])
        headers = resp.get("columnHeaders", [])
        if not rows or not headers:
            continue

        idx = {h["name"]: i for i, h in enumerate(headers)}
        i_video = idx.get("video")
        for row in rows:
            if i_video is None:
                continue
            vid = row[i_video]
            vals: Dict[str, float | None] = {}
            for m in ANALYTICS_METRICS:
                i = idx.get(m)
                if i is None:
                    continue
                try:
                    vals[m] = float(row[i])
                except Exception:
                    vals[m] = None
            out[vid] = vals

    return out


# ======================================================================
# LẤY THÔNG TIN VIDEO (Data API)
# ======================================================================
def get_video_snippet_map(credentials, video_ids: List[str]) -> Dict[str, Dict]:
    youtube = build("youtube", "v3", credentials=credentials)
    result: Dict[str, Dict] = {}

    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        resp = youtube.videos().list(
            part="snippet,statistics",
            id=",".join(batch),
            maxResults=50,
        ).execute()

        for item in resp.get("items", []):
            vid = item["id"]
            snip = item.get("snippet", {}) or {}
            stats = item.get("statistics", {}) or {}

            thumbs = snip.get("thumbnails", {}) or {}
            thumbnail = (
                (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get(
                    "url"
                )
                if thumbs
                else None
            )

            result[vid] = {
                "title": snip.get("title"),
                "publish_date": snip.get("publishedAt"),
                "thumbnail": thumbnail,
                "views": int(stats.get("viewCount", 0) or 0),
                "likes": int(stats.get("likeCount", 0) or 0),
                "comments": int(stats.get("commentCount", 0) or 0),
            }

    return result


# ======================================================================
# DATABASE FUNCTIONS
# ======================================================================
def create_video_overview_table(pg_url: str):
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS video_overview (
                account_tag TEXT,
                video_id TEXT,
                title TEXT,
                thumbnail TEXT,
                publish_date TEXT,
                views BIGINT,
                likes BIGINT,
                comments BIGINT,
                dislikes BIGINT,
                engaged_views BIGINT,
                annotation_click_through_rate DOUBLE PRECISION,
                annotation_close_rate DOUBLE PRECISION,
                average_view_duration_seconds DOUBLE PRECISION,
                shares BIGINT,
                subscribers_gained BIGINT,
                subscribers_lost BIGINT,
                updated_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (account_tag, video_id)
            );
        """
            )
        )
    print("[DB] video_overview table ready.")


def save_video_overview(pg_url: str, video_data: dict):
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
            INSERT INTO video_overview (
                account_tag,
                video_id, title, thumbnail, publish_date,
                views, likes, comments, dislikes, engaged_views,
                annotation_click_through_rate,
                annotation_close_rate, average_view_duration_seconds,
                shares, subscribers_gained, subscribers_lost,
                updated_at
            )
            VALUES (
                :account_tag,
                :video_id, :title, :thumbnail, :publish_date,
                :views, :likes, :comments, :dislikes, :engaged_views,
                :annotation_click_through_rate,
                :annotation_close_rate, :average_view_duration_seconds,
                :shares, :subscribers_gained, :subscribers_lost,
                NOW()
            )
            ON CONFLICT (account_tag, video_id) DO UPDATE SET
                title = EXCLUDED.title,
                thumbnail = EXCLUDED.thumbnail,
                publish_date = EXCLUDED.publish_date,
                views = EXCLUDED.views,
                likes = EXCLUDED.likes,
                comments = EXCLUDED.comments,
                dislikes = EXCLUDED.dislikes,
                engaged_views = EXCLUDED.engaged_views,
                annotation_click_through_rate = EXCLUDED.annotation_click_through_rate,
                annotation_close_rate = EXCLUDED.annotation_close_rate,
                average_view_duration_seconds = EXCLUDED.average_view_duration_seconds,
                shares = EXCLUDED.shares,
                subscribers_gained = EXCLUDED.subscribers_gained,
                subscribers_lost = EXCLUDED.subscribers_lost,
                updated_at = NOW();
        """
            ),
            video_data,
        )


# ======================================================================
# MAIN PIPELINE
# ======================================================================
def process_overall(cred_file: str, channel_id: Optional[str] = None):
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        raise RuntimeError("Missing PG_URL environment variable")

    # Chuẩn bị DB
    create_video_overview_table(pg_url)

    # Derive account_tag từ tên file credential, ví dụ: mychannel.json -> "mychannel"
    account_tag = os.path.splitext(os.path.basename(cred_file))[0]

    # Load credentials
    credentials = create_token_from_credentials(os.path.join(CREDENTIALS_FOLDER, cred_file))

    # Lấy toàn bộ video trên kênh
    playlist_id = get_upload_playlist_id(credentials, channel_id=channel_id)
    video_ids = get_video_list(credentials, playlist_id)

    print(f"[INFO] [{account_tag}] Found {len(video_ids)} videos.")

    # Snippet info
    snippet_map = get_video_snippet_map(credentials, video_ids)
    analytics_map = get_yt_analytics_bulk(credentials, video_ids, channel_id=channel_id)

    # ETL từng video
    for vid in video_ids:
        if _stop_requested():
            raise RuntimeError("Stop requested")
        print(f"[INFO] [{account_tag}] Processing video {vid} ...")

        base = snippet_map.get(vid, {})
        ana = analytics_map.get(vid, {})

        video_data = {
            "account_tag": account_tag,
            "video_id": vid,
            "title": base.get("title"),
            "thumbnail": base.get("thumbnail"),
            "publish_date": base.get("publish_date"),

            # basic stats: ưu tiên analytics, fallback sang Data API
            "views": ana.get("views") if ana.get("views") is not None else base.get("views"),
            "likes": ana.get("likes") if ana.get("likes") is not None else base.get("likes"),
            "comments": ana.get("comments")
            if ana.get("comments") is not None
            else base.get("comments"),

            "dislikes": ana.get("dislikes"),
            "engaged_views": ana.get("engagedViews"),
            "annotation_click_through_rate": ana.get("annotationClickThroughRate"),
            "annotation_close_rate": ana.get("annotationCloseRate"),
            "average_view_duration_seconds": ana.get("averageViewDuration"),
            "shares": ana.get("shares"),
            "subscribers_gained": ana.get("subscribersGained"),
            "subscribers_lost": ana.get("subscribersLost"),
        }

        save_video_overview(pg_url, video_data)

    print(f"[DONE] [{account_tag}] All videos processed & saved to database.")
