from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from python_backend.api.auth.auth_utils import get_current_user
from python_backend.api.auth.models import User
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import re

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


class AnalyticsRequest(BaseModel):
    cookies: str


def _parse_cookie_string(raw: str) -> Dict[str, str]:
    cookies = {}
    for pair in (raw or "").split(";"):
        if "=" in pair:
            name, value = pair.strip().split("=", 1)
            cookies[name] = value
    if not cookies.get("PHPSESSID"):
        return {}
    return cookies


def _parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    cleaned = value.replace("\xa0", " ").strip()

    patterns = [
        r"\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}:\d{2})?",
        r"\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2}:\d{2})?",
        r"\d{4}/\d{2}/\d{2}(?:\s+\d{2}:\d{2}:\d{2})?",
    ]

    candidates = [cleaned]
    for pat in patterns:
        match = re.search(pat, cleaned)
        if match:
            candidates.append(match.group(0))

    for candidate in candidates:
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d",
        ):
            try:
                return datetime.strptime(candidate, fmt)
            except ValueError:
                continue

    try:
        return datetime.fromisoformat(cleaned.replace(" ", "T"))
    except ValueError:
        return None


def _clean_link(value: str) -> str:
    if not value:
        return ""
    cleaned = value.replace("\xa0", " ").strip()
    match = re.search(r"(https?://[^\s]+)", cleaned)
    if match:
        return match.group(1)
    return cleaned.split("Additional data", 1)[0].strip()
    return None


def _previous_month_range(now: datetime) -> tuple[datetime, datetime]:
    first_day_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day_prev_month = first_day_this_month - timedelta(days=1)
    first_day_prev_month = last_day_prev_month.replace(day=1)
    return first_day_prev_month, first_day_this_month


@router.post("/analytics")
def smmstore_analytics(payload: AnalyticsRequest, current_user: User = Depends(get_current_user)):
    raw_cookie = (payload.cookies or "").strip()
    cookies = _parse_cookie_string(raw_cookie)
    if not cookies:
        raise HTTPException(status_code=400, detail="Missing PHPSESSID in cookies")

    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://10000smm.top/api",
    }
    if raw_cookie:
        headers["Cookie"] = raw_cookie

    start_date, end_date = _previous_month_range(datetime.now())
    max_pages = 200
    results: List[Dict] = []

    for page in range(1, max_pages + 1):
        url = f"https://10000smm.top/orders?page={page}"
        resp = session.get(url, headers=headers, cookies=cookies, timeout=30)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch orders")

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")
        if not table:
            snippet = resp.text[:400].replace("\n", " ").strip()
            raise HTTPException(
                status_code=401,
                detail=f"Không thấy bảng orders. Có thể cookie hết hạn hoặc bị redirect/login. Snippet: {snippet}",
            )

        rows = table.find_all("tr")[1:]
        if not rows:
            break

        page_has_target = False
        page_all_older = True
        parsed_any = False

        for tr in rows:
            tds = tr.find_all("td")
            if not tds:
                continue
            cols = [td.get_text(strip=True) for td in tds[:9]]
            if len(cols) < 9:
                continue

            date_value = _parse_date(cols[1])
            if not date_value:
                continue
            parsed_any = True

            if start_date <= date_value < end_date:
                page_has_target = True
                page_all_older = False
                results.append({
                    "ID": cols[0],
                    "Date": cols[1],
                    "Link": _clean_link(cols[2]),
                    "Charge": cols[3],
                    "Start count": cols[4],
                    "Quantity": cols[5],
                    "Service": cols[6],
                    "Status": cols[7],
                    "Remains": cols[8],
                })
            elif date_value >= end_date:
                page_all_older = False

        if not parsed_any:
            raise HTTPException(status_code=422, detail="Cannot parse Date column in orders table")

        if not page_has_target and page_all_older:
            break

    totals_by_channel: Dict[str, float] = {}
    total_sum = 0.0
    for row in results:
        link = row.get("Link") or "Unidentified"
        charge_raw = row.get("Charge", "").replace("$", "").replace(",", "").strip()
        try:
            charge_val = float(charge_raw)
        except ValueError:
            charge_val = 0.0
        totals_by_channel[link] = totals_by_channel.get(link, 0.0) + charge_val
        total_sum += charge_val

    totals_list = [
        {"link": k, "charge": round(v, 2)}
        for k, v in sorted(totals_by_channel.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "month": start_date.strftime("%Y-%m"),
        "count": len(results),
        "orders": results,
        "totals": {
            "by_channel": totals_list,
            "total": round(total_sum, 2),
        },
    }
