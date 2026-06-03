# -*- coding: utf-8 -*-
"""snapshot_store.py — Backend lưu snapshot cào (result dict) vào PostgreSQL.

Thay dần file pkl (~/.youtube_research/history/*.pkl). Đây CHỈ là tầng lưu
trữ độc lập — chưa wire vào pipeline; persistence.py sẽ delegate sang đây ở
bước sau (centralize-then-swap).

result dict chứa object sống: ChannelInfo / VideoInfo / KeywordEntry. Serializer
gắn thẻ `__type__` khi ghi JSON và rehydrate lại object khi đọc → giữ nguyên
@property (days_old, views_per_day) và KeywordEntry.sources về kiểu set.
"""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import text


# ============================================================
# Type registry (rehydrate)
# ============================================================
_TYPES: dict = {}


def _types() -> dict:
    global _TYPES
    if not _TYPES:
        try:
            from .youtube_client import ChannelInfo, VideoInfo
            from .keyword_extractor import KeywordEntry
            _TYPES = {"ChannelInfo": ChannelInfo,
                      "VideoInfo": VideoInfo,
                      "KeywordEntry": KeywordEntry}
        except Exception:
            _TYPES = {}
    return _TYPES


# ============================================================
# Serialize object/dict <-> JSON-safe
# ============================================================
def _to_jsonable(obj):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        out = {"__type__": type(obj).__name__}
        for f in dataclasses.fields(obj):
            out[f.name] = _to_jsonable(getattr(obj, f.name))
        return out
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)  # fallback an toàn (không để json.dumps vỡ)


def _from_jsonable(obj):
    if isinstance(obj, dict):
        t = obj.get("__type__")
        if t:
            data = {k: _from_jsonable(v) for k, v in obj.items()
                    if k != "__type__"}
            cls = _types().get(t)
            if cls is None:
                return data
            valid = {f.name for f in dataclasses.fields(cls)}
            kwargs = {k: v for k, v in data.items() if k in valid}
            if t == "KeywordEntry" and "sources" in kwargs:
                kwargs["sources"] = set(kwargs.get("sources") or [])
            try:
                return cls(**kwargs)
            except Exception:
                return data
        return {k: _from_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_from_jsonable(v) for v in obj]
    return obj


def result_to_payload(result: dict) -> dict:
    return _to_jsonable(result)


def result_from_payload(payload) -> dict:
    return _from_jsonable(_as_obj(payload))


def _as_obj(payload):
    """JSONB từ psycopg2 thường đã là dict/list; nếu là chuỗi thì parse."""
    if isinstance(payload, (dict, list)):
        return payload
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except Exception:
            return {}
    return payload or {}


# ============================================================
# PostgreSQL
# ============================================================
_ENGINE = None
_TRIED = False
_TABLE_READY = False

_DDL = """
CREATE TABLE IF NOT EXISTS research_snapshots (
    id BIGSERIAL PRIMARY KEY,
    job_id TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL DEFAULT 'channel',
    channel_id TEXT DEFAULT '',
    channel_title TEXT DEFAULT '',
    target TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    subscriber_count BIGINT DEFAULT 0,
    video_count INTEGER DEFAULT 0,
    keyword_count INTEGER DEFAULT 0,
    days INTEGER DEFAULT 0,
    xlsx_path TEXT DEFAULT '',
    input_keywords JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    payload JSONB NOT NULL
);
"""
_IDX = [
    "CREATE INDEX IF NOT EXISTS idx_research_snap_channel "
    "ON research_snapshots(channel_id, created_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_research_snap_type "
    "ON research_snapshots(type, created_at DESC);",
]


def _engine():
    global _ENGINE, _TRIED
    if not _TRIED:
        _TRIED = True
        try:
            from python_backend.db import engine
            _ENGINE = engine
        except Exception:
            _ENGINE = None
    return _ENGINE


