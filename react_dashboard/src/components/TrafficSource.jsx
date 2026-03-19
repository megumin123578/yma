// src/components/TrafficSource.jsx
import React, { useMemo, useState, useEffect, useCallback, useRef } from "react";
import { useTheme } from "@mui/material/styles";
import {
  Box,
  Stack,
  Typography,
  Avatar,
  Autocomplete,
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
  TextField,
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
  toUTCDate,
  getMonthRange,
  getChannelAvatarMap,
  getChannelRevenueMap,
} from "./Module";
import { CHANNEL_SWITCHER_SX } from "./ChannelSwitcher";

import dayjs from "dayjs";
import { LocalizationProvider, DatePicker } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";

import { API_BASE } from "../config";
import { sortByStoredTokenOrder } from "../utils/tokenOrder";
import { getStoredSharedChannelId, setStoredSharedChannelId } from "../utils/sharedChannel";

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
];

const TRAFFIC_SOURCE_PERIOD_OPTIONS = [
  ...PERIOD_OPTIONS.filter((option) => option.value.startsWith("last")),
  ...EXTRA_PERIODS,
  ...PERIOD_OPTIONS.filter((option) => option.value === "lifetime"),
  ...PERIOD_OPTIONS.filter((option) => option.value === "custom"),
];
const TRAFFIC_SOURCE_PERIOD_VALUES = new Set(
  TRAFFIC_SOURCE_PERIOD_OPTIONS.map((option) => option.value)
);

const normalizeTrafficSourcePeriod = (value) =>
  TRAFFIC_SOURCE_PERIOD_VALUES.has(value) ? value : "last28";

const FILTERS_STORAGE_KEY = "trafficSource.filters";
const RECENT_CHANNELS_STORAGE_KEY = "trafficSource.recentChannels";
const TRAFFIC_SOURCE_COLORS = [
  "#3b82f6",
  "#ef4444",
  "#22c55e",
  "#f59e0b",
  "#a855f7",
  "#ec4899",
  "#06b6d4",
  "#84cc16",
  "#f97316",
  "#6366f1",
  "#14b8a6",
  "#f43f5e",
];

const makeTrafficSourceColorMap = (ids, useDark = false) => {
  const orderedIds = Array.from(new Set((ids || []).map(String).filter(Boolean)));
  const lightness = useDark ? 68 : 58;
  const palette = {};

  orderedIds.forEach((id, index) => {
    if (index < TRAFFIC_SOURCE_COLORS.length) {
      palette[id] = TRAFFIC_SOURCE_COLORS[index];
      return;
    }

    const hue = Math.round((index * 137.508 + 23) % 360);
    palette[id] = `hsl(${hue}, 78%, ${lightness}%)`;
  });

  return palette;
};

const loadStoredFilters = () => {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(FILTERS_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    const sharedChannel = getStoredSharedChannelId("trafficSource.selectedChannelId");
    if (parsed) {
      return parsed.channel ? parsed : { ...parsed, channel: sharedChannel };
    }
    return sharedChannel ? { channel: sharedChannel } : null;
  } catch (e) {
    return null;
  }
};

const loadRecentChannels = () => {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(RECENT_CHANNELS_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.map(String).filter(Boolean) : [];
  } catch (e) {
    return [];
  }
};

const saveRecentChannels = (items) => {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      RECENT_CHANNELS_STORAGE_KEY,
      JSON.stringify(Array.from(new Set((items || []).map(String).filter(Boolean))).slice(0, 5))
    );
  } catch (e) { }
};

const formatChannelDate = (value, withTime = false) => {
  if (!value) return "";
  const parsed = dayjs(value);
  if (!parsed.isValid()) return "";
  return parsed.format(withTime ? "DD MMM YYYY, HH:mm" : "DD MMM YYYY");
};

