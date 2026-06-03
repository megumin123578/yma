"""
Comment Miner - khai thác bình luận khán giả của KÊNH CHÍNH.

Quy trình:
  - Chỉ cào 10 video mới đăng gần nhất của kênh chính (is_self)
  - Lấy hết bình luận mỗi video
  - Lưu vào SQLite, dò trùng → mỗi lần chạy chỉ thêm bình luận MỚI
  - Phân tích: từ khoá hay gặp, bình luận "xin làm video", top thích,
    cảm xúc thô

Mục đích: biết khán giả muốn gì, khen/chê gì → ý tưởng nội dung.
"""

from __future__ import annotations

import re
import threading
from typing import Callable, Optional

from . import snapshots


# Dấu hiệu bình luận dạng "yêu cầu / đề xuất nội dung" (đa ngôn ngữ)
_REQUEST_HINTS = [
    # tiếng Anh
    "please make", "please do", "can you make", "can you do",
    "make a video", "next video", "i want to see", "i wish",
    "please show", "do a video", "request", "pls make", "plz make",
    "you should make", "make more",
    # tiếng Việt
    "làm video", "muốn xem", "xin làm", "cho mình xem", "làm tiếp",
    "làm thêm", "ước gì", "đề nghị", "mong làm",
]

# Từ cảm xúc tích cực / tiêu cực (thô, đa ngôn ngữ phổ thông)
_POS_WORDS = {
    "nice", "good", "love", "best", "amazing", "great", "wow", "cool",
    "beautiful", "awesome", "perfect", "excellent", "super", "fantastic",
    "wonderful", "like", "satisfying", "tuyệt", "hay", "đẹp", "thích",
    "giỏi", "xuất sắc", "quá hay", "tuyệt vời",
}
_NEG_WORDS = {
    "bad", "fake", "worst", "boring", "stupid", "hate", "terrible",
    "awful", "poor", "useless", "dislike", "dở", "chán", "tệ", "kém",
    "thất vọng",
}

# Từ dừng (loại khi đếm tần suất) — Anh + Việt phổ thông
_STOP = {
    "the", "a", "an", "is", "are", "was", "this", "that", "it", "to",
    "of", "in", "on", "at", "for", "and", "or", "i", "you", "my", "we",
    "he", "she", "they", "so", "very", "too", "but", "with", "from",
    "your", "me", "do", "did", "be", "have", "has", "not", "no", "yes",
    "can", "will", "just", "all", "out", "up", "if", "as", "by", "what",
    "how", "when", "who", "video", "videos", "youtube", "channel",
    "like", "good", "nice", "thank", "thanks", "please", "đây", "này",
    "là", "và", "của", "có", "không", "cho", "được", "rất", "mình",
    "bạn", "em", "anh", "ạ", "ơi", "nhé", "thì", "lại", "một", "các",
    "với", "đi", "ơi", "ko", "wow", "haha", "hihi", "lol", "nha",
}


def _clean(text: str) -> str:
    """Bỏ emoji/ký tự lạ, giữ chữ + số + khoảng trắng."""
    return "".join(c if (c.isalnum() or c.isspace()) else " "
                   for c in (text or ""))


def mine_channel_comments(
    channel_id: str, channel_title: str, videos: list,
    chrome_mode: str = "headless",
    log_fn: Callable[[str], None] = print,
    max_videos: int = 10,
    max_comments_per_video: int = 3000,
    cancel_event: Optional[threading.Event] = None,
) -> dict:
    """Cào bình luận 10 video mới nhất của kênh + lưu (dò trùng).
    Trả dict tổng kết {videos_mined, new_comments, total_comments}."""
    from .youtube_client import PlaywrightBackend

    # 10 video mới đăng gần nhất
    vids = sorted([v for v in (videos or []) if getattr(v, "published_at", "")],
                  key=lambda v: v.published_at, reverse=True)[:max_videos]
    if not vids:
        log_fn("  ⚠ Không có video nào để cào bình luận.")
        return {"videos_mined": 0, "new_comments": 0,
                "total_comments": snapshots.count_comments(
                    channel_id=channel_id)}

    log_fn(f"💬 Khai thác bình luận kênh '{channel_title}' — "
           f"{len(vids)} video mới nhất...")
    client = PlaywrightBackend(chrome_mode=chrome_mode, log_fn=log_fn)
    new_total, mined = 0, 0
    try:
        for i, v in enumerate(vids, 1):
            if cancel_event and cancel_event.is_set():
                log_fn("  ✋ Đã dừng.")
                break
            log_fn(f"  ({i}/{len(vids)}) {v.title[:55]}")
            try:
                comments = client.get_video_comments(
                    v.video_id, max_comments=max_comments_per_video,
                    log_fn=log_fn)
                new_n = snapshots.save_comments(
                    channel_id, v.video_id, comments)
                new_total += new_n
                mined += 1
                log_fn(f"      Lấy {len(comments)} bình luận "
                       f"({new_n} mới được lưu)")
            except Exception as e:
                log_fn(f"      ⚠ Lỗi: {e}")
    finally:
        try:
            client.close()
        except Exception:
            pass

    total = snapshots.count_comments(channel_id=channel_id)
    log_fn(f"💬 Xong: {mined} video, +{new_total} bình luận mới, "
           f"kho hiện có {total} bình luận.")
    return {"videos_mined": mined, "new_comments": new_total,
            "total_comments": total}


