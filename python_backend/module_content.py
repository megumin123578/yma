from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import json
import sqlite3
from datetime import date, timedelta
from typing import List, Dict, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import create_engine, text

from module_trafficsource import (
    create_token_from_credentials,
    sanitize_filename,
    TOKEN_FOLDER,
)
try:
    from python_backend.token_store import account_tag_from_token_name
except ModuleNotFoundError:
    from token_store import account_tag_from_token_name

CONTENT_DAILY_LOOKBACK_DAYS = int(os.getenv("CONTENT_DAILY_LOOKBACK_DAYS", "28"))
CONTENT_DAILY_FULL_BACKFILL_LOOKBACK_DAYS = int(
    os.getenv("CONTENT_DAILY_FULL_BACKFILL_LOOKBACK_DAYS", "0")
)


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, str(default)) or "").strip()
    try:
        return int(raw)
    except Exception:
        return default


CONTENT_DAILY_MAX_WORKERS = max(1, min(_env_int("CONTENT_DAILY_MAX_WORKERS", 4), 8))


class ContentChannelAccessError(RuntimeError):
    pass


def _http_error_payload(exc: HttpError) -> dict:
    content = getattr(exc, "content", b"") or b""
    if not content:
        return {}
    if isinstance(content, bytes):
        try:
            return json.loads(content.decode("utf-8", errors="ignore"))
        except Exception:
            return {}
    try:
        return json.loads(str(content))
    except Exception:
        return {}


def _iter_http_error_reasons(payload: dict) -> list[str]:
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return []
    errors = error.get("errors")
    if isinstance(errors, list):
        return [
            str(item.get("reason") or "").strip()
            for item in errors
            if isinstance(item, dict) and str(item.get("reason") or "").strip()
        ]
    details = error.get("details")
    if isinstance(details, list):
        return [
            str(item.get("reason") or "").strip()
            for item in details
            if isinstance(item, dict) and str(item.get("reason") or "").strip()
        ]
    return []


def _raise_content_channel_access_error(exc: HttpError, channel_id: Optional[str] = None) -> None:
    payload = _http_error_payload(exc)
    reasons = {reason.lower() for reason in _iter_http_error_reasons(payload)}
    status = int(getattr(getattr(exc, "resp", None), "status", 0) or 0)
    if status == 401 and "youtubesignuprequired" in reasons:
        target = f" for channel {channel_id}" if channel_id else ""
        raise ContentChannelAccessError(
            f"Reconnect this account or reselect the channel{target}."
        ) from None


