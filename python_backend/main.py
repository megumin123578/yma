import base64
import json
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
from fastapi.staticfiles import StaticFiles

from python_backend.perf_log import drain_request_log, init_request_log


class PerfLogMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")
        init_request_log()
        t0 = time.perf_counter()

        async def send_with_perf_header(message):
            if message["type"] == "http.response.start":
                total_ms = (time.perf_counter() - t0) * 1000
                lines = drain_request_log()
                if lines:
                    payload = {
                        "method": method,
                        "path": path,
                        "total_ms": round(total_ms, 1),
                        "lines": lines,
                    }
                    encoded = base64.b64encode(
                        json.dumps(payload).encode("utf-8")
                    ).decode("ascii")
                    headers = list(message.get("headers", []))
                    headers.append((b"x-perf-log", encoded.encode("ascii")))
                    message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_perf_header)

from python_backend.config import load_env
from python_backend.google_api_quota import enable_google_api_quota_guard

load_env()
enable_google_api_quota_guard()

from python_backend.api.auth.routers import auth, user
from python_backend.api.auth.scheduler import start_scheduler, stop_scheduler
from python_backend.bootstrap import initialize_app_state
from python_backend.routes.audience import router as audience_router
from python_backend.routes.channel_compare import router as channel_compare_router
from python_backend.routes.content import router as content_router, prewarm_content_cache
from python_backend.routes.geography import router as geo_router
from python_backend.routes.mail import router as mail_router
from python_backend.routes.overview import router as overview_router
from python_backend.routes.reach import router as reach_router
from python_backend.routes.research import router as research_router
from python_backend.routes.revenue import router as revenue_router
from python_backend.routes.smmstore import router as smmstore_router
from python_backend.routes.traffic_timeseries import router as ts_router
from python_backend.routes.youtube import router as youtube_router


DEFAULT_CORS_ORIGIN_REGEX = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"


def _split_env_list(value: str) -> list[str]:
    return [item.strip().rstrip("/") for item in str(value or "").split(",") if item.strip()]


def _cors_origins() -> list[str]:
    return _split_env_list(os.getenv("CORS_ORIGINS", ""))


def _scheduler_enabled() -> bool:
    value = os.getenv("ENABLE_BACKGROUND_SCHEDULER", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _perf_log_enabled() -> bool:
    value = os.getenv("PERF_LOG_ENABLED", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


PERF_LOG_ENABLED = _perf_log_enabled()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_app_state()
    should_start_scheduler = _scheduler_enabled()
    if should_start_scheduler:
        start_scheduler()
    prewarm_content_cache()
    try:
        from python_backend.routes.research import prewarm_research_caches
        prewarm_research_caches()
    except Exception as e:  # noqa: BLE001
        print(f"[main] research prewarm loi: {e}")
    try:
        from python_backend.routes.research import start_research_scheduler
        start_research_scheduler()
    except Exception as e:  # noqa: BLE001
        print(f"[main] research scheduler start loi: {e}")
    try:
        yield
    finally:
        if should_start_scheduler:
            stop_scheduler()
        try:
            from python_backend.routes.research import stop_research_scheduler
            stop_research_scheduler()
        except Exception:
            pass


app = FastAPI(
    lifespan=lifespan,
    redirect_slashes=False,
    default_response_class=ORJSONResponse,
)

if PERF_LOG_ENABLED:
    app.add_middleware(PerfLogMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
_cors_origins_list = _cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins_list,
    allow_origin_regex=None if _cors_origins_list else DEFAULT_CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Perf-Log"] if PERF_LOG_ENABLED else [],
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
app.include_router(research_router)
app.include_router(revenue_router)
app.include_router(auth.router)
app.include_router(user.router, prefix="/api")

app.mount(
    "/uploads",
    StaticFiles(directory="python_backend/api/uploads"),
    name="uploads",
)
