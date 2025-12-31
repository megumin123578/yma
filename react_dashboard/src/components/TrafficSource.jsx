// src/components/Trafficsource.jsx
import React, { useMemo, useState, useEffect, useCallback } from "react";
import { useTheme } from "@mui/material/styles";
import {
  Box,
  Stack,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  ListItemText,
  Button,
} from "@mui/material";

import { ResponsivePie } from "@nivo/pie";
import { ResponsiveLine } from "@nivo/line";
import { ResponsiveBar } from "@nivo/bar";

import {
  n,
  formatNumber,
  formatSeconds,
  METRICS,
  METRIC_OPTIONS,
  PERIOD_OPTIONS,
  getRangeForPeriod,
  makeDistinctPalette,
  toUTCDate,
  getMonthRange,
} from "./Module";

import dayjs from "dayjs";
import { LocalizationProvider, DatePicker } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";

import { API_BASE } from "../config";

const DATA_LAG_DAYS = 3;
const LAG_PERIODS = new Set(["last7", "last28", "last90", "last365"]);

/* ===== Helpers ===== */
const pad2 = (x) => String(x).padStart(2, "0");
const toYMD = (d) =>
  `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
const formatPercent = (v) => `${n(v).toFixed(2)}%`;

function applyDataLag(range, periodValue, now = new Date(), lagDays = DATA_LAG_DAYS) {
  if (!range?.start || !range?.end || !Number.isFinite(lagDays) || lagDays <= 0) return range;
  const endIsToday = dayjs(range.end).isSame(dayjs(now), "day");
  if (!endIsToday) return range;
  const minusLag = dayjs(now).subtract(lagDays, "day").startOf("day");

  if (periodValue === "month_current") {
    const start = dayjs(range.start);
    if (minusLag.isBefore(start)) return range;
    return { start: start.format("YYYY-MM-DD"), end: minusLag.format("YYYY-MM-DD") };
  }

  const start = dayjs(range.start);
  const end = dayjs(range.end);
  const lengthDays = end.diff(start, "day") + 1;
  const newEnd = minusLag;
  const newStart = newEnd.subtract(lengthDays - 1, "day");
  return { start: newStart.format("YYYY-MM-DD"), end: newEnd.format("YYYY-MM-DD") };
}

const EXTRA_PERIODS = [
  { value: "month_current", label: "This month" },
  { value: "month_prev", label: "Last month" },
  { value: "month_prev2", label: "Preceding month" },
];

const FILTERS_STORAGE_KEY = "trafficSource.filters";

const loadStoredFilters = () => {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(FILTERS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
};

const TrafficSourceChart = () => {
  const theme = useTheme();

  /* === Controls === */
  const [chartType, setChartType] = useState(() => loadStoredFilters()?.chartType || "pie");
  const [metric, setMetric] = useState(() => loadStoredFilters()?.metric || "views");
  const [period, setPeriod] = useState(() => loadStoredFilters()?.period || "last28");
  const [interval, setInterval] = useState(() => loadStoredFilters()?.interval || "daily");

  const [channels, setChannels] = useState([]);
  const [channel, setChannel] = useState(() => loadStoredFilters()?.channel || "");
  const authHeaders = useMemo(() => {
    const token = localStorage.getItem("access_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  useEffect(() => {
    let stop = false;
    (async () => {
      try {
        const resp = await fetch(`${API_BASE}/api/traffic_source/channels`, {
          headers: authHeaders,
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        const norm = (Array.isArray(data?.items) ? data.items : data).map((x) => {
          if (typeof x === "string") return { value: x, label: x };
          if (x?.value && x?.label) return x;
          if (x?.root && x?.label) return { value: x.root, label: x.label };
          if (x?.root) return { value: x.root, label: x.root };
          return { value: String(x?.value ?? x?.id ?? x), label: String(x?.label ?? x?.name ?? x?.value ?? x) };
        });
        const order = (() => {
          try {
            return JSON.parse(localStorage.getItem("tokens.order") || "[]");
          } catch {
            return [];
          }
        })()
          .map((name) => (name || "").replace(/\.pickle$/i, ""))
          .filter(Boolean);
        const orderKey = (value) => String(value || "").toLowerCase();
        const byId = new Map(norm.map((c) => [orderKey(c.value), c]));
        const ordered = order
          .map((name) => byId.get(orderKey(name)))
          .filter(Boolean);
        const remaining = norm.filter(
          (c) => !order.map(orderKey).includes(orderKey(c.value))
        );
        const finalChannels = [...ordered, ...remaining];
        if (!stop) {
          setChannels(finalChannels);
          if (!finalChannels.length) {
            setChannel("");
          } else {
            const hasStored = channel && finalChannels.some((opt) => opt.value === channel);
            if (!hasStored) setChannel(finalChannels[0].value);
          }
        }
      } catch (e) {
        console.error("Load channels failed:", e);
        if (!stop) setChannels([]);
      }
    })();
    return () => { stop = true; };
  }, [channel, authHeaders]);

  const [startDate, setStartDate] = useState(() => loadStoredFilters()?.startDate || "");
  const [endDate, setEndDate] = useState(() => loadStoredFilters()?.endDate || "");

  /* === Data === */
  const mconf = METRICS[metric];
  const [tsData, setTsData] = useState([]);
  const [tsSeries, setTsSeries] = useState([]);

  const [, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const fetchRange = useCallback(
    async (start, end) => {
      setLoading(true);
      setErrorMsg("");
      try {
        const resp = await fetch(`${API_BASE}/api/traffic_source/range`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders },
          body: JSON.stringify({ start, end, channelRoot: channel }),
        });
        if (!resp.ok) throw new Error((await resp.text()) || `HTTP ${resp.status}`);
        const data = await resp.json();
        setTsData(Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : []);
        if (!Array.isArray(data) && !Array.isArray(data?.items)) setErrorMsg("Dữ liệu trả về không đúng định dạng mảng.");
      } catch (e) {
        console.error(e);
        setTsData([]);
        setErrorMsg(e?.message || "Lỗi tải dữ liệu.");
      } finally {
        setLoading(false);
      }
    },
    [channel, authHeaders]
  );

  const fetchTimeseries = useCallback(
    async (start, end, intervalValue) => {
      setLoading(true);
      setErrorMsg("");
      try {
        const resp = await fetch(`${API_BASE}/api/traffic_source/timeseries`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders },
          body: JSON.stringify({ start, end, channelRoot: channel, interval: intervalValue }),
        });
        if (!resp.ok) throw new Error((await resp.text()) || `HTTP ${resp.status}`);
        const data = await resp.json();
        setTsSeries(Array.isArray(data) ? data : []);
      } catch (e) {
        console.error(e);
        setTsSeries([]);
        setErrorMsg(e?.message || "Lỗi tải timeseries.");
      } finally {
        setLoading(false);
      }
    },
    [channel, authHeaders]
  );

  const computeRange = useCallback((periodValue, now = new Date()) => {
    if (periodValue === "month_current") return getMonthRange(0, now);
    if (periodValue === "month_prev") return getMonthRange(1, now);
    if (periodValue === "month_prev2") return getMonthRange(2, now);

    const out = getRangeForPeriod(periodValue, now) || {};

    if (periodValue === "lifetime") {
      const today = toYMD(now);
      return {
        start: out.start && out.start.trim() ? out.start : "2000-01-01",
        end: out.end && out.end.trim() ? out.end : today,
      };
    }

    if (LAG_PERIODS.has(periodValue)) return applyDataLag(out, periodValue, now);
    return out;
  }, []);

  useEffect(() => {
    if (!channel) return;
    const isCustom = period === "custom";
    const now = new Date();
    const { start, end } = isCustom ? { start: startDate, end: endDate } : computeRange(period, now);

    if (isCustom && (!start || !end)) return;
    if (!start || !end) {
      setErrorMsg("Hãy chọn thời gian hợp lệ.");
      return;
    }

    fetchRange(start, end);
    if (chartType !== "pie") fetchTimeseries(start, end, interval);
  }, [
    chartType,
    period,
    channel,
    interval,
    startDate,
    endDate,
    computeRange,
    fetchRange,
    fetchTimeseries,
  ]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(
        FILTERS_STORAGE_KEY,
        JSON.stringify({
          chartType,
          metric,
          period,
          interval,
          channel,
          startDate,
          endDate,
        })
      );
    } catch (e) {
      // ignore storage errors
    }
  }, [chartType, metric, period, interval, channel, startDate, endDate]);

  /* === Table aggregation (base for charts + header filter list) === */
  const { totals, rows } = useMemo(() => {
    const src = Array.isArray(tsData) ? tsData : [];
    const rawRows = src.map((d, i) => {
      const id = d.id ?? d.label ?? d.insightTrafficSourceType ?? `item-${i}`;
      const label = d.label ?? d.insightTrafficSourceType ?? `item-${i}`;
      const views = n(d.views);
      const emw = n(d.estimatedMinutesWatched);
      const avgDur = n(d.averageViewDuration);
      const avgPct = n(d.averageViewPercentage);
      const engaged = n(d.engagedViews);
      return {
        id,
        label,
        views,
        estimatedMinutesWatched: emw,
        averageViewDuration: avgDur,
        averageViewPercentage: avgPct,
        engagedViews: engaged,
        sortValue: METRICS[metric].valueOf(d),
      };
    });



    const tViews = rawRows.reduce((s, r) => s + r.views, 0);
    const tEmw = rawRows.reduce((s, r) => s + r.estimatedMinutesWatched, 0);
    const tEng = rawRows.reduce((s, r) => s + r.engagedViews, 0);

    const wAvgDur =
      tViews > 0 ? rawRows.reduce((s, r) => s + r.averageViewDuration * r.views, 0) / tViews : 0;
    const wAvgPct =
      tViews > 0 ? rawRows.reduce((s, r) => s + r.averageViewPercentage * r.views, 0) / tViews : 0;

    const sortedRows = rawRows
      .map((r) => ({
        ...r,
        viewsPct: tViews > 0 ? (r.views / tViews) * 100 : 0,
        emwPct: tEmw > 0 ? (r.estimatedMinutesWatched / tEmw) * 100 : 0,
        engagedPct: tEng > 0 ? (r.engagedViews / tEng) * 100 : 0,
      }))
      .sort((a, b) => b.sortValue - a.sortValue);

    return {
      totals: {
        views: tViews,
        estimatedMinutesWatched: tEmw,
        averageViewDuration: wAvgDur,
        averageViewPercentage: wAvgPct,
        engagedViews: tEng,
      },
      rows: sortedRows,
    };
  }, [tsData, metric]);


  /* === Source filter state (affects charts only) === */
  const [selectedSources, setSelectedSources] = useState([]); // ids
  const allSourceItems = useMemo(
    () => rows.map(r => ({ id: String(r.id), label: r.label || String(r.id) })),
    [rows]
  );
  const sourceFilterActive = selectedSources.length > 0;
  const includeSource = useCallback(
    (srcId) => (!sourceFilterActive ? true : selectedSources.includes(String(srcId))),
    [sourceFilterActive, selectedSources]
  );

  // ---- Top-5 LINE/BAR----
  const top5IdsForCharts = useMemo(() => {
    if (chartType === "pie") return [];
    if (Array.isArray(tsSeries) && tsSeries.length) {
      const agg = new Map(); // source -> sum(metric)
      for (const it of tsSeries) {
        const s = String(it.source || "Unknown");
        const v = n(METRICS[metric].valueOf(it));
        agg.set(s, (agg.get(s) || 0) + v);
      }
      return Array.from(agg.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([id]) => String(id));
    }
    // fallback theo bảng tổng hợp (rows)
    return rows.slice(0, 5).map(r => String(r.id));
  }, [chartType, tsSeries, metric, rows]);

  const includeSourceForCharts = useCallback(
    (srcId) => {
      // Nếu người dùng đã chọn filter -> tôn trọng lựa chọn
      if (sourceFilterActive) return selectedSources.includes(String(srcId));
      // Mặc định với LINE/BAR chỉ hiển thị Top-5
      if (chartType !== "pie") return top5IdsForCharts.includes(String(srcId));
      // Pie giữ nguyên: hiển thị tất cả
      return true;
    },
    [sourceFilterActive, selectedSources, chartType, top5IdsForCharts]
  );

  /* === Color map (stable across charts + table) === */
  const seriesIdsForPalette = useMemo(() => {
    const ids = new Set(rows.map(r => String(r.id)));
    for (const it of (tsSeries || [])) ids.add(String(it.source || "Unknown"));
    return Array.from(ids);
  }, [rows, tsSeries]);

  const colorMap = useMemo(() => makeDistinctPalette(seriesIdsForPalette), [seriesIdsForPalette]);

  const top5Ids = useMemo(() => rows.slice(0, 5).map(r => String(r.id)), [rows]);

  const tablePaperSx = useMemo(
    () => ({
      mt: 1,
      borderRadius: 3,
      border: "1px solid",
      borderColor:
        theme.palette.mode === "dark"
          ? "rgba(148,163,184,0.22)"
          : "rgba(15,23,42,0.12)",
      background:
        theme.palette.mode === "dark"
          ? "rgba(10,15,24,0.82)"
          : "rgba(255,255,255,0.94)",
      boxShadow:
        theme.palette.mode === "dark"
          ? "0 14px 28px rgba(15,23,42,0.4)"
          : "0 14px 26px rgba(148,163,184,0.25)",
      overflow: "auto",
    }),
    [theme.palette.mode]
  );

  const tableHeadSx = useMemo(
    () => ({
      background:
        theme.palette.mode === "dark"
          ? "rgba(15,23,42,0.9)"
          : "rgba(226,232,240,0.85)",
      "& .MuiTableCell-root": {
        fontWeight: 700,
        textTransform: "uppercase",
        letterSpacing: "0.08em",
        fontSize: "0.72rem",
        color:
          theme.palette.mode === "dark"
            ? "rgba(226,232,240,0.85)"
            : "rgba(15,23,42,0.75)",
      },
    }),
    [theme.palette.mode]
  );



  /* === Pie data (filtered by selectedSources) === */
  let pieData = useMemo(() => {
    const src = Array.isArray(tsData) ? tsData : [];
    return src
      .map((d, i) => {
        const id = String(d.id ?? d.label ?? d.insightTrafficSourceType ?? `item-${i}`);
        const label = d.label ?? d.insightTrafficSourceType ?? `item-${i}`;
        const value = mconf.valueOf(d);
        return { id, label, value };
      })
      .filter((d) => n(d.value) > 0);
  }, [tsData, mconf]);
  pieData = useMemo(() => pieData.filter(d => includeSource(d.id)), [pieData, includeSource]);
  const pieTotal = useMemo(() => pieData.reduce((s, d) => s + n(d.value), 0), [pieData]);

  const PieTooltip = ({ datum }) => {
    const pct = pieTotal > 0 ? ((datum.value / pieTotal) * 100).toFixed(1) : "0.0";
    const fmt =
      metric === "averageViewPercentage"
        ? `${n(datum.value).toFixed(2)}%`
        : metric === "averageViewDuration"
          ? formatSeconds(datum.value)
          : formatNumber(datum.value);
    return (
      <Box
        sx={{
          px: 1.25, py: 0.75, borderRadius: 1, boxShadow: 3, fontSize: 13, fontWeight: 600,
          color: theme.palette.mode === "dark" ? theme.palette.grey[100] : theme.palette.grey[900],
          bgcolor: theme.palette.mode === "dark" ? "rgba(0,0,0,0.75)" : "rgba(255,255,255,0.95)",
          border: `1px solid ${theme.palette.mode === "dark" ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.08)"}`
        }}
      >
        <div style={{ marginBottom: 4 }}>{datum.label}</div>
        <div>{METRICS[metric].label}: {fmt}</div>
        <div>%: {pct}%</div>
      </Box>
    );
  };

  const getSourceDisplayName = useCallback(
    (src) => {
      const hit = rows.find((r) => r.id === src);
      return (hit && (hit.label || hit.id)) || src || "Unknown";
    },
    [rows]
  );

  /* === Line series (filtered) === */
  const lineSeries = useMemo(() => {
    if (chartType !== "line") return [];
    const per = new Map();
    const EPS = 1e-9;

    for (const it of tsSeries) {
      const src = String(it.source || "Unknown");
      const yNum = n(METRICS[metric].valueOf(it));
      if (!per.has(src)) per.set(src, { data: [], hasNonZero: false });

      const d = toUTCDate(it.bucket) || new Date(it.bucket);
      const item = { x: d, y: yNum, source: src, sourceLabel: getSourceDisplayName(src) };
      const acc = per.get(src);
      acc.data.push(item);
      if (Math.abs(yNum) > EPS && Number.isFinite(yNum)) acc.hasNonZero = true;
    }
    for (const s of per.values()) s.data.sort((a, b) => +a.x - +b.x);

    return Array.from(per.entries())
      .filter(([, s]) => s.hasNonZero)
      .map(([id, s]) => ({ id: String(id), data: s.data }))
      .filter(s => includeSourceForCharts(s.id));
  }, [chartType, tsSeries, metric, getSourceDisplayName, includeSourceForCharts]);

  const lineDateTicks = useMemo(() => {
    if (!Array.isArray(lineSeries) || lineSeries.length === 0) return [];
    const uniq = new Map();
    for (const s of lineSeries) for (const p of s.data) uniq.set(+p.x, p.x);
    const all = Array.from(uniq.values()).sort((a, b) => +a - +b);
    const MAX = 7;
    if (all.length <= MAX) return all;
    const step = (all.length - 1) / (MAX - 1);
    const picks = [];
    for (let i = 0; i < MAX; i++) picks.push(all[Math.round(i * step)]);
    return Array.from(new Map(picks.map(d => [+d, d])).values());
  }, [lineSeries]);

  /* === Bar data (filtered) === */
  const barPrep = useMemo(() => {
    if (chartType !== "bar") return { data: [], keys: [] };
    const buckets = new Map(); // bucket -> Map(source -> value)
    const sources = new Set();

    for (const it of tsSeries) {
      const b = String(it.bucket);
      const s = String(it.source || "Unknown");
      if (!includeSourceForCharts(s)) continue;
      const yVal = n(METRICS[metric].valueOf(it));
      sources.add(s);
      if (!buckets.has(b)) buckets.set(b, new Map());
      buckets.get(b).set(s, (buckets.get(b).get(s) || 0) + yVal);
    }

    const sortedBuckets = Array.from(buckets.keys()).sort((a, b) => new Date(a) - new Date(b));
    const keys = Array.from(sources.values()).sort();
    const data = sortedBuckets.map((b) => {
      const row = { bucket: b };
      for (const k of keys) row[k] = buckets.get(b).get(k) || 0;
      return row;
    });
    return { data, keys };
  }, [chartType, tsSeries, metric, includeSourceForCharts]);

  const barXTicks = useMemo(() => {
    const xs = (barPrep.data || []).map((d) => d.bucket);
    if (xs.length <= 7) return xs;
    const step = (xs.length - 1) / 6;
    const picks = [];
    for (let i = 0; i < 7; i++) picks.push(xs[Math.round(i * step)]);
    return Array.from(new Set(picks));
  }, [barPrep.data]);

  /* === Center label for Pie === */
  const CenterLabel = ({ centerX, centerY }) => (
    <g transform={`translate(${centerX}, ${centerY})`}>
      <text
        textAnchor="middle"
        dominantBaseline="central"
        style={{
          fontSize: 12,
          fill: theme.palette.mode === "dark" ? theme.palette.grey[300] : theme.palette.grey[700],
          fontWeight: 600,
        }}
        y={-8}
      >
        {METRICS[metric].label}
      </text>
      <text
        textAnchor="middle"
        dominantBaseline="central"
        style={{
          fontSize: 16,
          fill: theme.palette.mode === "dark" ? theme.palette.grey[100] : theme.palette.grey[900],
          fontWeight: 800,
        }}
        y={12}
      >
        {metric === "averageViewPercentage"
          ? `${pieTotal.toFixed(2)}`
          : metric === "averageViewDuration"
            ? formatSeconds(pieTotal)
            : formatNumber(pieTotal)}
      </text>
    </g>
  );

  /* === UI === */
  return (
    <Stack spacing={1.5}>
      {/* Controls (NO source filter here) */}
      <Stack direction="row" alignItems="center" spacing={2} sx={{ px: 1, flexWrap: "wrap", rowGap: 1.25 }}>
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel id="chart-type-label">Chart</InputLabel>
          <Select labelId="chart-type-label" value={chartType} label="Chart" onChange={(e) => setChartType(e.target.value)}>
            <MenuItem value="pie">Pie</MenuItem>
            <MenuItem value="line">Line</MenuItem>
            <MenuItem value="bar">Bar</MenuItem>
          </Select>
        </FormControl>

        {chartType !== "pie" && (
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel id="interval-select-label">Interval</InputLabel>
            <Select labelId="interval-select-label" value={interval} label="Interval" onChange={(e) => setInterval(e.target.value)}>
              <MenuItem value="daily">Daily</MenuItem>
              <MenuItem value="weekly">Weekly</MenuItem>
              <MenuItem value="monthly">Monthly</MenuItem>
              <MenuItem value="yearly">Yearly</MenuItem>
            </Select>
          </FormControl>
        )}

        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel id="metric-select-label">Metric</InputLabel>
          <Select labelId="metric-select-label" value={metric} label="Metric" onChange={(e) => setMetric(e.target.value)}>
            {METRIC_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
            ))}
          </Select>
        </FormControl>

        <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75, minWidth: 280 }}>
          <FormControl size="small">
            <InputLabel id="period-select-label">Period</InputLabel>
            <Select labelId="period-select-label" value={period} label="Period" onChange={(e) => setPeriod(e.target.value)}>
              {[...PERIOD_OPTIONS, ...EXTRA_PERIODS].map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
              ))}
            </Select>
          </FormControl>

          {period === "custom" && (
            <LocalizationProvider dateAdapter={AdapterDayjs} adapterLocale="en">
              <Paper variant="outlined" sx={{ p: 0.5, display: "flex", alignItems: "center", gap: 1, borderRadius: 1 }}>
                <DatePicker
                  label="Start date"
                  value={startDate ? dayjs(startDate) : null}
                  onChange={(v) => setStartDate(v ? v.format("YYYY-MM-DD") : "")}
                  format="DD-MM-YYYY"
                  disableFuture
                  maxDate={endDate ? dayjs(endDate) : dayjs()}
                  slotProps={{ textField: { size: "small", sx: { width: 170 } } }}
                />
                <DatePicker
                  label="End date"
                  value={endDate ? dayjs(endDate) : null}
                  onChange={(v) => setEndDate(v ? v.format("YYYY-MM-DD") : "")}
                  format="DD-MM-YYYY"
                  disableFuture
                  minDate={startDate ? dayjs(startDate) : undefined}
                  slotProps={{ textField: { size: "small", sx: { width: 170 } } }}
                />
              </Paper>
            </LocalizationProvider>
          )}
        </Box>

        <FormControl size="small" sx={{ minWidth: 260, ml: "auto" }}>
          <InputLabel id="channel-select-label">Channel</InputLabel>
          <Select
            labelId="channel-select-label"
            value={channels.some((opt) => opt.value === channel) ? channel : ""}
            label="Channel"
            onChange={(e) => setChannel(e.target.value)}
          >
            {channels.length === 0 ? (
              <MenuItem value="" disabled>(Không tìm thấy channel nào)</MenuItem>
            ) : (
              channels.map((opt) => <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>)
            )}
          </Select>
        </FormControl>

        {errorMsg && <Typography variant="body2" color="error">{errorMsg}</Typography>}
      </Stack>

      {/* CHART AREA */}
      <Box sx={{ height: 420 }}>
        {chartType === "pie" && (
          <ResponsivePie
            debounceResize={150}
            data={pieData}
            colors={(d) => colorMap[String(d.id)] ?? "#888"}
            borderWidth={1}
            borderColor={{ from: "color", modifiers: [["darker", 0.2]] }}
            margin={{ top: 30, right: 24, bottom: 60, left: 24 }}
            innerRadius={0.55}
            padAngle={0.7}
            cornerRadius={3}
            activeOuterRadiusOffset={8}
            valueFormat={(v) =>
              metric === "averageViewPercentage"
                ? `${n(v).toFixed(2)}%`
                : metric === "averageViewDuration"
                  ? formatSeconds(v)
                  : formatNumber(v)
            }
            sortByValue
            enableArcLinkLabels
            arcLinkLabelsSkipAngle={8}
            arcLinkLabelsTextColor={theme.palette.mode === "dark" ? "#eee" : "#111"}
            arcLinkLabelsThickness={2}
            arcLinkLabelsColor={{ from: "color" }}
            enableArcLabels
            arcLabelsRadiusOffset={0.42}
            arcLabelsSkipAngle={10}
            arcLabelsComponent={() => (
              <text
                textAnchor="middle"
                dominantBaseline="central"
                style={{
                  fontSize: 10.5,
                  fontWeight: 700,
                  fill: theme.palette.mode === "dark" ? "rgba(255,255,255,0.92)" : "rgba(0,0,0,0.82)",
                  paintOrder: "stroke",
                  strokeWidth: 3,
                  stroke: theme.palette.mode === "dark" ? "rgba(0,0,0,0.45)" : "rgba(255,255,255,0.9)",
                }}
              />
            )}
            tooltip={PieTooltip}
            theme={{
              background: "transparent",
              textColor: theme.palette.mode === "dark" ? "#eee" : "#111",
            }}
            motionConfig="gentle"
            legends={[]} // hidden, using table as legend
            layers={["arcs", "arcLabels", "arcLinkLabels", "legends", CenterLabel]}
          />
        )}

        {chartType === "line" && (
          <ResponsiveLine
            debounceResize={150}
            data={lineSeries}
            colors={({ id }) => colorMap[String(id)] ?? "#888"}
            margin={{ top: 30, right: 24, bottom: 70, left: 60 }}
            xScale={{ type: "time", format: "%d-%m-%Y", useUTC: true, precision: "day" }}
            xFormat="time:%d-%m-%Y"
            axisBottom={{
              format: "%d-%m-%Y",
              tickRotation: 0,
              tickPadding: 10,
              tickSize: 0,
              tickValues: lineDateTicks,
              renderTick: (tick) => {
                const raw =
                  tick.format && tick.value
                    ? tick.format(tick.value)
                    : tick.value instanceof Date
                      ? `${String(tick.value.getUTCDate()).padStart(2, "0")}-${String(tick.value.getUTCMonth() + 1).padStart(2, "0")}-${tick.value.getUTCFullYear()}`
                      : String(tick.value);
                const xLabelColor = theme.palette.mode === "dark" ? "#e5e7eb" : "#334155";
                return (
                  <g transform={`translate(${tick.x},${tick.y})`} style={{ pointerEvents: "none" }}>
                    <text y={6} textAnchor="middle" dominantBaseline="hanging" style={{ fill: xLabelColor, fontSize: 12, fontWeight: 600, letterSpacing: 0.2 }}>
                      {raw}
                    </text>
                  </g>
                );
              },
            }}
            yScale={{ type: "linear", stacked: false, min: 0 }}
            enableArea
            areaOpacity={0.15}
            enableGridX={false}
            enableGridY
            pointSize={6}
            useMesh
            enableSlices="x"
            sliceTooltip={({ slice }) => {
              const p0 = slice.points[0];
              const dateLabel =
                typeof p0?.data?.xFormatted === "string"
                  ? p0.data.xFormatted
                  : p0?.data?.x instanceof Date
                    ? new Intl.DateTimeFormat("vi-VN").format(p0.data.x)
                    : String(p0?.data?.x ?? "");

              const colorOf = (p) =>
                colorMap[String(p.serieId)]         // ưu tiên màu trong palette ổn định
                ?? p.color                          // fallback khác của Nivo

              return (
                <Box sx={{
                  px: 1.25, py: 1, minWidth: 220, borderRadius: 1.25,
                  border: `1px solid ${theme.palette.divider}`, boxShadow: 3,
                  bgcolor: theme.palette.mode === "dark" ? "rgba(17,17,17,0.9)" : "rgba(255,255,255,0.98)",
                  fontSize: 14, lineHeight: 1.25, fontVariantNumeric: "tabular-nums"
                }}>
                  <Box sx={{ color: "text.secondary", mb: 0.75 }}>{dateLabel}</Box>

                  {slice.points.map(p => {
                    const name = p.data.sourceLabel || p.serieId || "Unknown";
                    const valueStr =
                      metric === "averageViewPercentage"
                        ? `${n(p.data.yFormatted).toFixed(2)}%`
                        : metric === "averageViewDuration"
                          ? formatSeconds(p.data.yFormatted)
                          : formatNumber(p.data.yFormatted);

                    return (
                      <Box key={p.id} sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.25 }}>
                        <span
                          style={{
                            width: 10, height: 10, borderRadius: 2,
                            background: colorOf(p), display: "inline-block"
                          }}
                        />
                        <b style={{ fontSize: 12, flex: 1 }}>{String(name)}</b>
                        <span>{valueStr}</span>
                      </Box>
                    );
                  })}
                </Box>
              );
            }}

          />
        )}

        {chartType === "bar" && (
          <ResponsiveBar
            debounceResize={150}
            data={barPrep.data}
            keys={barPrep.keys}
            indexBy="bucket"
            colors={({ id }) => colorMap[String(id)] ?? "#888"}
            margin={{ top: 30, right: 24, bottom: 60, left: 60 }}
            padding={0.2}
            valueScale={{ type: "linear" }}
            indexScale={{ type: "band", round: true }}
            axisBottom={{
              tickRotation: 0,
              tickValues: barXTicks,
              renderTick: (tick) => {
                const raw =
                  tick.format && tick.value
                    ? tick.format(tick.value)
                    : tick.value instanceof Date
                      ? new Intl.DateTimeFormat("sv-SE").format(tick.value)
                      : String(tick.value);
                const xLabelColor = theme.palette.mode === "dark" ? "#e5e7eb" : "#334155";
                return (
                  <g transform={`translate(${tick.x},${tick.y})`} style={{ pointerEvents: "none" }}>
                    <text y={6} textAnchor="middle" dominantBaseline="hanging" style={{ fill: xLabelColor, fontSize: 12, fontWeight: 600, letterSpacing: 0.2 }}>
                      {raw}
                    </text>
                  </g>
                );
              },
            }}
            enableGridX={false}
            labelSkipWidth={12}
            labelSkipHeight={12}
            tooltip={({ id, value, indexValue }) => (
              <Box sx={{ px: 1, py: 0.5, borderRadius: 1, boxShadow: 3, bgcolor: theme.palette.mode === "dark" ? "rgba(0,0,0,0.75)" : "rgba(255,255,255,0.95)" }}>
                <div><b>{String(id)}</b></div>
                <div>{String(indexValue)}</div>
                <div>
                  {metric === "averageViewPercentage"
                    ? `${n(value).toFixed(2)}%`
                    : metric === "averageViewDuration"
                      ? formatSeconds(value)
                      : formatNumber(value)}
                </div>
              </Box>
            )}
            legends={[]}
          />
        )}
      </Box>

      {/* TABLE */}
      <TableContainer
        component={Paper}
        elevation={0}
        sx={tablePaperSx}
      >
        <Table size="small" stickyHeader sx={{ minWidth: 1120 }}>
          <TableHead sx={tableHeadSx}>
            <TableRow>
              {/* Header Source + inline Select filter */}
              <TableCell sx={{ fontWeight: 700, whiteSpace: "nowrap" }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                  <span>Source</span>
                  <FormControl
                    size="small"
                    variant="standard"
                    sx={{
                      minWidth: 140,
                      "& .MuiInputBase-root": { fontSize: 12, fontWeight: 500 },
                    }}
                  >

                    <Select
                      labelId="source-select-label-inline"
                      multiple
                      value={selectedSources}
                      onChange={(e) => setSelectedSources(e.target.value)}
                      renderValue={(selected) => {
                        if (!selected?.length) return "All";
                        const names = selected
                          .map(id => allSourceItems.find(x => x.id === id)?.label || id)
                          .slice(0, 2)
                          .join(", ");
                        return selected.length > 2 ? `${names} (+${selected.length - 2})` : names;
                      }}
                      displayEmpty
                      disableUnderline
                      sx={{
                        "& .MuiSelect-select": { py: 0.2, px: 0.8 },
                        borderRadius: 1,
                        border: (t) => `1px solid ${t.palette.divider}`,
                        bgcolor: "background.paper",
                      }}
                      MenuProps={{ PaperProps: { style: { maxHeight: 360 } } }}
                    >
                      {/* Menu Item */}
                      <MenuItem
                        value="ALL"
                      >
                        <Box sx={{ display: "flex", alignItems: "center", width: "100%" }}>
                          {/* Bên trái: checkbox + nhãn (All) */}
                          <Box sx={{ display: "flex", alignItems: "center", flex: 1, minWidth: 0 }}>
                            <Checkbox
                              size="small"
                              checked={selectedSources.length === 0}
                              indeterminate={selectedSources.length > 0}
                              tabIndex={-1}
                              disableRipple
                                sx={{
                                  mr: 0.5,
                                  color: "#ffffff",
                                  "&.Mui-checked": {
                                    color: "#ffffff !important",
                                  },
                                  "&.MuiCheckbox-indeterminate": {
                                    color: "#ffffff !important",
                                  },
                                }}
                            />
                            <ListItemText
                              primary="(All)"
                              slotProps={{ primary: { sx: { fontSize: 13 } } }}
                            />
                          </Box>

                          {/* Clear select button */}
                          <Button
                            size="small"
                            variant="text"
                            onClick={(e) => {

                              e.preventDefault();
                              e.stopPropagation();
                              setSelectedSources([]);

                            }}
                            sx={(t) => ({
                              color: t.palette.mode === "dark" ? t.palette.info.light : t.palette.info.main,
                              "&:hover": { color: t.palette.info.dark, backgroundColor: "transparent" },
                            })}
                          >
                            Clear
                          </Button>
                        </Box>
                      </MenuItem>




                      {allSourceItems.map((opt) => {
                        const checked = selectedSources.indexOf(opt.id) > -1;
                        return (
                          <MenuItem key={opt.id} value={opt.id} dense>
                            <Checkbox
                              size="small"
                              checked={checked}
                              tabIndex={-1}
                              disableRipple
                              sx={{
                                mr: 1,
                                color: "#ffffff",        
                                "&.Mui-checked": {
                                  color: "#ffffff !important",
                                },
                              }}
                            />
                            {/* chấm màu để khớp chart */}
                            <span
                              style={{
                                width: 10,
                                height: 10,
                                borderRadius: 3,
                                display: "inline-block",
                                marginRight: 8,
                                background: colorMap[String(opt.id)] ?? "#00c8ff", // fallback cũng dùng cùng tông
                              }}
                            />

                            <ListItemText
                              primary={opt.label}
                              slotProps={{ primary: { sx: { fontSize: 13 } } }}
                            />
                          </MenuItem>
                        );
                      })}

                    </Select>
                  </FormControl>

                </Box>
              </TableCell>

              <TableCell align="right" sx={{ fontWeight: 700 }}>Views</TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>Estimated Minutes</TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>Avg View Duration</TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>Avg View %</TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>Engaged Views</TableCell>
            </TableRow>
          </TableHead>

          <TableBody>
            <TableRow>
              <TableCell sx={{ fontWeight: 900 }}>Total</TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>{formatNumber(totals.views)}</TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>{formatNumber(totals.estimatedMinutesWatched)}</TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>{formatSeconds(totals.averageViewDuration)}</TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>{formatPercent(totals.averageViewPercentage)}</TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>{formatNumber(totals.engagedViews)}</TableCell>
            </TableRow>
            {rows.map((r) => (
              <TableRow
                key={r.id}
                sx={{
                  transition: "transform 0.2s ease, background-color 0.2s ease",
                  "&:hover": {
                    backgroundColor:
                      theme.palette.mode === "dark"
                        ? "rgba(51,65,85,0.55)"
                        : "rgba(226,232,240,0.6)",
                    transform: "translateY(-1px)",
                  },
                }}
              >
                <TableCell>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    {top5Ids.includes(String(r.id)) && (
                      <span
                        style={{
                          width: 10,
                          height: 10,
                          borderRadius: 3,
                          display: "inline-block",
                          background: colorMap[String(r.id)] ?? "#888",
                        }}
                      />
                    )}
                    <span
                      style={{
                        fontWeight: top5Ids.includes(String(r.id)) ? 700 : 500,
                        color: top5Ids.includes(String(r.id))
                          ? (theme.palette.mode === "dark" ? "#e5e7eb" : "#111827")
                          : "inherit",
                      }}
                    >
                      {r.label}
                    </span>
                  </Box>
                </TableCell>
                <TableCell align="right">{formatNumber(r.views)}</TableCell>
                <TableCell align="right">{formatNumber(r.estimatedMinutesWatched)}</TableCell>
                <TableCell align="right">{formatSeconds(r.averageViewDuration)}</TableCell>
                <TableCell align="right">{formatPercent(r.averageViewPercentage)}</TableCell>
                <TableCell align="right">{formatNumber(r.engagedViews)}</TableCell>
              </TableRow>
            ))}
            <TableRow>
              <TableCell sx={{ fontWeight: 700 }}>Total</TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>
                {formatNumber(totals.views)}
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>
                {formatNumber(totals.estimatedMinutesWatched)}
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>
                {formatSeconds(totals.averageViewDuration)}
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>
                {formatNumber(totals.engagedViews)}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
};

export default TrafficSourceChart;
