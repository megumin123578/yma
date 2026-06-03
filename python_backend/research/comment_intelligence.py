# -*- coding: utf-8 -*-
"""Comment Intelligence — extract pain points, requests, sentiment.

Lớp insight phía trên `comment_miner.py` (đã có data raw). Dùng Claude
API extract:
- Pain points: vấn đề/khó chịu của audience
- Requests: "video tiếp theo nên làm về X"
- Praise patterns: cái gì khán giả thích nhất
- Sentiment shift: timeline thay đổi sentiment (rủi ro hate cmt tăng?)

USAGE:
    from .comment_intelligence import analyze_channel_comments
    result = analyze_channel_comments(channel_id, top_n_videos=20)

Cost: ~$0.02 / channel (group comments → 1 Claude call). 25 WL × ~10
channel = 250 call × $0.02 = $5/kỳ. Hơi tốn.
Tối ưu: chỉ chạy 1-2 lần/tuần thay vì daily.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Callable, Optional

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-4-5"

ANALYSIS_PROMPT = """Bạn là chuyên gia phân tích cộng đồng YouTube. Phân tích {n} comment dưới đây của kênh {channel_title} (chủ đề: {topic}).

Trả về JSON (KHÔNG markdown):
{{
  "pain_points": [
    {{"theme": "<chủ đề>", "n_mentions": <int>, "example_quotes": ["<comment 1>", "<comment 2>"]}}
  ],
  "video_requests": [
    {{"topic": "<yêu cầu nội dung>", "n_mentions": <int>, "example": "<comment>"}}
  ],
  "praise_themes": [
    {{"theme": "<điều khán giả thích>", "n_mentions": <int>, "example": "<comment>"}}
  ],
  "sentiment_overall": "<very_positive|positive|neutral|mixed|negative>",
  "sentiment_pct": {{"positive": <0-100>, "neutral": <0-100>, "negative": <0-100>}},
  "audience_demographic_hint": "<giả định về tuổi/giới tính/quốc tịch dựa trên ngôn ngữ + chủ đề>",
  "red_flags": ["<rủi ro 1>", "<rủi ro 2>"],
  "video_ideas": [
    "<Ý tưởng video 1 dựa trên audience demand>",
    "<Ý tưởng video 2>",
    "<Ý tưởng video 3>"
  ]
}}

Comments (mỗi dòng 1 comment):
{comments_text}

Lưu ý:
- Lọc bỏ spam/emoji thuần
- Pain points + requests RANK theo n_mentions giảm dần, lấy top 5
- video_ideas phải CỤ THỂ (có thể làm thumbnail + tiêu đề được), không chung chung
- red_flags: nếu thấy hate/criticism patterns, drama, hoặc dấu hiệu audience rời bỏ"""


def call_claude_text(prompt: str, api_key: str,
                     model: str = DEFAULT_MODEL,
                     max_tokens: int = 2048,
                     timeout: int = 60) -> str:
    """Gọi Claude API text-only. Trả string text response."""
    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        ANTHROPIC_URL, data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return json.dumps({"error": f"HTTP {e.code}",
                           "detail": e.read().decode("utf-8",
                                                     errors="replace")[:200]})
    except Exception as e:
        return json.dumps({"error": f"NETWORK: {e}"})

    content = data.get("content", [])
    if not content:
        return json.dumps({"error": "EMPTY_RESPONSE"})
    for c in content:
        if c.get("type") == "text":
            return c.get("text", "")
    return ""


def _parse_json_response(text: str) -> dict:
    """Parse JSON từ Claude response, strip markdown fence."""
    text = text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:-1])
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        return {"error": f"JSON_PARSE: {e}", "raw": text[:300]}


def analyze_channel_comments(
    channel_id: str,
    channel_title: str = "",
    topic: str = "",
    max_comments_for_analysis: int = 200,
    api_key: str = "",
    model: str = DEFAULT_MODEL,
    log_fn: Callable[[str], None] = print,
) -> dict:
    """Phân tích comment của 1 channel bằng Claude.

    Args:
        channel_id: ID kênh
        channel_title: tên (đưa vào prompt)
        topic: chủ đề/ngách (đưa vào prompt — vd "DIY tractor")
        max_comments_for_analysis: số comment tối đa send Claude
            (cắt do giới hạn context)

    Returns: dict {pain_points, video_requests, praise_themes,
        sentiment_overall, sentiment_pct, audience_demographic_hint,
        red_flags, video_ideas} hoặc {"error": "..."}
    """
    if not api_key:
        from .config import load_config
        api_key = load_config().get("anthropic_api_key", "").strip()
    if not api_key:
        return {"error": "Chưa cài Anthropic API key"}

    # Load comments từ comment_miner DB
    try:
        from .comment_miner import analyze_comments
        data = analyze_comments(channel_id)
    except Exception as e:
        return {"error": f"comment_miner err: {e}"}

    comments = data.get("samples") or data.get("comments") or []
    if not comments:
        return {"error": "Không có comment nào trong DB"}

    log_fn(f"  💬 comment_intel: {channel_title or channel_id[:15]} — "
           f"{len(comments)} comments, gửi {max_comments_for_analysis} "
           f"cho Claude")

    # Lấy text + filter
    samples = []
    seen = set()
    for c in comments[:max_comments_for_analysis * 3]:  # buffer
        if isinstance(c, dict):
            text = (c.get("text") or "").strip()
        else:
            text = str(c).strip()
        if not text or len(text) < 3:
            continue
        # Dedupe + skip emoji-only
        if text in seen:
            continue
        seen.add(text)
        clean = "".join(ch for ch in text if ord(ch) < 128
                        or ord(ch) > 0xFF)  # giữ lại unicode chữ
        if len(clean.strip()) < 3:
            continue
        samples.append(text[:200])  # cap mỗi cmt 200 char
        if len(samples) >= max_comments_for_analysis:
            break

    if len(samples) < 10:
        return {"error": f"Chỉ có {len(samples)} cmt sau filter, không "
                f"đủ để phân tích"}

    prompt = ANALYSIS_PROMPT.format(
        n=len(samples),
        channel_title=channel_title or "(không rõ)",
        topic=topic or "(không rõ)",
        comments_text="\n".join(f"- {c}" for c in samples),
    )

    text_response = call_claude_text(prompt, api_key, model=model,
                                     max_tokens=2048)
    result = _parse_json_response(text_response)
    if "error" in result:
        log_fn(f"    ❌ Claude err: {result.get('error', '')[:100]}")
        return result

    result["_n_comments_analyzed"] = len(samples)
    result["_channel_id"] = channel_id
    return result
