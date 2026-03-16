import { useMemo, useState, useEffect, useRef } from "react";
import { useTheme } from "@mui/material/styles";
import {
  Box,
  Stack,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TableContainer,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Checkbox,
  Radio,
  Divider,
  ListSubheader,
  Typography,
} from "@mui/material";
import { motion, AnimatePresence } from "framer-motion";
import CalendarMonthIcon from "@mui/icons-material/CalendarMonth";
import BarChartIcon from "@mui/icons-material/BarChart";

import { COUNTRY_FALLBACK } from "../data/countryMapping";
import { ResponsiveChoropleth } from "@nivo/geo";
import { geoFeatures } from "../data/mockGeoFeatures";
import api from "../services/api";
import { getChannelAvatarMap } from "./Module";
import ChannelSwitcher, { CHANNEL_SWITCHER_SX } from "./ChannelSwitcher";

// ===== Helpers =====
const n = (v) => Number(v) || 0;
const formatSeconds = (s) => {
  const sec = Math.max(0, Math.floor(n(s)));
  const m = Math.floor(sec / 60);
  const r = String(sec % 60).padStart(2, "0");
  return `${m}:${r}`;
};
const formatNumber = (v) => n(v).toLocaleString();
const percentStr = (p) => `${n(p).toFixed(2)}%`;

// ===== Metric config =====
const METRICS = {
  views: {
    key: "views",
    label: "Views",
    color: "#6366f1",
    valueOf: (d) => n(d.views),
    fmt: (v) => formatNumber(v),
  },
  estimatedMinutesWatched: {
    key: "estimatedMinutesWatched",
    label: "Watch Time",
    color: "#8b5cf6",
    valueOf: (d) => n(d.estimatedMinutesWatched),
    fmt: (v) => formatNumber(v),
  },
  averageViewDuration: {
    key: "averageViewDuration",
    label: "Avg Duration",
    color: "#ec4899",
    valueOf: (d) => n(d.averageViewDuration),
    fmt: (v) => formatSeconds(v),
  },
  averageViewPercentage: {
    key: "averageViewPercentage",
    label: "Avg %",
    color: "#10b981",
    valueOf: (d) => n(d.averageViewPercentage),
    fmt: (v) => `${n(v).toFixed(2)}%`,
  },
  engagedViews: {
    key: "engagedViews",
    label: "Engaged Views",
    color: "#f59e0b",
    valueOf: (d) => n(d.engagedViews),
    fmt: (v) => formatNumber(v),
  },
};

const METRIC_OPTIONS = Object.keys(METRICS).map((k) => ({
  value: k,
  label: METRICS[k].label,
}));

// ===== TABLE COLUMNS =====
const TABLE_COLUMNS = [
  { key: "views", label: "Views", width: 150 },
  { key: "engagedViews", label: "Engaged Views", width: 160 },
  { key: "watchTimeHours", label: "Watch (hrs)", width: 160 },
  { key: "averageViewDuration", label: "Avg Dur", width: 140 },
  { key: "averageViewPercentage", label: "Avg %", width: 130 },
];
const FILTERS_STORAGE_KEY = "geography.filters";

