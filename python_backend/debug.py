import csv
import csv
import io
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from python_backend.config import load_env
from python_backend.token_store import (
    get_auth_db_path,
    load_token_credentials,
)


REACH_REPORT_TYPE_ID = "channel_reach_basic_a1"
REACH_JOB_NAME = "debug_thumbnail_impressions"


def _default_date_range() -> tuple[str, str]:
    end = date.today() - timedelta(days=1)
    return "2005-02-14", end.isoformat()


def _date_range_for_videos(videos: List[Dict[str, str]]) -> tuple[str, str]:
    default_start, end_date = _default_date_range()
    parsed_dates: List[date] = []
    for video in videos:
        raw_date = str(video.get("publishedAt") or "")[:10]
        try:
            parsed_dates.append(date.fromisoformat(raw_date))
        except ValueError:
            continue
    if not parsed_dates:
        return default_start, end_date

    end = date.fromisoformat(end_date)
    start = min(parsed_dates)
    if start > end:
        start = end
    return start.isoformat(), end_date


def _list_saved_channels() -> List[Dict[str, Any]]:
    conn = sqlite3.connect(get_auth_db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                uc.id,
                uc.user_id,
                uc.account_tag,
                uc.token_name,
                uc.selected_channel_id,
                uc.selected_channel_title,
                uc.updated_at
            FROM user_credentials AS uc
            JOIN oauth_tokens AS ot
              ON ot.token_name = uc.token_name
            WHERE uc.token_name IS NOT NULL
              AND TRIM(uc.token_name) != ''
              AND ot.credentials_json IS NOT NULL
              AND TRIM(ot.credentials_json) != ''
            ORDER BY
                COALESCE(uc.selected_channel_title, uc.account_tag, uc.token_name) COLLATE NOCASE ASC,
                uc.id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _display_saved_channels(channels: List[Dict[str, Any]]) -> None:
    print("")
    print("Saved channels in auth.db:")
    for idx, channel in enumerate(channels, start=1):
        title = (
            str(channel.get("selected_channel_title") or "").strip()
            or str(channel.get("account_tag") or "").strip()
            or str(channel.get("token_name") or "").strip()
            or "(untitled)"
        )
        channel_id = str(channel.get("selected_channel_id") or "").strip() or "MINE"
        token_name = str(channel.get("token_name") or "").strip()
        user_id = channel.get("user_id")
        print(f"{idx:>2}. {title} | channel_id={channel_id} | token={token_name} | user_id={user_id}")
    print("")


def _select_saved_channel(channels: List[Dict[str, Any]]) -> Dict[str, Any]:
    while True:
        raw_value = input(f"Select channel number (1-{len(channels)}): ").strip()
        try:
            selected_index = int(raw_value)
        except ValueError:
            print("Please enter a number.")
            continue
        if 1 <= selected_index <= len(channels):
            return channels[selected_index - 1]
        print(f"Please enter a number from 1 to {len(channels)}.")


def _get_latest_videos(credentials, channel_id: str, limit: int = 10) -> List[Dict[str, str]]:
    yt = build("youtube", "v3", credentials=credentials)
    channel_query: Dict[str, Any] = {
        "part": "contentDetails",
        "maxResults": 1,
    }
    if channel_id:
        channel_query["id"] = channel_id
    else:
        channel_query["mine"] = True

    channel_resp = yt.channels().list(**channel_query).execute() or {}
    channel_items = channel_resp.get("items", []) or []
    if not channel_items:
        return []

    uploads_playlist_id = (
        channel_items[0]
        .get("contentDetails", {})
        .get("relatedPlaylists", {})
        .get("uploads", "")
    )
    if not uploads_playlist_id:
        return []

    playlist_resp = yt.playlistItems().list(
        part="contentDetails,snippet",
        playlistId=uploads_playlist_id,
        maxResults=max(1, min(int(limit or 10), 50)),
    ).execute() or {}

    videos: List[Dict[str, str]] = []
    for item in playlist_resp.get("items", []) or []:
        video_id = str(
            item.get("contentDetails", {}).get("videoId")
            or item.get("snippet", {}).get("resourceId", {}).get("videoId")
            or ""
        ).strip()
        if not video_id:
            continue
        videos.append(
            {
                "video": video_id,
                "title": str(item.get("snippet", {}).get("title") or "").strip(),
                "publishedAt": str(
                    item.get("contentDetails", {}).get("videoPublishedAt")
                    or item.get("snippet", {}).get("publishedAt")
                    or ""
                ).strip(),
            }
        )
    return videos[:limit]


def _http_error_text(exc: HttpError) -> str:
    return str(exc)


def _is_reporting_api_disabled(exc: HttpError) -> bool:
    return "youtubereporting.googleapis.com" in _http_error_text(exc) and "SERVICE_DISABLED" in _http_error_text(exc)


def _list_reach_jobs(reporting) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
    page_token = None
    while True:
        resp = reporting.jobs().list(pageToken=page_token).execute() or {}
        jobs.extend(
            job for job in resp.get("jobs", []) or []
            if job.get("reportTypeId") == REACH_REPORT_TYPE_ID
        )
        page_token = resp.get("nextPageToken")
        if not page_token:
            return jobs


def _get_or_create_reach_job(reporting) -> tuple[Optional[str], bool]:
    jobs = _list_reach_jobs(reporting)
    if jobs:
        return str(jobs[0].get("id") or "").strip(), False

    job = reporting.jobs().create(
        body={
            "reportTypeId": REACH_REPORT_TYPE_ID,
            "name": REACH_JOB_NAME,
        }
    ).execute() or {}
    return str(job.get("id") or "").strip(), True


def _parse_report_date(value: str) -> Optional[date]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _list_reach_reports(reporting, job_id: str) -> List[Dict[str, Any]]:
    reports: List[Dict[str, Any]] = []
    page_token = None
    while True:
        resp = reporting.jobs().reports().list(
            jobId=job_id,
            pageToken=page_token,
            pageSize=100,
        ).execute() or {}
        reports.extend(resp.get("reports", []) or [])
        page_token = resp.get("nextPageToken")
        if not page_token:
            return reports


def _download_report_csv(reporting, download_url: str) -> str:
    request = reporting.media().download(resourceName="")
    request.uri = download_url
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request, chunksize=-1)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue().decode("utf-8", errors="replace")