def get_upload_playlist_id(credentials, channel_id: Optional[str] = None):
    yt = build("youtube", "v3", credentials=credentials)
    try:
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
    except HttpError as exc:
        _raise_content_channel_access_error(exc, channel_id=channel_id)
        raise

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
            part="snippet,contentDetails,statistics,status",
            id=",".join(chunk)
        ).execute()

        for item in resp.get("items", []):
            stats = item.get("statistics", {})
            thumbnails = item.get("snippet", {}).get("thumbnails", {}) or {}
            medium_thumbnail = (
                (thumbnails.get("medium") or {}).get("url")
                or (thumbnails.get("high") or {}).get("url")
                or (thumbnails.get("default") or {}).get("url")
                or ""
            )

            results.append({
                "video_id": item["id"],
                "title": item["snippet"]["title"],
                "thumbnail": medium_thumbnail,
                "published_at": item["snippet"]["publishedAt"][:10],
                "duration": item["contentDetails"]["duration"],
                "privacy_status": str((item.get("status") or {}).get("privacyStatus") or "").strip().lower(),
                "tags": item["snippet"].get("tags", []),
                "views": int(stats.get("viewCount", 0) or 0),
                "likes": int(stats.get("likeCount", 0) or 0),
                "comments": int(stats.get("commentCount", 0) or 0),

                # reach impressions (filled later)
                "card_impressions": 0,
                "ad_impressions": 0,
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
            metrics="videoThumbnailImpressionsClickRate",
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
            "metrics": "cardImpressions,cardTeaserImpressions",
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
            out[vid] = {
                "card_impressions": card,
                "ad_impressions": teaser,
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


def _chunked_rows(rows: List[Dict], size: int) -> List[List[Dict]]:
    return [rows[i:i + size] for i in range(0, len(rows), size)]


def _resolve_content_daily_workers(video_count: int) -> int:
    return max(1, min(CONTENT_DAILY_MAX_WORKERS, max(1, video_count)))


def _resolve_daily_start_date(
    video_row: Dict,
    full_backfill: bool,
    recent_start_date: str,
    end_date: str,
) -> str:
    published_at = str(video_row.get("published_at") or "").strip()
    if not published_at:
        return recent_start_date if not full_backfill else end_date
    return published_at if full_backfill else max(published_at, recent_start_date)


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
            "metrics": "videoThumbnailImpressionsClickRate",
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
        i_ctr = idx.get("videoThumbnailImpressionsClickRate")
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
    
    def _query_daily(metrics: List[str], label: str) -> Dict[str, Dict]:
        q = {
            "ids": ids,
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": "day",
            "filters": f"video=={video_id}",
            "metrics": ",".join(metrics),
            "sort": "day",
        }
        try:
            resp = yta.reports().query(**q).execute() or {}
        except Exception as e:
            print(f"[WARN] Daily {label} failed for {video_id}: {e}")
            return {}

        rows = resp.get("rows") or []
        headers = resp.get("columnHeaders", []) or []
        if not rows or not headers:
            return {}

        idx = {h["name"]: i for i, h in enumerate(headers)}
        i_day = idx.get("day")
        if i_day is None:
            return {}

        out: Dict[str, Dict] = {}
        for row in rows:
            day = row[i_day]
            out[day] = {}
            for m in metrics:
                i_m = idx.get(m)
                if i_m is not None:
                    out[day][m] = row[i_m]
        return out

    def _to_int(v) -> int:
        try:
            return int(v or 0)
        except Exception:
            return 0

    def _to_float(v) -> float:
        try:
            return float(v or 0.0)
        except Exception:
            return 0.0

    def _to_optional_int(v):
        if v is None or v == "":
            return None
        try:
            return int(v)
        except Exception:
            return None

    def _to_optional_float(v):
        if v is None or v == "":
            return None
        try:
            return float(v)
        except Exception:
            return None

    # Core metrics first (must-have). If this fails, no daily row should be saved.
    core = _query_daily(
        ["views", "estimatedMinutesWatched", "averageViewDuration", "likes", "subscribersGained"],
        "core",
    )
    if not core:
        print(f"[ERROR] Failed core daily analytics for {video_id}")
        return []

    engagement_extra = _query_daily(
        ["averageViewPercentage", "engagedViews"],
        "engagement_extra",
    )

    all_days = sorted(core.keys())
    results = []
    for day in all_days:
        c = core.get(day, {})
        extra = engagement_extra.get(day, {})
        results.append(
            {
                "video_id": video_id,
                "day": day,
                "views": _to_int(c.get("views")),
                "estimated_minutes": _to_int(c.get("estimatedMinutesWatched")),
                "average_view_duration": _to_int(c.get("averageViewDuration")),
                "average_view_percentage": _to_optional_float(extra.get("averageViewPercentage")),
                "engaged_views": _to_optional_int(extra.get("engagedViews")),
                "likes": _to_int(c.get("likes")),
                "subscribers_gained": _to_int(c.get("subscribersGained")),
                "estimated_revenue": 0.0,
                "card_impressions": 0,
                "card_clicks": 0,
            }
        )

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
                privacy_status TEXT,
                tags TEXT,
                ctr NUMERIC DEFAULT 0
            );
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_videos_account_tag ON videos(account_tag);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_videos_account_published ON videos(account_tag, published_at DESC);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_vds_video_day ON video_daily_stats(video_id, day);"))
        conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS tags TEXT;"))
        conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS card_impressions BIGINT DEFAULT 0;"))
        conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS ad_impressions BIGINT DEFAULT 0;"))
        conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS privacy_status TEXT;"))
        if not videos:
            return

        params = [
            {
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
                "privacy_status": str(v.get("privacy_status") or "").strip().lower() or None,
                "tags": json.dumps(v.get("tags") or []),
                "ctr": v.get("ctr", 0.0),
            }
            for v in videos
        ]
        upsert_stmt = text("""
            INSERT INTO videos
                (video_id, account_tag, title, thumbnail,
                 published_at, duration, views, likes, comments,
                 card_impressions, ad_impressions, privacy_status, tags, ctr)
            VALUES
                (:id, :acct, :title, :thumb, :pub, :duration,
                 :views, :likes, :comments,
                 :card, :ad, :privacy_status, :tags, :ctr)
            ON CONFLICT(video_id)
            DO UPDATE SET
                views = EXCLUDED.views,
                likes = EXCLUDED.likes,
                comments = EXCLUDED.comments,
                card_impressions = EXCLUDED.card_impressions,
                ad_impressions = EXCLUDED.ad_impressions,
                privacy_status = EXCLUDED.privacy_status,
                tags = EXCLUDED.tags,
                ctr = EXCLUDED.ctr;
        """)
        for batch in _chunked_rows(params, 500):
            conn.execute(upsert_stmt, batch)


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
                average_view_percentage DOUBLE PRECISION,
                engaged_views INTEGER,
                likes INTEGER,
                subscribers_gained INTEGER DEFAULT 0,
                estimated_revenue NUMERIC DEFAULT 0,
                card_impressions INTEGER DEFAULT 0,
                card_clicks INTEGER DEFAULT 0,
                PRIMARY KEY (video_id, day)
            );
        """))
        # Migration for existing tables
        try:
            conn.execute(text("ALTER TABLE video_daily_stats ADD COLUMN IF NOT EXISTS average_view_percentage DOUBLE PRECISION;"))
            conn.execute(text("ALTER TABLE video_daily_stats ADD COLUMN IF NOT EXISTS engaged_views INTEGER;"))
            conn.execute(text("ALTER TABLE video_daily_stats ADD COLUMN IF NOT EXISTS subscribers_gained INTEGER DEFAULT 0;"))
            conn.execute(text("ALTER TABLE video_daily_stats ADD COLUMN IF NOT EXISTS estimated_revenue NUMERIC DEFAULT 0;"))
            conn.execute(text("ALTER TABLE video_daily_stats ADD COLUMN IF NOT EXISTS card_impressions INTEGER DEFAULT 0;"))
            conn.execute(text("ALTER TABLE video_daily_stats ADD COLUMN IF NOT EXISTS card_clicks INTEGER DEFAULT 0;"))
        except Exception:
            pass
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_vds_day ON video_daily_stats(day);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_vds_day_video ON video_daily_stats(day, video_id);"))
        if not daily_rows:
            return

        params = [
            {
                "id": r["video_id"],
                "day": r["day"],
                "views": r["views"],
                "emw": r["estimated_minutes"],
                "avd": r["average_view_duration"],
                "avp": r.get("average_view_percentage"),
                "eng": r.get("engaged_views"),
                "likes": r["likes"],
                "subs": r["subscribers_gained"],
                "rev": r["estimated_revenue"],
                "ci": r["card_impressions"],
                "cc": r["card_clicks"],
            }
            for r in daily_rows
        ]
        upsert_stmt = text("""
            INSERT INTO video_daily_stats
                (video_id, day, views, estimated_minutes, average_view_duration,
                 average_view_percentage, engaged_views, likes, 
                 subscribers_gained, estimated_revenue,
                 card_impressions, card_clicks)
            VALUES
                (:id, :day, :views, :emw, :avd, :avp, :eng, :likes, :subs, :rev, :ci, :cc)
            ON CONFLICT (video_id, day)
            DO UPDATE SET
                views = EXCLUDED.views,
                estimated_minutes = EXCLUDED.estimated_minutes,
                average_view_duration = EXCLUDED.average_view_duration,
                average_view_percentage = EXCLUDED.average_view_percentage,
                engaged_views = EXCLUDED.engaged_views,
                likes = EXCLUDED.likes,
                subscribers_gained = EXCLUDED.subscribers_gained,
                estimated_revenue = EXCLUDED.estimated_revenue,
                card_impressions = EXCLUDED.card_impressions,
                card_clicks = EXCLUDED.card_clicks;
        """)
        for batch in _chunked_rows(params, 1000):
            conn.execute(upsert_stmt, batch)


def _ensure_content_sync_state(conn) -> None:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS content_sync_state (
            account_tag TEXT PRIMARY KEY,
            backfill_complete BOOLEAN NOT NULL DEFAULT FALSE,
            last_daily_sync_date DATE,
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """))


