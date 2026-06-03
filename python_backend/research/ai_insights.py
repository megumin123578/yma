"""
AI Insights — phân tích pattern dùng Claude API.
Không dùng SDK để tránh thêm dependency: gọi HTTP trực tiếp.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Optional


ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5"  # rẻ và nhanh; user có thể đổi sau


# ============================================================
# FRAMEWORK SEO CHUẨN (21/05/2026) — inject vào prompt AI để
# phần mềm sinh báo cáo chất lượng cao như Claude Opus thủ công.
# Trích từ "Chuyên môn SEO Cơ bản đến Nâng cao A-Z" — Funtime Media.
# ============================================================

_SEO_FRAMEWORK = """
# ========================================================
# FRAMEWORK SEO YOUTUBE 2026 — BẮT BUỘC ÁP DỤNG KHI ĐỀ XUẤT
# ========================================================

## 1. 4 CÔNG THỨC TITLE THẮNG (chọn 1 cho mỗi ý tưởng video)
- **How-to**: "Cách + [làm gì] + [cho ai/khi nào]"
- **List**: "[Số] + [danh từ] + [hứa hẹn]" (vd "10 mẹo X")
- **Versus**: "[A] vs [B]: [câu hỏi quyết định]"
- **Question**: "[Câu hỏi gây tò mò]" (vd "Tại sao 90%...?")
Quy tắc: ≤70 ký tự, keyword chính ở 50 ký tự đầu, có tò mò/lợi
ích/năm 2026, 1-2 emoji.

## 2. 5 CÔNG THỨC HOOK 10 GIÂY ĐẦU (cho mỗi ý tưởng)
- **Result First**: show kết quả CUỐI trước, rồi process
- **Problem Punch**: nêu pain point mạnh
- **Bold Promise**: hứa benefit lớn + thời gian cụ thể
- **Curiosity Gap**: nêu fact gây tò mò không trả lời ngay
- **Story Hook**: bắt đầu bằng câu chuyện cá nhân có conflict
Hook 10s đầu quyết định 80% retention.

## 3. 5 LAYOUT THUMBNAIL (gợi ý cho mỗi video)
- **Face + Text** (75/25): tutorial, vlog, reaction
- **Object + Face** (50/50): review, unboxing
- **Before/After** (split): transformation, comparison
- **Versus** (A vs B + chữ VS to giữa): comparison
- **Number + Object** (số to + đồ vật): list video
Anatomy: Face 30-50% + Object 20-40% + Text 2-5 từ + Color contrast cao.

## 4. 8 KỸ THUẬT TĂNG RETENTION
Hook 10s mạnh / Pattern Interrupt mỗi 1-2 phút / Open Loops
(tiết lộ cuối) / Curiosity Gap / Numbered Lists / Visual Variety /
Stake Escalation / Strong CTA cuối → kéo session sang video tiếp.

## 5. 7 KPI CỐT LÕI + MỐC TỐT
CTR: 5-10% (≥10% xuất sắc) | AVD: ≥4p video 10p | AVP: ≥40% |
Like/View: 3-7% | Comment/1K: 0.5-2 | Session Duration: ≥10p |
Returning Viewers: 20-40%

## 6. BẢNG CHẨN ĐOÁN TRIỆU CHỨNG → SỬA
- CTR <3% → Thumbnail/Title yếu (redesign + face + contrast)
- AVP <30% → Hook yếu / clickbait (sửa hook 10s, title-thumb match)
- Retention drop 50-70% → Mid-video không giữ (boost moment: revelation)
- CTR cao + AVP thấp → Click bait (title/thumb match nội dung)
- CTR thấp + AVP cao → Title/thumb yếu nhưng content tốt (đổi T/T)
- Subs đứng yên 3+ kỳ → Sai pillar (audit 10 video gần)
- Δ Views 7d âm → Có video bị ẩn/xoá (check YouTube Studio)

## 7. SWEET SPOT ĐỘ DÀI THEO NGÁCH (rất quan trọng)
- Toy Unboxing: 8-13 phút (KHÔNG <5p)
- Slime ASMR / Bathtub: 30-60+ phút
- Mini Tractor DIY: 8-25 phút
- Numberblocks/Character Slime: 25-60 phút
- Paper Doll / KPop Glow: 25-60 phút (KHÔNG <20p)
- Horror Stories: 20-180 phút (Compilation 60-180p ăn cực mạnh)
- Car Crush Experiment: 3-15 phút
- Construction Vehicle: 8-25 phút

## 8. ANATOMY 1 SERIES (cấu trúc cố định, tăng retention)
Intro 5-10s (signature) → Hook 10-15s (kết quả + lợi ích) →
3-5 sections core → Recap + CTA → Outro với End Screen (video tiếp +
playlist + subscribe).

## 9. YÊU CẦU OUTPUT KHI ĐỀ XUẤT Ý TƯỞNG VIDEO
Mỗi ý tưởng PHẢI có:
- TITLE NHÁP (theo 1 trong 4 công thức, ≤70 ký tự, có năm 2026)
- HOOK 10s (chọn 1 trong 5 công thức + 1 câu mô tả triển khai)
- ĐỘ DÀI ĐỀ XUẤT (theo sweet spot ngách)
- LÝ DO ĂN (dẫn chứng video cụ thể của đối thủ có view cao)
- (Optional) THUMBNAIL LAYOUT đề xuất

## 10. ĐÁNH GIÁ ĐỐI THỦ — SCORING 9 NHÓM
Branding, Pillar/Series, Thumbnail, Hook, Tần suất, SEO metadata,
Funnel, Cộng đồng, Hiệu suất view+engagement. Cho điểm 0-10 mỗi
nhóm, tổng có trọng số.

