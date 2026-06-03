# -*- coding: utf-8 -*-
"""Phân tích thumbnail bằng Claude Vision API.

Bổ sung cho `thumbnail_analyzer.py` (chỉ đo pixel brightness/contrast).
Vision API HIỂU nội dung: subject (face/object/text/scene), emotion,
composition, color scheme, text overlay → đề xuất cải thiện cụ thể.

USAGE:
    from .thumbnail_vision import analyze_thumbnails_for_channel
    result = analyze_thumbnails_for_channel(
        channel_id="UCxxxx",
        videos=[VideoInfo, ...],
        top_n=10,
        log_fn=print,
    )
    # result: dict {video_id: vision_analysis_dict}

Cost: ~$0.003 / thumbnail (claude-haiku-4-5 vision). 25 WL × 10 thumb
= 250 image × $0.003 = $0.75/kỳ. Rẻ.
"""
from __future__ import annotations

import base64
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, Optional

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-4-5"  # rẻ + đủ tốt cho thumbnail


VISION_PROMPT = """Phân tích thumbnail YouTube này làm tham mưu cho creator.

Trả về JSON object với các trường (KHÔNG markdown, chỉ JSON):
{
  "subject": "<face_closeup|face_medium|object_centered|scene_wide|text_dominant|split_compare|product_demo|other>",
  "emotion": "<happy|surprise|curious|serious|fear|disgust|neutral|none>",
  "composition": "<center|rule_of_thirds|symmetric|diagonal|filled|empty>",
  "color_scheme": "<warm|cool|neon|pastel|monochrome|high_contrast|natural>",
  "dominant_colors": ["<color1>", "<color2>", "<color3>"],
  "text_overlay": {
    "present": <true|false>,
    "readable": <true|false>,
    "word_count_estimate": <int>,
    "position": "<top|bottom|left|right|center|multiple>"
  },
  "face_count": <int 0-N>,
  "click_score": <int 1-10 (your guess of CTR strength)>,
  "click_score_reason": "<1 câu giải thích>",
  "strengths": ["<điểm mạnh 1>", "<điểm mạnh 2>"],
  "weaknesses": ["<điểm yếu 1>", "<điểm yếu 2>"],
  "improvement": "<1-2 câu đề xuất cải thiện cụ thể, KHÔNG chung chung>"
}

Tiêu chí:
- click_score 1-3: yếu (text trộn lẫn, không có focus, màu nhạt)
- click_score 4-6: ổn (có focus rõ nhưng không nổi bật)
- click_score 7-9: tốt (face/emotion mạnh + text rõ + color contrast cao)
- click_score 10: xuất sắc (mọi yếu tố tối ưu, hứa hẹn CTR > 10%)

Đánh giá khắt khe — đa số thumbnail thuộc 4-6, hiếm khi 9-10."""


def _encode_image_b64(image_path: str) -> str:
    """Đọc file ảnh + encode base64."""
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def _detect_media_type(image_path: str) -> str:
    """Detect MIME type từ extension."""
    ext = Path(image_path).suffix.lower()
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif",
    }.get(ext, "image/jpeg")


