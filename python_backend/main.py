# python_backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from python_backend.config import load_env

from python_backend.api.auth.database import engine, Base
from sqlalchemy import text, create_engine
from python_backend.api.auth import models
import os
from python_backend.routes.traffic_timeseries import router as ts_router
from python_backend.routes.geography import router as geo_router
from python_backend.routes.content import router as content_router
from python_backend.routes.overview import router as overview_router
from python_backend.routes.smmstore import router as smmstore_router
from python_backend.routes.channel_compare import router as channel_compare_router
from python_backend.routes.youtube import router as youtube_router
from python_backend.routes.audience import router as audience_router
from python_backend.routes.reach import router as reach_router
from fastapi.staticfiles import StaticFiles
from python_backend.api.auth.routers import auth, user
from python_backend.api.auth.scheduler import start_scheduler

load_env()

app = FastAPI()

Base.metadata.create_all(bind=engine)

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


def ensure_rival_channel_avatar_column():
    with engine.begin() as conn:
        columns = conn.exec_driver_sql("PRAGMA table_info(rival_channels)").fetchall()
        has_column = any(row[1] == "channel_avatar_url" for row in columns)
        if not has_column:
            conn.exec_driver_sql(
                "ALTER TABLE rival_channels ADD COLUMN channel_avatar_url VARCHAR"
            )


ensure_rival_channel_avatar_column()


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

def drop_geography_daily_table():
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        return
    try:
        pg_engine = create_engine(pg_url, future=True)
        with pg_engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS geography_daily"))
    except Exception:
        pass


drop_geography_daily_table()


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ts_router)
app.include_router(geo_router)
app.include_router(content_router)
app.include_router(overview_router)
app.include_router(smmstore_router)
app.include_router(channel_compare_router)
app.include_router(youtube_router)
app.include_router(audience_router)
app.include_router(reach_router)
app.include_router(auth.router)
app.include_router(user.router, prefix="/api") 

app.mount(
    "/uploads",
    StaticFiles(directory="python_backend/api/uploads"),
    name="uploads",
)