def _sum_impressions_from_reports(
    reporting,
    reports: List[Dict[str, Any]],
    video_ids: List[str],
    start_date: str,
    end_date: str,
) -> Dict[str, Optional[int]]:
    target_ids = set(video_ids)
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    out: Dict[str, Optional[int]] = {video_id: None for video_id in video_ids}

    for report in sorted(reports, key=lambda item: str(item.get("startTime") or "")):
        report_start = _parse_report_date(report.get("startTime"))
        report_end = _parse_report_date(report.get("endTime"))
        if report_start and report_start > end:
            continue
        if report_end and report_end <= start:
            continue

        download_url = str(report.get("downloadUrl") or "").strip()
        if not download_url:
            continue

        csv_text = _download_report_csv(reporting, download_url)
        for row in csv.DictReader(io.StringIO(csv_text)):
            video_id = str(row.get("video_id") or "").strip()
            if video_id not in target_ids:
                continue

            row_date = _parse_report_date(row.get("date"))
            if row_date and not (start <= row_date <= end):
                continue

            try:
                impressions = int(float(row.get("video_thumbnail_impressions") or 0))
            except Exception:
                impressions = 0
            out[video_id] = int(out.get(video_id) or 0) + impressions

    return out


def _query_thumbnail_impressions_from_reporting(
    credentials,
    video_ids: List[str],
    start_date: str,
    end_date: str,
) -> Optional[Dict[str, Optional[int]]]:
    reporting = build("youtubereporting", "v1", credentials=credentials)
    try:
        job_id, created = _get_or_create_reach_job(reporting)
    except HttpError as exc:
        if _is_reporting_api_disabled(exc):
            print("")
            print("[ERROR] YouTube Analytics bulk reports are disabled for this Google Cloud project.")
            print("Thumbnail impressions are only available through the reach bulk report endpoint.")
            print("Enable YouTube Reporting API, then run the script again:")
            print("https://console.developers.google.com/apis/api/youtubereporting.googleapis.com/overview?project=480264422080")
            print("")
            return None
        raise

    if not job_id:
        print("[ERROR] Could not create or find YouTube Reporting reach job.")
        return None

    if created:
        print("")
        print(f"Created YouTube Reporting job: {job_id}")
        print("Analytics bulk reports are generated later by YouTube, usually after daily processing. Run this script again after reports appear.")
        print("")
        return None

    reports = _list_reach_reports(reporting, job_id)
    if not reports:
        print("")
        print(f"Reach job exists ({job_id}), but no generated Analytics bulk reports are available yet.")
        print("Run this script again after YouTube has generated the reach report.")
        print("")
        return None

    return _sum_impressions_from_reports(reporting, reports, video_ids, start_date, end_date)


