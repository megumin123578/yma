// components/research/reportTabs.jsx
// Định nghĩa 22 tab báo cáo nghiên cứu ngách (7 nhóm A-G), render từ build_data JSON.
import { Box, Link, Typography } from "@mui/material";
import {
  DataTable,
  EmptyState,
  Pill,
  PrioChip,
  SectionCard,
  SevChip,
  StatGrid,
  TextBlock,
  num,
} from "./primitives";
import Markdown from "./Markdown";

// ---------- helpers ----------
const isScalar = (v) => v === null || ["string", "number", "boolean"].includes(typeof v);

const prettyKey = (k) =>
  String(k)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());

// "2026-06-03" -> "03/06/2026"; rỗng -> "—"
const dmy = (s) => String(s || "").split("-").reverse().join("/") || "—";

// số có dấu +/- (cho delta tăng/giảm)
const sg = (v) => {
  const n = Number(v) || 0;
  return (n > 0 ? "+" : "") + num(n);
};

// dict scalar fields -> StatGrid
const autoStats = (obj, only = null, exclude = []) => {
  if (!obj || typeof obj !== "object") return [];
  const keys = (only || Object.keys(obj)).filter((k) => !exclude.includes(k));
  return keys
    .filter((k) => isScalar(obj[k]))
    .map((k) => ({ label: prettyKey(k), value: obj[k] }));
};

// array of objects -> DataTable (auto columns từ scalar keys của row đầu)
const PRIO_KEYS = new Set(["priority", "severity", "sev"]);

const AutoTable = ({ rows, limit = null }) => {
  if (!Array.isArray(rows) || !rows.length) return <EmptyState />;
  const first = rows.find((r) => r && typeof r === "object") || {};
  const cols = Object.keys(first)
    .filter((k) => isScalar(first[k]))
    .map((k) =>
      PRIO_KEYS.has(k)
        ? { key: k, label: prettyKey(k), align: "center", render: (r) => <PrioChip value={r[k]} /> }
        : { key: k, label: prettyKey(k), align: typeof first[k] === "number" ? "right" : "left" }
    );
  if (!cols.length) return <EmptyState />;
  return <DataTable columns={cols} rows={rows} limit={limit} />;
};

// C. Audit video kênh chính — mỗi video chấm 19 tiêu chí, hiện top 3 lỗi.
const SEV_SCORE_COLOR = { good: "success.main", warn: "warning.main", bad: "error.main" };

const VideoAuditCard = ({ rows }) => {
  const n = rows.length;
  const avg = Math.round(rows.reduce((s, v) => s + (v.score || 0), 0) / n);
  const goodN = rows.filter((v) => v.severity === "good").length;
  const warnN = rows.filter((v) => v.severity === "warn").length;
  const badN = rows.filter((v) => v.severity === "bad").length;
  const cols = [
    {
      key: "score",
      label: "Score",
      align: "right",
      render: (r) => (
        <Box component="span" sx={{ fontWeight: 700, color: SEV_SCORE_COLOR[r.severity] || "text.primary" }}>
          {r.score}
        </Box>
      ),
    },
    { key: "title", label: "Tiêu đề" },
    { key: "days_old", label: "Ngày", align: "right", render: (r) => `${(r.days_old || 0).toFixed(1)}d` },
    { key: "duration_seconds", label: "Độ dài", align: "right", render: (r) => `${Math.floor((r.duration_seconds || 0) / 60)}m` },
    { key: "view_count", label: "Views", align: "right", render: (r) => num(r.view_count) },
    {
      key: "fail_items",
      label: "Lỗi cần sửa (top 3)",
      render: (r) => {
        const top3 = [...(r.fail_items || [])].sort((a, b) => (b.weight || 0) - (a.weight || 0)).slice(0, 3);
        if (!top3.length) return <Typography variant="body2" color="text.secondary">(không có lỗi)</Typography>;
        return (
          <Box>
            {top3.map((f, i) => (
              <Typography key={i} variant="body2" sx={{ display: "block", lineHeight: 1.6, mb: 0.5 }}>
                <b>×</b> {f.label}: <i>{f.detail}</i>
              </Typography>
            ))}
          </Box>
        );
      },
    },
  ];
  return (
    <SectionCard
      title="Audit 10 video gần nhất (19 tiêu chí mỗi video)"
      action={
        <Box
          component="span"
          sx={{
            fontWeight: 700,
            whiteSpace: "nowrap",
            color: avg >= 70 ? "success.main" : avg >= 50 ? "warning.main" : "error.main",
          }}
        >
          Điểm TB {avg}/100
        </Box>
      }
      subtitle={
        <>
          <Box component="span" sx={{ color: "success.main", fontWeight: 600 }}>● TỐT {goodN}</Box>
          {"  ·  "}
          <Box component="span" sx={{ color: "warning.main", fontWeight: 600 }}>● CẦN CẢI THIỆN {warnN}</Box>
          {"  ·  "}
          <Box component="span" sx={{ color: "error.main", fontWeight: 600 }}>● YẾU {badN}</Box>
        </>
      }
    >
      <DataTable columns={cols} rows={rows} limit={null} />
    </SectionCard>
  );
};

