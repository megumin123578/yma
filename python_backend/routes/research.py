# routes/research.py
"""API nghiên cứu ngách (gộp pipeline YT vào yt_manage_app, 2026-06).

Phase 2: phục vụ báo cáo watchlist dưới dạng JSON.
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
from threading import Lock, Thread
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
_prewarm_lock = Lock()
_prewarm_started = False

# Báo cáo SEO (Claude CLI) đang sinh nền: tập wid để chống bấm trùng.
_seo_gen_lock = Lock()
_seo_generating: set[str] = set()
_comment_mine_lock = Lock()
_comment_mining: set[str] = set()
_comment_mine_last: dict[str, dict] = {}


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


def _watchlist_summary(w, connected=None, meta=None) -> dict:
    connected = connected if connected is not None else {}
    meta = meta if meta is not None else {}
    self_ch = w.self_channel
    self_tag = connected.get(self_ch.channel_id) if self_ch else None
    self_meta = (meta.get(self_ch.channel_id, {}) or {}) if self_ch else {}
    avatar = self_meta.get("avatar", "")
    return {
        "id": w.id,
        "name": w.name,
        "createdAt": getattr(w, "created_at", ""),
        "teamId": getattr(w, "team_id", "default"),
        "paused": bool(getattr(w, "paused", False)),
        "pausedReason": getattr(w, "paused_reason", ""),
        "avatar": avatar,
        "subs": int(self_meta.get("subs", 0) or 0),
        "totalViews": int(self_meta.get("totalViews", 0) or 0),
        "selfChannel": {
            "channelId": self_ch.channel_id,
            "title": self_ch.title,
            "connected": bool(self_tag),
            "accountTag": self_tag or "",
            "avatar": avatar,
        } if self_ch else None,
        "competitorCount": len(w.competitor_channels),
    }


@router.get("/watchlists")
def list_watchlists(current_user=Depends(get_current_user_optional)):
    """Danh sách watchlist (mới nhất trước)."""
    from python_backend.research import watchlist as wlmod

    t0 = time.perf_counter()
    wls = wlmod.list_watchlists()
    connected = _connected_channel_map()
    self_ids = [w.self_channel.channel_id for w in wls if w.self_channel]
    meta = _channel_meta_map(self_ids)
    items = [_watchlist_summary(w, connected, meta) for w in wls]
    # Kênh nhiều sub / view đứng trước.
    items.sort(key=lambda it: (it.get("subs", 0), it.get("totalViews", 0)), reverse=True)
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


def _enrich_report_channel_meta(data: dict) -> dict:
    """Fill tổng views/video từ metadata cache/API khi snapshot còn 0.

    Snapshot PostgreSQL hiện lưu payload `ChannelInfo.view_count/video_count`
    theo scraper; nhiều kênh có 2 field này = 0. Metadata này đã có sẵn qua
    channels.list cache nên dùng làm fallback cho card report. Subscribers giữ
    nguyên từ snapshot PostgreSQL.
    """
    if not isinstance(data, dict):
        return data
    channels = []
    for ch in [data.get("self")] + list(data.get("competitors") or []):
        if isinstance(ch, dict) and ch.get("channel_id"):
            channels.append(ch)
    ids = [ch["channel_id"] for ch in channels]
    meta = _channel_meta_map(ids)
    for ch in channels:
        m = meta.get(ch.get("channel_id")) or {}
        if not ch.get("total_views") and m.get("totalViews") is not None:
            ch["total_views"] = int(m.get("totalViews") or 0)
        if not ch.get("ch_vcount") and m.get("totalVideos") is not None:
            ch["ch_vcount"] = int(m.get("totalVideos") or 0)
    return data


def prewarm_research_caches() -> None:
    """Prewarm model viral + report mặc định trong thread nền.

    Không block startup/request. Frontend mặc định mở watchlist đầu tiên, nên
    cache report đầu tiên đủ để tránh lần mở trang đầu phải tự build lạnh.
    """
    global _prewarm_started
    with _prewarm_lock:
        if _prewarm_started:
            return
        _prewarm_started = True

    def _worker():
        try:
            from python_backend.research.viral_predictor import train_and_cache
            train_and_cache(force=False, log_fn=lambda s: None)
        except Exception as e:  # noqa: BLE001
            print(f"[research prewarm] viral model loi: {e}")

        try:
            from python_backend.research import watchlist as wlmod
            from python_backend.research.html_report import build_data

            wls = [w for w in wlmod.list_watchlists()
                   if not bool(getattr(w, "paused", False))]
            if not wls:
                return
            self_ids = [w.self_channel.channel_id for w in wls
                        if getattr(w, "self_channel", None)]
            meta = _channel_meta_map(self_ids)
            wls.sort(
                key=lambda w: (
                    int((meta.get(w.self_channel.channel_id, {}) or {})
                        .get("subs", 0) or 0) if w.self_channel else 0,
                    int((meta.get(w.self_channel.channel_id, {}) or {})
                        .get("totalViews", 0) or 0) if w.self_channel else 0,
                ),
                reverse=True,
            )
            wid = wls[0].id
            cache_key = f"{wid}|"
            with _cache_lock:
                hit = _report_cache.get(cache_key)
                if hit and (time.monotonic() - hit[0]) < _REPORT_TTL:
                    return
            t0 = time.perf_counter()
            data = _enrich_report_channel_meta(build_data(wid))
            if data:
                with _cache_lock:
                    _report_cache[cache_key] = (time.monotonic(), data)
                print("[research prewarm] report "
                      f"wid={wid} {(time.perf_counter() - t0) * 1000:.1f}ms")
        except Exception as e:  # noqa: BLE001
            print(f"[research prewarm] report loi: {e}")

    Thread(target=_worker, daemon=True, name="research-prewarm").start()


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
    date: str = "",
    current_user=Depends(get_current_user_optional),
):
    """Báo cáo 22 tab của 1 watchlist (JSON). `refresh=true` bỏ qua cache.
    `date=YYYY-MM-DD` xem báo cáo theo snapshot ngày đó (rỗng → mới nhất)."""
    now = time.monotonic()
    cache_key = f"{wid}|{date}"
    if not refresh:
        with _cache_lock:
            hit = _report_cache.get(cache_key)
            if hit and (now - hit[0]) < _REPORT_TTL:
                add_log(f"[H] research/report cache-hit wid={wid} date={date}")
                return hit[1]

    from python_backend.research.html_report import build_data

    t0 = time.perf_counter()
    try:
        data = build_data(wid, as_of_day=date)
        data = _enrich_report_channel_meta(data)
    except Exception as e:  # noqa: BLE001
        print(f"[research] build_data loi wid={wid}: {e}")
        raise HTTPException(status_code=500, detail=f"build_data failed: {e}")
    if not data:
        raise HTTPException(status_code=404, detail="Watchlist not found or no data")

    add_log(f"[H] research/report build wid={wid} date={date}: {(time.perf_counter() - t0) * 1000:.1f}ms")
    if data.get("viral_predictor_status") != "training":
        with _cache_lock:
            _report_cache[cache_key] = (now, data)
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
                for k in [k for k in _report_cache
                          if k == w or k.startswith(f"{w}|")]:
                    _report_cache.pop(k, None)
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


@router.get("/report/{wid}/seo")
def get_seo_report(
    wid: str,
    id: str = "",
    current_user=Depends(get_current_user_optional),
):
    """Báo cáo SEO (Claude CLI) của 1 watchlist.

    Trả {items, selected, generating}:
    - items: list metadata các báo cáo (cho dropdown chọn ngày), mới nhất trước.
    - selected: báo cáo đầy đủ (kèm content) theo `id`; rỗng → bản mới nhất.
    """
    from python_backend.research import seo_report
    items = seo_report.list_reports(wid)
    selected = seo_report.get_report(wid, id) if items else None
    with _seo_gen_lock:
        generating = wid in _seo_generating
    return {"items": items, "selected": selected, "generating": generating}


@router.post("/report/{wid}/seo")
def generate_seo_report(wid: str, current_user=Depends(get_current_user_optional)):
    """Sinh báo cáo SEO mới (nền) cho 1 watchlist. Trả ngay {status}."""
    with _seo_gen_lock:
        if wid in _seo_generating:
            return {"status": "generating"}
        _seo_generating.add(wid)

    def _worker():
        try:
            from python_backend.research import seo_report
            seo_report.generate(wid, log_fn=lambda m: add_log(f"[seo] {m}"))
        except Exception as e:  # noqa: BLE001
            add_log(f"[seo] generate loi wid={wid}: {e}")
        finally:
            with _seo_gen_lock:
                _seo_generating.discard(wid)

    Thread(target=_worker, daemon=True).start()
    add_log(f"[H] research/seo generate wid={wid}")
    return {"status": "started"}


@router.get("/report/{wid}/comments/mine")
def comment_mine_status(wid: str, current_user=Depends(get_current_user_optional)):
    """Trạng thái cào bình luận kênh chính. Trả {mining, last}."""
    with _comment_mine_lock:
        return {"mining": wid in _comment_mining,
                "last": _comment_mine_last.get(wid)}


@router.post("/report/{wid}/comments/mine")
def start_comment_mine(wid: str, current_user=Depends(get_current_user_optional)):
    """Cào bình luận 10 video mới nhất của kênh chính (nền). Trả ngay {status}."""
    with _comment_mine_lock:
        if wid in _comment_mining:
            return {"status": "mining"}
        _comment_mining.add(wid)

    def _worker():
        result, err = None, None
        try:
            from python_backend.research import (
                watchlist as wlmod, persistence, comment_miner)
            w = wlmod.load_watchlist(wid)
            self_ch = w.self_channel if w else None
            if not self_ch:
                raise RuntimeError("Watchlist không có kênh chính")
            days = persistence.snapshot_days_for_channel(self_ch.channel_id)
            self_res = (persistence.find_for_channel_as_of(
                self_ch.channel_id, days[0]) if days else None)
            videos = (self_res or {}).get("videos") or []
            if not videos:
                raise RuntimeError("Kênh chính chưa có video snapshot để cào")
            result = comment_miner.mine_channel_comments(
                self_ch.channel_id, self_ch.title or "", videos,
                log_fn=lambda m: add_log(f"[comment] {m}"))
        except Exception as e:  # noqa: BLE001
            err = str(e)
            add_log(f"[comment] mine loi wid={wid}: {e}")
        finally:
            with _comment_mine_lock:
                _comment_mining.discard(wid)
                _comment_mine_last[wid] = {
                    "new_comments": (result or {}).get("new_comments", 0),
                    "total_comments": (result or {}).get("total_comments", 0),
                    "error": err,
                }
            if err is None:
                _invalidate_report_cache([wid])

    Thread(target=_worker, daemon=True).start()
    add_log(f"[H] research/comments mine wid={wid}")
    return {"status": "started"}


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


@router.get("/runs/active")
def active_runs(current_user=Depends(get_current_user_optional)):
    """Run còn sống trong phiên process này (để UI re-attach sau khi mở lại)."""
    with _procs_lock:
        ids = list(_procs.keys())
    runs = [_read_progress(rid) for rid in ids if _proc_alive(rid)]
    return {"runs": runs}


# ----- Keywordtool harvest thủ công (nền, 1 lượt) -----
_kw_harvest = {"running": False, "last": None, "progress": None}
_kw_harvest_lock = Lock()


@router.post("/keywordtool/harvest")
def keywordtool_harvest(current_user=Depends(get_current_user_optional)):
    """Harvest seed pending qua API keywordtool (nền). Trả ngay {status}."""
    with _kw_harvest_lock:
        if _kw_harvest["running"]:
            return {"status": "running"}
        _kw_harvest["running"] = True
        _kw_harvest["progress"] = {"done": 0, "total": 0, "keywords": 0}

    def _worker():
        def _prog(done, total, kw):
            _kw_harvest["progress"] = {"done": done, "total": total, "keywords": kw}

        def _logfn(m):
            add_log(f"[keywordtool] {m}")
            print(f"[keywordtool] {m}", flush=True)

        try:
            from python_backend.research import keyword_fetch
            _kw_harvest["last"] = keyword_fetch.harvest_pending(
                50, _logfn, on_progress=_prog)
        except Exception as e:  # noqa: BLE001
            _kw_harvest["last"] = {"ok": False, "reason": str(e)[:200]}
            add_log(f"[keywordtool] harvest loi: {e}")
        finally:
            with _kw_harvest_lock:
                _kw_harvest["running"] = False

    Thread(target=_worker, daemon=True).start()
    add_log("[H] research/keywordtool harvest start")
    return {"status": "started"}


@router.get("/keywordtool/harvest")
def keywordtool_harvest_status(current_user=Depends(get_current_user_optional)):
    return {"running": _kw_harvest["running"], "last": _kw_harvest["last"],
            "progress": _kw_harvest.get("progress")}


# ============================================================
# Phase 6 — Cấu hình (config) + Lịch (scheduler)
# ============================================================
# Field cho phép sửa qua web. secret=True → ẩn giá trị, chỉ trả cờ *_set.
_CONFIG_FIELDS = [
    ("chrome_mode", False), ("parallel_workers", False),
    ("auto_discover_competitors", False), ("auto_discover_threshold", False),
    ("auto_discover_max", False),
    ("run_keywordtool", False),
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
    return web_scheduler.status()


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
    web_scheduler.save_schedule(d)
    return web_scheduler.status()


def start_research_scheduler():
    """Khởi động thread scheduler nền (gọi từ main.py lifespan)."""
    from python_backend.research import web_scheduler
    web_scheduler.start(lambda wl_ids=None, ai_only=False:
                        _spawn_worker(wl_ids=wl_ids, ai_only=ai_only))


def stop_research_scheduler():
    from python_backend.research import web_scheduler
    web_scheduler.stop()
