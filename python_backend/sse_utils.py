import asyncio
import json
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def format_event(data: Any, event: Optional[str] = None) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, default=str)
    lines = []
    if event:
        lines.append(f"event: {event}")
    for line in payload.split("\n"):
        lines.append(f"data: {line}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


async def poll_stream(
    request: Request,
    fetch: Callable[[], Any],
    *,
    interval_seconds: float = 2.0,
    heartbeat_seconds: float = 25.0,
    emit_initial: bool = True,
    is_terminal: Optional[Callable[[Any], bool]] = None,
    serialize: Optional[Callable[[Any], Any]] = None,
) -> AsyncIterator[str]:
    """Async generator that runs a sync `fetch` callable in a threadpool,
    diffs against last-emitted state, and yields SSE-formatted strings.
    Sends heartbeats while idle, stops when client disconnects or `is_terminal`
    returns True for the latest snapshot.
    """
    last_serialized: Any = object()
    last_heartbeat = 0.0
    elapsed_idle = 0.0
    first = True

    while True:
        if await request.is_disconnected():
            return

        try:
            snapshot = await run_in_threadpool(fetch)
        except Exception as exc:  # noqa: BLE001
            yield format_event({"error": str(exc)}, event="error")
            return

        encoded = serialize(snapshot) if serialize else snapshot
        changed = first or encoded != last_serialized

        if changed and (emit_initial or not first):
            last_serialized = encoded
            last_heartbeat = 0.0
            elapsed_idle = 0.0
            yield format_event(encoded)
        first = False

        if is_terminal and is_terminal(snapshot):
            return

        await asyncio.sleep(interval_seconds)
        elapsed_idle += interval_seconds
        last_heartbeat += interval_seconds

        if last_heartbeat >= heartbeat_seconds:
            last_heartbeat = 0.0
            yield ": ping\n\n"


def sse_response(generator: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
