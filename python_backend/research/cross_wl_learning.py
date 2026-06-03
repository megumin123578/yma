# -*- coding: utf-8 -*-
"""Cross-WL Learning — propagate insight giữa WL có overlap audience.

WL A đang viral cụm "DIY Tractor + Cement" → check WL B (Mini Toys
Construction) có overlap audience không (qua shared competitor, shared
tags, shared subscriber demographic) → đề xuất WL B test cụm tương tự.

LOGIC:
1. Build adjacency graph giữa 25 WL:
   - Edge weight = số đối thủ chung + Jaccard similarity của top tags
2. Với mỗi WL: detect viral cluster mới (cụm có ≥3 video > median × 3)
3. Tìm các WL láng giềng (edge weight cao) chưa có cụm này
4. Đề xuất cho các WL láng giềng: "test cụm X — đã viral ở WL Y"

USAGE:
    from .cross_wl_learning import build_wl_graph, find_propagation_opportunities
    graph = build_wl_graph()
    opps = find_propagation_opportunities()
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from statistics import median
from typing import Callable, Optional


def _video_tags_set(video) -> set:
    tags = getattr(video, "tags", []) or []
    title = getattr(video, "title", "") or ""
    s = set(t.lower().strip() for t in tags if t and len(t) >= 3)
    text = re.sub(r"[^\w\s]", " ", title.lower())
    s |= set(w for w in text.split() if len(w) >= 3)
    return s


def _wl_top_tags(wl, top_n: int = 30) -> set:
    """Tổng hợp top tags từ tất cả channel trong WL."""
    from . import persistence
    counter = Counter()
    for c in wl.channels:
        recs = persistence.records_for_channel(c.channel_id)[:1]
        for r in recs:
            d = persistence.load_result(r["id"])
            if d is None:
                continue
            for v in (d.get("videos") or []):
                counter.update(_video_tags_set(v))
    return set(t for t, _ in counter.most_common(top_n))


def _wl_competitors(wl) -> set:
    """Set channel_id của tất cả đối thủ trong WL."""
    return set(c.channel_id for c in wl.channels
               if c.channel_id != (
                   wl.self_channel.channel_id if wl.self_channel else ""))


def build_wl_graph(log_fn: Callable[[str], None] = print) -> dict:
    """Build similarity graph giữa các WL.

    Returns dict {
        wls: [wl_id...],
        edges: [{wl_a, wl_b, shared_competitors, jaccard_tags, score}],
        wl_top_tags: {wl_id: set_of_tags},
    }
    """
    from . import watchlist as wl_mod

    wls = wl_mod.list_watchlists()
    log_fn(f"  🔗 Build graph cho {len(wls)} WL...")

    wl_tags_map = {}
    wl_comps_map = {}
    for w in wls:
        wl_tags_map[w.id] = _wl_top_tags(w, top_n=50)
        wl_comps_map[w.id] = _wl_competitors(w)

    edges = []
    wl_list = list(wls)
    for i, w1 in enumerate(wl_list):
        for w2 in wl_list[i+1:]:
            comp_overlap = len(wl_comps_map[w1.id] & wl_comps_map[w2.id])
            tags1 = wl_tags_map[w1.id]
            tags2 = wl_tags_map[w2.id]
            union = tags1 | tags2
            jaccard = (len(tags1 & tags2) / len(union)
                       if union else 0)
            # Score: weighted (đối thủ chung x3 quan trọng hơn tag chung)
            score = comp_overlap * 3 + jaccard * 50
            if score >= 1:
                edges.append({
                    "wl_a": w1.id, "wl_a_name": w1.name,
                    "wl_b": w2.id, "wl_b_name": w2.name,
                    "shared_competitors": comp_overlap,
                    "jaccard_tags": round(jaccard, 3),
                    "score": round(score, 1),
                })

    edges.sort(key=lambda e: e["score"], reverse=True)
    log_fn(f"  → {len(edges)} edge với score ≥ 1")
    return {
        "wls": [w.id for w in wls],
        "edges": edges,
        "wl_top_tags": {k: list(v) for k, v in wl_tags_map.items()},
    }


def detect_viral_cluster(wl_id: str, viral_ratio: float = 3.0,
                         min_cluster_size: int = 3,
                         log_fn: Callable[[str], None] = print) -> list:
    """Phát hiện cụm viral trong WL (cụm tag có ≥3 video > median × ratio).

    Returns list dict {cluster_tag, n_viral_videos, sample_videos, avg_vpd}
    """
    from . import watchlist as wl_mod, persistence
    w = wl_mod.load_watchlist(wl_id)
    if not w:
        return []

    # Collect all videos trong WL
    all_vids = []
    for c in w.channels:
        recs = persistence.records_for_channel(c.channel_id)[:1]
        for r in recs:
            d = persistence.load_result(r["id"])
            if d is None:
                continue
            for v in (d.get("videos") or []):
                vc = getattr(v, "view_count", 0) or 0
                do = getattr(v, "days_old", None)
                if do is None or do <= 0:
                    continue
                vpd = vc / max(do, 1)
                all_vids.append({
                    "video_id": getattr(v, "video_id", ""),
                    "title": getattr(v, "title", ""),
                    "channel": c.title,
                    "vpd": vpd,
                    "tags": _video_tags_set(v),
                })

    if len(all_vids) < 20:
        return []

    vpds = [v["vpd"] for v in all_vids]
    med = median(vpds)
    threshold = med * viral_ratio
    viral = [v for v in all_vids if v["vpd"] >= threshold]
    if len(viral) < min_cluster_size:
        return []

    # Cluster viral videos theo tag chung
    tag_videos = defaultdict(list)
    for v in viral:
        for t in v["tags"]:
            if len(t) < 4:
                continue
            tag_videos[t].append(v)

    clusters = []
    for tag, vids in tag_videos.items():
        if len(vids) < min_cluster_size:
            continue
        avg_vpd = sum(v["vpd"] for v in vids) / len(vids)
        clusters.append({
            "cluster_tag": tag,
            "n_viral_videos": len(vids),
            "avg_vpd": int(avg_vpd),
            "sample_videos": [
                {"title": v["title"][:60], "channel": v["channel"],
                 "vpd": int(v["vpd"])}
                for v in sorted(vids, key=lambda x: -x["vpd"])[:3]
            ],
        })
    clusters.sort(key=lambda c: c["avg_vpd"], reverse=True)
    return clusters[:10]


def find_propagation_opportunities(
    log_fn: Callable[[str], None] = print) -> list:
    """Tìm các cơ hội propagate insight giữa WL.

    Returns list dict {source_wl, target_wl, score, viral_cluster,
        reason}
    """
    graph = build_wl_graph(log_fn)
    edges = graph["edges"]
    if not edges:
        return []

    log_fn(f"  🔍 Tìm propagation opportunities...")
    from . import watchlist as wl_mod
    wls_by_id = {w.id: w for w in wl_mod.list_watchlists()}

    opportunities = []
    for edge in edges[:50]:  # top 50 strongest edges
        for src, dst in [(edge["wl_a"], edge["wl_b"]),
                         (edge["wl_b"], edge["wl_a"])]:
            clusters = detect_viral_cluster(src)
            if not clusters:
                continue
            # Target WL có cụm này chưa?
            target_tags = set(graph["wl_top_tags"].get(dst, []))
            for cluster in clusters[:3]:
                tag = cluster["cluster_tag"]
                if tag in target_tags:
                    continue  # target đã có cụm này
                opportunities.append({
                    "source_wl_id": src,
                    "source_wl_name": wls_by_id[src].name
                                       if src in wls_by_id else src,
                    "target_wl_id": dst,
                    "target_wl_name": wls_by_id[dst].name
                                       if dst in wls_by_id else dst,
                    "similarity_score": edge["score"],
                    "viral_cluster": cluster["cluster_tag"],
                    "cluster_avg_vpd": cluster["avg_vpd"],
                    "sample_videos": cluster["sample_videos"],
                    "reason": (
                        f"WL '{wls_by_id[src].name[:25]}' đang viral "
                        f"cụm '{tag}' ({cluster['avg_vpd']:,} vpd TB, "
                        f"{cluster['n_viral_videos']} video) — "
                        f"WL '{wls_by_id[dst].name[:25]}' có "
                        f"{edge['shared_competitors']} đối thủ chung + "
                        f"tag overlap {edge['jaccard_tags']:.1%}"
                    ),
                })

    # Dedupe (source, target, cluster) → keep first
    seen = set()
    deduped = []
    for o in opportunities:
        key = (o["source_wl_id"], o["target_wl_id"], o["viral_cluster"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(o)

    deduped.sort(key=lambda o: o["cluster_avg_vpd"], reverse=True)
    return deduped[:30]