const TrafficLineChart = ({
  data,
  lineDateExtent,
  lineDateTicks,
  colorMap,
  themeMode,
  onSliceMove,
  onSliceLeave,
}) => {
  const isDark = themeMode === "dark";
  const axisTextColor = isDark ? "#e5e7eb" : "#374151";

  const renderBottomTick = useCallback(
    (tick) => {
      const d = tick.value instanceof Date ? tick.value : new Date(tick.value);
      const label = dayjs(d).format("DD/MM");
      return (
        <g transform={`translate(${tick.x},${tick.y})`} style={{ pointerEvents: "none" }}>
          <text
            y={6}
            textAnchor="middle"
            dominantBaseline="hanging"
            style={{
              fill: axisTextColor,
              fontSize: 11,
              fontWeight: 600,
            }}
          >
            {label}
          </text>
        </g>
      );
    },
    [axisTextColor]
  );

  const lineTheme = useMemo(
    () => ({
      axis: {
        ticks: {
          text: {
            fill: axisTextColor,
            fontSize: 11,
            fontWeight: 600,
          },
          line: {
            stroke: isDark
              ? "rgba(148,163,184,0.4)"
              : "rgba(148,163,184,0.6)",
          },
        },
      },
      grid: {
        line: {
          stroke: isDark
            ? "rgba(148,163,184,0.18)"
            : "rgba(148,163,184,0.25)",
          strokeWidth: 1,
          strokeDasharray: "4 4",
        },
      },
      crosshair: {
        line: {
          stroke: isDark
            ? "rgba(226,232,240,0.45)"
            : "rgba(15,23,42,0.35)",
          strokeWidth: 1,
          strokeDasharray: "3 3",
        },
      },
      tooltip: {
        container: {
          background: "transparent",
          padding: 0,
          boxShadow: "none",
          border: "none",
          borderRadius: 0,
        },
      },
    }),
    [axisTextColor, isDark]
  );

  return (
    <ResponsiveLine
      debounceResize={150}
      data={data}
      colors={(serie) => colorMap[serie.id] || "#60a5fa"}
      margin={{ top: 32, right: 8, bottom: 64, left: 56 }}
      xScale={{
        type: "time",
        format: "native",
        useUTC: false,
        precision: "day",
        min: lineDateExtent.min,
        max: lineDateExtent.max,
      }}
      yScale={{ type: "linear", min: 0, stacked: false }}
      curve="linear"
      enablePoints
      pointSize={6}
      enableSlices="x"
      enableCrosshair
      crosshairType="cross"
      tooltip={() => null}
      sliceTooltip={() => null}
      onMouseMove={onSliceMove}
      onMouseLeave={onSliceLeave}
      axisBottom={{
        tickValues: lineDateTicks,
        tickSize: 0,
        tickPadding: 10,
        renderTick: renderBottomTick,
      }}
      axisLeft={{
        tickSize: 0,
        tickPadding: 8,
        format: (v) => formatNumber(v),
      }}
      theme={lineTheme}
    />
  );
};

