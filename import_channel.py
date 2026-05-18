import json
import sqlite3
import sys
from datetime import datetime

if len(sys.argv) < 2:
    print("Usage: python import_channel.py <channel_TOKEN.json> [DST_DB_PATH] [ADMIN_USER_ID]")
    sys.exit(1)

JSON_PATH = sys.argv[1]
DST_DB = sys.argv[2] if len(sys.argv) > 2 else r"D:/dev/yt_manage_app/auth.db"
ADMIN_USER_ID = int(sys.argv[3]) if len(sys.argv) > 3 else 1

with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

dst = sqlite3.connect(DST_DB, timeout=30)
dst.execute("PRAGMA busy_timeout = 30000")

ot = data["oauth_tokens"]
dst.execute(
    """
    INSERT INTO oauth_tokens(token_name, credentials_json, created_at, updated_at)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(token_name) DO UPDATE SET
      credentials_json = excluded.credentials_json,
      updated_at = excluded.updated_at
    """,
    (ot["token_name"], ot["credentials_json"], ot["created_at"], ot["updated_at"]),
)
print(f"oauth_tokens upserted: {ot['token_name']}")

uc = data.get("user_credential")
if uc:
    now = datetime.utcnow().isoformat()
    dst.execute(
        """
        INSERT INTO user_credentials(
            user_id, account_tag, token_name, project_name,
            selected_channel_id, selected_channel_title, selected_channel_avatar,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, account_tag) DO UPDATE SET
          token_name = excluded.token_name,
          selected_channel_id = excluded.selected_channel_id,
          selected_channel_title = excluded.selected_channel_title,
          selected_channel_avatar = excluded.selected_channel_avatar,
          updated_at = excluded.updated_at
        """,
        (
            ADMIN_USER_ID,
            uc["account_tag"],
            uc["token_name"],
            uc["project_name"],
            uc["selected_channel_id"],
            uc["selected_channel_title"],
            uc["selected_channel_avatar"],
            now,
            now,
        ),
    )
    print(f"user_credentials upserted for user_id={ADMIN_USER_ID}")

dst.commit()
print("Done.")
