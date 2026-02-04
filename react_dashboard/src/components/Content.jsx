import { useState, useEffect, useCallback, useMemo, useRef } from "react";
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
  TablePagination,
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
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

import api from "../services/api";

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

const VideoThumbnail = ({ src, videoId, alt, duration }) => {
  const theme = useTheme();
  const [currentSrc, setCurrentSrc] = useState(src);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    setCurrentSrc(src);
    setHasError(false);
  }, [src]);

  // Better retry logic:
  const handleImgError = (e) => {
    if (videoId && currentSrc.includes("mqdefault")) {
      setCurrentSrc(`https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`);
    } else if (videoId && currentSrc.includes("hqdefault")) {
      setCurrentSrc(`https://i.ytimg.com/vi/${videoId}/default.jpg`);
    } else {
      setHasError(true);
    }
  };

  if (hasError || !currentSrc) {
    return (
      <Box
        sx={{
          width: 90,
          aspectRatio: "16/9",
          borderRadius: 1.5,
          bgcolor: theme.palette.mode === "dark" ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          border: "1px solid",
          borderColor: theme.palette.divider,
        }}
      >
        {/* Optional: Icon for missing image? */}
      </Box>
    );
  }

  return (
    <Box sx={{ position: "relative", display: "inline-flex" }}>
      <img
        src={currentSrc}
        width={90}
        style={{ borderRadius: 6 }}
        alt={alt || ""}
        onError={handleImgError}
      />
      {duration != null && (
        <Box
          sx={{
            position: "absolute",
            right: 4,
            bottom: 4,
            px: 0.5,
            py: 0.25,
            borderRadius: 0.75,
            fontSize: 11,
            fontWeight: 600,
            color: "#fff",
            backgroundColor: "rgba(15,23,42,0.8)",
          }}
        >
          {formatDuration(duration)}
        </Box>
      )}
    </Box>
  );
};