def analyze_comments(channel_id: str) -> dict:
    """Phân tích kho bình luận của 1 kênh. Trả dict:
      {total_comments, top_liked, requests, top_words, top_phrases,
       sentiment}
    """
    comments = snapshots.get_comments(channel_id=channel_id)
    n = len(comments)
    if n == 0:
        return {"total_comments": 0}

    # Top bình luận nhiều lượt thích
    top_liked = sorted(comments, key=lambda c: c.get("like_count", 0),
                       reverse=True)[:15]

    # Bình luận dạng yêu cầu nội dung
    requests = []
    for c in comments:
        low = (c.get("text", "") or "").lower()
        if any(h in low for h in _REQUEST_HINTS):
            requests.append(c)
    requests.sort(key=lambda c: c.get("like_count", 0), reverse=True)

    # Tần suất từ + cụm 2 từ
    word_freq = {}
    phrase_freq = {}
    pos, neg = 0, 0
    for c in comments:
        text = c.get("text", "") or ""
        low = text.lower()
        # cảm xúc
        if any(w in low for w in _POS_WORDS):
            pos += 1
        elif any(w in low for w in _NEG_WORDS):
            neg += 1
        # từ
        words = [w for w in _clean(low).split()
                 if len(w) >= 3 and w not in _STOP and not w.isdigit()]
        for w in words:
            word_freq[w] = word_freq.get(w, 0) + 1
        for j in range(len(words) - 1):
            ph = words[j] + " " + words[j + 1]
            phrase_freq[ph] = phrase_freq.get(ph, 0) + 1

    top_words = sorted(word_freq.items(), key=lambda x: x[1],
                       reverse=True)[:25]
    top_phrases = [(p, c) for p, c in
                   sorted(phrase_freq.items(), key=lambda x: x[1],
                          reverse=True) if c >= 3][:15]

    neutral = n - pos - neg
    sentiment = {
        "positive": pos, "negative": neg, "neutral": neutral,
        "positive_pct": pos / n * 100 if n else 0,
        "negative_pct": neg / n * 100 if n else 0,
    }

    return {
        "total_comments": n,
        "top_liked": [
            {"author": c.get("author", ""), "text": c.get("text", ""),
             "like_count": c.get("like_count", 0),
             "video_id": c.get("video_id", "")}
            for c in top_liked
        ],
        "requests": [
            {"author": c.get("author", ""), "text": c.get("text", ""),
             "like_count": c.get("like_count", 0),
             "video_id": c.get("video_id", "")}
            for c in requests[:30]
        ],
        "request_count": len(requests),
        "top_words": top_words,
        "top_phrases": top_phrases,
        "sentiment": sentiment,
    }


def format_summary(data: dict) -> str:
    """Tóm tắt phân tích bình luận dạng text."""
    if not data or not data.get("total_comments"):
        return "Chưa có bình luận nào trong kho."
    s = data["sentiment"]
    lines = [
        f"Kho bình luận: {data['total_comments']:,} bình luận.",
        f"Cảm xúc: {s['positive']} tích cực ({s['positive_pct']:.0f}%), "
        f"{s['negative']} tiêu cực ({s['negative_pct']:.0f}%), "
        f"còn lại trung tính.",
        f"Bình luận dạng yêu cầu nội dung: {data['request_count']}.",
    ]
    if data.get("top_words"):
        tw = ", ".join(f"{w} ({c})" for w, c in data["top_words"][:12])
        lines.append(f"Từ hay gặp: {tw}")
    return "\n".join(lines)
