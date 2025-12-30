import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import create_engine, text

try:
    from python_backend.module_trafficsource import sanitize_filename
except ModuleNotFoundError:
    from module_trafficsource import sanitize_filename


def _date_range_from_env() -> Tuple[str, str]:
    lookback_raw = os.getenv("REACH_LOOKBACK_DAYS", "").strip()
    if lookback_raw.isdigit():
        days = int(lookback_raw)
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=max(days - 1, 0))
        return start_date.isoformat(), end_date.isoformat()
    return "2005-02-14", datetime.utcnow().date().isoformat()


def _ensure_reach_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS reach_video_metrics (
                account_tag TEXT NOT NULL,
                video_id TEXT NOT NULL,
                title TEXT,
                thumbnail TEXT,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                views BIGINT DEFAULT 0,
                estimated_minutes_watched BIGINT DEFAULT 0,
                annotation_impressions BIGINT DEFAULT 0,
                card_impressions BIGINT DEFAULT 0,
                teaser_impressions BIGINT DEFAULT 0,
                total_impressions BIGINT DEFAULT 0,
                annotation_clicks BIGINT DEFAULT 0,
                card_clicks BIGINT DEFAULT 0,
                teaser_clicks BIGINT DEFAULT 0,
                total_clicks BIGINT DEFAULT 0,
                annotation_ctr DOUBLE PRECISION,
                card_ctr DOUBLE PRECISION,
                teaser_ctr DOUBLE PRECISION,
                total_ctr DOUBLE PRECISION,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                PRIMARY KEY (account_tag, video_id, start_date, end_date)
            );
            """
        )
    )


def _load_video_meta(pg_url: str, account_tag: str) -> Dict[str, Dict]:
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT video_id, title, thumbnail
                FROM videos
                WHERE account_tag = :acct
                """
            ),
            {"acct": account_tag},
        ).fetchall()
    return {r[0]: {"title": r[1], "thumbnail": r[2]} for r in rows}

