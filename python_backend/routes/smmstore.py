from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from python_backend.api.auth.auth_utils import get_current_user
from python_backend.api.auth.models import User
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

API_URL = "https://10000smm.top/api/v2"

router = APIRouter(prefix="/api/smmstore", tags=["smmstore"])


def smm_request(api_key: str, params: dict):
    payload = urlencode({"key": api_key, **params}).encode("utf-8")
    req = Request(API_URL, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    try:
        return json.loads(raw)
    except Exception:
        raise HTTPException(status_code=502, detail="Invalid response from SMM API")


def require_key(user: User) -> str:
    key = (user.smmstore_api_key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="Missing SMM API key")
    return key


@router.post("/balance")
def balance(current_user: User = Depends(get_current_user)):
    key = require_key(current_user)
    return smm_request(key, {"action": "balance"})


@router.post("/services")
def services(current_user: User = Depends(get_current_user)):
    key = require_key(current_user)
    return smm_request(key, {"action": "services"})


class OrderCreate(BaseModel):
    service: str
    link: str
    quantity: str
    runs: Optional[str] = None
    interval: Optional[str] = None


@router.post("/order")
def create_order(payload: OrderCreate, current_user: User = Depends(get_current_user)):
    key = require_key(current_user)
    params = {
        "action": "add",
        "service": payload.service,
        "link": payload.link,
        "quantity": payload.quantity,
    }
    if payload.runs:
        params["runs"] = payload.runs
    if payload.interval:
        params["interval"] = payload.interval
    return smm_request(key, params)


class OrderStatus(BaseModel):
    order: str


@router.post("/status")
def order_status(payload: OrderStatus, current_user: User = Depends(get_current_user)):
    key = require_key(current_user)
    return smm_request(key, {"action": "status", "order": payload.order})
