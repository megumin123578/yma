# -*- coding: utf-8 -*-
"""Title Pattern Miner — phân tích pattern tiêu đề từ top videos.

Phát hiện "công thức tiêu đề" data-driven:
- N-gram frequency (2-gram, 3-gram) trong top vs bottom videos
- Position của keyword (đầu/giữa/cuối tiêu đề)
- Có/không emoji, number, question mark, exclamation
- Title length (chars + words)
- Sentiment (positive/negative/curious)
- Correlate features với views_per_day

USAGE:
    from .title_pattern import analyze_title_patterns
    result = analyze_title_patterns(videos=[VideoInfo,...], log_fn=print)
    # result: dict {top_ngrams, position_stats, feature_correlation,
    #              winning_formula, losing_formula, recommendations}
"""
from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from typing import Callable, Optional


# Emoji range (đơn giản: detect common ranges)
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F680-\U0001F6FF"  # transport
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]+", flags=re.UNICODE
)


def _strip_emoji(text: str) -> str:
    return EMOJI_PATTERN.sub("", text)


def _has_emoji(text: str) -> bool:
    return bool(EMOJI_PATTERN.search(text))


def _has_number(text: str) -> bool:
    return bool(re.search(r"\d", text))


def _has_question(text: str) -> bool:
    return "?" in text or "？" in text


def _has_exclamation(text: str) -> bool:
    return "!" in text or "！" in text


def _has_uppercase_word(text: str) -> bool:
    """Có ít nhất 1 từ TOÀN HOA (>=3 ký tự)."""
    for w in text.split():
        clean = re.sub(r"[^\w]", "", w)
        if len(clean) >= 3 and clean.isupper():
            return True
    return False


def _starts_with_number(text: str) -> bool:
    return bool(re.match(r"^\s*\d", text))


def _word_count(text: str) -> int:
    return len(_strip_emoji(text).split())


def _char_count(text: str) -> int:
    return len(_strip_emoji(text))


def extract_features(title: str) -> dict:
    """Trích đặc trưng từ 1 title."""
    clean = _strip_emoji(title).strip()
    return {
        "title": title,
        "clean_title": clean,
        "word_count": _word_count(title),
        "char_count": _char_count(title),
        "has_emoji": _has_emoji(title),
        "has_number": _has_number(title),
        "has_question": _has_question(title),
        "has_exclamation": _has_exclamation(title),
        "has_uppercase": _has_uppercase_word(title),
        "starts_with_number": _starts_with_number(title),
    }


def _tokenize(text: str) -> list:
    """Tokenize đơn giản: lowercase, strip punctuation, split."""
    text = _strip_emoji(text).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return [t for t in text.split() if len(t) >= 2]


def _ngrams(tokens: list, n: int) -> list:
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


# Stopword cơ bản (EN + VI common)
STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "in", "on", "at", "for", "with", "by", "from", "as",
    "and", "or", "but", "if", "then", "so", "such", "than", "too", "very",
    "i", "me", "my", "you", "your", "he", "she", "it", "we", "they",
    "this", "that", "these", "those", "what", "which", "who",
    "when", "where", "why", "how", "all", "any", "each", "some",
    "có", "và", "là", "của", "trong", "cho", "với", "từ", "đến", "này",
    "đó", "kia", "ai", "tôi", "bạn", "chúng", "ta", "họ", "anh", "chị",
}


def _filter_meaningful_ngrams(ngrams: list, min_count: int = 2) -> list:
    """Lọc n-gram có ý nghĩa (skip nếu chứa toàn stopword)."""
    out = []
    for ng in ngrams:
        words = ng.split()
        if all(w in STOPWORDS for w in words):
            continue
        out.append(ng)
    return out


def _split_top_bottom(videos: list, top_pct: float = 0.3,
                     metric: str = "views_per_day") -> tuple:
    """Tách videos thành top X% và bottom X% theo metric.

    Returns: (top_list, bottom_list)
    """
    def _get(v):
        if metric == "views_per_day":
            return getattr(v, "views_per_day", 0) or 0
        return getattr(v, metric, 0) or 0

    sorted_v = sorted(videos, key=_get, reverse=True)
    n = len(sorted_v)
    cut = max(1, int(n * top_pct))
    return sorted_v[:cut], sorted_v[-cut:]


def _feature_correlation(videos: list, metric: str = "views_per_day") -> dict:
    """Tính trung bình metric cho từng feature on/off.

    Returns dict {feature: {on_avg, off_avg, lift_pct, n_on, n_off}}
    """
    feature_keys = ["has_emoji", "has_number", "has_question",
                    "has_exclamation", "has_uppercase",
                    "starts_with_number"]
    on_groups = defaultdict(list)
    off_groups = defaultdict(list)

    for v in videos:
        title = getattr(v, "title", "") or ""
        feats = extract_features(title)
        val = (getattr(v, metric, 0) or 0
               if metric != "views_per_day"
               else (getattr(v, "views_per_day", None)
                     or (getattr(v, "view_count", 0)
                         / max(getattr(v, "days_old", 1) or 1, 1))))
        for k in feature_keys:
            if feats[k]:
                on_groups[k].append(val)
            else:
                off_groups[k].append(val)

    out = {}
    for k in feature_keys:
        on = on_groups[k]
        off = off_groups[k]
        on_avg = statistics.mean(on) if on else 0
        off_avg = statistics.mean(off) if off else 0
        lift = (on_avg - off_avg) * 100 / off_avg if off_avg > 0 else 0
        out[k] = {
            "on_avg": round(on_avg, 0),
            "off_avg": round(off_avg, 0),
            "lift_pct": round(lift, 1),
            "n_on": len(on),
            "n_off": len(off),
        }
    return out


