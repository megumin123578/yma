import argparse
import json
import os
import pickle
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "python_backend"
TOKEN_DIR = BACKEND_DIR / "token"
DEFAULT_ACCOUNT_TAG = "Number_A"
DEFAULT_RANGE_DAYS = 28
DEFAULT_METRICS = [
    "cpm",
]


def resolve_auth_db_path() -> Path:
    candidates = [
        ROOT_DIR / "auth.db",
        BACKEND_DIR / "auth.db",
    ]
    for path in candidates:
        if path.exists() and path.stat().st_size > 0:
            return path
    return candidates[0]


AUTH_DB_PATH = resolve_auth_db_path()


def load_env() -> None:
    env_path = BACKEND_DIR / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and (os.getenv(key) is None or os.getenv(key, "").strip() == ""):
            os.environ[key] = value


def sanitize_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-\.]", "_", value.strip().replace(" ", "_"))


def print_section(title: str) -> None:
    print()
    print(f"=== {title} ===")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Debug YouTube Analytics metrics using existing token."
    )
    parser.add_argument(
        "account_tag",
        nargs="?",
        default=DEFAULT_ACCOUNT_TAG,
        help="Account tag from user_credentials.account_tag.",
    )
    parser.add_argument(
        "--start",
        default=None,
        help=f"Start date in YYYY-MM-DD format. Omit with --end to use last {DEFAULT_RANGE_DAYS} days.",
    )
    parser.add_argument(
        "--end",
        default=None,
        help=f"End date in YYYY-MM-DD format. Omit with --start to use last {DEFAULT_RANGE_DAYS} days.",
    )
    parser.add_argument(
        "--metrics",
        dest="metrics",
        action="append",
        default=[],
        help="Metrics to query. Can be passed multiple times or as comma-separated values.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print raw API response payloads.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available credentials and exit.",
    )
    return parser.parse_args()


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def normalize_items(values: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values or []:
        for part in str(value).split(","):
            item = part.strip()
            if not item or item in seen:
                continue
            seen.add(item)
            out.append(item)
    return out


def normalize_metric_name(value: str) -> str:
    return str(value or "").strip().rstrip("*").strip()


def normalize_metric_list(values: List[str]) -> List[str]:
    return [metric for metric in (normalize_metric_name(item) for item in normalize_items(values)) if metric]


def resolve_requested_metrics(values: List[str]) -> List[str]:
    requested = normalize_metric_list(values)
    if requested:
        return requested
    return DEFAULT_METRICS.copy()


def resolve_range(start_value: Optional[str], end_value: Optional[str]) -> Tuple[date, date]:
    if bool(start_value) != bool(end_value):
        raise ValueError("Provide both --start and --end, or neither.")
    if start_value and end_value:
        start_date = parse_date(start_value)
        end_date = parse_date(end_value)
    else:
        end_date = date.today()
        start_date = end_date - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    if start_date > end_date:
        raise ValueError("start date must be <= end date.")
    return start_date, end_date


def iter_credentials() -> Iterable[sqlite3.Row]:
    if not AUTH_DB_PATH.exists():
        raise FileNotFoundError(f"auth.db not found at {AUTH_DB_PATH}")
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                account_tag,
                token_name,
                selected_channel_id,
                selected_channel_title,
                updated_at
            FROM user_credentials
            WHERE token_name IS NOT NULL
              AND TRIM(token_name) <> ''
            ORDER BY datetime(updated_at) DESC, id DESC
            """
        ).fetchall()
    finally:
        conn.close()
    return rows


def list_credentials() -> None:
    print_section("Available Credentials")
    seen = set()
    rows = list(iter_credentials())
    if not rows:
        print("No credential rows with token_name were found.")
        return
    for row in rows:
        account_tag = row["account_tag"] or ""
        if not account_tag or account_tag in seen:
            continue
        seen.add(account_tag)
        title = row["selected_channel_title"] or ""
        channel_id = row["selected_channel_id"] or ""
        token_name = row["token_name"] or ""
        updated_at = row["updated_at"] or ""
        print(
            f"- account_tag={account_tag} | title={title or '-'} | "
            f"channel_id={channel_id or '-'} | token={token_name} | updated_at={updated_at or '-'}"
        )


def find_credential(account_tag: str) -> Optional[Dict[str, str]]:
    needle = (account_tag or "").strip()
    if not needle:
        return None
    needle_sanitized = sanitize_filename(needle)
    rows = list(iter_credentials())

    for row in rows:
        row_tag = (row["account_tag"] or "").strip()
        if row_tag == needle:
            return dict(row)

    for row in rows:
        row_tag = (row["account_tag"] or "").strip()
        if sanitize_filename(row_tag) in {needle, needle_sanitized}:
            return dict(row)

    return None


def load_token_credentials(token_name: str):
    token_path = TOKEN_DIR / token_name
    if not token_name or not token_path.exists():
        return None, token_path
    try:
        with open(token_path, "rb") as handle:
            creds = pickle.load(handle)
    except Exception:
        return None, token_path

    if not creds:
        return None, token_path

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, "wb") as handle:
                    pickle.dump(creds, handle)
            except Exception:
                return None, token_path
        else:
            return None, token_path

    return creds, token_path


def decode_http_error(exc: HttpError) -> str:
    content = getattr(exc, "content", b"")
    if isinstance(content, bytes):
        try:
            return content.decode("utf-8", errors="replace")
        except Exception:
            return repr(content)
    return str(content or exc)


def compact_request_payload(params: Dict[str, object]) -> Dict[str, object]:
    return {key: value for key, value in params.items() if value is not None}


def fetch_thumbnail_metrics(
    creds,
    channel_id: Optional[str],
    start_date: date,
    end_date: date,
    requested_metrics: List[str],
) -> Tuple[Optional[Dict[str, Optional[float]]], Dict, Optional[str]]:
    yta = build("youtubeAnalytics", "v2", credentials=creds)
    metrics_text = ",".join(requested_metrics)
    ids_value = f"channel=={channel_id}" if channel_id else "channel==MINE"
    request = compact_request_payload(
        {
            "ids": ids_value,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "metrics": metrics_text,
        }
    )
    try:
        response = yta.reports().query(**request).execute() or {}
    except HttpError as exc:
        return None, request, decode_http_error(exc)

    rows = response.get("rows") or []
    headers = response.get("columnHeaders") or []
    if not rows or not headers:
        return None, request, None

    index_by_name = {header["name"]: idx for idx, header in enumerate(headers)}
    row = rows[0]
    metric: Dict[str, Optional[float]] = {}
    for metric_name in requested_metrics:
        metric_idx = index_by_name.get(metric_name)
        if metric_idx is None:
            metric[metric_name] = None
            continue
        raw_value = row[metric_idx]
        if raw_value in (None, ""):
            metric[metric_name] = None
            continue
        try:
            text = str(raw_value).strip()
            metric[metric_name] = (
                int(text) if re.fullmatch(r"-?\d+", text) else float(text)
            )
        except Exception:
            metric[metric_name] = raw_value

    return metric, request, None


def format_metric_pairs(metric_values: Optional[Dict[str, Optional[float]]], metric_names: List[str]) -> str:
    if metric_values is None:
        return "no row returned"
    return " | ".join(
        f"{metric_name}={metric_values.get(metric_name)}"
        for metric_name in metric_names
    )


def main() -> int:
    load_env()
    args = parse_args()

    if args.list:
        list_credentials()
        return 0

    try:
        start_date, end_date = resolve_range(args.start, args.end)
    except ValueError as exc:
        print(f"Invalid date range: {exc}")
        return 2

    requested_metrics = resolve_requested_metrics(args.metrics)

    credential = find_credential(args.account_tag)
    if not credential:
        print(f"Credential not found for account_tag={args.account_tag!r}")
        print("Use --list to inspect available account tags.")
        return 1

    creds, token_path = load_token_credentials(credential.get("token_name") or "")
    if not creds:
        print(
            f"Failed to load valid credentials from token={credential.get('token_name')!r} "
            f"at {token_path}"
        )
        return 1

    channel_id = credential.get("selected_channel_id") or None

    metric_values, request_payload, error_text = fetch_thumbnail_metrics(
        creds,
        channel_id,
        start_date,
        end_date,
        requested_metrics,
    )

    print_section("Query")
    print(f"ids={request_payload.get('ids')}")
    print(f"metrics={','.join(requested_metrics)}")

    if args.raw:
        print_section("Request")
        print(json.dumps(request_payload, indent=2, ensure_ascii=True))

    if error_text:
        print_section("Error")
        print(error_text)
        return 1

    print_section("Result")
    if metric_values is None:
        print("No row returned.")
        if args.raw:
            print("The request executed successfully, but YouTube Analytics returned no rows.")
        return 0

    print(format_metric_pairs(metric_values, requested_metrics))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
