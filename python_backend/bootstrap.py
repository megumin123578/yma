from python_backend.api.auth.database import engine as sqlite_auth_engine
from python_backend.db import engine as pg_engine
from python_backend.pg_bootstrap import ensure_postgres_state
from python_backend.sqlite_auth_bootstrap import (
    create_sqlite_auth_schema,
    ensure_sqlite_auth_state,
)


def initialize_app_state() -> None:
    create_sqlite_auth_schema(sqlite_auth_engine)
    ensure_postgres_state(pg_engine)
    ensure_sqlite_auth_state(sqlite_auth_engine)
