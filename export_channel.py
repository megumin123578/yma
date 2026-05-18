import json
import sqlite3
import sys

TOKEN_NAME = sys.argv[1] if len(sys.argv) > 1 else "999_ASMR_Crunchy"
SRC_DB = r"D:/dev/yt_manage_app/auth.db"

src = sqlite3.connect(SRC_DB)
ot = src.execute(
    "SELECT token_name, credentials_json, created_at, updated_at "
    "FROM oauth_tokens WHERE token_name = ?",
    (TOKEN_NAME,),
).fetchone()
if not ot:
    print(f"oauth_tokens row not found for token_name={TOKEN_NAME}")
    sys.exit(1)

uc = src.execute(
    "SELECT account_tag, token_name, project_name, "
    "selected_channel_id, selected_channel_title, selected_channel_avatar "
    "FROM user_credentials WHERE token_name = ? LIMIT 1",
    (TOKEN_NAME,),
).fetchone()

data = {
    "oauth_tokens": {
        "token_name": ot[0],
        "credentials_json": ot[1],
        "created_at": ot[2],
        "updated_at": ot[3],
    },
    "user_credential": (
        {
            "account_tag": uc[0],
            "token_name": uc[1],
            "project_name": uc[2],
            "selected_channel_id": uc[3],
            "selected_channel_title": uc[4],
            "selected_channel_avatar": uc[5],
        }
        if uc
        else None
    ),
}

out_path = f"channel_{TOKEN_NAME}.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"Exported {out_path}")
