import { Fragment, useEffect, useMemo, useState } from "react";
import {
  Avatar,
  Box,
  Chip,
  CircularProgress,
  Collapse,
  FormControl,
  Link,
  MenuItem,
  Paper,
  Popover,
  Select,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  Typography,
  useTheme,
} from "@mui/material";
import KeyboardArrowDownRoundedIcon from "@mui/icons-material/KeyboardArrowDownRounded";
import { alpha } from "@mui/material/styles";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { DataTable, EmptyState, SectionCard, TextBlock, num } from "./primitives";
import {
  getResearchSummary,
  getVideoRetention,
  listWatchlists,
} from "../../services/researchService";
import {
  getSharedFilterControlSx,
  getSharedSelectMenuProps,
} from "../filterStyles";

// giây -> "m:ss"
const fmtDur = (sec) => {
  const s = Math.round(Number(sec) || 0);
  if (!s) return "—";
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

const fmtAvgDur = (avgSec, totalSec) => {
  const avg = Number(avgSec) || 0;
  const total = Number(totalSec) || 0;
  if (!avg) return "—";
  const pct = total > 0 ? ` (${Math.round((avg / total) * 100)}%)` : "";
  return `${fmtDur(avg)}${pct}`;
};

// Mini stat cho header chart retention.
const RetStat = ({ label, value, color }) => (
  <Box sx={{ flex: 1, minWidth: 0 }}>
    <Typography variant="caption" color="text.secondary" noWrap sx={{ display: "block", lineHeight: 1.2 }}>
      {label}
    </Typography>
    <Typography variant="subtitle2" fontWeight={800} sx={{ color, lineHeight: 1.2 }}>
      {value}
    </Typography>
  </Box>
);

// Chart retention (nguồn page Audience) — diễn giải dễ hiểu khi hover video.
const RetentionMini = ({ rows, title, durationSeconds, theme }) => {
  if (rows == null) {
    return (
      <Box display="flex" alignItems="center" gap={1}>
        <CircularProgress size={14} />
        <Typography variant="caption" color="text.secondary">
          Đang tải retention…
        </Typography>
      </Box>
    );
  }
  if (!rows.length) {
    return (
      <Typography variant="caption" color="text.secondary">
        Không có dữ liệu retention cho video này.
      </Typography>
    );
  }

  const data = rows
    .filter((r) => r.elapsed_video_time_ratio != null)
    .sort((a, b) => a.elapsed_video_time_ratio - b.elapsed_video_time_ratio)
    .map((r) => ({
      x: Math.round((r.elapsed_video_time_ratio || 0) * 100),
      y: +(((r.audience_watch_ratio || 0) * 100).toFixed(1)),
    }));
  const getRetentionAt = (xPct) => {
    if (!data.length || xPct == null) return null;
    if (xPct <= data[0].x) return data[0].y;
    for (let i = 1; i < data.length; i++) {
      const prev = data[i - 1];
      const curr = data[i];
      if (xPct <= curr.x) {
        const span = curr.x - prev.x;
        if (!span) return curr.y;
        const ratio = (xPct - prev.x) / span;
        return prev.y + (curr.y - prev.y) * ratio;
      }
    }
    return data[data.length - 1].y;
  };
  const thirtySecondX =
    Number(durationSeconds) > 30 ? Math.min(100, (30 / Number(durationSeconds)) * 100) : null;
  const thirtySecondPct = thirtySecondX == null ? null : getRetentionAt(thirtySecondX);
  const thirtySecondLabel =
    thirtySecondPct != null
      ? `${thirtySecondPct.toFixed(1)}%`
      : Number(durationSeconds) > 0
      ? "Video <30s"
      : "Chua co do dai";

  // Chỉ số tóm tắt dễ hiểu
  const avgPct = Math.round(data.reduce((s, p) => s + p.y, 0) / data.length);
  const endPct = Math.round(data[data.length - 1].y);
  let dropX = null;
  let dropAmt = 0;
  for (let i = 1; i < data.length; i++) {
    const d = data[i - 1].y - data[i].y;
    if (d > dropAmt) {
      dropAmt = d;
      dropX = data[i].x;
    }
  }
  const endColor =
    endPct >= 50 ? theme.palette.success.main : endPct >= 30 ? theme.palette.warning.main : theme.palette.error.main;
  // Keep retention line and tooltip cursor the same color in light/dark mode.
  const lineColor = theme.palette.info.light;

  return (
    <Box>
      <Typography variant="subtitle2" fontWeight={700} noWrap title={title} sx={{ maxWidth: 410 }}>
        {title}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
        Tỷ lệ người xem còn lại theo thời lượng video
      </Typography>

      <Box display="flex" gap={1.5} mb={1}>
        <RetStat label="Xem trung bình" value={`${avgPct}%`} color={lineColor} />
        <RetStat label="30s đầu" value={thirtySecondLabel} color={theme.palette.warning.main} />
        <RetStat label="Xem đến hết" value={`${endPct}%`} color={endColor} />
        <RetStat
          label="Tụt mạnh nhất"
          value={dropX != null ? `${dropX}% video` : "—"}
          color={theme.palette.error.main}
        />
      </Box>

      <Box sx={{ height: 168 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 6, right: 10, bottom: 18, left: -8 }}>
            <defs>
              <linearGradient id="retGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={lineColor} stopOpacity={0.35} />
                <stop offset="100%" stopColor={lineColor} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={alpha(theme.palette.text.secondary, 0.18)} vertical={false} />
            <XAxis
              dataKey="x"
              type="number"
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              tick={{ fontSize: 10 }}
              tickFormatter={(v) => `${v}%`}
              stroke={theme.palette.text.secondary}
              label={{ value: "Thời lượng video", position: "insideBottom", offset: -8, fontSize: 11, fill: theme.palette.text.secondary }}
            />
            <YAxis
              tick={{ fontSize: 10 }}
              tickFormatter={(v) => `${v}%`}
              width={42}
              stroke={theme.palette.text.secondary}
              domain={[0, (max) => Math.max(100, Math.ceil(max / 10) * 10)]}
            />
            <RTooltip
              formatter={(v) => [`${v}%`, "Người xem còn lại"]}
              labelFormatter={(l) => `Tại ${l}% video`}
              cursor={{ stroke: lineColor, strokeWidth: 1.5, strokeDasharray: "4 4" }}
              content={({ active, label, payload }) => {
                if (!active || !payload?.length) return null;
                const point = payload[0];
                return (
                  <Box
                    sx={{
                      p: 1,
                      minWidth: 160,
                      borderRadius: 1,
                      bgcolor: theme.palette.background.paper,
                      border: `1px solid ${alpha(lineColor, 0.45)}`,
                      boxShadow: theme.shadows[3],
                    }}
                  >
                    <Typography variant="caption" fontWeight={700} sx={{ display: "block" }}>
                      {`Tại ${label}% video`}
                    </Typography>
                    <Box display="flex" justifyContent="space-between" gap={2} mt={0.5}>
                      <Typography variant="caption" color="text.secondary">
                        Người xem còn lại
                      </Typography>
                      <Typography variant="caption" fontWeight={800} sx={{ color: lineColor }}>
                        {`${Number(point.value || 0).toFixed(1)}%`}
                      </Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between" gap={2} mt={0.25}>
                      <Typography variant="caption" color="text.secondary">
                        30s đầu
                      </Typography>
                      <Typography variant="caption" fontWeight={800} sx={{ color: theme.palette.warning.main }}>
                        {thirtySecondLabel}
                      </Typography>
                    </Box>
                  </Box>
                );
              }}
            />
            <ReferenceLine
              y={100}
              stroke={alpha(theme.palette.text.secondary, 0.5)}
              strokeDasharray="4 4"
              label={{ value: "Bắt đầu 100%", position: "right", fontSize: 9, fill: theme.palette.text.secondary }}
            />
            {dropX != null && (
              <ReferenceLine x={dropX} stroke={theme.palette.error.main} strokeDasharray="4 4" strokeOpacity={0.7} />
            )}
            <Area
              type="monotone"
              dataKey="y"
              stroke={lineColor}
              strokeWidth={2}
              fill="url(#retGrad)"
              dot={false}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </Box>

      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
        Đường càng cao &amp; phẳng = giữ chân tốt · vạch đỏ = nơi nhiều người thoát.
      </Typography>
    </Box>
  );
};

const sg = (v) => {
  const n = Number(v) || 0;
  return (n > 0 ? "+" : "") + num(n);
};

// "2026-06-05 14:56" -> ngày "2026-06-05", giờ "14:56"
const snapYmd = (dt) => String(dt || "").split(" ")[0];
const snapHm = (dt) => String(dt || "").split(" ")[1] || "";
// "2026-06-05" -> "05/06/2026" (đồng bộ format các page báo cáo khác)
const fmtSnapDay = (ymd) => {
  const [y, m, d] = String(ymd || "").split("-");
  return y && m && d ? `${d}/${m}/${y}` : String(ymd || "");
};

const SummaryReport = () => {
  const theme = useTheme();
  const filterControlSx = getSharedFilterControlSx(theme, { flex: "0 0 auto" });
  const selectMenuProps = getSharedSelectMenuProps(theme);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [avatars, setAvatars] = useState({});
  const [expandedWid, setExpandedWid] = useState("");
  const [tab, setTab] = useState("overview");
  const [retHover, setRetHover] = useState(null); // {anchorEl, key, video}
  const [retCache, setRetCache] = useState({}); // key -> rows | null(loading)

  const handleVideoEnter = (e, accountTag, v) => {
    const key = `${accountTag || ""}|${v.video_id}`;
    setRetHover({ anchorEl: e.currentTarget, key, video: v });
    if (accountTag && v.video_id && retCache[key] === undefined) {
      setRetCache((c) => ({ ...c, [key]: null }));
      getVideoRetention(accountTag, v.video_id)
        .then((d) => setRetCache((c) => ({ ...c, [key]: d?.rows || [] })))
        .catch(() => setRetCache((c) => ({ ...c, [key]: [] })));
    }
  };
  const handleVideoLeave = () => setRetHover(null);

  const load = (opts = {}) => {
    setLoading(true);
    setError("");
    getResearchSummary(opts)
      .then(setData)
      .catch((e) => {
        setData(null);
        setError(e?.response?.data?.detail || e.message);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    listWatchlists()
      .then((items) => {
        const m = {};
        items.forEach((w) => {
          if (w.avatar) m[w.id] = w.avatar;
        });
        setAvatars(m);
      })
      .catch(() => {});
  }, []);

  const snapshots = data?.snapshots || [];
  const snapshotId = data?.snapshot_id || "";

  // Tách ngày / giờ: dropdown ngày, kèm dropdown giờ khi 1 ngày có ≥2 báo cáo.
  const selSnap = snapshots.find((s) => s.id === snapshotId);
  const snapDays = [...new Set(snapshots.map((s) => snapYmd(s.date)))];
  const snapDay = snapYmd(selSnap?.date) || snapDays[0] || "";
  const snapDayItems = snapshots.filter((s) => snapYmd(s.date) === snapDay);

  const warnings = useMemo(
    () =>
      (data?.watchlists || []).flatMap((w) =>
        (w.warnings || []).map((warning) => ({
          watchlist: w.name,
          channel: w.self_title,
          warning,
        }))
      ),
    [data]
  );

  if (loading && !data) {
    return (
      <Box display="flex" alignItems="center" gap={1}>
        <CircularProgress size={18} />
        <Typography variant="body2" color="text.secondary">
          Đang tạo báo cáo tổng hợp…
        </Typography>
      </Box>
    );
  }

  if (error && !data) return <EmptyState text={`Lỗi: ${error}`} />;
  if (!data) return <EmptyState text="Chưa có dữ liệu báo cáo tổng hợp." />;

  const wlRows = data.watchlists || [];
  const topVideos = data.cross_top_videos || [];
  const opps = data.cross_wl_opps || [];
  const oppColumns = opps.length
    ? Object.keys(opps[0])
        .filter((k) => ["string", "number", "boolean"].includes(typeof opps[0][k]))
        .slice(0, 8)
        .map((k) => ({ key: k, label: k.replace(/_/g, " ") }))
    : [];

  const pos = theme.palette.success.main;
  const neg = theme.palette.error.main;
  const deltaColor = (v) =>
    Number(v) > 0 ? pos : Number(v) < 0 ? neg : theme.palette.text.secondary;
  const Delta = (v) => (
    <Typography component="span" variant="body2" fontWeight={700} sx={{ color: deltaColor(v) }}>
      {sg(v)}
    </Typography>
  );

  const kpis = [
    {
      label: "Người đăng ký",
      value: num(data.total_subs),
      hint: "Tổng hiện tại",
      accent: theme.palette.primary.main,
    },
    {
      label: "Δ Subs · 7 ngày",
      value: sg(data.total_subs_delta_7d),
      hint: "So với tuần trước",
      accent: deltaColor(data.total_subs_delta_7d),
      color: deltaColor(data.total_subs_delta_7d),
    },
    {
      label: "Δ Views · 7 ngày",
      value: sg(data.total_views_delta_7d),
      hint: "Tăng trưởng gần nhất",
      accent: deltaColor(data.total_views_delta_7d),
      color: deltaColor(data.total_views_delta_7d),
    },
    {
      label: "Cảnh báo",
      value: num(data.n_warnings),
      hint: data.n_warnings ? "Cần xử lý" : "Tốt, không có",
      accent: data.n_warnings ? theme.palette.warning.main : pos,
      color: data.n_warnings ? theme.palette.warning.main : pos,
    },
  ];

  const cardBg =
    theme.palette.mode === "dark" ? "rgba(255,255,255,0.03)" : "rgba(15,23,42,0.02)";
  const subtleBorder = `1px solid ${theme.palette.divider}`;
  // dark mode: primary.main gần trùng nền → dùng màu sáng cho accent/hover.
  const accentColor =
    theme.palette.mode === "dark" ? theme.palette.info.light : theme.palette.primary.main;

  const dateBar = (
    <Box display="flex" alignItems="center" gap={1.5} mb={2} flexWrap="wrap">
      {snapshots.length > 0 && (
        <FormControl size="small" sx={{ ...filterControlSx, minWidth: { xs: "100%", sm: 175 } }}>
          <Select
            value={snapDay}
            onChange={(e) => {
              const newest = snapshots.find((s) => snapYmd(s.date) === e.target.value);
              if (newest) load({ snapshot: newest.id });
            }}
            disabled={loading}
            MenuProps={selectMenuProps}
            renderValue={(val) => `🗓 ${fmtSnapDay(val)}`}
          >
            {snapDays.map((d) => (
              <MenuItem key={d} value={d}>
                {fmtSnapDay(d)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      )}
      {snapDayItems.length > 1 && (
        <FormControl size="small" sx={{ ...filterControlSx, minWidth: { xs: "100%", sm: 130 } }}>
          <Select
            value={snapshotId}
            onChange={(e) => load({ snapshot: e.target.value })}
            disabled={loading}
            MenuProps={selectMenuProps}
            renderValue={(val) => `🕐 ${snapHm(snapshots.find((s) => s.id === val)?.date)}`}
          >
            {snapDayItems.map((it) => (
              <MenuItem key={it.id} value={it.id}>
                {snapHm(it.date)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      )}
      {loading && <CircularProgress size={18} />}
      {error && <Chip size="small" color="error" variant="outlined" label={error} />}
    </Box>
  );

  // dark mode: primary.main gần trùng nền → dùng secondary cho tab đang chọn.
  const selColor = theme.palette.mode === "dark" ? "secondary" : "primary";
  const summaryTabs = [
    { key: "overview", label: `Tổng quan (${wlRows.length} kênh)` },
    { key: "topvideos", label: `Top video (${topVideos.length})` },
    { key: "warnings", label: `Cảnh báo (${warnings.length})` },
    { key: "cross", label: `Cross-WL (${opps.length})` },
    { key: "strategy", label: "Chiến lược" },
  ];

  return (
    <Box>
      {dateBar}
      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        variant="scrollable"
        scrollButtons="auto"
        textColor={selColor}
        indicatorColor={selColor}
        sx={{ borderBottom: `1px solid ${theme.palette.divider}`, mb: 2 }}
      >
        {summaryTabs.map((t) => (
          <Tab key={t.key} value={t.key} label={t.label} sx={{ textTransform: "none" }} />
        ))}
      </Tabs>

      {tab === "overview" && (
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(165px, 1fr))",
          gap: 1.5,
          mb: 2,
        }}
      >
        {kpis.map((k) => (
          <Box
            key={k.label}
            sx={{
              p: 1.5,
              borderRadius: 2,
              border: subtleBorder,
              borderLeft: `3px solid ${k.accent}`,
              bgcolor: alpha(k.accent, theme.palette.mode === "dark" ? 0.1 : 0.05),
            }}
          >
            <Typography variant="caption" color="text.secondary" noWrap title={k.label}>
              {k.label}
            </Typography>
            <Typography variant="h5" fontWeight={800} sx={{ lineHeight: 1.3, color: k.color }}>
              {k.value}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {k.hint}
            </Typography>
          </Box>
        ))}
      </Box>
      )}

      {tab === "overview" && (
      <SectionCard
        title="Tình hình từng kênh"
        subtitle="Bấm vào một kênh để xem 3 video mới nhất"
        action={<Chip size="small" variant="outlined" label={`${wlRows.length} kênh`} />}
      >
        <TableContainer
          component={Paper}
          elevation={0}
          sx={{ border: subtleBorder, borderRadius: 2 }}
        >
          <Table stickyHeader size="small">
            <TableHead>
              <TableRow>
                {["", "Kênh chính", "Subs", "Δ Subs 7d", "Δ Views 7d", "View/ngày TB", "Video hot nhất"].map(
                  (h, i) => (
                    <TableCell
                      key={i}
                      align={i >= 2 && i <= 5 ? "right" : "left"}
                      sx={{ fontWeight: 700, whiteSpace: "nowrap", bgcolor: theme.palette.background.paper }}
                    >
                      {h}
                    </TableCell>
                  )
                )}
              </TableRow>
            </TableHead>
            <TableBody>
              {wlRows.map((r) => {
                const open = expandedWid === r.wid;
                const vids = r.latest_videos || [];
                const top = (r.top_videos_today || [])[0];
                return (
                  <Fragment key={r.wid}>
                    <TableRow
                      hover
                      onClick={() => setExpandedWid(open ? "" : r.wid)}
                      sx={{ cursor: "pointer", "& > *": { borderBottom: open ? "unset" : undefined } }}
                    >
                      <TableCell sx={{ width: 36 }}>
                        <KeyboardArrowDownRoundedIcon
                          fontSize="small"
                          sx={{
                            color: "text.secondary",
                            transition: "transform .2s ease",
                            transform: open ? "rotate(180deg)" : "none",
                          }}
                        />
                      </TableCell>
                      <TableCell>
                        <Box display="flex" alignItems="center" gap={1}>
                          <Avatar src={avatars[r.wid] || ""} sx={{ width: 30, height: 30 }}>
                            {(r.self_title || r.name || "?")[0]}
                          </Avatar>
                          <Box sx={{ minWidth: 0 }}>
                            <Typography variant="body2" fontWeight={700} noWrap>
                              {r.self_title || r.name || "—"}
                            </Typography>
                            {r.name && r.name !== r.self_title && (
                              <Typography variant="caption" color="text.secondary" noWrap>
                                {r.name}
                              </Typography>
                            )}
                          </Box>
                        </Box>
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="body2" fontWeight={600}>{num(r.subs)}</Typography>
                      </TableCell>
                      <TableCell align="right">{Delta(r.subs_delta_7d)}</TableCell>
                      <TableCell align="right">{Delta(r.views_delta_7d)}</TableCell>
                      <TableCell align="right">{num(r.avg_daily_views_7d)}</TableCell>
                      <TableCell>
                        {top ? (
                          <Box>
                            <Typography variant="body2" noWrap sx={{ maxWidth: 260 }} title={top.title}>
                              {top.title}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              ~{num(top.vpd)} view/ngày
                            </Typography>
                          </Box>
                        ) : (
                          <Typography variant="body2" color="text.secondary">—</Typography>
                        )}
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell colSpan={7} sx={{ py: 0, border: 0, bgcolor: cardBg }}>
                        <Collapse in={open} timeout="auto" unmountOnExit>
                          <Box sx={{ py: 1.75, px: 1 }}>
                            {vids.length ? (
                              <TableContainer
                                component={Paper}
                                elevation={0}
                                sx={{ border: subtleBorder, borderRadius: 2, mt: 1 }}
                              >
                                <Table size="small">
                                  <TableHead>
                                    <TableRow>
                                      {["Video", "Ngày đăng", "Views", "Watch time (h)", "Avg duration", "Subs", "Impressions", "CTR"].map(
                                        (h, i) => (
                                          <TableCell
                                            key={i}
                                            align={i >= 2 ? "right" : "left"}
                                            sx={{ fontWeight: 700, whiteSpace: "nowrap", bgcolor: theme.palette.background.paper }}
                                          >
                                            {h}
                                          </TableCell>
                                        )
                                      )}
                                    </TableRow>
                                  </TableHead>
                                  <TableBody>
                                    {vids.map((v) => (
                                      <TableRow
                                        key={v.video_id}
                                        hover
                                        onMouseEnter={(e) => handleVideoEnter(e, r.account_tag, v)}
                                        onMouseLeave={handleVideoLeave}
                                      >
                                        <TableCell>
                                          <Link
                                            href={v.url || undefined}
                                            target="_blank"
                                            rel="noopener"
                                            underline="none"
                                            sx={{
                                              display: "flex",
                                              alignItems: "center",
                                              gap: 1,
                                              color: "inherit",
                                              "&:hover .vtitle": { color: accentColor },
                                            }}
                                          >
                                            <Box
                                              sx={{
                                                width: 72,
                                                height: 40,
                                                position: "relative",
                                                flexShrink: 0,
                                              }}
                                            >
                                              <Box
                                                component="img"
                                                src={
                                                  (v.thumbnail || "").startsWith("http")
                                                    ? v.thumbnail
                                                    : v.video_id
                                                    ? `https://i.ytimg.com/vi/${v.video_id}/mqdefault.jpg`
                                                    : ""
                                                }
                                                alt=""
                                                loading="lazy"
                                                sx={{
                                                  width: "100%",
                                                  height: "100%",
                                                  objectFit: "cover",
                                                  borderRadius: 1,
                                                  bgcolor: theme.palette.action.hover,
                                                  display: "block",
                                                }}
                                              />
                                              {v.duration_seconds ? (
                                                <Box
                                                  sx={{
                                                    position: "absolute",
                                                    right: 3,
                                                    bottom: 3,
                                                    px: 0.45,
                                                    py: 0.1,
                                                    borderRadius: 0.5,
                                                    bgcolor: "rgba(0,0,0,0.78)",
                                                    color: "#fff",
                                                    fontSize: 10,
                                                    fontWeight: 700,
                                                    lineHeight: 1.2,
                                                  }}
                                                >
                                                  {fmtDur(v.duration_seconds)}
                                                </Box>
                                              ) : null}
                                            </Box>
                                            <Typography
                                              className="vtitle"
                                              variant="body2"
                                              sx={{
                                                fontWeight: 600,
                                                maxWidth: 320,
                                                display: "-webkit-box",
                                                WebkitLineClamp: 2,
                                                WebkitBoxOrient: "vertical",
                                                overflow: "hidden",
                                                lineHeight: 1.35,
                                              }}
                                              title={v.title}
                                            >
                                              {v.title}
                                            </Typography>
                                          </Link>
                                        </TableCell>
                                        <TableCell sx={{ whiteSpace: "nowrap" }}>{v.published_at || "—"}</TableCell>
                                        <TableCell align="right">{num(v.views)}</TableCell>
                                        <TableCell align="right">
                                          {v.watch_minutes == null ? "—" : num(Math.round(v.watch_minutes / 60))}
                                        </TableCell>
                                        <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                                          {fmtAvgDur(v.avg_view_duration, v.duration_seconds)}
                                        </TableCell>
                                        <TableCell align="right">{num(v.subscribers)}</TableCell>
                                        <TableCell align="right">{num(v.impressions)}</TableCell>
                                        <TableCell align="right">{v.ctr == null ? "—" : `${v.ctr}%`}</TableCell>
                                      </TableRow>
                                    ))}
                                  </TableBody>
                                </Table>
                              </TableContainer>
                            ) : (
                              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                                Chưa có dữ liệu video.
                              </Typography>
                            )}
                          </Box>
                        </Collapse>
                      </TableCell>
                    </TableRow>
                  </Fragment>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      </SectionCard>
      )}

      {tab === "topvideos" && (
      <SectionCard
        title="Top video nổi bật toàn công ty"
        subtitle="Video bùng nổ xuyên ngách"
        action={topVideos.length ? <Chip size="small" variant="outlined" label={`${topVideos.length} video`} /> : null}
      >
        {topVideos.length ? (
          <DataTable
            rows={topVideos}
            limit={null}
            columns={[
              {
                key: "title",
                label: "Video",
                render: (r) => (
                  <Box display="flex" alignItems="center" gap={1}>
                    {r.video_id ? (
                      <Box
                        component="img"
                        src={`https://i.ytimg.com/vi/${r.video_id}/mqdefault.jpg`}
                        alt=""
                        loading="lazy"
                        sx={{
                          width: 72,
                          height: 40,
                          objectFit: "cover",
                          borderRadius: 1,
                          flexShrink: 0,
                          bgcolor: theme.palette.action.hover,
                        }}
                      />
                    ) : null}
                    <Typography variant="body2" fontWeight={600} sx={{ maxWidth: 320 }} noWrap title={r.title}>
                      {r.title}
                    </Typography>
                  </Box>
                ),
              },
              {
                key: "channel",
                label: "Kênh",
                render: (r) => (
                  <Box display="flex" alignItems="center" gap={1}>
                    <Avatar src={avatars[r.wid] || ""} sx={{ width: 24, height: 24 }}>
                      {(r.channel || "?")[0]}
                    </Avatar>
                    <Typography variant="body2" noWrap sx={{ maxWidth: 180 }} title={r.channel}>
                      {r.channel}
                    </Typography>
                  </Box>
                ),
              },
              { key: "views", label: "Views", align: "right", render: (r) => num(r.views) },
              { key: "vpd", label: "View/ngày", align: "right", render: (r) => (r.vpd ? num(r.vpd) : "—") },
              {
                key: "mult",
                label: "Outlier",
                align: "right",
                render: (r) =>
                  r.mult ? (
                    <Chip size="small" color="error" variant="outlined" label={`${r.mult}×`} />
                  ) : (
                    "—"
                  ),
              },
            ]}
          />
        ) : (
          <EmptyState text="Chưa có video nổi bật." />
        )}
      </SectionCard>
      )}

      {tab === "warnings" && (
      <SectionCard
        title="Cảnh báo"
        subtitle="Kênh tụt subs, video bị ẩn/xoá cần kiểm tra"
        action={
          <Chip
            size="small"
            color={warnings.length ? "warning" : "success"}
            variant="outlined"
            label={warnings.length ? `${warnings.length} cảnh báo` : "Không có"}
          />
        }
      >
        {warnings.length ? (
          <DataTable
            rows={warnings}
            limit={null}
            columns={[
              {
                key: "channel",
                label: "Kênh",
                render: (r) => (
                  <Box>
                    <Typography variant="body2" fontWeight={700}>{r.channel || "—"}</Typography>
                    <Typography variant="caption" color="text.secondary">{r.watchlist}</Typography>
                  </Box>
                ),
              },
              {
                key: "warning",
                label: "Nội dung",
                render: (r) => (
                  <Typography variant="body2" sx={{ color: theme.palette.warning.main }}>
                    {r.warning}
                  </Typography>
                ),
              },
            ]}
          />
        ) : (
          <EmptyState text="Không có cảnh báo." />
        )}
      </SectionCard>
      )}

      {tab === "cross" && (
      <SectionCard
        title="Cơ hội Cross-WL"
        subtitle="Cụm đang viral ở WL này → gợi ý thử cho WL khác có cùng tệp người xem"
      >
        {opps.length ? (
          <DataTable rows={opps} columns={oppColumns} limit={20} />
        ) : (
          <EmptyState text="Chưa có cơ hội Cross-WL." />
        )}
      </SectionCard>
      )}

      {tab === "strategy" && (
      <SectionCard title="Tóm lược chiến lược từng kênh">
        {wlRows.some((w) => w.strategy_preview) ? (
          <Box
            sx={{
              display: "grid",
              gap: 1.5,
              gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
            }}
          >
            {wlRows
              .filter((w) => w.strategy_preview)
              .map((w) => (
                <Box
                  key={w.wid}
                  sx={{
                    p: 1.75,
                    borderRadius: 2,
                    border: subtleBorder,
                    borderLeft: `3px solid ${theme.palette.secondary.main}`,
                    bgcolor: cardBg,
                  }}
                >
                  <Typography variant="subtitle2" fontWeight={700} gutterBottom>
                    {w.name}
                  </Typography>
                  <TextBlock text={w.strategy_preview} />
                </Box>
              ))}
          </Box>
        ) : (
          <EmptyState text="Chưa có tóm lược chiến lược." />
        )}
      </SectionCard>
      )}

      <Popover
        open={Boolean(retHover)}
        anchorEl={retHover?.anchorEl}
        onClose={handleVideoLeave}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
        transformOrigin={{ vertical: "top", horizontal: "left" }}
        disableRestoreFocus
        sx={{ pointerEvents: "none" }}
        slotProps={{ paper: { sx: { p: 1.5, width: 460, borderRadius: 2 } } }}
      >
        {retHover && (
          <RetentionMini
            rows={retCache[retHover.key]}
            title={retHover.video.title}
            durationSeconds={retHover.video.duration_seconds}
            theme={theme}
          />
        )}
      </Popover>
    </Box>
  );
};

export default SummaryReport;
