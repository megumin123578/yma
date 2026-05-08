from datetime import datetime, timedelta
import os
import time
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext

from python_backend.perf_log import add_log

from python_backend.config import load_env
from python_backend.api.auth.models import User  
from typing import Optional
from python_backend.api.auth.database import get_db
from sqlalchemy.orm import Session

load_env()

def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer") from exc
    if value <= 0:
        raise RuntimeError(f"Environment variable {name} must be greater than 0")
    return value


SECRET_KEY = _require_env("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = _get_int_env("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 7)

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return user


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    t_total = time.perf_counter()
    auth = request.headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        add_log("[AUTH] no token (anonymous)")
        return None

    token = auth.split(" ", 1)[1].strip()
    if not token:
        return None

    t_jwt = time.perf_counter()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
    jwt_ms = (time.perf_counter() - t_jwt) * 1000

    t_query = time.perf_counter()
    user = db.query(User).filter(User.username == username).first()
    query_ms = (time.perf_counter() - t_query) * 1000

    total_ms = (time.perf_counter() - t_total) * 1000
    add_log(
        f"[AUTH] total={total_ms:.1f}ms "
        f"jwt={jwt_ms:.1f}ms user_query={query_ms:.1f}ms"
    )
    return user
