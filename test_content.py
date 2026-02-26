import os
from datetime import date
from dotenv import load_dotenv

load_dotenv("python_backend/.env")
os.environ["SQLALCHEMY_DATABASE_URI"] = os.environ.get("PG_URL", "")

from sqlalchemy.orm import Session
from python_backend.db import engine
from python_backend.routes.content import content_list, ContentListRequest, _find_credential_row

def main():
    _session = Session(engine)
    try:
        from python_backend.api.auth.models import UserCredential
        from sqlalchemy import text
        # Just grab any tag that exists in videos
        res = _session.execute(text("SELECT account_tag FROM videos LIMIT 1")).mappings().first()
        if not res:
            print("No videos found.")
            return

        tag = res["account_tag"]
        print(f"Testing with account_tag: {tag}")
        
        req = ContentListRequest(
            start=date(2026, 2, 1),
            end=date(2026, 2, 26),
            channelId=tag
        )

        res = content_list(req, _session, current_user=None)
        
        items = res.get("items", [])
        print(f"Number of items: {len(items)}")
        
        if items:
            print(f"First item full payload: {items[0]}")
        
        for item in items[:5]:
            print(f"Video: {item.get('videoId')} - {item.get('title')}")
            print(f"  Views: {item.get('views')} | Watch Time: {item.get('watchTimeHours')} | Subscribers: {item.get('subscribers')} | Revenue: {item.get('estimatedRevenue')}")
            print("---")
            
    except Exception as e:
        print("ERROR:", e)
    finally:
        _session.close()

if __name__ == "__main__":
    main()