def call_claude_vision(
    image_path: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
    prompt: str = VISION_PROMPT,
    max_tokens: int = 1024,
    timeout: int = 60,
) -> dict:
    """Gọi Claude Vision API phân tích 1 ảnh.

    Returns: dict (JSON parsed) hoặc {"error": "..."} nếu lỗi.
    """
    if not Path(image_path).exists():
        return {"error": f"IMAGE_NOT_FOUND: {image_path}"}

    try:
        img_b64 = _encode_image_b64(image_path)
        media_type = _detect_media_type(image_path)
    except Exception as e:
        return {"error": f"ENCODE_FAIL: {e}"}

    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": img_b64,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    }).encode("utf-8")

    req = urllib.request.Request(
        ANTHROPIC_URL,
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {e.code}: {err_body[:300]}"}
    except urllib.error.URLError as e:
        return {"error": f"NETWORK: {e}"}
    except Exception as e:
        return {"error": f"UNKNOWN: {e}"}

    # Parse response
    content = data.get("content", [])
    if not content:
        return {"error": "EMPTY_RESPONSE"}
    text = ""
    for c in content:
        if c.get("type") == "text":
            text = c.get("text", "")
            break
    if not text:
        return {"error": "NO_TEXT_IN_RESPONSE"}

    # Strip markdown fence nếu có
    text = text.strip()
    if text.startswith("```"):
        # ```json\n{...}\n```
        text = "\n".join(text.split("\n")[1:-1])

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        return {"error": f"JSON_PARSE: {e}", "raw": text[:300]}


def analyze_thumbnails_for_channel(
    channel_id: str,
    videos: list,
    top_n: int = 10,
    api_key: str = "",
    model: str = DEFAULT_MODEL,
    log_fn: Callable[[str], None] = print,
) -> dict:
    """Phân tích top N thumbnail của 1 channel bằng Claude Vision.

    Args:
        channel_id: ID kênh
        videos: list[VideoInfo] (đã sort theo view_count desc)
        top_n: số thumbnail phân tích
        api_key: Anthropic key (load_config nếu rỗng)

    Returns: dict {video_id: vision_analysis | error}
    """
    if not api_key:
        from .config import load_config
        api_key = load_config().get("anthropic_api_key", "").strip()
    if not api_key:
        log_fn("  ⚠ thumbnail_vision: chưa cài Anthropic API key, skip")
        return {}

    from . import thumbnails as _th

    out = {}
    vids = sorted(videos, key=lambda v: getattr(v, "view_count", 0),
                  reverse=True)[:top_n]
    log_fn(f"  🔍 thumbnail_vision: phân tích {len(vids)} thumbnail "
           f"của {channel_id[:15]}...")

    for i, v in enumerate(vids, 1):
        vid = getattr(v, "video_id", "")
        if not vid:
            continue
        img_path = _th.download_thumbnail(vid, "mqdefault")
        if not img_path:
            out[vid] = {"error": "DOWNLOAD_FAIL"}
            continue
        result = call_claude_vision(img_path, api_key, model=model)
        out[vid] = result
        if "error" in result:
            log_fn(f"    [{i}/{len(vids)}] {vid}: ERR "
                   f"{result['error'][:60]}")
        else:
            score = result.get("click_score", "?")
            subj = result.get("subject", "?")
            log_fn(f"    [{i}/{len(vids)}] {vid}: score={score}/10 "
                   f"({subj})")

    return out


def aggregate_channel_vision(vision_results: dict) -> dict:
    """Aggregate vision results cho 1 channel → summary metrics.

    Args:
        vision_results: dict {video_id: vision_dict}

    Returns: dict summary {avg_click_score, n_with_face, n_with_text,
        top_emotion, color_scheme_dominant, common_strengths,
        common_weaknesses, improvement_summary}
    """
    from collections import Counter
    valid = [r for r in vision_results.values()
             if isinstance(r, dict) and "error" not in r]
    if not valid:
        return {"n": 0, "error": "NO_VALID_RESULTS"}

    scores = [r.get("click_score", 0) for r in valid
              if isinstance(r.get("click_score"), (int, float))]
    avg_score = sum(scores) / len(scores) if scores else 0

    n_with_face = sum(1 for r in valid if r.get("face_count", 0) > 0)
    n_with_text = sum(1 for r in valid
                      if r.get("text_overlay", {}).get("present"))

    emotions = Counter(r.get("emotion", "none") for r in valid)
    schemes = Counter(r.get("color_scheme", "none") for r in valid)
    subjects = Counter(r.get("subject", "other") for r in valid)

    all_strengths = []
    all_weaknesses = []
    all_improvements = []
    for r in valid:
        all_strengths.extend(r.get("strengths", []) or [])
        all_weaknesses.extend(r.get("weaknesses", []) or [])
        imp = r.get("improvement", "")
        if imp:
            all_improvements.append(imp)

    return {
        "n": len(valid),
        "n_with_error": len(vision_results) - len(valid),
        "avg_click_score": round(avg_score, 1),
        "max_click_score": max(scores) if scores else 0,
        "min_click_score": min(scores) if scores else 0,
        "n_with_face": n_with_face,
        "pct_with_face": round(100 * n_with_face / len(valid), 0),
        "n_with_text": n_with_text,
        "pct_with_text": round(100 * n_with_text / len(valid), 0),
        "top_emotion": emotions.most_common(1)[0][0] if emotions else "?",
        "top_subject": subjects.most_common(1)[0][0] if subjects else "?",
        "top_color_scheme": (schemes.most_common(1)[0][0]
                             if schemes else "?"),
        "common_strengths": [s for s, _ in
                             Counter(all_strengths).most_common(5)],
        "common_weaknesses": [s for s, _ in
                              Counter(all_weaknesses).most_common(5)],
        "sample_improvements": all_improvements[:5],
    }
