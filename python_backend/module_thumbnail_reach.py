import csv
import gzip
import io
import os
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from sqlalchemy import create_engine, text

try:
    from python_backend.module_trafficsource import sanitize_filename
except ModuleNotFoundError:
    from module_trafficsource import sanitize_filename
try:
    from python_backend.progress_state import write_progress
except ModuleNotFoundError:
    from progress_state import write_progress


REPORT_TYPE_ID = "channel_reach_basic_a1"
REPORT_JOB_NAME = "thumbnail_reach_daily"


def _ensure_tables(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS youtube_reporting_jobs (
                account_tag TEXT NOT NULL,
                report_type_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                token_name TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                PRIMARY KEY (account_tag, report_type_id)
            );
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS youtube_reporting_processed_reports (
                account_tag TEXT NOT NULL,
                report_type_id TEXT NOT NULL,
                report_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                processed_at TIMESTAMP NOT NULL DEFAULT NOW(),
                row_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (account_tag, report_type_id, report_id)
            );
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS video_thumbnail_daily (
                account_tag TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                video_id TEXT NOT NULL,
                day DATE NOT NULL,
                thumbnail_impressions BIGINT NOT NULL DEFAULT 0,
                thumbnail_ctr DOUBLE PRECISION,
                report_id TEXT,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                PRIMARY KEY (account_tag, video_id, day)
            );
            """
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_video_thumbnail_daily_account_day "
            "ON video_thumbnail_daily (account_tag, day);"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_video_thumbnail_daily_video_day "
            "ON video_thumbnail_daily (video_id, day);"
        )
    )


def _http_text(exc: HttpError) -> str:
    return str(exc)


def _is_reporting_api_disabled(exc: HttpError) -> bool:
    body = _http_text(exc)
    return "youtubereporting.googleapis.com" in body and "SERVICE_DISABLED" in body


def _is_scope_error(exc: HttpError) -> bool:
    body = _http_text(exc).lower()
    return "insufficient" in body and "scope" in body


def _list_reach_jobs(reporting) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
    page_token = None
    while True:
        resp = reporting.jobs().list(pageToken=page_token).execute() or {}
        jobs.extend(
            job
            for job in resp.get("jobs", []) or []
            if job.get("reportTypeId") == REPORT_TYPE_ID
        )
        page_token = resp.get("nextPageToken")
        if not page_token:
            return jobs


def _store_job(conn, account_tag: str, job_id: str, token_name: str = "") -> None:
    conn.execute(
        text(
            """
            INSERT INTO youtube_reporting_jobs (
                account_tag, report_type_id, job_id, token_name, updated_at
            )
            VALUES (
                :account_tag, :report_type_id, :job_id, :token_name, NOW()
            )
            ON CONFLICT (account_tag, report_type_id) DO UPDATE SET
                job_id = EXCLUDED.job_id,
                token_name = EXCLUDED.token_name,
                updated_at = NOW();
            """
        ),
        {
            "account_tag": account_tag,
            "report_type_id": REPORT_TYPE_ID,
            "job_id": job_id,
            "token_name": token_name,
        },
    )


def _get_or_create_job(reporting, conn, account_tag: str, token_name: str = "") -> Tuple[Optional[str], bool]:
    jobs = _list_reach_jobs(reporting)
    if jobs:
        job_id = str(jobs[0].get("id") or "").strip()
        if job_id:
            _store_job(conn, account_tag, job_id, token_name)
            return job_id, False

    job = reporting.jobs().create(
        body={
            "reportTypeId": REPORT_TYPE_ID,
            "name": REPORT_JOB_NAME,
        }
    ).execute() or {}
    job_id = str(job.get("id") or "").strip()
    if job_id:
        _store_job(conn, account_tag, job_id, token_name)
    return job_id or None, True


def _list_reports(reporting, job_id: str) -> List[Dict[str, Any]]:
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


def _processed_report_ids(conn, account_tag: str) -> set[str]:
    rows = conn.execute(
        text(
            """
            SELECT report_id
            FROM youtube_reporting_processed_reports
            WHERE account_tag = :account_tag
              AND report_type_id = :report_type_id
            """
        ),
        {"account_tag": account_tag, "report_type_id": REPORT_TYPE_ID},
    ).fetchall()
    return {str(row[0]) for row in rows if row and row[0]}


def _download_report_bytes(reporting, download_url: str) -> bytes:
    request = reporting.media().download(resourceName="")
    request.uri = download_url
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request, chunksize=-1)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    data = buffer.getvalue()
    if data.startswith(b"\x1f\x8b"):
        return gzip.decompress(data)
    return data


def _parse_report_day(value: str) -> Optional[date]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _to_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def _to_fraction(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        num = float(value)
    except Exception:
        return None
    # Reporting rate fields can be observed as either a fraction or a percent.
    # Store a fraction so Content route can consistently multiply by 100.
    if num > 1:
        return num / 100.0
    return num


def _iter_csv_rows(csv_bytes: bytes) -> Iterable[Dict[str, str]]:
    text_value = csv_bytes.decode("utf-8-sig", errors="replace")
    yield from csv.DictReader(io.StringIO(text_value))


def _upsert_thumbnail_rows(
    conn,
    account_tag: str,
    rows: Iterable[Dict[str, str]],
    report_id: str,
    selected_channel_id: str = "",
) -> int:
    count = 0
    for row in rows:
        day = _parse_report_day(row.get("date"))
        video_id = str(row.get("video_id") or "").strip()
        channel_id = str(row.get("channel_id") or selected_channel_id or "").strip()
        if not day or not video_id:
            continue
        if selected_channel_id and channel_id and channel_id != selected_channel_id:
            continue

        conn.execute(
            text(
                """
                INSERT INTO video_thumbnail_daily (
                    account_tag,
                    channel_id,
                    video_id,
                    day,
                    thumbnail_impressions,
                    thumbnail_ctr,
                    report_id,
                    updated_at
                )
                VALUES (
                    :account_tag,
                    :channel_id,
                    :video_id,
                    :day,
                    :thumbnail_impressions,
                    :thumbnail_ctr,
                    :report_id,
                    NOW()
                )
                ON CONFLICT (account_tag, video_id, day) DO UPDATE SET
                    channel_id = EXCLUDED.channel_id,
                    thumbnail_impressions = EXCLUDED.thumbnail_impressions,
                    thumbnail_ctr = EXCLUDED.thumbnail_ctr,
                    report_id = EXCLUDED.report_id,
                    updated_at = NOW();
                """
            ),
            {
                "account_tag": account_tag,
                "channel_id": channel_id,
                "video_id": video_id,
                "day": day.isoformat(),
                "thumbnail_impressions": _to_int(row.get("video_thumbnail_impressions")),
                "thumbnail_ctr": _to_fraction(row.get("video_thumbnail_impressions_ctr")),
                "report_id": report_id,
            },
        )
        count += 1
    return count


def _mark_report_processed(
    conn,
    account_tag: str,
    report: Dict[str, Any],
    row_count: int,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO youtube_reporting_processed_reports (
                account_tag,
                report_type_id,
                report_id,
                job_id,
                start_time,
                end_time,
                processed_at,
                row_count
            )
            VALUES (
                :account_tag,
                :report_type_id,
                :report_id,
                :job_id,
                :start_time,
                :end_time,
                NOW(),
                :row_count
            )
            ON CONFLICT (account_tag, report_type_id, report_id) DO UPDATE SET
                job_id = EXCLUDED.job_id,
                start_time = EXCLUDED.start_time,
                end_time = EXCLUDED.end_time,
                processed_at = NOW(),
                row_count = EXCLUDED.row_count;
            """
        ),
        {
            "account_tag": account_tag,
            "report_type_id": REPORT_TYPE_ID,
            "report_id": str(report.get("id") or ""),
            "job_id": str(report.get("jobId") or ""),
            "start_time": report.get("startTime"),
            "end_time": report.get("endTime"),
            "row_count": row_count,
        },
    )


