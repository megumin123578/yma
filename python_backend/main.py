# python_backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from python_backend.api.auth.database import engine, Base
from python_backend.api.auth import models

from python_backend.routes.traffic_timeseries import router as ts_router
from python_backend.routes.geography import router as geo_router
from python_backend.routes.content import router as content_router
from python_backend.routes.overview import router as overview_router
from fastapi.staticfiles import StaticFiles
from python_backend.api.auth.routers import auth, user

app = FastAPI()

Base.metadata.create_all(bind=engine)

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
app.include_router(auth.router)
app.include_router(user.router, prefix="/api") 

app.mount(
    "/uploads",
    StaticFiles(directory="python_backend/api/uploads"),
    name="uploads",
)