# python_backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from python_backend.config import load_env

load_env()

from python_backend.api.auth.database import engine, Base
from python_backend.api.auth import models
from python_backend.routes.traffic_timeseries import router as ts_router
from python_backend.routes.geography import router as geo_router
from python_backend.routes.content import router as content_router
from python_backend.routes.overview import router as overview_router
from python_backend.routes.smmstore import router as smmstore_router
from python_backend.routes.channel_compare import router as channel_compare_router
from python_backend.routes.youtube import router as youtube_router
from python_backend.routes.audience import router as audience_router
from python_backend.routes.reach import router as reach_router
from python_backend.routes.revenue import router as revenue_router
from fastapi.staticfiles import StaticFiles
from python_backend.api.auth.routers import auth, user
from python_backend.api.auth.scheduler import start_scheduler

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://192.168.1.162:3000",
        "http://192.168.1.162:3001",
        "http://192.168.1.162:3002",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "https://tuanfmcaa.site",
        "https://app.tuanfmcaa.site",
        "http://tuanfmcaa.site",
        "http://app.tuanfmcaa.site",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


Base.metadata.create_all(bind=engine)


def ensure_token_progress_table():
    with engine.begin() as conn:
        conn.exec_driver_sql("""
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
        """)
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


ensure_token_progress_table()

def ensure_video_live_counter_snapshots_channel_name():
    with engine.begin() as conn:
        cols = conn.exec_driver_sql(
            "PRAGMA table_info(video_live_counter_snapshots)"
        ).fetchall()
        has_column = any(row[1] == "channel_name" for row in cols)
        if not has_column:
            conn.exec_driver_sql(
                "ALTER TABLE video_live_counter_snapshots ADD COLUMN channel_name VARCHAR"
            )


ensure_video_live_counter_snapshots_channel_name()


def ensure_user_schedule_run_columns():
    with engine.begin() as conn:
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


ensure_user_schedule_run_columns()

start_scheduler()


def ensure_user_smmstore_column():
    with engine.begin() as conn:
        columns = conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
        has_column = any(row[1] == "smmstore_api_key" for row in columns)
        if not has_column:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN smmstore_api_key VARCHAR"
            )


ensure_user_smmstore_column()


def ensure_user_credential_group_column():
    with engine.begin() as conn:
        columns = conn.exec_driver_sql("PRAGMA table_info(user_credentials)").fetchall()
        has_column = any(row[1] == "group_name" for row in columns)
        if not has_column:
            conn.exec_driver_sql(
                "ALTER TABLE user_credentials ADD COLUMN group_name VARCHAR"
            )


ensure_user_credential_group_column()


def ensure_user_credential_groups_table():
    with engine.begin() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS user_credential_groups (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                group_name VARCHAR NOT NULL,
                color VARCHAR
            );
        """)
        columns = conn.exec_driver_sql("PRAGMA table_info(user_credential_groups)").fetchall()
        has_color = any(row[1] == "color" for row in columns)
        if not has_color:
            conn.exec_driver_sql(
                "ALTER TABLE user_credential_groups ADD COLUMN color VARCHAR"
            )
        conn.exec_driver_sql("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_user_credential_group_name
            ON user_credential_groups (user_id, group_name);
        """)
        conn.exec_driver_sql("""
            INSERT OR IGNORE INTO user_credential_groups (user_id, group_name)
            SELECT user_id, group_name
            FROM user_credentials
            WHERE group_name IS NOT NULL AND TRIM(group_name) != '';
        """)


ensure_user_credential_groups_table()


def ensure_rival_channel_avatar_column():
    with engine.begin() as conn:
        columns = conn.exec_driver_sql("PRAGMA table_info(rival_channels)").fetchall()
        has_column = any(row[1] == "channel_avatar_url" for row in columns)
        if not has_column:
            conn.exec_driver_sql(
                "ALTER TABLE rival_channels ADD COLUMN channel_avatar_url VARCHAR"
            )


ensure_rival_channel_avatar_column()


def ensure_rival_channel_group_column():
    with engine.begin() as conn:
        columns = conn.exec_driver_sql("PRAGMA table_info(rival_channels)").fetchall()
        has_column = any(row[1] == "group_name" for row in columns)
        if not has_column:
            conn.exec_driver_sql(
                "ALTER TABLE rival_channels ADD COLUMN group_name VARCHAR"
            )


ensure_rival_channel_group_column()


