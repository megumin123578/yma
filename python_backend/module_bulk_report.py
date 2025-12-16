import os
from io import FileIO
from typing import Dict, List, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from module_trafficsource import create_token_from_credentials, sanitize_filename


def build_reporting_service(credentials):
    # YouTube Reporting API
    return build("youtubereporting", "v1", credentials=credentials)


def list_all_report_types(ytr, on_behalf_of_content_owner: Optional[str] = None) -> List[Dict]:
    kwargs = {}
    if on_behalf_of_content_owner:
        kwargs["onBehalfOfContentOwner"] = on_behalf_of_content_owner

    out: List[Dict] = []
    req = ytr.reportTypes().list(**kwargs)
    while req is not None:
        resp = req.execute() or {}
        out.extend(resp.get("reportTypes", []) or [])
        req = ytr.reportTypes().list_next(req, resp)
    return out


def list_all_jobs(ytr, on_behalf_of_content_owner: Optional[str] = None) -> List[Dict]:
    kwargs = {}
    if on_behalf_of_content_owner:
        kwargs["onBehalfOfContentOwner"] = on_behalf_of_content_owner

    out: List[Dict] = []
    req = ytr.jobs().list(**kwargs)
    while req is not None:
        resp = req.execute() or {}
        out.extend(resp.get("jobs", []) or [])
        req = ytr.jobs().list_next(req, resp)
    return out


def ensure_job_for_report_type(
    ytr,
    report_type_id: str,
    existing_jobs_by_report_type: Dict[str, str],
    on_behalf_of_content_owner: Optional[str] = None
) -> str:
    if report_type_id in existing_jobs_by_report_type:
        return existing_jobs_by_report_type[report_type_id]

    body = {"reportTypeId": report_type_id, "name": f"job::{report_type_id}"}
    kwargs = {}
    if on_behalf_of_content_owner:
        kwargs["onBehalfOfContentOwner"] = on_behalf_of_content_owner

    job = ytr.jobs().create(body=body, **kwargs).execute()
    job_id = job["id"]
    existing_jobs_by_report_type[report_type_id] = job_id
    return job_id


def list_reports_for_job(ytr, job_id: str, on_behalf_of_content_owner: Optional[str] = None) -> List[Dict]:
    kwargs = {"jobId": job_id}
    if on_behalf_of_content_owner:
        kwargs["onBehalfOfContentOwner"] = on_behalf_of_content_owner

    out: List[Dict] = []
    req = ytr.jobs().reports().list(**kwargs)
    while req is not None:
        resp = req.execute() or {}
        out.extend(resp.get("reports", []) or [])
        req = ytr.jobs().reports().list_next(req, resp)
    return out


def download_report(ytr, report_url: str, local_file: str):
    """
    Official sample pattern: call reporting_api.media().download(...) then override request.uri = report_url
    """
    os.makedirs(os.path.dirname(local_file), exist_ok=True)

    request = ytr.media().download(resourceName="")
    request.uri = report_url

    with FileIO(local_file, mode="wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def download_all_bulk_reports(
    cred_file: str,
    out_dir: str = "yt_bulk_reports",
    on_behalf_of_content_owner: Optional[str] = None
):
    cred_path = os.path.join("credentials", cred_file)
    credentials = create_token_from_credentials(cred_path)

    account_tag = sanitize_filename(os.path.splitext(cred_file)[0])
    ytr = build_reporting_service(credentials)

    # 1) report types available
    report_types = list_all_report_types(ytr, on_behalf_of_content_owner=on_behalf_of_content_owner)
    if not report_types:
        print("No report types available for this account.")
        return

    # 2) existing jobs -> map by reportTypeId
    jobs = list_all_jobs(ytr, on_behalf_of_content_owner=on_behalf_of_content_owner)
    jobs_by_rt: Dict[str, str] = {}
    for j in jobs:
        rt_id = j.get("reportTypeId")
        j_id = j.get("id")
        if rt_id and j_id:
            jobs_by_rt[rt_id] = j_id

    print(f"Report types: {len(report_types)} | Existing jobs: {len(jobs_by_rt)}")

    # 3) ensure a job per report type
    for rt in report_types:
        rt_id = rt["id"]
        try:
            ensure_job_for_report_type(
                ytr,
                report_type_id=rt_id,
                existing_jobs_by_report_type=jobs_by_rt,
                on_behalf_of_content_owner=on_behalf_of_content_owner
            )
        except HttpError as e:
            print(f"[WARN] Cannot create/ensure job for {rt_id}: {e}")

    # 4) download all reports for all jobs
    downloaded = 0
    skipped = 0

    for rt_id, job_id in jobs_by_rt.items():
        try:
            reports = list_reports_for_job(ytr, job_id, on_behalf_of_content_owner=on_behalf_of_content_owner)
        except HttpError as e:
            print(f"[WARN] Cannot list reports for job {job_id} ({rt_id}): {e}")
            continue

        for rep in reports:
            rep_id = rep.get("id")
            url = rep.get("downloadUrl")
            if not rep_id or not url:
                continue

            st = (rep.get("startTime") or "na").replace(":", "").replace("-", "")
            et = (rep.get("endTime") or "na").replace(":", "").replace("-", "")
            local_path = os.path.join(out_dir, account_tag, rt_id, f"{st}_{et}_{rep_id}.csv")

            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                skipped += 1
                continue

            try:
                download_report(ytr, url, local_path)
                downloaded += 1
                print(f"Downloaded: {local_path}")
            except HttpError as e:
                print(f"[WARN] Download failed ({rt_id} / {rep_id}): {e}")

    print(f"DONE. downloaded={downloaded}, skipped_existing={skipped}")


# Example usage:
download_all_bulk_reports("megumin.json", out_dir="reports")
