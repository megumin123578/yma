# -*- coding: utf-8 -*-
"""Viral Score Predictor — dự đoán views/day cho video chưa upload.

Train từ data lịch sử (pkl history): linear regression với numpy.lstsq.
Output: predicted views/day + percentile so với median channel.

Features (numeric):
- log_subs (log10 channel subscribers)
- title_word_count
- title_char_count
- duration_seconds (capped 0-3600)
- posting_hour (0-23)
- posting_dow (0-6, Mon=0)
- has_emoji (0/1)
- has_number (0/1)
- has_question (0/1)
- has_uppercase_word (0/1)
- channel_median_vpd (log10 baseline kênh)

Target: log10(views_per_day + 1)

USAGE:
    from .viral_predictor import train_predictor, predict
    model = train_predictor(videos_data=[...])
    score = predict(model, channel_subs=100000, title="...",
                    duration=600, posting_hour=20, posting_dow=5,
                    channel_median_vpd=5000)
    # score: {predicted_vpd, percentile, confidence}
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Callable, Optional


FEATURE_NAMES = [
    "log_subs", "title_word_count", "title_char_count", "duration_sec",
    "posting_hour", "posting_dow",
    "has_emoji", "has_number", "has_question", "has_uppercase",
    "log_channel_median_vpd",
]


def _video_to_features(video, channel_subs: int,
                       channel_median_vpd: float) -> Optional[list]:
    """Trích vector feature từ 1 VideoInfo. Trả None nếu thiếu data."""
    try:
        from .title_pattern import extract_features
        title = getattr(video, "title", "") or ""
        if not title:
            return None
        duration = getattr(video, "duration_seconds", 0) or 0
        if duration <= 0:
            return None
        feats = extract_features(title)
        # Parse posting time
        pub = getattr(video, "published_at", "") or ""
        posting_hour = -1
        posting_dow = -1
        if pub:
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                posting_hour = dt.hour
                posting_dow = dt.weekday()
            except Exception:
                pass
        if posting_hour < 0:
            return None
        return [
            math.log10(max(channel_subs, 1)),
            float(feats["word_count"]),
            float(feats["char_count"]),
            float(min(duration, 3600)),
            float(posting_hour),
            float(posting_dow),
            float(feats["has_emoji"]),
            float(feats["has_number"]),
            float(feats["has_question"]),
            float(feats["has_uppercase"]),
            math.log10(max(channel_median_vpd, 1)),
        ]
    except Exception:
        return None


def collect_training_data(wl_ids: Optional[list] = None,
                           log_fn: Callable[[str], None] = print) -> tuple:
    """Lấy training data từ pkl history của tất cả channel.

    Returns: (X, y) numpy arrays.
        X: shape (n_samples, n_features)
        y: shape (n_samples,) = log10(views_per_day + 1)
    """
    import numpy as np
    from . import persistence, watchlist as wl_mod
    from statistics import median

    if wl_ids is None:
        wl_ids = [w.id for w in wl_mod.list_watchlists()]

    X_rows = []
    y_rows = []
    n_pkl = 0
    n_skip = 0
    seen_video = set()

    for wid in wl_ids:
        w = wl_mod.load_watchlist(wid)
        if not w:
            continue
        for c in [w.self_channel] + list(w.channels):
            if not c:
                continue
            recs = persistence.records_for_channel(c.channel_id)[:3]
            for r in recs:
                d = persistence.load_result(r["id"])
                if d is None:
                    n_skip += 1
                    continue
                n_pkl += 1
                ch = d.get("channel")
                vids = d.get("videos") or []
                if not ch or not vids:
                    continue
                subs = getattr(ch, "subscriber_count", 0) or 0
                if subs < 100:
                    continue
                # Tính median vpd cho channel này
                vpds = []
                for v in vids:
                    vc = getattr(v, "view_count", 0) or 0
                    do = getattr(v, "days_old", None)
                    if do is None or do <= 0:
                        continue
                    vpds.append(vc / max(do, 1))
                if len(vpds) < 5:
                    continue
                ch_median_vpd = median(vpds)
                # Mỗi video → 1 sample
                for v in vids:
                    vid = getattr(v, "video_id", "")
                    if not vid or vid in seen_video:
                        continue
                    seen_video.add(vid)
                    feats = _video_to_features(v, subs, ch_median_vpd)
                    if not feats:
                        n_skip += 1
                        continue
                    vc = getattr(v, "view_count", 0) or 0
                    do = getattr(v, "days_old", None) or 1
                    vpd = vc / max(do, 1)
                    X_rows.append(feats)
                    y_rows.append(math.log10(vpd + 1))

    log_fn(f"  📊 training data: {len(X_rows)} samples from {n_pkl} pkls "
           f"({n_skip} skip)")
    if not X_rows:
        return None, None
    return np.array(X_rows, dtype=float), np.array(y_rows, dtype=float)


def train_predictor(X=None, y=None, wl_ids: Optional[list] = None,
                    log_fn: Callable[[str], None] = print) -> dict:
    """Train linear regression với numpy.lstsq + thêm bias.

    Returns dict {coefficients, bias, n_samples, feature_names,
        r_squared, percentiles}
    """
    import numpy as np

    if X is None or y is None:
        X, y = collect_training_data(wl_ids, log_fn)
    if X is None or len(X) < 50:
        return {"error": f"Không đủ data train (cần ≥50, có "
                f"{len(X) if X is not None else 0})"}

    # Add bias column
    X_b = np.column_stack([X, np.ones(len(X))])
    # Least squares
    coef_full, residuals, rank, sv = np.linalg.lstsq(X_b, y, rcond=None)
    coef = coef_full[:-1]
    bias = coef_full[-1]

    # R² (coefficient of determination)
    y_pred = X_b @ coef_full
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    # Percentile thresholds của y (log scale)
    pcts = {f"p{p}": float(np.percentile(y, p))
            for p in [10, 25, 50, 75, 90, 95]}

    log_fn(f"  ✓ train_predictor: R²={r_squared:.3f}, "
           f"n_samples={len(X)}, p50={pcts['p50']:.2f}, "
           f"p90={pcts['p90']:.2f}")

    return {
        "coefficients": coef.tolist(),
        "bias": float(bias),
        "n_samples": len(X),
        "feature_names": FEATURE_NAMES,
        "r_squared": float(r_squared),
        "percentiles": pcts,
    }


def predict(model: dict, channel_subs: int, title: str,
            duration_seconds: int, posting_hour: int,
            posting_dow: int, channel_median_vpd: float) -> dict:
    """Dự đoán views/day cho 1 video chưa upload.

    Returns dict {predicted_vpd, predicted_log, percentile_rank,
        confidence_band, advice}
    """
    if "error" in model:
        return {"error": model["error"]}

    from .title_pattern import extract_features
    feats = extract_features(title)
    x = [
        math.log10(max(channel_subs, 1)),
        float(feats["word_count"]),
        float(feats["char_count"]),
        float(min(duration_seconds, 3600)),
        float(posting_hour),
        float(posting_dow),
        float(feats["has_emoji"]),
        float(feats["has_number"]),
        float(feats["has_question"]),
        float(feats["has_uppercase"]),
        math.log10(max(channel_median_vpd, 1)),
    ]
    # Predict: y = X @ coef + bias
    y_log = sum(c * xi for c, xi in zip(model["coefficients"], x)) \
            + model["bias"]
    predicted_vpd = max(0, 10 ** y_log - 1)

    # Percentile rank
    pcts = model["percentiles"]
    rank = 0
    for p_str in ["p10", "p25", "p50", "p75", "p90", "p95"]:
        if y_log >= pcts.get(p_str, 0):
            rank = int(p_str[1:])
    if y_log < pcts["p10"]:
        rank = 5  # < p10

    # Confidence: R² thấp → low confidence
    r2 = model.get("r_squared", 0)
    confidence = "low" if r2 < 0.4 else ("medium" if r2 < 0.7 else "high")

    advice = []
    if rank >= 90:
        advice.append(f"🔥 Tiềm năng VIRAL (top {100-rank}% — predicted "
                      f"{int(predicted_vpd):,} views/day)")
    elif rank >= 75:
        advice.append(f"⚡ Trên trung bình kênh (top {100-rank}% — "
                      f"~{int(predicted_vpd):,} views/day)")
    elif rank >= 50:
        advice.append(f"✓ Trung bình (~{int(predicted_vpd):,} views/day)")
    elif rank >= 25:
        advice.append(f"⚠ Dưới trung bình — cân nhắc đổi title/thumbnail "
                      f"(~{int(predicted_vpd):,} views/day)")
    else:
        advice.append(f"❌ Có nguy cơ flop (bottom {rank}% — "
                      f"~{int(predicted_vpd):,} views/day)")

    return {
        "predicted_vpd": int(predicted_vpd),
        "predicted_log10": round(y_log, 2),
        "percentile_rank": rank,
        "confidence": confidence,
        "model_r_squared": round(r2, 3),
        "advice": advice,
    }
