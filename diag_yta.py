
import os
import pickle
import json
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

TOKEN_DIR = "d:/dev/yt_manage_app/python_backend/token"
TOKEN_NAME = "Du_Vi_t.pickle" # Based on logs showing this channel ID

def load_creds(token_name):
    token_path = os.path.join(TOKEN_DIR, token_name)
    if not os.path.exists(token_path):
        return None
    with open(token_path, "rb") as f:
        creds = pickle.load(f)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "wb") as f:
                pickle.dump(creds, f)
    return creds

def main():
    creds = load_creds(TOKEN_NAME)
    if not creds:
        print("Creds not found")
        return

    yta = build("youtubeAnalytics", "v2", credentials=creds)
    ids = "channel==MINE"
    
    tests = [
        ("Views (Day)", {"metrics": "views", "dimensions": "day"}),
        ("Subscribers (No Dim)", {"metrics": "subscribersGained"}),
        ("Subscribers (Day)", {"metrics": "subscribersGained", "dimensions": "day"}),
        ("Subscribers (Video)", {"metrics": "subscribersGained", "dimensions": "video"}),
        ("Impressions (No Dim)", {"metrics": "videoThumbnailImpressions"}),
        ("Impressions (Video)", {"metrics": "videoThumbnailImpressions", "dimensions": "video"}),
        ("Impressions (Day)", {"metrics": "videoThumbnailImpressions", "dimensions": "day"}),
        ("Subscribers (Video) - 10 IDs", {"metrics": "subscribersGained", "dimensions": "video", "filters": "video==YOEoz0tMpVs,vjgR6kfeXvM,2oGmqdOJuwU"}),
    ]
    
    results = []
    for name, params in tests:
        q = {
            "ids": ids,
            "startDate": "2026-01-01",
            "endDate": "2026-01-31",
            **params
        }
        try:
            resp = yta.reports().query(**q).execute()
            results.append(f"SUCCESS: {name}")
        except HttpError as e:
            results.append(f"FAILED : {name} -> {e.resp.status}: {e.reason}")
        except Exception as e:
            results.append(f"ERROR  : {name} -> {str(e)}")

    with open("d:/dev/yt_manage_app/diag_results.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(results))
    print("Done")

if __name__ == "__main__":
    main()
