"""Đọc/ghi cấu hình pipeline — DEFAULTS override bằng ~/.youtube_research/config.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Nạp .env (YOUTUBE_API_KEY3...) — worker/CLI process không chạy main.load_env.
# Idempotent + overwrite=False nên không đè biến môi trường đã có.
try:
    from python_backend.config import load_env as _load_env
    _load_env()
except Exception:
    pass


def config_dir() -> Path:
    d = Path.home() / ".youtube_research"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return config_dir() / "config.json"


def youtube_api_keys() -> list:
    """Danh sách key Data API để xoay tua: YOUTUBE_API_KEY1/2/3 (.env)."""
    keys = []
    for name in ("YOUTUBE_API_KEY1", "YOUTUBE_API_KEY2", "YOUTUBE_API_KEY3"):
        v = (os.getenv(name, "") or "").strip()
        if v and v not in keys:
            keys.append(v)
    return keys


def _youtube_api_key() -> str:
    """1 key Data API (key đầu danh sách) — cho consumer chỉ cần 1 key."""
    keys = youtube_api_keys()
    return keys[0] if keys else ""


def _keywordtool_api_key() -> str:
    """Key Keywordtool từ .env (KEYWORDTOOL_API_KEY)."""
    return (os.getenv("KEYWORDTOOL_API_KEY", "") or "").strip()


DEFAULTS = {
    # ----- Thông số chạy -----
    "days": 7,
    "top_keywords": 30,
    "per_keyword": 10,
    "max_channel_videos": 30,
    "region": "",
    "output_dir": "",
    "last_channel": "",
    "chrome_mode": "headless",  # show | minimized | headless
    "user_name": "",
    "shared_history_dir": "",
    "parallel_workers": 3,  # 1-6
    # ----- Tự kết nạp đối thủ -----
    "auto_discover_competitors": True,
    "auto_discover_threshold": 35,  # % trùng ngách tối thiểu
    "auto_discover_max": 5,
    "keywordtool_api_key": "",
    "run_keywordtool": False,  # bật → runall harvest Keywordtool trước
    # ----- Local server -----
    "local_data_dir": "",
    "report_web_url": "https://api.tuanfmcaa.site",  # KHÔNG có / ở cuối
    # ----- YouTube Data API v3 (xoay tua .env: YOUTUBE_API_KEY1/2/3) -----
    "youtube_data_api_key": "",
}


def load_config() -> dict:
    p = config_path()
    if not p.exists():
        out = dict(DEFAULTS)
    else:
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Migration: headless (bool) cũ → chrome_mode (str) mới
            if "chrome_mode" not in data and "headless" in data:
                data["chrome_mode"] = "headless" if data["headless"] else "show"
            out = dict(DEFAULTS)
            out.update({k: v for k, v in data.items() if k in DEFAULTS})
        except Exception:
            out = dict(DEFAULTS)
    # API key luôn ƯU TIÊN .env, bỏ qua giá trị cũ còn sót trong config.json.
    env_key = _youtube_api_key()
    if env_key:
        out["youtube_data_api_key"] = env_key
    env_kt = _keywordtool_api_key()
    if env_kt:
        out["keywordtool_api_key"] = env_kt
    return out


def save_config(cfg: dict) -> None:
    p = config_path()
    clean = {k: cfg.get(k, v) for k, v in DEFAULTS.items()}
    clean["youtube_data_api_key"] = ""  # luôn lấy từ .env, không lưu ra file
    clean["keywordtool_api_key"] = ""   # luôn lấy từ .env, không lưu ra file
    with open(p, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)


def update_config(**kwargs: Any) -> dict:
    cfg = load_config()
    cfg.update({k: v for k, v in kwargs.items() if k in DEFAULTS})
    save_config(cfg)
    return cfg
