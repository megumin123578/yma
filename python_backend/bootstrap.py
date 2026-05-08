from sqlalchemy.engine import Engine

from python_backend.api.auth import models  # noqa: F401
from python_backend.api.auth.database import Base, engine
from python_backend.db import engine as pg_engine


def ensure_token_progress_table(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS token_progress (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                token_name VARCHAR NOT NULL,
                account_tag VARCHAR NOT NULL,
                run_id VARCHAR,
                status VARCHAR NOT NULL,
                stage VARCHAR,
                percent INTEGER NOT NULL DEFAULT 0,
                message TEXT,
                started_at DATETIME,
                finished_at DATETIME,
                updated_at DATETIME NOT NULL
            );
            """
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_token_progress_user_token ON token_progress(user_id, token_name);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_token_progress_user ON token_progress(user_id);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_token_progress_token ON token_progress(token_name);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_token_progress_run ON token_progress(run_id);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_token_progress_updated ON token_progress(updated_at);"
        )


def ensure_users_is_admin_column(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        cols = conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
        col_names = {str(row[1]).lower() for row in cols}
        if "is_admin" not in col_names:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"
            )


def ensure_video_live_counter_snapshots_channel_name(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        cols = conn.exec_driver_sql(
            "PRAGMA table_info(video_live_counter_snapshots)"
        ).fetchall()
        has_column = any(row[1] == "channel_name" for row in cols)
        if not has_column:
            conn.exec_driver_sql(
                "ALTER TABLE video_live_counter_snapshots ADD COLUMN channel_name VARCHAR"
            )


def ensure_mail_accounts_channel_name(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        cols = conn.exec_driver_sql("PRAGMA table_info(mail_accounts)").fetchall()
        has_column = any(row[1] == "channel_name" for row in cols)
        if not has_column:
            conn.exec_driver_sql(
                "ALTER TABLE mail_accounts ADD COLUMN channel_name VARCHAR"
            )


def ensure_user_schedule_run_columns(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        columns = conn.exec_driver_sql("PRAGMA table_info(user_schedule_runs)").fetchall()
        has_token_name = any(row[1] == "token_name" for row in columns)
        has_token_names = any(row[1] == "token_names" for row in columns)
        has_run_type = any(row[1] == "run_type" for row in columns)
        if not has_token_name:
            conn.exec_driver_sql(
                "ALTER TABLE user_schedule_runs ADD COLUMN token_name VARCHAR"
            )
        if not has_token_names:
            conn.exec_driver_sql(
                "ALTER TABLE user_schedule_runs ADD COLUMN token_names TEXT"
            )
        if not has_run_type:
            conn.exec_driver_sql(
                "ALTER TABLE user_schedule_runs ADD COLUMN run_type VARCHAR"
            )


def ensure_user_smmstore_column(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        columns = conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
        has_column = any(row[1] == "smmstore_api_key" for row in columns)
        if not has_column:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN smmstore_api_key VARCHAR"
            )


def ensure_user_credential_group_column(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        columns = conn.exec_driver_sql("PRAGMA table_info(user_credentials)").fetchall()
        has_column = any(row[1] == "group_name" for row in columns)
        if not has_column:
            conn.exec_driver_sql(
                "ALTER TABLE user_credentials ADD COLUMN group_name VARCHAR"
            )


def ensure_user_credential_project_column(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        columns = conn.exec_driver_sql("PRAGMA table_info(user_credentials)").fetchall()
        has_column = any(row[1] == "project_name" for row in columns)
        if not has_column:
            conn.exec_driver_sql(
                "ALTER TABLE user_credentials ADD COLUMN project_name VARCHAR"
            )


def ensure_user_credential_groups_table(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS user_credential_groups (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                group_name VARCHAR NOT NULL,
                color VARCHAR
            );
            """
        )
        columns = conn.exec_driver_sql("PRAGMA table_info(user_credential_groups)").fetchall()
        has_color = any(row[1] == "color" for row in columns)
        if not has_color:
            conn.exec_driver_sql(
                "ALTER TABLE user_credential_groups ADD COLUMN color VARCHAR"
            )
        conn.exec_driver_sql(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_user_credential_group_name
            ON user_credential_groups (user_id, group_name);
            """
        )
        conn.exec_driver_sql(
            """
            INSERT OR IGNORE INTO user_credential_groups (user_id, group_name)
            SELECT user_id, group_name
            FROM user_credentials
            WHERE group_name IS NOT NULL AND TRIM(group_name) != '';
            """
        )


def ensure_user_credential_projects_table(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS user_credential_projects (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                group_name VARCHAR NOT NULL,
                project_name VARCHAR NOT NULL
            );
            """
        )
        conn.exec_driver_sql(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_user_credential_project_name
            ON user_credential_projects (user_id, group_name, project_name);
            """
        )
        conn.exec_driver_sql(
            """
            INSERT OR IGNORE INTO user_credential_projects (user_id, group_name, project_name)
            SELECT user_id, group_name, project_name
            FROM user_credentials
            WHERE group_name IS NOT NULL
              AND TRIM(group_name) != ''
              AND project_name IS NOT NULL
              AND TRIM(project_name) != '';
            """
        )


def ensure_rival_channel_avatar_column(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        columns = conn.exec_driver_sql("PRAGMA table_info(rival_channels)").fetchall()
        has_column = any(row[1] == "channel_avatar_url" for row in columns)
        if not has_column:
            conn.exec_driver_sql(
                "ALTER TABLE rival_channels ADD COLUMN channel_avatar_url VARCHAR"
            )


def ensure_rival_channel_group_column(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        columns = conn.exec_driver_sql("PRAGMA table_info(rival_channels)").fetchall()
        has_column = any(row[1] == "group_name" for row in columns)
        if not has_column:
            conn.exec_driver_sql(
                "ALTER TABLE rival_channels ADD COLUMN group_name VARCHAR"
            )


def ensure_rival_channel_groups_table(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS rival_channel_groups (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                channel_id VARCHAR NOT NULL,
                group_name VARCHAR NOT NULL
            );
            """
        )
        conn.exec_driver_sql(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_rival_group
            ON rival_channel_groups (user_id, channel_id, group_name);
            """
        )
        conn.exec_driver_sql(
            """
            INSERT OR IGNORE INTO rival_channel_groups (user_id, channel_id, group_name)
            SELECT user_id, channel_id, group_name
            FROM rival_channels
            WHERE group_name IS NOT NULL AND TRIM(group_name) != '';
            """
        )


def ensure_rival_groups_table(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS rival_groups (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                group_name VARCHAR NOT NULL
            );
            """
        )
        conn.exec_driver_sql(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_rival_group_name
            ON rival_groups (user_id, group_name);
            """
        )
        conn.exec_driver_sql(
            """
            INSERT OR IGNORE INTO rival_groups (user_id, group_name)
            SELECT user_id, group_name
            FROM rival_channel_groups
            WHERE group_name IS NOT NULL AND TRIM(group_name) != '';
            """
        )


def ensure_smmstore_analytics_cache_table(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS smmstore_analytics_cache (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                payload TEXT NOT NULL,
                updated_at DATETIME NOT NULL
            );
            """
        )
        conn.exec_driver_sql(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_smmstore_user_month
            ON smmstore_analytics_cache (user_id, month);
            """
        )


def ensure_smmstore_scheduled_orders_table(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS smmstore_scheduled_orders (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                run_at DATETIME NOT NULL,
                service VARCHAR NOT NULL,
                link VARCHAR NOT NULL,
                quantity VARCHAR NOT NULL,
                runs VARCHAR,
                interval VARCHAR,
                status VARCHAR NOT NULL DEFAULT 'queued',
                remote_order_id VARCHAR,
                charge VARCHAR,
                remains VARCHAR,
                last_error TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                submitted_at DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_smmstore_sched_user ON smmstore_scheduled_orders(user_id);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_smmstore_sched_run_at ON smmstore_scheduled_orders(run_at);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_smmstore_sched_status ON smmstore_scheduled_orders(status);"
        )


def ensure_user_schedules_nullable_token(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS user_schedules (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                token_name VARCHAR,
                mode VARCHAR NOT NULL,
                time_of_day VARCHAR,
                every_minutes INTEGER,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_run_at DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
            """
        )
        cols = conn.exec_driver_sql("PRAGMA table_info(user_schedules)").fetchall()
        col_map = {row[1]: row for row in cols}
        token_col = col_map.get("token_name")
        if token_col and token_col[3] == 1:
            conn.exec_driver_sql(
                """
                CREATE TABLE user_schedules_new (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    token_name VARCHAR,
                    mode VARCHAR NOT NULL,
                    time_of_day VARCHAR,
                    every_minutes INTEGER,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_run_at DATETIME,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                );
                """
            )
            conn.exec_driver_sql(
                """
                INSERT INTO user_schedules_new
                  (id, user_id, token_name, mode, time_of_day, every_minutes, enabled, last_run_at, created_at, updated_at)
                SELECT
                  id, user_id, NULL, mode, time_of_day, every_minutes, enabled, last_run_at, created_at, updated_at
                FROM user_schedules;
                """
            )
            conn.exec_driver_sql("DROP TABLE user_schedules;")
            conn.exec_driver_sql("ALTER TABLE user_schedules_new RENAME TO user_schedules;")