def _merge_latest_videos_with_metrics(
    videos: List[Dict[str, str]],
    impressions_by_video: Dict[str, Optional[int]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for video in videos:
        video_id = video["video"]
        out.append(
            {
                "video": video_id,
                "title": video.get("title", ""),
                "publishedAt": video.get("publishedAt", ""),
                "videoThumbnailImpressions": impressions_by_video.get(video_id),
            }
        )
    return out


def _shorten(value: Any, width: int) -> str:
    text = str(value or "")
    if len(text) <= width:
        return text
    return text[: max(0, width - 3)] + "..."


def _print_result_table(rows: List[Dict[str, Any]]) -> None:
    print("")
    print("Latest 10 videos - thumbnail impressions")
    print(
        f"{'#':>2}  {'video':<13}  {'published':<10}  {'thumb_impr':>12}  title"
    )
    print("-" * 78)
    for idx, row in enumerate(rows, start=1):
        published = str(row.get("publishedAt") or "")[:10]
        print(
            f"{idx:>2}  "
            f"{_shorten(row.get('video'), 13):<13}  "
            f"{published:<10}  "
            f"{'' if row.get('videoThumbnailImpressions') is None else int(row.get('videoThumbnailImpressions') or 0):>12}  "
            f"{_shorten(row.get('title'), 50)}"
        )
    print("")


def main() -> int:
    load_env()

    channels = _list_saved_channels()
    if not channels:
        print("No saved channel with OAuth token found in auth.db.")
        return 1

    _display_saved_channels(channels)
    selected_channel = _select_saved_channel(channels)

    token_name = str(selected_channel.get("token_name") or "").strip()
    channel_id = str(selected_channel.get("selected_channel_id") or "").strip()
    title = (
        str(selected_channel.get("selected_channel_title") or "").strip()
        or str(selected_channel.get("account_tag") or "").strip()
        or token_name
    )

    try:
        credentials = load_token_credentials(token_name)
        videos = _get_latest_videos(credentials, channel_id=channel_id, limit=10)
        if not videos:
            print(f"No latest videos found for channel: {title}")
            return 1

        start_date, end_date = _date_range_for_videos(videos)
        video_ids = [video["video"] for video in videos]
        impressions_by_video = _query_thumbnail_impressions_from_reporting(
            credentials=credentials,
            start_date=start_date,
            end_date=end_date,
            video_ids=video_ids,
        )
        if impressions_by_video is None:
            return 1
    except HttpError as exc:
        print("[ERROR] YouTube API request failed.")
        print(exc)
        return 1

    rows = _merge_latest_videos_with_metrics(videos, impressions_by_video)
    _print_result_table(rows)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
