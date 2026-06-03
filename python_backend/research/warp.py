# -*- coding: utf-8 -*-
"""Cloudflare WARP wrapper — tự bật/tắt WARP để bypass rate limit.

WARP đổi IP công cộng sang IP của Cloudflare → tránh bị YouTube/SocialBlade/
Google Trends throttle khi IP nhà đã bị flag.

Cách dùng:
    from . import warp
    if not warp.is_connected():
        warp.connect()
    # ... cào dữ liệu ...
    # warp.disconnect()  # tuỳ chọn — nếu muốn dùng IP nhà cho việc khác

API:
    is_connected() -> bool
    is_available() -> bool          # WARP có cài không
    connect(wait_sec=15) -> bool    # bật + đợi đến khi Connected
    disconnect() -> bool             # ngắt
    ensure_connected() -> bool      # bật nếu chưa, idempotent
    status() -> str                  # raw status string
    current_ip() -> str              # IP công cộng hiện tại
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

# Đường dẫn warp-cli.exe trên Windows (cài chuẩn)
_WARP_CLI_CANDIDATES = [
    r"C:\Program Files\Cloudflare\Cloudflare WARP\warp-cli.exe",
    r"C:\Program Files (x86)\Cloudflare\Cloudflare WARP\warp-cli.exe",
]


def _find_cli() -> str:
    """Trả đường dẫn warp-cli.exe nếu tìm được, không thì empty."""
    for p in _WARP_CLI_CANDIDATES:
        if Path(p).exists():
            return p
    return ""


def is_available() -> bool:
    """WARP có cài trên máy không."""
    return bool(_find_cli())


def _run(args: list, timeout: int = 30) -> tuple[int, str]:
    """Chạy warp-cli với args. Trả (returncode, output)."""
    cli = _find_cli()
    if not cli:
        return (-1, "warp-cli khong tim thay")
    try:
        proc = subprocess.run(
            [cli] + args,
            capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return (proc.returncode, (proc.stdout + proc.stderr).strip())
    except subprocess.TimeoutExpired:
        return (-1, f"timeout {timeout}s")
    except Exception as e:
        return (-1, str(e))


def status() -> str:
    """Trả raw status string từ warp-cli."""
    rc, out = _run(["status"])
    return out


def is_connected() -> bool:
    """True nếu WARP đang kết nối."""
    s = status().lower()
    return "connected" in s and "disconnected" not in s


def connect(wait_sec: int = 15) -> bool:
    """Kết nối WARP. Đợi tối đa wait_sec giây để chuyển sang Connected."""
    if is_connected():
        return True
    rc, out = _run(["connect"])
    # Đợi state chuyển sang Connected
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        if is_connected():
            return True
        time.sleep(1)
    return is_connected()


def disconnect() -> bool:
    """Ngắt WARP."""
    if not is_connected():
        return True
    rc, out = _run(["disconnect"])
    time.sleep(1)
    return not is_connected()


def ensure_connected(log_fn=print) -> bool:
    """Đảm bảo WARP đang Connected. Bật nếu chưa. Trả True nếu thành công."""
    if not is_available():
        log_fn("  [WARP] khong cai - bo qua")
        return False
    if is_connected():
        log_fn("  [WARP] da Connected")
        return True
    log_fn("  [WARP] dang ket noi...")
    ok = connect(wait_sec=15)
    if ok:
        log_fn("  [WARP] Connected OK")
    else:
        log_fn(f"  [WARP] LOI ket noi - status: {status()}")
    return ok


def current_ip(timeout: int = 10) -> str:
    """Trả IP công cộng hiện tại (qua https://api.ipify.org). Trả empty
    nếu lỗi mạng. Dùng để verify IP đã đổi sau khi connect."""
    try:
        import urllib.request
        with urllib.request.urlopen(
                "https://api.ipify.org?format=json",
                timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            import json
            return json.loads(data).get("ip", "")
    except Exception:
        return ""


if __name__ == "__main__":
    # CLI nhanh: python core/warp.py [status|connect|disconnect|ip]
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        print(f"Available: {is_available()}")
        print(f"Connected: {is_connected()}")
        print(f"Status: {status()}")
        print(f"IP: {current_ip()}")
    elif cmd == "connect":
        print("Connecting...")
        print("OK" if connect() else "FAIL")
        print(f"IP: {current_ip()}")
    elif cmd == "disconnect":
        print("Disconnecting...")
        print("OK" if disconnect() else "FAIL")
        print(f"IP: {current_ip()}")
    elif cmd == "ip":
        print(f"IP: {current_ip()}")
    elif cmd == "ensure":
        ensure_connected()
        print(f"IP: {current_ip()}")
    else:
        print("Dung: python core/warp.py [status|connect|disconnect|ip|ensure]")
