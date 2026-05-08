# db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from python_backend.config import load_env

load_env()

PG_URL = os.getenv("PG_URL", "").strip()
if not PG_URL:
    raise RuntimeError("Missing required environment variable: PG_URL")

# Engine
engine = create_engine(
    PG_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
    future=True,
)

# Session Factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Dependency để inject vào router FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