// A. Audit cấp kênh — bảng tiêu chí pass/fail + điểm tổng.
const ChannelAuditCard = ({ hc }) => {
  const rows = [
    ...(hc.fail_items || []).map((x) => ({ ...x, ok: false })),
    ...(hc.pass_items || []).map((x) => ({ ...x, ok: true })),
  ];
  const cols = [
    { key: "ok", label: "Trạng thái", align: "center", render: (r) => (r.ok ? "✅" : "❌") },
    { key: "label", label: "Tiêu chí" },
    { key: "detail", label: "Chi tiết" },
    { key: "weight", label: "Trọng số", align: "right" },
  ];
  return (
    <SectionCard
      title="Audit cấp kênh"
      action={
        <Box
          component="span"
          sx={{ fontWeight: 700, whiteSpace: "nowrap", color: SEV_SCORE_COLOR[hc.severity] || "text.primary" }}
        >
          {hc.score}/100 · {hc.severity_label} ({hc.passed_count}/{hc.total_checks} pass)
        </Box>
      }
    >
      {rows.length > 0 ? (
        <DataTable columns={cols} rows={rows} limit={null} />
      ) : (
        <StatGrid stats={autoStats(hc)} />
      )}
    </SectionCard>
  );
};

// keywordtool/YT-search cells: Bid Ads (KT) %, Volume (KT), Cạnh tranh SEO YT.
// Tra cứu d.kw_enrich theo keyword (lowercase). Dùng cho các bảng từ khoá phụ.
const ktInfo = (kwEnrich, kw) => (kwEnrich || {})[(kw || "").trim().toLowerCase()] || null;
const ktCols = (kwEnrich) => [
  {
    key: "_bid",
    label: "Bid Ads (KT)",
    align: "right",
    render: (r) => {
      const e = ktInfo(kwEnrich, r.kw);
      if (!e || e.comp == null) return "—";
      const c = e.comp < 0.33 ? "success" : e.comp < 0.66 ? "warning" : "error";
      return <Pill label={`${Math.round(e.comp * 100)}%`} color={c} />;
    },
  },
  {
    key: "_vol",
    label: "Volume (KT)",
    align: "right",
    render: (r) => {
      const e = ktInfo(kwEnrich, r.kw);
      return e && e.vol != null ? num(e.vol) : "—";
    },
  },
  {
    key: "_seo",
    label: "Cạnh tranh SEO YT",
    align: "center",
    render: (r) => {
      const e = ktInfo(kwEnrich, r.kw);
      if (!e || !(e.rc > 0)) return "—";
      const lv = e.rc < 100000 ? "success" : e.rc < 1000000 ? "warning" : "error";
      const lbl = lv === "success" ? "Thấp" : lv === "warning" ? "Trung" : "Cao";
      return <Pill label={`${lbl} (${num(e.rc)})`} color={lv} />;
    },
  },
];

const videoCols = [
  {
    key: "title",
    label: "Video",
    render: (r) =>
      r.url ? (
        <Link href={r.url} target="_blank" rel="noopener" underline="hover">
          {r.title}
        </Link>
      ) : (
        r.title
      ),
  },
  { key: "ch", label: "Kênh" },
  { key: "views", label: "Views", align: "right", render: (r) => num(r.views) },
  { key: "vpd", label: "View/ngày", align: "right", render: (r) => num(Math.round(r.vpd || 0)) },
  { key: "age_days", label: "Tuổi (ngày)", align: "right" },
  { key: "eng", label: "Eng %", align: "right", render: (r) => (r.eng != null ? `${r.eng}%` : "—") },
];

const kwCols = [
  { key: "kw", label: "Từ khoá" },
  { key: "kt_vol", label: "Volume", align: "right", render: (r) => num(r.kt_vol) },
  { key: "score", label: "Score", align: "right", render: (r) => num(r.score) },
  { key: "rc", label: "Kết quả YT", align: "right", render: (r) => num(r.rc) },
  { key: "trend", label: "Trend", align: "right", render: (r) => num(r.trend) },
];

