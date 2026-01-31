#react_dashboard/src/api/auth/main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from src.api.auth.routers import auth

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://192.168.1.162:3001",
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

app.include_router(auth.router)


