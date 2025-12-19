// src/components/ContentAnalytics.jsx
import { useState, useEffect, useCallback, useMemo } from "react";
import { useTheme } from "@mui/material/styles";
import {
  Box,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  FormControl,
  Select,
  MenuItem,
  InputLabel,
} from "@mui/material";

import dayjs from "dayjs";
import { LocalizationProvider, DatePicker } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";

import { ResponsiveLine } from "@nivo/line";
import { ResponsiveBar } from "@nivo/bar";
import { formatDuration } from './Module';

import {
  METRIC_OPTIONS,
  PERIOD_OPTIONS,
  getRangeForPeriod,
  getMonthRange,
  n,
  formatNumber,
  pickTicks, // dùng để chọn ít tick ngày
} from "./Module";

import { API_BASE } from "../config";

/* Extra periods – chỉ khai báo value + label (không chứa ngày) */
const EXTRA_PERIODS = [
  { value: "month_current", label: "This month" },
  { value: "month_prev", label: "Last month" },
  { value: "month_prev2", label: "Preceding month" },
  { value: "year_current", label: "This year" },
  { value: "year_prev", label: "Last year" },
  { value: "last14", label: "Last 14 days" },
  { value: "last180", label: "Last 180 days" },
];

// 🟣 helper riêng cho watch hours (hiển thị thập phân)
const formatWatchHours = (v, digits = 1) =>
  n(v).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

// 🟣 helper để format Y-axis / tooltip theo metric đang chọn
const formatMetricValue = (metric, v) => {
  if (metric === "estimatedMinutesWatched") {
    // đang map sang watch_hours (giờ) → hiển thị 1 chữ số thập phân
    return formatWatchHours(v);
  }
  return formatNumber(v);
};