# ========================================================
# KẾT FRAMEWORK — Vận dụng khi viết phân tích bên dưới
# ========================================================
"""


def build_prompt(result: dict, previous_ai: str = "",
                 is_self_channel: bool = False) -> str:
    """Xây prompt phân tích 1 kênh — cấu trúc CHUẨN từ 21/05/2026 (giống
    AI Opus thủ công của Claude).

    Cấu trúc 6 mục: HIỆN TRẠNG / ĐIỂM SÁNG / CHẨN ĐOÁN / ĐỐI CHIẾU /
    KHUYẾN NGHỊ / VIỆC LÀM NGAY 7 NGÀY.

    Args:
        result: dict kết quả nghiên cứu (channel + videos + keywords...)
        previous_ai: AI phân tích kỳ trước (nếu có) — để AI nhắc lại
            khuyến nghị chưa được thực hiện.
        is_self_channel: True nếu đây là kênh chính của user (★) —
            prompt sẽ tập trung hành động cho user; False → đối thủ
            (prompt ngắn, tập trung insight cho user học hỏi).
    """
    channel = result.get("channel")
    videos = result.get("videos", [])[:30]
    keywords = result.get("keywords", [])[:15]
    recent_by_kw = result.get("recent_by_keyword", {})

    lines = []
    if is_self_channel:
        lines.append(
            "Bạn là chuyên gia chiến lược YouTube giúp KÊNH CHÍNH của tôi "
            "phát triển. Viết phân tích bằng TIẾNG VIỆT theo đúng cấu "
            "trúc 6 mục dưới đây. Trả lời TRỰC TIẾP, KHÔNG mào đầu. "
            "Mỗi mục có số liệu cụ thể, không chung chung.")
    else:
        lines.append(
            "Bạn là chuyên gia nghiên cứu YouTube. Đây là phân tích "
            "kênh ĐỐI THỦ trong cùng ngách của tôi. Viết NGẮN GỌN 3 mục: "
            "(1) HIỆN TRẠNG số liệu + top 3 video; (2) ĐIỂM ĐÁNG HỌC "
            "format/chủ đề; (3) INSIGHT cho kênh chính của tôi. Viết "
            "bằng TIẾNG VIỆT, trực tiếp, KHÔNG mào đầu.")
    lines.append("")

    # === DỮ LIỆU KÊNH ===
    if channel and getattr(channel, "title", ""):
        lines.append(f"## DỮ LIỆU KÊNH: {channel.title}")
        subs = getattr(channel, "subscriber_count", 0) or 0
        lines.append(f"- Người đăng ký: {subs:,}")
        vcount = getattr(channel, "video_count", 0) or 0
        if vcount:
            lines.append(f"- Tổng video: {vcount:,}")
        desc = getattr(channel, "description", "") or ""
        if desc:
            lines.append(f"- Mô tả: {desc[:200]}")

    # Top 8 video theo view + Latest 8 theo ngày (cho kênh chính, AI cần
    # nhìn cả "đỉnh kênh" lẫn "video mới nhất" để chẩn đoán xu hướng)
    if videos:
        top_v = sorted(videos,
                       key=lambda v: getattr(v, "view_count", 0) or 0,
                       reverse=True)[:8]
        lines.append("")
        lines.append("## TOP 8 VIDEO THEO VIEW:")
        for v in top_v:
            dur = getattr(v, "duration_seconds", 0) or 0
            pub = (getattr(v, "published_at", "") or "")[:10]
            days = getattr(v, "days_old", 0) or 0
            vc = getattr(v, "view_count", 0) or 0
            lines.append(
                f"  - {vc:>10,}v | {pub} ({days:.0f}d) | "
                f"{dur//60}m{dur%60:02d}s | "
                f"\"{getattr(v, 'title', '')[:90]}\"")

        latest = sorted(videos,
                        key=lambda v: getattr(v, "days_old", 9999) or 9999
                        )[:8]
        lines.append("")
        lines.append("## 8 VIDEO MỚI NHẤT:")
        for v in latest:
            dur = getattr(v, "duration_seconds", 0) or 0
            pub = (getattr(v, "published_at", "") or "")[:10]
            days = getattr(v, "days_old", 0) or 0
            vc = getattr(v, "view_count", 0) or 0
            lines.append(
                f"  - {vc:>10,}v | {pub} ({days:.1f}d) | "
                f"{dur//60}m | "
                f"\"{getattr(v, 'title', '')[:90]}\"")

    # Từ khoá kênh
    if keywords:
        lines.append("")
        lines.append("## TOP 15 TỪ KHOÁ KÊNH:")
        for kw in keywords:
            lines.append(f"  - {kw.keyword} (điểm {kw.score:.1f})")

    # Top video MỚI nhiều view nhất theo từ khoá (bối cảnh ngách)
    if recent_by_kw:
        lines.append("")
        lines.append("## TOP VIDEO MỚI NHIỀU VIEW THEO TỪ KHOÁ NGÁCH "
                     "(bối cảnh đối thủ):")
        cnt = 0
        for kw_name, vids in recent_by_kw.items():
            if not vids:
                continue
            sorted_v = sorted(vids,
                              key=lambda v: getattr(v, "view_count", 0) or 0,
                              reverse=True)[:3]
            lines.append(f"\n### {kw_name}")
            for v in sorted_v:
                cnt += 1
                vc = getattr(v, "view_count", 0) or 0
                ct = getattr(v, "channel_title", "")
                dys = getattr(v, "days_old", 0) or 0
                lines.append(
                    f"  - \"{getattr(v, 'title', '')[:80]}\" — {ct} — "
                    f"{vc:,}v ({dys:.0f}d)")
            if cnt > 20:
                break

    # === AI KỲ TRƯỚC (nếu có) - dùng để nhắc lại khuyến nghị chưa làm ===
    if previous_ai and previous_ai.strip():
        lines.append("")
        lines.append("## AI KỲ TRƯỚC (để đối chiếu, NHẮC LẠI khuyến nghị "
                     "kỳ trước nếu kênh chưa thực hiện):")
        prev_short = previous_ai[:2500]
        if len(previous_ai) > 2500:
            prev_short += "\n[...rút gọn...]"
        lines.append(prev_short)

    lines.append("")
    if is_self_channel:
        # === INJECT DATA INSIDE (nếu có) — chính xác hơn scrape public ===
        if channel and getattr(channel, "title", ""):
            inside_block = _build_inside_block(
                channel.title, getattr(channel, "channel_id", ""))
            if inside_block:
                lines.append(inside_block)
            # === INJECT KHO TỪ KHOÁ KEYWORDTOOL (nếu kênh có data) ===
            kw_bank_block = _build_kw_bank_block(
                channel.title, getattr(channel, "channel_id", ""),
                existing_keywords=[getattr(k, "keyword", "")
                                   for k in keywords])
            if kw_bank_block:
                lines.append(kw_bank_block)
            # === INJECT INSIGHT NÂNG CAO (Wave 1-2 cải tiến 23/05) ===
            adv_block = _build_advanced_insights_block(result)
            if adv_block:
                lines.append(adv_block)
        # === INJECT FRAMEWORK SEO — kênh chính cần áp dụng ===
        lines.append(_SEO_FRAMEWORK)
        # === CẤU TRÚC 6 MỤC CHO KÊNH CHÍNH ===
        from datetime import datetime
        today = datetime.now().strftime("%d/%m/%Y")
        lines.append(f"# YÊU CẦU PHÂN TÍCH (kỳ giám sát {today}):")
        lines.append("")
        lines.append("Viết phân tích kênh chính theo đúng 6 mục dưới đây. "
                     "Mỗi mục NGẮN GỌN, GIÀU SỐ LIỆU CỤ THỂ, ngôn từ "
                     "trực tiếp:")
        lines.append("")
        lines.append("## 1. HIỆN TRẠNG")
        lines.append(
            "Tóm tắt số liệu hôm nay bằng câu văn: subs, top 3 video "
            "(view + ngày đăng + độ dài), video mới nhất (view sau "
            "bao nhiêu ngày). Nếu subs hôm nay LỆCH LỚN so với kỳ "
            "trước (vd kỳ trước 21.100, hôm nay 21) → ghi chú \"parse "
            "fail, cần xác minh\".")
        lines.append("")
        lines.append("## 2. ĐIỂM SÁNG / SỰ KIỆN ĐÁNG CHÚ Ý")
        lines.append(
            "Có cụm chủ đề / video mới nào đang ăn view không? Có dấu "
            "hiệu bùng nổ nào không? 1-3 điểm. Nếu KHÔNG có điểm sáng "
            "thì nói thẳng \"không có điểm sáng nào\".")
        lines.append("")
        lines.append("## 3. CHẨN ĐOÁN / CẢNH BÁO")
        lines.append(
            "Vấn đề chính của kênh là gì? NẾU AI kỳ trước đã khuyến "
            "nghị 1 hành động và kênh CHƯA LÀM → NHẮC LẠI rõ \"lần thứ "
            "2/3 nhắc về X\". Đây là phần áp lực thúc đẩy hành động.")
        lines.append("")
        lines.append("## 4. ĐỐI CHIẾU TRỰC TIẾP VỚI ĐỐI THỦ")
        lines.append(
            "Bắt buộc lấy ít nhất 1 đối thủ trong dữ liệu ngách bên "
            "trên + so sánh TRỰC TIẾP: cùng chủ đề/cùng thời điểm, "
            "đối thủ subs X view Y vs kênh chính subs A view B → chênh "
            "bao nhiêu LẦN. Số liệu chứng minh > lời nói. Đặc biệt ưu "
            "tiên đối thủ NHỎ HƠN subs nhưng VIEW LỚN HƠN — đây là "
            "bằng chứng \"vấn đề KHÔNG phải subs, mà là CONTENT\".")
        lines.append("")
        lines.append("## 5. KHUYẾN NGHỊ KỲ NÀY")
        lines.append(
            "3-4 hành động cụ thể, có lý do dựa trên dữ liệu. Nếu kỳ "
            "trước đã có khuyến nghị → ghi rõ \"giữ\" hay \"cập nhật\" "
            "khuyến nghị đó (không lặp y nguyên).")
        lines.append("")
        lines.append("## 6. VIỆC LÀM NGAY (7 NGÀY)")
        lines.append(
            "Danh sách 4-6 video cụ thể sẽ làm trong tuần. MỖI Ý "
            "TƯỞNG PHẢI ĐẦY ĐỦ 5 thông tin sau (theo Framework SEO "
            "mục 9 ở trên):\n"
            "  • TITLE NHÁP — chọn 1 trong 4 công thức (How-to/List/"
            "Versus/Question), ≤70 ký tự, có năm 2026.\n"
            "  • HOOK 10s — chọn 1 trong 5 công thức (Result First/"
            "Problem Punch/Bold Promise/Curiosity Gap/Story) + mô "
            "tả triển khai 1 câu.\n"
            "  • ĐỘ DÀI — theo sweet spot ngách (Framework mục 7).\n"
            "  • LÝ DO ĂN — dẫn 1 video đối thủ cụ thể có view cao.\n"
            "  • (Optional) THUMBNAIL LAYOUT — 1 trong 5 layout.\n"
            "Cuối cùng thêm 1 câu \"KHÔNG đăng X\" (việc nên dừng).")
    else:
        # === CẤU TRÚC NGẮN 3 MỤC CHO ĐỐI THỦ ===
        lines.append("# YÊU CẦU PHÂN TÍCH ĐỐI THỦ:")
        lines.append("")
        lines.append("## 1. HIỆN TRẠNG")
        lines.append(
            "Subs + Top 3 video (view + ngày + độ dài + tiêu đề rút "
            "gọn). Latest 1-2 video mới nhất (view sau bao nhiêu "
            "ngày). NGẮN gọn 5-8 dòng.")
        lines.append("")
        lines.append("## 2. ĐIỂM ĐÁNG HỌC")
        lines.append(
            "Format/chủ đề/độ dài đặc trưng kênh này. Pattern tiêu đề. "
            "Tốc độ đăng. 3-5 dòng.")
        lines.append("")
        lines.append("## 3. INSIGHT CHO KÊNH CHÍNH")
        lines.append(
            "Kênh chính nên HỌC điều gì từ đối thủ này? Nếu đối thủ "
            "NHỎ HƠN nhưng VIEW LỚN HƠN → chỉ rõ \"bằng chứng kênh "
            "chính cũng làm được nếu X\". 3-5 dòng.")

    lines.append("")
    lines.append("Trả lời TRỰC TIẾP nội dung, KHÔNG mào đầu \"Dưới "
                 "đây là phân tích...\"")

    return "\n".join(lines)


# Backend AI mặc định = Claude Code CLI (gói subscription, KHÔNG cần API
# key). K9: khâu báo cáo chỉ dùng Opus.
CLI_MODEL = "opus"


def _cli_config() -> tuple:
    """Cấu hình backend CLI. Trả (enabled, exe_path, cli_model).

    Mặc định luôn bật Claude Code CLI; exe tự dò trong PATH / ~/.local/bin.
    """
    return (True, "", CLI_MODEL)


def cli_available() -> bool:
    """True nếu backend = claude_cli VÀ tìm thấy claude.exe."""
    enabled, exe, _ = _cli_config()
    return bool(enabled and _resolve_claude_exe(exe))


def _resolve_claude_exe(exe_path: str = "") -> str:
    """Tìm claude.exe: config → PATH → ~/.local/bin. Trả "" nếu không có."""
    import os
    import shutil
    if exe_path and os.path.exists(exe_path):
        return exe_path
    found = shutil.which("claude")
    if found:
        return found
    cand = os.path.join(os.path.expanduser("~"), ".local", "bin",
                        "claude.exe")
    return cand if os.path.exists(cand) else ""


def call_claude_cli(prompt: str, model: str = "", exe_path: str = "",
                    timeout: int = 300) -> str:
    """Gọi Claude Code CLI headless (`claude -p`) qua stdin → trả text.

    Dùng gói subscription đã login trên máy (KHÔNG cần API key). Prompt
    đẩy qua stdin nên không vướng giới hạn độ dài dòng lệnh Windows.
    Raise RuntimeError nếu lỗi.
    """
    import subprocess
    exe = _resolve_claude_exe(exe_path)
    if not exe:
        raise RuntimeError("Không tìm thấy claude.exe (cài Claude Code "
                           "hoặc thêm claude.exe vào PATH)")
    args = [exe, "-p", "--output-format", "json"]
    if model:
        args += ["--model", model]
    try:
        proc = subprocess.run(
            args, input=prompt, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Claude CLI timeout sau {timeout}s") from e
    except Exception as e:
        raise RuntimeError(f"Lỗi chạy Claude CLI: {e}") from e
    if proc.returncode != 0:
        raise RuntimeError(f"Claude CLI rc={proc.returncode}: "
                           f"{(proc.stderr or proc.stdout or '')[:400]}")
    try:
        data = json.loads(proc.stdout)
    except Exception as e:
        raise RuntimeError(f"Claude CLI output không phải JSON: "
                           f"{proc.stdout[:300]}") from e
    if data.get("is_error") or data.get("subtype") != "success":
        raise RuntimeError(f"Claude CLI lỗi: {data.get('result', '')[:400]}")
    text = (data.get("result") or "").strip()
    if not text:
        raise RuntimeError("Claude CLI trả về rỗng")
    return text


def call_claude(api_key: str, prompt: str, model: str = MODEL,
                max_tokens: int = 2000) -> str:
    """Gọi Claude → trả về text. Raise RuntimeError nếu lỗi.

    Mặc định gọi Claude Code CLI (gói subscription, KHÔNG cần API key).
    Tham số api_key/model giữ cho tương thích chữ ký cũ; đường HTTP
    Anthropic phía dưới chỉ là fallback (không chạy khi đã có CLI).
    """
    enabled, exe, cli_model = _cli_config()
    if enabled:
        # K9: khâu báo cáo chỉ Opus. cli_model rỗng → để CLI tự chọn
        # mặc định (hiện là Opus). Có giá trị → ép --model đó.
        return call_claude_cli(prompt, model=cli_model, exe_path=exe)

    if not api_key or not api_key.startswith("sk-"):
        raise RuntimeError("API key không hợp lệ (cần bắt đầu bằng sk-)")

    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
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
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body[:500]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e}") from e

    # Anthropic trả về {"content": [{"type": "text", "text": "..."}]}
    content = data.get("content", [])
    if not content:
        raise RuntimeError("API trả về rỗng")
    parts = [c.get("text", "") for c in content if c.get("type") == "text"]
    return "\n".join(parts).strip()


def _build_inside_block(channel_title: str, channel_id: str = "") -> str:
    """Nếu có cache Analytics Inside, trả block text inject vào prompt.
    Rỗng nếu không có cache hoặc không match account_tag."""
    try:
        from .analytics_inside import (is_available, match_account_tag,
            get_channel_inside, get_retention_curves)
        if not is_available():
            return ""
        tag = match_account_tag(channel_title, channel_id)
        if not tag:
            return ""
        ci = get_channel_inside(tag, recent_days=30)
        if not ci.get("has_data"):
            return ""
        lines = []
        lines.append("")
        lines.append("## 📊 DATA INSIDE (YouTube Studio Analytics — 30 ngày)")
        lines.append("Dữ liệu CHÍNH THỨC từ Studio (không phải scrape public). "
                     "Dùng để diagnose chính xác:")
        lines.append(f"- Views 30d: {ci['last_views']:,} | "
                     f"Subs gained {ci['last_subs_gained']} − "
                     f"lost {ci['last_subs_lost']} = "
                     f"NET {ci['last_subs_net']:+}")
        lines.append(f"- AVD TB: {ci['avg_avd_seconds']:.0f}s "
                     f"({ci['avg_avd_seconds']/60:.1f}p) | "
                     f"Thumbnail CTR TB: {ci['avg_thumbnail_ctr']*100:.2f}%")
        ts = ci.get('traffic_sources_recent') or []
        if ts:
            lines.append(f"- Top traffic source: " +
                         ", ".join([f"{t['source']} {t['pct']:.0f}%"
                                    for t in ts[:5]]))
        demo = ci.get('demographics') or []
        if demo:
            lines.append(f"- Top demographic: " +
                         ", ".join([f"{d['gender']} {d['age_group']} "
                                    f"{d['pct']:.0f}%" for d in demo[:3]]))
        dev = ci.get('devices') or {}
        if dev:
            top_dev = sorted(dev.items(), key=lambda x: -x[1])[0]
            lines.append(f"- Device chính: {top_dev[0]} {top_dev[1]:.0f}%")
        countries = ci.get('top_countries') or []
        if countries:
            lines.append(f"- Top 3 quốc gia: " +
                         ", ".join([f"{c['country']} {c['pct']:.0f}%"
                                    for c in countries[:3]]))
        # Retention curves
        retentions = get_retention_curves(tag, top_n=3, min_views=1000)
        if retentions:
            lines.append("")
            lines.append("**Retention curve top 3 video** (drop point quan trọng):")
            for r in retentions:
                drops_str = ""
                if r.get('drop_points'):
                    drops_str = " | DROPS: " + ", ".join(
                        [f"{d['at_pct']:.0f}%: −{d['drop_pct']:.0f}%"
                         for d in r['drop_points'][:3]])
                lines.append(
                    f"  • \"{r['title'][:60]}\" ({r['views']:,}v) — "
                    f"avg retention {r['avg_retention']:.0f}%{drops_str}")
        lines.append("")
        lines.append("**Bài học rút ra để diagnose**:")
        # Heuristic insights
        if ts and ts[0]['source'] == 'YT_SEARCH' and ts[0]['pct'] < 5:
            lines.append("  - YT_SEARCH <5% → keyword/title kênh yếu, "
                         "không ranking trên search. PHẢI cải thiện SEO.")
        if ci['avg_thumbnail_ctr'] < 0.03:
            lines.append(f"  - Thumbnail CTR {ci['avg_thumbnail_ctr']*100:.1f}% "
                         "<3% — thumbnail/title cực yếu, redesign ngay.")
        elif ci['avg_thumbnail_ctr'] > 0.10:
            lines.append(f"  - Thumbnail CTR {ci['avg_thumbnail_ctr']*100:.1f}% "
                         ">10% — XUẤT SẮC, giữ pattern thumbnail.")
        if ci['last_subs_net'] < 0:
            lines.append(f"  - NET subs ÂM ({ci['last_subs_net']:+}) — "
                         "kênh ĐANG MẤT audience. Audit lại pillar.")
        if dev and dev.get('MOBILE', 0) > 90:
            lines.append("  - MOBILE >90% → thumbnail/text phải đọc được ở "
                         "màn nhỏ. KHÔNG chèn nhiều chi tiết.")
        lines.append("")
        return "\n".join(lines)
    except Exception:
        return ""


def _build_kw_bank_block(channel_title: str, channel_id: str = "",
                         existing_keywords: list = None) -> str:
    """Nếu kênh có data trong kho từ khoá keywordtool, trả block text
    inject vào prompt cho AI dùng phân tích SEO. Rỗng nếu không có data.

    Pattern giống `_build_inside_block` — degrade an toàn.
    """
    try:
        from .keyword_bank_analysis import get_channel_kw_bank
        data = get_channel_kw_bank(
            channel_id, channel_title,
            existing_keywords=existing_keywords)
        if not data:
            return ""
        lines = []
        lines.append("")
        lines.append("## 📚 KHO TỪ KHOÁ KEYWORDTOOL "
                     "(volume + cạnh tranh THẬT từ keywordtool.io)")
        status_txt = ("FULL" if data["status"] == "full"
                      else f"PARTIAL "
                           f"{100*data['seeds_done']//data['seeds_total']}%")
        lines.append(
            f"Kho ngách kênh ({status_txt} — {data['seeds_done']}/"
            f"{data['seeds_total']} seed đã thu hoạch): "
            f"**{data['kw_total']:,} từ khoá ngách**, "
            f"**{data['kw_golden']:,} từ 'vàng'** "
            f"(volume cao + cạnh tranh thấp).")
        if data["top_golden"]:
            lines.append("")
            lines.append("**TOP 20 TỪ KHOÁ VÀNG** (cơ hội ăn view cao nhất):")
            for k in data["top_golden"][:20]:
                lines.append(
                    f"- \"{k['keyword'][:60]}\" — vol {k['volume']:,}, "
                    f"cạnh tranh {k['comp']*100:.0f}%")
        if data["niche_clusters"]:
            lines.append("")
            lines.append("**NGÁCH CON** (gom theo cụm từ gốc):")
            for n in data["niche_clusters"][:8]:
                lines.append(
                    f"- **{n['name']}** — {n['kw_count']} từ, vol tổng "
                    f"{n['total_volume']:,}, cạnh tranh TB "
                    f"{n['avg_comp']*100:.0f}%")
        if data["coverage_gap"]:
            lines.append("")
            lines.append("**TỪ KHOÁ VÀNG KÊNH CHƯA TẬN DỤNG** "
                         "(làm video về các từ này sớm để ăn view):")
            for k in data["coverage_gap"][:10]:
                lines.append(
                    f"- \"{k['keyword'][:60]}\" — vol {k['volume']:,}, "
                    f"cạnh tranh {k['comp']*100:.0f}%")
        lines.append("")
        lines.append("**NHIỆM VỤ AI:** trong mục 5 (KHUYẾN NGHỊ) và 6 "
                     "(VIỆC LÀM 7 NGÀY), DÙNG kho từ khoá này để: "
                     "(a) đánh giá bộ từ khoá hiện tại của kênh đã đủ "
                     "tốt chưa (chạm vào từ vàng nào, bỏ sót từ nào); "
                     "(b) gợi ý 1-2 NGÁCH TỪ KHOÁ kênh nên đi tiếp để "
                     "tận dụng cơ hội (volume cao + cạnh tranh thấp). "
                     "Mỗi ý tưởng video (mục 6) NÊN nêu từ khoá vàng "
                     "ngách nào nó target.")
        lines.append("")
        return "\n".join(lines)
    except Exception:
        import traceback
        traceback.print_exc()
        return ""


def analyze(result: dict, api_key: str, model: Optional[str] = None,
            previous_ai: str = "", is_self_channel: bool = False,
            max_tokens: int = 3000) -> str:
    """Phân tích 1 kênh, trả về markdown text.

    Args:
        result: dict result của 1 kênh.
        api_key: Claude API key.
        model: model name (mặc định MODEL).
        previous_ai: AI phân tích kỳ trước (để nhắc lại khuyến nghị
            chưa thực hiện). Truyền "" nếu không có.
        is_self_channel: True nếu là kênh chính của user → prompt 6 mục;
            False → đối thủ → prompt ngắn 3 mục.
        max_tokens: giới hạn token output (kênh chính cần 3000+, đối
            thủ chỉ cần 1500).
    """
    prompt = build_prompt(result, previous_ai=previous_ai,
                          is_self_channel=is_self_channel)
    return call_claude(api_key, prompt,
                       model=model or MODEL,
                       max_tokens=max_tokens)


def build_compare_prompt(results: list) -> str:
    """Xây prompt so sánh nhiều kênh/bộ từ khoá."""
    lines = []
    lines.append("Bạn là chuyên gia chiến lược YouTube. Tôi đang so sánh "
                 f"{len(results)} kênh/bộ từ khoá. Hãy phân tích chiến lược "
                 "TỔNG HỢP bằng TIẾNG VIỆT, súc tích, có cấu trúc.")
    lines.append("")

    for i, r in enumerate(results, 1):
        channel = r.get("channel")
        is_kw_mode = bool(r.get("input_keywords")) or (
            channel and not getattr(channel, "channel_id", "")
        )

        if is_kw_mode:
            lines.append(f"## Mục #{i}: Bộ từ khoá")
            kws_list = r.get("input_keywords", [])
            if not kws_list:
                kws_list = [k.keyword for k in r.get("keywords", [])[:10]]
            lines.append(f"- Từ khoá: {', '.join(kws_list[:10])}")
        else:
            lines.append(f"## Kênh #{i}: {channel.title if channel else '?'}")
            if channel:
                lines.append(f"- Subs: {channel.subscriber_count:,}")
                lines.append(f"- Tổng view kênh: {channel.view_count:,}")
                lines.append(f"- Số video kênh: {channel.video_count}")

        # Top từ khoá đại diện ngách (top 5)
        kws_obj = r.get("keywords", [])[:5]
        if kws_obj:
            lines.append(f"- Top 5 từ khoá: "
                         + ", ".join(k.keyword for k in kws_obj))

        # Top 5 video MỚI nhiều view nhất (kết quả chính)
        all_recent = []
        for vids in r.get("recent_by_keyword", {}).values():
            all_recent.extend(vids)
        unique_v = {v.video_id: v for v in all_recent}
        top_recent = sorted(unique_v.values(),
                            key=lambda v: v.view_count, reverse=True)[:5]
        if top_recent:
            lines.append("- Top 5 video MỚI nhiều view:")
            for v in top_recent:
                lines.append(
                    f"  • \"{v.title[:70]}\" ({v.channel_title}) — "
                    f"{v.view_count:,} views"
                )
        lines.append("")

    lines.append("## Yêu cầu phân tích so sánh:")
    lines.append("")
    lines.append("### 1. Vị thế từng kênh/mục")
    lines.append(
        "So sánh quy mô, chiến lược, điểm mạnh/yếu của từng mục. Ai dẫn đầu? "
        "Ai đang nổi nhanh nhất? Ai có engagement tốt nhất?")
    lines.append("")
    lines.append("### 2. Đối thủ chung (kênh KHÁC xuất hiện nhiều lần)")
    lines.append(
        "Nhìn vào các tên kênh trong top video, có kênh NGOÀI nào xuất hiện "
        "ở nhiều mục? Họ là đối thủ chung của cả ngách. Liệt kê tên + tại sao họ mạnh.")
    lines.append("")
    lines.append("### 3. Khoảng trống chiến lược (Content Gap)")
    lines.append(
        "Có chủ đề/format/sub-niche nào CHƯA mục nào khai thác mạnh? "
        "Đây là cơ hội.")
    lines.append("")
    lines.append("### 4. Top từ khoá overlap (nếu rõ)")
    lines.append(
        "Từ khoá nào xuất hiện ở cả 2+ mục → cạnh tranh trực tiếp ở đó.")
    lines.append("")
    lines.append("### 5. 3 khuyến nghị chiến lược TỔNG HỢP")
    lines.append(
        "Dựa trên so sánh, đưa ra 3 hành động cụ thể nên làm.")
    lines.append("")
    lines.append("Trả lời trực tiếp nội dung, dùng markdown ngắn gọn.")

    return "\n".join(lines)


def analyze_compare(results: list, api_key: str,
                    model: Optional[str] = None) -> str:
    """Phân tích so sánh nhiều results bằng AI. Trả markdown."""
    prompt = build_compare_prompt(results)
    return call_claude(api_key, prompt, model=model or MODEL, max_tokens=2500)


# ============================================================
# Watchlist strategy analysis - tập trung vào kênh của user
# ============================================================

def build_watchlist_strategy_prompt(
    watchlist, channels_data: list,
    previous_channels_data: Optional[list] = None,
    previous_analysis_text: str = "",
) -> str:
    """
    Xây prompt phân tích chiến lược watchlist.
    Lấy KÊNH USER làm trung tâm, đối thủ làm bối cảnh.
    Mục tiêu: User nên làm gì để kênh phát triển.

    channels_data: list dict, mỗi dict gồm:
      - title, channel_id, is_self, subscriber_count, video_count,
        view_count, captured_at
      - top_videos_by_vph: list[dict] (title, views, likes, comments,
        views_per_hour, viral_score, days_old, video_id)
      - avg_views_per_video, median_views, top1_views
      - like_view_ratio, comment_view_ratio
      - videos_per_day, last_upload
      - research_keywords (top 30)
    """
    # Tách kênh user và đối thủ
    user_ch = next((c for c in channels_data if c.get("is_self")), None)
    competitors = [c for c in channels_data if not c.get("is_self")]
    competitors.sort(key=lambda c: c.get("subscriber_count", 0), reverse=True)

    # Mode: initial (không có lần trước) vs delta (có lần trước)
    is_delta = bool(previous_channels_data and previous_analysis_text)

    # Quy tắc ngôn ngữ — bắt buộc thuần Việt
    lang_rule = (
        "QUY TẮC NGÔN NGỮ (BẮT BUỘC): Viết HOÀN TOÀN bằng tiếng Việt. "
        "KHÔNG dùng từ tiếng Anh cho thuật ngữ. Cụ thể: "
        "'velocity surge' → 'tăng tốc đột biến'; "
        "'early viral' → 'chớm viral'; 'subs/subscribers' → 'người đăng "
        "ký'; 'views' → 'lượt xem'; 'engagement' → 'mức tương tác'; "
        "'like' → 'lượt thích'; 'comment' → 'bình luận'; "
        "'channel' → 'kênh'; 'TL;DR' → 'Tóm tắt nhanh'; "
        "'KPI' → 'Chỉ số mục tiêu'; 'algorithm' → 'thuật toán'; "
        "'content gap' → 'khoảng trống nội dung'; "
        "'thumbnail' → 'ảnh thu nhỏ'. "
        "CHỈ giữ nguyên gốc: tên kênh, tiêu đề video, từ khoá, thẻ tag "
        "(các nội dung gốc của kênh). Được giữ 'viral', 'YouTube', "
        "'SEO' vì đã phổ biến."
    )

    lines = []
    if is_delta:
        lines.append(
            "Bạn là chuyên gia chiến lược YouTube. Đây là lần phân tích "
            "TIẾP THEO của danh sách theo dõi. Lần trước đã có 1 báo cáo "
            "đầy đủ. Lần này hãy viết BÁO CÁO CẬP NHẬT — CHỈ TẬP TRUNG "
            "VÀO THAY ĐỔI MỚI so với lần trước. KHÔNG lặp lại phân tích "
            "đã có. Báo cáo súc tích, tập trung kênh của tôi (★)."
        )
    else:
        lines.append(
            "Bạn là chuyên gia chiến lược YouTube giúp nhà sáng tạo phát "
            "triển kênh. Đây là lần phân tích ĐẦU TIÊN của danh sách "
            "theo dõi. Viết BÁO CÁO CHIẾN LƯỢC đầy đủ, tập trung kênh "
            "của tôi (★). Mục tiêu: tôi cần biết phải làm gì để kênh "
            "PHÁT TRIỂN."
        )
    lines.append("")
    lines.append(lang_rule)
    lines.append("")
    lines.append(f"# Watchlist: {watchlist.name}")
    if watchlist.description:
        lines.append(f"Mô tả: {watchlist.description}")
    lines.append("")

    # Kênh user
    if user_ch:
        lines.append(f"## ★ KÊNH USER: {user_ch['title']}")
        lines.append(
            f"- Subs: {user_ch.get('subscriber_count', 0):,}")
        lines.append(
            f"- Video kênh đã đo: {len(user_ch.get('top_videos_by_vph', []))}")
        if user_ch.get("avg_views_per_video"):
            lines.append(
                f"- Trung bình views/video: "
                f"{user_ch['avg_views_per_video']:,}")
        if user_ch.get("top1_views"):
            lines.append(
                f"- Top 1 video views: {user_ch['top1_views']:,}")
        if user_ch.get("like_view_ratio"):
            lines.append(
                f"- Tỷ lệ Like/View: {user_ch['like_view_ratio']:.2f}%")
        if user_ch.get("comment_view_ratio"):
            lines.append(
                f"- Tỷ lệ Comment/View: {user_ch['comment_view_ratio']:.3f}%")
        if user_ch.get("videos_per_day"):
            lines.append(
                f"- Tần suất upload: {user_ch['videos_per_day']:.2f} "
                "video/ngày")
        if user_ch.get("research_keywords"):
            lines.append(
                f"- Top từ khoá kênh: "
                f"{', '.join(user_ch['research_keywords'][:15])}")
        lines.append("")
        lines.append("### Top video của user (theo views/giờ hiện tại):")
        for i, v in enumerate(user_ch.get("top_videos_by_vph", [])[:10], 1):
            lines.append(
                f"  {i}. {v['view_count']:,}v • "
                f"{v.get('views_per_hour', 0):.0f}v/h • "
                f"score {v.get('viral_score', 0):.1f}× — "
                f"\"{v['title'][:70]}\"")
        lines.append("")
    else:
        lines.append("## ⚠ KHÔNG CÓ KÊNH USER trong watchlist")
        lines.append(
            "User chưa đánh dấu kênh nào là 'kênh của tôi'. "
            "Đề xuất user mark 1 kênh.")
        lines.append("")

    # Đối thủ
    lines.append(f"## ĐỐI THỦ ({len(competitors)} kênh)")
    for i, c in enumerate(competitors, 1):
        lines.append("")
        lines.append(f"### {i}. {c['title']}")
        lines.append(f"  - Subs: {c.get('subscriber_count', 0):,}")
        if c.get("avg_views_per_video"):
            lines.append(
                f"  - Trung bình views/video: "
                f"{c['avg_views_per_video']:,}")
        if c.get("top1_views"):
            lines.append(
                f"  - Top 1 video views: {c['top1_views']:,}")
        if c.get("like_view_ratio"):
            lines.append(
                f"  - Like/View: {c['like_view_ratio']:.2f}%")
        if c.get("comment_view_ratio"):
            lines.append(
                f"  - Comment/View: {c['comment_view_ratio']:.3f}%")
        if c.get("videos_per_day"):
            lines.append(
                f"  - Tần suất: {c['videos_per_day']:.2f} video/ngày")
        if c.get("research_keywords"):
            lines.append(
                f"  - Từ khoá: "
                f"{', '.join(c['research_keywords'][:10])}")
        # Top 5 video viral
        lines.append("  - Top 5 video đang viral:")
        for v in c.get("top_videos_by_vph", [])[:5]:
            lines.append(
                f"    • {v['view_count']:,}v • "
                f"{v.get('views_per_hour', 0):.0f}v/h • "
                f"score {v.get('viral_score', 0):.1f}× — "
                f"\"{v['title'][:70]}\"")

    # === Nếu mode DELTA: thêm previous data + previous analysis ===
    if is_delta:
        lines.append("")
        lines.append("# ==============================================")
        lines.append("# DATA LẦN TRƯỚC (để so sánh)")
        lines.append("# ==============================================")
        # Map cid → prev data
        prev_map = {p["channel_id"]: p for p in previous_channels_data}
        lines.append("")
        lines.append("## Số liệu kênh lần trước:")
        prev_user = prev_map.get(user_ch["channel_id"] if user_ch else "")
        if prev_user:
            lines.append(
                f"- ★ {prev_user.get('title', '')}: "
                f"{prev_user.get('subscriber_count', 0):,} subs, "
                f"avg view {prev_user.get('avg_views_per_video', 0):,}, "
                f"L/V {prev_user.get('like_view_ratio', 0):.2f}%, "
                f"top {prev_user.get('top1_views', 0):,} views")
        for c in competitors:
            pc = prev_map.get(c["channel_id"])
            if pc:
                lines.append(
                    f"- {pc.get('title', '')}: "
                    f"{pc.get('subscriber_count', 0):,} subs, "
                    f"avg {pc.get('avg_views_per_video', 0):,}, "
                    f"L/V {pc.get('like_view_ratio', 0):.2f}%, "
                    f"top {pc.get('top1_views', 0):,}")

        lines.append("")
        lines.append("## Báo cáo lần trước (TÓM TẮT — không lặp lại):")
        # Truncate previous analysis to save tokens
        prev_short = previous_analysis_text[:3000]
        if len(previous_analysis_text) > 3000:
            prev_short += "\n\n[...báo cáo lần trước đã rút gọn...]"
        lines.append(prev_short)
        lines.append("")

    lines.append("")
    lines.append("# YÊU CẦU BÁO CÁO (markdown, TIẾNG VIỆT, súc tích, có số)")
    lines.append("")

    if is_delta:
        # === INJECT FRAMEWORK SEO cho strategy delta ===
        lines.append(_SEO_FRAMEWORK)
        lines.append("ĐÂY LÀ BÁO CÁO CẬP NHẬT (delta). Cấu trúc 5 phần:")
        lines.append("")
        lines.append("## 1. TÓM TẮT THAY ĐỔI — 3 điều mới quan trọng nhất")
        lines.append(
            "So với lần trước, 3 thay đổi đáng chú ý nhất là gì? "
            "Có thể là: subs delta, video viral mới, đối thủ mới lên, "
            "engagement tăng/giảm... Mỗi điều 1-2 câu, có số cụ thể.")
        lines.append("")
        lines.append("## 2. CẬP NHẬT KÊNH USER (★)")
        lines.append(
            "Số liệu user thay đổi thế nào kể từ lần trước? "
            "Có viral mới không? Có cải thiện hay xấu đi điểm gì? "
            "Theo dõi tiến độ các action item từ báo cáo cũ.")
        lines.append("")
        lines.append("## 3. CẬP NHẬT ĐỐI THỦ")
        lines.append(
            "Đối thủ nào có thay đổi đáng kể (subs spike, viral mới, "
            "video drop off)? Ai đang nguy hiểm hơn? Ai đang nguội đi?")
        lines.append("")
        lines.append("## 4. ACTION MỚI cần làm trong tuần tới")
        lines.append(
            "Dựa trên thay đổi, 3-5 action cụ thể nên làm tuần này, "
            "khác với action đã đề xuất lần trước. Nếu có ý tưởng "
            "video MỚI → áp dụng Framework SEO mục 9 (TITLE + HOOK + "
            "ĐỘ DÀI + LÝ DO ĂN + THUMBNAIL).")
        lines.append("")
        lines.append("## 5. RỦI RO MỚI hoặc cảnh báo cập nhật")
        lines.append(
            "Vấn đề mới phát hiện hoặc rủi ro cũ đã được xử lý chưa?")
        lines.append("")
        lines.append(
            "QUAN TRỌNG: KHÔNG lặp lại phần phân tích lớn từ báo cáo cũ. "
            "User có thể xem lại báo cáo cũ khi cần. "
            "Chỉ tập trung vào THAY ĐỔI MỚI.")
    else:
        # === INJECT FRAMEWORK SEO cho strategy WL ===
        lines.append(_SEO_FRAMEWORK)
        lines.append("ĐÂY LÀ BÁO CÁO ĐẦU TIÊN. Cấu trúc 9 phần:")
        lines.append("")
        lines.append("## 1. TL;DR — 3 việc QUAN TRỌNG NHẤT cần làm ngay")
        lines.append("Liệt kê 3 hành động ưu tiên cao nhất user nên làm "
                     "trong tuần này, có lý do bằng số liệu cụ thể.")
        lines.append("")
        lines.append("## 2. Vị thế hiện tại của kênh user trong watchlist")
        lines.append(
            "Xếp hạng tương đối, điểm mạnh độc đáo, điểm yếu. "
            "Tốc độ tăng trưởng so với đối thủ.")
        lines.append("")
        lines.append("## 3. Phân tích đối thủ")
        lines.append(
            "- Ai là đối thủ nguy hiểm nhất? Tại sao?\n"
            "- Ai có thể vượt qua trong 90 ngày?\n"
            "- Đối thủ nhỏ nào đang lên nhanh, cần theo dõi sát?\n"
            "- Đối thủ nào đang nguội, không cần lo?")
        lines.append("")
        lines.append("## 4. Khoảng trống nội dung — cơ hội lớn cho kênh user")
        lines.append(
            "Theme/format nào đối thủ ăn nhiều mà kênh user CHƯA làm? "
            "Liệt kê 3-5 cơ hội rõ nhất kèm best view của đối thủ.")
        lines.append("")
        lines.append("## 5. Ý TƯỞNG VIDEO CỤ THỂ NÊN LÀM NGAY")
        lines.append(
            "Đề xuất 5-8 ý tưởng video cụ thể cho kênh user. MỖI Ý "
            "TƯỞNG PHẢI ĐẦY ĐỦ 5 thông tin theo Framework SEO mục 9:\n"
            "  • TITLE NHÁP — chọn 1 trong 4 công thức (How-to/List/"
            "Versus/Question), ≤70 ký tự, có năm 2026.\n"
            "  • HOOK 10s — chọn 1 trong 5 công thức (Result First/"
            "Problem Punch/Bold Promise/Curiosity Gap/Story) + 1 câu "
            "mô tả triển khai.\n"
            "  • ĐỘ DÀI — theo sweet spot ngách (Framework mục 7).\n"
            "  • LÝ DO ĂN — dẫn 1 video đối thủ cụ thể có view cao.\n"
            "  • (Optional) THUMBNAIL LAYOUT — 1 trong 5 layout.\n"
            "Ưu tiên ý tưởng bám video đột biến + khoảng trống nội "
            "dung ở mục 3-4 trên.")
        lines.append("")
        lines.append("## 6. Điểm mạnh độc nhất của user cần củng cố")
        lines.append(
            "Theme/format gì kênh user đang LÀM tốt mà đối thủ chưa làm "
            "hoặc làm kém? Đề xuất cách scale up.")
        lines.append("")
        lines.append("## 7. Lộ trình hành động 30 ngày")
        lines.append(
            "Chia theo tuần, mỗi tuần 2-3 hành động cụ thể.")
        lines.append("")
        lines.append("## 8. KPI cần theo dõi hàng tuần")
        lines.append(
            "Bảng các chỉ số: hiện tại → mục tiêu 30 ngày → 90 ngày.")
        lines.append("")
        lines.append("## 9. Rủi ro + Cảnh báo")
        lines.append("Vấn đề nghiêm trọng cần xử lý ngay.")

    # PER-NGÁCH GUIDANCE: detect niche từ keyword + video titles, inject
    # hướng dẫn cụ thể (vd Toy Unboxing thì sweet spot 8-13 phút, không
    # phải 3-5 phút). Giúp AI đề xuất ý tưởng video phù hợp ngách.
    try:
        from .niche_detector import _NICHE_PATTERNS, get_niche_guidance
        text_pool = []
        for c in channels_data:
            text_pool.extend(c.get("research_keywords", []) or [])
            for v in (c.get("top_videos_by_vph") or []):
                t = v.get("title", "") if isinstance(v, dict) else ""
                if t:
                    text_pool.append(t)
        full_text = " ".join((t or "").lower() for t in text_pool)
        if full_text:
            scores = {n: sum(full_text.count(p) for p in patts)
                      for n, patts in _NICHE_PATTERNS.items()}
            best = max(scores, key=scores.get) if scores else "generic"
            if scores.get(best, 0) >= 3:
                guidance = get_niche_guidance(best)
                if guidance:
                    lines.append("")
                    lines.append(guidance)
                    lines.append("")
                    lines.append(
                        f"[Niche detected: {best}. Bám theo guidance trên "
                        f"khi đề xuất ý tưởng video.]")
    except Exception as e:
        pass  # Niche detect không bắt buộc, skip nếu lỗi

    lines.append("")
    lines.append("Trả lời TRỰC TIẾP nội dung báo cáo, không cần mào đầu.")
    return "\n".join(lines)


def analyze_watchlist_strategy(
    watchlist, channels_data: list, api_key: str,
    model: Optional[str] = None,
    previous_channels_data: Optional[list] = None,
    previous_analysis_text: str = "",
) -> str:
    """Phân tích chiến lược watchlist bằng AI. Trả markdown.

    Nếu có previous_channels_data + previous_analysis_text → AI sẽ tập trung
    vào THAY ĐỔI MỚI thay vì lặp lại phân tích cũ (delta mode).
    """
    prompt = build_watchlist_strategy_prompt(
        watchlist, channels_data,
        previous_channels_data=previous_channels_data,
        previous_analysis_text=previous_analysis_text,
    )
    return call_claude(api_key, prompt,
                       model=model or MODEL, max_tokens=4000)


# ============================================================
# Báo cáo SEO thực chiến — cấu trúc theo quy trình 9 bước
# (1.1→3.3), bám dữ liệu watchlist, mỗi bước có việc làm cụ thể.
# ============================================================

_SEO_LANG_RULE = (
    "QUY TẮC NGÔN NGỮ (BẮT BUỘC): Viết HOÀN TOÀN bằng tiếng Việt, giọng "
    "rõ ràng, dễ hiểu, thực chiến. Hạn chế thuật ngữ; nếu buộc dùng "
    "(CTR, retention, AVD, pillar...) thì mở ngoặc giải thích 1 câu ngắn. "
    "Giữ nguyên gốc: tên kênh, tiêu đề video, từ khoá."
)


def build_seo_report_prompt(watchlist, channels_data: list) -> str:
    """Prompt báo cáo SEO thực chiến — 9 bước theo quy trình chuẩn.

    Mỗi bước có 3 phần: (a) Hiện trạng bám số liệu thật; (b) Vì sao quan
    trọng (1 câu ngắn); (c) Việc làm ngay (gạch đầu dòng cụ thể).
    """
    user_ch = next((c for c in channels_data if c.get("is_self")), None)
    competitors = [c for c in channels_data if not c.get("is_self")]
    competitors.sort(key=lambda c: c.get("subscriber_count", 0), reverse=True)

    lines = []
    lines.append(
        "Bạn là CHUYÊN GIA SEO YouTube, viết BÁO CÁO SEO thực chiến cho "
        "kênh. Mục tiêu: đọc xong BIẾT CHÍNH XÁC PHẢI LÀM GÌ để kênh SEO "
        "tốt lên — cụ thể, làm theo được ngay, không nói chung chung.")
    lines.append("")
    lines.append(_SEO_LANG_RULE)
    lines.append("")
    lines.append(f"# DỮ LIỆU WATCHLIST: {watchlist.name}")
    if getattr(watchlist, "description", ""):
        lines.append(f"Mô tả: {watchlist.description}")
    lines.append("")

    if user_ch:
        lines.append(f"## ★ KÊNH CỦA BẠN: {user_ch['title']}")
        lines.append(f"- Người đăng ký: {user_ch.get('subscriber_count', 0):,}")
        if user_ch.get("avg_views_per_video"):
            lines.append(f"- Trung bình lượt xem/video: "
                         f"{user_ch['avg_views_per_video']:,}")
        if user_ch.get("top1_views"):
            lines.append(f"- Video cao nhất: {user_ch['top1_views']:,} lượt xem")
        if user_ch.get("like_view_ratio"):
            lines.append(f"- Tỷ lệ thích/xem: {user_ch['like_view_ratio']:.2f}%")
        if user_ch.get("videos_per_day"):
            lines.append(f"- Tần suất đăng: {user_ch['videos_per_day']:.2f} "
                         "video/ngày")
        if user_ch.get("research_keywords"):
            lines.append(f"- Từ khoá kênh: "
                         f"{', '.join(user_ch['research_keywords'][:15])}")
        lines.append("### Top video của bạn:")
        for i, v in enumerate(user_ch.get("top_videos_by_vph", [])[:8], 1):
            lines.append(f"  {i}. {v['view_count']:,} lượt xem — "
                         f"\"{v['title'][:70]}\"")
        lines.append("")
    else:
        lines.append("## ⚠ Watchlist chưa đánh dấu KÊNH CỦA BẠN (kênh chính). "
                     "Hãy nhắc người dùng đánh dấu 1 kênh là 'kênh của tôi'.")
        lines.append("")

    lines.append(f"## ĐỐI THỦ ({len(competitors)} kênh):")
    for i, c in enumerate(competitors[:8], 1):
        lines.append(f"### {i}. {c['title']} — {c.get('subscriber_count', 0):,} "
                     "người đăng ký")
        if c.get("avg_views_per_video"):
            lines.append(f"  - TB lượt xem/video: {c['avg_views_per_video']:,}")
        if c.get("research_keywords"):
            lines.append(f"  - Từ khoá: {', '.join(c['research_keywords'][:8])}")
        for v in c.get("top_videos_by_vph", [])[:3]:
            lines.append(f"  - Video hot: {v['view_count']:,} lượt xem — "
                         f"\"{v['title'][:70]}\"")
    lines.append("")

    lines.append(_SEO_FRAMEWORK)

    lines.append("# YÊU CẦU: viết BÁO CÁO SEO theo ĐÚNG 9 BƯỚC dưới đây. "
                 "MỖI BƯỚC gồm 3 phần ghi rõ:")
    lines.append("- **(a) Hiện trạng** — 1-3 câu bám số liệu thật ở trên. "
                 "Nếu thiếu dữ liệu thì ghi \"chưa có dữ liệu — cần thu thập "
                 "thêm\".")
    lines.append("- **(b) Vì sao quan trọng** — 1 câu ngắn, dễ hiểu.")
    lines.append("- **(c) Việc làm ngay** — 2-4 gạch đầu dòng CỰC CỤ THỂ, "
                 "làm theo được ngay (ví dụ mẫu title/hook nếu hợp).")
    lines.append("")
    steps = [
        ("1.1 — Phân tích thị trường & đối thủ",
         "Ngách chính, đối thủ mạnh/yếu, khoảng trống cơ hội kênh bạn nên chiếm."),
        ("1.2 — Phân tích từ khoá",
         "Từ khoá nên nhắm (ý định tìm kiếm rõ, đủ lượt tìm, ít cạnh tranh)."),
        ("1.3 — Phân tích xu hướng",
         "Chủ đề/format đang lên trong ngách; nên bắt trend nào, tránh gì."),
        ("2.1 — Xây dựng thương hiệu kênh",
         "Tên/handle, avatar/banner, mô tả kênh chứa từ khoá, tông giọng."),
        ("2.2 — Cấu trúc nội dung kênh",
         "Trụ cột nội dung (pillar), series, playlist theo ý định người xem."),
        ("2.3 — On-Video SEO",
         "Tiêu đề ≤70 ký tự có từ khoá, mô tả 2-3 dòng đầu, hashtag/tag, "
         "timestamp, thumbnail, hook 10s."),
        ("3.1 — Theo dõi & đo lường",
         "Chỉ số cần theo dõi (CTR, AVD, retention, like/xem) và mốc tốt."),
        ("3.2 — Tương tác cộng đồng",
         "Trả lời bình luận, bài community, livestream để tăng quay lại."),
        ("3.3 — Duy trì & phát triển",
         "Lịch đăng đều, làm lại video cũ yếu (refresh), kế hoạch 30-90 ngày."),
    ]
    for title, hint in steps:
        lines.append(f"## Bước {title}")
        lines.append(hint)
        lines.append("")
    lines.append("## ✅ TÓM TẮT — 5 VIỆC LÀM TUẦN NÀY")
    lines.append("Liệt kê đúng 5 việc ưu tiên cao nhất rút ra từ 9 bước trên, "
                 "theo thứ tự, mỗi việc 1 dòng, làm được ngay trong tuần.")
    lines.append("")
    lines.append("Trả lời TRỰC TIẾP bằng markdown. BẮT ĐẦU NGAY bằng "
                 "\"## Bước 1.1\". TUYỆT ĐỐI KHÔNG viết câu dẫn nhập / khẩu "
                 "hiệu / tiêu đề tổng — vào thẳng nội dung từng bước.")
    return "\n".join(lines)


def analyze_seo_report(watchlist, channels_data: list,
                       api_key: str = "", model: Optional[str] = None) -> str:
    """Sinh báo cáo SEO thực chiến bằng Claude CLI (Opus). Trả markdown."""
    prompt = build_seo_report_prompt(watchlist, channels_data)
    return call_claude(api_key, prompt, model=model or MODEL, max_tokens=5000)


def collect_watchlist_data_previous(watchlist) -> Optional[list]:
    """
    Lấy data của watchlist tại lần monitor TRƯỚC lần gần nhất (để diff).
    Trả None nếu chỉ có 1 lần monitor (không có previous để so sánh).
    """
    from . import snapshots
    snapshots.init_db()

    # Get list of distinct captured_at times for this watchlist (sorted desc)
    with snapshots._DB_LOCK:
        conn = snapshots._connect()
        try:
            rows = conn.execute("""
                SELECT DISTINCT captured_at
                FROM channel_snapshots
                WHERE watchlist_id=?
                ORDER BY captured_at DESC
                LIMIT 50
            """, (watchlist.id,)).fetchall()
        finally:
            conn.close()

    # Nhóm các snapshots gần nhau (cùng 1 batch monitor) → mỗi batch ≤ 1 giờ
    times = [r["captured_at"] for r in rows]
    if len(times) < 2:
        return None

    # Tìm 2 batch riêng biệt (cách nhau ít nhất 30 phút)
    from datetime import datetime, timedelta
    try:
        latest = datetime.fromisoformat(times[0])
    except Exception:
        return None
    previous_batch_time = None
    for t in times[1:]:
        try:
            t_obj = datetime.fromisoformat(t)
            if (latest - t_obj) >= timedelta(minutes=30):
                previous_batch_time = t
                break
        except Exception:
            continue
    if not previous_batch_time:
        return None

    # Collect data using snapshots at/before previous_batch_time
    data = []
    for ch in watchlist.channels:
        cid = ch.channel_id
        # Snapshot at exactly previous batch time (or closest before)
        with snapshots._DB_LOCK:
            conn = snapshots._connect()
            try:
                row = conn.execute("""
                    SELECT * FROM channel_snapshots
                    WHERE watchlist_id=? AND channel_id=?
                      AND captured_at <= ?
                    ORDER BY captured_at DESC LIMIT 1
                """, (watchlist.id, cid, previous_batch_time)).fetchone()
                snap = dict(row) if row else None
                vsnaps = []
                if snap:
                    rows2 = conn.execute("""
                        SELECT * FROM video_snapshots
                        WHERE channel_snapshot_id=?
                        ORDER BY views_per_hour DESC
                    """, (snap["id"],)).fetchall()
                    vsnaps = [dict(r) for r in rows2]
            finally:
                conn.close()

        if not snap:
            continue

        views = [v.get("view_count", 0) for v in vsnaps]
        likes = [v.get("like_count", 0) for v in vsnaps]
        comments = [v.get("comment_count", 0) for v in vsnaps]
        entry = {
            "title": ch.title,
            "channel_id": cid,
            "is_self": ch.is_self,
            "subscriber_count": snap.get("subscriber_count", 0),
            "video_count": snap.get("video_count", 0),
            "view_count": snap.get("view_count", 0),
            "captured_at": snap.get("captured_at", ""),
            "top1_views": max(views) if views else 0,
            "avg_views_per_video": (
                sum(views) // max(len(views), 1) if views else 0),
            "like_view_ratio": (
                sum(likes) / sum(views) * 100 if sum(views) > 0 else 0),
            "comment_view_ratio": (
                sum(comments) / sum(views) * 100 if sum(views) > 0 else 0),
            "data_source": "previous_snapshot",
        }
        data.append(entry)
    return data if data else None


def collect_watchlist_data(watchlist) -> list:
    """
    Gom data cho từng kênh trong watchlist:
      - Channel snapshot mới nhất (subs, video_count, view_count)
      - Top 10 video theo views_per_hour
      - Metrics: avg views/video, like/view ratio, comment/view ratio,
        videos_per_day
      - Research keywords (nếu có history)

    Trả list dict đã chuẩn bị sẵn cho build_watchlist_strategy_prompt.
    """
    from . import snapshots
    from .persistence import find_previous_for_channel
    from datetime import datetime

    snapshots.init_db()
    data = []
    for ch in watchlist.channels:
        cid = ch.channel_id
        snap = snapshots.get_latest_channel_snapshot(watchlist.id, cid)
        # Video snapshots
        vsnaps = []
        if snap:
            with snapshots._DB_LOCK:
                conn = snapshots._connect()
                try:
                    rows = conn.execute("""
                        SELECT * FROM video_snapshots
                        WHERE channel_snapshot_id=?
                        ORDER BY views_per_hour DESC
                    """, (snap["id"],)).fetchall()
                    vsnaps = [dict(r) for r in rows]
                finally:
                    conn.close()
        # Research nếu có
        research = (find_previous_for_channel(cid)
                    if cid.startswith("UC") else None)
        # Build entry
        entry = {
            "title": ch.title,
            "channel_id": cid,
            "is_self": ch.is_self,
            "subscriber_count": snap["subscriber_count"] if snap else 0,
            "video_count": snap["video_count"] if snap else 0,
            "view_count": snap["view_count"] if snap else 0,
            "captured_at": snap["captured_at"] if snap else "",
            "top_videos_by_vph": [
                {
                    "title": v.get("title", ""),
                    "view_count": v.get("view_count", 0),
                    "like_count": v.get("like_count", 0),
                    "comment_count": v.get("comment_count", 0),
                    "views_per_hour": v.get("views_per_hour", 0),
                    "viral_score": v.get("viral_score", 0),
                    "published_at": v.get("published_at", ""),
                    "video_id": v.get("video_id", ""),
                }
                for v in vsnaps[:10]
            ],
            "research_keywords": [
                k.keyword
                for k in (research.get("keywords", []) if research else [])
            ][:30],
            "has_research": bool(research),
        }
        # Compute aggregates - ưu tiên research data (có like/comment đầy đủ),
        # fallback snapshot data (light monitor không enrich nên like/comment = 0)
        rvideos = (research.get("videos", []) if research else [])
        use_research = bool(rvideos) and any(
            getattr(v, "like_count", 0) > 0 for v in rvideos)

        if use_research:
            views = [v.view_count for v in rvideos]
            likes = [v.like_count for v in rvideos]
            comments = [v.comment_count for v in rvideos]
            entry["data_source"] = "research"
        elif vsnaps:
            views = [v.get("view_count", 0) for v in vsnaps]
            likes = [v.get("like_count", 0) for v in vsnaps]
            comments = [v.get("comment_count", 0) for v in vsnaps]
            entry["data_source"] = "snapshot"
        else:
            views = likes = comments = []
            entry["data_source"] = "none"

        if views:
            entry["avg_views_per_video"] = sum(views) // max(len(views), 1)
            entry["median_views"] = sorted(views)[len(views) // 2]
            entry["top1_views"] = max(views)
            if sum(views) > 0:
                entry["like_view_ratio"] = (
                    sum(likes) / sum(views) * 100)
                entry["comment_view_ratio"] = (
                    sum(comments) / sum(views) * 100)

        # Post freq - ưu tiên research videos nếu có
        pubs = []
        src = rvideos if use_research else vsnaps
        for v in src:
            pa = (getattr(v, "published_at", "") if use_research
                  else v.get("published_at", ""))
            if pa:
                try:
                    pubs.append(datetime.fromisoformat(
                        pa.replace("Z", "+00:00")))
                except Exception:
                    pass
        if len(pubs) >= 2:
            pubs.sort(reverse=True)
            span_days = (pubs[0] - pubs[-1]).days
            if span_days > 0:
                entry["videos_per_day"] = len(pubs) / span_days
                entry["last_upload"] = pubs[0].isoformat(
                    timespec="seconds")
        data.append(entry)
    return data


def _build_advanced_insights_block(result: dict) -> str:
    """Inject summary insight nâng cao từ Wave 1-2 modules vào AI prompt.

    Modules: title_pattern, thumb_vision, ab_rescue, comment_intel,
    hook_timing, posting_v2, viral_predictor. Mỗi cái có data trong pkl
    thì format vài dòng summary. Không có thì skip.

    Mục tiêu: AI Opus / Haiku có context đủ để khuyến nghị cụ thể —
    không phải đoán mò.
    """
    lines = []

    # Title Pattern
    tp = result.get("title_pattern") or {}
    if tp and not tp.get("error") and tp.get("recommendations"):
        lines.append("## INSIGHT TIÊU ĐỀ (data-driven từ "
                     f"{tp.get('n_videos', 0)} video kênh chính)")
        for r in tp["recommendations"]:
            lines.append(f"- {r}")
        if tp.get("winning_ngrams"):
            top = ", ".join(n["ngram"]
                            for n in tp["winning_ngrams"][:5])
            lines.append(f"- Cụm từ \"thắng\" (top video hay dùng): {top}")
        lines.append("")

    # Thumbnail Vision summary
    tv = result.get("thumbnail_vision_summary") or {}
    if tv and not tv.get("error") and tv.get("n"):
        lines.append(f"## INSIGHT THUMBNAIL (Claude Vision phân tích "
                     f"{tv['n']} top thumbnail)")
        lines.append(
            f"- Click score TB: {tv.get('avg_click_score', 0)}/10 "
            f"({tv.get('pct_with_face', 0)}% có face, "
            f"{tv.get('pct_with_text', 0)}% có text overlay)")
        lines.append(
            f"- Emotion chủ đạo: {tv.get('top_emotion', '?')}, "
            f"subject: {tv.get('top_subject', '?')}, "
            f"color: {tv.get('top_color_scheme', '?')}")
        if tv.get("common_weaknesses"):
            lines.append(
                f"- Điểm yếu thường gặp: "
                f"{', '.join(tv['common_weaknesses'][:3])}")
        if tv.get("sample_improvements"):
            lines.append("- Đề xuất cụ thể (mẫu):")
            for imp in tv["sample_improvements"][:3]:
                lines.append(f"  • {imp}")
        lines.append("")

    # AB Rescue
    ab = result.get("ab_rescue") or []
    if ab:
        lines.append(f"## VIDEO FLOP CẦN CỨU ({len(ab)} video)")
        for i, rec in enumerate(ab[:5], 1):
            sv = rec["self_video"]
            best = rec["competitor_matches"][0]
            lines.append(
                f"{i}. \"{sv['title'][:60]}\" ({sv['vpd']:,} v/d) — "
                f"đối thủ {best['comp_channel'][:25]} đạt "
                f"{best['comp_video']['vpd']:,} v/d "
                f"(lift {best['lift_potential']}x) với title "
                f"\"{best['comp_video']['title'][:60]}\"")
        lines.append("")

    # Comment Intelligence
    ci = result.get("comment_intelligence") or {}
    if ci and not ci.get("error"):
        lines.append("## AUDIENCE INSIGHT (từ comment khán giả)")
        if ci.get("sentiment_overall"):
            lines.append(f"- Sentiment: {ci['sentiment_overall']}")
        if ci.get("pain_points"):
            top_pp = ci["pain_points"][:3]
            lines.append(
                f"- Pain points top: "
                f"{', '.join(p['theme'] for p in top_pp)}")
        if ci.get("video_requests"):
            top_req = ci["video_requests"][:3]
            lines.append(
                f"- Audience yêu cầu: "
                f"{', '.join(r['topic'] for r in top_req)}")
        if ci.get("video_ideas"):
            lines.append("- Ý tưởng video từ demand:")
            for idea in ci["video_ideas"][:3]:
                lines.append(f"  • {idea}")
        if ci.get("red_flags"):
            lines.append(
                f"- ⚠ Cảnh báo: {'; '.join(ci['red_flags'][:2])}")
        lines.append("")

    # Hook Timing (Inside data only — nếu có)
    hk = result.get("hook_timing") or {}
    if hk and not hk.get("error") and hk.get("n_videos"):
        lines.append("## HOOK TIMING (retention 15s đầu)")
        lines.append(
            f"- {hk['n_strong']} video hook mạnh / "
            f"{hk['n_weak']} hook yếu / {hk['n_videos']} total")
        if hk.get("recommendations"):
            for r in hk["recommendations"]:
                lines.append(f"- {r}")
        lines.append("")

    # Posting Time V2
    pt = result.get("posting_v2") or {}
    if pt and not pt.get("error") and pt.get("best_slots_local"):
        lines.append("## GIỜ POST TỐI ƯU (theo audience timezone)")
        top3 = pt["best_slots_local"][:3]
        slots_str = ", ".join(f"{s['local_hour']:02d}h"
                              for s in top3)
        lines.append(f"- Top 3 khung giờ VN: {slots_str}")
        if pt.get("audience_breakdown"):
            lines.append(
                f"- Audience: {' · '.join(pt['audience_breakdown'][:3])}")
        lines.append("")

    # Viral Predictor (cho top 5 video gần đây)
    vp = result.get("viral_predictor") or {}
    if vp and vp.get("predictions"):
        lines.append("## DỰ ĐOÁN VIRAL (top 5 video gần đây)")
        for p in vp["predictions"]:
            adv = p.get("advice", [""])[0] if p.get("advice") else ""
            lines.append(
                f"- \"{p['title'][:50]}\": "
                f"predicted {p['predicted_vpd']:,} v/d "
                f"(actual {p['actual_vpd']:,}, p{p['percentile_rank']}) "
                f"— {adv[:80]}")
        lines.append("")

    if not lines:
        return ""

    header = ("\n# DỮ LIỆU INSIGHT NÂNG CAO (Wave 1-2 — chuyên gia)\n"
              "Dùng các insight dưới đây để khuyến nghị CỤ THỂ trong "
              "phần 5+6. Không lặp lại nguyên văn, mà tích hợp tự nhiên "
              "vào lý luận.\n")
    return header + "\n".join(lines)
