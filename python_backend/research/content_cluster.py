"""
Content Cluster - phân cụm video của 1 kênh theo chủ đề/format,
rồi xếp hạng cụm theo lượt xem trung bình.

Mục đích: trả lời "format/series nào của kênh đang thắng?"
Phương pháp: gom video theo cụm từ chung trong tiêu đề (n-gram), không
dùng thư viện ML — chạy nhanh, cục bộ, giải thích được.
"""

from __future__ import annotations

import re
from typing import Optional


# Từ chung chung trong ngách (không dùng để gom cụm — không phân biệt được)
_STOPWORDS = {
    # tiếng Anh phổ thông
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for",
    "with", "from", "by", "is", "are", "this", "that", "it", "as", "be",
    "your", "you", "my", "i", "we", "how", "what", "new", "best", "top",
    "vs", "via", "amp",
    # chung chung trong ngách DIY/mini tractor (không phân biệt)
    "diy", "mini", "video", "videos", "making", "make", "made", "build",
    "builds", "building", "project", "projects", "science", "creative",
    "idea", "ideas", "amazing", "satisfying", "real", "realistic",
    "machine", "machines", "model", "working", "tractor", "miniature",
}


def _strip_emoji(text: str) -> str:
    """Bỏ emoji và ký tự đặc biệt, giữ chữ + số + khoảng trắng."""
    # Giữ chữ cái (mọi ngôn ngữ), số, khoảng trắng
    out = []
    for ch in text:
        if ch.isalnum() or ch.isspace():
            out.append(ch)
        else:
            out.append(" ")
    return "".join(out)


def _normalize_words(title: str) -> list:
    """Chuẩn hoá tiêu đề → list từ (lowercase, bỏ emoji/dấu câu/stopword)."""
    if not title:
        return []
    text = _strip_emoji(title.lower())
    words = [w for w in text.split() if len(w) >= 2]
    return words


def _ngrams(words: list, n: int) -> list:
    """Sinh n-gram từ list từ."""
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


def _candidate_phrases(words: list) -> set:
    """Sinh các cụm từ ứng viên (1-2-3 gram) đã loại stopword thuần."""
    phrases = set()
    # 1-gram: chỉ giữ từ không phải stopword
    for w in words:
        if w not in _STOPWORDS and len(w) >= 3:
            phrases.add(w)
    # 2-gram, 3-gram: giữ nếu KHÔNG phải toàn stopword
    for n in (2, 3):
        for g in _ngrams(words, n):
            parts = g.split()
            non_stop = [p for p in parts if p not in _STOPWORDS]
            if non_stop:  # có ít nhất 1 từ "có nghĩa"
                phrases.add(g)
    return phrases