def _get_content_sync_state(pg_url: str, account_tag: str) -> Dict:
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        _ensure_content_sync_state(conn)
        row = conn.execute(
            text("""
                SELECT account_tag, backfill_complete, last_daily_sync_date
                FROM content_sync_state
                WHERE account_tag = :tag
            """),
            {"tag": account_tag},
        ).mappings().first()
        return dict(row) if row else {}


def _mark_content_sync_complete(pg_url: str, account_tag: str, last_daily_sync_date: str) -> None:
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        _ensure_content_sync_state(conn)
        conn.execute(
            text("""
                INSERT INTO content_sync_state (account_tag, backfill_complete, last_daily_sync_date, updated_at)
                VALUES (:tag, TRUE, :last_daily_sync_date, NOW())
                ON CONFLICT (account_tag)
                DO UPDATE SET
                    backfill_complete = TRUE,
                    last_daily_sync_date = EXCLUDED.last_daily_sync_date,
                    updated_at = NOW()
            """),
            {"tag": account_tag, "last_daily_sync_date": last_daily_sync_date},
        )


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


def _fetch_daily_rows_for_video(
    credentials,
    video_row: Dict,
    recent_start_date: str,
    end_date: str,
    channel_id: Optional[str],
    full_backfill: bool,
) -> List[Dict]:
    video_id = video_row["video_id"]
    start_date = _resolve_daily_start_date(
        video_row,
        full_backfill=full_backfill,
        recent_start_date=recent_start_date,
        end_date=end_date,
    )
    return get_video_daily_analytics(
        credentials,
        video_id,
        start_date,
        end_date,
        channel_id=channel_id,
    )