// ---------- channel block (self + competitors) ----------
const ChannelBlock = ({ ch, defaultOpen = false }) => {
  if (!ch) return null;
  if (!ch.has) {
    return (
      <SectionCard title={ch.title || "Kênh"}>
        <EmptyState text="Kênh này chưa có dữ liệu thu thập (chỉ theo dõi qua Inside hoặc chưa monitor)." />
      </SectionCard>
    );
  }
  const sb = ch.sb || {};
  const delta = ch.delta || {};
  return (
    <SectionCard
      title={ch.title}
      subtitle={ch.url}
      action={ch.auto_added ? <Pill label="Mới kết nạp" color="info" /> : null}
    >
      <StatGrid
        stats={[
          { label: "Subscribers", value: ch.subs },
          { label: "Tổng views", value: ch.total_views },
          { label: "Số video kênh", value: ch.ch_vcount },
          { label: "Video phân tích", value: ch.vcount },
          { label: "SEO score", value: ch.seo },
          { label: "View trung vị", value: ch.median_v },
          { label: "Eng TB %", value: ch.eng_avg },
          sb.subs_g != null ? { label: `Δ Subs (${sb.days || "?"}d)`, value: sb.subs_g } : null,
          sb.views_g != null ? { label: `Δ Views (${sb.days || "?"}d)`, value: sb.views_g } : null,
          delta.new_vid != null ? { label: "Video mới kỳ này", value: delta.new_vid } : null,
        ]}
      />
      {ch.posting && (
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.25 }}>
          ⏰ {ch.posting}
        </Typography>
      )}
      {delta.has && (
        <Box mt={2}>
          <Typography variant="subtitle2" fontWeight={700} mb={0.5}>
            Thay đổi so với kỳ trước{delta.prev ? ` (${delta.prev})` : ""}
          </Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.6 }}>
            Người đăng ký: <b>{sg(delta.sub_d)}</b> ({sg(delta.sub_pct)}%)
            {delta.vc_d ? (
              <>
                {" "}· Số video kênh: <b>{sg(delta.vc_d)}</b>
              </>
            ) : null}
            {delta.ch_up ? (
              <>
                {" "}· Kênh vừa đăng <b>{num(delta.ch_up)}</b> video mới
              </>
            ) : null}
            {delta.new_vid != null ? <> · Video mới trong ngành: {num(delta.new_vid)}</> : null}
          </Typography>
          {Array.isArray(delta.new_kw) && delta.new_kw.length > 0 && (
            <Typography variant="body2" sx={{ mt: 0.5 }}>
              <b>Từ khoá mới của ngành:</b> {delta.new_kw.join(", ")}
            </Typography>
          )}
          {Array.isArray(delta.trend_kw) && delta.trend_kw.length > 0 && (
            <Box mt={0.75}>
              <Typography variant="body2" component="span" sx={{ mr: 0.5 }}>
                <b>Từ khoá đang nóng lên:</b>
              </Typography>
              {delta.trend_kw.map((t, i) => (
                <Pill key={i} label={`${t.kw} (${sg(t.pct)}%)`} color="warning" />
              ))}
            </Box>
          )}
        </Box>
      )}
      {sb.days > 0 && (
        <Box mt={2}>
          <Typography variant="subtitle2" fontWeight={700} mb={0.5}>
            {sb.source === "inside_api" ? "Inside YouTube Analytics" : "Social Blade"} — {sb.days} ngày gần nhất
          </Typography>
          <Typography variant="body2" sx={{ mb: 1 }}>
            Người đăng ký: <b>{sg(sb.subs_g)}</b> (TB {sg(sb.avg_sub)}/ngày) · Lượt xem:{" "}
            <b>{sg(sb.views_g)}</b> (TB {sg(sb.avg_view)}/ngày)
          </Typography>
          {Array.isArray(sb.daily) && sb.daily.length > 0 && (
            <DataTable
              limit={null}
              rows={sb.daily}
              columns={
                sb.source === "inside_api"
                  ? [
                      { key: "d", label: "Ngày" },
                      { key: "sc", label: "ĐK +/-", align: "right", render: (r) => sg(r.sc) },
                      { key: "vc", label: "Xem +/-", align: "right", render: (r) => sg(r.vc) },
                    ]
                  : [
                      { key: "d", label: "Ngày" },
                      { key: "s", label: "Người ĐK", align: "right", render: (r) => num(r.s) },
                      { key: "sc", label: "ĐK +/-", align: "right", render: (r) => sg(r.sc) },
                      { key: "v", label: "Tổng xem", align: "right", render: (r) => num(r.v) },
                      { key: "vc", label: "Xem +/-", align: "right", render: (r) => sg(r.vc) },
                    ]
              }
            />
          )}
        </Box>
      )}
      {Array.isArray(ch.all_v) && ch.all_v.length > 0 && (
        <Box mt={2}>
          <Typography variant="subtitle2" fontWeight={700} mb={1}>
            Video ({ch.all_v.length})
          </Typography>
          <DataTable columns={videoCols} rows={ch.all_v} />
        </Box>
      )}
      {Array.isArray(ch.top_tags) && ch.top_tags.length > 0 && (
        <Box mt={2}>
          <Typography variant="subtitle2" fontWeight={700} mb={1}>
            Thẻ tag hay dùng
          </Typography>
          <Box>
            {ch.top_tags.slice(0, 20).map((t, i) => (
              <Pill key={i} label={`${t.tag} (${t.n})`} />
            ))}
          </Box>
        </Box>
      )}
      {ch.ai && String(ch.ai).trim() && (
        <Box mt={2}>
          <Typography variant="subtitle2" fontWeight={700} mb={1}>
            Phân tích AI
          </Typography>
          <TextBlock text={ch.ai} />
        </Box>
      )}
    </SectionCard>
  );
};

// ---------- tab definitions ----------
// group: nhãn nhóm; id, label, render(d)
export const TAB_GROUPS = [
  { key: "A", label: "Tổng quan & Sức khoẻ" },
  { key: "B", label: "Hiệu quả tổng thể" },
  { key: "C", label: "Khán giả" },
  { key: "D", label: "Traffic & CTR" },
  { key: "E", label: "Nội dung" },
  { key: "F", label: "Từ khoá & SEO" },
  { key: "G", label: "Đối thủ & Ngách" },
];

