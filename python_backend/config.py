import os
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


def _strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _load_dotenv_file(path: Path, overwrite: bool = False) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        raw_key, raw_value = line.split("=", 1)
        key = _normalize_key(raw_key)
        if not key:
            continue

        value = _strip_wrapping_quotes(raw_value.strip())
        _set_env_value(key, value, overwrite=overwrite)


def _resolve_path(base_dir: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    return base_dir / path


def load_env(path: Optional[str] = None) -> None:
    base_dir = Path(__file__).resolve().parent
    env_path = _resolve_path(base_dir, path) if path else base_dir / ".env"
    _load_dotenv_file(env_path)
