import contextvars
from typing import Optional

_request_log: contextvars.ContextVar[Optional[list]] = contextvars.ContextVar(
    "request_log", default=None
)


def init_request_log() -> None:
    _request_log.set([])


def add_log(line: str) -> None:
    buf = _request_log.get()
    if buf is not None:
        buf.append(line)


def drain_request_log() -> list:
    buf = _request_log.get() or []
    _request_log.set(None)
    return list(buf)
