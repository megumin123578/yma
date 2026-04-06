import os
import csv
from datetime import datetime
from typing import Tuple, Dict, Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from python_backend.token_store import load_token_credentials


SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.monetary.readonly",
]

TOKEN_NAME = os.environ.get("TOKEN_NAME", "abc").strip()
OUTPUT_FILE = "youtube_revenue.csv"

CONTENT_OWNER_ID = os.environ.get("CONTENT_OWNER_ID", "").strip()
IS_OWNER_MODE = bool(CONTENT_OWNER_ID)


def get_credentials() -> Credentials:
    if not TOKEN_NAME:
        raise FileNotFoundError("Missing TOKEN_NAME")

    creds: Credentials = load_token_credentials(TOKEN_NAME)

    granted = set(getattr(creds, "scopes", []) or [])
    required = set(SCOPES)
    if not required.issubset(granted):
        missing = ", ".join(sorted(required - granted))
        raise PermissionError(
            "Current token is missing revenue scopes.\n"
            f"Missing: {missing}\n"
            "Re-authorize with 'yt-analytics.monetary.readonly'."
        )

    return creds


def _ids_params() -> Tuple[str, Dict[str, Any]]:
    if IS_OWNER_MODE:
        return f"contentOwner=={CONTENT_OWNER_ID}", {"onBehalfOfContentOwner": CONTENT_OWNER_ID}
    return "channel==MINE", {}


def get_revenue(start_date: str, end_date: str, currency: str = "USD") -> Dict[str, Any]:
    creds = get_credentials()
    yta = build("youtubeAnalytics", "v2", credentials=creds)

    ids, extra = _ids_params()
    req = {
        "ids": ids,
        "startDate": start_date,
        "endDate": end_date,
        "metrics": "estimatedRevenue",
        "dimensions": "day",
        "currency": currency,
        **extra,
    }

    return yta.reports().query(**req).execute()


def save_to_csv(response: Dict[str, Any], output_file: str) -> None:
    headers = ["date", "estimatedRevenue"]
    rows = response.get("rows", []) or []

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    print(f"Saved {len(rows)} rows to {output_file}")


if __name__ == "__main__":
    start_date = "2025-01-01"
    end_date = datetime.today().strftime("%Y-%m-%d")

    try:
        resp = get_revenue(start_date, end_date, currency="USD")
        save_to_csv(resp, OUTPUT_FILE)

        for row in resp.get("rows", []) or []:
            print("Date:", row[0], "Revenue:", row[1])

    except PermissionError as e:
        print("Permission error:", e)

    except HttpError as e:
        print("HTTP Error:", getattr(e, "status_code", "unknown"))
        print((getattr(e, "content", b"") or b"")[:600])

    except Exception as e:
        print("Unexpected error:", repr(e))