# ============================
# RUNNER
# ============================

def run_content_v3_hybrid(
    credentials,
    account_tag,
    pg_url,
    channel_id: Optional[str] = None,
    force_full_backfill: bool = False,
):
    playlist_id = get_upload_playlist_id(credentials, channel_id=channel_id)
    if not playlist_id:
        print("Không tìm thấy uploads playlist.")
        return

    end_date = date.today().isoformat()
    recent_start_date = (date.today() - timedelta(days=max(0, CONTENT_DAILY_LOOKBACK_DAYS - 1))).isoformat()
    sync_state = _get_content_sync_state(pg_url, account_tag)
    full_backfill = force_full_backfill or not bool(sync_state.get("backfill_complete"))

    print("→ Fetching video list...")
    video_ids = get_video_list(credentials, playlist_id)
    print(f"→ Found {len(video_ids)} videos")

    print("→ Fetching video metadata...")
    videos = get_video_metadata(credentials, video_ids)

    print("→ Saving metadata to PostgreSQL...")
    save_metadata(videos, account_tag, pg_url)
    if full_backfill:
        lookback_days = max(0, CONTENT_DAILY_FULL_BACKFILL_LOOKBACK_DAYS)
        if lookback_days > 0:
            recent_start_date = (date.today() - timedelta(days=max(0, lookback_days - 1))).isoformat()
            print(
                "-> Fetching DAILY analytics via YouTube Analytics API "
                f"(full backfill, last {lookback_days} days window)..."
            )
        else:
            print("-> Fetching DAILY analytics via YouTube Analytics API (full backfill)...")
    else:
        print(
            "-> Fetching DAILY analytics via YouTube Analytics API "
            f"(recent {CONTENT_DAILY_LOOKBACK_DAYS} days)..."
        )
    daily_rows = []
    daily_workers = _resolve_content_daily_workers(len(videos))
    print(f"[INFO] [content] Daily workers: {daily_workers}")

    if daily_workers == 1:
        for v in videos:
            if _stop_requested():
                raise RuntimeError("Stop requested")
            video_id = v["video_id"]
            print(f"[INFO] [content] Daily video: {video_id}")
            daily_rows.extend(
                _fetch_daily_rows_for_video(
                    credentials,
                    v,
                    recent_start_date,
                    end_date,
                    channel_id,
                    full_backfill,
                )
            )
    else:
        future_to_video_id = {}
        with ThreadPoolExecutor(
            max_workers=daily_workers,
            thread_name_prefix="content-daily",
        ) as executor:
            for v in videos:
                if _stop_requested():
                    raise RuntimeError("Stop requested")
                future = executor.submit(
                    _fetch_daily_rows_for_video,
                    credentials,
                    v,
                    recent_start_date,
                    end_date,
                    channel_id,
                    full_backfill,
                )
                future_to_video_id[future] = v["video_id"]

            for future in as_completed(future_to_video_id):
                if _stop_requested():
                    for pending_future in future_to_video_id:
                        pending_future.cancel()
                    raise RuntimeError("Stop requested")
                video_id = future_to_video_id[future]
                print(f"[INFO] [content] Daily video: {video_id}")
                try:
                    daily_rows.extend(future.result())
                except Exception as e:
                    print(f"[WARN] Daily analytics failed for {video_id}: {e}")

    print("→ Saving daily stats...")
    save_daily_stats(daily_rows, pg_url)
    _mark_content_sync_complete(pg_url, account_tag, end_date)
    invalidate_content_timeseries_cache(pg_url, account_tag)

    print("[DONE] Metadata + DAILY stats saved successfully")


def process_content(cred_file: str, channel_id: Optional[str] = None, force_full_backfill: bool = False):
    cred_path = os.path.join(TOKEN_FOLDER, cred_file)
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        raise RuntimeError("Missing PG_URL env var")

    credentials = create_token_from_credentials(cred_path)
    account_tag = sanitize_filename(account_tag_from_token_name(cred_file))

    run_content_v3_hybrid(
        credentials,
        account_tag,
        pg_url,
        channel_id=channel_id,
        force_full_backfill=force_full_backfill,
    )
