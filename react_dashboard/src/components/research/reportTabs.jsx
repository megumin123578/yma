// components/research/reportTabs.jsx
// Định nghĩa 22 tab báo cáo nghiên cứu ngách (7 nhóm A-G), render từ build_data JSON.
import { useEffect, useRef, useState } from "react";
import { Box, Button, CircularProgress, FormControl, Link, MenuItem, Select, Typography } from "@mui/material";
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
import SeoBestPractice from "./SeoBestPractice";
import { getCommentMineStatus, mineComments } from "../../services/researchService";

// Nút cào bình luận kênh chính (chạy nền) + poll trạng thái; xong thì reload report.
const CommentMineButton = ({ wid, onDone }) => {
  const [mining, setMining] = useState(false);
  const [msg, setMsg] = useState("");
  const pollRef = useRef(null);

  const stop = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const poll = () => {
    stop();
    pollRef.current = setInterval(async () => {
      try {
        const r = await getCommentMineStatus(wid);
        if (!r?.mining) {
          stop();
          setMining(false);
          setMsg(
            r?.last?.error
              ? `Lỗi: ${r.last.error}`
              : `Đã cào ${r?.last?.new_comments ?? 0} bình luận mới.`
          );
          onDone?.();
        }
      } catch {
        // lỗi tạm thời → tiếp tục poll
      }
    }, 4000);
  };

  useEffect(() => {
    let alive = true;
    getCommentMineStatus(wid)
      .then((r) => {
        if (alive && r?.mining) {
          setMining(true);
          poll();
        }
      })
      .catch(() => {});
    return () => {
      alive = false;
      stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wid]);

  const run = async () => {
    setMsg("");
    try {
      await mineComments(wid);
      setMining(true);
      poll();
    } catch (e) {
      setMsg(e?.response?.data?.detail || e.message);
    }
  };

  return (
    <Box display="flex" alignItems="center" gap={1} mb={2} flexWrap="wrap">
      <Button
        size="small"
        variant="contained"
        onClick={run}
        disabled={mining}
        startIcon={mining ? <CircularProgress size={14} color="inherit" /> : null}
      >
        {mining ? "Đang cào bình luận…" : "Cào bình luận"}
      </Button>
      {msg && (
        <Typography variant="caption" color="text.secondary">
          {msg}
        </Typography>
      )}
    </Box>
  );
};

const AudienceInsight = ({ d, ctx }) => {
  const ci = d.comment_intel;
  const c = d.comments;
  const hasCi =
    ci && (typeof ci === "string" || (typeof ci === "object" && Object.keys(ci).length && !ci.error));
  const hasComments = c && Object.keys(c).length;
  return (
    <>
      {ctx?.wid && <CommentMineButton wid={ctx.wid} onDone={ctx.reload} />}
      {hasCi ? (
        <TextBlock text={typeof ci === "string" ? ci : JSON.stringify(ci, null, 2)} />
      ) : hasComments ? (
        Object.entries(c).map(([k, v]) => (
          <SectionCard key={k} title={prettyKey(k)}>
            {Array.isArray(v) ? <AutoTable rows={v} /> : <TextBlock text={String(v)} />}
          </SectionCard>
        ))
      ) : (
        <EmptyState text="Chưa có dữ liệu bình luận — bấm “Cào bình luận” để thu thập." />
      )}
    </>
  );
};
import InsideSynthesis from "./InsideSynthesis";

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
    key: "thumb",
    label: "Ảnh",
    render: (r) =>
      r.vid ? (
        <Box
          component="a"
          href={r.url || `https://www.youtube.com/watch?v=${r.vid}`}
          target="_blank"
          rel="noopener"
          sx={{ display: "block", lineHeight: 0 }}
        >
          <Box
            component="img"
            src={`https://i.ytimg.com/vi/${r.vid}/mqdefault.jpg`}
            alt=""
            loading="lazy"
            sx={{ width: 96, height: 54, objectFit: "cover", borderRadius: 1, display: "block" }}
          />
        </Box>
      ) : (
        "—"
      ),
  },
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
const ChannelBlock = ({ ch, defaultOpen = false, showUrl = true }) => {
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
      subtitle={showUrl ? ch.url : ""}
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
                      { key: "d", label: "Ngày", render: (r) => dmy(r.d) },
                      { key: "sc", label: "ĐK +/-", align: "right", render: (r) => sg(r.sc) },
                      { key: "vc", label: "Xem +/-", align: "right", render: (r) => sg(r.vc) },
                    ]
                  : [
                      { key: "d", label: "Ngày", render: (r) => dmy(r.d) },
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
      {Array.isArray(ch.clusters) && ch.clusters.length > 0 && (
        <Box mt={2}>
          <Typography variant="subtitle2" fontWeight={700} mb={1}>
            Phân cụm nội dung — format nào hiệu quả
          </Typography>
          <DataTable
            limit={null}
            rows={ch.clusters}
            columns={[
              { key: "label", label: "Cụm" },
              { key: "n", label: "Số video", align: "right" },
              { key: "avg", label: "View TB", align: "right", render: (r) => num(r.avg) },
            ]}
          />
        </Box>
      )}
      {Array.isArray(ch.new_v) && ch.new_v.length > 0 && (
        <Box mt={2}>
          <Typography variant="subtitle2" fontWeight={700} mb={1}>
            Video vừa đăng (mới từ kỳ trước)
          </Typography>
          <DataTable columns={videoCols} rows={ch.new_v} limit={null} />
        </Box>
      )}
      {Array.isArray(ch.all_v) && ch.all_v.length > 0 && (
        <Box mt={2}>
          <Typography variant="subtitle2" fontWeight={700} mb={1}>
            Video của kênh ({ch.all_v.length})
          </Typography>
          <DataTable columns={videoCols} rows={ch.all_v} limit={null} />
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
      {Array.isArray(ch.seo_comps) && ch.seo_comps.length > 0 && (
        <Box mt={2}>
          <Typography variant="subtitle2" fontWeight={700} mb={1}>
            Phân tích thẻ tag & SEO
          </Typography>
          <DataTable
            limit={null}
            rows={ch.seo_comps}
            columns={[
              { key: "name", label: "Thành phần" },
              { key: "avg", label: "TB", align: "right", render: (r) => num(r.avg) },
              { key: "max", label: "Tối đa", align: "right", render: (r) => num(r.max) },
            ]}
          />
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
      {ch.thumb && ch.thumb.self && (
        <Box mt={2}>
          <Typography variant="subtitle2" fontWeight={700} mb={1}>
            Phân tích thumbnail
          </Typography>
          <StatGrid
            stats={[
              ch.thumb.self.bright ? { label: "Độ sáng (kênh)", value: ch.thumb.self.bright } : null,
              ch.thumb.self.sat ? { label: "Độ rực (kênh)", value: ch.thumb.self.sat } : null,
              ch.thumb.self.colors ? { label: "Màu chủ đạo (kênh)", value: ch.thumb.self.colors } : null,
              ch.thumb.niche?.colors ? { label: "Màu chủ đạo (ngách)", value: ch.thumb.niche.colors } : null,
            ]}
          />
          {Array.isArray(ch.thumb.obs) && ch.thumb.obs.length > 0 && (
            <Box component="ul" sx={{ pl: 2, mt: 1, mb: 0 }}>
              {ch.thumb.obs.map((o, i) => (
                <li key={i}>
                  <Typography variant="body2">{o}</Typography>
                </li>
              ))}
            </Box>
          )}
          {ch.thumb.verdict && String(ch.thumb.verdict).trim() && (
            <Typography variant="body2" sx={{ mt: 1 }}>
              {ch.thumb.verdict}
            </Typography>
          )}
        </Box>
      )}
      {Array.isArray(ch.kw) && ch.kw.length > 0 && (
        <Box mt={2}>
          <Typography variant="subtitle2" fontWeight={700} mb={1}>
            Từ khoá của kênh
          </Typography>
          <DataTable
            limit={null}
            rows={ch.kw}
            columns={[
              { key: "kw", label: "Từ khoá" },
              { key: "score", label: "Điểm", align: "right", render: (r) => (r.score != null ? r.score.toFixed(2) : "—") },
              { key: "chv", label: "Video kênh dùng", align: "right", render: (r) => num(r.chv) },
              { key: "comp", label: "Cạnh tranh", align: "center", render: (r) => r.comp || "—" },
              { key: "rc", label: "Kết quả YT", align: "right", render: (r) => num(r.rc) },
            ]}
          />
        </Box>
      )}
      {ch.desc && String(ch.desc).trim() && (
        <Box mt={2}>
          <Typography variant="subtitle2" fontWeight={700} mb={1}>
            Mô tả kênh
          </Typography>
          <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>
            {ch.desc}
          </Typography>
        </Box>
      )}
    </SectionCard>
  );
};

// Bình luận khán giả (kênh chính) — sentiment + nhận định AI + yêu cầu + top.
const CommentsBlock = ({ c }) => {
  if (!c || !c.total) return null;
  const pill = (w, i) =>
    typeof w === "string" ? (
      <Pill key={i} label={w} />
    ) : (
      <Pill key={i} label={`${w.word || w.text || ""} (${w.n ?? w.count ?? ""})`} />
    );
  return (
    <SectionCard
      title={`Bình luận khán giả (${num(c.total)})`}
      action={
        <Box component="span" sx={{ fontWeight: 700, whiteSpace: "nowrap" }}>
          <Box component="span" sx={{ color: "success.main" }}>
            👍 {num(c.pos)} ({c.pos_pct}%)
          </Box>
          {"  ·  "}
          <Box component="span" sx={{ color: "error.main" }}>
            👎 {num(c.neg)} ({c.neg_pct}%)
          </Box>
        </Box>
      }
    >
      {c.report && String(c.report).trim() && (
        <Box mb={2}>
          <Typography variant="subtitle2" fontWeight={700} mb={0.5}>
            Nhận định AI{c.report_at ? ` — ${c.report_at}` : ""}
          </Typography>
          <TextBlock text={c.report} />
        </Box>
      )}
      {Array.isArray(c.requests) && c.requests.length > 0 && (
        <Box mb={2}>
          <Typography variant="subtitle2" fontWeight={700} mb={1}>
            Khán giả xin làm video
          </Typography>
          <AutoTable rows={c.requests} />
        </Box>
      )}
      {Array.isArray(c.top_liked) && c.top_liked.length > 0 && (
        <Box mb={2}>
          <Typography variant="subtitle2" fontWeight={700} mb={1}>
            Bình luận nhiều thích nhất
          </Typography>
          <AutoTable rows={c.top_liked} />
        </Box>
      )}
      {Array.isArray(c.words) && c.words.length > 0 && (
        <Box mb={1}>
          <Typography variant="body2" component="span" sx={{ mr: 0.5 }}>
            <b>Từ hay gặp:</b>
          </Typography>
          {c.words.slice(0, 30).map(pill)}
        </Box>
      )}
      {Array.isArray(c.all) && c.all.length > 0 && (
        <Box mt={2}>
          <Typography variant="subtitle2" fontWeight={700} mb={1}>
            Toàn bộ bình luận ({c.all.length})
          </Typography>
          <AutoTable rows={c.all} />
        </Box>
      )}
    </SectionCard>
  );
};

// Video của ngành theo từ khoá — dropdown chọn keyword → video mới + xếp hạng.
const NicheByKeyword = ({ niche, nicheTop }) => {
  const keys = Object.keys(niche || {});
  const [sel, setSel] = useState(keys[0] || "");
  if (!keys.length) return <EmptyState text="Chưa có dữ liệu video ngành theo từ khoá." />;
  const cur = keys.includes(sel) ? sel : keys[0];
  const recent = (niche || {})[cur] || [];
  const top = (nicheTop || {})[cur] || [];
  return (
    <SectionCard
      title="Video của ngành theo từ khoá"
      action={
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <Select value={cur} onChange={(e) => setSel(e.target.value)}>
            {keys.map((k) => (
              <MenuItem key={k} value={k}>
                {k}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      }
    >
      {recent.length > 0 && (
        <Box mb={2}>
          <Typography variant="subtitle2" fontWeight={700} mb={1}>
            🚀 Video mới nhiều view — "{cur}"
          </Typography>
          <DataTable columns={videoCols} rows={recent} limit={null} />
        </Box>
      )}
      {top.length > 0 && (
        <Box>
          <Typography variant="subtitle2" fontWeight={700} mb={1}>
            🔥 Xếp hạng top — "{cur}"
          </Typography>
          <DataTable columns={videoCols} rows={top} limit={null} />
        </Box>
      )}
      {!recent.length && !top.length && <EmptyState text="Từ khoá này chưa có video." />}
    </SectionCard>
  );
};

// ---------- tab definitions ----------
// group: nhãn nhóm; id, label, render(d)
export const TAB_GROUPS = [
  { key: "A", label: "Tổng quan & Sức khoẻ" },
  { key: "B", label: "Kênh chính" },
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
    render: (d) => (
      <>
        <ChannelBlock ch={d.self} defaultOpen showUrl={false} />
        {Array.isArray(d.video_track) && d.video_track.length > 0 && (
          <SectionCard title="📈 Diễn biến lượt xem video kênh chính">
            <DataTable
              limit={null}
              rows={d.video_track}
              columns={[
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
                { key: "pts", label: "Lượt xem qua các kỳ", render: (r) => (r.pts || []).map(num).join(" → ") },
                { key: "growth", label: "Tăng", align: "right", render: (r) => sg(r.growth) },
              ]}
            />
          </SectionCard>
        )}
        <CommentsBlock c={d.comments} />
      </>
    ),
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
    render: (d) => <InsideSynthesis s={d.inside_synthesis} />,
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
    render: (d, ctx) => <AudienceInsight d={d} ctx={ctx} />,
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
    render: (d) => <NicheByKeyword niche={d.niche} nicheTop={d.niche_top} />,
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
      const kws = d.keywords || [];
      const tp = d.title_patterns || [];
      const tpk = d.title_pattern && Object.keys(d.title_pattern).length ? d.title_pattern : null;
      if (!kws.length && !tp.length && !tpk) return <EmptyState text="Chưa có dữ liệu từ khoá." />;
      const fc = tpk?.feature_correlation
        ? Object.entries(tpk.feature_correlation).map(([k, v]) => ({ feat: k, ...(v || {}) }))
        : [];
      const ls = tpk?.length_stats
        ? Object.entries(tpk.length_stats).map(([k, v]) => ({ bucket: k, ...(v || {}) }))
        : [];
      return (
        <>
          {kws.length > 0 && (
            <SectionCard title={`Từ khoá chủ đạo của ngành (${kws.length})`}>
              <DataTable
                limit={null}
                rows={kws}
                columns={[
                  { key: "kw", label: "Từ khoá" },
                  { key: "score", label: "Điểm", align: "right", render: (r) => (r.score != null ? r.score.toFixed(2) : "—") },
                  { key: "chv", label: "Video kênh chứa", align: "right", render: (r) => num(r.chv) },
                  { key: "sources", label: "Nguồn", render: (r) => (r.sources || []).join(", ") || "—" },
                  ...ktCols(d.kw_enrich),
                  { key: "sug", label: "Gợi ý tìm", render: (r) => (r.sug || []).slice(0, 6).join(", ") || "—" },
                ]}
              />
            </SectionCard>
          )}
          {tp.length > 0 && (
            <SectionCard title="Công thức tiêu đề thắng trong ngành">
              <DataTable
                limit={null}
                rows={tp}
                columns={[
                  { key: "feat", label: "Đặc điểm tiêu đề" },
                  { key: "n", label: "Số video", align: "right" },
                  { key: "med_with", label: "View TB khi CÓ", align: "right", render: (r) => num(r.med_with) },
                  { key: "med_without", label: "khi KHÔNG", align: "right", render: (r) => num(r.med_without) },
                  { key: "lift", label: "Hệ số", align: "right", render: (r) => (r.lift != null ? `${r.lift}x` : "—") },
                ]}
              />
            </SectionCard>
          )}
          {tpk && (
            <SectionCard title="Công thức tiêu đề (data-driven)">
              {Array.isArray(tpk.recommendations) && tpk.recommendations.length > 0 && (
                <Box component="ul" sx={{ pl: 2, mt: 0, mb: 2 }}>
                  {tpk.recommendations.map((r, i) => (
                    <li key={i}>
                      <Typography variant="body2">{r}</Typography>
                    </li>
                  ))}
                </Box>
              )}
              {fc.length > 0 && (
                <Box mb={2}>
                  <Typography variant="subtitle2" fontWeight={700} mb={1}>
                    Tương quan feature × views/ngày
                  </Typography>
                  <DataTable
                    limit={null}
                    rows={fc}
                    columns={[
                      { key: "feat", label: "Feature" },
                      { key: "n_on", label: "N có", align: "right" },
                      { key: "on_avg", label: "View TB CÓ", align: "right", render: (r) => num(r.on_avg) },
                      { key: "off_avg", label: "View TB KHÔNG", align: "right", render: (r) => num(r.off_avg) },
                      { key: "lift_pct", label: "Lift %", align: "right", render: (r) => (r.lift_pct != null ? `${r.lift_pct}%` : "—") },
                    ]}
                  />
                </Box>
              )}
              {ls.length > 0 && (
                <Box mb={2}>
                  <Typography variant="subtitle2" fontWeight={700} mb={1}>
                    Độ dài tiêu đề × views/ngày
                  </Typography>
                  <DataTable
                    limit={null}
                    rows={ls}
                    columns={[
                      { key: "bucket", label: "Độ dài" },
                      { key: "n", label: "N", align: "right" },
                      { key: "avg_views_per_day", label: "View/ngày TB", align: "right", render: (r) => num(r.avg_views_per_day) },
                    ]}
                  />
                </Box>
              )}
              {Array.isArray(tpk.winning_ngrams) && tpk.winning_ngrams.length > 0 && (
                <Box mb={1}>
                  <Typography variant="body2" component="span" sx={{ mr: 0.5 }}>
                    <b>🏆 Cụm "thắng":</b>
                  </Typography>
                  {tpk.winning_ngrams.map((g, i) => (
                    <Pill key={i} label={g.ngram || String(g)} color="success" />
                  ))}
                </Box>
              )}
              {Array.isArray(tpk.losing_ngrams) && tpk.losing_ngrams.length > 0 && (
                <Box>
                  <Typography variant="body2" component="span" sx={{ mr: 0.5 }}>
                    <b>⚠ Cụm "thua":</b>
                  </Typography>
                  {tpk.losing_ngrams.map((g, i) => (
                    <Pill key={i} label={g.ngram || String(g)} color="error" />
                  ))}
                </Box>
              )}
            </SectionCard>
          )}
        </>
      );
    },
  },
  {
    id: "title_pattern",
    group: "F",
    label: "Tiêu đề mẫu",
    render: (d) => {
      const tv = d.title_variants || [];
      if (!tv.length) return <EmptyState text="Chưa đủ dữ liệu để sinh tiêu đề mẫu." />;
      return (
        <SectionCard title="Tiêu đề mẫu — sinh từ công thức thắng">
          <DataTable
            limit={null}
            rows={tv}
            columns={[
              { key: "title", label: "Tiêu đề mẫu" },
              { key: "score", label: "Điểm", align: "right", render: (r) => num(r.score) },
              { key: "template", label: "Mẫu gốc" },
            ]}
          />
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
    render: () => <SeoBestPractice />,
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