const TrafficSourceChart = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const chartRef = useRef(null);
  const [hoverSlice, setHoverSlice] = useState(null);

  /* === Controls === */
  const [chartType, setChartType] = useState(() => loadStoredFilters()?.chartType || "pie");
  const [metric, setMetric] = useState(() => loadStoredFilters()?.metric || "views");
  const [period, setPeriod] = useState(() =>
    normalizeTrafficSourcePeriod(loadStoredFilters()?.period)
  );
  const [interval, setInterval] = useState(() => loadStoredFilters()?.interval || "daily");

  const [channels, setChannels] = useState([]);
  const [channelAvatarMap, setChannelAvatarMap] = useState({});
  const [channelRevenueMap, setChannelRevenueMap] = useState({});
  const [recentChannels, setRecentChannels] = useState(() => loadRecentChannels());
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
          if (typeof x === "string") return { value: x, label: x, avatar: "", updatedAt: null, lastDataDate: null, subscribers: null };
          if (x?.value && x?.label) {
            return {
              value: String(x.value),
              label: String(x.label),
              avatar: x.avatar || "",
              updatedAt: x.updatedAt || x.updated_at || null,
              lastDataDate: x.lastDataDate || x.last_data_date || null,
              subscribers: x.subscribers ?? x.subscriberCount ?? null,
            };
          }
          if (x?.root && x?.label) {
            return {
              value: String(x.root),
              label: String(x.label),
              avatar: x.avatar || "",
              updatedAt: x.updatedAt || x.updated_at || null,
              lastDataDate: x.lastDataDate || x.last_data_date || null,
              subscribers: x.subscribers ?? x.subscriberCount ?? null,
            };
          }
          if (x?.root) {
            return {
              value: String(x.root),
              label: String(x.root),
              avatar: x.avatar || "",
              updatedAt: x.updatedAt || x.updated_at || null,
              lastDataDate: x.lastDataDate || x.last_data_date || null,
              subscribers: x.subscribers ?? x.subscriberCount ?? null,
            };
          }
          return {
            value: String(x?.value ?? x?.id ?? x),
            label: String(x?.label ?? x?.name ?? x?.value ?? x),
            avatar: x?.avatar || "",
            updatedAt: x?.updatedAt || x?.updated_at || null,
            lastDataDate: x?.lastDataDate || x?.last_data_date || null,
            subscribers: x?.subscribers ?? x?.subscriberCount ?? null,
          };
        });
        const finalChannels = sortByStoredTokenOrder(
          norm,
          (item) => item.value
        );
        if (!stop) {
          setChannels(finalChannels);
          setChannel((current) => {
            const preferredChannel =
              getStoredSharedChannelId("trafficSource.selectedChannelId") || current;
            if (!finalChannels.length) return "";
            if (
              !preferredChannel ||
              !finalChannels.some((opt) => opt.value === preferredChannel)
            ) {
              return finalChannels[0].value;
            }
            return preferredChannel;
          });
        }
      } catch (e) {
        console.error("Load channels failed:", e);
        if (!stop) setChannels([]);
      }
    })();
    return () => { stop = true; };
  }, [authHeaders]);

  useEffect(() => {
    let active = true;
    getChannelAvatarMap().then((map) => {
      if (active) setChannelAvatarMap(map || {});
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    getChannelRevenueMap().then((map) => {
      if (active) setChannelRevenueMap(map || {});
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!channel) return;
    setRecentChannels((current) => {
      const next = [channel, ...current.filter((item) => item !== channel)].slice(0, 5);
      saveRecentChannels(next);
      return next;
    });
    setStoredSharedChannelId(channel, "trafficSource.selectedChannelId");
  }, [channel]);

  const [startDate, setStartDate] = useState(() => loadStoredFilters()?.startDate || "");
  const [endDate, setEndDate] = useState(() => loadStoredFilters()?.endDate || "");

  /* === Data === */
  const mconf = METRICS[metric];
  const [tsData, setTsData] = useState([]);
  const [tsSeries, setTsSeries] = useState([]);

  const [loading, setLoading] = useState(false);
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
        setErrorMsg(e?.message || "Lá»—i táº£i dá»¯ liá»‡u.");
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
        setErrorMsg(e?.message || "Lá»—i táº£i timeseries.");
      } finally {
        setLoading(false);
      }
    },
    [channel, authHeaders]
  );

  const computeRange = useCallback((periodValue, now = new Date()) => {
    if (periodValue === "month_current") return getMonthRange(0, now);
    if (periodValue === "month_prev") return getMonthRange(1, now);

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

  const currentChannelLabel = useMemo(() => {
    const selected = channels.find((item) => item.value === channel);
    return selected?.label || channel || "No channel selected";
  }, [channels, channel]);

  const orderedChannelOptions = useMemo(() => {
    const recentRank = new Map(recentChannels.map((value, index) => [String(value), index]));
    const recent = [];
    const others = [];

    channels.forEach((item) => {
      if (recentRank.has(String(item.value))) {
        recent.push({ ...item, group: "Recent", meta: channelRevenueMap[item.value] || "" });
      } else {
        others.push({ ...item, group: "All channels", meta: channelRevenueMap[item.value] || "" });
      }
    });

    recent.sort((a, b) => recentRank.get(String(a.value)) - recentRank.get(String(b.value)));
    return [...recent, ...others];
  }, [channels, recentChannels, channelRevenueMap]);

  const currentChannelMeta = useMemo(
    () => channels.find((item) => item.value === channel) || null,
    [channels, channel]
  );

  const getChannelAvatar = useCallback(
    (channelValue, fallbackAvatar = "") =>
      channelAvatarMap[channelValue] || fallbackAvatar || "",
    [channelAvatarMap]
  );

  useEffect(() => {
    if (!channel) return;
    const { start, end } = currentRange;
    if (period === "custom" && (!start || !end)) return;
    if (!start || !end) {
      setErrorMsg("HÃ£y chá»n thá»i gian há»£p lá»‡.");
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

  const colorMap = useMemo(
    () => makeTrafficSourceColorMap(seriesIdsForPalette, theme.palette.mode === "dark"),
    [seriesIdsForPalette, theme.palette.mode]
  );

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
      const color = colorMap[src] || "#888";
      const data = allDatesSorted.map(d => {
        const y = dataMap.get(d.getTime()) || 0;
        if (Math.abs(y) > EPS) nonZero = true;
        return { x: d, y, source: src, sourceLabel: getSourceDisplayName(src), color };
      });
      if (nonZero && includeSourceForCharts(src)) {
        result.push({ id: src, data, color });
      }
    }
    return result;
  }, [chartType, tsSeries, mconf, getSourceDisplayName, includeSourceForCharts, colorMap]);

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
  const chartPaperSx = useMemo(() => ({
    height: 420,
    minWidth: 320,
    borderRadius: 2,
    border: `1px solid ${theme.palette.mode === "dark"
      ? "rgba(255,255,255,0.08)"
      : "rgba(0,0,0,0.06)"
      }`,
    p: 1,
    position: "relative",
    backgroundColor: "transparent",
  }), [theme.palette.mode]);
  const chartTooltipSx = useMemo(() => ({
    px: 2,
    py: 1.25,
    borderRadius: 2,
    bgcolor: theme.palette.mode === "dark" ? "#0b1020" : "#ffffff",
    border: `1px solid ${theme.palette.mode === "dark"
      ? "rgba(148,163,184,0.24)"
      : "rgba(15,23,42,0.14)"
      }`,
    boxShadow: theme.palette.mode === "dark"
      ? "0 18px 40px rgba(0,0,0,0.55)"
      : "0 18px 34px rgba(15,23,42,0.18)",
  }), [theme.palette.mode]);

  const hasChartData = useMemo(() => {
    if (chartType === "pie") return rows.length > 0;
    if (chartType === "line") return lineSeries.length > 0;
    return barPrep.data.length > 0 && barPrep.keys.length > 0;
  }, [chartType, rows.length, lineSeries.length, barPrep.data.length, barPrep.keys.length]);

  const emptyState = (
    <Box
      sx={{
        position: "absolute",
        inset: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        px: 3,
        zIndex: 2,
        borderRadius: 2,
      }}
    >
      <Box>
        <Typography variant="body2" color="text.secondary">
          No timeseries data in this range.
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
          Channel: {currentChannelLabel}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Range: {currentRange.start || "-"} to {currentRange.end || "-"}
        </Typography>
      </Box>
    </Box>
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
    >
      <Stack spacing={2}>
        {/* SELECTORS */}
        <Stack direction="row" alignItems="center" spacing={2} sx={{ flexWrap: "wrap", rowGap: 2 }}>
          <Box sx={CHANNEL_SWITCHER_SX}>
            <Autocomplete
              size="small"
              disableClearable
              options={orderedChannelOptions}
              value={currentChannelMeta}
              isOptionEqualToValue={(option, value) => option?.value === value?.value}
              groupBy={(option) => option.group || "All channels"}
              filterOptions={(options, state) => {
                const query = state.inputValue.trim().toLowerCase();
                if (!query) return options;
                return options.filter((option) =>
                  [option.label, option.value, formatChannelDate(option.lastDataDate)]
                    .filter(Boolean)
                    .join(" ")
                    .toLowerCase()
                    .includes(query)
                );
              }}
              noOptionsText="No channels found"
              onChange={(_, nextValue) => {
                if (nextValue?.value) setChannel(nextValue.value);
              }}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Channel"
                  placeholder="Search by channel name"
                  InputProps={{
                    ...params.InputProps,
                    startAdornment: (
                      <>
                        {currentChannelMeta ? (
                          <Avatar
                            src={getChannelAvatar(currentChannelMeta.value, currentChannelMeta.avatar)}
                            alt={currentChannelMeta.label}
                            sx={{ width: 22, height: 22, mr: 1 }}
                          />
                        ) : (
                          <YouTubeIcon sx={{ fontSize: 18, color: "text.secondary", mr: 1 }} />
                        )}
                        {params.InputProps.startAdornment}
                      </>
                    ),
                    endAdornment: (
                      <>
                        {orderedChannelOptions.find((item) => item.value === channel)?.meta ? (
                          <Box
                            sx={{
                              mr: 0.25,
                              px: 0.5,
                              py: 0.15,
                              borderRadius: 999,
                              fontSize: 11,
                              fontWeight: 800,
                              lineHeight: 1,
                              color: "success.main",
                              bgcolor: "rgba(46, 125, 50, 0.12)",
                              border: "1px solid",
                              borderColor: "rgba(46, 125, 50, 0.2)",
                            }}
                            >
                            {orderedChannelOptions.find((item) => item.value === channel)?.meta}
                          </Box>
                        ) : null}
                        {params.InputProps.endAdornment}
                      </>
                    ),
                  }}
                />
              )}
              renderOption={(props, option) => (
                <Box component="li" {...props} sx={{ display: "flex", alignItems: "center", gap: 1.25, py: 1 }}>
                  <Avatar
                    src={getChannelAvatar(option.value, option.avatar)}
                    alt={option.label}
                    sx={{ width: 30, height: 30 }}
                  />
                  <Box sx={{ minWidth: 0, flex: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 700 }} noWrap>
                      {option.label}
                    </Typography>
                  </Box>
                  {option.meta ? (
                    <Box
                      sx={{
                        minWidth: 20,
                        px: 0.75,
                        py: 0.25,
                        borderRadius: 999,
                        fontSize: 12,
                        fontWeight: 800,
                        lineHeight: 1,
                        color: "success.main",
                        bgcolor: "rgba(46, 125, 50, 0.12)",
                        border: "1px solid",
                        borderColor: "rgba(46, 125, 50, 0.2)",
                      }}
                    >
                      {option.meta}
                    </Box>
                  ) : null}
                </Box>
              )}
            />
          </Box>

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
              {TRAFFIC_SOURCE_PERIOD_OPTIONS.map(o => <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>)}
            </Select>
          </FormControl>

          {period === "custom" && (
            <LocalizationProvider dateAdapter={AdapterDayjs}>
              <DatePicker label="Start" value={startDate ? dayjs(startDate) : null} onChange={v => setStartDate(v ? v.format("YYYY-MM-DD") : "")} slotProps={{ textField: { size: "small" } }} />
              <DatePicker label="End" value={endDate ? dayjs(endDate) : null} onChange={v => setEndDate(v ? v.format("YYYY-MM-DD") : "")} slotProps={{ textField: { size: "small" } }} />
            </LocalizationProvider>
          )}
        </Stack>

        {errorMsg && <Typography color="error" variant="body2" sx={{ px: 1 }}>{errorMsg}</Typography>}
        {/* CHART SECTION */}
        <Box
          sx={chartPaperSx}
        >
          {loading && (
            <Box
              sx={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                bgcolor: "rgba(0,0,0,0.05)",
                zIndex: 3,
                borderRadius: 2,
                backdropFilter: "blur(2px)",
              }}
            >
              Loading...
            </Box>
          )}

          {!loading && !errorMsg && !hasChartData && emptyState}

          {chartType === "pie" && (
            <ResponsivePie
              data={rows.filter(r => includeSourceForCharts(r.id)).map(r => ({ id: String(r.id), label: r.label, value: r.sortValue }))}
              colors={d => colorMap[d.id] || "#888"}
              margin={{ top: 50, right: 50, bottom: 50, left: 50 }}
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
                  sx={{ ...chartTooltipSx, minWidth: 180 }}
                >
                  <Typography variant="subtitle2" fontWeight={800} color={isDark ? "#e5e7eb" : "#111827"}>{datum.label}</Typography>
                  <Divider sx={{ my: 0.5, opacity: 0.1 }} />
                  <Typography variant="body2" sx={{ color: "text.secondary" }}>
                    {mconf.label}: <strong style={{ color: isDark ? "#e5e7eb" : "#111827" }}>{metric === "averageViewDuration" ? formatSeconds(datum.value) : formatNumber(datum.value)}</strong>
                  </Typography>
                </Box>
              )}
            />
          )}

          {chartType === "line" && (
            <Box ref={chartRef} sx={{ height: "100%" }}>
              <TrafficLineChart
                data={lineSeries}
                lineDateExtent={lineDateExtent}
                lineDateTicks={lineDateTicks}
                colorMap={colorMap}
                themeMode={theme.palette.mode}
                onSliceMove={setHoverSlice}
                onSliceLeave={() => setHoverSlice(null)}
              />
            </Box>
          )}

          {chartType === "line" && hoverSlice && (
            <Box
              sx={{
                position: "absolute",
                top: 10,
                left: 0,
                transform: `translate3d(${56 + hoverSlice.x}px, 0, 0) translateX(-50%)`,
                transition: "transform 140ms cubic-bezier(0.2, 0.9, 0.2, 1)",
                willChange: "transform",
                pointerEvents: "none",
                zIndex: 20,
                width: "min(360px, 92%)",
              }}
            >
              <Box sx={{ ...chartTooltipSx }}>
                <Typography
                  variant="subtitle2"
                  sx={{
                    fontWeight: 800,
                    mb: 1,
                    color: isDark ? "#e5e7eb" : "#111827",
                  }}
                >
                  {(() => {
                    const p0 = hoverSlice.points?.[0];
                    const x = p0?.data?.x;
                    if (x instanceof Date) return dayjs(x).format("MMM D, YYYY");
                    return String(x ?? "");
                  })()}
                </Typography>
                <Box sx={{ display: "grid", gap: 0.75 }}>
                  {hoverSlice.points
                    .slice()
                    .sort((a, b) => (b.data.y ?? 0) - (a.data.y ?? 0))
                    .slice(0, 5)
                    .map((p) => {
                      const color = colorMap[p.serieId] || p.color || "#888";
                      const label = p.data.sourceLabel || getSourceDisplayName(p.serieId);
                      return (
                        <Box
                          key={p.id}
                          sx={{
                            display: "grid",
                            gridTemplateColumns: "minmax(0, 1fr) auto",
                            alignItems: "center",
                            gap: 2,
                            width: "100%",
                            minWidth: 0,
                          }}
                        >
                          <Box sx={{ display: "flex", alignItems: "center", gap: 1, minWidth: 0, overflow: "hidden" }}>
                            <Box
                              component="span"
                              sx={{
                                width: 10,
                                height: 10,
                                borderRadius: "50%",
                                backgroundColor: color,
                                flexShrink: 0,
                              }}
                            />
                            <Typography
                              variant="body2"
                              title={label}
                              noWrap
                              sx={{
                                fontSize: 12,
                                fontWeight: 600,
                                lineHeight: 1.25,
                                display: "block",
                                width: "100%",
                                minWidth: 0,
                                maxWidth: "100%",
                                color: isDark ? "#e5e7eb" : "#111827",
                              }}
                            >
                              {label}
                            </Typography>
                          </Box>
                          <Typography
                            variant="body2"
                            sx={{
                              fontSize: 12,
                              fontWeight: 800,
                              color: isDark ? "#e5e7eb" : "#111827",
                              flexShrink: 0,
                            }}
                          >
                            {metric === "averageViewPercentage"
                              ? `${n(p.data.y).toFixed(2)}%`
                              : metric === "averageViewDuration"
                                ? formatSeconds(p.data.y)
                                : formatNumber(p.data.y)}
                          </Typography>
                        </Box>
                      );
                    })}
                </Box>
              </Box>
            </Box>
          )}

          {chartType === "bar" && (
            <ResponsiveBar
              data={barPrep.data}
              keys={barPrep.keys}
              indexBy="bucket"
              colors={d => colorMap[d.id] || "#888"}
              margin={{ top: 20, right: 20, bottom: 60, left: 60 }}
              padding={0.4}
              innerPadding={2}
              borderRadius={6}
              axisBottom={{
                format: v => dayjs(v).format("DD/MM"),
                tickValues: barXTicks,
                tickPadding: 10,
              }}
              enableGridY={true}
              gridYValues={5}
              labelSkipWidth={12}
              labelSkipHeight={12}
              motionConfig="gentle"
              theme={{
                axis: {
                  ticks: { text: { fontSize: 11, fill: theme.palette.text.secondary, fontWeight: 500 } },
                  domain: { line: { stroke: "transparent" } }
                },
                grid: { line: { stroke: isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)", strokeDasharray: "4 4" } }
              }}
              tooltip={({ id, value, indexValue, color }) => (
                <Box sx={{ ...chartTooltipSx, minWidth: 220 }}>
                  <Typography
                    variant="subtitle2"
                    sx={{
                      fontWeight: 800,
                      mb: 1,
                      color: isDark ? "#e5e7eb" : "#111827",
                    }}
                  >
                      {dayjs(indexValue).format("DD MMMM YYYY")}
                  </Typography>
                  <Box
                    sx={{
                      display: "grid",
                      gridTemplateColumns: "minmax(0, 1fr) auto",
                      alignItems: "center",
                      gap: 2,
                      minWidth: 0,
                    }}
                  >
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1, minWidth: 0, overflow: "hidden" }}>
                      <Box sx={{ width: 10, height: 10, borderRadius: "50%", backgroundColor: color, flexShrink: 0 }} />
                      <Typography
                        variant="body2"
                        title={getSourceDisplayName(id)}
                        noWrap
                        sx={{
                          fontSize: 12,
                          fontWeight: 600,
                          lineHeight: 1.25,
                          display: "block",
                          width: "100%",
                          minWidth: 0,
                          maxWidth: "100%",
                          color: isDark ? "#e5e7eb" : "#111827",
                        }}
                      >
                        {getSourceDisplayName(id)}
                      </Typography>
                    </Box>
                    <Typography
                      variant="body2"
                      sx={{
                        fontSize: 12,
                        fontWeight: 800,
                        color: isDark ? "#e5e7eb" : "#111827",
                        flexShrink: 0,
                      }}
                    >
                      {metric === "averageViewPercentage" ? `${n(value).toFixed(2)}%` : metric === "averageViewDuration" ? formatSeconds(value) : formatNumber(value)}
                    </Typography>
                  </Box>
                </Box>
              )}
            />
          )}
        </Box>

        {/* TABLE SECTION */}
        <Box sx={tablePaperSx}>
          {!loading && !errorMsg && rows.length === 0 && (
            <Box sx={{ px: 2, py: 3 }}>
              <Typography variant="body2" color="text.secondary">
                No table rows for {currentChannelLabel} in {currentRange.start || "-"} to {currentRange.end || "-"}.
              </Typography>
            </Box>
          )}
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
                      <TableCell sx={{ fontWeight: 600, fontSize: 13, borderLeft: idx < 5 && colorMap[r.id] ? `3px solid ${colorMap[r.id]}` : "none" }}>
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
