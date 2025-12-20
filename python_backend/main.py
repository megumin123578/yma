# python_backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from python_backend.config import load_env

from python_backend.api.auth.database import engine, Base
from sqlalchemy import text
from python_backend.api.auth import models

from python_backend.routes.traffic_timeseries import router as ts_router
from python_backend.routes.geography import router as geo_router
from python_backend.routes.content import router as content_router
from python_backend.routes.overview import router as overview_router
from python_backend.routes.smmstore import router as smmstore_router
from python_backend.routes.channel_compare import router as channel_compare_router
from python_backend.routes.youtube import router as youtube_router
from fastapi.staticfiles import StaticFiles
from python_backend.api.auth.routers import auth, user

load_env()

app = FastAPI()

Base.metadata.create_all(bind=engine)


def ensure_user_smmstore_column():
    with engine.begin() as conn:
        columns = conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
        has_column = any(row[1] == "smmstore_api_key" for row in columns)
        if not has_column:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN smmstore_api_key VARCHAR"
            )


ensure_user_smmstore_column()

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
app.include_router(auth.router)
app.include_router(user.router, prefix="/api") 

app.mount(
    "/uploads",
    StaticFiles(directory="python_backend/api/uploads"),
    name="uploads",
)