def _clear_content_caches(conn, account_tag: str) -> None:
    for table_name in ("content_timeseries_cache", "content_video_metrics_cache"):
        try:
            conn.execute(
                text(f"DELETE FROM {table_name} WHERE account_tag = :account_tag"),
                {"account_tag": account_tag},
            )
        except Exception:
            pass


def run_thumbnail_reach_sync(
    credentials,
    account_tag: str,
    pg_url: str,
    channel_id: Optional[str] = None,
    token_name: str = "",
) -> None:
    safe_tag = sanitize_filename(account_tag)
    selected_channel_id = str(channel_id or "").strip()
    engine = create_engine(pg_url, future=True)
    reporting = build("youtubereporting", "v1", credentials=credentials)

    with engine.begin() as conn:
        _ensure_tables(conn)

    try:
        with engine.begin() as conn:
            job_id, created = _get_or_create_job(reporting, conn, safe_tag, token_name=token_name)
    except HttpError as exc:
        if _is_reporting_api_disabled(exc):
            print("[WARN] thumbnail reach skipped: YouTube Reporting API is disabled for this Google project.")
            write_progress(safe_tag, "thumbnail_reach", 0, "idle", "Enable YouTube Reporting API")
            return
        if _is_scope_error(exc):
            print("[WARN] thumbnail reach skipped: token is missing YouTube Analytics Reporting scope.")
            write_progress(safe_tag, "thumbnail_reach", 0, "idle", "Reconnect account for reporting scope")
            return
        raise

    if not job_id:
        print("[WARN] thumbnail reach skipped: could not create or find reach report job.")
        return
    if created:
        print(f"[INFO] thumbnail reach job created: {job_id}. Reports will appear after YouTube daily processing.")
        write_progress(safe_tag, "thumbnail_reach", 92, "running", "Reach report job created; waiting for reports")
        return

    reports = _list_reports(reporting, job_id)
    if not reports:
        print(f"[INFO] thumbnail reach: no reports available yet for job {job_id}.")
        write_progress(safe_tag, "thumbnail_reach", 92, "running", "No thumbnail reach reports yet")
        return

    max_reports = int(os.getenv("THUMBNAIL_REACH_MAX_REPORTS", "0") or "0")
    imported_reports = 0
    imported_rows = 0
    with engine.begin() as conn:
        processed_ids = _processed_report_ids(conn, safe_tag)
        pending_reports = [
            report
            for report in sorted(reports, key=lambda item: str(item.get("startTime") or ""))
            if str(report.get("id") or "") not in processed_ids
        ]
        if max_reports > 0:
            pending_reports = pending_reports[-max_reports:]

        total = len(pending_reports)
        if total == 0:
            print(f"[INFO] thumbnail reach: all reports already processed for {safe_tag}.")
            write_progress(safe_tag, "thumbnail_reach", 95, "running", "Thumbnail reach already up to date")
            return

        for idx, report in enumerate(pending_reports, start=1):
            report_id = str(report.get("id") or "").strip()
            download_url = str(report.get("downloadUrl") or "").strip()
            if not report_id or not download_url:
                continue
            write_progress(safe_tag, "thumbnail_reach", 90 + int((idx / total) * 8), "running", f"Importing reach report {idx}/{total}")
            csv_bytes = _download_report_bytes(reporting, download_url)
            row_count = _upsert_thumbnail_rows(
                conn,
                safe_tag,
                _iter_csv_rows(csv_bytes),
                report_id,
                selected_channel_id=selected_channel_id,
            )
            _mark_report_processed(conn, safe_tag, report, row_count)
            imported_reports += 1
            imported_rows += row_count

        if imported_reports:
            _clear_content_caches(conn, safe_tag)

    print(
        f"[INFO] thumbnail reach imported: account={safe_tag}, "
        f"reports={imported_reports}, rows={imported_rows}"
    )
    write_progress(safe_tag, "thumbnail_reach", 98, "running", f"Imported thumbnail reach reports: {imported_reports}")
