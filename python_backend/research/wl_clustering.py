# -*- coding: utf-8 -*-
"""Gom cụm Watchlist theo ĐỐI THỦ CHUNG — phục vụ stage_discover tránh
chạy trùng cho các WL cùng ngách.

User chốt 24/05: các WL có kênh chính cùng chủ đề thì:
- Chỉ chạy `tools/discover.py` cho 1 WL ANCHOR (kênh chính view/7d nhất)
- Các WL còn lại trong cụm: COPY kết quả candidate từ anchor → add vào WL

Tiết kiệm thời gian discover gấp 2-3 lần (vd cụm 4 WL cùng ngách
Slime/Sand chỉ chạy 1 lần thay 4 lần).

Logic gom cụm: 2 WL cùng cụm nếu chia sẻ ≥2 đối thủ chung + ≥20% so WL
ít đối thủ hơn (union-find).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional


_ANCHOR_CACHE_FILE = (Path.home() / ".youtube_research"
                       / "discover_anchors.json")


def compute_clusters() -> Dict[str, List[str]]:
    """Trả {cluster_id: [wid, wid, ...]} với cluster_id = wid đại diện.

    Tiêu chí: 2 WL cùng cụm khi share ≥2 channel_id đối thủ + ≥20% so
    WL ít đối thủ hơn. Union-find liên thông.
    """
    from . import watchlist as wl_mod

    wls = []
    for w in wl_mod.list_watchlists():
        full = wl_mod.load_watchlist(w.id)
        if not full:
            continue
        comp = set(c.channel_id for c in full.competitor_channels
                   if c.channel_id)
        wls.append({"id": full.id, "name": full.name or full.id,
                    "comp": comp})

    n = len(wls)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            ci, cj = wls[i]["comp"], wls[j]["comp"]
            ov = len(ci & cj)
            mn = min(len(ci), len(cj)) or 1
            if ov >= 2 and ov * 100 // mn >= 20:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[rj] = ri

    clusters: Dict[str, List[str]] = {}
    for i in range(n):
        root_wid = wls[find(i)]["id"]
        clusters.setdefault(root_wid, []).append(wls[i]["id"])

    return clusters


def _view_7d_for_wl(wid: str) -> float:
    """Trả view/ngày TB 7d của KÊNH CHÍNH của WL — dùng chọn anchor +
    sort priority daily_run.

    A62 (28/05 sáng — đồng bộ với summary_report A54): kênh chính SKIP
    SocialBlade (A36) → SB pkl rỗng → 5/6 WL active = 0 (sai sort).
    FIX: ƯU TIÊN Inside (channel_daily_metrics 7d), FALLBACK SB.

    Giống logic _build_wl_info() trong summary_report.py → 2 file ra
    cùng thứ tự sort cho user dễ theo dõi.
    """
    from . import watchlist as wl_mod, persistence
    from .daily_orchestrator import _compute_view_7d_avg
    import pickle as _pickle

    wl = wl_mod.load_watchlist(wid)
    if not wl or not wl.self_channel:
        return 0.0
    sc = wl.self_channel
    cid = sc.channel_id
    if not cid:
        return 0.0

    # ---- A62: ƯU TIÊN Inside daily_metrics_15d (last 7) ----
    try:
        from .analytics_inside import (
            get_channel_inside, match_account_tag)
        tag = match_account_tag(sc.title, cid)
        if tag:
            inside_ci = get_channel_inside(tag, recent_days=7)
            if inside_ci and inside_ci.get("has_data"):
                daily = inside_ci.get("daily_metrics_15d") or []
                last7 = daily[-7:] if len(daily) >= 7 else daily
                if last7:
                    views_vals = [int(d.get("views_daily", 0) or 0)
                                  for d in last7]
                    views_vals = [v for v in views_vals if v >= 0]
                    if views_vals:
                        return float(sum(views_vals) / len(views_vals))
    except Exception:
        pass  # silent fallback to SB

    # ---- FALLBACK: SB pkl (logic gốc) ----
    recs = persistence.records_for_channel(cid)
    if not recs:
        return 0.0
    data = persistence.load_result(recs[0]["id"])
    if data is None:
        return 0.0
    return _compute_view_7d_avg(data.get("socialblade") or {})


def select_anchor(cluster_wids: List[str]) -> str:
    """Chọn anchor = kênh chính có SB view/7d cao nhất trong cụm.

    Tiebreak: nếu tất cả = 0 (cụm chưa có SB) → chọn theo wid alphabet
    để stable.
    """
    if not cluster_wids:
        return ""
    if len(cluster_wids) == 1:
        return cluster_wids[0]
    scored = [(wid, _view_7d_for_wl(wid)) for wid in cluster_wids]
    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored[0][0]


def compute_anchor_map() -> Dict[str, str]:
    """Trả {wid: anchor_wid}. Mỗi WL biết anchor cụm mình.

    Lưu vào file ~/.youtube_research/discover_anchors.json — stage
    discover đọc khi quyết định chạy thật hay copy.
    """
    clusters = compute_clusters()
    anchor_map: Dict[str, str] = {}
    cluster_info: Dict[str, List[str]] = {}

    for root_wid, members in clusters.items():
        anchor = select_anchor(members)
        for m in members:
            anchor_map[m] = anchor
        cluster_info[anchor] = members

    return anchor_map


def save_anchor_map(anchor_map: Dict[str, str]) -> None:
    """Ghi map ra file để stage_discover đọc."""
    _ANCHOR_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ANCHOR_CACHE_FILE.write_text(
        json.dumps(anchor_map, ensure_ascii=False, indent=2),
        encoding="utf-8")


def load_anchor_map() -> Dict[str, str]:
    """Đọc map. Trả {} nếu chưa có file."""
    if not _ANCHOR_CACHE_FILE.exists():
        return {}
    try:
        return json.loads(
            _ANCHOR_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def summarize_clusters(log_fn=print) -> Dict[str, List[str]]:
    """In ra clusters + anchors. Dùng debug + log khi orchestrator chạy."""
    from . import watchlist as wl_mod

    clusters = compute_clusters()
    log_fn(f"=== {len(clusters)} cụm WL "
           f"({sum(len(m) for m in clusters.values())} WL tổng) ===")

    name_of = {w.id: w.name for w in wl_mod.list_watchlists()}

    cluster_list = []
    for root_wid, members in clusters.items():
        anchor = select_anchor(members)
        anchor_score = _view_7d_for_wl(anchor)
        cluster_list.append({
            "anchor": anchor,
            "anchor_name": name_of.get(anchor, anchor),
            "anchor_score": anchor_score,
            "members": members,
        })

    cluster_list.sort(
        key=lambda c: (-len(c["members"]), -c["anchor_score"]))

    for c in cluster_list:
        n_m = len(c["members"])
        if n_m == 1:
            log_fn(f"  · {c['anchor_name']} (1 WL, view/7d={int(c['anchor_score']):,})")
        else:
            log_fn(f"  ▣ {c['anchor_name']} ★ ANCHOR (view/7d={int(c['anchor_score']):,})")
            for m in c["members"]:
                if m == c["anchor"]:
                    continue
                log_fn(f"      · {name_of.get(m, m)} (member, view/7d={int(_view_7d_for_wl(m)):,})")

    return clusters


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    summarize_clusters()
    am = compute_anchor_map()
    save_anchor_map(am)
    print(f"\nĐã lưu anchor map: {len(am)} WL → "
          f"{len(set(am.values()))} anchor")