export const TABS = [
  // ===== A. Tổng quan & Sức khoẻ =====
  {
    id: "health",
    group: "A",
    label: "🩺 Health Check",
    render: (d) => {
      const hk = d.health_keywords || {};
      const hasKw = Object.keys(hk).length > 0;
      const hasAny =
        (d.health || []).length ||
        Object.keys(d.health_channel || {}).length ||
        (d.health_actions || []).length ||
        hasKw;
      if (!hasAny) return <EmptyState />;
      return (
        <>
          {Object.keys(d.health_channel || {}).length > 0 && (
            <ChannelAuditCard hc={d.health_channel} />
          )}
          {hasKw && (
            <SectionCard
              title="Chiến lược từ khoá — Đồng bộ kênh vs ngách"
              action={
                hk.theme_consistency != null ? (
                  <Box
                    component="span"
                    sx={{
                      fontWeight: 700,
                      whiteSpace: "nowrap",
                      color:
                        hk.theme_consistency >= 70
                          ? "success.main"
                          : hk.theme_consistency >= 50
                          ? "warning.main"
                          : "error.main",
                    }}
                  >
                    Theme consistency {hk.theme_consistency}% (mục tiêu ≥70%)
                  </Box>
                ) : null
              }
            >
              {Array.isArray(hk.self_keywords) && hk.self_keywords.length > 0 && (
                <Box mb={2}>
                  <Typography variant="subtitle2" fontWeight={700} mb={1}>Top từ khoá kênh</Typography>
                  <DataTable
                    columns={[
                      { key: "kw", label: "Từ khoá" },
                      { key: "score", label: "SEO Score", align: "right", render: (r) => (r.score != null ? r.score.toFixed(1) : "—") },
                      { key: "in_about", label: "Trong About?", align: "center", render: (r) => (r.in_about ? "✅" : "❌") },
                      { key: "in_video_pct", label: "% Video dùng", align: "right", render: (r) => `${Math.round(r.in_video_pct || 0)}%` },
                      ...ktCols(d.kw_enrich),
                    ]}
                    rows={hk.self_keywords}
                  />
                </Box>
              )}
              {Array.isArray(hk.niche_keywords) && hk.niche_keywords.length > 0 && (
                <Box mb={2}>
                  <Typography variant="subtitle2" fontWeight={700} mb={1}>Top từ khoá ngách (từ đối thủ)</Typography>
                  <DataTable
                    columns={[
                      { key: "kw", label: "Từ khoá ngách" },
                      { key: "freq_in_niche", label: "Số đối thủ dùng", align: "right" },
                      { key: "in_self", label: "Kênh dùng?", align: "center", render: (r) => (r.in_self ? "✅" : "❌") },
                      ...ktCols(d.kw_enrich),
                    ]}
                    rows={hk.niche_keywords}
                  />
                </Box>
              )}
              {Array.isArray(hk.gaps) && hk.gaps.length > 0 && (
                <Box mb={2}>
                  <Typography variant="subtitle2" fontWeight={700} mb={1}>🎯 GAP — keyword ngách mạnh kênh chưa dùng</Typography>
                  <Box>{hk.gaps.map((g, i) => <Pill key={i} label={g} color="warning" />)}</Box>
                </Box>
              )}
              {Array.isArray(hk.overused) && hk.overused.length > 0 && (
                <Box mb={2}>
                  <Typography variant="subtitle2" fontWeight={700} mb={1}>⚠ Keyword kênh không khớp ngách</Typography>
                  <Box>{hk.overused.map((o, i) => <Pill key={i} label={o} />)}</Box>
                </Box>
              )}
              {Array.isArray(hk.actions) && hk.actions.length > 0 && (
                <Box>
                  <Typography variant="subtitle2" fontWeight={700} mb={1}>Hành động từ phân tích từ khoá</Typography>
                  <AutoTable rows={hk.actions} limit={null} />
                </Box>
              )}
            </SectionCard>
          )}
          {(d.health || []).length > 0 && <VideoAuditCard rows={d.health} />}
          {(d.health_actions || []).length > 0 && (
            <SectionCard title="Hành động đề xuất">
              <AutoTable rows={d.health_actions} limit={null} />
            </SectionCard>
          )}
        </>
      );
    },
  },
  {
    id: "ai_feedback",
    group: "A",
    label: "Phản hồi AI",
    render: (d) => {
      const f = d.ai_feedback;
      if (!f || !Object.keys(f).length) return <EmptyState />;
      return (
        <>
          <SectionCard title="Đối chiếu ý tưởng AI kỳ trước">
            <StatGrid stats={autoStats(f, ["ideas_total", "ideas_done", "ideas_pending", "success_rate", "avg_perf_ratio"])} />
          </SectionCard>
          {Array.isArray(f.detail) && f.detail.length > 0 && (
            <SectionCard title="Chi tiết ý tưởng">
              <DataTable
                limit={null}
                rows={f.detail}
                columns={[
                  { key: "idea", label: "Ý tưởng" },
                  { key: "date", label: "Ngày đề xuất", align: "right", render: (r) => dmy(r.date) },
                  { key: "status", label: "Trạng thái", align: "center", render: (r) => (r.status === "done" ? "✅" : "⏳") },
                  { key: "video", label: "Video đã đăng", render: (r) => r.video || "—" },
                  { key: "video_pub", label: "Ngày đăng", align: "right", render: (r) => (r.video_pub ? dmy(r.video_pub) : "—") },
                  { key: "views", label: "View", align: "right", render: (r) => (r.views != null ? num(r.views) : "—") },
                  {
                    key: "ratio",
                    label: "Hiệu suất",
                    align: "right",
                    render: (r) =>
                      r.ratio != null ? (
                        <Box component="span" sx={{ fontWeight: 700, color: r.ratio >= 1 ? "success.main" : "warning.main" }}>
                          {r.ratio}×
                        </Box>
                      ) : (
                        "—"
                      ),
                  },
                ]}
              />
            </SectionCard>
          )}
        </>
      );
    },
  },
  {
    id: "strategy",
    group: "A",
    label: "Chiến lược AI",
    render: (d) => (
      <SectionCard title="Cập nhật chiến lược ngách" subtitle={d.niche_detected ? `Ngách: ${d.niche_detected}` : ""}>
        <Markdown text={d.strategy} />
      </SectionCard>
    ),
  },

  // ===== B. Hiệu quả tổng thể =====
  {
    id: "self",
    group: "B",
    label: "Kênh chính",
    render: (d) => <ChannelBlock ch={d.self} defaultOpen />,
  },
  {
    id: "inside_summary",
    group: "B",
    label: "📊 Inside: Tóm tắt",
    render: (d) => {
      const ins = d.inside;
      if (!ins || !Object.keys(ins).length) return <EmptyState text="Kênh chưa có dữ liệu Inside (Analytics API)." />;
      return (
        <>
          {ins.channel_summary && (
            <SectionCard title="Tóm tắt kênh (Studio)">
              <StatGrid stats={autoStats(ins.channel_summary, null, ["account_tag", "has_data"])} />
            </SectionCard>
          )}
          {Array.isArray(ins.retention_top) && ins.retention_top.length > 0 && (
            <SectionCard title="Top video theo AVD (retention)">
              <AutoTable rows={ins.retention_top} />
            </SectionCard>
          )}
        </>
      );
    },
  },
  {
    id: "inside_synthesis",
    group: "B",
    label: "🧠 Inside × SEO Synthesis",
    render: (d) => {
      const s = d.inside_synthesis;
      if (!s || !Object.keys(s).length) return <EmptyState />;
      return (
        <>
          <SectionCard title={s.niche_name || "Synthesis"} subtitle={s.niche_key}>
            {Array.isArray(s.findings) && s.findings.length > 0 ? (
              s.findings.map((f, i) => {
                if (typeof f === "string")
                  return (
                    <Typography key={i} variant="body2" sx={{ mb: 1, lineHeight: 1.6 }}>
                      {f}
                    </Typography>
                  );
                const c = SEV_SCORE_COLOR[f.severity] || "text.secondary";
                return (
                  <Box key={i} sx={{ borderLeft: "3px solid", borderColor: c, pl: 1.5, py: 0.5, mb: 1.5 }}>
                    <Typography variant="subtitle2" fontWeight={700} sx={{ color: c }}>
                      {f.finding}
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
              })
            ) : (
              <EmptyState />
            )}
          </SectionCard>
          {Array.isArray(s.traffic_playbook) && s.traffic_playbook.length > 0 && (
            <SectionCard title="Traffic Playbook">
              <DataTable
                limit={null}
                rows={s.traffic_playbook}
                columns={[
                  { key: "name", label: "Nguồn", render: (r) => r.name || r.source || "—" },
                  { key: "share_pct", label: "Tỷ lệ", align: "right", render: (r) => (r.share_pct != null ? `${r.share_pct}%` : "—") },
                  { key: "views", label: "Views", align: "right", render: (r) => num(r.views) },
                  { key: "benchmark", label: "Benchmark", align: "center", render: (r) => r.benchmark || "—" },
                  {
                    key: "status",
                    label: "Trạng thái",
                    align: "center",
                    render: (r) => {
                      const st = String(r.status || "");
                      const col =
                        st === "HIGH" ? "warning" : st === "LOW" ? "error" : st === "OK" || st === "GOOD" ? "success" : "default";
                      return st ? <Pill label={st} color={col} /> : "—";
                    },
                  },
                  {
                    key: "actions",
                    label: "Hành động",
                    render: (r) =>
                      Array.isArray(r.actions) && r.actions.length > 0 ? (
                        <Box component="ul" sx={{ pl: 2, m: 0 }}>
                          {r.actions.map((a, i) => (
                            <li key={i}>
                              <Typography variant="body2" sx={{ lineHeight: 1.5 }}>
                                {a}
                              </Typography>
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
        </>
      );
    },
  },

  // ===== C. Khán giả =====
  {
    id: "inside_audience",
    group: "C",
    label: "👥 Inside: Audience",
    render: (d) => {
      const ins = d.inside || {};
      const aud = ins.audience_full;
      if (!aud || !Object.keys(aud).length) return <EmptyState text="Chưa có dữ liệu Audience (Inside)." />;
      const blocks = Object.entries(aud).filter(([, v]) => Array.isArray(v) && v.length);
      if (!blocks.length) return <StatGrid stats={autoStats(aud)} />;
      return blocks.map(([k, v]) => (
        <SectionCard key={k} title={prettyKey(k)}>
          <AutoTable rows={v} />
        </SectionCard>
      ));
    },
  },
  {
    id: "audience_insight",
    group: "C",
    label: "💬 Audience insight",
    render: (d) => {
      const ci = d.comment_intel;
      if (ci && Object.keys(ci).length) return <TextBlock text={typeof ci === "string" ? ci : JSON.stringify(ci, null, 2)} />;
      const c = d.comments;
      if (c && Object.keys(c).length) {
        return Object.entries(c).map(([k, v]) => (
          <SectionCard key={k} title={prettyKey(k)}>
            {Array.isArray(v) ? <AutoTable rows={v} /> : <TextBlock text={String(v)} />}
          </SectionCard>
        ));
      }
      return <EmptyState text="Chưa có phân tích bình luận (tính năng tuỳ chọn)." />;
    },
  },
  {
    id: "inside_retention",
    group: "C",
    label: "📉 Inside: Retention",
    render: (d) => {
      const ins = d.inside || {};
      const rows = ins.retention_top || ins.retention || [];
      if (!rows.length) return <EmptyState text="Chưa có dữ liệu retention (Inside)." />;
      return (
        <SectionCard title="Đường giữ chân (AVD) theo video">
          <AutoTable rows={rows} />
        </SectionCard>
      );
    },
  },

  // ===== D. Traffic & CTR =====
  {
    id: "inside_traffic",
    group: "D",
    label: "🚦 Inside: Traffic",
    render: (d) => {
      const ins = d.inside || {};
      const th = ins.traffic_health;
      const tt = ins.traffic_trend;
      if (!th && !tt) return <EmptyState text="Chưa có dữ liệu traffic (Inside)." />;
      return (
        <>
          {th && (
            <SectionCard title="Sức khoẻ nguồn traffic">
              {Array.isArray(th) ? <AutoTable rows={th} /> : <StatGrid stats={autoStats(th)} />}
            </SectionCard>
          )}
          {tt && (
            <SectionCard title="Xu hướng traffic">
              {Array.isArray(tt) ? <AutoTable rows={tt} /> : <StatGrid stats={autoStats(tt)} />}
            </SectionCard>
          )}
        </>
      );
    },
  },
  {
    id: "thumbnail_ctr",
    group: "D",
    label: "🖼 Inside: Thumbnail CTR",
    render: (d) => {
      const ins = d.inside || {};
      const top = ins.thumbnail_ctr_top || [];
      const worst = ins.thumbnail_ctr_worst || [];
      if (!top.length && !worst.length) return <EmptyState text="Chưa có dữ liệu Thumbnail CTR (Inside)." />;
      return (
        <>
          {top.length > 0 && (
            <SectionCard title="CTR cao nhất">
              <AutoTable rows={top} />
            </SectionCard>
          )}
          {worst.length > 0 && (
            <SectionCard title="CTR thấp nhất">
              <AutoTable rows={worst} />
            </SectionCard>
          )}
        </>
      );
    },
  },
  {
    id: "thumb_vision",
    group: "D",
    label: "🤖 AI Vision thumbnail",
    render: (d) => {
      const s = d.thumb_vision_summary;
      const det = d.thumb_vision_detail;
      if (!s && !det) return <EmptyState text="Chưa bật AI Vision thumbnail (tuỳ chọn)." />;
      return (
        <>
          {s && (
            <SectionCard title="Tóm tắt Vision">
              {typeof s === "string" ? <TextBlock text={s} /> : <StatGrid stats={autoStats(s)} />}
            </SectionCard>
          )}
          {Array.isArray(det) && det.length > 0 && (
            <SectionCard title="Chi tiết theo thumbnail">
              <AutoTable rows={det} />
            </SectionCard>
          )}
        </>
      );
    },
  },
  {
    id: "predict_posting",
    group: "D",
    label: "🔮 Dự đoán + ⏰ Giờ post",
    render: (d) => {
      const vp = d.viral_predictor;
      const pv = d.posting_v2;
      const hasVp = vp && vp.predictions && vp.predictions.length;
      const hasPv = pv && !pv.error && Object.keys(pv).length;
      if (!hasVp && !hasPv) return <EmptyState text="Chưa đủ dữ liệu dự đoán / giờ đăng (cần data kênh chính)." />;
      return (
        <>
          {hasVp && (
            <SectionCard title="Dự đoán viral" subtitle={`R²=${vp.model_r_squared} · n=${vp.model_n_samples}`}>
              <AutoTable rows={vp.predictions} />
            </SectionCard>
          )}
          {hasPv && (
            <SectionCard title="Giờ đăng tối ưu (TZ-aware)">
              {Array.isArray(pv) ? <AutoTable rows={pv} /> : <StatGrid stats={autoStats(pv)} />}
            </SectionCard>
          )}
        </>
      );
    },
  },

  // ===== E. Nội dung =====
  {
    id: "videos_by_kw",
    group: "E",
    label: "Video theo từ khoá",
    render: (d) => {
      const self = d.self || {};
      const rows = self.all_v || [];
      if (!rows.length) return <EmptyState text="Kênh chính chưa có video thu thập." />;
      return (
        <SectionCard title="Video kênh chính">
          <DataTable columns={videoCols} rows={rows} />
        </SectionCard>
      );
    },
  },
  {
    id: "outliers",
    group: "E",
    label: "Video đột biến",
    render: (d) => {
      if (!d.outliers?.length) return <EmptyState text="Không có video đột biến trong kỳ." />;
      return (
        <SectionCard title={`Video đột biến (${d.outliers.length})`} subtitle="Vượt ≥3 lần view trung vị, đăng ≤7 ngày">
          <DataTable columns={videoCols} rows={d.outliers} />
        </SectionCard>
      );
    },
  },
  {
    id: "ab_rescue",
    group: "E",
    label: "💡 Cứu video flop",
    render: (d) => {
      if (!d.ab_rescue?.length) return <EmptyState text="Không có video flop cần cứu (cần data kênh chính)." />;
      return (
        <SectionCard title="Đề xuất cứu video flop">
          <AutoTable rows={d.ab_rescue} />
        </SectionCard>
      );
    },
  },

  // ===== F. Từ khoá & SEO =====
  {
    id: "keywords",
    group: "F",
    label: "Từ khoá",
    render: (d) => {
      const enrich = d.kw_enrich || {};
      const rows = Object.entries(enrich).map(([kw, v]) => ({ kw, ...(v || {}) }));
      if (!rows.length) return <EmptyState text="Chưa có từ khoá enrich." />;
      const cols = [
        { key: "kw", label: "Từ khoá" },
        { key: "vol", label: "Volume (KT)", align: "right", render: (r) => num(r.vol) },
        { key: "comp", label: "Cạnh tranh", align: "right", render: (r) => num(r.comp) },
        { key: "rc", label: "Kết quả YT", align: "right", render: (r) => num(r.rc) },
      ];
      return (
        <SectionCard title={`Từ khoá ngách (${rows.length})`}>
          <DataTable columns={cols} rows={rows} />
        </SectionCard>
      );
    },
  },
  {
    id: "title_pattern",
    group: "F",
    label: "Tiêu đề mẫu",
    render: (d) => {
      const rows = d.title_patterns || [];
      if (!rows.length) return <EmptyState text="Chưa đủ video kênh chính để rút công thức tiêu đề." />;
      const cols = [
        { key: "feat", label: "Đặc trưng" },
        { key: "n", label: "Số video", align: "right" },
        { key: "med_with", label: "Median có", align: "right", render: (r) => num(r.med_with) },
        { key: "med_without", label: "Median không", align: "right", render: (r) => num(r.med_without) },
        { key: "lift", label: "Lift", align: "right", render: (r) => (r.lift != null ? `${r.lift}x` : "—") },
      ];
      return (
        <SectionCard title="Công thức tiêu đề (data-driven)" subtitle={d.title_n ? `${d.title_n} video phân tích` : ""}>
          <DataTable columns={cols} rows={rows} />
        </SectionCard>
      );
    },
  },
  {
    id: "kw_bank",
    group: "F",
    label: "📚 Kho từ khoá",
    render: (d) => {
      const kb = d.kw_bank;
      if (!kb) return <EmptyState text="Kênh chưa harvest keywordtool." />;
      if (Array.isArray(kb)) return <AutoTable rows={kb} />;
      return <StatGrid stats={autoStats(kb)} />;
    },
  },
  {
    id: "kw_history",
    group: "F",
    label: "📈 Lịch sử KT",
    render: (d) => {
      const h = d.kw_history;
      if (!h || !h.snapshot_count) return <EmptyState text="Chưa có lịch sử kho từ khoá." />;
      return (
        <>
          <SectionCard title="Tổng quan" subtitle={`${h.snapshot_count} snapshot`}>
            <StatGrid stats={autoStats(h, ["snapshot_count"])} />
          </SectionCard>
          {Array.isArray(h.diff_history) && h.diff_history.length > 0 && (
            <SectionCard title="Biến động (NEW / LOST / CHANGED)">
              <AutoTable rows={h.diff_history} />
            </SectionCard>
          )}
        </>
      );
    },
  },
  {
    id: "seo_best",
    group: "F",
    label: "📚 SEO Best Practice",
    render: (d) => {
      const self = d.self || {};
      const comps = self.seo_comps || [];
      if (!comps.length) return <EmptyState text="Chưa có dữ liệu SEO components của kênh chính." />;
      const cols = [
        { key: "name", label: "Thành phần" },
        { key: "avg", label: "TB", align: "right", render: (r) => num(r.avg) },
        { key: "max", label: "Max", align: "right", render: (r) => num(r.max) },
      ];
      return (
        <SectionCard title="SEO components kênh chính" subtitle={self.seo != null ? `SEO score: ${self.seo}` : ""}>
          <DataTable columns={cols} rows={comps} />
        </SectionCard>
      );
    },
  },

  // ===== G. Đối thủ & Ngách =====
  {
    id: "competitors",
    group: "G",
    label: "Đối thủ",
    render: (d) => {
      const comps = d.competitors || [];
      if (!comps.length) return <EmptyState text="Chưa có đối thủ." />;
      return (
        <>
          {(d.sb_compare || []).length > 0 && (
            <SectionCard title="So sánh tăng trưởng (SocialBlade)">
              <DataTable
                columns={[
                  { key: "title", label: "Kênh", render: (r) => (r.is_self ? `★ ${r.title}` : r.title) },
                  { key: "subs", label: "Subs", align: "right", render: (r) => num(r.subs) },
                  { key: "subs_g", label: "Δ Subs", align: "right", render: (r) => num(r.subs_g) },
                  { key: "views_g", label: "Δ Views", align: "right", render: (r) => num(r.views_g) },
                  { key: "avg_sub", label: "Subs/ngày", align: "right", render: (r) => num(r.avg_sub) },
                ]}
                rows={d.sb_compare}
              />
            </SectionCard>
          )}
          {comps.map((c, i) => (
            <ChannelBlock key={i} ch={c} />
          ))}
        </>
      );
    },
  },
  {
    id: "competitive_gaps",
    group: "G",
    label: "Khoảng trống đối thủ",
    render: (d) => {
      const rows = d.competitive_gaps || [];
      if (!rows.length) return <EmptyState text="Không phát hiện khoảng trống." />;
      const cols = [
        { key: "keyword", label: "Từ khoá" },
        { key: "n_competitors", label: "Số đối thủ", align: "right" },
        { key: "competitor_video_views_median", label: "View trung vị", align: "right", render: (r) => num(r.competitor_video_views_median) },
        { key: "competitor_top_video_title", label: "Video top đối thủ" },
        { key: "competitor_top_video_views", label: "View top", align: "right", render: (r) => num(r.competitor_top_video_views) },
      ];
      return (
        <SectionCard title={`Khoảng trống nội dung (${rows.length})`} subtitle="Từ khoá đối thủ ăn mà kênh chính chưa khai thác">
          <DataTable columns={cols} rows={rows} />
        </SectionCard>
      );
    },
  },
  {
    id: "topic_clusters",
    group: "G",
    label: "Cụm chủ đề",
    render: (d) => {
      const rows = d.topic_clusters || [];
      if (!rows.length) return <EmptyState />;
      const cols = [
        { key: "cluster", label: "Cụm" },
        { key: "n_kw", label: "Từ khoá", align: "right" },
        { key: "n_videos", label: "Video", align: "right" },
        { key: "view_median", label: "View trung vị", align: "right", render: (r) => num(r.view_median) },
        { key: "view_max", label: "View max", align: "right", render: (r) => num(r.view_max) },
        { key: "top_video_title", label: "Video top" },
        { key: "is_self_active", label: "Kênh chính có?", align: "center", render: (r) => (r.is_self_active ? "✓" : "—") },
      ];
      return (
        <SectionCard title={`Bản đồ cụm chủ đề ngách (${rows.length})`}>
          <DataTable columns={cols} rows={rows} />
        </SectionCard>
      );
    },
  },
  {
    id: "events",
    group: "G",
    label: "Diễn biến & Sự kiện",
    render: (d) => {
      const rows = d.events || [];
      const newc = d.new_comp || [];
      return (
        <>
          {rows.length > 0 ? (
            <SectionCard title={`Sự kiện đáng chú ý (${rows.length})`}>
              <DataTable
                columns={[
                  { key: "date", label: "Ngày" },
                  { key: "sev", label: "Mức", render: (r) => <SevChip sev={r.sev} /> },
                  { key: "title", label: "Sự kiện" },
                ]}
                rows={rows}
              />
            </SectionCard>
          ) : (
            <EmptyState text="Không có sự kiện trong kỳ." />
          )}
          {newc.length > 0 && (
            <SectionCard title={`Đối thủ mới phát hiện (${newc.length})`}>
              <DataTable
                columns={[
                  {
                    key: "title",
                    label: "Kênh",
                    render: (r) =>
                      r.url ? (
                        <Link href={r.url} target="_blank" rel="noopener" underline="hover">
                          {r.title}
                        </Link>
                      ) : (
                        r.title
                      ),
                  },
                  { key: "subs", label: "Subs", align: "right", render: (r) => num(r.subs) },
                  { key: "total_views", label: "Tổng views", align: "right", render: (r) => num(r.total_views) },
                  { key: "vcount", label: "Video", align: "right", render: (r) => num(r.vcount) },
                ]}
                rows={newc}
              />
            </SectionCard>
          )}
        </>
      );
    },
  },
];
