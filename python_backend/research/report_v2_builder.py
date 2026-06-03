# -*- coding: utf-8 -*-
"""Report V2 Builder — HTML báo cáo 4 panel + Executive Summary.

Mục đích: 1 file HTML phục vụ 3 vai trò team media:
- Panel A: PM (bao quát thị trường)
- Panel B: Editor/Producer (gợi ý sản xuất)
- Panel C: SEO (tối ưu thuật toán)
- Panel D: Data raw (audit/verify)

Mỗi panel có 5-7 sub-tab. Tab system vanilla JS, không phụ thuộc CDN.

Usage:
    from .report_v2_builder import build_report_v2
    out_path = build_report_v2(wid, out_dir="ket_qua/bao_cao_html_v2")
    # out_path: đường dẫn file HTML đã tạo

Architecture:
- collect_data(wid) → dict tất cả data từ pkl + modules → dùng cho render
- render_executive(data) → HTML string
- render_panel_a/b/c/d(data) → HTML string
- assemble(exec, panels) → 1 file HTML hoàn chỉnh
"""
from __future__ import annotations

import json
import os
import pickle
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# DATA COLLECTION
# ============================================================

def collect_data(wid: str, log_fn=print) -> dict:
    """Đọc TẤT CẢ data sources cho 1 WL → trả dict thống nhất.

    Trả dict:
        {
          'wl': watchlist object,
          'self_pkl': pkl kênh chính,
          'self_pkl_prev': pkl kỳ trước (so sánh),
          'competitor_pkls': [pkl các kênh đối thủ trong WL],
          'inside': dict YouTube Analytics (channel_inside + retention + ctr),
          'kw_bank': keyword bank harvest,
          'modules': {
              'title_pattern': ..., 'viral_predictor': ...,
              'hook_timing': ..., 'content_cluster': ...,
              'posting_v2': ..., 'ab_rescue': ...,
              'cross_wl': ...
          },
          'data_health': {
              'inside_fresh': bool, 'sb_fresh': bool, 'trends_fresh': bool,
              'comments_available': bool, 'cross_wl_available': bool
          }
        }
    """
    from . import watchlist as wl_mod, persistence

    out = {
        "wid": wid,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "wl": None,
        "self_pkl": None,
        "self_pkl_prev": None,
        "competitor_pkls": [],
        "inside": {},
        "kw_bank": None,
        "modules": {},
        "data_health": {},
    }

    w = wl_mod.load_watchlist(wid)
    if not w:
        log_fn(f"  ! WL không tồn tại: {wid}")
        return out
    out["wl"] = w

    # Self pkl (kênh chính)
    if w.self_channel and w.self_channel.channel_id:
        cid = w.self_channel.channel_id
        idx = persistence._load_index()
        recs = sorted(
            [e for e in idx if e.get("channel_id") == cid
             and e.get("type") == "channel"],
            key=lambda e: e["id"], reverse=True)
        if recs:
            try:
                with open(recs[0]["pkl_path"], "rb") as f:
                    out["self_pkl"] = pickle.load(f)
            except Exception as e:
                log_fn(f"  ! Lỗi đọc self pkl: {e}")
            # Pkl kỳ trước (record thứ 2)
            if len(recs) > 1:
                try:
                    with open(recs[1]["pkl_path"], "rb") as f:
                        out["self_pkl_prev"] = pickle.load(f)
                except Exception:
                    pass

    # Competitor pkls (trong WL, không tính self)
    self_cid = w.self_channel.channel_id if w.self_channel else None
    for c in w.channels:
        if not c.channel_id or not c.channel_id.startswith("UC"):
            continue
        if c.channel_id == self_cid:
            continue
        idx = persistence._load_index()
        recs = sorted(
            [e for e in idx if e.get("channel_id") == c.channel_id
             and e.get("type") == "channel"],
            key=lambda e: e["id"], reverse=True)
        if recs:
            try:
                with open(recs[0]["pkl_path"], "rb") as f:
                    out["competitor_pkls"].append(pickle.load(f))
            except Exception:
                pass

    # Inside (YouTube Analytics)
    if w.self_channel:
        try:
            from .analytics_inside import (
                match_account_tag, get_channel_inside,
                get_retention_full, get_thumbnail_ctr_top, is_available)
            if is_available():
                tag = match_account_tag(
                    w.self_channel.title, w.self_channel.channel_id)
                if tag:
                    out["inside"]["account_tag"] = tag
                    out["inside"]["summary"] = get_channel_inside(
                        tag, recent_days=30) or {}
                    try:
                        out["inside"]["retention"] = get_retention_full(
                            tag, top_n=15, min_views=500) or []
                    except Exception as e:
                        log_fn(f"  ! retention err: {e}")
                        out["inside"]["retention"] = []
                    try:
                        out["inside"]["ctr_top"] = get_thumbnail_ctr_top(
                            tag, top_n=15, min_impressions=200) or []
                    except Exception as e:
                        log_fn(f"  ! ctr err: {e}")
                        out["inside"]["ctr_top"] = []
        except Exception as e:
            log_fn(f"  ! inside err: {e}")

    # Keyword bank
    if w.self_channel:
        try:
            from .keyword_bank_analysis import get_channel_kw_bank
            out["kw_bank"] = get_channel_kw_bank(
                w.self_channel.channel_id, w.self_channel.title)
        except Exception as e:
            log_fn(f"  ! kw_bank err: {e}")

    # Modules đã có trong self pkl (đọc thẳng từ pkl)
    sp = out["self_pkl"] or {}
    out["modules"] = {
        "title_pattern": sp.get("title_pattern") or {},
        "viral_predictor": sp.get("viral_predictor") or {},
        "hook_timing": sp.get("hook_timing") or {},
        "posting_v2": sp.get("posting_v2") or {},
        "ab_rescue": sp.get("ab_rescue") or [],
        "thumbnail_analysis": sp.get("thumbnail_analysis") or {},
        "channel_thumbnail_analysis": sp.get(
            "channel_thumbnail_analysis") or {},
        "thumbnail_comparison": sp.get("thumbnail_comparison") or {},
        "tag_metrics": sp.get("tag_metrics") or {},
        "recent_by_keyword": sp.get("recent_by_keyword") or {},
        "top_by_keyword": sp.get("top_by_keyword") or {},
        "ai_analysis": sp.get("ai_analysis") or "",
    }

    # Cross-WL learning
    try:
        from .cross_wl_learning import get_cross_wl_insights
        out["modules"]["cross_wl"] = get_cross_wl_insights(wid) or {}
    except Exception as e:
        out["modules"]["cross_wl"] = {}

    # Data health
    out["data_health"] = {
        "inside_fresh": bool(out["inside"].get("summary", {}).get("has_data")),
        "retention_available": bool(out["inside"].get("retention")),
        "ctr_available": bool(out["inside"].get("ctr_top")),
        "sb_fresh": bool((sp.get("socialblade") or {}).get("summary")),
        "trends_fresh": bool(out["modules"]["tag_metrics"].get(
            "per_keyword", {})),
        "kw_bank_available": bool(out["kw_bank"]),
        "ai_available": bool(out["modules"]["ai_analysis"]),
        "title_pattern_available": bool(out["modules"]["title_pattern"]),
        "competitors_count": len(out["competitor_pkls"]),
    }

    return out


# ============================================================
# CSS + JS (inline, không CDN)
# ============================================================

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #f3f4f6; color: #1f2937; line-height: 1.5;
}
.container { max-width: 1400px; margin: 0 auto; padding: 16px; }

