# -*- coding: utf-8 -*-
"""core/keyword_bank_analysis.py — Phân tích kho từ khoá keywordtool.

Cung cấp 2 lớp tiện ích để các tầng khác (AI prompt, HTML report) tận
dụng kho từ khoá keywordtool đã thu hoạch:

1. ENRICH (`enrich_keywords`): tra cứu volume + cạnh tranh + CPC cho 1
   hoặc nhiều từ khoá → bổ sung vào các bảng từ khoá trong báo cáo HTML
   hiện có (chỗ nào đang phân tích từ khoá mà chưa có số liệu thì có).

2. CHANNEL ANALYSIS (`get_channel_kw_bank`): phân tích toàn bộ kho từ
   khoá ngách của 1 kênh chính → top từ "vàng" (volume cao + cạnh tranh
   thấp), ngách con, từ vàng kênh CHƯA tận dụng, gợi ý hướng SEO. Dùng
   cho tab mới HTML + AI Opus prompt.

Module pure-Python, đọc `keyword_bank.connect()` (SQLite). Đóng exe được.
"""
from __future__ import annotations

import json
import re
import statistics
from typing import Dict, List, Optional

try:
    from . import keyword_bank
except ImportError:
    from . import keyword_bank


_COMP_LABEL = {"low": 0.2, "thấp": 0.2, "medium": 0.5, "trung bình": 0.5,
               "high": 0.85, "cao": 0.85}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _comp_norm(comp, label) -> float:
    """Đưa cạnh tranh về thang 0..1 (0 = không cạnh tranh)."""
    if comp is not None:
        try:
            c = float(comp)
            if c > 1.5:
                return min(1.0, c / 100.0)
            return min(1.0, max(0.0, c))
        except (TypeError, ValueError):
            pass
    if label:
        return _COMP_LABEL.get(str(label).strip().lower(), 0.5)
    return 0.5


def _comp_label_vi(comp_norm: float) -> str:
    """Nhãn cạnh tranh tiếng Việt từ thang 0..1."""
    if comp_norm < 0.33:
        return "thấp"
    if comp_norm < 0.66:
        return "trung bình"
    return "cao"


# ============================================================
# ENRICH — tra số liệu keywordtool cho 1 hoặc nhiều từ khoá
# ============================================================

def enrich_keywords(keywords: List[str]) -> Dict[str, dict]:
    """Tra volume + cạnh tranh + CPC cho danh sách từ khoá.

    Trả: {keyword_lowercase: {volume, competition_norm, competition_label,
    cpc}}. Từ không có trong kho → KHÔNG xuất hiện trong dict.

    Trong kho 1 từ có thể nằm dưới nhiều seed → lấy volume LỚN NHẤT
    (cùng comp tương ứng).
    """
    if not keywords:
        return {}
    norms = list({_norm(k) for k in keywords if k})
    if not norms:
        return {}
    keyword_bank.init_db()
    conn = keyword_bank.connect()
    try:
        out = {}
        for i in range(0, len(norms), 500):
            chunk = norms[i:i + 500]
            qs = ",".join(["?"] * len(chunk))
            # Lấy row có search_volume cao nhất cho mỗi norm
            rows = conn.execute(
                f"SELECT norm, search_volume, competition, "
                f"competition_label, cpc FROM keywords "
                f"WHERE norm IN ({qs}) ORDER BY search_volume DESC NULLS LAST",
                chunk).fetchall()
            for n, vol, comp, lbl, cpc in rows:
                if n in out:
                    continue   # đã có (row đầu có vol cao nhất)
                cn = _comp_norm(comp, lbl)
                out[n] = {
                    "volume": int(vol) if vol else 0,
                    "competition_norm": cn,
                    "competition_label": lbl or _comp_label_vi(cn),
                    "cpc": float(cpc) if cpc else 0.0,
                }
    finally:
        conn.close()
    return out


# ============================================================
# CHANNEL ANALYSIS — phân tích cho 1 kênh chính
# ============================================================