def ensure_ready():
    """Trả engine nếu PG sẵn sàng + bảng tồn tại, else None (degrade an toàn)."""
    eng = _engine()
    if eng is None:
        return None
    global _TABLE_READY
    if not _TABLE_READY:
        try:
            with eng.begin() as conn:
                conn.execute(text(_DDL))
                for s in _IDX:
                    conn.execute(text(s))
            _TABLE_READY = True
        except Exception:
            return None
    return eng


def available() -> bool:
    return ensure_ready() is not None


_META_COLS = ("job_id, created_at, type, channel_id, channel_title, target, "
              "user_name, subscriber_count, video_count, keyword_count, days, "
              "xlsx_path, input_keywords")


def _meta_from_row(r) -> dict:
    """Map 1 dòng (theo _META_COLS) → entry dict tương thích index.json cũ."""
    created = r[1]
    return {
        "id": r[0],
        "date": created.isoformat() if hasattr(created, "isoformat") else str(created or ""),
        "type": r[2],
        "channel_id": r[3] or "",
        "channel_title": r[4] or "",
        "target": r[5] or "",
        "user_name": r[6] or "",
        "subscriber_count": int(r[7] or 0),
        "video_count": int(r[8] or 0),
        "keyword_count": int(r[9] or 0),
        "days": int(r[10] or 0),
        "xlsx_path": r[11] or "",
        "input_keywords": _as_obj(r[12]) or [],
        "pkl_path": "",  # giữ key cho code cũ đọc rec["pkl_path"] khỏi KeyError
    }


def save(meta: dict, result: dict) -> bool:
    """INSERT (upsert theo job_id) 1 snapshot. meta = output _compute_meta."""
    eng = ensure_ready()
    if eng is None:
        return False
    payload = json.dumps(result_to_payload(result), ensure_ascii=False)
    ik = json.dumps(meta.get("input_keywords") or [], ensure_ascii=False)
    with eng.begin() as conn:
        conn.execute(text("""
            INSERT INTO research_snapshots
              (job_id, type, channel_id, channel_title, target, user_name,
               subscriber_count, video_count, keyword_count, days, xlsx_path,
               input_keywords, created_at, payload)
            VALUES
              (:job_id, :type, :channel_id, :channel_title, :target, :user_name,
               :sub, :vid, :kw, :days, :xlsx,
               CAST(:ik AS JSONB), :created_at, CAST(:payload AS JSONB))
            ON CONFLICT (job_id) DO UPDATE SET payload = EXCLUDED.payload
        """), {
            "job_id": meta["id"], "type": meta.get("type", "channel"),
            "channel_id": meta.get("channel_id", ""),
            "channel_title": meta.get("channel_title", ""),
            "target": meta.get("target", ""),
            "user_name": meta.get("user_name", ""),
            "sub": int(meta.get("subscriber_count") or 0),
            "vid": int(meta.get("video_count") or 0),
            "kw": int(meta.get("keyword_count") or 0),
            "days": int(meta.get("days") or 0),
            "xlsx": meta.get("xlsx_path", ""),
            "ik": ik,
            "created_at": meta.get("date") or datetime.now().isoformat(timespec="seconds"),
            "payload": payload,
        })
    return True


def update(job_id: str, result: dict) -> bool:
    """Ghi đè payload của 1 snapshot (in-place mutate AI / SB → atomic UPDATE)."""
    eng = ensure_ready()
    if eng is None or not job_id:
        return False
    payload = json.dumps(result_to_payload(result), ensure_ascii=False)
    with eng.begin() as conn:
        res = conn.execute(text(
            "UPDATE research_snapshots SET payload = CAST(:p AS JSONB) "
            "WHERE job_id = :j"), {"p": payload, "j": job_id})
    return (res.rowcount or 0) > 0


def load(job_id: str) -> Optional[dict]:
    eng = ensure_ready()
    if eng is None or not job_id:
        return None
    with eng.connect() as conn:
        row = conn.execute(text(
            "SELECT payload FROM research_snapshots WHERE job_id = :j"),
            {"j": job_id}).fetchone()
    return result_from_payload(row[0]) if row else None


