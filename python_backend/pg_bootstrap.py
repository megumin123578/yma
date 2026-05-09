from sqlalchemy.engine import Engine


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
        conn.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS idx_video_overview_account_publish
            ON video_overview (account_tag, publish_date DESC);
            """
        )

def ensure_postgres_state(db_engine: Engine) -> None:
    ensure_video_overview_table_pg(db_engine)
    ensure_revenue_table_pg(db_engine)
    ensure_channel_daily_table_pg(db_engine)