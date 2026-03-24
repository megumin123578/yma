from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from python_backend.api.auth.auth_utils import get_current_user
from python_backend.api.auth.database import get_db, SessionLocal
from python_backend.api.auth.models import User, SmmstoreAnalyticsCache, SmmstoreScheduledOrder
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
import re

API_URL = "https://10000smm.top/api/v2"

router = APIRouter(prefix="/api/smmstore", tags=["smmstore"])
_channel_cache: Dict[str, str] = {}


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


def _error_text(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        return f"HTTP {exc.status_code}"
    message = str(exc).strip()
    return message or exc.__class__.__name__


def _log_submit_event(level: str, message: str) -> None:
    print(f"[SMMSTORE][{level}] {message}")


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


def _normalize_order_inputs(
    service: str,
    link: str,
    quantity: str,
    runs: Optional[str] = None,
    interval: Optional[str] = None,
) -> tuple[str, str, str, Optional[str], Optional[str]]:
    clean_service = (service or "").strip()
    clean_link = (link or "").strip()
    clean_quantity = str(quantity or "").strip()

    if not clean_service:
        raise HTTPException(status_code=400, detail="service is required")
    if not clean_link:
        raise HTTPException(status_code=400, detail="link is required")
    try:
        qty_num = int(float(clean_quantity))
    except Exception:
        raise HTTPException(status_code=400, detail="quantity must be a number")
    if qty_num <= 0:
        raise HTTPException(status_code=400, detail="quantity must be greater than 0")
    if not clean_link.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="link must start with http:// or https://")

    clean_runs = (runs or "").strip()
    clean_interval = (interval or "").strip()
    if bool(clean_runs) != bool(clean_interval):
        raise HTTPException(
            status_code=400,
            detail="runs and interval are required together for drip-feed orders",
        )
    if clean_runs and clean_interval:
        try:
            runs_num = int(clean_runs)
            interval_num = int(clean_interval)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="runs and interval must be integers",
            )
        if runs_num <= 0 or interval_num <= 0:
            raise HTTPException(
                status_code=400,
                detail="runs and interval must be greater than 0",
            )
        clean_runs = str(runs_num)
        clean_interval = str(interval_num)

    return (
        clean_service,
        clean_link,
        str(qty_num),
        clean_runs or None,
        clean_interval or None,
    )


