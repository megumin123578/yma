import os
import sqlite3
import sys
from pathlib import Path

from sqlalchemy import create_engine, text


def load_env() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
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


def print_section(title: str) -> None:
    print()
    print(f"=== {title} ===")


def main() -> int:
    load_env()
    account_tag = sys.argv[1] if len(sys.argv) > 1 else "Thomas___Friends_World"

    pg_url = os.getenv(
        "PG_URL",
        "postgresql+psycopg2://postgres:V!etdu1492003@localhost:5432/analytics",
    )
    admin_usernames = os.getenv("ADMIN_USERNAME", "admin")
    auth_db_path = Path(__file__).resolve().parent.parent / "auth.db"

    print_section("Runtime")
    print(f"account_tag={account_tag}")
    print(f"PG_URL set={bool(pg_url)}")
    print(f"ADMIN_USERNAME={admin_usernames}")
    print(f"auth_db={auth_db_path}")

    engine = create_engine(pg_url, future=True)
    with engine.connect() as conn:
        print_section("Traffic Source Rows")
        count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM traffic_source_daily
                WHERE account_tag = :tag
                """
            ),
            {"tag": account_tag},
        ).scalar()
        print(f"row_count={count}")

        min_max = conn.execute(
            text(
                """
                SELECT MIN(day), MAX(day)
                FROM traffic_source_daily
                WHERE account_tag = :tag
                """
            ),
            {"tag": account_tag},
        ).fetchone()
        print(f"min_day={min_max[0]} max_day={min_max[1]}")

        latest_sources = conn.execute(
            text(
                """
                SELECT source, SUM(views) AS views
                FROM traffic_source_daily
                WHERE account_tag = :tag
                  AND day >= CURRENT_DATE - INTERVAL '28 day'
                GROUP BY source
                ORDER BY views DESC, source ASC
                LIMIT 10
                """
            ),
            {"tag": account_tag},
        ).fetchall()
        print("last_28d_top_sources=")
        for row in latest_sources:
            print(f"  {row[0]}: {row[1]}")

        distinct_tags = conn.execute(
            text(
                """
                SELECT DISTINCT account_tag
                FROM traffic_source_daily
                WHERE account_tag ILIKE :needle
                ORDER BY account_tag
                """
            ),
            {"needle": "%Thomas%"},
        ).fetchall()
        print("matching_account_tags=")
        for row in distinct_tags:
            print(f"  {row[0]}")

    print_section("Auth DB")
    conn = sqlite3.connect(auth_db_path)
    try:
        cur = conn.cursor()
        print("users:")
        for row in cur.execute("SELECT id, username FROM users ORDER BY username"):
            print(f"  id={row[0]} username={row[1]}")

        print("credentials_for_channel:")
        for row in cur.execute(
            """
            SELECT u.username, uc.account_tag, uc.token_name, uc.selected_channel_title
            FROM user_credentials uc
            LEFT JOIN users u ON u.id = uc.user_id
            WHERE uc.account_tag = ?
            ORDER BY u.username
            """,
            (account_tag,),
        ):
            print(
                f"  username={row[0]} account_tag={row[1]} token_name={row[2]} title={row[3]}"
            )

        print("hidden_channel_rows:")
        for row in cur.execute(
            """
            SELECT u.username, h.account_tag
            FROM user_hidden_channels h
            LEFT JOIN users u ON u.id = h.user_id
            WHERE h.account_tag = ?
            ORDER BY u.username
            """,
            (account_tag,),
        ):
            print(f"  username={row[0]} hidden_tag={row[1]}")
    finally:
        conn.close()

    print_section("Next Check")
    print("If row_count=0: production has no traffic source data for this channel.")
    print("If row_count>0 but credentials_for_channel empty: user/channel mapping is missing.")
    print("If hidden_channel_rows has your username: the channel is hidden for that user.")
    print("If ADMIN_USERNAME is wrong: restart backend after fixing env.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
