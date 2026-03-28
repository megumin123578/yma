import os
import json
from pathlib import Path
from typing import Optional


_INITIAL_ENV_KEYS = {
    key
    for key, value in os.environ.items()
    if str(value or "").strip() != ""
}


def _normalize_key(key: str) -> str:
    return (
        str(key or "")
        .strip()
        .replace("-", "_")
        .replace(" ", "_")
        .upper()
    )


def _normalize_value(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        items = [str(item).strip() for item in value if item is not None and str(item).strip() != ""]
        return ",".join(items) if items else None
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    normalized = str(value).strip()
    return normalized or None


def _set_env_value(key: str, value, overwrite: bool = False) -> None:
    key = _normalize_key(key)
    if not key:
        return

    if key in _INITIAL_ENV_KEYS:
        return

    normalized = _normalize_value(value)
    if normalized is None:
        return

    existing = os.environ.get(key)
    if not overwrite and existing is not None and existing.strip() != "":
        return
    os.environ[key] = normalized


def _iter_json_env_items(prefix: str, value):
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            child_name = _normalize_key(child_key)
            if not child_name:
                continue
            merged = f"{prefix}_{child_name}" if prefix else child_name
            yield from _iter_json_env_items(merged, child_value)
        return

    yield prefix, value


def _load_json_file(path: Path, overwrite: bool = False) -> None:
    if not path.exists():
        return

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return

    if not isinstance(payload, dict):
        return

    direct_env = payload.get("env")
    if isinstance(direct_env, dict):
        for key, value in direct_env.items():
            _set_env_value(key, value, overwrite=overwrite)

    for key, value in payload.items():
        if key == "env" and isinstance(value, dict):
            continue
        for env_key, env_value in _iter_json_env_items("", {key: value}):
            _set_env_value(env_key, env_value, overwrite=overwrite)


def _resolve_path(base_dir: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    return base_dir / path


def load_env(path: Optional[str] = None) -> None:
    base_dir = Path(__file__).resolve().parent
    config_path = _resolve_path(base_dir, path) if path else base_dir / "config.json"
    _load_json_file(config_path)
