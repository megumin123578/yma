// src/components/TrafficSource.jsx
import React, { useMemo, useState, useEffect, useCallback, useRef } from "react";
import { useTheme } from "@mui/material/styles";
import {
  Box,
  Stack,
  Typography,
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
  Divider,
} from "@mui/material";
import { motion, AnimatePresence } from "framer-motion";
import BarChartIcon from "@mui/icons-material/BarChart";
import CalendarMonthIcon from "@mui/icons-material/CalendarMonth";
import YouTubeIcon from "@mui/icons-material/YouTube";
import PieChartIcon from "@mui/icons-material/PieChart";
import TimelineIcon from "@mui/icons-material/Timeline";

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
  const isDark = theme.palette.mode === "dark";
  const chartRef = useRef(null);

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
        const ordered = order.map((name) => byId.get(orderKey(name))).filter(Boolean);
        const remaining = norm.filter((c) => !order.map(orderKey).includes(orderKey(c.value)));
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

  const currentRange = useMemo(() => {
    const isCustom = period === "custom";
    const now = new Date();
    return isCustom ? { start: startDate, end: endDate } : computeRange(period, now);
  }, [period, startDate, endDate, computeRange]);

  useEffect(() => {
    if (!channel) return;
    const { start, end } = currentRange;
    if (period === "custom" && (!start || !end)) return;
    if (!start || !end) {
      setErrorMsg("Hãy chọn thời gian hợp lệ.");
      return;
    }
    fetchRange(start, end);
    if (chartType !== "pie") fetchTimeseries(start, end, interval);
  }, [chartType, period, channel, interval, startDate, endDate, currentRange, fetchRange, fetchTimeseries]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(
        FILTERS_STORAGE_KEY,
        JSON.stringify({ chartType, metric, period, interval, channel, startDate, endDate })
      );
    } catch (e) { }
  }, [chartType, metric, period, interval, channel, startDate, endDate]);

  /* === Table aggregation === */
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
        id, label, views, estimatedMinutesWatched: emw,
        averageViewDuration: avgDur, averageViewPercentage: avgPct, engagedViews: engaged,
        sortValue: mconf.valueOf(d),
      };
    });

    const tViews = rawRows.reduce((s, r) => s + r.views, 0);
    const tEmw = rawRows.reduce((s, r) => s + r.estimatedMinutesWatched, 0);
    const tEng = rawRows.reduce((s, r) => s + r.engagedViews, 0);
    const wAvgDur = tViews > 0 ? rawRows.reduce((s, r) => s + r.averageViewDuration * r.views, 0) / tViews : 0;
    const wAvgPct = tViews > 0 ? rawRows.reduce((s, r) => s + r.averageViewPercentage * r.views, 0) / tViews : 0;

    const sortedRows = rawRows
      .map((r) => ({
        ...r,
        viewsPct: tViews > 0 ? (r.views / tViews) * 100 : 0,
        emwPct: tEmw > 0 ? (r.estimatedMinutesWatched / tEmw) * 100 : 0,
        engagedPct: tEng > 0 ? (r.engagedViews / tEng) * 100 : 0,
      }))
      .sort((a, b) => b.sortValue - a.sortValue);

    return {
      totals: { views: tViews, estimatedMinutesWatched: tEmw, averageViewDuration: wAvgDur, averageViewPercentage: wAvgPct, engagedViews: tEng },
      rows: sortedRows,
    };
  }, [tsData, mconf]);

  const [selectedSources] = useState([]);
  const sourceFilterActive = selectedSources.length > 0;

  const includeSourceForCharts = useCallback(
    (srcId) => {
      if (sourceFilterActive) return selectedSources.includes(String(srcId));
      if (chartType === "pie") return true;
      // Top 5 fallback
      const top5 = rows.slice(0, 5).map(r => String(r.id));
      return top5.includes(String(srcId));
    },
    [sourceFilterActive, selectedSources, chartType, rows]
  );

  const getSourceDisplayName = useCallback((id) => {
    const r = rows.find(x => String(x.id) === String(id));
    return r?.label || id;
  }, [rows]);

  const seriesIdsForPalette = useMemo(() => {
    const ids = new Set(rows.map(r => String(r.id)));
    for (const it of (tsSeries || [])) ids.add(String(it.source || "Unknown"));
    return Array.from(ids);
  }, [rows, tsSeries]);

  const colorMap = useMemo(() => makeDistinctPalette(seriesIdsForPalette, { useDark: theme.palette.mode === "dark" }), [seriesIdsForPalette, theme.palette.mode]);

  /* === Line Series with Padding and Alignment === */
  const lineSeries = useMemo(() => {
    if (chartType !== "line") return [];

    // 1. All dates in tsSeries
    const allDatesSet = new Set();
    tsSeries.forEach(it => {
      const d = toUTCDate(it.bucket) || new Date(it.bucket);
      if (d) allDatesSet.add(d.getTime());
    });
    const allDatesSorted = Array.from(allDatesSet).sort((a, b) => a - b).map(t => new Date(t));

    const per = new Map();
    const EPS = 1e-9;

    for (const it of tsSeries) {
      const src = String(it.source || "Unknown");
      const yNum = n(mconf.valueOf(it));
      if (!per.has(src)) per.set(src, new Map());
      const d = toUTCDate(it.bucket) || new Date(it.bucket);
      if (d) per.get(src).set(d.getTime(), yNum);
    }

    const result = [];
    for (const [src, dataMap] of per.entries()) {
      let nonZero = false;
      const data = allDatesSorted.map(d => {
        const y = dataMap.get(d.getTime()) || 0;
        if (Math.abs(y) > EPS) nonZero = true;
        return { x: d, y, source: src, sourceLabel: getSourceDisplayName(src) };
      });
      if (nonZero && includeSourceForCharts(src)) {
        result.push({ id: src, data });
      }
    }
    return result;
  }, [chartType, tsSeries, mconf, getSourceDisplayName, includeSourceForCharts]);

  const lineDateExtent = useMemo(() => {
    if (!lineSeries.length || !lineSeries[0].data.length) return { min: "auto", max: "auto" };
    const first = lineSeries[0].data[0].x;
    const last = lineSeries[0].data[lineSeries[0].data.length - 1].x;
    return { min: first, max: last };
  }, [lineSeries]);

  const lineDateTicks = useMemo(() => {
    const all = [];
    lineSeries.forEach(s => s.data.forEach(p => all.push(p.x)));
    const uniq = Array.from(new Set(all.map(d => d.getTime()))).sort().map(t => new Date(t));
    if (uniq.length <= 7) return uniq;
    const step = (uniq.length - 1) / 6;
    const picks = [];
    for (let i = 0; i < 7; i++) picks.push(uniq[Math.round(i * step)]);
    return picks;
  }, [lineSeries]);

  const barPrep = useMemo(() => {
    if (chartType !== "bar") return { data: [], keys: [] };
    const buckets = new Map();
    const sources = new Set();
    for (const it of tsSeries) {
      const b = String(it.bucket);
      const s = String(it.source || "Unknown");
      if (!includeSourceForCharts(s)) continue;
      const yVal = n(mconf.valueOf(it));
      sources.add(s);
      if (!buckets.has(b)) buckets.set(b, new Map());
      buckets.get(b).set(s, (buckets.get(b).get(s) || 0) + yVal);
    }
    const sortedB = Array.from(buckets.keys()).sort((a, b) => new Date(a) - new Date(b));
    const keys = Array.from(sources).sort();
    const data = sortedB.map(b => {
      const row = { bucket: b };
      for (const k of keys) row[k] = buckets.get(b).get(k) || 0;
      return row;
    });
    return { data, keys };
  }, [chartType, tsSeries, mconf, includeSourceForCharts]);

  const barXTicks = useMemo(() => {
    const xs = barPrep.data.map(d => d.bucket);
    if (xs.length <= 7) return xs;
    const step = (xs.length - 1) / 6;
    const picks = [];
    for (let i = 0; i < 7; i++) picks.push(xs[Math.round(i * step)]);
    return picks;
  }, [barPrep.data]);

  const CenterLabel = ({ centerX, centerY }) => (
    <g transform={`translate(${centerX}, ${centerY})`}>
      <text textAnchor="middle" dominantBaseline="central" style={{ fontSize: 12, fill: theme.palette.text.secondary, fontWeight: 600 }} y={-8}>
        {mconf.label}
      </text>
      <text textAnchor="middle" dominantBaseline="central" style={{ fontSize: 16, fill: theme.palette.text.primary, fontWeight: 800 }} y={12}>
        {metric === "averageViewPercentage" ? `${totals.averageViewPercentage.toFixed(2)}` : metric === "averageViewDuration" ? formatSeconds(totals.averageViewDuration) : formatNumber(totals.views)}
      </text>
    </g>
  );

  const glassSx = useMemo(() => ({
    bgcolor: isDark ? "rgba(15, 23, 42, 0.65)" : "rgba(255, 255, 255, 0.8)",
    backdropFilter: "blur(12px)",
    borderRadius: 4,
    border: "1px solid",
    borderColor: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)",
    boxShadow: isDark ? "0 8px 32px rgba(0,0,0,0.4)" : "0 8px 24px rgba(15,23,42,0.08)",
  }), [isDark]);

  const tablePaperSx = useMemo(() => ({
    ...glassSx,
    p: 1,
    overflow: "hidden",
  }), [glassSx]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
    >
      <Stack spacing={2}>
        {/* SELECTORS */}
        <Stack direction="row" alignItems="center" spacing={2} sx={{ flexWrap: "wrap", rowGap: 2 }}>
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <PieChartIcon sx={{ fontSize: 16 }} /> Chart
            </InputLabel>
            <Select value={chartType} label="Chart" onChange={(e) => setChartType(e.target.value)}>
              <MenuItem value="pie">Pie</MenuItem>
              <MenuItem value="line">Line</MenuItem>
              <MenuItem value="bar">Bar</MenuItem>
            </Select>
          </FormControl>

          {chartType !== "pie" && (
            <FormControl size="small" sx={{ minWidth: 140 }}>
              <InputLabel sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                <TimelineIcon sx={{ fontSize: 16 }} /> Interval
              </InputLabel>
              <Select value={interval} label="Interval" onChange={(e) => setInterval(e.target.value)}>
                <MenuItem value="daily">Daily</MenuItem>
                <MenuItem value="weekly">Weekly</MenuItem>
                <MenuItem value="monthly">Monthly</MenuItem>
              </Select>
            </FormControl>
          )}

          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <BarChartIcon sx={{ fontSize: 16 }} /> Metric
            </InputLabel>
            <Select value={metric} label="Metric" onChange={(e) => setMetric(e.target.value)}>
              {METRIC_OPTIONS.map(o => <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>)}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <CalendarMonthIcon sx={{ fontSize: 16 }} /> Period
            </InputLabel>
            <Select value={period} label="Period" onChange={(e) => setPeriod(e.target.value)}>
              {[...PERIOD_OPTIONS, ...EXTRA_PERIODS].map(o => <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>)}
            </Select>
          </FormControl>

          {period === "custom" && (
            <LocalizationProvider dateAdapter={AdapterDayjs}>
              <DatePicker label="Start" value={startDate ? dayjs(startDate) : null} onChange={v => setStartDate(v ? v.format("YYYY-MM-DD") : "")} slotProps={{ textField: { size: "small" } }} />
              <DatePicker label="End" value={endDate ? dayjs(endDate) : null} onChange={v => setEndDate(v ? v.format("YYYY-MM-DD") : "")} slotProps={{ textField: { size: "small" } }} />
            </LocalizationProvider>
          )}

          <FormControl size="small" sx={{ minWidth: 240 }}>
            <InputLabel sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <YouTubeIcon sx={{ fontSize: 16 }} /> Channel
            </InputLabel>
            <Select
              value={channel}
              label="Channel"
              onChange={e => setChannel(e.target.value)}
              renderValue={(v) => {
                const sel = channels.find(c => c.value === v);
                return sel ? sel.label : v;
              }}
            >
              {channels.map(c => <MenuItem key={c.value} value={c.value}>{c.label}</MenuItem>)}
            </Select>
          </FormControl>
        </Stack>

        {errorMsg && <Typography color="error" variant="body2" sx={{ px: 1 }}>{errorMsg}</Typography>}

        {/* CHART SECTION */}
        <Box
          sx={{
            ...glassSx,
            height: 480,
            p: 0.5,
            position: "relative",
            background: isDark
              ? `radial-gradient(circle at 50% 50%, rgba(30, 41, 59, 0.4) 0%, rgba(15, 23, 42, 1) 100%)`
              : `radial-gradient(circle at 50% 50%, #f8fafc 0%, #f1f5f9 100%)`,
          }}
        >
          {chartType === "pie" && (
            <ResponsivePie
              data={rows.filter(r => includeSourceForCharts(r.id)).map(r => ({ id: String(r.id), label: r.label, value: r.sortValue }))}
              colors={d => colorMap[d.id] || "#888"}
              margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
              innerRadius={0.6} padAngle={0} cornerRadius={2}
              activeOuterRadiusOffset={8}
              enableArcLabels={false}
              enableArcLinkLabels
              arcLinkLabelsSkipAngle={10}
              arcLinkLabelsTextColor={theme.palette.text.primary}
              arcLinkLabelsThickness={2}
              arcLinkLabelsColor={{ from: "color" }}
              layers={["arcs", "arcLabels", "arcLinkLabels", "legends", CenterLabel]}
              tooltip={({ datum }) => (
                <Box
                  sx={{
                    p: 1.5,
                    bgcolor: isDark ? "#111827" : "#ffffff",
                    border: "1px solid",
                    borderColor: "divider",
                    borderRadius: 2,
                    boxShadow: 4,
                    minWidth: 160
                  }}
                >
                  <Typography variant="subtitle2" fontWeight={800} color={isDark ? "#f8fafc" : "#0f172a"}>{datum.label}</Typography>
                  <Divider sx={{ my: 0.5, opacity: 0.1 }} />
                  <Typography variant="body2" sx={{ color: isDark ? "#94a3b8" : "#64748b" }}>
                    {mconf.label}: <strong style={{ color: isDark ? "#f8fafc" : "#0f172a" }}>{metric === "averageViewDuration" ? formatSeconds(datum.value) : formatNumber(datum.value)}</strong>
                  </Typography>
                </Box>
              )}
            />
          )}

          {chartType === "line" && (
            <Box ref={chartRef} sx={{ height: "100%" }}>
              <ResponsiveLine
                data={lineSeries}
                colors={d => colorMap[d.id] || "#888"}
                margin={{ top: 20, right: 20, bottom: 60, left: 60 }}
                xScale={{ type: "time", format: "native", useUTC: true, precision: "day", min: lineDateExtent.min, max: lineDateExtent.max }}
                yScale={{ type: "linear", min: 0, max: "auto" }}
                curve="monotoneX"
                axisBottom={{
                  format: "%d/%m",
                  tickValues: lineDateTicks,
                  tickPadding: 10,
                }}
                enablePoints={true}
                pointSize={8}
                pointColor="#fff"
                pointBorderWidth={2}
                pointBorderColor={{ from: "serieColor" }}
                useMesh
                enableSlices="x"
                sliceTooltip={({ slice }) => {
                  const isRight = chartRef.current && slice.x > chartRef.current.offsetWidth / 2;
                  return (
                    <Box sx={{
                      p: 1.5, borderRadius: 2.5, minWidth: 220,
                      bgcolor: isDark ? "rgba(11, 15, 25, 0.98)" : "rgba(255,255,255,0.98)",
                      border: "1px solid",
                      borderColor: isDark ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.08)",
                      boxShadow: isDark ? "0 12px 36px rgba(0,0,0,0.5)" : "0 8px 24px rgba(15,23,42,0.15)",
                      transform: isRight ? "translateX(-110%)" : "translateX(10%)", transition: "transform 0.1s"
                    }}>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>{dayjs(slice.points[0].data.x).format("DD/MM/YYYY")}</Typography>
                      {slice.points.map(p => (
                        <Box key={p.id} display="flex" alignItems="center" justifyContent="space-between" gap={2} mt={0.5}>
                          <Box display="flex" alignItems="center" gap={1}>
                            <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: p.color }} />
                            <Typography variant="body2" sx={{ fontSize: 13, fontWeight: 500 }}>{getSourceDisplayName(p.serieId)}</Typography>
                          </Box>
                          <Typography variant="body2" sx={{ fontSize: 13, fontWeight: 800 }}>
                            {metric === "averageViewPercentage" ? `${n(p.data.y).toFixed(2)}%` : metric === "averageViewDuration" ? formatSeconds(p.data.y) : formatNumber(p.data.y)}
                          </Typography>
                        </Box>
                      ))}
                    </Box>
                  )
                }}
                theme={{
                  axis: {
                    ticks: { text: { fontSize: 11, fill: theme.palette.text.secondary } },
                    domain: { line: { stroke: "transparent" } }
                  },
                  grid: { line: { stroke: isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)" } }
                }}
              />
            </Box>
          )}

          {chartType === "bar" && (
            <ResponsiveBar
              data={barPrep.data}
              keys={barPrep.keys}
              indexBy="bucket"
              colors={d => colorMap[d.id] || "#888"}
              margin={{ top: 30, right: 30, bottom: 60, left: 60 }}
              padding={0.3}
              borderRadius={4}
              axisBottom={{ format: v => dayjs(v).format("DD/MM"), tickValues: barXTicks }}
              labelSkipWidth={12}
              labelSkipHeight={12}
              enableGridY
              theme={{
                axis: { ticks: { text: { fontSize: 11, fill: theme.palette.text.secondary } } },
                grid: { line: { stroke: isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)" } }
              }}
              tooltip={({ id, value, indexValue }) => (
                <Box
                  sx={{
                    p: 1.5,
                    bgcolor: isDark ? "#111827" : "#ffffff",
                    border: "1px solid",
                    borderColor: "divider",
                    borderRadius: 2,
                    boxShadow: 4,
                    minWidth: 160
                  }}
                >
                  <Typography variant="caption" color="text.secondary" display="block">{dayjs(indexValue).format("DD/MM/YYYY")}</Typography>
                  <Typography variant="subtitle2" fontWeight={800}>{getSourceDisplayName(id)}: {formatNumber(value)}</Typography>
                </Box>
              )}
            />
          )}
        </Box>

        {/* TABLE SECTION */}
        <Box sx={tablePaperSx}>
          <TableContainer>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow sx={{ "& .MuiTableCell-head": { py: 2, fontWeight: 800, textTransform: "uppercase", fontSize: 11, letterSpacing: 1, opacity: 0.7 } }}>
                  <TableCell>Source</TableCell>
                  <TableCell align="right">Views</TableCell>
                  <TableCell align="right">Avg Dur</TableCell>
                  <TableCell align="right">Avg %</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {/* TOTAL ROW */}
                <TableRow sx={{ bgcolor: isDark ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.02)" }}>
                  <TableCell sx={{ fontWeight: 900 }}>Total</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 900 }}>{formatNumber(totals.views)}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 900 }}>{formatSeconds(totals.averageViewDuration)}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 900 }}>{totals.averageViewPercentage.toFixed(2)}%</TableCell>
                </TableRow>

                <AnimatePresence mode="popLayout">
                  {rows.map((r, idx) => (
                    <TableRow
                      key={r.id}
                      hover
                      component={motion.tr}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.03 }}
                      sx={{ "&:hover": { bgcolor: isDark ? "rgba(255,255,255,0.02) !important" : "rgba(0,0,0,0.01) !important" } }}
                    >
                      <TableCell sx={{ fontWeight: 600, fontSize: 13, borderLeft: idx < 3 ? `3px solid ${colorMap[r.id]}` : "none" }}>
                        <Box display="flex" alignItems="center" gap={1.5}>
                          <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: colorMap[r.id] }} />
                          {r.label}
                        </Box>
                      </TableCell>
                      <TableCell align="right">
                        <Box sx={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
                          <Typography variant="body2" sx={{ fontWeight: 700 }}>
                            {formatNumber(r.views)}
                          </Typography>
                          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 0.5, width: 80 }}>
                            <Box sx={{ flex: 1, height: 4, bgcolor: isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.05)", borderRadius: 2, overflow: "hidden" }}>
                              <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${r.viewsPct}%` }}
                                transition={{ duration: 1, delay: idx * 0.05 }}
                                style={{ height: "100%", background: colorMap[r.id], borderRadius: 2 }}
                              />
                            </Box>
                            <Typography sx={{ fontSize: 9, opacity: 0.6, width: 30, textAlign: "right" }}>{Math.round(r.viewsPct)}%</Typography>
                          </Box>
                        </Box>
                      </TableCell>
                      <TableCell align="right" sx={{ fontSize: 13 }}>{formatSeconds(r.averageViewDuration)}</TableCell>
                      <TableCell align="right" sx={{ fontSize: 13 }}>{r.averageViewPercentage.toFixed(2)}%</TableCell>
                    </TableRow>
                  ))}
                </AnimatePresence>
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      </Stack>
    </motion.div>
  );
};

export default TrafficSourceChart;