def ensure_rival_channel_groups_table():
    with engine.begin() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS rival_channel_groups (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                channel_id VARCHAR NOT NULL,
                group_name VARCHAR NOT NULL
            );
        """)
        conn.exec_driver_sql("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_rival_group
            ON rival_channel_groups (user_id, channel_id, group_name);
        """)
        conn.exec_driver_sql("""
            INSERT OR IGNORE INTO rival_channel_groups (user_id, channel_id, group_name)
            SELECT user_id, channel_id, group_name
            FROM rival_channels
            WHERE group_name IS NOT NULL AND TRIM(group_name) != '';
        """)


ensure_rival_channel_groups_table()


def ensure_rival_groups_table():
    with engine.begin() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS rival_groups (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                group_name VARCHAR NOT NULL
            );
        """)
        conn.exec_driver_sql("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_rival_group_name
            ON rival_groups (user_id, group_name);
        """)
        conn.exec_driver_sql("""
            INSERT OR IGNORE INTO rival_groups (user_id, group_name)
            SELECT user_id, group_name
            FROM rival_channel_groups
            WHERE group_name IS NOT NULL AND TRIM(group_name) != '';
        """)


ensure_rival_groups_table()


def ensure_smmstore_analytics_cache_table():
    with engine.begin() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS smmstore_analytics_cache (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                payload TEXT NOT NULL,
                updated_at DATETIME NOT NULL
            );
        """)
        conn.exec_driver_sql("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_smmstore_user_month
            ON smmstore_analytics_cache (user_id, month);
        """)


ensure_smmstore_analytics_cache_table()


def ensure_smmstore_scheduled_orders_table():
    with engine.begin() as conn:
        conn.exec_driver_sql("""
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
        """)
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_smmstore_sched_user ON smmstore_scheduled_orders(user_id);")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_smmstore_sched_run_at ON smmstore_scheduled_orders(run_at);")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_smmstore_sched_status ON smmstore_scheduled_orders(status);")


ensure_smmstore_scheduled_orders_table()
def ensure_user_schedules_nullable_token():
    with engine.begin() as conn:
        conn.exec_driver_sql("""
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
        """)
        cols = conn.exec_driver_sql("PRAGMA table_info(user_schedules)").fetchall()
        col_map = {row[1]: row for row in cols}
        token_col = col_map.get("token_name")
        if token_col and token_col[3] == 1:
            conn.exec_driver_sql("""
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
            """)
            conn.exec_driver_sql("""
                INSERT INTO user_schedules_new
                  (id, user_id, token_name, mode, time_of_day, every_minutes, enabled, last_run_at, created_at, updated_at)
                SELECT
                  id, user_id, NULL, mode, time_of_day, every_minutes, enabled, last_run_at, created_at, updated_at
                FROM user_schedules;
            """)
            conn.exec_driver_sql("DROP TABLE user_schedules;")
            conn.exec_driver_sql("ALTER TABLE user_schedules_new RENAME TO user_schedules;")


ensure_user_schedules_nullable_token()

def ensure_user_credentials_token_name():
    with engine.begin() as conn:
        cols = conn.exec_driver_sql("PRAGMA table_info(user_credentials)").fetchall()
        has_column = any(row[1] == "token_name" for row in cols)
        if not has_column:
            conn.exec_driver_sql("ALTER TABLE user_credentials ADD COLUMN token_name VARCHAR")


ensure_user_credentials_token_name()

def ensure_user_credentials_selected_channel():
    with engine.begin() as conn:
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


ensure_user_credentials_selected_channel()

def ensure_user_credentials_avatar():
    with engine.begin() as conn:
        cols = conn.exec_driver_sql("PRAGMA table_info(user_credentials)").fetchall()
        has_avatar = any(row[1] == "selected_channel_avatar" for row in cols)
        if not has_avatar:
            conn.exec_driver_sql(
                "ALTER TABLE user_credentials ADD COLUMN selected_channel_avatar VARCHAR"
            )


ensure_user_credentials_avatar()

# CORS middleware moved to top

app.include_router(ts_router)
app.include_router(geo_router)
app.include_router(content_router)
app.include_router(overview_router)
app.include_router(smmstore_router)
app.include_router(channel_compare_router)
app.include_router(youtube_router)
app.include_router(audience_router)
app.include_router(reach_router)
app.include_router(revenue_router)
app.include_router(auth.router)
app.include_router(user.router, prefix="/api") 

app.mount(
    "/uploads",
    StaticFiles(directory="python_backend/api/uploads"),
    name="uploads",
)