def _list_video_ids(pg_url: str, account_tag: str) -> List[str]:
    max_videos = int(os.getenv("REACH_MAX_VIDEOS", "20"))
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT video_id
                FROM videos
                WHERE account_tag = :acct
                ORDER BY views DESC NULLS LAST
                LIMIT :limit
                """
            ),
            {"acct": account_tag, "limit": max_videos},
        ).fetchall()
    return [r[0] for r in rows]


def fetch_reach(
    credentials,
    pg_url: str,
    account_tag: str,
    channel_id: Optional[str] = None,
) -> Tuple[List[Dict], str, str]:
    start_date, end_date = _date_range_from_env()
    yta = build("youtubeAnalytics", "v2", credentials=credentials)
    ids = f"channel=={channel_id}" if channel_id else "channel==MINE"
    base_query = {
        "ids": ids,
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": "video",
        "sort": "-views",
    }
    primary_metrics = [
        "views",
        "estimatedMinutesWatched",
        "annotationImpressions",
        "annotationClicks",
        "annotationClickThroughRate",
        "cardImpressions",
        "cardClicks",
        "cardClickRate",
        "cardTeaserImpressions",
        "cardTeaserClicks",
        "cardTeaserClickRate",
    ]
    fallback_metrics = [
        "views",
        "estimatedMinutesWatched",
        "cardImpressions",
        "cardClicks",
        "cardClickRate",
        "cardTeaserImpressions",
        "cardTeaserClicks",
        "cardTeaserClickRate",
    ]
    try:
        resp = yta.reports().query(**{**base_query, "metrics": ",".join(primary_metrics)}).execute() or {}
    except HttpError:
        try:
            resp = yta.reports().query(**{**base_query, "metrics": ",".join(fallback_metrics)}).execute() or {}
        except HttpError:
            return _fetch_reach_per_video(yta, pg_url, account_tag, start_date, end_date, channel_id=channel_id)

    rows = resp.get("rows") or []
    max_videos = int(os.getenv("REACH_MAX_VIDEOS", "20"))
    if max_videos > 0:
        rows = rows[:max_videos]
    headers = [h["name"] for h in resp.get("columnHeaders", [])]
    idx = {h: i for i, h in enumerate(headers)}

    out = []
    for row in rows:
        def val(name, default=0):
            i = idx.get(name)
            if i is None:
                return default
            try:
                return float(row[i]) if name.endswith("Rate") or name.endswith("ThroughRate") else int(row[i] or 0)
            except Exception:
                return default

        video_id = row[idx["video"]]
        annotation_impressions = int(val("annotationImpressions", 0))
        card_impressions = int(val("cardImpressions", 0))
        teaser_impressions = int(val("cardTeaserImpressions", 0))
        annotation_clicks = int(val("annotationClicks", 0))
        card_clicks = int(val("cardClicks", 0))
        teaser_clicks = int(val("cardTeaserClicks", 0))
        total_impressions = annotation_impressions + card_impressions + teaser_impressions
        total_clicks = annotation_clicks + card_clicks + teaser_clicks
        total_ctr = (total_clicks / total_impressions) if total_impressions > 0 else None

        print(f"[INFO] [reach] Processing video {video_id}...")
        out.append(
            {
                "video_id": video_id,
                "views": int(val("views", 0)),
                "estimated_minutes_watched": int(val("estimatedMinutesWatched", 0)),
                "annotation_impressions": annotation_impressions,
                "card_impressions": card_impressions,
                "teaser_impressions": teaser_impressions,
                "total_impressions": total_impressions,
                "annotation_clicks": annotation_clicks,
                "card_clicks": card_clicks,
                "teaser_clicks": teaser_clicks,
                "total_clicks": total_clicks,
                "annotation_ctr": val("annotationClickThroughRate", None),
                "card_ctr": val("cardClickRate", None),
                "teaser_ctr": val("cardTeaserClickRate", None),
                "total_ctr": total_ctr,
            }
        )

    return out, start_date, end_date


def _fetch_reach_per_video(
    yta,
    pg_url: str,
    account_tag: str,
    start_date: str,
    end_date: str,
    channel_id: Optional[str] = None,
) -> Tuple[List[Dict], str, str]:
    warned = False
    video_ids = _list_video_ids(pg_url, account_tag)
    if not video_ids:
        return [], start_date, end_date

    metrics = [
        "views",
        "estimatedMinutesWatched",
        "cardImpressions",
        "cardClicks",
        "cardTeaserImpressions",
        "cardTeaserClicks",
    ]
    out = []
    for vid in video_ids:
        print(f"[INFO] [reach] Processing video {vid}...")
        ids = f"channel=={channel_id}" if channel_id else "channel==MINE"
        query = {
            "ids": ids,
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": "day",
            "filters": f"video=={vid}",
            "metrics": ",".join(metrics),
        }
        try:
            resp = yta.reports().query(**query).execute() or {}
        except HttpError:
            if not warned:
                print("[WARN] reach per-video query failed for some videos.")
                warned = True
            continue

        rows = resp.get("rows") or []
        headers = [h["name"] for h in resp.get("columnHeaders", [])]
        idx = {h: i for i, h in enumerate(headers)}
        sums = {
            "views": 0,
            "estimatedMinutesWatched": 0,
            "cardImpressions": 0,
            "cardClicks": 0,
            "cardTeaserImpressions": 0,
            "cardTeaserClicks": 0,
        }
        for row in rows:
            for key in sums:
                i = idx.get(key)
                if i is None:
                    continue
                try:
                    sums[key] += int(row[i] or 0)
                except Exception:
                    pass

        card_impressions = sums["cardImpressions"]
        card_clicks = sums["cardClicks"]
        teaser_impressions = sums["cardTeaserImpressions"]
        teaser_clicks = sums["cardTeaserClicks"]
        total_impressions = card_impressions + teaser_impressions
        total_clicks = card_clicks + teaser_clicks

        out.append(
            {
                "video_id": vid,
                "views": sums["views"],
                "estimated_minutes_watched": sums["estimatedMinutesWatched"],
                "annotation_impressions": 0,
                "card_impressions": card_impressions,
                "teaser_impressions": teaser_impressions,
                "total_impressions": total_impressions,
                "annotation_clicks": 0,
                "card_clicks": card_clicks,
                "teaser_clicks": teaser_clicks,
                "total_clicks": total_clicks,
                "annotation_ctr": None,
                "card_ctr": (card_clicks / card_impressions) if card_impressions else None,
                "teaser_ctr": (teaser_clicks / teaser_impressions) if teaser_impressions else None,
                "total_ctr": (total_clicks / total_impressions) if total_impressions else None,
            }
        )
    return out, start_date, end_date


def save_reach(pg_url: str, account_tag: str, rows: List[Dict], start_date: str, end_date: str) -> None:
    if not rows:
        return
    safe_tag = sanitize_filename(account_tag)
    meta = _load_video_meta(pg_url, safe_tag)
    engine = create_engine(pg_url, future=True)
    with engine.begin() as conn:
        _ensure_reach_table(conn)
        for row in rows:
            meta_row = meta.get(row["video_id"], {})
            conn.execute(
                text(
                    """
                    INSERT INTO reach_video_metrics (
                        account_tag, video_id, title, thumbnail,
                        start_date, end_date, views, estimated_minutes_watched,
                        annotation_impressions, card_impressions, teaser_impressions, total_impressions,
                        annotation_clicks, card_clicks, teaser_clicks, total_clicks,
                        annotation_ctr, card_ctr, teaser_ctr, total_ctr, updated_at
                    )
                    VALUES (
                        :account_tag, :video_id, :title, :thumbnail,
                        :start_date, :end_date, :views, :estimated_minutes_watched,
                        :annotation_impressions, :card_impressions, :teaser_impressions, :total_impressions,
                        :annotation_clicks, :card_clicks, :teaser_clicks, :total_clicks,
                        :annotation_ctr, :card_ctr, :teaser_ctr, :total_ctr, NOW()
                    )
                    ON CONFLICT (account_tag, video_id, start_date, end_date)
                    DO UPDATE SET
                        title = EXCLUDED.title,
                        thumbnail = EXCLUDED.thumbnail,
                        views = EXCLUDED.views,
                        estimated_minutes_watched = EXCLUDED.estimated_minutes_watched,
                        annotation_impressions = EXCLUDED.annotation_impressions,
                        card_impressions = EXCLUDED.card_impressions,
                        teaser_impressions = EXCLUDED.teaser_impressions,
                        total_impressions = EXCLUDED.total_impressions,
                        annotation_clicks = EXCLUDED.annotation_clicks,
                        card_clicks = EXCLUDED.card_clicks,
                        teaser_clicks = EXCLUDED.teaser_clicks,
                        total_clicks = EXCLUDED.total_clicks,
                        annotation_ctr = EXCLUDED.annotation_ctr,
                        card_ctr = EXCLUDED.card_ctr,
                        teaser_ctr = EXCLUDED.teaser_ctr,
                        total_ctr = EXCLUDED.total_ctr,
                        updated_at = NOW();
                    """
                ),
                {
                    "account_tag": safe_tag,
                    "video_id": row["video_id"],
                    "title": meta_row.get("title"),
                    "thumbnail": meta_row.get("thumbnail"),
                    "start_date": start_date,
                    "end_date": end_date,
                    "views": row["views"],
                    "estimated_minutes_watched": row["estimated_minutes_watched"],
                    "annotation_impressions": row["annotation_impressions"],
                    "card_impressions": row["card_impressions"],
                    "teaser_impressions": row["teaser_impressions"],
                    "total_impressions": row["total_impressions"],
                    "annotation_clicks": row["annotation_clicks"],
                    "card_clicks": row["card_clicks"],
                    "teaser_clicks": row["teaser_clicks"],
                    "total_clicks": row["total_clicks"],
                    "annotation_ctr": row["annotation_ctr"],
                    "card_ctr": row["card_ctr"],
                    "teaser_ctr": row["teaser_ctr"],
                    "total_ctr": row["total_ctr"],
                },
            )


def run_reach_analytics(
    credentials,
    account_tag: str,
    pg_url: str,
    channel_id: Optional[str] = None,
) -> None:
    rows, start_date, end_date = fetch_reach(credentials, pg_url, account_tag, channel_id=channel_id)
    save_reach(pg_url, account_tag, rows, start_date, end_date)
