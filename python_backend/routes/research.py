# routes/research.py
"""API nghiên cứu ngách (gộp pipeline YT vào yt_manage_app, 2026-06).

Phase 2: phục vụ báo cáo watchlist dưới dạng JSON (thay HTML/Firebase).
  GET /api/research/watchlists       -> danh sách watchlist
  GET /api/research/report/{wid}     -> build_data(wid) JSON (payload 22 tab)

build_data() đọc dữ liệu đã thu thập trong ~/.youtube_research/ (read-only).
Import lazy trong handler để không kéo dependency nặng lúc app khởi động.
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from python_backend.api.auth.auth_utils import get_current_user_optional
from python_backend.perf_log import add_log
from python_backend.sse_utils import poll_stream, sse_response

router = APIRouter(prefix="/api/research", tags=["research"])

# Repo root = .../yt_manage_app (cha của python_backend) — cwd cho worker.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ORCH_DB = Path.home() / ".youtube_research" / "orchestrator.sqlite"
_RUN_LOG_DIR = Path.home() / ".youtube_research" / "run_logs"
_META_CACHE = Path.home() / ".youtube_research" / "channel_meta.json"
_META_TTL = 86400  # 24h — avatar/subs/views/videos ít đổi
_meta_lock = Lock()
_meta_fail_until = 0.0  # cooldown khi fetch lỗi (vd hết quota) để khỏi gọi lại liên tục


def _youtube_data_client():
    """Client YouTube Data API. Ưu tiên OAuth token (project đang dùng, còn quota);
    fallback developerKey từ config. None nếu không có nguồn nào."""
    from googleapiclient.discovery import build
    # 1) OAuth token bất kỳ (channels.list theo id là public, token nào cũng gọi được)
    try:
        from python_backend.token_store import list_token_names, load_token_credentials
        for name in list_token_names():
            if str(name or "").lower().startswith("mail__"):
                continue
            try:
                creds = load_token_credentials(name, refresh=True)
                if creds:
                    return build("youtube", "v3", credentials=creds, cache_discovery=False)
            except Exception:
                continue
    except Exception:
        pass
    # 2) API key
    try:
        from python_backend.research.config import load_config
        key = (load_config().get("youtube_data_api_key") or "").strip()
        if key:
            return build("youtube", "v3", developerKey=key, cache_discovery=False)
    except Exception:
        pass
    return None

# Theo dõi worker đã spawn trong phiên process này: run_id -> Popen.
_procs: dict[str, subprocess.Popen] = {}
_procs_lock = Lock()

# Cache build_data theo wid (build hơi đắt: quét pkl + train viral model).
# TTL ngắn để đổi tab/refresh nhanh không recompute, nhưng vẫn tươi trong phiên.
_REPORT_TTL = 300  # giây
_report_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = Lock()


def _connected_channel_map() -> dict:
    """{channel_id: account_tag} cho các kênh đã OAuth ở app chính (có chọn kênh)."""
    try:
        from python_backend.api.auth.database import SessionLocal
        from python_backend.api.auth.models import UserCredential

        db = SessionLocal()
        try:
            rows = (
                db.query(UserCredential.selected_channel_id, UserCredential.account_tag)
                .filter(UserCredential.selected_channel_id.isnot(None))
                .all()
            )
        finally:
            db.close()
        return {cid: tag for cid, tag in rows if cid}
    except Exception as e:  # noqa: BLE001
        print(f"[research] connected map loi: {e}")
        return {}


def _channel_meta_map(channel_ids) -> dict:
    """{channel_id: {avatar, subs, totalViews, totalVideos}} qua YouTube Data API.

    Cache file ~/.youtube_research/channel_meta.json, TTL 24h. channels.list
    batch 50 id/request = 1 quota unit/request → ~6 unit cho ~270 kênh. Lỗi/
    thiếu key → trả những gì cache có (không vỡ endpoint).
    """
    global _meta_fail_until
    ids = [c for c in dict.fromkeys(channel_ids) if c]  # unique, giữ thứ tự
    if not ids:
        return {}
    with _meta_lock:
        try:
            cache = json.loads(_META_CACHE.read_text(encoding="utf-8")) if _META_CACHE.exists() else {}
        except Exception:
            cache = {}
        now = time.time()
        stale = [c for c in ids if c not in cache or (now - cache[c].get("ts", 0)) > _META_TTL]

        if stale and now >= _meta_fail_until:
            yt = _youtube_data_client()
            if yt is None:
                _meta_fail_until = now + 600
            else:
                ok = False
                try:
                    for i in range(0, len(stale), 50):
                        batch = stale[i:i + 50]
                        resp = yt.channels().list(
                            part="snippet,statistics", id=",".join(batch),
                            maxResults=50).execute() or {}
                        for it in resp.get("items", []):
                            cid = it.get("id")
                            sn = it.get("snippet", {}) or {}
                            st = it.get("statistics", {}) or {}
                            thumbs = sn.get("thumbnails", {}) or {}
                            avatar = ((thumbs.get("default") or {}).get("url")
                                      or (thumbs.get("medium") or {}).get("url") or "")
                            cache[cid] = {
                                "avatar": avatar,
                                "subs": int(st.get("subscriberCount", 0) or 0),
                                "totalViews": int(st.get("viewCount", 0) or 0),
                                "totalVideos": int(st.get("videoCount", 0) or 0),
                                "ts": now,
                            }
                        ok = True
                    try:
                        _META_CACHE.parent.mkdir(parents=True, exist_ok=True)
                        _META_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                    except Exception as e:  # noqa: BLE001
                        print(f"[research] save channel_meta loi: {e}")
                except Exception as e:  # noqa: BLE001
                    print(f"[research] fetch channel_meta loi: {e}")
                    if not ok:
                        _meta_fail_until = now + 600  # hết quota/lỗi → nghỉ 10 phút

        return {c: cache[c] for c in ids if c in cache}


def _watchlist_summary(w, connected=None) -> dict:
    connected = connected if connected is not None else {}
    self_ch = w.self_channel
    self_tag = connected.get(self_ch.channel_id) if self_ch else None
    return {
        "id": w.id,
        "name": w.name,
        "createdAt": getattr(w, "created_at", ""),
        "teamId": getattr(w, "team_id", "default"),
        "paused": bool(getattr(w, "paused", False)),
        "pausedReason": getattr(w, "paused_reason", ""),
        "selfChannel": {
            "channelId": self_ch.channel_id,
            "title": self_ch.title,
            "connected": bool(self_tag),
            "accountTag": self_tag or "",
        } if self_ch else None,
        "competitorCount": len(w.competitor_channels),
    }


@router.get("/watchlists")
def list_watchlists(current_user=Depends(get_current_user_optional)):
    """Danh sách watchlist (mới nhất trước)."""
    from python_backend.research import watchlist as wlmod

    t0 = time.perf_counter()
    connected = _connected_channel_map()
    items = [_watchlist_summary(w, connected) for w in wlmod.list_watchlists()]
    add_log(f"[H] research/watchlists: {(time.perf_counter() - t0) * 1000:.1f}ms n={len(items)}")
    return {"items": items}


def _channel_dto(c, connected=None, meta=None) -> dict:
    connected = connected if connected is not None else {}
    tag = connected.get(c.channel_id)
    m = (meta or {}).get(c.channel_id) or {}
    return {
        "channelId": c.channel_id,
        "title": c.title,
        "url": c.url,
        "isSelf": bool(c.is_self),
        "autoAdded": bool(c.auto_added),
        "archived": bool(c.archived),
        "connected": bool(tag),
        "accountTag": tag or "",
        "avatar": m.get("avatar", ""),
        "subs": m.get("subs"),
        "totalViews": m.get("totalViews"),
        "totalVideos": m.get("totalVideos"),
    }


class WatchlistCreate(BaseModel):
    name: str
    description: str = ""


class WatchlistPatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    paused: Optional[bool] = None


@router.get("/channels-unified")
def channels_unified(current_user=Depends(get_current_user_optional)):
    """1 list thống nhất: TẤT CẢ watchlist (kể cả kênh chính chưa OAuth) + kênh phụ.

    Nguồn sự thật = watchlist. Mỗi item: self (có connected/accountTag), competitors,
    paused. Frontend (CredentialsDialog list view) dựng 1 danh sách duy nhất từ đây.
    """
    from python_backend.research import watchlist as wlmod

    connected = _connected_channel_map()  # channel_id -> account_tag
    wls = wlmod.list_watchlists()
    # gom mọi channel_id (self + competitor) → fetch meta 1 lượt (avatar/subs/views/videos)
    all_ids = []
    for w in wls:
        if w.self_channel:
            all_ids.append(w.self_channel.channel_id)
        all_ids += [c.channel_id for c in w.competitor_channels]
    meta = _channel_meta_map(all_ids)

    items = []
    for w in wls:
        sc = w.self_channel
        self_tag = connected.get(sc.channel_id) if sc else None
        items.append({
            "watchlistId": w.id,
            "watchlistName": w.name,
            "paused": bool(getattr(w, "paused", False)),
            "self": (_channel_dto(sc, connected, meta) if sc else None),
            "accountTag": self_tag or "",
            "competitorCount": len(w.competitor_channels),
            "competitors": [_channel_dto(c, connected, meta) for c in w.competitor_channels],
        })
    return {"items": items}


@router.post("/watchlists")
def create_watchlist(req: WatchlistCreate, current_user=Depends(get_current_user_optional)):
    from python_backend.research import watchlist as wlmod

    if not req.name.strip():
        raise HTTPException(400, "name required")
    w = wlmod.create_watchlist(req.name.strip(), req.description.strip())
    _invalidate_report_cache(None)
    return _watchlist_summary(w)


@router.patch("/watchlists/{wid}")
def patch_watchlist(wid: str, req: WatchlistPatch, current_user=Depends(get_current_user_optional)):
    """Đổi tên/mô tả/pause-unpause 1 watchlist."""
    from datetime import datetime as _dt
    from python_backend.research import watchlist as wlmod

    w = wlmod.load_watchlist(wid)
    if not w:
        raise HTTPException(404, "watchlist not found")
    if req.name is not None and req.name.strip():
        w.name = req.name.strip()
    if req.description is not None:
        w.description = req.description.strip()
    if req.paused is not None:
        w.paused = bool(req.paused)
        if req.paused:
            w.paused_at = _dt.now().isoformat(timespec="seconds")
            w.paused_reason = w.paused_reason or "manual"
        else:
            w.paused_at = ""
            w.paused_reason = ""
    wlmod.save_watchlist(w)
    _invalidate_report_cache([wid])
    return _watchlist_summary(w)


@router.delete("/watchlists/{wid}/channels/{cid}")
def remove_channel(wid: str, cid: str, current_user=Depends(get_current_user_optional)):
    from python_backend.research import watchlist as wlmod

    ok = wlmod.remove_channel(wid, cid)
    if not ok:
        raise HTTPException(404, "channel/watchlist not found")
    _invalidate_report_cache([wid])
    return {"removed": True, "channelId": cid}


@router.get("/report/{wid}")
def get_report(
    wid: str,
    refresh: bool = False,
    current_user=Depends(get_current_user_optional),
):
    """Báo cáo 22 tab của 1 watchlist (JSON). `refresh=true` bỏ qua cache."""
    now = time.monotonic()
    if not refresh:
        with _cache_lock:
            hit = _report_cache.get(wid)
            if hit and (now - hit[0]) < _REPORT_TTL:
                add_log(f"[H] research/report cache-hit wid={wid}")
                return hit[1]

    from python_backend.research.html_report import build_data

    t0 = time.perf_counter()
    try:
        data = build_data(wid)
    except Exception as e:  # noqa: BLE001
        print(f"[research] build_data loi wid={wid}: {e}")
        raise HTTPException(status_code=500, detail=f"build_data failed: {e}")
    if not data:
        raise HTTPException(status_code=404, detail="Watchlist not found or no data")

    add_log(f"[H] research/report build wid={wid}: {(time.perf_counter() - t0) * 1000:.1f}ms")
    with _cache_lock:
        _report_cache[wid] = (now, data)
    return data


# ============================================================
# Phase 3 — Trigger pipeline (worker process) + progress
# ============================================================
class RunRequest(BaseModel):
    wlIds: Optional[list[str]] = None   # None = tất cả WL chưa paused
    resume: Optional[str] = None        # run_id cũ để resume
    aiOnly: bool = False                # chỉ sinh AI (không monitor/Chrome)


def _invalidate_report_cache(wl_ids):
    with _cache_lock:
        if wl_ids:
            for w in wl_ids:
                _report_cache.pop(w, None)
        else:
            _report_cache.clear()


def _proc_alive(run_id: str) -> Optional[int]:
    """Trả PID nếu worker còn sống (trong phiên process này), else None."""
    with _procs_lock:
        p = _procs.get(run_id)
    if p is None:
        return None
    return p.pid if p.poll() is None else None


def _read_progress(run_id: str) -> dict:
    """Đọc tiến trình từ orchestrator.sqlite, gom theo wl_id."""
    if not _ORCH_DB.exists():
        return {"runId": run_id, "watchlists": [], "alive": False, "counts": {}}
    conn = sqlite3.connect(f"file:{_ORCH_DB}?mode=ro", uri=True, timeout=10)
    try:
        rows = conn.execute(
            "SELECT wl_id, stage, status, error, started_at, finished_at "
            "FROM wl_stage_state WHERE run_id=? ORDER BY wl_id, stage",
            (run_id,)).fetchall()
    finally:
        conn.close()

    by_wl: dict[str, dict] = {}
    counts: dict[str, int] = {}
    for wl_id, stage, status, error, started, finished in rows:
        counts[status] = counts.get(status, 0) + 1
        wl = by_wl.setdefault(wl_id, {"wlId": wl_id, "stages": []})
        wl["stages"].append({
            "stage": stage, "status": status, "error": error or "",
            "startedAt": started, "finishedAt": finished,
        })
    return {
        "runId": run_id,
        "watchlists": list(by_wl.values()),
        "counts": counts,
        "alive": _proc_alive(run_id) is not None,
    }


@router.post("/run")
def _spawn_worker(run_id=None, wl_ids=None, resume=None, ai_only=False) -> dict:
    """Spawn worker process chạy pipeline. Dùng chung cho API + scheduler nền."""
    run_id = resume or run_id or ("run_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    if _proc_alive(run_id):
        raise HTTPException(409, f"run {run_id} dang chay")

    _RUN_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = _RUN_LOG_DIR / f"{run_id}.log"
    cmd = [sys.executable, "-X", "utf8", "-m",
           "python_backend.research.run_pipeline", "--run-id", run_id]
    if wl_ids:
        cmd += ["--wl", ",".join(wl_ids)]
    if resume:
        cmd += ["--resume", resume]
    if ai_only:
        cmd += ["--ai-only"]

    _invalidate_report_cache(wl_ids)

    logf = open(log_path, "a", encoding="utf-8")  # noqa: SIM115 (đời sống = worker)
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        cmd, cwd=str(_REPO_ROOT), stdout=logf, stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    with _procs_lock:
        _procs[run_id] = proc
    add_log(f"[H] research/run spawn run_id={run_id} pid={proc.pid}")
    return {"runId": run_id, "pid": proc.pid, "logPath": str(log_path)}


def start_run(req: RunRequest, current_user=Depends(get_current_user_optional)):
    """Spawn worker chạy pipeline thu thập data. Trả run_id để track progress."""
    return _spawn_worker(wl_ids=req.wlIds, resume=req.resume, ai_only=req.aiOnly)


@router.post("/report/{wid}/ai")
def generate_ai(wid: str, current_user=Depends(get_current_user_optional)):
    """Sinh (lại) AI cho 1 watchlist (không monitor). Trả run_id để track."""
    return start_run(RunRequest(wlIds=[wid], aiOnly=True), current_user)


@router.get("/run/{run_id}")
def run_progress(run_id: str, current_user=Depends(get_current_user_optional)):
    """Tiến trình 1 run (snapshot)."""
    return _read_progress(run_id)


@router.get("/run/{run_id}/stream")
async def run_progress_stream(run_id: str, request: Request):
    """SSE: stream tiến trình run mỗi 2s tới khi worker kết thúc."""
    def fetch():
        return _read_progress(run_id)

    def is_terminal(snap):
        # Dừng stream khi worker không còn sống VÀ không còn stage 'running'
        if snap.get("alive"):
            return False
        running = any(
            s["status"] == "running"
            for wl in snap.get("watchlists", []) for s in wl["stages"]
        )
        has_any = bool(snap.get("watchlists"))
        return has_any and not running

    return sse_response(poll_stream(request, fetch, interval_seconds=2.0,
                                    is_terminal=is_terminal))


@router.post("/run/{run_id}/stop")
def stop_run(run_id: str, current_user=Depends(get_current_user_optional)):
    """Dừng worker đang chạy (nếu được spawn trong phiên process này)."""
    with _procs_lock:
        p = _procs.get(run_id)
    if p is None or p.poll() is not None:
        raise HTTPException(404, "run khong chay (hoac spawn boi process khac)")
    p.terminate()
    add_log(f"[H] research/run stop run_id={run_id}")
    return {"runId": run_id, "stopped": True}


# ============================================================
# Phase 6 — Cấu hình (config) + Lịch (scheduler)
# ============================================================
# Field cho phép sửa qua web. secret=True → ẩn giá trị, chỉ trả cờ *_set.
_CONFIG_FIELDS = [
    ("inside_data_dir", False), ("inside_auto_fetch", False),
    ("chrome_mode", False), ("parallel_workers", False),
    ("auto_discover_competitors", False), ("auto_discover_threshold", False),
    ("auto_discover_max", False),
    ("keywordtool_api_key", True), ("mkvn_proxy_csv_path", False),
    ("monitor_backend", False),
]
_SECRET_KEYS = {k for k, secret in _CONFIG_FIELDS if secret}


class ConfigPatch(BaseModel):
    values: dict


@router.get("/config")
def get_config(current_user=Depends(get_current_user_optional)):
    """Cấu hình research (secret bị ẩn, chỉ trả cờ *_set)."""
    from python_backend.research.config import load_config

    cfg = load_config()
    out = {}
    for key, secret in _CONFIG_FIELDS:
        if secret:
            out[key] = ""
            out[f"{key}_set"] = bool((cfg.get(key) or "").strip())
        else:
            out[key] = cfg.get(key)
    return out


@router.put("/config")
def put_config(req: ConfigPatch, current_user=Depends(get_current_user_optional)):
    """Cập nhật cấu hình. Field secret rỗng/khuyết → giữ nguyên (không ghi đè)."""
    from python_backend.research.config import update_config

    allowed = {k for k, _ in _CONFIG_FIELDS}
    patch = {}
    for k, v in (req.values or {}).items():
        if k not in allowed:
            continue
        if k in _SECRET_KEYS and (v is None or str(v).strip() == ""):
            continue  # không xoá secret bằng giá trị rỗng
        patch[k] = v
    if patch:
        update_config(**patch)
    return get_config(current_user)


@router.get("/schedule")
def get_schedule(current_user=Depends(get_current_user_optional)):
    from python_backend.research import web_scheduler
    return web_scheduler.load_schedule()


class SchedulePatch(BaseModel):
    enabled: Optional[bool] = None
    time: Optional[str] = None          # "HH:MM" giờ máy
    wlIds: Optional[list[str]] = None
    aiOnly: Optional[bool] = None


@router.put("/schedule")
def put_schedule(req: SchedulePatch, current_user=Depends(get_current_user_optional)):
    from python_backend.research import web_scheduler

    d = {}
    if req.enabled is not None:
        d["enabled"] = bool(req.enabled)
    if req.time is not None:
        d["time"] = req.time
    if req.wlIds is not None:
        d["wlIds"] = req.wlIds or None
    if req.aiOnly is not None:
        d["aiOnly"] = bool(req.aiOnly)
    return web_scheduler.save_schedule(d)


def start_research_scheduler():
    """Khởi động thread scheduler nền (gọi từ main.py lifespan)."""
    from python_backend.research import web_scheduler
    web_scheduler.start(lambda wl_ids=None, ai_only=False:
                        _spawn_worker(wl_ids=wl_ids, ai_only=ai_only))


def stop_research_scheduler():
    from python_backend.research import web_scheduler
    web_scheduler.stop()