def cluster_channel_videos(videos: list,
                           max_clusters: int = 10,
                           channel_name: str = "") -> dict:
    """
    Gom video của 1 kênh thành cụm chủ đề + xếp hạng theo lượt xem TB.

    videos: list VideoInfo (có .title, .view_count, .video_id, .url)
    channel_name: tên kênh — các từ trong tên sẽ bị loại khỏi nhãn cụm
                  (tên kênh không phải chủ đề nội dung)
    Trả dict:
      {
        "clusters": [ {label, video_count, total_views, avg_views,
                       median_views, videos:[...], top_video:{}}, ... ],
        "total_videos": int,
        "clustered_videos": int,   # số video gom được vào cụm (>=2 video)
        "unique_videos": int,      # số video lẻ (không thuộc cụm nào)
        "best_cluster": dict | None,
        "is_series_channel": bool, # True nếu kênh có series lặp lại rõ
      }
    """
    vids = [v for v in (videos or []) if getattr(v, "title", "")]
    total = len(vids)
    if total < 3:
        return {"clusters": [], "total_videos": total,
                "clustered_videos": 0, "unique_videos": total,
                "best_cluster": None, "is_series_channel": False}

    # Loại từ trong tên kênh khỏi cụm từ ứng viên (tên kênh ≠ chủ đề)
    channel_words = set(_normalize_words(channel_name))

    # 1) Chuẩn hoá + sinh cụm từ ứng viên cho mỗi video
    vid_words = []
    for v in vids:
        words = _normalize_words(v.title)
        vid_words.append(words)

    # 2) Document frequency: mỗi cụm từ xuất hiện trong bao nhiêu video
    df = {}  # phrase -> set chỉ số video
    for i, words in enumerate(vid_words):
        for ph in _candidate_phrases(words):
            # Bỏ cụm từ chỉ gồm từ trong tên kênh
            ph_words = set(ph.split())
            if ph_words and ph_words.issubset(channel_words):
                continue
            df.setdefault(ph, set()).add(i)

    # 3) Lọc cụm từ ứng viên làm "nhãn cụm":
    #    - xuất hiện >= 2 video (mới thành cụm)
    #    - không quá 70% tổng video (không phải từ chung chung của kênh)
    hi_cut = max(2, int(total * 0.7))
    candidates = []
    for ph, idxs in df.items():
        cnt = len(idxs)
        if 2 <= cnt <= hi_cut:
            # điểm: ưu tiên cụm gom nhiều video + cụm từ dài (cụ thể hơn)
            n_words = len(ph.split())
            score = cnt * 10 + n_words * 3
            candidates.append((ph, idxs, cnt, score))

    # 4) Gom cụm tham lam: cụm điểm cao trước, mỗi video chỉ vào 1 cụm
    candidates.sort(key=lambda x: x[3], reverse=True)
    assigned = {}  # video index -> cluster label
    clusters_raw = {}  # label -> list video index
    for ph, idxs, cnt, score in candidates:
        free = [i for i in idxs if i not in assigned]
        if len(free) < 2:
            continue  # không đủ 2 video chưa gán → bỏ
        for i in free:
            assigned[i] = ph
        clusters_raw[ph] = free
        if len(clusters_raw) >= max_clusters:
            break

    # 5) Video chưa gom → cụm "Khác"
    unassigned = [i for i in range(total) if i not in assigned]

    # 6) Tính chỉ số mỗi cụm
    def _label(ph: str) -> str:
        return " ".join(w.capitalize() for w in ph.split())

    clusters = []
    for ph, idxs in clusters_raw.items():
        cvids = [vids[i] for i in idxs]
        views = sorted(v.view_count for v in cvids)
        total_v = sum(views)
        top = max(cvids, key=lambda v: v.view_count)
        clusters.append({
            "label": _label(ph),
            "video_count": len(cvids),
            "total_views": total_v,
            "avg_views": total_v // len(cvids),
            "median_views": views[len(views) // 2],
            "videos": [
                {"title": v.title, "view_count": v.view_count,
                 "video_id": getattr(v, "video_id", ""),
                 "url": getattr(v, "url", "")}
                for v in sorted(cvids, key=lambda v: v.view_count,
                                reverse=True)
            ],
            "top_video": {"title": top.title,
                          "view_count": top.view_count,
                          "url": getattr(top, "url", "")},
        })

    # Sắp xếp cụm theo lượt xem trung bình giảm dần
    clusters.sort(key=lambda c: c["avg_views"], reverse=True)

    # Cụm "Khác" (video lẻ) đưa xuống cuối
    if unassigned:
        ovids = [vids[i] for i in unassigned]
        views = sorted(v.view_count for v in ovids)
        total_v = sum(views)
        clusters.append({
            "label": "Khác (video lẻ, chưa thành series)",
            "video_count": len(ovids),
            "total_views": total_v,
            "avg_views": total_v // max(len(ovids), 1),
            "median_views": views[len(views) // 2] if views else 0,
            "videos": [
                {"title": v.title, "view_count": v.view_count,
                 "video_id": getattr(v, "video_id", ""),
                 "url": getattr(v, "url", "")}
                for v in sorted(ovids, key=lambda v: v.view_count,
                                reverse=True)
            ],
            "top_video": None,
            "is_other": True,
        })

    clustered = sum(c["video_count"] for c in clusters
                    if not c.get("is_other"))
    # Kênh "có series" nếu >= 40% video gom được vào cụm
    is_series = clustered >= total * 0.4

    best = None
    real_clusters = [c for c in clusters if not c.get("is_other")]
    if real_clusters:
        best = max(real_clusters, key=lambda c: c["avg_views"])

    return {
        "clusters": clusters,
        "total_videos": total,
        "clustered_videos": clustered,
        "unique_videos": len(unassigned),
        "best_cluster": best,
        "is_series_channel": is_series,
    }


def format_summary(data: dict) -> str:
    """Tóm tắt phân cụm dạng text (cho log / copy)."""
    if not data or not data.get("clusters"):
        return "Không đủ video để phân cụm."
    lines = []
    total = data["total_videos"]
    clustered = data["clustered_videos"]
    lines.append(f"Phân cụm {total} video → {clustered} video thuộc series, "
                 f"{data['unique_videos']} video lẻ.")
    if not data["is_series_channel"]:
        lines.append("⚠ Kênh chưa có series lặp lại rõ — đa số video là "
                     "chủ đề riêng lẻ.")
    lines.append("")
    for i, c in enumerate(data["clusters"], 1):
        if c.get("is_other"):
            lines.append(f"  • {c['label']}: {c['video_count']} video, "
                         f"TB {c['avg_views']:,} lượt xem")
        else:
            lines.append(f"  {i}. {c['label']}: {c['video_count']} video, "
                         f"TB {c['avg_views']:,} lượt xem "
                         f"(cao nhất {c['top_video']['view_count']:,})")
    return "\n".join(lines)