const loadStoredFilters = () => {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(FILTERS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
};

const GeographyChart = ({ isDashboard = false }) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  // ===== State =====
  const [rawData, setRawData] = useState([]);
  const [range, setRange] = useState(() => loadStoredFilters()?.range || "28d");
  const [channel, setChannel] = useState(() => loadStoredFilters()?.channel || "");
  const [channelLabelFallback, setChannelLabelFallback] = useState(
    () => loadStoredFilters()?.channelLabel || ""
  );
  const [channels, setChannels] = useState([]);
  const [channelAvatarMap, setChannelAvatarMap] = useState({});
  const channelsRef = useRef([]);

  const [visibleColumns, setVisibleColumns] = useState(() => loadStoredFilters()?.visibleColumns || {
    views: true,
    engagedViews: true,
    watchTimeHours: true,
    averageViewDuration: true,
    averageViewPercentage: true,
  });

  const [metric, setMetric] = useState(() => loadStoredFilters()?.metric || "views");
  const mconf = METRICS[metric];

  // ===== Fetch data =====
  useEffect(() => {
    // Backend route is mounted at `/api/geography/` (trailing slash). Using it avoids 307 redirects.
    const url = `/api/geography/?range=${range}${channel ? `&channel=${channel}` : ""}`;
    api.get(url)
      .then((r) => r.data)
      .then((json) => {
        setRawData(json.rows || []);
        if (json.availableChannels) {
          const existingLabelMap = new Map((channelsRef.current || []).map(c => [c.value, c.label || c.value]));
          const normalized = (Array.isArray(json.availableChannels) ? json.availableChannels : [])
            .map((item) => {
              const value = typeof item === "string" ? item : (item?.value || item?.name || "");
              const label = typeof item === "string" ? (existingLabelMap.get(item) || item) : (item?.label || item?.name || existingLabelMap.get(value) || value);
              return { value, label };
            }).filter(i => i.value);

          const curStr = JSON.stringify((channelsRef.current || []).map(c => c.value));
          const newStr = JSON.stringify(normalized.map(c => c.value));

          if (curStr !== newStr || !channelsRef.current.length) {
            const final = normalized.sort((a, b) => a.label.localeCompare(b.label));
            channelsRef.current = final;
            setChannels(final);
            if (channel) {
              const sel = final.find(c => c.value === channel);
              if (sel?.label) setChannelLabelFallback(sel.label);
            }
            if (!channel && final.length) {
              setChannel(final[0].value);
              setChannelLabelFallback(final[0].label);
            }
          }
        }
      }).catch(err => console.error(err));
  }, [range, channel]);

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
    const label = (channelsRef.current || []).find(c => c.value === channel)?.label || channelLabelFallback || "";
    window.localStorage.setItem(FILTERS_STORAGE_KEY, JSON.stringify({ range, channel, channelLabel: label, metric, visibleColumns }));
  }, [range, channel, metric, visibleColumns, channelLabelFallback]);

  // ===== ISO Resolver =====
  const resolvers = useMemo(() => {
    const iso2To3 = new Map();
    const idToName = new Map();
    geoFeatures.features.forEach(f => {
      const id = String(f.id || f.properties?.iso_a3 || "");
      const iso2 = f.properties?.iso_a2?.toUpperCase() || "";
      if (iso2) iso2To3.set(iso2, id);
      idToName.set(id, f.properties?.name || id);
    });
    return {
      resolveId: (code) => {
        const c = String(code).toUpperCase();
        return iso2To3.get(c) || COUNTRY_FALLBACK[c] || c;
      },
      nameOf: (id) => idToName.get(id) || id,
    };
  }, []);

  const data = useMemo(() => rawData.map(d => {
    const id = resolvers.resolveId(d.country);
    return { ...d, id, label: resolvers.nameOf(id) };
  }), [rawData, resolvers]);

  const mapData = useMemo(() => data.map(d => ({ id: d.id, value: mconf.valueOf(d) })), [data, mconf]);
  const domainMax = useMemo(() => {
    if (metric === "averageViewPercentage") return 100;
    return Math.max(1, ...mapData.map(d => n(d.value)));
  }, [mapData, metric]);

  const { rows, totals } = useMemo(() => {
    const rawRows = data.map(d => ({
      id: d.id,
      label: d.label,
      views: n(d.views),
      engagedViews: n(d.engagedViews),
      watchTimeHours: n(d.estimatedMinutesWatched) / 60,
      averageViewDuration: n(d.averageViewDuration),
      averageViewPercentage: n(d.averageViewPercentage),
      sortValue: mconf.valueOf(d),
    }));
    const tv = rawRows.reduce((a, b) => a + b.views, 0);
    const te = rawRows.reduce((a, b) => a + b.engagedViews, 0);
    const tw = rawRows.reduce((a, b) => a + b.watchTimeHours, 0);
    const totals = {
      views: tv,
      engagedViews: te,
      watchTimeHours: tw,
      averageViewDuration: rawRows.reduce((a, b) => a + (b.averageViewDuration * b.views), 0) / (tv || 1),
      averageViewPercentage: rawRows.reduce((a, b) => a + (b.averageViewPercentage * b.views), 0) / (tv || 1),
    };
    return {
      totals,
      rows: rawRows.map(r => ({
        ...r,
        viewsPct: tv ? (r.views / tv) * 100 : 0,
        engagedPct: te ? (r.engagedViews / te) * 100 : 0,
        watchPct: tw ? (r.watchTimeHours / tw) * 100 : 0,
      })).sort((a, b) => b.sortValue - a.sortValue).slice(0, 50),
    };
  }, [data, mconf]);

  const metricsSelectValue = useMemo(() => {
    return [`map:${metric}`, ...Object.entries(visibleColumns).filter(([, v]) => v).map(([k]) => `col:${k}`)];
  }, [metric, visibleColumns]);

  // Styles
  const glassSx = {
    bgcolor: isDark ? "rgba(15, 23, 42, 0.65)" : "rgba(255, 255, 255, 0.8)",
    backdropFilter: "blur(12px)",
    borderRadius: 4,
    border: "1px solid",
    borderColor: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)",
    boxShadow: isDark ? "0 8px 32px rgba(0,0,0,0.4)" : "0 8px 24px rgba(15,23,42,0.08)",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
    >
      <Stack spacing={3}>
        {/* SELECTORS */}
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} justifyContent="flex-start">
          <ChannelSwitcher
            options={channels}
            value={channel}
            onChange={(option) => {
              const next = option?.value || "";
              setChannel(next);
              if (option?.label) setChannelLabelFallback(option.label);
            }}
            sx={CHANNEL_SWITCHER_SX}
            recentStorageKey="geography.recentChannels"
            getOptionAvatar={(option) => channelAvatarMap[option?.value] || ""}
            getOptionLabel={(option) =>
              option?.label
                ? option.label
                : channelLabelFallback || String(option?.value || "").replace(/_+/g, " ").trim()
            }
          />

          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <CalendarMonthIcon sx={{ fontSize: 16 }} /> Period
            </InputLabel>
            <Select label="Period" value={range} onChange={(e) => setRange(e.target.value)}>
              <MenuItem value="7d">Last 7 days</MenuItem>
              <MenuItem value="28d">Last 28 days</MenuItem>
              <MenuItem value="90d">Last 90 days</MenuItem>
              <MenuItem value="365d">Last 365 days</MenuItem>
              <MenuItem value="lifetime">Lifetime</MenuItem>
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <BarChartIcon sx={{ fontSize: 16 }} /> Metrics
            </InputLabel>
            <Select multiple label="Metrics" value={metricsSelectValue} renderValue={() => `Metrics (${Object.values(visibleColumns).filter(Boolean).length})`}>
              <ListSubheader>Main Map Metric</ListSubheader>
              {METRIC_OPTIONS.map(o => (
                <MenuItem key={o.value} onClick={() => setMetric(o.value)}>
                  <Radio size="small" checked={metric === o.value} sx={{ color: METRICS[o.value].color, '&.Mui-checked': { color: METRICS[o.value].color } }} />
                  <Typography variant="body2">{o.label}</Typography>
                </MenuItem>
              ))}
              <Divider />
              <ListSubheader>Table Columns</ListSubheader>
              {TABLE_COLUMNS.map(c => (
                <MenuItem key={c.key} onClick={(e) => { e.stopPropagation(); setVisibleColumns(p => ({ ...p, [c.key]: !p[c.key] })); }}>
                  <Checkbox size="small" checked={visibleColumns[c.key]} />
                  <Typography variant="body2">{c.label}</Typography>
                </MenuItem>
              ))}
            </Select>
          </FormControl>

        </Stack>

        {/* MAP SECTION */}
        <Box
          sx={{
            ...glassSx,
            height: isDashboard ? 400 : 580,
            overflow: "hidden",
            position: "relative",
            background: isDark
              ? `radial-gradient(circle at 50% 50%, rgba(30, 41, 59, 0.4) 0%, rgba(15, 23, 42, 1) 100%)`
              : `radial-gradient(circle at 50% 50%, #f8fafc 0%, #f1f5f9 100%)`,
          }}
        >


          <ResponsiveChoropleth
            debounceResize={150}
            data={mapData}
            features={geoFeatures.features}
            valueFormat={mconf.fmt}
            domain={[0, domainMax]}
            colors={isDark ? "BuGn" : "blues"}

            theme={{
              background: "transparent",
              text: { fontSize: 12, fill: theme.palette.text.primary },
              tooltip: {
                container: {
                  background: isDark ? "rgba(11, 15, 25, 0.98)" : "#ffffff",
                  color: isDark ? "#f1f5f9" : "#1e293b",
                  fontSize: 13,
                  borderRadius: 12,
                  boxShadow: isDark ? "0 10px 30px rgba(0,0,0,0.6)" : "0 10px 25px rgba(0,0,0,0.1)",
                  padding: "10px 14px",
                  border: `1px solid ${isDark ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.08)"}`,
                }
              }
            }}
            unknownColor={isDark ? "rgba(255,255,255,0.04)" : "#e2e8f0"}
            projectionScale={isDashboard ? 100 : 150}
            projectionTranslation={[0.5, 0.65]}
            borderWidth={0.5}
            borderColor={isDark ? "rgba(255,255,255,0.1)" : "#94a3b8"}
            tooltip={({ feature }) => {
              if (feature.value === undefined) return null;
              const textColor = isDark ? "#f8fafc" : "#0f172a";
              const secondaryColor = isDark ? "#94a3b8" : "#64748b";
              const bgColor = isDark ? "#111827" : "#ffffff";

              return (
                <Box
                  sx={{
                    bgcolor: bgColor,
                    p: 1.5,
                    borderRadius: 2.5,
                    border: "1px solid",
                    borderColor: isDark ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.08)",
                    boxShadow: isDark ? "0 12px 36px rgba(0,0,0,0.5)" : "0 8px 24px rgba(15,23,42,0.15)",
                    minWidth: 160
                  }}
                >
                  <Stack spacing={0.75}>
                    <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
                      <Typography
                        variant="subtitle2"
                        sx={{
                          fontWeight: 800,
                          color: textColor,
                          fontSize: "0.875rem",
                          letterSpacing: "-0.01em"
                        }}
                      >
                        {resolvers.nameOf(feature.id)}
                      </Typography>
                      <Box
                        sx={{
                          width: 10,
                          height: 10,
                          borderRadius: "50%",
                          bgcolor: mconf.color,
                          boxShadow: `0 0 10px ${mconf.color}`
                        }}
                      />
                    </Box>
                    <Divider sx={{ opacity: 0.1, my: 0.5 }} />
                    <Box sx={{ display: "flex", alignItems: "baseline", gap: 1 }}>
                      <Typography
                        variant="caption"
                        sx={{
                          color: secondaryColor,
                          fontWeight: 500,
                          textTransform: "uppercase",
                          letterSpacing: "0.05em",
                          fontSize: "0.65rem"
                        }}
                      >
                        {mconf.label}
                      </Typography>
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: 700,
                          color: textColor,
                          fontSize: "0.9rem"
                        }}
                      >
                        {mconf.fmt(feature.value)}
                      </Typography>
                    </Box>
                  </Stack>
                </Box>
              );
            }}
          />
        </Box>

        {/* TABLE SECTION */}
        <Box sx={{ ...glassSx, p: 1, overflow: "hidden" }}>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ "& .MuiTableCell-head": { py: 2, fontWeight: 800, textTransform: "uppercase", fontSize: 11, letterSpacing: 1, opacity: 0.7 } }}>
                  <TableCell>Country</TableCell>
                  {TABLE_COLUMNS.map(c => visibleColumns[c.key] && (
                    <TableCell key={c.key} align="right">{c.label}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {/* TOTAL ROW */}
                <TableRow sx={{ bgcolor: isDark ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.02)" }}>
                  <TableCell sx={{ fontWeight: 900, fontSize: 13 }}>Total</TableCell>
                  {TABLE_COLUMNS.map(c => visibleColumns[c.key] && (
                    <TableCell key={c.key} align="right" sx={{ fontWeight: 900, color: mconf.key === c.key ? mconf.color : "inherit" }}>
                      {c.key === "averageViewDuration" ? formatSeconds(totals[c.key]) : c.key === "averageViewPercentage" ? percentStr(totals[c.key]) : formatNumber(totals[c.key])}
                    </TableCell>
                  ))}
                </TableRow>

                {/* DATA ROWS */}
                <AnimatePresence mode="popLayout">
                  {rows.map((r, idx) => (
                    <TableRow
                      component={motion.tr}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.03 }}
                      key={r.id}
                      hover
                      sx={{ "&:hover": { bgcolor: isDark ? "rgba(255,255,255,0.02) !important" : "rgba(0,0,0,0.01) !important" } }}
                    >
                      <TableCell sx={{ fontWeight: 600, fontSize: 13, borderLeft: idx < 3 ? `3px solid ${mconf.color}` : "none" }}>
                        {r.label}
                      </TableCell>

                      {TABLE_COLUMNS.map(c => {
                        if (!visibleColumns[c.key]) return null;
                        const isPrimary = mconf.key === c.key;
                        const pctValue = c.key === "views" ? r.viewsPct : c.key === "engagedViews" ? r.engagedPct : c.key === "watchTimeHours" ? r.watchPct : 0;

                        return (
                          <TableCell key={c.key} align="right">
                            <Box sx={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
                              <Typography variant="body2" sx={{ fontWeight: isPrimary ? 800 : 500, color: isPrimary ? mconf.color : "inherit" }}>
                                {c.key === "averageViewDuration" ? formatSeconds(r[c.key]) : c.key === "averageViewPercentage" ? percentStr(r[c.key]) : formatNumber(r[c.key])}
                              </Typography>
                              {pctValue > 0 && (
                                <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 0.5, width: 80 }}>
                                  <Box sx={{ flex: 1, height: 4, bgcolor: isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.05)", borderRadius: 2, overflow: "hidden" }}>
                                    <motion.div
                                      initial={{ width: 0 }}
                                      animate={{ width: `${pctValue}%` }}
                                      transition={{ duration: 1, delay: idx * 0.05 }}
                                      style={{ height: "100%", background: isPrimary ? mconf.color : "#94a3b8", borderRadius: 2 }}
                                    />
                                  </Box>
                                  <Typography sx={{ fontSize: 9, opacity: 0.6, width: 30, textAlign: "right" }}>{Math.round(pctValue)}%</Typography>
                                </Box>
                              )}
                            </Box>
                          </TableCell>
                        );
                      })}
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

export default GeographyChart;
