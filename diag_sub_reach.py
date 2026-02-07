
import os
import pickle
import json
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

TOKEN_DIR = "d:/dev/yt_manage_app/python_backend/token"
TOKEN_NAME = "Du_Vi_t.pickle"

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
    
    # Let's test standard core metrics first
    # Maybe subscribersGained is restricted or only available in certain combinations
    
    video_id = "YOEoz0tMpVs" # One of user's videos
    
    tests = [
        ("Subscribers Total", {"metrics": "subscribersGained"}),
        ("Views Total", {"metrics": "views"}),
        ("Impressions Total (No Dim)", {"metrics": "videoThumbnailImpressions"}),
    ]
    
    results = []
    for name, params in tests:
        q = {
            "ids": ids,
            "startDate": "2024-01-01",
            "endDate": "2025-12-31", # Fixed dates
            **params
        }
        try:
            resp = yta.reports().query(**q).execute()
            rows = resp.get("rows") or []
            results.append(f"SUCCESS: {name} -> Rows: {len(rows)} | Sample: {rows[0] if rows else 'None'}")
        except HttpError as e:
            results.append(f"FAILED : {name} -> {e.resp.status}: {e.reason}")
        except Exception as e:
            results.append(f"ERROR  : {name} -> {str(e)}")

    with open("d:/dev/yt_manage_app/diag_sub_reach.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(results))
    print("Done checking subs and impressions")

if __name__ == "__main__":
    main()
