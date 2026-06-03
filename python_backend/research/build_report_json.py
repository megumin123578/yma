# -*- coding: utf-8 -*-
"""CLI Phase 1 — dump báo cáo 1 watchlist ra JSON.

Chạy:  python -m python_backend.research.build_report_json <wid> [out.json]
Đọc data đã thu thập sẵn trong ~/.youtube_research/ → build_data() → JSON.
"""
import json
import sys

from python_backend.research.html_report import build_data


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python -m python_backend.research.build_report_json <wid> [out.json]")
        return 2
    wid = sys.argv[1]
    data = build_data(wid)
    if not data:
        print(f"Khong build duoc data cho {wid}")
        return 1
    out = sys.argv[2] if len(sys.argv) > 2 else f"{wid}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print("OK keys:", ", ".join(data.keys()))
    print("self.has:", data.get("self", {}).get("has"))
    print("competitors:", len(data.get("competitors", [])))
    print("written:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