def _length_stats(videos: list, metric: str = "views_per_day") -> dict:
    """Phân tích tương quan length × metric."""
    buckets = {"<30 char": [], "30-50": [], "50-80": [], "80-120": [],
               ">120": []}
    for v in videos:
        title = getattr(v, "title", "") or ""
        c = _char_count(title)
        val = (getattr(v, "views_per_day", None)
               or (getattr(v, "view_count", 0)
                   / max(getattr(v, "days_old", 1) or 1, 1)))
        if c < 30:
            buckets["<30 char"].append(val)
        elif c < 50:
            buckets["30-50"].append(val)
        elif c < 80:
            buckets["50-80"].append(val)
        elif c < 120:
            buckets["80-120"].append(val)
        else:
            buckets[">120"].append(val)
    return {
        bucket: {
            "n": len(vals),
            "avg_views_per_day": round(statistics.mean(vals), 0)
                                  if vals else 0,
        } for bucket, vals in buckets.items()
    }


def analyze_title_patterns(videos: list, top_pct: float = 0.3,
                           min_videos: int = 10,
                           log_fn: Callable[[str], None] = print) -> dict:
    """Phân tích pattern tiêu đề từ list videos.

    Args:
        videos: list[VideoInfo]
        top_pct: % top vs bottom để compare (0.3 = top 30% vs bottom 30%)
        min_videos: tối thiểu N video để phân tích có ý nghĩa

    Returns: dict {
        n_videos, top_ngrams_winning, top_ngrams_losing,
        feature_correlation, length_stats,
        winning_formula, losing_formula, recommendations
    }
    """
    if not videos or len(videos) < min_videos:
        return {"error": f"Cần ≥{min_videos} video, có {len(videos or [])}",
                "n_videos": len(videos or [])}

    log_fn(f"  📝 title_pattern: phân tích {len(videos)} video")

    # Split top vs bottom
    top, bot = _split_top_bottom(videos, top_pct=top_pct)

    # N-grams
    top_tokens = []
    bot_tokens = []
    for v in top:
        top_tokens.extend(_tokenize(getattr(v, "title", "") or ""))
    for v in bot:
        bot_tokens.extend(_tokenize(getattr(v, "title", "") or ""))

    top_ngrams = (
        _filter_meaningful_ngrams(_ngrams(top_tokens, 2))
        + _filter_meaningful_ngrams(_ngrams(top_tokens, 3))
    )
    bot_ngrams = (
        _filter_meaningful_ngrams(_ngrams(bot_tokens, 2))
        + _filter_meaningful_ngrams(_ngrams(bot_tokens, 3))
    )

    top_counter = Counter(top_ngrams)
    bot_counter = Counter(bot_ngrams)

    # N-gram "winning" = xuất hiện nhiều ở top, ít ở bottom
    winning = []
    for ng, cnt in top_counter.most_common(50):
        if cnt < 2:
            break
        bot_cnt = bot_counter.get(ng, 0)
        if bot_cnt == 0 or cnt / max(bot_cnt, 1) >= 2:
            winning.append({"ngram": ng, "top_cnt": cnt, "bot_cnt": bot_cnt})

    losing = []
    for ng, cnt in bot_counter.most_common(50):
        if cnt < 2:
            break
        top_cnt = top_counter.get(ng, 0)
        if top_cnt == 0 or cnt / max(top_cnt, 1) >= 2:
            losing.append({"ngram": ng, "bot_cnt": cnt, "top_cnt": top_cnt})

    # Feature correlation
    feat_corr = _feature_correlation(videos)
    length = _length_stats(videos)

    # Sinh recommendation
    recommendations = []
    for k, v in feat_corr.items():
        if v["lift_pct"] > 30 and v["n_on"] >= 3:
            name = {
                "has_emoji": "thêm emoji",
                "has_number": "có số trong tiêu đề",
                "has_question": "đặt câu hỏi (?)",
                "has_exclamation": "có dấu chấm than (!)",
                "has_uppercase": "in HOA 1 từ",
                "starts_with_number": "bắt đầu bằng số",
            }.get(k, k)
            recommendations.append(
                f"NÊN {name} (+{v['lift_pct']:.0f}% views/ngày)")
        elif v["lift_pct"] < -20 and v["n_off"] >= 3:
            name = {
                "has_emoji": "emoji",
                "has_number": "số trong tiêu đề",
                "has_question": "dấu hỏi",
                "has_exclamation": "dấu chấm than",
                "has_uppercase": "in hoa",
                "starts_with_number": "bắt đầu bằng số",
            }.get(k, k)
            recommendations.append(
                f"TRÁNH {name} ({v['lift_pct']:.0f}% views/ngày)")

    # Length recommendation
    best_bucket = max(length.items(),
                      key=lambda x: x[1]["avg_views_per_day"])
    if best_bucket[1]["n"] >= 3:
        recommendations.append(
            f"ĐỘ DÀI tốt nhất: {best_bucket[0]} "
            f"({best_bucket[1]['avg_views_per_day']:.0f} views/ngày TB)")

    return {
        "n_videos": len(videos),
        "n_top": len(top),
        "n_bot": len(bot),
        "winning_ngrams": winning[:15],
        "losing_ngrams": losing[:10],
        "feature_correlation": feat_corr,
        "length_stats": length,
        "recommendations": recommendations,
    }