@router.post("/order")
def create_order(
    payload: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    key = require_key(current_user)
    service, link, quantity, runs, interval = _normalize_order_inputs(
        payload.service,
        payload.link,
        payload.quantity,
        payload.runs,
        payload.interval,
    )
    params = {
        "action": "add",
        "service": service,
        "link": link,
        "quantity": quantity,
    }
    if runs:
        params["runs"] = runs
    if interval:
        params["interval"] = interval
    try:
        resp = smm_request(key, params)
        remote_id = str(resp.get("order") or "").strip()
        if remote_id:
            now = datetime.utcnow()
            row = SmmstoreScheduledOrder(
                user_id=current_user.id,
                run_at=now,
                service=service,
                link=link,
                quantity=quantity,
                runs=runs,
                interval=interval,
                status="submitted",
                remote_order_id=remote_id,
                submitted_at=now,
                charge=str(resp.get("charge") or ""),
                remains=str(resp.get("remains") or resp.get("remain") or ""),
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.commit()
            _log_submit_event(
                "OK",
                f"direct submit user={current_user.username} service={service} quantity={quantity} order_id={remote_id}",
            )
        else:
            _log_submit_event(
                "FAIL",
                f"direct submit user={current_user.username} service={service} quantity={quantity} error={resp.get('error') or 'Missing order id'}",
            )
        return resp
    except Exception as exc:
        _log_submit_event(
            "FAIL",
            f"direct submit user={current_user.username} service={service} quantity={quantity} error={_error_text(exc)}",
        )
        raise


class OrderStatus(BaseModel):
    order: str


@router.post("/status")
def order_status(payload: OrderStatus, current_user: User = Depends(get_current_user)):
    key = require_key(current_user)
    return smm_request(key, {"action": "status", "order": payload.order})




def _serialize_scheduled_order(row: SmmstoreScheduledOrder) -> Dict:
    return {
        "id": f"ord_{row.id}",
        "dbId": row.id,
        "runAt": row.run_at.isoformat() if row.run_at else None,
        "serviceId": row.service,
        "service": row.service,
        "link": row.link,
        "quantity": row.quantity,
        "status": row.status,
        "orderId": row.remote_order_id or "",
        "charge": row.charge or "",
        "remains": row.remains or "",
        "dripFeed": bool((row.runs or "").strip() or (row.interval or "").strip()),
        "runs": row.runs or "",
        "interval": row.interval or "",
        "error": row.last_error or "",
        "submittedAt": row.submitted_at.isoformat() if row.submitted_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


class ScheduleOrderCreate(BaseModel):
    service: str
    link: str
    quantity: str
    run_at: datetime
    runs: Optional[str] = None
    interval: Optional[str] = None


@router.post("/schedule-order")
def create_scheduled_order(
    payload: ScheduleOrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_key(current_user)
    service, link, quantity, runs, interval = _normalize_order_inputs(
        payload.service,
        payload.link,
        payload.quantity,
        payload.runs,
        payload.interval,
    )

    run_at = payload.run_at
    if run_at.tzinfo is not None:
        run_at = run_at.astimezone().replace(tzinfo=None)
    if run_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="run_at must be in the future")

    row = SmmstoreScheduledOrder(
        user_id=current_user.id,
        run_at=run_at,
        service=service,
        link=link,
        quantity=quantity,
        runs=runs or None,
        interval=interval or None,
        status="queued",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _log_submit_event(
        "QUEUED",
        f"scheduled submit user={current_user.username} service={service} quantity={quantity} run_at={row.run_at.isoformat()} schedule_id={row.id}",
    )
    return {"ok": True, "item": _serialize_scheduled_order(row)}


@router.get("/scheduled-orders")
def list_scheduled_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(SmmstoreScheduledOrder)
        .filter(SmmstoreScheduledOrder.user_id == current_user.id)
        .order_by(SmmstoreScheduledOrder.run_at.desc(), SmmstoreScheduledOrder.id.desc())
        .limit(300)
        .all()
    )
    return {"items": [_serialize_scheduled_order(r) for r in rows]}


@router.delete("/scheduled-orders/{order_id}")
def delete_scheduled_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(SmmstoreScheduledOrder)
        .filter(
            SmmstoreScheduledOrder.id == order_id,
            SmmstoreScheduledOrder.user_id == current_user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


def process_due_smmstore_orders(limit: int = 20) -> None:
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        due_rows = (
            db.query(SmmstoreScheduledOrder, User)
            .join(User, User.id == SmmstoreScheduledOrder.user_id)
            .filter(
                SmmstoreScheduledOrder.status == "queued",
                SmmstoreScheduledOrder.run_at <= now,
            )
            .order_by(SmmstoreScheduledOrder.run_at.asc(), SmmstoreScheduledOrder.id.asc())
            .limit(limit)
            .all()
        )

        for order_row, user_row in due_rows:
            api_key = (user_row.smmstore_api_key or "").strip()
            if not api_key:
                order_row.status = "failed"
                order_row.last_error = "Missing SMM API key"
                order_row.attempts = int(order_row.attempts or 0) + 1
                order_row.updated_at = datetime.utcnow()
                db.add(order_row)
                db.commit()
                _log_submit_event(
                    "FAIL",
                    f"scheduled execution user={user_row.username} schedule_id={order_row.id} service={order_row.service} quantity={order_row.quantity} error=Missing SMM API key",
                )
                continue

            params = {
                "action": "add",
                "service": order_row.service,
                "link": order_row.link,
                "quantity": order_row.quantity,
            }
            if order_row.runs:
                params["runs"] = order_row.runs
            if order_row.interval:
                params["interval"] = order_row.interval

            try:
                resp = smm_request(api_key, params)
                remote_id = str(resp.get("order") or "").strip()
                if not remote_id:
                    order_row.status = "failed"
                    order_row.last_error = str(resp.get("error") or "Missing order id")
                    _log_submit_event(
                        "FAIL",
                        f"scheduled execution user={user_row.username} schedule_id={order_row.id} service={order_row.service} quantity={order_row.quantity} error={order_row.last_error}",
                    )
                else:
                    order_row.remote_order_id = remote_id
                    order_row.status = "submitted"
                    order_row.submitted_at = datetime.utcnow()
                    order_row.last_error = None
                    _log_submit_event(
                        "OK",
                        f"scheduled execution user={user_row.username} schedule_id={order_row.id} service={order_row.service} quantity={order_row.quantity} order_id={remote_id}",
                    )
            except Exception as exc:
                order_row.status = "failed"
                order_row.last_error = _error_text(exc)
                _log_submit_event(
                    "FAIL",
                    f"scheduled execution user={user_row.username} schedule_id={order_row.id} service={order_row.service} quantity={order_row.quantity} error={order_row.last_error}",
                )

            order_row.attempts = int(order_row.attempts or 0) + 1
            order_row.updated_at = datetime.utcnow()
            db.add(order_row)
            db.commit()

        refresh_rows = (
            db.query(SmmstoreScheduledOrder, User)
            .join(User, User.id == SmmstoreScheduledOrder.user_id)
            .filter(
                SmmstoreScheduledOrder.remote_order_id.isnot(None),
                SmmstoreScheduledOrder.status.notin_([
                    "completed",
                    "partial",
                    "canceled",
                    "cancelled",
                    "failed",
                ]),
            )
            .order_by(SmmstoreScheduledOrder.updated_at.asc())
            .limit(limit)
            .all()
        )

        for order_row, user_row in refresh_rows:
            api_key = (user_row.smmstore_api_key or "").strip()
            if not api_key:
                continue
            try:
                resp = smm_request(
                    api_key,
                    {"action": "status", "order": order_row.remote_order_id},
                )
                status_text = str(resp.get("status") or "submitted").strip()
                order_row.status = status_text or "submitted"
                order_row.charge = str(resp.get("charge") or "")
                order_row.remains = str(resp.get("remains") or resp.get("remain") or "")
                order_row.updated_at = datetime.utcnow()
                db.add(order_row)
                db.commit()
            except Exception:
                pass
    finally:
        db.close()


class AnalyticsRequest(BaseModel):
    cookies: str = ""
    month: Optional[str] = None


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


def _extract_video_id(url: str) -> Optional[str]:
    if not url:
        return None
    match = re.search(r"(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})", url)
    if match:
        return match.group(1)
    return None


def _is_quota_exceeded(payload: Dict) -> bool:
    try:
        error = payload.get("error") or {}
        for item in error.get("errors", []):
            if item.get("reason") == "quotaExceeded":
                return True
    except Exception:
        return False
    return False


def _fetch_channel_title(video_id: str) -> Optional[str]:
    api_keys = [
        os.getenv("YOUTUBE_API_KEY1", "").strip(),
        os.getenv("YOUTUBE_API_KEY2", "").strip(),
        os.getenv("YOUTUBE_API_KEY", "").strip(),
    ]
    api_keys = [k for k in api_keys if k]
    if not api_keys:
        return None

    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {"part": "snippet", "id": video_id}

    for key in api_keys:
        params["key"] = key
        try:
            resp = requests.get(url, params=params, timeout=20)
            data = resp.json()
        except Exception:
            continue

        if _is_quota_exceeded(data):
            continue

        items = data.get("items") or []
        if not items:
            return None
        snippet = items[0].get("snippet") or {}
        return snippet.get("channelTitle") or None

    return None


def _map_links_to_channels(links: List[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    unique_links = [link for link in set(links) if link]

    def fetch_one(link: str):
        if link in _channel_cache:
            return link, _channel_cache[link]
        video_id = _extract_video_id(link)
        if not video_id:
            return link, link
        title = _fetch_channel_title(video_id)
        return link, title or link

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_one, link): link for link in unique_links}
        for future in as_completed(futures):
            link, title = future.result()
            mapping[link] = title
            _channel_cache[link] = title

    return mapping
    return None


def _previous_month_range(now: datetime) -> tuple[datetime, datetime]:
    first_day_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day_prev_month = first_day_this_month - timedelta(days=1)
    first_day_prev_month = last_day_prev_month.replace(day=1)
    return first_day_prev_month, first_day_this_month


def _month_range_from_key(month_key: str) -> Optional[tuple[datetime, datetime]]:
    try:
        dt = datetime.strptime(month_key, "%Y-%m")
    except ValueError:
        return None
    start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


@router.get("/analytics/months")
def list_cached_months(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(SmmstoreAnalyticsCache.month, SmmstoreAnalyticsCache.updated_at)
        .filter(SmmstoreAnalyticsCache.user_id == current_user.id)
        .order_by(SmmstoreAnalyticsCache.month.desc())
        .all()
    )
    return [{"month": r[0], "updated_at": r[1].isoformat() if r[1] else None} for r in rows]


@router.delete("/analytics/months/{month_key}")
def delete_cached_month(
    month_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(SmmstoreAnalyticsCache)
        .filter(
            SmmstoreAnalyticsCache.user_id == current_user.id,
            SmmstoreAnalyticsCache.month == month_key,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Month not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.post("/analytics")
def smmstore_analytics(
    payload: AnalyticsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        if payload.month:
            range_pair = _month_range_from_key(payload.month)
            if not range_pair:
                raise HTTPException(status_code=400, detail="Invalid month format")
            start_date, end_date = range_pair
            month_key = payload.month
        else:
            start_date, end_date = _previous_month_range(datetime.now())
            month_key = start_date.strftime("%Y-%m")
        cached = (
            db.query(SmmstoreAnalyticsCache)
            .filter(
                SmmstoreAnalyticsCache.user_id == current_user.id,
                SmmstoreAnalyticsCache.month == month_key,
            )
            .first()
        )
        if cached:
            try:
                return json.loads(cached.payload)
            except Exception:
                pass

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
                    detail=f"Orders table not found. Cookie may be expired or redirected to login. Snippet: {snippet}",
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

        link_map = {}
        if results:
            link_map = _map_links_to_channels([row.get("Link", "") for row in results])

        totals_by_channel: Dict[str, float] = {}
        total_sum = 0.0
        for row in results:
            raw_link = row.get("Link") or "Unidentified"
            link = link_map.get(raw_link, raw_link)
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

        response_payload = {
            "month": start_date.strftime("%Y-%m"),
            "count": len(results),
            "orders": results,
            "totals": {
                "by_channel": totals_list,
                "total": round(total_sum, 2),
            },
        }
        try:
            payload_str = json.dumps(response_payload, ensure_ascii=False)
            if cached:
                cached.payload = payload_str
                cached.updated_at = datetime.utcnow()
            else:
                db.add(
                    SmmstoreAnalyticsCache(
                        user_id=current_user.id,
                        month=month_key,
                        payload=payload_str,
                        updated_at=datetime.utcnow(),
                    )
                )
            db.commit()
        except Exception:
            db.rollback()
        return response_payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
