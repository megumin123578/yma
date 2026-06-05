// components/research/InsideSynthesis.jsx
// Render đầy đủ Inside × SEO Synthesis (G1–G20) từ d.inside_synthesis.
import { Box, Typography } from "@mui/material";
import { DataTable, EmptyState, Pill, SectionCard, StatGrid, num } from "./primitives";

const SEV = { good: "success.main", warn: "warning.main", bad: "error.main", high: "error.main", medium: "warning.main", low: "success.main" };
const PILLC = { good: "success", warn: "warning", bad: "error", high: "error", medium: "warning", low: "success" };

const arr = (a) => (Array.isArray(a) ? a.join("–") : a ?? "—");
const has = (v) => (Array.isArray(v) ? v.length > 0 : v && typeof v === "object" ? Object.keys(v).length > 0 : !!v);

// khối finding {finding/issue, diagnosis, action, severity}
const Findings = ({ items }) =>
  (items || []).map((f, i) => {
    if (typeof f === "string")
      return (
        <Typography key={i} variant="body2" sx={{ mb: 1, lineHeight: 1.6 }}>
          {f}
        </Typography>
      );
    const c = SEV[f.severity] || "text.secondary";
    return (
      <Box key={i} sx={{ borderLeft: "3px solid", borderColor: c, pl: 1.5, py: 0.5, mb: 1.5 }}>
        <Typography variant="subtitle2" fontWeight={700} sx={{ color: c }}>
          {f.finding || f.issue || f.title}
        </Typography>
        {f.diagnosis && (
          <Typography variant="body2" sx={{ mt: 0.5, lineHeight: 1.6 }}>
            <b>Chẩn đoán:</b> {f.diagnosis}
          </Typography>
        )}
        {f.action && (
          <Typography variant="body2" sx={{ mt: 0.5, lineHeight: 1.6 }}>
            <b>Hành động:</b> {f.action}
          </Typography>
        )}
      </Box>
    );
  });

const Chips = ({ items, color = "default" }) =>
  (items || []).map((x, i) => <Pill key={i} label={typeof x === "string" ? x : JSON.stringify(x)} color={color} />);

const SubHead = ({ children }) => (
  <Typography variant="subtitle2" fontWeight={700} sx={{ mt: 2, mb: 1 }}>
    {children}
  </Typography>
);