def get_channel_kw_bank(channel_id: str, channel_title: str = "",
                        existing_keywords: Optional[List[str]] = None
                        ) -> Optional[dict]:
    """Phân tích kho từ khoá ngách cho 1 kênh chính.

    Trả dict hoặc None nếu kênh KHÔNG có data trong kho (chưa harvest
    seed nào của kênh).

    Args:
        channel_id: UC...
        channel_title: tên hiển thị.
        existing_keywords: list từ khoá kênh hiện đang dùng (từ
            result["top_keywords"]) để tính từ "vàng" kênh CHƯA tận dụng.
            None = bỏ qua coverage gap.

    Output dict gồm:
        - status: "full" (mọi seed done) | "partial" (1 phần done)
        - seeds_done / seeds_total
        - kw_total: tổng từ khoá ngách (đã khử trùng)
        - kw_golden: số từ "vàng" (volume ≥ trung vị + cạnh tranh ≤ trung vị)
        - top_golden: top 30 từ vàng [{keyword, level, volume, comp,
            comp_label, score}]
        - niche_clusters: top 15 cụm ngách [{name, kw_count, total_volume,
            avg_comp}] — gom theo 2 từ đầu của keyword.
        - coverage_gap: từ vàng kênh CHƯA dùng (nếu cấp existing_keywords).
        - recommendation: text markdown gợi ý ngách nên đi.
    """
    keyword_bank.init_db()
    conn = keyword_bank.connect()
    try:
        seed_rows = conn.execute(
            "SELECT norm, channels, status FROM seeds").fetchall()
        my_seeds = []   # [(seed_norm, status)]
        for sn, ch_json, status in seed_rows:
            for c in json.loads(ch_json or "[]"):
                if c.get("channel_id") == channel_id:
                    my_seeds.append((sn, status))
                    break
        if not my_seeds:
            return None
        seeds_done = sum(1 for _, st in my_seeds if st == "done")
        seeds_total = len(my_seeds)
        if seeds_done == 0:
            return None
        seed_norms = [sn for sn, _ in my_seeds]
        qs = ",".join(["?"] * len(seed_norms))
        kw_rows = conn.execute(
            f"SELECT keyword, level, search_volume, competition, "
            f"competition_label FROM keywords WHERE seed_norm IN ({qs})",
            seed_norms).fetchall()
    finally:
        conn.close()

    if not kw_rows:
        return None

    # Khử trùng — mỗi keyword giữ row có volume cao nhất
    seen: Dict[str, dict] = {}
    for kw, lv, vol, comp, lbl in kw_rows:
        cn = _comp_norm(comp, lbl)
        v = int(vol) if vol else 0
        norm_kw = _norm(kw)
        ex = seen.get(norm_kw)
        if ex is None or v > ex["volume"]:
            seen[norm_kw] = {
                "keyword": kw,
                "level": lv,
                "volume": v,
                "comp": cn,
                "comp_label": lbl or _comp_label_vi(cn),
                "score": v * (1.0 - cn),
            }
    kws = list(seen.values())
    if not kws:
        return None

    vols = [k["volume"] for k in kws]
    med_v = statistics.median(vols) if vols else 0
    comps = [k["comp"] for k in kws]
    med_c = statistics.median(comps) if comps else 0.5

    for k in kws:
        k["golden"] = (k["volume"] >= med_v and k["comp"] <= med_c
                       and k["volume"] > 0)
    kws.sort(key=lambda x: x["score"], reverse=True)
    golden = [k for k in kws if k["golden"]]
    top_golden = [_kw_clean(k) for k in golden[:30]]

    # Niche clusters — gom theo 2 từ đầu (heuristic đủ tốt cho VN/EN)
    niches: Dict[str, dict] = {}
    for k in kws:
        words = re.findall(r"[^\s]+", k["keyword"].lower())
        if len(words) < 2:
            continue
        key = " ".join(words[:2])
        n = niches.setdefault(key, {"name": key, "kw_count": 0,
                                    "total_volume": 0, "_comps": [],
                                    "keywords": []})
        n["kw_count"] += 1
        n["total_volume"] += k["volume"]
        n["_comps"].append(k["comp"])
        # 24/05: lưu list keyword (top 10) trong cụm để HTML render
        # cột "Cạnh tranh SEO YT TB" — lookup kw_enrich.rc trong JS.
        if len(n["keywords"]) < 10:
            n["keywords"].append(k["keyword"])
    niche_list = []
    for n in niches.values():
        if n["kw_count"] >= 3 and n["total_volume"] > 0:
            n["avg_comp"] = sum(n["_comps"]) / len(n["_comps"])
            del n["_comps"]
            niche_list.append(n)
    niche_list.sort(
        key=lambda x: x["total_volume"] * (1 - x["avg_comp"]), reverse=True)
    niche_list = niche_list[:15]

    # Coverage gap — từ vàng kênh CHƯA tận dụng
    coverage_gap = []
    if existing_keywords:
        existing_norms = {_norm(k) for k in existing_keywords if k}
        for k in golden[:80]:
            kn = _norm(k["keyword"])
            covered = False
            for ek in existing_norms:
                if not ek:
                    continue
                if kn in ek or ek in kn:
                    covered = True
                    break
            if not covered:
                coverage_gap.append(_kw_clean(k))
        coverage_gap = coverage_gap[:20]

    # Recommendation — text ngắn cho AI prompt
    rec = []
    if niche_list:
        rec.append("**Ngách nên ưu tiên** (volume cao + cạnh tranh thấp):")
        for n in niche_list[:5]:
            rec.append(
                f"- **{n['name']}** — {n['kw_count']} từ khoá, "
                f"tổng volume {n['total_volume']:,}, "
                f"cạnh tranh TB {n['avg_comp']*100:.0f}%")
    if coverage_gap:
        rec.append("")
        rec.append("**Từ khoá VÀNG kênh CHƯA tận dụng** "
                   "(làm nội dung sớm để ăn view):")
        for k in coverage_gap[:8]:
            rec.append(
                f"- \"{k['keyword']}\" — vol {k['volume']:,}, "
                f"cạnh tranh {k['comp']*100:.0f}%")

    return {
        "channel_id": channel_id,
        "channel_title": channel_title or channel_id,
        "status": "full" if seeds_done == seeds_total else "partial",
        "seeds_done": seeds_done,
        "seeds_total": seeds_total,
        "kw_total": len(kws),
        "kw_golden": len(golden),
        "top_golden": top_golden,
        "niche_clusters": niche_list,
        "coverage_gap": coverage_gap,
        "recommendation": "\n".join(rec),
    }


def _kw_clean(k: dict) -> dict:
    """Tỉa các field nội bộ trước khi xuất ra (bỏ `golden`)."""
    return {kk: v for kk, v in k.items() if kk != "golden"}
