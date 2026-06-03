# -*- coding: utf-8 -*-
"""3 insight nâng cao cho báo cáo HTML:
  1. topic_clusters(): gom keyword thành cluster theo từ chính chung.
  2. competitive_gaps(): tìm chủ đề đối thủ làm nhiều mà kênh chính chưa.
  3. generate_title_variants(): sinh 10-20 tiêu đề mẫu từ top patterns.

Đầu vào: list pkl đã save (1 self + N competitors). Output dict, gắn vào
data của html_report.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict


# Stopwords cơ bản EN + VN — token quá ngắn/phổ thông không dùng làm cluster
_STOP = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at",
    "for", "with", "by", "from", "is", "are", "was", "were", "be", "this",
    "that", "it", "as", "vs", "tv", "vn", "us", "uk",
    "và", "của", "cho", "với", "trong", "khi", "này", "đó", "thì", "là",
    "video", "youtube", "channel", "kanh", "kenh",
}


def _tokenize(s: str) -> list:
    """Tách chuỗi thành token đã lowercased, loại stopword + token ngắn."""
    if not s:
        return []
    # Tách theo whitespace + dấu câu cơ bản
    toks = re.split(r"[\s,\-_\|\(\)\[\]\.!?:;/]+", s.lower())
    return [t for t in toks if len(t) > 2 and t not in _STOP]


# ============================================================
# 1. TOPIC CLUSTERS
# ============================================================

def topic_clusters(channels_data: list, top_n: int = 12) -> list:
    """Gom keyword từ all kênh thành cluster + đo performance.

    channels_data: list dict {title, is_self, keywords, videos} từ pkl.

    Trả list dict {cluster, keywords[], n_kw, n_videos, view_median,
    view_max, top_video_title, top_video_views, is_self_active}.
    """
    # Bước 1: collect keyword + videos toàn ngách
    all_kw_lower = {}     # kw_lower -> kw_original (giữ case đẹp nhất)
    kw_to_channels = defaultdict(set)  # kw_lower -> set(channel_title)
    self_kws_lower = set()
    all_videos = []       # list (title, view_count, channel_title)

    for ch in channels_data:
        ch_title = ch.get("title", "")
        is_self = ch.get("is_self", False)
        for kw in ch.get("keywords", []):
            kl = kw.lower().strip()
            if not kl:
                continue
            all_kw_lower[kl] = all_kw_lower.get(kl) or kw
            kw_to_channels[kl].add(ch_title)
            if is_self:
                self_kws_lower.add(kl)
        for v in ch.get("videos", []):
            title = v.get("title") or ""
            views = v.get("view_count") or 0
            if title and views > 0:
                all_videos.append((title, views, ch_title))

    # Bước 2: cluster keyword theo "từ chính" (token dài nhất sau loại stop)
    clusters_kws = defaultdict(list)   # cluster_key -> [kw_original]
    for kl, kw_orig in all_kw_lower.items():
        toks = _tokenize(kl)
        if not toks:
            continue
        # Dùng từ DÀI NHẤT làm key cluster (thường là từ chính)
        key = max(toks, key=len)
        clusters_kws[key].append(kw_orig)

    # Bước 3: với mỗi cluster, tính metric
    out = []
    for cluster_key, kws in clusters_kws.items():
        if len(kws) < 1:
            continue
        # Video toàn ngách có TỪ CHÍNH trong tiêu đề
        matched_videos = [
            (t, v, c) for (t, v, c) in all_videos
            if cluster_key in t.lower()
        ]
        if len(matched_videos) < 2:
            continue  # Cluster yếu, bỏ qua
        views = [v for (_, v, _) in matched_videos]
        # Top video của cluster
        top_t, top_v, top_c = max(matched_videos, key=lambda x: x[1])
        # Kênh chính có active cluster này không
        is_self_active = any(kw.lower() in self_kws_lower for kw in kws)
        out.append({
            "cluster": cluster_key.title(),  # capitalize cho đẹp
            "keywords": sorted(set(kws))[:8],
            "n_kw": len(set(kws)),
            "n_videos": len(matched_videos),
            "view_median": int(statistics.median(views)),
            "view_max": top_v,
            "top_video_title": top_t,
            "top_video_channel": top_c,
            "is_self_active": is_self_active,
        })
    # Sort theo view_median descending
    out.sort(key=lambda c: c["view_median"], reverse=True)
    return out[:top_n]


# ============================================================
# 2. COMPETITIVE GAPS
# ============================================================

def competitive_gaps(channels_data: list, min_competitors: int = 2,
                     top_n: int = 15) -> list:
    """Tìm keyword/topic đối thủ làm nhiều mà kênh chính chưa làm.

    Trả list dict {keyword, n_competitors, sample_competitors[],
    competitor_video_views_median, competitor_top_video_title,
    competitor_top_video_views, competitor_top_channel}.
    """
    self_kws_lower = set()
    competitor_kws_to_channels = defaultdict(set)  # kw_lower -> set(comp_title)
    competitor_videos_by_kw = defaultdict(list)    # kw_lower -> [(title, views, ch)]

    # Phân loại self vs competitor
    for ch in channels_data:
        ch_title = ch.get("title", "")
        is_self = ch.get("is_self", False)
        kws = ch.get("keywords", [])
        if is_self:
            for kw in kws:
                self_kws_lower.add(kw.lower().strip())
        else:
            for kw in kws:
                kl = kw.lower().strip()
                if kl:
                    competitor_kws_to_channels[kl].add(ch_title)
            # Map keyword → competitor videos (match by title contains)
            for v in ch.get("videos", []):
                vtitle = (v.get("title") or "").lower()
                vviews = v.get("view_count") or 0
                if vviews <= 0:
                    continue
                for kw in kws:
                    kl = kw.lower().strip()
                    if kl and kl in vtitle:
                        competitor_videos_by_kw[kl].append(
                            (v["title"], vviews, ch_title))

    # Gap: keyword competitor có ≥min_competitors, self không có
    gaps = []
    for kl, comp_set in competitor_kws_to_channels.items():
        if kl in self_kws_lower:
            continue
        if len(comp_set) < min_competitors:
            continue
        vids = competitor_videos_by_kw.get(kl, [])
        if not vids:
            continue
        view_median = int(statistics.median([v for (_, v, _) in vids]))
        top_t, top_v, top_c = max(vids, key=lambda x: x[1])
        gaps.append({
            "keyword": kl.title(),
            "n_competitors": len(comp_set),
            "sample_competitors": sorted(comp_set)[:5],
            "competitor_video_views_median": view_median,
            "competitor_top_video_title": top_t,
            "competitor_top_video_views": top_v,
            "competitor_top_channel": top_c,
        })
    # Sort theo competitor_top_video_views descending (gap nào hot nhất)
    gaps.sort(key=lambda g: g["competitor_top_video_views"], reverse=True)
    return gaps[:top_n]


# ============================================================
# 3. TITLE A/B GENERATOR
# ============================================================

# Template ngôn ngữ EN (ngách YouTube quốc tế thường dùng EN)
_TEMPLATES_EN = [
    "{n} {emoji} {topic} {hook}",
    "{n} {topic} ({timeframe})",
    "How to {action} {topic} in {timeframe}",
    "I Tried {topic} for {timeframe} — Here's What Happened",
    "{topic} vs {topic2}: Which is Better?",
    "Top {n} {topic} You Need to See",
    "The Truth About {topic} {emoji}",
    "Why {topic} is {adjective} {emoji}",
    "{n} {adjective} {topic} Stories {emoji}",
    "{topic}: {hook}",
    "{action} {topic} — {result}",
    "{topic} Compilation — {n} Minutes Satisfying",
]

# Default fillers (sẽ override bằng top words từ patterns/keyword nếu có)
_FILLERS_DEFAULT = {
    "n": ["3", "5", "10", "20"],
    "emoji": ["💥", "🔥", "⚡", "🚀", "✨", "💦", "🎯"],
    "timeframe": ["30 Days", "24 Hours", "1 Week", "10 Minutes"],
    "action": ["Build", "Fix", "Make", "Test", "Try"],
    "hook": ["You Won't Believe", "Insane Results", "Crazy Outcome",
             "Shocking Truth"],
    "adjective": ["INSANE", "AMAZING", "EPIC", "CRAZY", "UNREAL"],
    "result": ["Mind Blown", "Goes Wrong", "Final Result"],
}


def generate_title_variants(self_videos: list, keywords: list,
                            title_patterns: dict, n_variants: int = 16) -> list:
    """Sinh n_variants tiêu đề mẫu dựa trên top patterns + top keywords.

    self_videos: list dict {title, view_count} của kênh chính.
    keywords: list keyword đã extract.
    title_patterns: dict {feature: {lift, ...}} từ html_report._title_stats.
    """
    import random as rnd

    # Build pool topic words: lấy keyword (case nice) + top keyword từ video top
    topic_pool = list(dict.fromkeys(keywords))[:15]
    if not topic_pool:
        return []

    # Tìm top winning features từ title_patterns (lift > 1.2 = ăn view)
    winning_feats = []
    if title_patterns:
        for feat, info in title_patterns.items():
            try:
                lift = float(info.get("lift", 0)) if isinstance(
                    info, dict) else float(info)
                if lift >= 1.2:
                    winning_feats.append((feat, lift))
            except (ValueError, TypeError):
                continue
    winning_feats.sort(key=lambda x: x[1], reverse=True)

    fillers = dict(_FILLERS_DEFAULT)
    # Topic pool dùng cho {topic} + {topic2}
    fillers["topic"] = topic_pool
    fillers["topic2"] = topic_pool

    out = []
    seen = set()
    rnd.seed(42)  # deterministic
    attempts = 0
    while len(out) < n_variants and attempts < n_variants * 8:
        attempts += 1
        tmpl = rnd.choice(_TEMPLATES_EN)
        # Fill placeholders
        try:
            keys_needed = re.findall(r"\{(\w+)\}", tmpl)
            replacements = {}
            for k in keys_needed:
                if k in fillers and fillers[k]:
                    replacements[k] = rnd.choice(fillers[k])
                else:
                    replacements[k] = "?"
            title = tmpl.format(**replacements)
            # Tránh duplicate topic
            if title in seen:
                continue
            seen.add(title)
            # Score đơn giản: số winning feature title này có
            t_lower = title.lower()
            score = 0
            for feat, lift in winning_feats:
                if isinstance(feat, str) and feat.lower() in t_lower:
                    score += lift
            out.append({"title": title, "score": round(score, 1),
                        "template": tmpl})
        except KeyError:
            continue
    # Sort theo score descending
    out.sort(key=lambda v: v["score"], reverse=True)
    return out[:n_variants]


# ============================================================
# Helper: trích dữ liệu từ pkl
# ============================================================

def extract_channels_data(res_list_with_self_flag: list) -> list:
    """Convert list (res, is_self, channel_title) thành format dùng cho
    topic_clusters/competitive_gaps.

    Mỗi res là pkl từ persistence (dict).
    """
    out = []
    for res, is_self, ch_title in res_list_with_self_flag:
        if not res:
            continue
        # Keywords từ tag_metrics hoặc keywords list
        kws = []
        for k in (res.get("keywords") or []):
            name = getattr(k, "keyword", None) if not isinstance(k, str) else k
            if name:
                kws.append(name)
        # Videos
        vids = []
        for v in (res.get("videos") or []):
            try:
                vids.append({
                    "title": getattr(v, "title", "") or "",
                    "view_count": int(getattr(v, "view_count", 0) or 0),
                })
            except Exception:
                continue
        out.append({
            "title": ch_title,
            "is_self": is_self,
            "keywords": kws,
            "videos": vids,
        })
    return out