def ensure_user_credentials_token_name(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        cols = conn.exec_driver_sql("PRAGMA table_info(user_credentials)").fetchall()
        has_column = any(row[1] == "token_name" for row in cols)
        if not has_column:
            conn.exec_driver_sql("ALTER TABLE user_credentials ADD COLUMN token_name VARCHAR")


def ensure_user_credentials_selected_channel(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        cols = conn.exec_driver_sql("PRAGMA table_info(user_credentials)").fetchall()
        has_channel_id = any(row[1] == "selected_channel_id" for row in cols)
        if not has_channel_id:
            conn.exec_driver_sql(
                "ALTER TABLE user_credentials ADD COLUMN selected_channel_id VARCHAR"
            )
        has_channel_title = any(row[1] == "selected_channel_title" for row in cols)
        if not has_channel_title:
            conn.exec_driver_sql(
                "ALTER TABLE user_credentials ADD COLUMN selected_channel_title VARCHAR"
            )


def ensure_user_credentials_avatar(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        cols = conn.exec_driver_sql("PRAGMA table_info(user_credentials)").fetchall()
        has_avatar = any(row[1] == "selected_channel_avatar" for row in cols)
        if not has_avatar:
            conn.exec_driver_sql(
                "ALTER TABLE user_credentials ADD COLUMN selected_channel_avatar VARCHAR"
            )


def ensure_oauth_tokens_table(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS oauth_tokens (
                id INTEGER PRIMARY KEY,
                token_name VARCHAR NOT NULL,
                credentials_json TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
            """
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_oauth_tokens_token_name ON oauth_tokens(token_name);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_oauth_tokens_updated ON oauth_tokens(updated_at);"
        )


def ensure_revenue_table_pg(db_engine: Engine) -> None:
    from python_backend.module_revenue import _ensure_revenue_table

    with db_engine.begin() as conn:
        _ensure_revenue_table(conn)


def ensure_channel_daily_table_pg(db_engine: Engine) -> None:
    from python_backend.module_channel_daily import _ensure_channel_daily_table

    with db_engine.begin() as conn:
        _ensure_channel_daily_table(conn)


def ensure_video_overview_table_pg(db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS video_overview (
                account_tag TEXT,
                video_id TEXT,
                title TEXT,
                thumbnail TEXT,
                publish_date TEXT,
                views BIGINT,
                likes BIGINT,
                comments BIGINT,
                dislikes BIGINT,
                engaged_views BIGINT,
                annotation_click_through_rate DOUBLE PRECISION,
                annotation_close_rate DOUBLE PRECISION,
                average_view_duration_seconds DOUBLE PRECISION,
                shares BIGINT,
                subscribers_gained BIGINT,
                subscribers_lost BIGINT,
                updated_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (account_tag, video_id)
            );
            """
        )


def initialize_app_state() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_video_overview_table_pg(pg_engine)
    ensure_revenue_table_pg(pg_engine)
    ensure_channel_daily_table_pg(pg_engine)
    ensure_token_progress_table(engine)
    ensure_users_is_admin_column(engine)
    ensure_video_live_counter_snapshots_channel_name(engine)
    ensure_mail_accounts_channel_name(engine)
    ensure_user_schedule_run_columns(engine)
    ensure_user_smmstore_column(engine)
    ensure_user_credential_group_column(engine)
    ensure_user_credential_project_column(engine)
    ensure_user_credential_groups_table(engine)
    ensure_user_credential_projects_table(engine)
    ensure_rival_channel_avatar_column(engine)
    ensure_rival_channel_group_column(engine)
    ensure_rival_channel_groups_table(engine)
    ensure_rival_groups_table(engine)
    ensure_smmstore_analytics_cache_table(engine)
    ensure_smmstore_scheduled_orders_table(engine)
    ensure_user_schedules_nullable_token(engine)
    ensure_user_credentials_token_name(engine)
    ensure_user_credentials_selected_channel(engine)
    ensure_user_credentials_avatar(engine)
    ensure_oauth_tokens_table(engine)