def find_latest(channel_id: str, exclude_id: str = "") -> Optional[dict]:
    """Snapshot mới nhất của 1 kênh (loại exclude_id) → result đã rehydrate."""
    eng = ensure_ready()
    if eng is None or not channel_id:
        return None
    with eng.connect() as conn:
        row = conn.execute(text(
            "SELECT payload FROM research_snapshots "
            "WHERE channel_id = :c AND type = 'channel' "
            "AND (:ex = '' OR job_id <> :ex) "
            "ORDER BY created_at DESC LIMIT 1"),
            {"c": channel_id, "ex": exclude_id or ""}).fetchone()
    return result_from_payload(row[0]) if row else None


def records_for_channel(channel_id: str) -> list:
    """Meta (KHÔNG payload) mọi snapshot của kênh, mới nhất trước."""
    eng = ensure_ready()
    if eng is None or not channel_id:
        return []
    with eng.connect() as conn:
        rows = conn.execute(text(
            f"SELECT {_META_COLS} FROM research_snapshots "
            "WHERE channel_id = :c AND type = 'channel' "
            "ORDER BY created_at DESC"), {"c": channel_id}).fetchall()
    return [_meta_from_row(r) for r in rows]


def list_all(limit: int = 500) -> list:
    eng = ensure_ready()
    if eng is None:
        return []
    with eng.connect() as conn:
        rows = conn.execute(text(
            f"SELECT {_META_COLS} FROM research_snapshots "
            "ORDER BY created_at DESC LIMIT :lim"), {"lim": limit}).fetchall()
    return [_meta_from_row(r) for r in rows]


def find_for_keywords(keywords: list, exclude_id: str = "",
                      min_overlap: float = 0.6) -> Optional[dict]:
    """Snapshot keyword-type có overlap từ khoá >= min_overlap → result."""
    eng = ensure_ready()
    if eng is None or not keywords:
        return None
    kw_set = {str(k).lower().strip() for k in keywords if k}
    if not kw_set:
        return None
    with eng.connect() as conn:
        rows = conn.execute(text(
            "SELECT job_id, input_keywords FROM research_snapshots "
            "WHERE type = 'keywords' AND (:ex = '' OR job_id <> :ex) "
            "ORDER BY created_at DESC"), {"ex": exclude_id or ""}).fetchall()
    for job_id, ik in rows:
        prev = {str(k).lower().strip() for k in (_as_obj(ik) or []) if k}
        if not prev:
            continue
        overlap = len(kw_set & prev) / max(len(kw_set), len(prev))
        if overlap >= min_overlap:
            return load(job_id)
    return None


def delete(job_id: str) -> bool:
    eng = ensure_ready()
    if eng is None or not job_id:
        return False
    with eng.begin() as conn:
        res = conn.execute(text(
            "DELETE FROM research_snapshots WHERE job_id = :j"), {"j": job_id})
    return (res.rowcount or 0) > 0


def clear() -> int:
    eng = ensure_ready()
    if eng is None:
        return 0
    with eng.begin() as conn:
        res = conn.execute(text("DELETE FROM research_snapshots"))
    return res.rowcount or 0


def prune_channel(channel_id: str, user_name: str, keep: int) -> int:
    """Giữ `keep` snapshot mới nhất của (channel_id, user) — xoá phần dư."""
    eng = ensure_ready()
    if eng is None or not channel_id or keep <= 0:
        return 0
    with eng.begin() as conn:
        res = conn.execute(text("""
            DELETE FROM research_snapshots
            WHERE type = 'channel' AND channel_id = :c AND user_name = :u
              AND job_id NOT IN (
                SELECT job_id FROM research_snapshots
                WHERE type = 'channel' AND channel_id = :c AND user_name = :u
                ORDER BY created_at DESC LIMIT :keep)
        """), {"c": channel_id, "u": user_name or "", "keep": keep})
    return res.rowcount or 0