export default function InsideSynthesis({ s }) {
  if (!s || !Object.keys(s).length) return <EmptyState />;
  const pd = s.period_delta;
  const ta = s.top_anatomy;
  const wt = s.worst_vs_top;
  const da = s.desc_audit;
  const tg = s.tags_audit;
  const ti = s.title_audit;
  const rm = s.retention_map;
  const cs = s.ctr_sweet;
  const tl = s.thumbnail_layout;
  const ut = s.upload_timing;
  const eg = s.engagement;
  const cg = s.content_gap;
  const cx = s.channel_x_inside;
  const cc = s.competitor_cross;
  const kc = s.keyword_cluster;
  const cb = s.clickbait_check;
  const cap = s.caption;

  return (
    <>
      {/* G1 — Findings */}
      {has(s.findings) && (
        <SectionCard title={s.niche_name || "Synthesis"} subtitle={s.niche_key}>
          <Findings items={s.findings} />
        </SectionCard>
      )}

      {/* G7 — So sánh chu kỳ 7 ngày */}
      {pd && (
        <SectionCard title="⏱ So sánh chu kỳ này vs kỳ trước">
          <Findings items={pd.alerts} />
          <DataTable
            limit={null}
            rows={[
              { m: "Views", now: pd.current?.views, prev: pd.previous?.views, d: pd.delta?.views_pct, suf: "%" },
              { m: "Subs NET", now: pd.current?.subs_net, prev: pd.previous?.subs_net, d: pd.delta?.subs_net_delta, suf: "" },
              { m: "AVD (s)", now: pd.current?.avd, prev: pd.previous?.avd, d: pd.delta?.avd_pct, suf: "%" },
              { m: "CTR (%)", now: pd.current?.ctr, prev: pd.previous?.ctr, d: pd.delta?.ctr_pct, suf: "%" },
            ]}
            columns={[
              { key: "m", label: "Chỉ số" },
              { key: "now", label: "Kỳ này", align: "right", render: (r) => num(r.now) },
              { key: "prev", label: "Kỳ trước", align: "right", render: (r) => num(r.prev) },
              { key: "d", label: "Δ", align: "right", render: (r) => (r.d == null ? "—" : `${r.d > 0 ? "+" : ""}${r.d}${r.suf}`) },
            ]}
          />
        </SectionCard>
      )}

      {/* G2 — Top anatomy */}
      {ta && (ta.formula || has(ta.patterns)) && (
        <SectionCard title="🏆 Công thức TOP — Thumbnail/Title CTR cao">
          {ta.formula && <Typography variant="body2" sx={{ mb: 1 }}><b>Công thức:</b> {ta.formula}</Typography>}
          {ta.title_length_avg ? <Typography variant="caption" color="text.secondary">Độ dài title TB: {ta.title_length_avg}</Typography> : null}
          {has(ta.patterns) && (
            <DataTable
              limit={null}
              rows={ta.patterns}
              columns={[
                { key: "pattern", label: "Pattern", render: (r) => r.pattern || r.name },
                { key: "pct", label: "% xuất hiện", align: "right", render: (r) => (r.pct != null ? `${r.pct}%` : "—") },
                { key: "examples", label: "Ví dụ", render: (r) => arr(r.examples || r.titles) },
              ]}
            />
          )}
        </SectionCard>
      )}

      {/* G3 — Worst vs top */}
      {wt && (has(wt.missing_patterns) || has(wt.per_video_diag)) && (
        <SectionCard title="⚠ WORST thiếu gì so với TOP">
          {has(wt.missing_patterns) && (
            <DataTable
              limit={null}
              rows={wt.missing_patterns}
              columns={[
                { key: "pattern", label: "Pattern thiếu", render: (r) => r.pattern || r.name },
                { key: "top_pct", label: "TOP có %", align: "right", render: (r) => (r.top_pct != null ? `${r.top_pct}%` : "—") },
                { key: "worst_pct", label: "WORST có %", align: "right", render: (r) => (r.worst_pct != null ? `${r.worst_pct}%` : "—") },
                { key: "gap", label: "Gap", align: "right", render: (r) => (r.gap != null ? `${r.gap}` : "—") },
              ]}
            />
          )}
          {has(wt.per_video_diag) && <Findings items={wt.per_video_diag} />}
        </SectionCard>
      )}

      {/* G4 — Traffic Playbook */}
      {has(s.traffic_playbook) && (
        <SectionCard title="🚦 Playbook theo Traffic Source">
          <DataTable
            limit={null}
            rows={s.traffic_playbook}
            columns={[
              { key: "name", label: "Nguồn", render: (r) => r.name || r.source || "—" },
              { key: "share_pct", label: "Tỷ lệ", align: "right", render: (r) => (r.share_pct != null ? `${r.share_pct}%` : "—") },
              { key: "views", label: "Views", align: "right", render: (r) => num(r.views) },
              { key: "benchmark", label: "Benchmark", align: "center", render: (r) => r.benchmark || "—" },
              { key: "status", label: "Trạng thái", align: "center", render: (r) => (r.status ? <Pill label={r.status} color={r.status === "HIGH" ? "warning" : r.status === "LOW" ? "error" : "success"} /> : "—") },
              {
                key: "actions",
                label: "Hành động",
                render: (r) =>
                  Array.isArray(r.actions) && r.actions.length ? (
                    <Box component="ul" sx={{ pl: 2, m: 0 }}>
                      {r.actions.map((a, i) => (
                        <li key={i}>
                          <Typography variant="body2" sx={{ lineHeight: 1.5 }}>{a}</Typography>
                        </li>
                      ))}
                    </Box>
                  ) : (
                    "—"
                  ),
              },
            ]}
          />
        </SectionCard>
      )}

      {/* G5 — Drop diag */}
      {has(s.drop_diag) && (
        <SectionCard title="📉 Drop point retention → Title">
          <Findings items={s.drop_diag} />
        </SectionCard>
      )}

      {/* G6 — Keyword cluster */}
      {kc && (has(kc.primary) || has(kc.secondary) || kc.reasoning) && (
        <SectionCard title="🔑 Keyword Cluster theo Audience">
          {kc.reasoning && <Typography variant="body2" sx={{ mb: 1 }}>{kc.reasoning}</Typography>}
          {has(kc.primary) && (<><SubHead>Primary</SubHead><Box><Chips items={kc.primary} color="success" /></Box></>)}
          {has(kc.secondary) && (<><SubHead>Secondary</SubHead><Box><Chips items={kc.secondary} color="warning" /></Box></>)}
          {has(kc.modifiers) && (<><SubHead>Modifier</SubHead><Box><Chips items={kc.modifiers} /></Box></>)}
        </SectionCard>
      )}

      {/* G8 — Description audit */}
      {da && has(da.per_video) && (
        <SectionCard
          title="📝 DESCRIPTION Audit"
          action={<Box component="span" sx={{ fontWeight: 700, color: da.fail_rate_pct >= 50 ? "error.main" : "success.main" }}>Fail {da.fail_rate_pct}% · TB {da.avg_word_count} từ (cần ≥{da.min_required})</Box>}
        >
          <DataTable
            limit={null}
            rows={da.per_video}
            columns={[
              { key: "title", label: "Video" },
              { key: "word_count", label: "Từ", align: "right" },
              { key: "hashtags_count", label: "Hashtag", align: "right" },
              { key: "timestamps_count", label: "Timestamp", align: "right" },
              { key: "has_subscribe", label: "CTA Sub", align: "center", render: (r) => (r.has_subscribe ? "✅" : "❌") },
              { key: "issues", label: "Vấn đề", render: (r) => arr(r.issues) },
            ]}
          />
        </SectionCard>
      )}

      {/* G9 — Tags audit */}
      {tg && (has(tg.per_video) || has(tg.recommended_broad)) && (
        <SectionCard
          title="🏷 TAGS Audit"
          action={<Box component="span" sx={{ fontWeight: 700, color: tg.fail_rate_pct >= 50 ? "error.main" : "success.main" }}>Fail {tg.fail_rate_pct}% · nên {arr(tg.recommended_count)} tag</Box>}
        >
          {has(tg.recommended_broad) && (<><SubHead>Tag BROAD nên dùng</SubHead><Box><Chips items={tg.recommended_broad} color="success" /></Box></>)}
          {has(tg.recommended_specific) && (<><SubHead>Tag SPECIFIC nên dùng</SubHead><Box><Chips items={tg.recommended_specific} color="warning" /></Box></>)}
          {has(tg.most_used_tags) && (<><SubHead>Tag kênh đang dùng</SubHead><Box><Chips items={(tg.most_used_tags || []).map((t) => `${t.tag} (${t.n})`)} /></Box></>)}
          {has(tg.per_video) && (
            <>
              <SubHead>Theo video</SubHead>
              <DataTable
                limit={null}
                rows={tg.per_video}
                columns={[
                  { key: "title", label: "Video" },
                  { key: "tag_count", label: "#Tags", align: "right", render: (r) => num(r.tag_count ?? r.n_tags) },
                  { key: "issues", label: "Vấn đề", render: (r) => arr(r.issues) },
                ]}
              />
            </>
          )}
        </SectionCard>
      )}

      {/* G14 — Title audit */}
      {ti && (ti.niche_formula_best || has(ti.formula_distribution)) && (
        <SectionCard title="✏ TITLE — Position keyword + công thức">
          {ti.niche_formula_best && <Typography variant="body2" sx={{ mb: 0.5 }}><b>Công thức tốt nhất:</b> {ti.niche_formula_best}</Typography>}
          {ti.niche_keyword_position_rule && <Typography variant="body2" sx={{ mb: 0.5 }}><b>Vị trí keyword:</b> {ti.niche_keyword_position_rule}</Typography>}
          {ti.niche_optimal_length && <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>Độ dài tối ưu: {arr(ti.niche_optimal_length)} ký tự</Typography>}
          {has(ti.formula_distribution) && (
            <DataTable
              limit={null}
              rows={ti.formula_distribution}
              columns={[
                { key: "formula", label: "Công thức" },
                { key: "count", label: "Số video", align: "right" },
                { key: "desc", label: "Cách dùng" },
              ]}
            />
          )}
        </SectionCard>
      )}

      {/* G20 — Clickbait */}
      {cb && (has(cb.violations) || cb.videos_checked) && (
        <SectionCard
          title="🚫 CLICKBAIT Penalty"
          action={<Box component="span" sx={{ fontWeight: 700, color: cb.violations_count ? "error.main" : "success.main" }}>{cb.violations_count || 0} vi phạm / {cb.videos_checked} video</Box>}
        >
          {has(cb.forbidden_words) && (
            <Box mb={has(cb.violations) ? 2 : 0}>
              <Typography variant="body2" component="span" sx={{ mr: 0.5 }}><b>Từ cấm:</b></Typography>
              <Chips items={cb.forbidden_words} color="error" />
            </Box>
          )}
          {has(cb.violations) && (
            <DataTable
              limit={null}
              rows={cb.violations}
              columns={[
                { key: "title", label: "Video" },
                { key: "words", label: "Từ vi phạm", render: (r) => arr(r.words || r.matched) },
                { key: "views", label: "Views", align: "right", render: (r) => num(r.views) },
              ]}
            />
          )}
        </SectionCard>
      )}

      {/* G15 — Thumbnail layout */}
      {tl && (tl.primary_layout || has(tl.layouts_recipe)) && (
        <SectionCard
          title="🖼 THUMBNAIL Layout per niche"
          action={tl.current_avg_ctr_pct != null ? <Box component="span" sx={{ fontWeight: 700, color: SEV[tl.status] || "text.primary" }}>CTR {tl.current_avg_ctr_pct}% · sweet {arr(tl.niche_sweet_spot)}%</Box> : null}
        >
          {tl.primary_layout && <Typography variant="body2" sx={{ mb: 1 }}><b>Layout chính:</b> {tl.primary_layout}</Typography>}
          {has(tl.layouts_recipe) && (
            <DataTable
              limit={null}
              rows={Object.entries(tl.layouts_recipe).map(([k, v]) => ({ name: k, recipe: v }))}
              columns={[
                { key: "name", label: "Layout" },
                { key: "recipe", label: "Công thức" },
              ]}
            />
          )}
          <StatGrid
            stats={[
              tl.color_palette ? { label: "Bảng màu", value: tl.color_palette } : null,
              tl.text_words_max ? { label: "Text tối đa (từ)", value: tl.text_words_max } : null,
              tl.text_size_min_px ? { label: "Text size min (px)", value: tl.text_size_min_px } : null,
              tl.face_size_pct_range ? { label: "Face size %", value: arr(tl.face_size_pct_range) } : null,
            ]}
          />
        </SectionCard>
      )}

      {/* G17 — CTR sweet spot */}
      {cs && (
        <SectionCard title="📊 CTR — Niche Sweet Spot">
          <StatGrid
            stats={[
              { label: "CTR hiện tại %", value: cs.current_avg_ctr_pct },
              { label: "CTR top5 %", value: cs.top5_avg_ctr_pct },
              { label: "Sweet spot %", value: arr(cs.niche_sweet_spot) },
              { label: "Xuất sắc ≥%", value: cs.niche_high_excellent },
              { label: "Cảnh báo <%", value: cs.niche_low_warning },
              { label: "Decay (ngày)", value: arr(cs.niche_decay_days) },
              { label: "Gap tới xuất sắc %", value: cs.gap_to_excellent_pct },
            ]}
          />
        </SectionCard>
      )}

      {/* G16 — Retention map */}
      {rm && (has(rm.prioritized_techniques) || has(rm.all_techniques)) && (
        <SectionCard
          title="📉 RETENTION — Techniques per niche"
          action={rm.current_avg_retention_pct != null ? <Box component="span" sx={{ fontWeight: 700 }}>Retention TB {rm.current_avg_retention_pct}%{rm.weakest_segment ? ` · yếu nhất: ${rm.weakest_segment}` : ""}</Box> : null}
        >
          {has(rm.prioritized_techniques) && (
            <>
              <SubHead>Ưu tiên cho đoạn yếu</SubHead>
              <Box component="ol" sx={{ pl: 2.5, m: 0 }}>
                {rm.prioritized_techniques.map((t, i) => (
                  <li key={i}><Typography variant="body2" sx={{ lineHeight: 1.6 }}>{t}</Typography></li>
                ))}
              </Box>
            </>
          )}
          {has(rm.all_techniques) && (
            <>
              <SubHead>Tất cả techniques ngách này</SubHead>
              <Box component="ul" sx={{ pl: 2.5, m: 0 }}>
                {rm.all_techniques.map((t, i) => (
                  <li key={i}><Typography variant="body2" sx={{ lineHeight: 1.6 }}>{t}</Typography></li>
                ))}
              </Box>
            </>
          )}
        </SectionCard>
      )}

      {/* G10 — Upload timing */}
      {ut && (
        <SectionCard title="⏰ UPLOAD TIMING — Best time slot">
          <StatGrid
            stats={[
              ut.niche_recommended_days ? { label: "Ngày nên đăng (ngách)", value: (ut.niche_recommended_days || []).join(", ") } : null,
              ut.niche_recommended_hours ? { label: "Giờ nên đăng (ngách)", value: (ut.niche_recommended_hours || []).map((h) => arr(h) + "h").join(", ") } : null,
              ut.niche_frequency_per_week ? { label: "Tần suất/tuần", value: arr(ut.niche_frequency_per_week) } : null,
            ]}
          />
          {has(ut.actual_best_weekdays) && (
            <>
              <SubHead>Dữ liệu thực tế kênh — ngày tốt</SubHead>
              <DataTable
                limit={null}
                rows={ut.actual_best_weekdays}
                columns={[
                  { key: "day", label: "Ngày" },
                  { key: "avg_views", label: "View TB", align: "right", render: (r) => num(r.avg_views) },
                ]}
              />
            </>
          )}
        </SectionCard>
      )}

      {/* G11 — Engagement */}
      {eg && (
        <SectionCard title="💬 ENGAGEMENT Signals">
          <DataTable
            limit={null}
            rows={[
              { m: "Like / View", now: eg.avg_like_pct, base: eg.baseline_like_pct, st: eg.status_like },
              { m: "Comment / View", now: eg.avg_comment_pct, base: eg.baseline_comment_pct, st: eg.status_comment },
            ]}
            columns={[
              { key: "m", label: "Chỉ số" },
              { key: "now", label: "Hiện tại %", align: "right", render: (r) => num(r.now) },
              { key: "base", label: "Baseline %", align: "right", render: (r) => num(r.base) },
              { key: "st", label: "Trạng thái", align: "center", render: (r) => (r.st ? <Pill label={r.st} color={PILLC[r.st] || "default"} /> : "—") },
            ]}
          />
          {has(eg.low_engagement_videos) && (
            <>
              <SubHead>Video engagement THẤP</SubHead>
              <DataTable
                limit={null}
                rows={eg.low_engagement_videos}
                columns={[
                  { key: "title", label: "Video" },
                  { key: "views", label: "Views", align: "right", render: (r) => num(r.views) },
                  { key: "like_pct", label: "Like %", align: "right", render: (r) => num(r.like_pct) },
                  { key: "comment_pct", label: "Cmt %", align: "right", render: (r) => num(r.comment_pct) },
                ]}
              />
            </>
          )}
        </SectionCard>
      )}

      {/* G12 — Caption */}
      {cap && Object.keys(cap).length > 0 && (
        <SectionCard title="🌐 CAPTION — Multi-language">
          <StatGrid stats={[
            cap.total_audience_in_top5_lang != null ? { label: "% audience top5 ngôn ngữ", value: cap.total_audience_in_top5_lang } : null,
            { label: "Auto-translate title", value: cap.auto_translate_title ? "Nên" : "Không" },
            { label: "Auto-caption", value: cap.auto_caption ? "Nên" : "Không" },
          ]} />
          {has(cap.recommended_languages) && (
            <Box mt={1}><Chips items={cap.recommended_languages.map((l) => (typeof l === "string" ? l : l.language || JSON.stringify(l)))} /></Box>
          )}
        </SectionCard>
      )}

      {/* G13 — Content gap */}
      {cg && (
        <SectionCard
          title="📂 CONTENT — Pillar coverage"
          action={<Box component="span" sx={{ fontWeight: 700 }}>{cg.pillars_covered}/{cg.pillars_total} pillar · thiếu {cg.pillars_missing}</Box>}
        >
          {has(cg.covered_detail) && (
            <DataTable
              limit={null}
              rows={cg.covered_detail}
              columns={[
                { key: "pillar", label: "Pillar đã làm" },
                { key: "video_count", label: "Số video", align: "right" },
                { key: "share_pct", label: "% gần đây", align: "right", render: (r) => (r.share_pct != null ? `${r.share_pct}%` : "—") },
              ]}
            />
          )}
          {has(cg.missing_pillars) && (<><SubHead>Pillar CHƯA làm</SubHead><Box><Chips items={cg.missing_pillars} color="warning" /></Box></>)}
          {has(cg.new_video_ideas) && (
            <>
              <SubHead>💡 Ý tưởng video mới</SubHead>
              <Box component="ul" sx={{ pl: 2.5, m: 0 }}>
                {cg.new_video_ideas.map((v, i) => (
                  <li key={i}><Typography variant="body2" sx={{ lineHeight: 1.6 }}>{typeof v === "string" ? v : `${v.pillar || ""}: ${v.template || v.idea || ""}`}</Typography></li>
                ))}
              </Box>
            </>
          )}
        </SectionCard>
      )}

      {/* G18 — Channel x Inside */}
      {cx && (cx.channel_score != null || has(cx.findings)) && (
        <SectionCard
          title="⚙ CHANNEL META × INSIDE"
          action={<Box component="span" sx={{ fontWeight: 700 }}>Score {cx.channel_score}/100 · CTR {cx.inside_ctr_pct}% · AVD {cx.inside_avd_seconds}s</Box>}
        >
          {has(cx.findings) ? <Findings items={cx.findings} /> : <Typography variant="body2" color="text.secondary">Không có cảnh báo.</Typography>}
        </SectionCard>
      )}

      {/* G19 — Competitor cross */}
      {cc && (has(cc.competitors) || has(cc.findings)) && (
        <SectionCard title="⚔ COMPETITOR × INSIDE">
          <DataTable
            limit={null}
            rows={[{ title: "★ Kênh của bạn", ...(cc.self || {}) }, ...(cc.competitors || [])]}
            columns={[
              { key: "title", label: "Kênh" },
              { key: "subs", label: "Subs", align: "right", render: (r) => num(r.subs) },
              { key: "videos_30d", label: "Video/30d", align: "right", render: (r) => num(r.videos_30d) },
              { key: "avg_view", label: "View TB", align: "right", render: (r) => num(r.avg_view) },
            ]}
          />
          {has(cc.findings) && <Box mt={1}><Findings items={cc.findings} /></Box>}
        </SectionCard>
      )}
    </>
  );
}
