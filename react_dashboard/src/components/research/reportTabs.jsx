// components/research/reportTabs.jsx
// Định nghĩa 22 tab báo cáo nghiên cứu ngách (7 nhóm A-G), render từ build_data JSON.
import { Box, Link, Typography } from "@mui/material";
import {
  DataTable,
  EmptyState,
  Pill,
  SectionCard,
  SevChip,
  StatGrid,
  TextBlock,
  num,
} from "./primitives";

// ---------- helpers ----------
const isScalar = (v) => v === null || ["string", "number", "boolean"].includes(typeof v);

const prettyKey = (k) =>
  String(k)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());

// dict scalar fields -> StatGrid
const autoStats = (obj, only = null) => {
  if (!obj || typeof obj !== "object") return [];
  const keys = only || Object.keys(obj);
  return keys
    .filter((k) => isScalar(obj[k]))
    .map((k) => ({ label: prettyKey(k), value: obj[k] }));
};

// array of objects -> DataTable (auto columns từ scalar keys của row đầu)
const AutoTable = ({ rows, maxHeight }) => {
  if (!Array.isArray(rows) || !rows.length) return <EmptyState />;
  const first = rows.find((r) => r && typeof r === "object") || {};
  const cols = Object.keys(first)
    .filter((k) => isScalar(first[k]))
    .map((k) => ({
      key: k,
      label: prettyKey(k),
      align: typeof first[k] === "number" ? "right" : "left",
    }));
  if (!cols.length) return <EmptyState />;
  return <DataTable columns={cols} rows={rows} maxHeight={maxHeight} />;
};

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
      {Array.isArray(ch.all_v) && ch.all_v.length > 0 && (
        <Box mt={2}>
          <Typography variant="subtitle2" fontWeight={700} mb={1}>
            Video ({ch.all_v.length})
          </Typography>
          <DataTable columns={videoCols} rows={ch.all_v} maxHeight={360} />
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
      const hasAny =
        (d.health || []).length ||
        Object.keys(d.health_channel || {}).length ||
        (d.health_actions || []).length;
      if (!hasAny) return <EmptyState />;
      return (
        <>
          {Object.keys(d.health_channel || {}).length > 0 && (
            <SectionCard title="Sức khoẻ kênh">
              <StatGrid stats={autoStats(d.health_channel)} />
            </SectionCard>
          )}
          {(d.health || []).length > 0 && (
            <SectionCard title="Tiêu chí video">
              <AutoTable rows={d.health} />
            </SectionCard>
          )}
          {(d.health_actions || []).length > 0 && (
            <SectionCard title="Hành động đề xuất">
              <AutoTable rows={d.health_actions} />
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
            <SectionCard title="Chi tiết">
              <AutoTable rows={f.detail} />
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
        <TextBlock text={d.strategy} />
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
            <SectionCard title="Tóm tắt kênh (Studio)" subtitle={ins.account_tag ? `Tag: ${ins.account_tag}` : ""}>
              <StatGrid stats={autoStats(ins.channel_summary)} />
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
              <Box component="ul" sx={{ pl: 2, m: 0 }}>
                {s.findings.map((f, i) => (
                  <li key={i}>
                    <Typography variant="body2">{typeof f === "string" ? f : JSON.stringify(f)}</Typography>
                  </li>
                ))}
              </Box>
            ) : (
              <EmptyState />
            )}
          </SectionCard>
          {s.traffic_playbook && (
            <SectionCard title="Traffic Playbook">
              <TextBlock text={typeof s.traffic_playbook === "string" ? s.traffic_playbook : JSON.stringify(s.traffic_playbook, null, 2)} />
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
          <DataTable columns={videoCols} rows={rows} maxHeight={560} />
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
          <DataTable columns={videoCols} rows={d.outliers} maxHeight={560} />
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
          <DataTable columns={cols} rows={rows} maxHeight={560} />
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
      if (Array.isArray(kb)) return <AutoTable rows={kb} maxHeight={560} />;
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
          <DataTable columns={cols} rows={rows} maxHeight={560} />
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
          <DataTable columns={cols} rows={rows} maxHeight={560} />
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
                maxHeight={420}
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
                maxHeight={360}
              />
            </SectionCard>
          )}
        </>
      );
    },
  },
];
