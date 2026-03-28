import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from python_backend.config import load_env

load_env()

from python_backend.api.auth.routers import auth, user
from python_backend.api.auth.scheduler import start_scheduler, stop_scheduler
from python_backend.bootstrap import initialize_app_state
from python_backend.routes.audience import router as audience_router
from python_backend.routes.channel_compare import router as channel_compare_router
from python_backend.routes.content import router as content_router
from python_backend.routes.geography import router as geo_router
from python_backend.routes.mail import router as mail_router
from python_backend.routes.overview import router as overview_router
from python_backend.routes.reach import router as reach_router
from python_backend.routes.revenue import router as revenue_router
from python_backend.routes.smmstore import router as smmstore_router
from python_backend.routes.traffic_timeseries import router as ts_router
from python_backend.routes.youtube import router as youtube_router


def _scheduler_enabled() -> bool:
    value = os.getenv("ENABLE_BACKGROUND_SCHEDULER", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_app_state()
    should_start_scheduler = _scheduler_enabled()
    if should_start_scheduler:
        start_scheduler()
    try:
        yield
    finally:
        if should_start_scheduler:
            stop_scheduler()


app = FastAPI(lifespan=lifespan)

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

app.include_router(ts_router)
app.include_router(geo_router)
app.include_router(content_router)
app.include_router(mail_router)
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