const ContentAnalytics = () => {
  const theme = useTheme();

  const [videos, setVideos] = useState([]);
  const [timeseries, setTimeseries] = useState([]);
  const [channelList, setChannelList] = useState([]);
  const chartRef = useRef(null);

  const [chartType, setChartType] = useState("line");
  const [metric, setMetric] = useState("views");
  const [period, setPeriod] = useState("last28");
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(50);

  const [channelId, setChannelId] = useState(() => {
    try {
      return localStorage.getItem("content.selectedChannelId") || "";
    } catch {
      return "";
    }
  });
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  /* ================================
     LOAD CHANNELS
  ================================= */
  useEffect(() => {
    (async () => {
      try {
        const resp = await api.get("/api/content/channels");
        const data = resp.data;

        const items =
          data.items?.map((c) => ({
            id: c.value,
            title: c.label,
          })) ?? [];

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
        const byId = new Map(items.map((c) => [orderKey(c.id), c]));
        const ordered = order
          .map((name) => byId.get(orderKey(name)))
          .filter(Boolean);
        const remaining = items.filter(
          (c) => !order.map(orderKey).includes(orderKey(c.id))
        );
        const finalChannels = [...ordered, ...remaining];
        setChannelList(finalChannels);
        if (!finalChannels.length) {
          setChannelId("");
        } else if (!channelId || !finalChannels.some((c) => c.id === channelId)) {
          setChannelId(finalChannels[0].id);
        }
      } catch (err) {
        console.error("Load channels failed:", err);
      }
    })();
  }, [channelId]);

  useEffect(() => {
    if (!channelId) return;
    try {
      localStorage.setItem("content.selectedChannelId", channelId);
    } catch {
      // ignore storage errors
    }
  }, [channelId]);

  /* ================================
     API CALLS
  ================================= */
  const fetchVideos = useCallback(
    async (start, end) => {
      if (!channelId) return;
      try {
        const resp = await api.post("/api/content/list", {
          start,
          end,
          channelId,
        });

        const raw = resp.data;
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
        const resp = await api.post("/api/content/timeseries", {
          start,
          end,
          channelId,
        });

        const raw = resp.data;
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
        cardImpressions: n(v.cardImpressions),
        adImpressions: n(v.adImpressions),
        annotationImpressions: n(v.annotationImpressions),
      })),
    [videos]
  );

  const totals = useMemo(
    () => ({
      views: rows.reduce((s, r) => s + r.views, 0),
      watchHours: rows.reduce((s, r) => s + r.watchHours, 0),
      likes: rows.reduce((s, r) => s + r.likes, 0),
      cardImpressions: rows.reduce((s, r) => s + r.cardImpressions, 0),
      adImpressions: rows.reduce((s, r) => s + r.adImpressions, 0),
      annotationImpressions: rows.reduce((s, r) => s + r.annotationImpressions, 0),
    }),
    [rows]
  );

  const pagedRows = useMemo(() => {
    const start = page * rowsPerPage;
    const end = start + rowsPerPage;
    return rows.slice(start, end);
  }, [rows, page, rowsPerPage]);

  /* ================================
     CHART DATA
  ================================= */
  const lineData = useMemo(() => {
    if (chartType !== "line") return [];

    // 1. Identify all unique dates in the timeseries
    const allDatesSet = new Set();
    timeseries.forEach(t => {
      const d = dayjs(t.bucket).startOf('day').toDate().getTime();
      allDatesSet.add(d);
    });
    const allDatesSorted = Array.from(allDatesSet).sort((a, b) => a - b).map(t => new Date(t));

    const map = new Map();
    timeseries.forEach((t) => {
      const id = t.videoId;
      if (!id) return;
      const title = t.title || id;
      if (!map.has(id)) {
        map.set(id, new Map());
      }
      const metricKey =
        {
          views: "views",
          estimatedMinutesWatched: "watch_hours",
        }[metric] ?? "views";

      const d = dayjs(t.bucket).startOf('day').toDate().getTime();
      map.get(id).set(d, { y: n(t[metricKey]), title });
    });

    return Array.from(map.entries()).map(([id, dataMap]) => {
      const data = allDatesSorted.map(d => {
        const entry = dataMap.get(d.getTime());
        return {
          x: d,
          y: entry ? entry.y : 0,
          videoId: id,
          title: entry ? entry.title : id
        };
      });
      return { id, data };
    });
  }, [timeseries, chartType, metric]);

  const lineDateExtent = useMemo(() => {
    if (!lineData.length || !lineData[0].data.length) return { min: "auto", max: "auto" };
    const first = lineData[0].data[0].x;
    const last = lineData[0].data[lineData[0].data.length - 1].x;
    return { min: first, max: last };
  }, [lineData]);

  // Chọn tick ngày thưa để không đè chữ
  const xTickValues = useMemo(() => {
    if (!timeseries.length) return [];
    const allDates = timeseries.map((t) => dayjs(t.bucket).startOf("day").toDate());
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

  const seriesColors = useMemo(() => {
    const palette = [
      "#e41a1c",
      "#377eb8",
      "#4daf4a",
      "#984ea3",
      "#ff7f00",
      "#ffff33",
      "#a65628",
      "#f781bf",
      "#999999",
    ];
    const map = {};
    lineData.forEach((serie, index) => {
      map[serie.id] = palette[index % palette.length];
    });
    return map;
  }, [lineData]);

  const latestVideoIds = useMemo(() => {
    return rows
      .filter((r) => r.published)
      .slice()
      .sort((a, b) => new Date(b.published) - new Date(a.published))
      .map((r) => r.id)
      .slice(0, 5);
  }, [rows]);

  const hasBarData =
    barPrep.data && barPrep.data.length > 0 && barPrep.keys && barPrep.keys.length > 0;

  const tablePaperSx = useMemo(
    () => ({
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
      overflow: "hidden",
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
            value={channelList.some((c) => c.id === channelId) ? channelId : ""}
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
        ref={chartRef}
        sx={{
          height: 420,
          minWidth: 320,
          borderRadius: 2,
          border: `1px solid ${theme.palette.mode === "dark"
            ? "rgba(255,255,255,0.08)"
            : "rgba(0,0,0,0.06)"
            }`,
          p: 1,
        }}
      >
        {chartType === "line" && lineData.length > 0 && (
          <ResponsiveLine
            debounceResize={150}
            data={lineData}
            margin={{ top: 32, right: 8, bottom: 64, left: 56 }}
            xScale={{
              type: "time",
              format: "native",
              useUTC: false,
              precision: "day",
              min: lineDateExtent.min,
              max: lineDateExtent.max
            }}
            yScale={{ type: "linear", min: 0, stacked: false }}
            curve="linear"
            enablePoints={true}
            pointSize={6}
            colors={(serie) => seriesColors[serie.id] || "#60a5fa"}
            useMesh
            enableSlices="x"
            enableCrosshair
            crosshairType="cross"
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
              crosshair: {
                line: {
                  stroke:
                    theme.palette.mode === "dark"
                      ? "rgba(226,232,240,0.45)"
                      : "rgba(15,23,42,0.35)",
                  strokeWidth: 1,
                  strokeDasharray: "3 3",
                },
              },
            }}
            sliceTooltip={({ slice }) => {
              const p0 = slice.points[0];
              const dateLabel =
                p0?.data?.x instanceof Date
                  ? dayjs(p0.data.x).format("DD/MM/YYYY")
                  : String(p0?.data?.x ?? "");

              const isRightSide = chartRef.current && slice.x > chartRef.current.offsetWidth / 2;

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
                    transform: isRightSide ? "translateX(-110%)" : "translateX(10%)",
                    transition: "transform 0.1s ease-out",
                  }}
                >
                  <Box sx={{ mb: 0.75, color: "text.secondary" }}>{dateLabel}</Box>

                  {slice.points
                    .slice()
                    .sort((a, b) => (b.data.y ?? 0) - (a.data.y ?? 0))
                    .slice(0, 5)
                    .map((p) => {
                      const value = formatMetricValue(metric, p.data.y);
                      const name = p.data.title || p.serieId;
                      const label =
                        name && name.length > 28 ? `${name.slice(0, 28)}...` : name;

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
                                background: seriesColors[p.serieId] || p.color,
                                display: "inline-block",
                              }}
                            />
                            <span style={{ fontSize: 12, fontWeight: 600 }}>
                              {label}
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
            debounceResize={150}
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
      <TableContainer component={Paper} elevation={0} sx={tablePaperSx}>
        <Table size="small">
          <TableHead sx={tableHeadSx}>
            <TableRow>
              <TableCell>Video</TableCell>
              <TableCell>Publish Date</TableCell>
              <TableCell align="right">Views</TableCell>
              <TableCell align="right">Watch Hours</TableCell>
              <TableCell align="right">Likes</TableCell>
              <TableCell align="right">Cards impressions</TableCell>
              <TableCell align="right">Ad impressions</TableCell>
              <TableCell align="right">Annotation impressions</TableCell>
            </TableRow>
          </TableHead>

          <TableBody>
            {pagedRows.map((r) => (
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
                <TableCell
                  sx={{
                    borderLeft: latestVideoIds.includes(r.id)
                      ? `4px solid ${seriesColors[r.id] || "transparent"}`
                      : "4px solid transparent",
                    pl: 1.5,
                  }}
                >
                  <Stack direction="row" spacing={1} alignItems="center">
                    <a
                      href={`https://www.youtube.com/watch?v=${r.id}`}
                      target="_blank"
                      rel="noreferrer"
                      style={{ display: "inline-flex" }}
                    >
                      <VideoThumbnail src={r.thumbnail} duration={r.duration} videoId={r.id} />
                    </a>
                    <a
                      href={`https://www.youtube.com/watch?v=${r.id}`}
                      target="_blank"
                      rel="noreferrer"
                      style={{ color: "inherit", textDecoration: "none" }}
                    >
                      {r.title}
                    </a>
                  </Stack>
                </TableCell>

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
                  {formatNumber(r.cardImpressions)}
                </TableCell>
                <TableCell align="right">
                  {formatNumber(r.adImpressions)}
                </TableCell>
                <TableCell align="right">
                  {formatNumber(r.annotationImpressions)}
                </TableCell>
              </TableRow>
            ))}

            {/* Total */}
            <TableRow>
              <TableCell sx={{ fontWeight: 700 }}>TOTAL</TableCell>
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
                {formatNumber(totals.cardImpressions)}
              </TableCell>
              <TableCell align="right">
                {formatNumber(totals.adImpressions)}
              </TableCell>
              <TableCell align="right">
                {formatNumber(totals.annotationImpressions)}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <TablePagination
          component="div"
          count={rows.length}
          page={page}
          onPageChange={(_, nextPage) => setPage(nextPage)}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={(e) => {
            setRowsPerPage(Number(e.target.value) || 10);
            setPage(0);
          }}
          rowsPerPageOptions={[25, 50, 100, 200]}
        />
      </TableContainer>
    </Stack>
  );
};

export default ContentAnalytics;