/* Executive Summary header sticky */
.exec-summary {
  background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
  color: white; padding: 24px; border-radius: 12px;
  margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.exec-summary h1 { font-size: 22px; margin-bottom: 8px; }
.exec-summary .meta { font-size: 13px; opacity: 0.7; margin-bottom: 16px; }
.exec-kpis { display: flex; gap: 24px; margin: 16px 0; flex-wrap: wrap; }
.kpi-box {
  background: rgba(255,255,255,0.1); padding: 12px 20px; border-radius: 8px;
  border-left: 4px solid #60a5fa; min-width: 150px;
}
.kpi-box .label { font-size: 11px; text-transform: uppercase; opacity: 0.7; }
.kpi-box .value { font-size: 24px; font-weight: 700; margin-top: 4px; }
.kpi-box .delta { font-size: 12px; margin-top: 2px; }
.kpi-box .delta.up { color: #4ade80; }
.kpi-box .delta.down { color: #f87171; }
.kpi-box .delta.flat { color: #fbbf24; }
.strategy {
  background: rgba(255,255,255,0.15); padding: 12px 16px;
  border-radius: 8px; margin-top: 12px; font-size: 15px;
}
.strategy::before { content: "🎯 "; }
.top-actions { margin-top: 12px; }
.top-actions li { margin: 4px 0 4px 20px; font-size: 14px; }

/* Tab bar (4 panel) */
.panel-tabs {
  display: flex; gap: 4px; margin-bottom: 0; padding: 0;
  background: #fff; border-radius: 12px 12px 0 0;
  overflow-x: auto; border-bottom: 2px solid #e5e7eb;
}
.panel-tab {
  padding: 14px 24px; cursor: pointer; font-weight: 600;
  border: none; background: transparent; color: #6b7280;
  font-size: 15px; white-space: nowrap;
  border-bottom: 3px solid transparent;
  transition: all 0.2s;
}
.panel-tab:hover { color: #1f2937; background: #f9fafb; }
.panel-tab.active {
  color: #2563eb; border-bottom-color: #2563eb;
  background: #eff6ff;
}
.panel-tab .role-badge {
  display: inline-block; font-size: 10px; padding: 2px 6px;
  border-radius: 4px; margin-left: 6px; opacity: 0.8;
  background: rgba(0,0,0,0.08);
}

/* Panel content */
.panel-content {
  background: #fff; border-radius: 0 0 12px 12px;
  padding: 20px; min-height: 400px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.panel { display: none; }
.panel.active { display: block; }

/* Sub-tabs trong panel */
.sub-tabs {
  display: flex; gap: 2px; flex-wrap: wrap; margin-bottom: 16px;
  border-bottom: 1px solid #e5e7eb; padding-bottom: 0;
}
.sub-tab {
  padding: 8px 14px; cursor: pointer; font-size: 13px;
  background: #f9fafb; color: #4b5563;
  border: 1px solid #e5e7eb; border-bottom: none;
  border-radius: 6px 6px 0 0;
  font-weight: 500;
}
.sub-tab.active {
  background: #2563eb; color: white; border-color: #2563eb;
}
.sub-content { display: none; }
.sub-content.active { display: block; }
.sub-content h3 {
  font-size: 18px; margin-bottom: 12px;
  color: #1e293b; border-bottom: 2px solid #e5e7eb;
  padding-bottom: 8px;
}
.sub-content h4 { font-size: 15px; margin: 16px 0 8px; color: #334155; }

/* Card grid */
.card-grid {
  display: grid; gap: 12px; margin: 12px 0;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}
.card {
  background: #f9fafb; padding: 14px; border-radius: 8px;
  border-left: 3px solid #cbd5e1;
}
.card.hot { border-left-color: #ef4444; }
.card.warm { border-left-color: #f59e0b; }
.card.cool { border-left-color: #10b981; }
.card .title { font-weight: 600; font-size: 14px; }
.card .desc { font-size: 13px; color: #6b7280; margin-top: 4px; }
.card .stats { font-size: 12px; margin-top: 6px; color: #475569; }

/* Tables */
table.data {
  width: 100%; border-collapse: collapse; margin: 12px 0;
  font-size: 13px;
}
table.data th, table.data td {
  padding: 8px 10px; text-align: left;
  border-bottom: 1px solid #e5e7eb;
}
table.data th {
  background: #f3f4f6; font-weight: 600;
  position: sticky; top: 0;
}
table.data tr:hover { background: #f9fafb; }
table.data .num { text-align: right; font-variant-numeric: tabular-nums; }
table.data .pos { color: #16a34a; }
table.data .neg { color: #dc2626; }

/* Alert badges */
.badge {
  display: inline-block; padding: 2px 8px; border-radius: 12px;
  font-size: 11px; font-weight: 600;
}
.badge.ok { background: #d1fae5; color: #065f46; }
.badge.warn { background: #fef3c7; color: #92400e; }
.badge.fail { background: #fee2e2; color: #991b1b; }
.badge.info { background: #dbeafe; color: #1e40af; }

.alert {
  padding: 12px 16px; border-radius: 8px; margin: 12px 0;
  border-left: 4px solid;
}
.alert.warn {
  background: #fffbeb; border-color: #f59e0b; color: #78350f;
}
.alert.info {
  background: #eff6ff; border-color: #3b82f6; color: #1e3a8a;
}
.alert.error {
  background: #fef2f2; border-color: #ef4444; color: #7f1d1d;
}

/* AI text (markdown-like) */
.ai-text {
  background: #fafafa; padding: 16px 20px; border-radius: 8px;
  border-left: 4px solid #8b5cf6;
  font-family: "Segoe UI", sans-serif; font-size: 14px;
  white-space: pre-wrap; line-height: 1.6;
  max-height: 800px; overflow-y: auto;
}

.footer {
  text-align: center; margin-top: 32px; padding: 16px;
  color: #9ca3af; font-size: 12px;
}

/* Print friendly */
@media print {
  .panel { display: block !important; }
  .panel-tabs, .sub-tabs { display: none; }
  .sub-content { display: block !important; page-break-inside: avoid; }
}

/* Mobile responsive */
@media (max-width: 768px) {
  .container { padding: 8px; }
  .panel-tab { padding: 10px 12px; font-size: 13px; }
  .panel-content { padding: 12px; }
  .card-grid { grid-template-columns: 1fr; }
  .kpi-box { min-width: 100%; }
}
"""

JS = """
// Panel tab switching
document.querySelectorAll('.panel-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const target = tab.dataset.target;
    document.querySelectorAll('.panel-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(target).classList.add('active');
    // Activate first sub-tab in this panel
    const panel = document.getElementById(target);
    const firstSubTab = panel.querySelector('.sub-tab');
    if (firstSubTab) firstSubTab.click();
  });
});

// Sub-tab switching (scoped per panel)
document.querySelectorAll('.sub-tab').forEach(st => {
  st.addEventListener('click', () => {
    const target = st.dataset.subTarget;
    const panel = st.closest('.panel');
    panel.querySelectorAll('.sub-tab').forEach(t => t.classList.remove('active'));
    panel.querySelectorAll('.sub-content').forEach(c => c.classList.remove('active'));
    st.classList.add('active');
    panel.querySelector('#' + target).classList.add('active');
  });
});

// Auto-activate first panel + first sub-tab on load
window.addEventListener('DOMContentLoaded', () => {
  const firstTab = document.querySelector('.panel-tab');
  if (firstTab) firstTab.click();
});

// Sortable tables
document.querySelectorAll('table.sortable th').forEach(th => {
  th.style.cursor = 'pointer';
  th.addEventListener('click', () => {
    const table = th.closest('table');
    const idx = Array.from(th.parentNode.children).indexOf(th);
    const rows = Array.from(table.tBodies[0].rows);
    const asc = !th.classList.contains('asc');
    table.querySelectorAll('th').forEach(t => t.classList.remove('asc', 'desc'));
    th.classList.add(asc ? 'asc' : 'desc');
    rows.sort((a, b) => {
      const av = a.cells[idx].textContent.replace(/[^0-9.\\-]/g, '');
      const bv = b.cells[idx].textContent.replace(/[^0-9.\\-]/g, '');
      const an = parseFloat(av) || a.cells[idx].textContent;
      const bn = parseFloat(bv) || b.cells[idx].textContent;
      if (typeof an === 'number' && typeof bn === 'number') {
        return asc ? an - bn : bn - an;
      }
      return asc ? String(an).localeCompare(String(bn))
                 : String(bn).localeCompare(String(an));
    });
    rows.forEach(r => table.tBodies[0].appendChild(r));
  });
});
"""


# ============================================================
# RENDER HELPERS
# ============================================================

def _fmt_num(n) -> str:
    """Format số 1500000 → '1.5M', 32000 → '32K'."""
    if n is None:
        return "—"
    try:
        n = float(n)
    except Exception:
        return str(n)
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if abs(n) >= 1_000:
        return f"{n/1_000:.1f}K"
    return f"{int(n):,}"


def _fmt_pct(p) -> str:
    if p is None:
        return "—"
    try:
        return f"{float(p):.1f}%"
    except Exception:
        return str(p)


def _h(s) -> str:
    """HTML escape."""
    if s is None:
        return ""
    s = str(s)
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def _badge_data_health(available: bool, label: str) -> str:
    cls = "ok" if available else "fail"
    txt = "✓" if available else "⚠ THIẾU"
    return f'<span class="badge {cls}">{txt} {_h(label)}</span>'


# ============================================================
# EXECUTIVE SUMMARY
# ============================================================

def render_executive(data: dict) -> str:
    """Render header sticky — KPI + chiến lược 1 dòng + top 3 việc."""
    w = data["wl"]
    sp = data["self_pkl"] or {}
    sp_prev = data["self_pkl_prev"] or {}
    sb = (sp.get("socialblade") or {}).get("summary", {}) or {}

    name = (w.name if w else "Unknown WL")
    self_title = sp.get("channel_title", "—")
    subs_now = sp.get("subscriber_count") or 0
    subs_prev = sp_prev.get("subscriber_count") or 0
    subs_delta = subs_now - subs_prev

    vids = sp.get("videos") or []
    # Views 7d: tổng view của video đăng trong 7 ngày qua
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)
    views_7d = 0
    hit_count = 0
    for v in vids:
        a = v.__dict__ if hasattr(v, "__dict__") else v
        pub = a.get("published_at", "")
        if not pub: continue
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            if dt >= cutoff:
                vc = a.get("view_count") or 0
                views_7d += vc
                if vc >= 1_000_000:
                    hit_count += 1
        except Exception:
            pass

    # Health score (placeholder formula)
    health = 50
    if hit_count >= 1: health += 20
    if subs_delta > 0: health += 15
    if subs_delta > 10000: health += 10
    if sb.get("avg_daily_subs", 0) > 1000: health += 10
    health = min(100, health)

    health_color = "#10b981" if health >= 75 else (
        "#f59e0b" if health >= 50 else "#ef4444")

    # KPI deltas
    subs_class = "up" if subs_delta > 0 else ("down" if subs_delta < 0 else "flat")
    subs_sign = "▲" if subs_delta > 0 else ("▼" if subs_delta < 0 else "→")

    # Strategy + actions từ AI
    ai_text = data["modules"]["ai_analysis"] or ""
    # Cố lọc khuyến nghị từ AI (mục 5 hoặc 6)
    strategy_line = "(AI chưa viết — cần Claude Opus 4.7)"
    if ai_text:
        for line in ai_text.split("\n"):
            line = line.strip()
            if line.startswith("- TẬN DỤNG") or line.startswith("- THỬ"):
                strategy_line = line[2:].strip()[:120]
                break

    return f"""
<div class="exec-summary">
  <h1>📊 {_h(name)} <span style="opacity:0.6;font-size:14px;font-weight:400;">— {_h(self_title)}</span></h1>
  <div class="meta">Báo cáo {data["generated_at"]} · Báo cáo V2</div>

  <div class="exec-kpis">
    <div class="kpi-box" style="border-left-color:{health_color};">
      <div class="label">Health Score</div>
      <div class="value">{health}/100</div>
      <div class="delta {subs_class}">{"Tốt" if health >= 75 else ("Cần cải thiện" if health >= 50 else "Báo động")}</div>
    </div>
    <div class="kpi-box">
      <div class="label">Subscribers</div>
      <div class="value">{_fmt_num(subs_now)}</div>
      <div class="delta {subs_class}">{subs_sign} {_fmt_num(abs(subs_delta))} vs kỳ trước</div>
    </div>
    <div class="kpi-box">
      <div class="label">Views 7d (video mới)</div>
      <div class="value">{_fmt_num(views_7d)}</div>
      <div class="delta info">{len(vids)} video tracking</div>
    </div>
    <div class="kpi-box">
      <div class="label">Hit ≥1M / 7d</div>
      <div class="value">{hit_count}</div>
      <div class="delta {'up' if hit_count >= 1 else 'flat'}">{'Có hit MEGA' if hit_count >= 1 else 'Chưa có hit'}</div>
    </div>
  </div>

  <div class="strategy">{_h(strategy_line)}</div>

  <div class="top-actions">
    <strong>📌 Top 3 việc làm ngay:</strong>
    <ol style="margin-top:4px;">
      <li>Xem Panel B (Sản xuất) → tab B4 cho 5 idea video cụ thể tuần này</li>
      <li>Xem Panel C (SEO) → tab C7 kiểm tra tuân khuyến nghị kỳ trước</li>
      <li>Xem Panel A (Thị trường) → tab A3 movers 7d xem ai đang vượt</li>
    </ol>
  </div>
</div>
"""


# ============================================================
# PANEL A — THỊ TRƯỜNG (skeleton, sẽ wire data ở Phase 2)
# ============================================================

def _tier_of(subs: int) -> str:
    if subs >= 3_000_000: return "Mega"
    if subs >= 1_000_000: return "Hit"
    if subs >= 200_000: return "Warm"
    return "Baseline"


def render_panel_a(data: dict) -> str:
    health = data["data_health"]
    cn = health.get("competitors_count", 0)
    badges = " ".join([
        _badge_data_health(cn >= 5, f"{cn} đối thủ"),
        _badge_data_health(health.get("sb_fresh"), "SocialBlade fresh"),
        _badge_data_health(health.get("trends_fresh"), "Trends"),
    ])
    sp = data["self_pkl"] or {}
    self_cid = (data["wl"].self_channel.channel_id
                if data["wl"] and data["wl"].self_channel else None)

    # A1 — bản đồ ngách (bảng tier)
    channels = [sp] + (data["competitor_pkls"] or [])
    a1_rows = []
    by_tier = {"Mega": [], "Hit": [], "Warm": [], "Baseline": []}
    for ch_pkl in channels:
        title = ch_pkl.get("channel_title", "—")
        subs = ch_pkl.get("subscriber_count") or 0
        tier = _tier_of(subs)
        ch_obj = ch_pkl.get("channel")
        cid = ch_obj.channel_id if ch_obj else ""
        is_self = cid == self_cid
        # Top view
        vids = ch_pkl.get("videos") or []
        top_view = 0; top_title = ""
        for v in vids:
            a = v.__dict__ if hasattr(v,'__dict__') else v
            vc = a.get("view_count") or 0
            if vc > top_view:
                top_view = vc; top_title = a.get("title","")[:50]
        # Growth 7d từ SB
        sb_sum = ch_pkl.get("socialblade", {}).get("summary", {}) or {}
        avg_d_subs = sb_sum.get("avg_daily_subs") or 0
        by_tier[tier].append({
            "title": title, "subs": subs, "top": top_view,
            "top_title": top_title, "growth": avg_d_subs, "self": is_self})

    a1_html_parts = []
    for tier in ("Mega", "Hit", "Warm", "Baseline"):
        items = by_tier[tier]
        if not items: continue
        items.sort(key=lambda x: x["subs"], reverse=True)
        cards = []
        for it in items:
            mark = " ★ KÊNH CHÍNH" if it["self"] else ""
            cls = "hot" if it["self"] else ""
            cards.append(f"""
            <div class="card {cls}">
              <div class="title">{_h(it["title"])}{mark}</div>
              <div class="desc">Top: {_h(it["top_title"])}</div>
              <div class="stats">
                {_fmt_num(it["subs"])} subs · top {_fmt_num(it["top"])} view
                · {it["growth"]:.0f}/d
              </div>
            </div>""")
        a1_html_parts.append(f"""
        <h4>Tier {tier} ({len(items)} kênh)</h4>
        <div class="card-grid">{''.join(cards)}</div>""")

    # A2 — cụm chủ đề từ recent_by_keyword
    rbk = sp.get("recent_by_keyword") or {}
    cluster_stats = []
    for kw, vids in rbk.items():
        if not isinstance(vids, list): continue
        total_view = sum((v.get("view_count") or 0) if isinstance(v, dict)
                         else 0 for v in vids)
        cluster_stats.append((kw, len(vids), total_view))
    cluster_stats.sort(key=lambda x: x[2], reverse=True)
    a2_rows = "".join(f"""
        <tr><td>{_h(kw)}</td><td class="num">{nv}</td>
        <td class="num">{_fmt_num(tv)}</td></tr>"""
        for kw, nv, tv in cluster_stats[:15])
    a2_html = f"""
    <table class="data sortable">
      <thead><tr><th>Keyword cụm</th><th class="num">#video</th>
      <th class="num">Tổng view (10 video top)</th></tr></thead>
      <tbody>{a2_rows}</tbody>
    </table>""" if cluster_stats else (
        "<div class='alert warn'>recent_by_keyword chưa có data</div>")

    # A3 — Movers 7d (top growth + top tụt từ avg_daily_subs)
    movers = [(it["title"], it["growth"], it["subs"])
              for tier_lst in by_tier.values() for it in tier_lst
              if it["growth"]]
    movers.sort(key=lambda x: x[1], reverse=True)
    top_up = movers[:5]
    top_down = sorted([m for m in movers if m[1] < 0])[:5]
    a3_html = """<h4>📈 Tăng nhanh (avg subs/day)</h4>
        <table class="data"><thead><tr><th>Kênh</th>
        <th class="num">Subs/day</th><th class="num">Tổng subs</th></tr></thead>
        <tbody>"""
    for t, g, s in top_up:
        cls = "pos" if g > 0 else ""
        a3_html += f'<tr><td>{_h(t)}</td><td class="num {cls}">+{int(g):,}</td><td class="num">{_fmt_num(s)}</td></tr>'
    a3_html += "</tbody></table>"
    if top_down:
        a3_html += """<h4>📉 Đang tụt</h4>
            <table class="data"><thead><tr><th>Kênh</th>
            <th class="num">Subs/day</th><th class="num">Tổng subs</th></tr></thead>
            <tbody>"""
        for t, g, s in top_down:
            a3_html += f'<tr><td>{_h(t)}</td><td class="num neg">{int(g):,}</td><td class="num">{_fmt_num(s)}</td></tr>'
        a3_html += "</tbody></table>"

    # A4 — Top 10 hit ngách 7d (từ recent_by_keyword)
    all_vids_set = {}
    for kw, vids in rbk.items():
        if not isinstance(vids, list): continue
        for v in vids:
            if not isinstance(v, dict): continue
            vid = v.get("video_id") or v.get("url") or v.get("title", "")
            if vid in all_vids_set: continue
            all_vids_set[vid] = v
    # Filter 7d
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)
    a4_vids = []
    for v in all_vids_set.values():
        pub = v.get("published_at") or v.get("upload_date") or ""
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            if dt >= cutoff:
                a4_vids.append(v)
        except Exception:
            pass
    a4_vids.sort(key=lambda v: v.get("view_count", 0), reverse=True)
    a4_rows = "".join(f"""
        <tr>
          <td>{_h((v.get('published_at','') or '')[:10])}</td>
          <td>{_h((v.get('title') or '')[:80])}</td>
          <td>{_h((v.get('channel_title') or '')[:30])}</td>
          <td class="num">{_fmt_num(v.get('view_count'))}</td>
        </tr>""" for v in a4_vids[:10])
    a4_html = f"""
    <table class="data sortable">
      <thead><tr><th>Ngày</th><th>Tiêu đề</th><th>Kênh</th>
      <th class="num">Views</th></tr></thead>
      <tbody>{a4_rows}</tbody>
    </table>""" if a4_vids else "<div class='alert warn'>Chưa có video viral 7d</div>"

    # A5 — Trends keyword
    tm = sp.get("tag_metrics", {}) or {}
    per_kw = tm.get("per_keyword", {}) or {}
    trends_up = []
    trends_down = []
    trends_429 = 0
    for kw, info in per_kw.items():
        if not isinstance(info, dict): continue
        tr = info.get("trend") or {}
        if "429" in str(tr.get("error", "")):
            trends_429 += 1
            continue
        score = tr.get("score")
        direction = tr.get("direction", "")
        if score is None: continue
        if direction == "up" or score > 60:
            trends_up.append((kw, score, direction))
        elif direction == "down" or score < 30:
            trends_down.append((kw, score, direction))
    a5_html = ""
    if trends_429 > 0:
        a5_html += f"<div class='alert warn'>⚠ {trends_429} keyword bị Google Trends 429 — IP nhà rate limited (theo K6 user skip).</div>"
    if trends_up:
        a5_html += "<h4>📈 Top keyword tăng</h4><table class='data'><thead><tr><th>Keyword</th><th class='num'>Score</th><th>Direction</th></tr></thead><tbody>"
        for kw, s, d in sorted(trends_up, key=lambda x: -x[1])[:10]:
            a5_html += f"<tr><td>{_h(kw)}</td><td class='num'>{s}</td><td>{_h(d)}</td></tr>"
        a5_html += "</tbody></table>"
    if trends_down:
        a5_html += "<h4>📉 Top keyword giảm</h4><table class='data'><thead><tr><th>Keyword</th><th class='num'>Score</th><th>Direction</th></tr></thead><tbody>"
        for kw, s, d in sorted(trends_down, key=lambda x: x[1])[:10]:
            a5_html += f"<tr><td>{_h(kw)}</td><td class='num'>{s}</td><td>{_h(d)}</td></tr>"
        a5_html += "</tbody></table>"
    if not trends_up and not trends_down and trends_429 == 0:
        a5_html += "<div class='alert info'>Trends chưa fetch — chạy stage_trends khi IP sạch (VPN/WARP)</div>"

    # A6 — Cảnh báo thị trường
    warnings = []
    # Cụm bão hoà: nếu ≥5 kênh cùng làm top 1 video chứa keyword trùng
    # (đơn giản: list các cluster đầu top với #channel xếp top)
    if len(cluster_stats) > 3:
        warnings.append(f"📊 Top 3 cụm chiếm phần lớn lưu lượng: <b>{', '.join(c[0] for c in cluster_stats[:3])}</b> — cụm A có {_fmt_num(cluster_stats[0][2])} view tổng")
    # Đối thủ mới (chưa đọc được — chờ cross_wl)
    # Tổng kết
    if not warnings:
        warnings.append("✅ Chưa phát hiện cảnh báo quan trọng kỳ này")
    a6_html = "".join(f"<div class='alert warn'>{w}</div>" for w in warnings)

    return f"""
<div class="panel" id="panel-a">
  <div class="sub-tabs">
    <button class="sub-tab" data-sub-target="a1">A1. Bản đồ ngách</button>
    <button class="sub-tab" data-sub-target="a2">A2. Cụm chủ đề</button>
    <button class="sub-tab" data-sub-target="a3">A3. Movers 7d</button>
    <button class="sub-tab" data-sub-target="a4">A4. Top hit ngách</button>
    <button class="sub-tab" data-sub-target="a5">A5. Trends keyword</button>
    <button class="sub-tab" data-sub-target="a6">A6. Cảnh báo</button>
  </div>
  <div style="margin-bottom:12px;">{badges}</div>

  <div class="sub-content" id="a1">
    <h3>A1. Bản đồ ngách — {len(channels)} kênh (chia 4 tier theo subs)</h3>
    {''.join(a1_html_parts)}
  </div>
  <div class="sub-content" id="a2">
    <h3>A2. Cụm chủ đề top 15 (theo total view 10 video đứng đầu mỗi cụm)</h3>
    {a2_html}
  </div>
  <div class="sub-content" id="a3">
    <h3>A3. Movers — tốc độ subs/day (SocialBlade 15-30 ngày)</h3>
    {a3_html}
  </div>
  <div class="sub-content" id="a4">
    <h3>A4. Top 10 video viral ngách 7 ngày qua</h3>
    {a4_html}
  </div>
  <div class="sub-content" id="a5">
    <h3>A5. Google Trends — keyword 7d</h3>
    {a5_html}
  </div>
  <div class="sub-content" id="a6">
    <h3>A6. Cảnh báo thị trường</h3>
    {a6_html}
  </div>
</div>
"""


# ============================================================
# PANEL B — SẢN XUẤT (skeleton)
# ============================================================

def render_panel_b(data: dict) -> str:
    health = data["data_health"]
    badges = " ".join([
        _badge_data_health(health.get("title_pattern_available"), "Title pattern"),
        _badge_data_health(health.get("retention_available"), "Retention"),
        _badge_data_health(health.get("ai_available"), "AI Opus"),
    ])
    sp = data["self_pkl"] or {}
    mods = data["modules"]
    ai_text = mods["ai_analysis"] or "(AI chưa viết)"

    # B1 — title_pattern module ĐẦY ĐỦ
    tp = mods["title_pattern"] or {}
    b1_html = ""
    if tp:
        n_videos = tp.get("n_videos", 0)
        n_top = tp.get("n_top", 0)
        n_bot = tp.get("n_bot", 0)
        length_stats = tp.get("length_stats", {}) or {}
        winning = tp.get("winning_ngrams", []) or []
        losing = tp.get("losing_ngrams", []) or []
        recs = tp.get("recommendations", []) or []
        feat_corr = tp.get("feature_correlation", {}) or {}

        b1_html += f"""
        <div class="card-grid">
          <div class="card hot">
            <div class="title">Phân tích từ</div>
            <div class="stats">{n_videos} video (top {n_top}, bottom {n_bot})</div>
          </div>
          <div class="card">
            <div class="title">Độ dài top video</div>
            <div class="stats">median <b>{length_stats.get('top_median', '—')}</b> ký tự
            (min {length_stats.get('top_min','—')} max {length_stats.get('top_max','—')})</div>
          </div>
          <div class="card">
            <div class="title">Độ dài bottom video</div>
            <div class="stats">median <b>{length_stats.get('bot_median', '—')}</b> ký tự</div>
          </div>
        </div>"""

        # Winning n-grams
        if winning:
            b1_html += "<h4>🏆 N-grams THẮNG (chỉ xuất hiện ở top video)</h4>"
            b1_html += "<table class='data sortable'><thead><tr><th>N-gram</th><th class='num'>Top freq</th><th class='num'>Bot freq</th><th class='num'>Lift</th></tr></thead><tbody>"
            for w in winning[:25]:
                if isinstance(w, dict):
                    b1_html += f"""<tr>
                        <td><b>{_h(w.get('ngram', w.get('text','')))}</b></td>
                        <td class='num pos'>{w.get('top_freq', w.get('top_count', 0))}</td>
                        <td class='num'>{w.get('bot_freq', w.get('bot_count', 0))}</td>
                        <td class='num pos'>{w.get('lift', w.get('score', '—'))}</td>
                    </tr>"""
                elif isinstance(w, (list, tuple)) and len(w) >= 2:
                    b1_html += f"<tr><td>{_h(w[0])}</td><td class='num'>{w[1]}</td><td>—</td><td>—</td></tr>"
            b1_html += "</tbody></table>"

        # Losing n-grams
        if losing:
            b1_html += "<h4>❌ N-grams THUA (chỉ xuất hiện ở bottom video, nên TRÁNH)</h4>"
            b1_html += "<table class='data'><thead><tr><th>N-gram</th><th class='num'>Bot freq</th><th class='num'>Top freq</th></tr></thead><tbody>"
            for w in losing[:25]:
                if isinstance(w, dict):
                    b1_html += f"""<tr>
                        <td><b>{_h(w.get('ngram', w.get('text','')))}</b></td>
                        <td class='num neg'>{w.get('bot_freq', w.get('bot_count', 0))}</td>
                        <td class='num'>{w.get('top_freq', w.get('top_count', 0))}</td>
                    </tr>"""
                elif isinstance(w, (list, tuple)) and len(w) >= 2:
                    b1_html += f"<tr><td>{_h(w[0])}</td><td class='num'>{w[1]}</td><td>—</td></tr>"
            b1_html += "</tbody></table>"

        # Feature correlations
        if feat_corr:
            b1_html += "<h4>📊 Feature correlation với view count</h4>"
            b1_html += "<div class='card-grid'>"
            for feat, corr in feat_corr.items():
                # corr có thể là số hoặc dict {value, p_value}
                if isinstance(corr, dict):
                    val = corr.get("correlation") or corr.get("value") or corr.get("r") or 0
                    extra = f" (p={corr.get('p_value','—')})" if corr.get('p_value') else ""
                else:
                    val = corr
                    extra = ""
                try:
                    val_f = float(val)
                    cls = "hot" if abs(val_f) > 0.3 else ""
                    val_s = f"{val_f:.3f}"
                except (TypeError, ValueError):
                    cls = ""
                    val_s = str(val)
                b1_html += f"""<div class='card {cls}'>
                    <div class='title'>{_h(feat)}</div>
                    <div class='stats'>r = {val_s}{extra}</div>
                </div>"""
            b1_html += "</div>"

        # Recommendations
        if recs:
            b1_html += "<h4>💡 Khuyến nghị từ title pattern</h4><ul style='padding-left:20px;line-height:1.7;'>"
            for r in recs[:15]:
                b1_html += f"<li>{_h(str(r))}</li>"
            b1_html += "</ul>"
    else:
        b1_html = "<div class='alert warn'>title_pattern module chưa chạy — cần rebuild pkl</div>"

    # B2 — thumbnail comparison
    tc = mods["thumbnail_comparison"] or {}
    cta = mods["channel_thumbnail_analysis"] or {}
    ta = mods["thumbnail_analysis"] or {}
    b2_html = ""
    if cta:
        b2_html += "<h4>Kênh chính — phân tích thumbnail</h4><div class='card-grid'>"
        for k, v in list(cta.items())[:10]:
            if isinstance(v, (int, float)):
                b2_html += f"<div class='card'><div class='title'>{_h(k)}</div><div class='stats'>{(f"{v:.2f}" if isinstance(v, float) else str(v))}</div></div>"
            elif isinstance(v, (list, dict)) and v:
                b2_html += f"<div class='card'><div class='title'>{_h(k)}</div><div class='stats'>{_h(str(v)[:100])}</div></div>"
        b2_html += "</div>"
    if tc:
        b2_html += "<h4>So sánh với top đối thủ</h4><div class='card-grid'>"
        for k, v in list(tc.items())[:8]:
            b2_html += f"<div class='card'><div class='title'>{_h(k)}</div><div class='stats'>{_h(str(v)[:120])}</div></div>"
        b2_html += "</div>"
    if not b2_html:
        b2_html = "<div class='alert warn'>thumbnail_analysis chưa có data</div>"

    # B3 — Retention + Hook timing ĐẦY ĐỦ
    inside = data["inside"]
    retention = inside.get("retention") or []
    ht = mods["hook_timing"] or {}
    b3_html = ""

    if ht:
        n_v = ht.get("n_videos", 0)
        n_strong = ht.get("n_strong", 0)
        n_ok = ht.get("n_ok", 0)
        n_weak = ht.get("n_weak", 0)
        b3_html += f"""
        <h4>🎯 Hook 15s đầu — Phân loại {n_v} video kênh nhà</h4>
        <div class="card-grid">
          <div class="card hot"><div class="title">Hook MẠNH</div>
            <div class="stats">{n_strong} video (giữ ≥70% sau 15s)</div></div>
          <div class="card warm"><div class="title">Hook OK</div>
            <div class="stats">{n_ok} video (giữ 50-70%)</div></div>
          <div class="card"><div class="title">Hook YẾU</div>
            <div class="stats">{n_weak} video (giữ &lt;50% — cần fix intro)</div></div>
        </div>"""

        top_hook = ht.get("top_hook_videos", []) or []
        worst_hook = ht.get("worst_hook_videos", []) or []
        if top_hook:
            b3_html += "<h4>✨ Top video hook tốt nhất</h4>"
            b3_html += "<table class='data sortable'><thead><tr><th>Tiêu đề</th><th class='num'>Hook 15s %</th><th class='num'>Views</th></tr></thead><tbody>"
            for v in top_hook[:10]:
                if isinstance(v, dict):
                    hook = v.get("retention_15s") or v.get("hook_pct") or v.get("retention_at_15") or 0
                    hook_s = f"{hook:.1f}" if isinstance(hook, float) else str(hook)
                    b3_html += f"<tr><td>{_h((v.get('title','') or '')[:70])}</td><td class='num pos'>{hook_s}%</td><td class='num'>{_fmt_num(v.get('views') or v.get('view_count'))}</td></tr>"
            b3_html += "</tbody></table>"
        if worst_hook:
            b3_html += "<h4>⚠ Top video hook YẾU (cần re-record intro)</h4>"
            b3_html += "<table class='data sortable'><thead><tr><th>Tiêu đề</th><th class='num'>Hook 15s %</th><th class='num'>Views</th></tr></thead><tbody>"
            for v in worst_hook[:10]:
                if isinstance(v, dict):
                    hook = v.get("retention_15s") or v.get("hook_pct") or v.get("retention_at_15") or 0
                    hook_s = f"{hook:.1f}" if isinstance(hook, float) else str(hook)
                    b3_html += f"<tr><td>{_h((v.get('title','') or '')[:70])}</td><td class='num neg'>{hook_s}%</td><td class='num'>{_fmt_num(v.get('views') or v.get('view_count'))}</td></tr>"
            b3_html += "</tbody></table>"

        recs = ht.get("recommendations", []) or []
        if recs:
            b3_html += "<h4>💡 Khuyến nghị hook timing</h4><ul style='padding-left:20px;line-height:1.7;'>"
            for r in recs[:10]:
                b3_html += f"<li>{_h(str(r))}</li>"
            b3_html += "</ul>"

    if retention:
        retention_sorted = sorted(retention,
            key=lambda r: r.get("avd_pct") or 0, reverse=True)
        b3_html += "<h4>📊 Inside Retention — Top 5 video AVD cao nhất</h4>"
        b3_html += "<table class='data'><thead><tr><th>Tiêu đề</th><th class='num'>AVD %</th><th class='num'>AVD sec</th><th class='num'>Views</th></tr></thead><tbody>"
        for r in retention_sorted[:5]:
            avd = r.get("avd_pct") or 0
            avd_sec = r.get("avd_seconds") or r.get("avd_sec") or 0
            avd_s = f"{avd:.1f}" if isinstance(avd, float) else str(avd)
            b3_html += f"<tr><td>{_h((r.get('title','') or '')[:70])}</td><td class='num pos'>{avd_s}%</td><td class='num'>{int(avd_sec) if avd_sec else 0}s</td><td class='num'>{_fmt_num(r.get('views'))}</td></tr>"
        b3_html += "</tbody></table>"
        b3_html += "<h4>📉 Bottom 5 video AVD thấp nhất</h4>"
        b3_html += "<table class='data'><thead><tr><th>Tiêu đề</th><th class='num'>AVD %</th><th class='num'>AVD sec</th><th class='num'>Views</th></tr></thead><tbody>"
        for r in retention_sorted[-5:]:
            avd = r.get("avd_pct") or 0
            avd_sec = r.get("avd_seconds") or r.get("avd_sec") or 0
            avd_s = f"{avd:.1f}" if isinstance(avd, float) else str(avd)
            b3_html += f"<tr><td>{_h((r.get('title','') or '')[:70])}</td><td class='num neg'>{avd_s}%</td><td class='num'>{int(avd_sec) if avd_sec else 0}s</td><td class='num'>{_fmt_num(r.get('views'))}</td></tr>"
        b3_html += "</tbody></table>"

    if not b3_html:
        b3_html = "<div class='alert warn'>Retention/hook_timing chưa có data — chạy stage_inside</div>"

    # B5 — NGỪNG NGAY (ab_rescue + viral_predictor ĐẦY ĐỦ)
    vp = mods["viral_predictor"] or {}
    ab = mods["ab_rescue"] or []
    b5_html = ""
    if ab:
        b5_html += f"<h4>💔 {len(ab)} video FLOP — gợi ý cứu từ đối thủ (AB recommender)</h4>"
        b5_html += "<div class='alert info'>Mỗi video flop được match với 1 video đối thủ THẮNG cùng cụm chủ đề — học pattern để rescue.</div>"
        for i, item in enumerate(ab[:10], 1):
            if not isinstance(item, dict): continue
            sv = item.get("self_video", {}) or {}
            cv = item.get("competitor_top", {}) or item.get("rescue", {}) or {}
            why = item.get("why") or item.get("reason") or item.get("recommendation", "")
            b5_html += f"""
            <div class='card' style='margin-bottom:8px;'>
              <div class='title'>#{i} VIDEO FLOP CỦA KÊNH:</div>
              <div class='desc'>"{_h((sv.get('title','') or '')[:90])}"</div>
              <div class='stats'>
                Views: {_fmt_num(sv.get('view_count'))} ·
                VPD: {_fmt_num(sv.get('vpd'))} ·
                Tags: {len(sv.get('tags') or [])}
              </div>"""
            if cv:
                b5_html += f"""
              <div style='margin-top:8px;padding:8px;background:#f0fdf4;border-left:3px solid #16a34a;'>
                <div class='title' style='color:#15803d;'>→ HỌC TỪ ĐỐI THỦ THẮNG:</div>
                <div class='desc'>"{_h((cv.get('title','') or '')[:90])}"</div>
                <div class='stats'>
                  Channel: <b>{_h(cv.get('channel_title','') or cv.get('channel','—'))}</b> ·
                  Views: <b>{_fmt_num(cv.get('view_count') or cv.get('views'))}</b> ·
                  VPD: <b>{_fmt_num(cv.get('vpd'))}</b>
                </div>
              </div>"""
            if why:
                b5_html += f"<div style='margin-top:6px;color:#92400e;'>💡 <i>{_h(str(why)[:200])}</i></div>"
            b5_html += "</div>"

    if vp:
        b5_html += "<h4>🔮 Viral Predictor — Model & Predictions</h4>"
        r2 = vp.get("model_r_squared")
        n_samples = vp.get("model_n_samples", 0)
        preds = vp.get("predictions", []) or []
        b5_html += f"""
        <div class="card-grid">
          <div class="card"><div class="title">Model R²</div>
            <div class="stats">{f"{r2:.3f}" if isinstance(r2, float) else r2} (≥0.5 là tốt)</div></div>
          <div class="card"><div class="title">Train samples</div>
            <div class="stats">{n_samples} video</div></div>
        </div>"""
        if preds:
            b5_html += "<h4>Dự đoán views/ngày của 30 video kênh nhà</h4>"
            b5_html += "<table class='data sortable'><thead><tr><th>Tiêu đề</th><th class='num'>Predicted VPD</th><th class='num'>Actual VPD</th><th class='num'>Δ%</th></tr></thead><tbody>"
            for p in preds[:30]:
                if not isinstance(p, dict): continue
                pred = p.get("predicted_vpd") or p.get("predicted_views_per_day") or 0
                actual = p.get("actual_vpd") or p.get("vpd") or 0
                if actual:
                    dt_pct = (pred - actual) / actual * 100
                else:
                    dt_pct = 0
                dt_class = "pos" if dt_pct >= 0 else "neg"
                b5_html += f"<tr><td>{_h((p.get('title','') or '')[:60])}</td><td class='num'>{_fmt_num(pred)}</td><td class='num'>{_fmt_num(actual)}</td><td class='num {dt_class}'>{dt_pct:+.1f}%</td></tr>"
            b5_html += "</tbody></table>"

    if not b5_html:
        b5_html = "<div class='alert info'>Chưa có ab_rescue / viral_predictor data</div>"

    return f"""
<div class="panel" id="panel-b">
  <div class="sub-tabs">
    <button class="sub-tab" data-sub-target="b1">B1. Pattern tiêu đề</button>
    <button class="sub-tab" data-sub-target="b2">B2. Pattern thumbnail</button>
    <button class="sub-tab" data-sub-target="b3">B3. Retention insight</button>
    <button class="sub-tab" data-sub-target="b4">B4. 5 idea video ★</button>
    <button class="sub-tab" data-sub-target="b5">B5. NGỪNG NGAY</button>
  </div>
  <div style="margin-bottom:12px;">{badges}</div>

  <div class="sub-content" id="b1">
    <h3>B1. Pattern tiêu đề thắng — phân tích NLP từ top video viral</h3>
    {b1_html}
  </div>
  <div class="sub-content" id="b2">
    <h3>B2. Pattern thumbnail thắng</h3>
    {b2_html}
  </div>
  <div class="sub-content" id="b3">
    <h3>B3. Retention insight kênh nhà</h3>
    {b3_html}
  </div>
  <div class="sub-content" id="b4">
    <h3>B4. AI Opus 4.7 — phân tích + 5 idea video cho 7 ngày tới</h3>
    <div class="ai-text">{_h(ai_text)}</div>
  </div>
  <div class="sub-content" id="b5">
    <h3>B5. NGỪNG NGAY — pattern flop + video cần rescue</h3>
    {b5_html}
  </div>
</div>
"""


# ============================================================
# PANEL C — SEO (skeleton)
# ============================================================

def _extract_keywords_from_ai(ai_text: str) -> list:
    """Lấy keyword/title từ khuyến nghị AI Opus mục VIỆC LÀM NGAY."""
    if not ai_text: return []
    import re
    out = []
    in_action = False
    for line in ai_text.split("\n"):
        if "VIỆC LÀM NGAY" in line or "Việc làm ngay" in line:
            in_action = True
            continue
        if in_action:
            if line.strip().startswith("##") or "KẾT LUẬN" in line:
                break
            # Tìm title trong quotes
            ms = re.findall(r'"([^"]{15,150})"', line)
            for m in ms:
                if "DIY" in m or "Mini" in m or "Build" in m or "RESCUE" in m or "Concrete" in m or "Brick" in m:
                    out.append(m)
    return out


def _check_compliance(self_pkl, self_pkl_prev) -> dict:
    """So title 5 video MỚI ĐĂNG (sau pkl kỳ trước) vs khuyến nghị
    AI Opus kỳ trước (mục VIỆC LÀM NGAY)."""
    if not self_pkl_prev or not self_pkl:
        return {"available": False, "reason": "Chưa có pkl kỳ trước để so"}
    prev_ai = self_pkl_prev.get("ai_analysis") or ""
    suggested = _extract_keywords_from_ai(prev_ai)
    if not suggested:
        return {"available": False, "reason": "AI kỳ trước không có mục VIỆC LÀM NGAY rõ ràng"}

    # Video mới đăng = video published sau timestamp của pkl kỳ trước
    # Đơn giản: lấy 5 video mới nhất theo published_at
    vids = self_pkl.get("videos") or []
    new_vids = sorted(vids, key=lambda v: (v.__dict__ if hasattr(v,'__dict__') else v).get("published_at",""), reverse=True)[:5]
    # Lấy ngày pkl kỳ trước
    prev_vids = self_pkl_prev.get("videos") or []
    prev_dates = sorted(set((v.__dict__ if hasattr(v,'__dict__') else v).get("published_at","")[:10] for v in prev_vids), reverse=True)[:3]
    prev_latest = prev_dates[0] if prev_dates else ""
    # Filter video đăng SAU prev_latest
    truly_new = []
    for v in new_vids:
        a = v.__dict__ if hasattr(v,'__dict__') else v
        pub = (a.get("published_at") or "")[:10]
        if pub > prev_latest:
            truly_new.append(a)

    # So từng video mới với khuyến nghị: nếu title chứa keyword chính từ khuyến nghị → match
    matches = []
    for v in truly_new:
        title = v.get("title", "").lower()
        matched_sug = None
        # Đơn giản: kiểm 3 từ trong title vs khuyến nghị
        for sug in suggested:
            sug_words = set(w.lower() for w in sug.split() if len(w) > 4)
            title_words = set(w.lower() for w in title.split() if len(w) > 4)
            overlap = sug_words & title_words
            # Cần ≥3 từ trùng (loại từ chung "diy", "mini", "tractor")
            generic = {"diy", "mini", "tractor", "hp"}
            real_overlap = overlap - generic
            if len(real_overlap) >= 2:
                matched_sug = sug
                break
        matches.append({"video": title, "matched_to": matched_sug})

    n_match = sum(1 for m in matches if m["matched_to"])
    n_total = len(truly_new)

    return {
        "available": True,
        "n_match": n_match, "n_total": n_total,
        "suggested": suggested,
        "matches": matches,
        "compliance_pct": (100 * n_match / n_total) if n_total > 0 else 0,
    }


def render_panel_c(data: dict) -> str:
    health = data["data_health"]
    badges = " ".join([
        _badge_data_health(health.get("kw_bank_available"), "Keyword Bank"),
        _badge_data_health(health.get("inside_fresh"), "Inside Analytics"),
        _badge_data_health(health.get("ctr_available"), "CTR data"),
    ])
    sp = data["self_pkl"] or {}
    mods = data["modules"]
    inside = data["inside"]
    kw_bank = data["kw_bank"] or {}

    # C1 — Title SEO checklist (extract idea từ AI Opus)
    ai_text = mods["ai_analysis"] or ""
    suggested_titles = _extract_keywords_from_ai(ai_text)
    c1_html = ""
    if suggested_titles:
        c1_html = "<h4>5 title nháp từ AI Opus — checklist SEO</h4>"
        c1_html += "<table class='data'><thead><tr><th>Title</th><th class='num'>Length</th><th>Có emoji?</th><th>Có số cụ thể?</th><th>Có CTR trigger?</th></tr></thead><tbody>"
        triggers = ["RESCUE", "MEGA", "EMERGENCY", "DYING", "FIREPROOF", "CRACKED", "FLOOD", "WILDFIRE", "REAL", "HIDDEN", "NEAR CRASH"]
        for t in suggested_titles[:10]:
            ln = len(t)
            ln_class = "pos" if ln <= 60 else ("neg" if ln > 80 else "")
            has_emoji = any(ord(c) > 127 for c in t)
            has_num = any(c.isdigit() for c in t)
            has_trigger = any(tr in t.upper() for tr in triggers)
            c1_html += f"""<tr>
                <td>{_h(t)}</td>
                <td class='num {ln_class}'>{ln}</td>
                <td>{'✅' if has_emoji else '❌'}</td>
                <td>{'✅' if has_num else '❌'}</td>
                <td>{'✅' if has_trigger else '❌'}</td>
            </tr>"""
        c1_html += "</tbody></table>"
        c1_html += """<div class='alert info'>
            <b>Tiêu chuẩn:</b> Length ≤60 (hiển full mobile) · Có emoji (CTR +12%) ·
            Có số cụ thể (3-Day, 4-Day...) · Có từ trigger (RESCUE/MEGA/EMERGENCY) chứng minh tăng CTR
        </div>"""
    else:
        c1_html = "<div class='alert warn'>AI Opus chưa có mục VIỆC LÀM NGAY với title nháp</div>"

    # C2 — Description (chỉ template thôi vì description thật do team viết)
    c2_html = """
    <div class="alert info">Template description chuẩn — copy paste cho mỗi video:</div>
    <pre style="background:#f3f4f6;padding:12px;border-radius:6px;font-size:13px;overflow:auto;">
[100 ký tự đầu: HOOK + keyword chính + CTA]
DIY Mini Tractor [Tên chủ đề] | [Outcome] - Cứu farm/dựng cầu/v.v. trong [N] ngày

[Chapter timestamps để boost retention]
00:00 [Problem setup]
00:30 [Hook drama]
01:00 [Action begins]
...

[Mô tả chi tiết 200-300 chữ]
[Liên kết playlist + 3 video related]

🎬 More videos: [link playlist]
👉 Subscribe for daily DIY: [link]

[Tags ẩn]
#DIYMiniTractor #FarmRescue #MiniConstruction
</pre>"""

    # C3 — Tag suggestion ĐẦY ĐỦ (per_keyword: competition + autosuggest)
    tm = sp.get("tag_metrics", {}) or {}
    per_kw = tm.get("per_keyword", {}) or {}
    seo_sum = tm.get("seo_summary", {}) or {}
    c3_html = ""
    if seo_sum:
        c3_html += "<h4>📊 SEO summary toàn ngách</h4><div class='card-grid'>"
        for k, v in seo_sum.items():
            c3_html += f"<div class='card'><div class='title'>{_h(k)}</div><div class='stats'>{_h(str(v)[:60])}</div></div>"
        c3_html += "</div>"
    if per_kw:
        c3_html += f"<h4>🔑 Tag broad — {len(per_kw)} keyword với competition + autosuggest</h4>"
        c3_html += "<table class='data sortable'><thead><tr><th>Keyword</th><th>Cạnh tranh</th><th class='num'>Kết quả</th><th>Top 5 autosuggest</th></tr></thead><tbody>"
        for kw, info in per_kw.items():
            if not isinstance(info, dict): continue
            comp = info.get("competition", {}) or {}
            level = comp.get("level", "—")
            label = comp.get("label", "—")
            human = comp.get("human", "")
            result_count = comp.get("result_count", 0)
            autosuggest = info.get("autosuggest", []) or []
            cls = "neg" if level == "high" else ("pos" if level == "low" else "")
            c3_html += f"""<tr>
                <td><b>{_h(kw)}</b></td>
                <td class='{cls}'>{_h(label)}</td>
                <td class='num'>{_fmt_num(result_count)}</td>
                <td>{_h(', '.join(autosuggest[:5]))}</td>
            </tr>"""
        c3_html += "</tbody></table>"

    # kw_bank tier
    if kw_bank:
        c3_html += "<h4>💎 Kho từ khoá keywordtool (đã enrich)</h4>"
        c3_html += "<div class='card-grid'>"
        tier_labels = {"top_vang": "🥇 VÀNG (search volume cao + competition thấp)",
                       "top_bac": "🥈 BẠC (volume vừa)",
                       "top_dong": "🥉 ĐỒNG (volume thấp nhưng dễ rank)"}
        for tier, label in tier_labels.items():
            items = kw_bank.get(tier, []) if isinstance(kw_bank.get(tier), list) else []
            if not items: continue
            c3_html += f"<div class='card'><div class='title'>{label}</div><div class='stats'>{len(items)} keyword</div></div>"
        c3_html += "</div>"
        # Detail table
        all_kws = []
        for tier in ("top_vang", "top_bac", "top_dong"):
            for it in kw_bank.get(tier, []) or []:
                if isinstance(it, dict):
                    all_kws.append({**it, "tier": tier})
        if all_kws:
            c3_html += "<h4>Bảng từ khoá chi tiết (sort được)</h4>"
            c3_html += "<table class='data sortable'><thead><tr><th>Keyword</th><th>Tier</th><th class='num'>Volume</th><th class='num'>CPM</th><th>Trend</th></tr></thead><tbody>"
            for it in all_kws[:30]:
                vol = it.get("search_volume") or it.get("volume") or 0
                cpm = it.get("cpc") or it.get("cpm") or 0
                trend = it.get("trend", "—")
                c3_html += f"""<tr>
                    <td><b>{_h(it.get('keyword',''))}</b></td>
                    <td><span class='badge {'ok' if it.get('tier')=='top_vang' else 'info'}'>{_h(it.get('tier',''))}</span></td>
                    <td class='num'>{_fmt_num(vol)}</td>
                    <td class='num'>{_fmt_num(cpm)}</td>
                    <td>{_h(str(trend)[:20])}</td>
                </tr>"""
            c3_html += "</tbody></table>"

    if not c3_html:
        c3_html = "<div class='alert warn'>kw_bank + tag_metrics chưa có data</div>"

    # C4 — Audience signal (posting_v2 + Inside)
    pv = mods["posting_v2"] or {}
    c4_html = ""
    if pv:
        c4_html += "<h4>Posting time v2 (timezone-aware)</h4>"
        for k, v in list(pv.items())[:10]:
            c4_html += f"<div class='card'><div class='title'>{_h(k)}</div><div class='stats'>{_h(str(v)[:200])}</div></div>"
    if inside.get("summary"):
        s = inside["summary"]
        countries = s.get("top_countries") or []
        c4_html += "<h4>Audience timezone (top countries)</h4>"
        c4_html += "<table class='data'><thead><tr><th>Country</th><th class='num'>%</th><th>Suggest timezone</th></tr></thead><tbody>"
        tz_map = {"IN": "+5:30", "BD": "+6:00", "PK": "+5:00", "ID": "+7:00",
                  "NP": "+5:45", "EG": "+2:00", "PH": "+8:00", "BR": "-3:00",
                  "KH": "+7:00", "UZ": "+5:00"}
        for c in countries[:10]:
            if isinstance(c, dict):
                cc = c.get("country", "")
                tz = tz_map.get(cc, "—")
                c4_html += f"<tr><td>{_h(cc)}</td><td class='num'>{_fmt_pct(c.get('pct'))}</td><td>{tz}</td></tr>"
        c4_html += "</tbody></table>"
        # Khuyến nghị giờ đăng (audience top tz)
        c4_html += "<div class='alert info'>💡 <b>Khuyến nghị:</b> đăng video lúc <b>19:00-21:00 IST (giờ Ấn Độ)</b> = <b>20:30-22:30 GMT+7 Việt Nam</b> — peak engagement audience NAM Á.</div>"
    if not c4_html:
        c4_html = "<div class='alert warn'>Inside + posting_v2 chưa có data</div>"

    # C5 — Algorithm health
    c5_html = ""
    if inside.get("summary"):
        s = inside["summary"]
        ts = s.get("traffic_sources_recent") or []
        c5_html += "<h4>Traffic source breakdown (Inside 30d)</h4>"
        c5_html += "<table class='data'><thead><tr><th>Source</th><th class='num'>Views</th><th class='num'>%</th><th>Ý nghĩa</th></tr></thead><tbody>"
        means = {
            "RELATED_VIDEO": "Thuật toán đề xuất (sidebar/next-up) — sức khoẻ kênh",
            "YT_OTHER_PAGE": "YouTube homepage browse — appeal CTR",
            "SUBSCRIBER": "Người sub xem — loyal audience",
            "YT_SEARCH": "SEO search — keyword tốt",
            "END_SCREEN": "End screen click — internal linking",
            "PLAYLIST": "Playlist autoplay — series binge",
            "NOTIFICATION": "Bell notify — sub active",
            "EXT_URL": "Embed/share ngoài — viral spread"
        }
        for t in ts[:10]:
            if isinstance(t, dict):
                src = t.get("source", "")
                c5_html += f"<tr><td>{_h(src)}</td><td class='num'>{_fmt_num(t.get('views'))}</td><td class='num'>{_fmt_pct(t.get('pct'))}</td><td>{_h(means.get(src,''))}</td></tr>"
        c5_html += "</tbody></table>"
        # Health indicators
        related_pct = next((t.get("pct", 0) for t in ts if isinstance(t,dict) and t.get("source")=="RELATED_VIDEO"), 0)
        search_pct = next((t.get("pct", 0) for t in ts if isinstance(t,dict) and t.get("source")=="YT_SEARCH"), 0)
        sub_pct = next((t.get("pct", 0) for t in ts if isinstance(t,dict) and t.get("source")=="SUBSCRIBER"), 0)
        c5_html += f"""<h4>Algorithm health score</h4>
        <div class="card-grid">
          <div class="card {'hot' if related_pct >= 50 else 'warm'}">
            <div class="title">Related Video %</div>
            <div class="stats">{related_pct:.1f}% — {'Thuật toán đang đẩy mạnh' if related_pct >= 50 else 'Thuật toán đẩy yếu, cần tối ưu thumbnail/title'}</div>
          </div>
          <div class="card {'hot' if search_pct >= 10 else 'warm'}">
            <div class="title">Search %</div>
            <div class="stats">{search_pct:.1f}% — {'SEO tốt' if search_pct >= 10 else 'SEO yếu, cần optimize tag + description'}</div>
          </div>
          <div class="card {'hot' if sub_pct >= 15 else 'warm'}">
            <div class="title">Subscriber %</div>
            <div class="stats">{sub_pct:.1f}% — {'Audience loyal' if sub_pct >= 15 else 'Sub không active, cần notification campaign'}</div>
          </div>
        </div>"""
    else:
        c5_html = "<div class='alert warn'>Inside chưa có data traffic source</div>"

    # C6 — Playlist + End screen + Cards
    c6_html = """
    <div class="alert info">Khuyến nghị structural cho 5 video mới:</div>
    <ol style="padding-left:20px;line-height:1.8;">
      <li><b>Playlist gom:</b> Tạo playlist "Construction MEGA Series" — gom 3 video cụm Bridge/Brick Water/Fireproof. Đặt video MEGA nhất ở vị trí 1 để algorithm autoplay drive views.</li>
      <li><b>End screen 20s cuối:</b> Link 3 video hot nhất 30d (Irrigation Hard Soil 1.6M, Disc Harrow 527K, Land Roller 499K). Mỗi video có element CTA "Watch next" + sub bell.</li>
      <li><b>Cards:</b> Đặt card click-through tại các điểm drop retention (xem Panel B3) — thường là phút 3-4 (khi audience bắt đầu chán). Card link sang video same cluster để giữ session.</li>
      <li><b>Pinned comment:</b> mỗi video đăng comment ngắn từ chính kênh kêu gọi "Like & Sub for more MEGA builds" — algorithm coi đây là engagement signal.</li>
      <li><b>Community post warming:</b> 2 ngày trước khi đăng video MEGA, post poll Community ("Which should we build next: Bridge or Brick Pond?") → tạo anticipation.</li>
    </ol>"""

    # C7 — Compliance (★ TỰ ĐỘNG)
    comp = _check_compliance(sp, data["self_pkl_prev"])
    c7_html = ""
    if comp.get("available"):
        pct = comp["compliance_pct"]
        n_m = comp["n_match"]; n_t = comp["n_total"]
        cls = "ok" if pct >= 60 else ("warn" if pct >= 30 else "fail")
        c7_html = f"""
        <div class="alert {('info' if pct >= 60 else 'warn' if pct >= 30 else 'error')}">
          <h4 style="margin:0 0 6px 0;">Tuân khuyến nghị: <b>{n_m}/{n_t} video</b> ({pct:.0f}%)</h4>
          {'✅ Kênh đang theo định hướng tốt' if pct >= 60 else '⚠ Kênh chưa nghe khuyến nghị — nhắc lại RÕ hơn kỳ này' if pct >= 30 else '❌ Kênh hoàn toàn không theo — cần meeting với team biên kịch'}
        </div>"""
        c7_html += "<h4>Khuyến nghị kỳ trước</h4><ul style='padding-left:20px;'>"
        for s in comp["suggested"][:10]:
            c7_html += f"<li>{_h(s)}</li>"
        c7_html += "</ul>"
        c7_html += "<h4>Video MỚI ĐĂNG (sau kỳ trước) vs khuyến nghị</h4>"
        c7_html += "<table class='data'><thead><tr><th>Video mới đăng</th><th>Match khuyến nghị nào?</th></tr></thead><tbody>"
        for m in comp["matches"]:
            ok = m["matched_to"] is not None
            mark = "✅" if ok else "❌"
            c7_html += f"<tr><td>{mark} {_h(m['video'][:70])}</td><td>{_h(m['matched_to'] or '(không match khuyến nghị nào)')}</td></tr>"
        c7_html += "</tbody></table>"
    else:
        c7_html = f"<div class='alert info'>{_h(comp.get('reason','Chưa thể kiểm tra compliance'))}</div>"

    return f"""
<div class="panel" id="panel-c">
  <div class="sub-tabs">
    <button class="sub-tab" data-sub-target="c1">C1. Title SEO</button>
    <button class="sub-tab" data-sub-target="c2">C2. Description</button>
    <button class="sub-tab" data-sub-target="c3">C3. Tag suggestion</button>
    <button class="sub-tab" data-sub-target="c4">C4. Audience signal</button>
    <button class="sub-tab" data-sub-target="c5">C5. Algorithm health</button>
    <button class="sub-tab" data-sub-target="c6">C6. Playlist + EndScr</button>
    <button class="sub-tab" data-sub-target="c7">C7. Compliance ★</button>
  </div>
  <div style="margin-bottom:12px;">{badges}</div>

  <div class="sub-content" id="c1">
    <h3>C1. Title SEO checklist — extract từ AI Opus mục VIỆC LÀM NGAY</h3>
    {c1_html}
  </div>
  <div class="sub-content" id="c2">
    <h3>C2. Description script template</h3>
    {c2_html}
  </div>
  <div class="sub-content" id="c3">
    <h3>C3. Tag suggestion (broad + long-tail)</h3>
    {c3_html}
  </div>
  <div class="sub-content" id="c4">
    <h3>C4. Audience signal — giờ đăng tối ưu cho audience NAM Á</h3>
    {c4_html}
  </div>
  <div class="sub-content" id="c5">
    <h3>C5. Algorithm health check (Inside 30d)</h3>
    {c5_html}
  </div>
  <div class="sub-content" id="c6">
    <h3>C6. Playlist + End screen + Cards strategy</h3>
    {c6_html}
  </div>
  <div class="sub-content" id="c7">
    <h3>C7. Compliance — TỰ ĐỘNG so video mới đăng vs khuyến nghị kỳ trước</h3>
    {c7_html}
  </div>
</div>
"""


# ============================================================
# PANEL D — DATA RAW (skeleton)
# ============================================================

def _render_delta(data: dict) -> str:
    """Render bảng so kỳ trước cho các chỉ số quan trọng."""
    sp = data["self_pkl"] or {}
    spp = data["self_pkl_prev"] or {}
    if not spp:
        return "<div class='alert info'>Chưa có pkl kỳ trước để so</div>"
    rows = []
    fields = [
        ("subscriber_count", "Subscribers"),
        ("video_count", "Video count"),
    ]
    for f, label in fields:
        cur = sp.get(f) or 0
        prev = spp.get(f) or 0
        delta = cur - prev
        pct = (100 * delta / prev) if prev else 0
        cls = "pos" if delta > 0 else ("neg" if delta < 0 else "")
        sign = "+" if delta > 0 else ""
        rows.append(f"""<tr>
          <td>{label}</td>
          <td class='num'>{_fmt_num(prev)}</td>
          <td class='num'>{_fmt_num(cur)}</td>
          <td class='num {cls}'>{sign}{_fmt_num(delta)}</td>
          <td class='num {cls}'>{sign}{pct:.1f}%</td>
        </tr>""")
    # SB delta
    sb_cur = (sp.get("socialblade") or {}).get("summary", {}) or {}
    sb_prev = spp.get("socialblade", {}).get("summary", {}) or {}
    for f, label in [("latest_views", "Total views (SB)"),
                     ("avg_daily_subs", "Avg subs/day"),
                     ("avg_daily_views", "Avg views/day")]:
        cur = sb_cur.get(f) or 0
        prev = sb_prev.get(f) or 0
        delta = cur - prev
        pct = (100 * delta / prev) if prev else 0
        cls = "pos" if delta > 0 else ("neg" if delta < 0 else "")
        sign = "+" if delta > 0 else ""
        rows.append(f"""<tr>
          <td>{label}</td>
          <td class='num'>{_fmt_num(prev)}</td>
          <td class='num'>{_fmt_num(cur)}</td>
          <td class='num {cls}'>{sign}{_fmt_num(delta)}</td>
          <td class='num {cls}'>{sign}{pct:.1f}%</td>
        </tr>""")
    return f"""
    <table class='data'>
      <thead><tr><th>Chỉ số</th><th class='num'>Kỳ trước</th>
      <th class='num'>Kỳ này</th><th class='num'>Δ tuyệt đối</th>
      <th class='num'>Δ %</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>"""


def render_panel_d(data: dict) -> str:
    sp = data["self_pkl"] or {}
    vids = sp.get("videos") or []
    # D1 — bảng 30 video sortable
    rows = []
    for v in vids:
        a = v.__dict__ if hasattr(v, "__dict__") else v
        pub = (a.get("published_at") or "")[:10]
        rows.append(f"""
        <tr>
          <td>{_h(pub)}</td>
          <td>{_h((a.get("title") or "")[:80])}</td>
          <td class="num">{_fmt_num(a.get("view_count"))}</td>
          <td class="num">{_fmt_num(a.get("like_count"))}</td>
          <td class="num">{_fmt_num(a.get("comment_count"))}</td>
          <td class="num">{int((a.get("duration_seconds") or 0)/60)}p</td>
          <td class="num">{len(a.get("tags") or [])}</td>
        </tr>""")
    d1_table = f"""
    <table class="data sortable">
      <thead>
        <tr><th>Ngày</th><th>Tiêu đề</th><th>Views</th><th>Likes</th>
        <th>Cmt</th><th>Dài</th><th>#Tag</th></tr>
      </thead>
      <tbody>{''.join(rows)}</tbody>
    </table>"""

    # D2 — SocialBlade
    sb_summary = (sp.get("socialblade") or {}).get("summary", {}) or {}
    sb_html = "<div class='alert info'>SocialBlade chưa có data</div>"
    if sb_summary:
        sb_html = f"""
        <div class="card-grid">
          <div class="card"><div class="title">Grade</div>
            <div class="stats">{_h(sb_summary.get("grade", "—"))}</div></div>
          <div class="card"><div class="title">Avg subs/day</div>
            <div class="stats">{_fmt_num(sb_summary.get("avg_daily_subs"))}</div></div>
          <div class="card"><div class="title">Avg views/day</div>
            <div class="stats">{_fmt_num(sb_summary.get("avg_daily_views"))}</div></div>
          <div class="card"><div class="title">Period subs growth</div>
            <div class="stats">{_fmt_num(sb_summary.get("period_subs_growth"))}</div></div>
        </div>"""

    # D3 — Inside summary
    inside = data["inside"]
    inside_html = "<div class='alert warn'>Inside chưa có data (kênh không có OAuth token)</div>"
    if inside.get("summary"):
        s = inside["summary"]
        inside_html = f"""
        <h4>Tổng quan 30d</h4>
        <div class="card-grid">
          <div class="card"><div class="title">Account tag</div>
            <div class="stats">{_h(inside.get("account_tag", "—"))}</div></div>
          <div class="card"><div class="title">Video tracking</div>
            <div class="stats">{s.get("video_count", 0)}</div></div>
          <div class="card"><div class="title">Avg AVD</div>
            <div class="stats">{int(s.get("avg_avd_seconds") or 0)}s</div></div>
        </div>
        <h4>Devices</h4>
        <table class="data"><thead><tr><th>Device</th><th class="num">%</th></tr></thead>
        <tbody>{"".join(f"<tr><td>{_h(k)}</td><td class='num'>{_fmt_pct(v)}</td></tr>" for k,v in (s.get("devices") or {}).items())}</tbody>
        </table>"""

    # D5 — Đối thủ chi tiết (mỗi kênh 1 card)
    competitors = data["competitor_pkls"] or []
    d5_html = f"<h4>{len(competitors)} kênh đối thủ trong WL — chi tiết</h4>"
    for c_pkl in competitors:
        c_title = c_pkl.get("channel_title", "—")
        c_subs = c_pkl.get("subscriber_count") or 0
        c_obj = c_pkl.get("channel")
        c_desc = ""
        c_kws = []
        if c_obj:
            ca = c_obj.__dict__ if hasattr(c_obj, "__dict__") else c_obj
            c_desc = (ca.get("description") or "")[:200]
            c_kws = ca.get("keywords") or []
        c_vids = c_pkl.get("videos") or []
        # Top 5 video
        c_vids_sorted = sorted(c_vids,
            key=lambda v: (v.__dict__ if hasattr(v,'__dict__') else v).get("view_count", 0),
            reverse=True)[:5]
        c_sb = c_pkl.get("socialblade", {}).get("summary", {}) or {}

        d5_html += f"""
        <details style='margin-bottom:8px;border:1px solid #e5e7eb;border-radius:6px;'>
          <summary style='padding:10px;cursor:pointer;background:#f9fafb;font-weight:600;'>
            {_h(c_title)} — {_fmt_num(c_subs)} subs
            <span style='font-weight:400;color:#666;'>· top {_fmt_num(c_vids_sorted[0].__dict__.get('view_count',0) if c_vids_sorted and hasattr(c_vids_sorted[0],'__dict__') else 0)} view</span>
          </summary>
          <div style='padding:12px;'>
            <p style='color:#475569;font-size:13px;margin-bottom:8px;'>📝 {_h(c_desc) or '(không có mô tả)'}</p>
            <div style='font-size:12px;color:#6b7280;margin-bottom:8px;'><b>Keywords kênh:</b> {_h(', '.join(c_kws[:15]))}</div>
            <div style='font-size:12px;color:#6b7280;margin-bottom:8px;'>
              <b>SB:</b> grade {_h(str(c_sb.get('grade','—')))} ·
              avg subs/d {_fmt_num(c_sb.get('avg_daily_subs'))} ·
              avg views/d {_fmt_num(c_sb.get('avg_daily_views'))}
            </div>
            <h4 style='margin-top:8px;'>Top 5 video</h4>
            <table class='data'><thead><tr><th>Tiêu đề</th><th class='num'>Views</th><th class='num'>Ngày</th></tr></thead><tbody>"""
        for v in c_vids_sorted:
            a = v.__dict__ if hasattr(v,'__dict__') else v
            d5_html += f"<tr><td>{_h((a.get('title','') or '')[:80])}</td><td class='num'>{_fmt_num(a.get('view_count'))}</td><td>{_h((a.get('published_at','') or '')[:10])}</td></tr>"
        d5_html += "</tbody></table></div></details>"

    # D6 — Top by keyword (21 cụm × 14 video top all-time)
    tbk = sp.get("top_by_keyword") or {}
    d6_html = f"<h4>{len(tbk)} cụm chủ đề × top 14 video all-time</h4>"
    if tbk:
        for kw, vids in tbk.items():
            if not isinstance(vids, list) or not vids: continue
            top_v = max(vids, key=lambda v: v.get("view_count", 0) if isinstance(v, dict) else 0)
            d6_html += f"""
            <details style='margin-bottom:6px;border:1px solid #e5e7eb;border-radius:6px;'>
              <summary style='padding:8px;cursor:pointer;background:#fef3c7;font-weight:600;'>
                🔑 {_h(kw)} — {len(vids)} video · top {_fmt_num(top_v.get('view_count') if isinstance(top_v, dict) else 0)}
              </summary>
              <div style='padding:8px;'>
                <table class='data'><thead><tr><th>Tiêu đề</th><th>Kênh</th><th class='num'>Views</th></tr></thead><tbody>"""
            for v in vids[:10]:
                if not isinstance(v, dict): continue
                d6_html += f"<tr><td>{_h((v.get('title','') or '')[:70])}</td><td>{_h((v.get('channel_title','') or '')[:25])}</td><td class='num'>{_fmt_num(v.get('view_count'))}</td></tr>"
            d6_html += "</tbody></table></div></details>"
    else:
        d6_html += "<div class='alert warn'>top_by_keyword chưa có data</div>"

    return f"""
<div class="panel" id="panel-d">
  <div class="sub-tabs">
    <button class="sub-tab" data-sub-target="d1">D1. Video kênh nhà</button>
    <button class="sub-tab" data-sub-target="d2">D2. SocialBlade</button>
    <button class="sub-tab" data-sub-target="d3">D3. Inside</button>
    <button class="sub-tab" data-sub-target="d4">D4. So kỳ trước</button>
    <button class="sub-tab" data-sub-target="d5">D5. {len(competitors)} đối thủ chi tiết</button>
    <button class="sub-tab" data-sub-target="d6">D6. Top {len(tbk)} cụm chủ đề</button>
  </div>

  <div class="sub-content" id="d1">
    <h3>D1. Bảng 30 video kênh chính (click cột để sort)</h3>
    {d1_table}
  </div>
  <div class="sub-content" id="d2">
    <h3>D2. SocialBlade summary</h3>
    {sb_html}
  </div>
  <div class="sub-content" id="d3">
    <h3>D3. Inside (YouTube Analytics API)</h3>
    {inside_html}
  </div>
  <div class="sub-content" id="d4">
    <h3>D4. So kỳ trước (delta)</h3>
    {_render_delta(data)}
  </div>
  <div class="sub-content" id="d5">
    <h3>D5. Toàn bộ {len(competitors)} đối thủ — click để mở chi tiết</h3>
    {d5_html}
  </div>
  <div class="sub-content" id="d6">
    <h3>D6. Top by keyword — {len(tbk)} cụm × top 10 video all-time</h3>
    {d6_html}
  </div>
</div>
"""


# ============================================================
# ASSEMBLE
# ============================================================

def assemble(data: dict, exec_html: str, panels: dict) -> str:
    """Gom executive + 4 panel thành 1 file HTML hoàn chỉnh."""
    w = data["wl"]
    name = (w.name if w else "WL")
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_h(name)} — Báo cáo V2</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
  {exec_html}

  <div class="panel-tabs">
    <button class="panel-tab" data-target="panel-a">
      📈 Thị trường <span class="role-badge">PM</span>
    </button>
    <button class="panel-tab" data-target="panel-b">
      🎬 Sản xuất <span class="role-badge">Editor</span>
    </button>
    <button class="panel-tab" data-target="panel-c">
      🔍 SEO <span class="role-badge">SEO</span>
    </button>
    <button class="panel-tab" data-target="panel-d">
      📋 Data raw <span class="role-badge">Audit</span>
    </button>
  </div>

  <div class="panel-content">
    {panels['a']}
    {panels['b']}
    {panels['c']}
    {panels['d']}
  </div>

  <div class="footer">
    Báo cáo V2 · WL: {_h(name)} · Generated {data["generated_at"]}<br>
    Data sources: Monitor + SocialBlade + YouTube Analytics API + keywordtool + 10+ insight modules
  </div>
</div>
<script>{JS}</script>
</body>
</html>
"""


# ============================================================
# MAIN
# ============================================================

def build_report_v2(wid: str, out_dir: Optional[str] = None,
                     log_fn=print) -> Optional[str]:
    """Main entry — build HTML V2 cho 1 WL.

    Returns: đường dẫn file HTML đã tạo, hoặc None nếu fail.
    """
    log_fn(f"[V2] Build báo cáo V2 cho WL {wid}...")
    data = collect_data(wid, log_fn=log_fn)
    if not data["wl"]:
        log_fn(f"[V2] FAIL — WL không tồn tại")
        return None

    exec_html = render_executive(data)
    panels = {
        "a": render_panel_a(data),
        "b": render_panel_b(data),
        "c": render_panel_c(data),
        "d": render_panel_d(data),
    }
    html = assemble(data, exec_html, panels)

    # Output path
    out_dir = Path(out_dir or (_ROOT / "ket_qua" / "bao_cao_html_v2"))
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%d%m%y_%H%M%S")
    name_safe = (data["wl"].name if data["wl"] else "wl")
    name_safe = "".join(c if c.isalnum() or c in " _-" else "_"
                        for c in name_safe).strip()
    out_path = out_dir / f"{ts}_V2_{name_safe}.html"
    out_path.write_text(html, encoding="utf-8")
    log_fn(f"[V2] OK → {out_path} ({len(html):,} bytes)")
    return str(out_path)


# ============================================================
# DUMP DATA cho AI Opus đọc trước khi viết
# ============================================================

def dump_ai_data_files(wid: str, out_dir: Optional[str] = None,
                        log_fn=print) -> dict:
    """Dump 4 file JSON data → AI Opus đọc TRƯỚC khi viết AI.

    Mục đích: Claude Opus viết AI phải có GROUND TRUTH, không guess.
    User dặn 24/05: báo cáo phải dùng data thật, không reasoning suông.

    Files dump:
    - {wid}_retention.json    — top/bottom 15 video AVD (Inside)
    - {wid}_ctr.json          — top 15 video CTR (Inside)
    - {wid}_cluster.json      — top 15 cụm chủ đề theo total view
    - {wid}_compliance.json   — so video mới đăng vs khuyến nghị kỳ trước

    Returns: dict {file_name: path} các file đã dump.
    """
    out_dir = Path(out_dir or (_ROOT / "ket_qua" / "ai_data_dump"))
    out_dir.mkdir(parents=True, exist_ok=True)

    log_fn(f"[AI DATA] Dump 4 file JSON cho WL {wid}...")
    data = collect_data(wid, log_fn=log_fn)
    if not data["wl"]:
        log_fn(f"[AI DATA] FAIL — WL không tồn tại")
        return {}

    files = {}

    # 1. Retention
    retention = data["inside"].get("retention") or []
    if retention:
        retention_sorted = sorted(retention,
            key=lambda r: r.get("avd_pct") or 0, reverse=True)
        out = {
            "wid": wid, "generated_at": data["generated_at"],
            "top_5_high_avd": retention_sorted[:5],
            "bottom_5_low_avd": retention_sorted[-5:],
            "median_avd_pct": (
                retention_sorted[len(retention_sorted)//2].get("avd_pct")
                if retention_sorted else None),
        }
        p = out_dir / f"{wid}_retention.json"
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2,
                                default=str), encoding="utf-8")
        files["retention"] = str(p)
        log_fn(f"  retention: {len(retention)} videos → {p.name}")

    # 2. CTR
    ctr = data["inside"].get("ctr_top") or []
    if ctr:
        out = {
            "wid": wid, "generated_at": data["generated_at"],
            "top_15": ctr[:15],
        }
        p = out_dir / f"{wid}_ctr.json"
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2,
                                default=str), encoding="utf-8")
        files["ctr"] = str(p)
        log_fn(f"  ctr: {len(ctr)} videos → {p.name}")

    # 3. Cluster (top 15 cụm theo total view recent_by_keyword)
    rbk = (data["self_pkl"] or {}).get("recent_by_keyword") or {}
    clusters = []
    for kw, vids in rbk.items():
        if not isinstance(vids, list): continue
        total_view = sum((v.get("view_count") or 0) if isinstance(v, dict)
                         else 0 for v in vids)
        top_video = max(vids, key=lambda v: v.get("view_count", 0)
                        if isinstance(v, dict) else 0, default=None)
        clusters.append({
            "keyword": kw, "video_count": len(vids),
            "total_view": total_view,
            "top_video": ({
                "title": top_video.get("title") if isinstance(top_video, dict) else None,
                "view_count": top_video.get("view_count") if isinstance(top_video, dict) else None,
                "channel": top_video.get("channel_title") if isinstance(top_video, dict) else None,
            } if top_video else None),
        })
    clusters.sort(key=lambda c: c["total_view"], reverse=True)
    out = {"wid": wid, "generated_at": data["generated_at"],
           "top_15_clusters": clusters[:15]}
    p = out_dir / f"{wid}_cluster.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2,
                            default=str), encoding="utf-8")
    files["cluster"] = str(p)
    log_fn(f"  cluster: {len(clusters)} → top 15 → {p.name}")

    # 4. Compliance
    comp = _check_compliance(data["self_pkl"], data["self_pkl_prev"])
    out = {"wid": wid, "generated_at": data["generated_at"], **comp}
    p = out_dir / f"{wid}_compliance.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2,
                            default=str), encoding="utf-8")
    files["compliance"] = str(p)
    log_fn(f"  compliance: available={comp.get('available')} → {p.name}")

    # 5. Inside summary (bonus)
    insum = data["inside"].get("summary") or {}
    if insum:
        out = {"wid": wid, "generated_at": data["generated_at"], **insum}
        p = out_dir / f"{wid}_inside_summary.json"
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2,
                                default=str), encoding="utf-8")
        files["inside_summary"] = str(p)
        log_fn(f"  inside_summary → {p.name}")

    log_fn(f"[AI DATA] Đã dump {len(files)} file vào {out_dir}")
    return files


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) < 2:
        print("Usage: python -m core.report_v2_builder <wid> [--dump-ai-data]")
        sys.exit(1)
    wid = sys.argv[1]
    if "--dump-ai-data" in sys.argv:
        files = dump_ai_data_files(wid)
        print(f"DONE dump: {len(files)} files")
    else:
        p = build_report_v2(wid)
        if p:
            print(f"DONE: {p}")
        else:
            sys.exit(1)