const ContentAnalytics = () => {
  const theme = useTheme();

  const [videos, setVideos] = useState([]);
  const [timeseries, setTimeseries] = useState([]);
  const [channelList, setChannelList] = useState([]);

  const [chartType, setChartType] = useState("line");
  const [metric, setMetric] = useState("views");
  const [period, setPeriod] = useState("last28");

  const [channelId, setChannelId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  /* ================================
     LOAD CHANNELS
  ================================= */
  useEffect(() => {
    (async () => {
      try {
        const resp = await fetch(`${API_BASE}/api/content/channels`);
        const data = await resp.json();

        const items =
          data.items?.map((c) => ({
            id: c.value,
            title: c.label,
          })) ?? [];

        setChannelList(items);

        if (!channelId && items.length > 0) {
          setChannelId(items[0].id);
        }
      } catch (err) {
        console.error("Load channels failed:", err);
      }
    })();
  }, [channelId]);

  /* ================================
     API CALLS
  ================================= */
  const fetchVideos = useCallback(
    async (start, end) => {
      if (!channelId) return;
      try {
        const resp = await fetch(`${API_BASE}/api/content/list`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ start, end, channelId }),
        });

        const raw = await resp.json();
        setVideos(raw.items ?? []);
      } catch (err) {
        console.error("Fetch videos failed:", err);
        setVideos([]);
      }
    },
    [channelId]
  );

  const fetchTimeseries = useCallback(
    async (start, end) => {
      if (!channelId) return;
      try {
        const resp = await fetch(`${API_BASE}/api/content/timeseries`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ start, end, channelId }),
        });

        const raw = await resp.json();
        setTimeseries(raw.items ?? []);
      } catch (err) {
        console.error("Fetch timeseries failed:", err);
        setTimeseries([]);
      }
    },
    [channelId]
  );

  /* ================================
     PERIOD HANDLING
  ================================= */
  const resolvePeriod = useCallback(() => {
    const now = new Date();

    if (period === "custom") {
      return { start: startDate, end: endDate };
    }

    // Month-based
    if (period === "month_current") return getMonthRange(0, now);
    if (period === "month_prev") return getMonthRange(1, now);
    if (period === "month_prev2") return getMonthRange(2, now);

    // Year-based
    if (period === "year_current") {
      return {
        start: dayjs().startOf("year").format("YYYY-MM-DD"),
        end: dayjs().endOf("year").format("YYYY-MM-DD"),
      };
    }
    if (period === "year_prev") {
      return {
        start: dayjs().subtract(1, "year").startOf("year").format("YYYY-MM-DD"),
        end: dayjs().subtract(1, "year").endOf("year").format("YYYY-MM-DD"),
      };
    }

    // Normal (last7, last28, last90, last365, y-2024, y-2025…)
    const r = getRangeForPeriod(period, now);

    if (period === "lifetime") {
      return {
        start: r.start || "2000-01-01",
        end: r.end || dayjs(now).format("YYYY-MM-DD"),
      };
    }

    return r;
  }, [period, startDate, endDate]);

  // Fetch khi period / channel thay đổi
  useEffect(() => {
    if (!channelId) return;

    const { start, end } = resolvePeriod();
    if (!start || !end) return;

    fetchVideos(start, end);
    fetchTimeseries(start, end);
  }, [resolvePeriod, fetchVideos, fetchTimeseries, channelId]);

  /* ================================
     TABLE ROWS
  ================================= */
  const rows = useMemo(
    () =>
      videos.map((v) => ({
        id: v.videoId,
        title: v.title,
        thumbnail: v.thumbnail,
        published: v.publishedAt,
        duration: v.duration,

        views: n(v.views),
        watchHours: n(v.watchTimeHours), // có thể là số thập phân
        likes: n(v.likes),
        revenue: n(v.estimatedRevenue),
        impressions: n(v.impressions),
        ctr: n(v.ctr),
      })),
    [videos]
  );

  const totals = useMemo(
    () => ({
      views: rows.reduce((s, r) => s + r.views, 0),
      watchHours: rows.reduce((s, r) => s + r.watchHours, 0),
      likes: rows.reduce((s, r) => s + r.likes, 0),
      revenue: rows.reduce((s, r) => s + r.revenue, 0),
      impressions: rows.reduce((s, r) => s + r.impressions, 0),
    }),
    [rows]
  );

  /* ================================
     CHART DATA
  ================================= */
  const lineData = useMemo(() => {
    if (chartType !== "line") return [];

    const map = new Map();
    timeseries.forEach((t) => {
      const id = t.videoId;
      if (!id) return;

      const title = t.title || id;

      if (!map.has(id)) {
        map.set(id, { id, data: [] });
      }

      const metricKey =
        {
          views: "views",
          estimatedMinutesWatched: "watch_hours", // map sang watch_hours
        }[metric] ?? "views";

      map.get(id).data.push({
        x: new Date(t.bucket),
        y: n(t[metricKey]),
        videoId: id,
        title,
      });
    });

    return [...map.values()];
  }, [timeseries, chartType, metric]);

  // Chọn tick ngày thưa để không đè chữ
  const xTickValues = useMemo(() => {
    if (!timeseries.length) return [];
    const allDates = timeseries.map((t) => new Date(t.bucket));
    return pickTicks(allDates, 7); // tối đa 7 tick
  }, [timeseries]);

  const barPrep = useMemo(() => {
    if (chartType !== "bar") return { keys: [], data: [] };

    const metricKey =
      {
        views: "views",
      }[metric] ?? "views";

    return {
      keys: rows.map((r) => r.id),
      data: rows.map((r) => ({
        video: r.title,
        [r.id]: r[metricKey],
      })),
    };
  }, [rows, chartType, metric]);

  const hasBarData =
    barPrep.data && barPrep.data.length > 0 && barPrep.keys && barPrep.keys.length > 0;

  /* ================================
     UI
  ================================= */
  return (
    <Stack spacing={2}>
      {/* FILTERS */}
      <Stack direction="row" spacing={2} flexWrap="wrap">
        {/* Metric */}
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Metric</InputLabel>
          <Select
            value={metric}
            label="Metric"
            onChange={(e) => setMetric(e.target.value)}
          >
            {METRIC_OPTIONS.map((m) => (
              <MenuItem key={m.value} value={m.value}>
                {m.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Chart */}
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel>Chart</InputLabel>
          <Select
            value={chartType}
            label="Chart"
            onChange={(e) => setChartType(e.target.value)}
          >
            <MenuItem value="bar">Bar</MenuItem>
            <MenuItem value="line">Line</MenuItem>
          </Select>
        </FormControl>

        {/* Period */}
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Period</InputLabel>
          <Select
            value={period}
            label="Period"
            onChange={(e) => setPeriod(e.target.value)}
          >
            {[...PERIOD_OPTIONS, ...EXTRA_PERIODS].map((p) => (
              <MenuItem key={p.value} value={p.value}>
                {p.label}
              </MenuItem>
            ))}
            <MenuItem value="custom">Custom</MenuItem>
          </Select>
        </FormControl>

        {/* Channel */}
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Channel</InputLabel>
          <Select
            value={channelId}
            label="Channel"
            onChange={(e) => setChannelId(e.target.value)}
          >
            {channelList.map((c) => (
              <MenuItem key={c.id} value={c.id}>
                {c.title}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Custom date range */}
        {period === "custom" && (
          <LocalizationProvider dateAdapter={AdapterDayjs}>
            <Stack direction="row" spacing={1}>
              <DatePicker
                label="Start"
                value={startDate ? dayjs(startDate) : null}
                onChange={(v) =>
                  setStartDate(v ? v.format("YYYY-MM-DD") : "")
                }
              />
              <DatePicker
                label="End"
                value={endDate ? dayjs(endDate) : null}
                onChange={(v) =>
                  setEndDate(v ? v.format("YYYY-MM-DD") : "")
                }
              />
            </Stack>
          </LocalizationProvider>
        )}
      </Stack>

      {/* CHART */}
      <Box
        sx={{
          height: 420,
          minWidth: 320,
          borderRadius: 2,
          border: `1px solid ${
            theme.palette.mode === "dark"
              ? "rgba(255,255,255,0.08)"
              : "rgba(0,0,0,0.06)"
          }`,
          p: 1,
        }}
      >
        {chartType === "line" && lineData.length > 0 && (
          <ResponsiveLine
            data={lineData}
            margin={{ top: 32, right: 24, bottom: 64, left: 56 }}
            xScale={{ type: "time", format: "native", useUTC: false, precision: "day" }}
            yScale={{ type: "linear", min: 0, stacked: false }}
            curve="monotoneX"
            enableArea
            areaOpacity={0.12}
            enablePoints={true}
            pointSize={6}
            colors={{ scheme: "set1" }}
            useMesh
            enableSlices="x"
            axisBottom={{
              tickValues: xTickValues,
              tickSize: 0,
              tickPadding: 10,
              renderTick: (tick) => {
                const d =
                  tick.value instanceof Date ? tick.value : new Date(tick.value);
                const label = dayjs(d).format("DD/MM");
                const color =
                  theme.palette.mode === "dark" ? "#e5e7eb" : "#374151";

                return (
                  <g
                    transform={`translate(${tick.x},${tick.y})`}
                    style={{ pointerEvents: "none" }}
                  >
                    <text
                      y={6}
                      textAnchor="middle"
                      dominantBaseline="hanging"
                      style={{
                        fill: color,
                        fontSize: 11,
                        fontWeight: 600,
                      }}
                    >
                      {label}
                    </text>
                  </g>
                );
              },
            }}
            axisLeft={{
              tickSize: 0,
              tickPadding: 8,
              format: (v) => formatMetricValue(metric, v),
            }}
            theme={{
              axis: {
                ticks: {
                  text: {
                    fill: theme.palette.mode === "dark" ? "#e5e7eb" : "#374151",
                    fontSize: 11,
                    fontWeight: 600,
                  },
                  line: {
                    stroke:
                      theme.palette.mode === "dark"
                        ? "rgba(148,163,184,0.4)"
                        : "rgba(148,163,184,0.6)",
                  },
                },
                legend: {
                  text: {
                    fill: theme.palette.mode === "dark" ? "#e5e7eb" : "#374151",
                  },
                },
              },
              grid: {
                line: {
                  stroke:
                    theme.palette.mode === "dark"
                      ? "rgba(148,163,184,0.18)"
                      : "rgba(148,163,184,0.25)",
                  strokeWidth: 1,
                  strokeDasharray: "4 4",
                },
              },
            }}
            sliceTooltip={({ slice }) => {
              const p0 = slice.points[0];
              const dateLabel =
                p0?.data?.x instanceof Date
                  ? dayjs(p0.data.x).format("DD/MM/YYYY")
                  : String(p0?.data?.x ?? "");

              return (
                <Box
                  sx={{
                    px: 1.25,
                    py: 1,
                    borderRadius: 1,
                    bgcolor:
                      theme.palette.mode === "dark"
                        ? "rgba(15,23,42,0.95)"
                        : "rgba(255,255,255,0.98)",
                    border: `1px solid ${theme.palette.divider}`,
                    boxShadow: 3,
                    fontSize: 13,
                  }}
                >
                  <Box sx={{ mb: 0.75, color: "text.secondary" }}>{dateLabel}</Box>

                  {slice.points.map((p) => {
                    const value = formatMetricValue(metric, p.data.y);
                    const name = p.data.title || p.serieId;

                    return (
                      <Box
                        key={p.id}
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: 1,
                        }}
                      >
                        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
                          <span
                            style={{
                              width: 10,
                              height: 10,
                              borderRadius: 2,
                              background: p.color,
                              display: "inline-block",
                            }}
                          />
                          <span style={{ fontSize: 12, fontWeight: 600 }}>
                            {name}
                          </span>
                        </Box>
                        <span>{value}</span>
                      </Box>
                    );
                  })}
                </Box>
              );
            }}
          />
        )}

        {chartType === "line" && lineData.length === 0 && (
          <Box
            sx={{
              height: 1,
              minHeight: 120,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "text.secondary",
              fontSize: 14,
            }}
          >
            No timeseries data in this range.
          </Box>
        )}

        {chartType === "bar" && hasBarData && (
          <ResponsiveBar
            data={barPrep.data}
            keys={barPrep.keys}
            indexBy="video"
            margin={{ top: 32, right: 16, bottom: 80, left: 56 }}
            padding={0.2}
            valueScale={{ type: "linear" }}
            indexScale={{ type: "band", round: true }}
            enableGridX={false}
            axisBottom={{
              tickRotation: -40,
              tickPadding: 6,
              renderTick: (tick) => {
                const label = String(tick.value);
                const color =
                  theme.palette.mode === "dark" ? "#e5e7eb" : "#374151";
                return (
                  <g transform={`translate(${tick.x},${tick.y})`}>
                    <text
                      y={6}
                      textAnchor="end"
                      dominantBaseline="hanging"
                      style={{
                        fill: color,
                        fontSize: 11,
                      }}
                    >
                      {label}
                    </text>
                  </g>
                );
              },
            }}
            axisLeft={{
              tickSize: 0,
              tickPadding: 8,
              format: (v) => formatNumber(v),
            }}
            labelSkipWidth={12}
            labelSkipHeight={12}
            labelTextColor={{
              from: "color",
              modifiers: [["darker", 2.5]],
            }}
            tooltip={({ id, value, indexValue }) => (
              <Box
                sx={{
                  px: 1,
                  py: 0.75,
                  borderRadius: 1,
                  bgcolor:
                    theme.palette.mode === "dark"
                      ? "rgba(15,23,42,0.95)"
                      : "rgba(255,255,255,0.98)",
                  border: `1px solid ${theme.palette.divider}`,
                  boxShadow: 3,
                  fontSize: 13,
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: 2 }}>
                  {String(indexValue)}
                </div>
                <div>{formatNumber(value)}</div>
              </Box>
            )}
            legends={[]}
          />
        )}

        {chartType === "bar" && !hasBarData && (
          <Box
            sx={{
              height: 1,
              minHeight: 120,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "text.secondary",
              fontSize: 14,
            }}
          >
            No data to display.
          </Box>
        )}
      </Box>

      {/* TABLE */}
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Video</TableCell>
              <TableCell>Duration</TableCell>
              <TableCell>Publish Date</TableCell>
              <TableCell align="right">Views</TableCell>
              <TableCell align="right">Watch Hours</TableCell>
              <TableCell align="right">Likes</TableCell>
              <TableCell align="right">Revenue</TableCell>
              <TableCell align="right">Impressions</TableCell>
              <TableCell align="right">CTR</TableCell>
            </TableRow>
          </TableHead>

          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.id}>
                <TableCell>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <img
                      src={r.thumbnail}
                      width={90}
                      style={{ borderRadius: 6 }}
                      alt=""
                    />
                    <span>{r.title}</span>
                  </Stack>
                </TableCell>

                <TableCell>{formatDuration(r.duration)}</TableCell>
                <TableCell>
                  {r.published
                    ? dayjs(r.published).format("DD-MM-YYYY")
                    : ""}
                </TableCell>

                <TableCell align="right">
                  {formatNumber(r.views)}
                </TableCell>

                {/* 🟣 dùng formatWatchHours → số thập phân */}
                <TableCell align="right">
                  {formatWatchHours(r.watchHours)}
                </TableCell>

                <TableCell align="right">
                  {formatNumber(r.likes)}
                </TableCell>
                <TableCell align="right">
                  ${formatNumber(r.revenue)}
                </TableCell>
                <TableCell align="right">
                  {formatNumber(r.impressions)}
                </TableCell>
                <TableCell align="right">
                  {r.ctr.toFixed(2)}%
                </TableCell>
              </TableRow>
            ))}

            {/* Total */}
            <TableRow>
              <TableCell sx={{ fontWeight: 700 }}>TOTAL</TableCell>
              <TableCell />
              <TableCell />
              <TableCell align="right">
                {formatNumber(totals.views)}
              </TableCell>
              <TableCell align="right">
                {formatWatchHours(totals.watchHours)}
              </TableCell>
              <TableCell align="right">
                {formatNumber(totals.subs)}
              </TableCell>
              <TableCell align="right">
                ${formatNumber(totals.revenue)}
              </TableCell>
              <TableCell align="right">
                {formatNumber(totals.impressions)}
              </TableCell>
              <TableCell align="right">—</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
};

export default ContentAnalytics;
