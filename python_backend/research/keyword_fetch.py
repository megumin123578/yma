# -*- coding: utf-8 -*-
"""core/keyword_fetch.py — Thu hoạch từ khoá qua REST API keywordtool.io.

Gọi THẲNG REST API (api.keywordtool.io/v2) bằng API key → ghi trực
tiếp vào keyword_bank. KHÔNG qua MCP, KHÔNG qua context Claude → chạy
tự động hàng loạt, đóng gói được vào exe.

- Endpoint: POST /v2/search/suggestions/youtube
- metrics=true → mỗi từ khoá kèm volume + cmp (cạnh tranh) + cpc.
- type=suggestions → cây mở rộng cấp 1→2→3 của seed.
- Giới hạn: 15 request/phút (throttle 5s/lượt) + quota ngày (50-400
  tuỳ gói, DÙNG CHUNG web/API/MCP).

Resumable: seed đã 'done' trong keyword_bank thì bỏ qua → chạy lại
tiếp tục được.
"""
from __future__ import annotations

import sys
import time
import traceback

API_BASE = "https://api.keywordtool.io/v2"
PROVIDER = "youtube"
THROTTLE_SEC = 5.0          # 12 request/phút — an toàn dưới 15/phút


def api_key() -> str:
    try:
        try:
            from .config import load_config
        except ImportError:
            from .config import load_config
        return (load_config().get("keywordtool_api_key") or "").strip()
    except Exception:
        return ""


def _post(endpoint: str, payload: dict) -> dict:
    """POST JSON tới keywordtool API. Trả dict JSON. Raise nếu lỗi mạng."""
    import requests
    url = f"{API_BASE}/{endpoint}"
    r = requests.post(url, json=payload,
                      headers={"Content-Type": "application/json"},
                      timeout=90)
    try:
        data = r.json()
    except ValueError:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    if r.status_code != 200:
        msg = ""
        if isinstance(data, dict):
            msg = (data.get("error") or data.get("message")
                   or data.get("errors") or "")
        raise RuntimeError(f"HTTP {r.status_code}: {msg or data}")
    return data


def _parse(resp: dict) -> list:
    """Chuẩn hoá kết quả → [{keyword, search_volume, competition,
    competition_label, cpc, trend}].

    `results` của keywordtool là dict {tiền_tố: [danh sách từ khoá]} —
    phải LÀM PHẲNG rồi khử trùng (1 từ khoá có thể nằm ở nhiều tiền tố).
    """
    out = []
    seen = set()
    results = resp.get("results")
    items = []
    if isinstance(results, dict):
        for v in results.values():
            if isinstance(v, list):
                items.extend(v)
            elif isinstance(v, dict):
                items.append(v)
    elif isinstance(results, list):
        items = results
    elif isinstance(resp.get("data"), list):
        items = resp["data"]
    for d in items:
        if not isinstance(d, dict):
            continue
        kw = (d.get("string") or d.get("keyword") or "").strip()
        if not kw:
            continue
        nk = kw.lower()
        if nk in seen:
            continue
        seen.add(nk)
        out.append({
            "keyword": kw,
            "search_volume": d.get("volume"),
            "competition": d.get("cmp"),
            "competition_label": "",
            "cpc": d.get("cpc"),
            "trend": d.get("trend"),
        })
    return out


def fetch_suggestions(seed: str, kw_type: str = "suggestions") -> dict:
    """Gọi API lấy từ khoá cho 1 seed (kèm metrics). Trả JSON thô."""
    key = api_key()
    if not key:
        raise RuntimeError("Chưa cấu hình keywordtool_api_key")
    payload = {
        "apikey": key,
        "keyword": seed,
        "type": kw_type,
        "metrics": True,
        "output": "json",
    }
    return _post(f"search/suggestions/{PROVIDER}", payload)


def harvest_seed(seed: str) -> int:
    """Thu hoạch 1 seed → ghi keyword_bank → đánh dấu done. Trả số từ."""
    try:
        from . import keyword_bank
    except ImportError:
        from . import keyword_bank
    resp = fetch_suggestions(seed)
    rows = _parse(resp)
    n = keyword_bank.store_result(seed, rows)
    keyword_bank.mark_seed(keyword_bank.norm(seed), "done", n)
    return n


def harvest_pending(max_calls: int = 50, log=None) -> dict:
    """Thu hoạch các seed 'pending' (ưu tiên cao trước), tối đa max_calls
    lượt. Dừng nhẹ nhàng khi hết quota / lỗi. Trả {done, keywords, ...}."""
    try:
        from . import keyword_bank
    except ImportError:
        from . import keyword_bank

    def _log(m):
        if log:
            log(m)
        else:
            print(m, flush=True)

    if not api_key():
        _log("LỖI: chưa có keywordtool_api_key trong cấu hình.")
        return {"ok": False, "done": 0, "keywords": 0,
                "reason": "no_api_key"}

    seeds = keyword_bank.pending_seeds(max_calls)
    if not seeds:
        _log("Không còn seed nào pending — kho đã thu hoạch đủ.")
        return {"ok": True, "done": 0, "keywords": 0, "reason": "empty"}

    _log(f"Thu hoạch {len(seeds)} seed (giới hạn {max_calls} lượt)...")
    done = 0
    total_kw = 0
    for i, s in enumerate(seeds, 1):
        seed = s["seed"]
        try:
            n = harvest_seed(seed)
            done += 1
            total_kw += n
            _log(f"  [{i}/{len(seeds)}] {seed}: +{n} từ khoá")
        except Exception as e:
            emsg = str(e)
            _log(f"  [{i}/{len(seeds)}] {seed}: LỖI — {emsg}")
            low = emsg.lower()
            # hết quota / rate limit → DỪNG (seed còn lại giữ pending)
            if any(k in low for k in ("quota", "limit", "429",
                                      "exceed", "rate")):
                _log("  → Hết quota/giới hạn — DỪNG, để dành seed còn lại.")
                break
            keyword_bank.mark_seed(keyword_bank.norm(seed), "error", 0)
        if i < len(seeds):
            time.sleep(THROTTLE_SEC)

    st = keyword_bank.stats()
    _log(f"XONG đợt: {done} seed, +{total_kw} từ khoá. "
         f"Kho: {st['seeds_done']}/{st['seeds_total']} seed, "
         f"{st['keywords_total']} từ khoá.")
    return {"ok": True, "done": done, "keywords": total_kw, "stats": st}


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    argv = argv if argv is not None else sys.argv[1:]
    max_calls = 50
    if argv and argv[0].isdigit():
        max_calls = int(argv[0])
    try:
        res = harvest_pending(max_calls=max_calls)
        return 0 if res.get("ok") else 1
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
