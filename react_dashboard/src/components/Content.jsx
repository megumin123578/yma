import { useState, useEffect, useCallback, useMemo, useRef, memo } from "react";

import { useTheme } from "@mui/material/styles";

import {

  Box,
  Stack,
  Typography,
  Avatar,
  Checkbox,
  ListItemText,
  Table,
  TableBody,

  TableCell,

  TableContainer,

  TableHead,

  TableRow,
  TableSortLabel,

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



const TABLE_METRIC_OPTIONS = [

  { value: "averageViewDuration", label: "Average view duration", type: "duration" },

  { value: "averagePercentageViewed", label: "Average percentage viewed", type: "percent" },

  { value: "engagedViews", label: "Engaged views", type: "number" },

  { value: "stayedToWatch", label: "Stayed to watch", type: "percent" },

  { value: "uniqueViewers", label: "Unique viewers", type: "number" },

  { value: "averageViewsPerViewer", label: "Average views per viewer", type: "decimal" },

  { value: "newViewers", label: "New viewers", type: "number" },

  { value: "returningViewers", label: "Returning viewers", type: "number" },

  { value: "casualViewers", label: "Casual viewers", type: "number" },

  { value: "regularViewers", label: "Regular viewers", type: "number" },

  { value: "views", label: "Views", type: "number" },

  { value: "watchTimeHours", label: "Watch time (hours)", type: "hours" },

  { value: "subscribers", label: "Subscribers", type: "number" },

  { value: "estimatedRevenue", label: "Estimated revenue", type: "currency" },

  { value: "impressions", label: "Impressions", type: "number" },

  { value: "impressionsClickThroughRate", label: "Impressions click-through rate", type: "percent" },

];



const DEFAULT_TABLE_METRICS = [

  "views",

  "watchTimeHours",

  "subscribers",

  "estimatedRevenue",

  "impressions",

  "impressionsClickThroughRate",

];



const NON_SUM_METRICS = new Set([

  "averageViewDuration",

  "averagePercentageViewed",

  "stayedToWatch",

  "averageViewsPerViewer",

  "impressionsClickThroughRate",

]);



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

const toNullableNumber = (value) => {
  if (value === null || value === undefined || value === "") return null;
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
};

const formatTableMetricValue = (metricKey, value) => {
  if (value === null || value === undefined) return "-";
  const meta = TABLE_METRIC_OPTIONS.find((m) => m.value === metricKey);
  const safe = n(value);
  if (!meta) return formatNumber(safe);

  if (meta.type === "duration") return formatDuration(safe);

  if (meta.type === "hours") return formatWatchHours(safe);

  if (meta.type === "currency") return `$${formatNumber(safe)}`;

  if (meta.type === "percent") return `${safe.toFixed(2)}%`;

  if (meta.type === "decimal") return safe.toFixed(2);

  return formatNumber(safe);

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



const LineChart = memo(function LineChart({

  data,

  margin,

  lineDateExtent,

  xTickValues,

  metric,

  themeMode,

  seriesColors,

  onSliceMove,

  onSliceLeave,

}) {

  const isDark = themeMode === "dark";

  const axisTextColor = isDark ? "#e5e7eb" : "#374151";



  const colorFn = useCallback(

    (serie) => seriesColors[serie.id] || "#60a5fa",

    [seriesColors]

  );



  const renderBottomTick = useCallback(

    (tick) => {

      const d = tick.value instanceof Date ? tick.value : new Date(tick.value);

      const label = dayjs(d).format("DD/MM");



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



  const axisBottom = useMemo(

    () => ({

      tickValues: xTickValues,

      tickSize: 0,

      tickPadding: 10,

      renderTick: renderBottomTick,

    }),

    [xTickValues, renderBottomTick]

  );



  const axisLeft = useMemo(

    () => ({

      tickSize: 0,

      tickPadding: 8,

      format: (v) => formatMetricValue(metric, v),

    }),

    [metric]

  );



  const nivoTheme = useMemo(

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

        legend: {

          text: { fill: axisTextColor },

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

      margin={margin}

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

      enablePoints={true}

      pointSize={6}

      colors={colorFn}

      enableSlices="x"

      enableCrosshair

      crosshairType="cross"

      tooltip={() => null}

      sliceTooltip={() => null}

      onMouseMove={onSliceMove}

      onMouseLeave={onSliceLeave}

      axisBottom={axisBottom}

      axisLeft={axisLeft}

      theme={nivoTheme}

    />

  );

});



LineChart.displayName = "LineChart";



const ContentAnalytics = () => {

  const theme = useTheme();

  const LINE_MARGIN = useMemo(

    () => ({ top: 32, right: 8, bottom: 64, left: 56 }),

    []

  );

  const chartPaddingPx = useMemo(() => {

    const n = Number.parseFloat(theme.spacing(1));

    return Number.isFinite(n) ? n : 0;

  }, [theme]);



  const [videos, setVideos] = useState([]);

  const [timeseries, setTimeseries] = useState([]);

  const [channelList, setChannelList] = useState([]);

  const [channelMetrics, setChannelMetrics] = useState(null);

  const chartRef = useRef(null);

  const [hoverSlice, setHoverSlice] = useState(null);



  const [chartType, setChartType] = useState("line");

  const [metric, setMetric] = useState("views");

  const [period, setPeriod] = useState("last28");

  const [selectedTableMetrics, setSelectedTableMetrics] = useState(DEFAULT_TABLE_METRICS);

  const [page, setPage] = useState(0);

  const [rowsPerPage, setRowsPerPage] = useState(50);
  const [sortKey, setSortKey] = useState("views");
  const [sortDirection, setSortDirection] = useState("desc");



  const [channelId, setChannelId] = useState(() => {

    try {

      return localStorage.getItem("content.selectedChannelId") || "";

    } catch {

      return "";

    }

  });

  const [startDate, setStartDate] = useState("");

  const [endDate, setEndDate] = useState("");

  const [loadingVideos, setLoadingVideos] = useState(false);
  const [loadingTimeseries, setLoadingTimeseries] = useState(false);
  const [loadingChannelMetrics, setLoadingChannelMetrics] = useState(false);

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
            avatar: c.avatar,
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

        setChannelId((current) => {
          if (!finalChannels.length) return "";
          if (!current || !finalChannels.some((c) => c.id === current)) {
            return finalChannels[0].id;
          }
          return current;
        });

      } catch (err) {

        console.error("Load channels failed:", err);

      }

    })();

  }, []);



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

      setLoadingVideos(true);

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

      } finally {

        setLoadingVideos(false);

      }

    },

    [channelId]

  );



  const fetchTimeseries = useCallback(

    async (start, end) => {

      if (!channelId) return;

      setLoadingTimeseries(true);

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

      } finally {

        setLoadingTimeseries(false);

      }

    },

    [channelId]

  );

  const fetchChannelMetrics = useCallback(

    async (start, end) => {

      if (!channelId) return;

      setChannelMetrics(null);
      setLoadingChannelMetrics(true);

      try {

        const resp = await api.post("/api/content/channel-metrics", {

          start,

          end,

          channelId,

        });



        setChannelMetrics(resp.data ?? null);

      } catch (err) {

        console.error("Fetch channel metrics failed:", err);

        setChannelMetrics(null);

      } finally {

        setLoadingChannelMetrics(false);

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

    fetchChannelMetrics(start, end);

  }, [resolvePeriod, fetchVideos, fetchTimeseries, fetchChannelMetrics, channelId]);



  /* ================================

     TABLE ROWS

  ================================= */

  const rows = useMemo(

    () =>

      videos

        .map((v) => ({

          id: v.videoId,

          title: v.title,

          thumbnail: v.thumbnail,

          published: v.publishedAt,

          duration: v.duration,

          views: n(v.views),
          watchHours: n(v.watchTimeHours),
          watchTimeHours: n(v.watchTimeHours),
          averageViewDuration: toNullableNumber(v.averageViewDuration ?? v.average_view_duration),
          averagePercentageViewed: toNullableNumber(v.averagePercentageViewed ?? v.average_view_percentage),
          engagedViews: toNullableNumber(v.engagedViews ?? v.engaged_views),
          stayedToWatch: toNullableNumber(v.stayedToWatch ?? v.stayed_to_watch),
          uniqueViewers: toNullableNumber(v.uniqueViewers ?? v.unique_viewers),
          averageViewsPerViewer: toNullableNumber(v.averageViewsPerViewer ?? v.average_views_per_viewer),
          newViewers: toNullableNumber(v.newViewers ?? v.new_viewers),
          returningViewers: toNullableNumber(v.returningViewers ?? v.returning_viewers),
          casualViewers: toNullableNumber(v.casualViewers ?? v.casual_viewers),
          regularViewers: toNullableNumber(v.regularViewers ?? v.regular_viewers),
          subscribers: toNullableNumber(v.subscribers),
          estimatedRevenue: toNullableNumber(v.estimatedRevenue ?? v.estimated_revenue),
          impressions: toNullableNumber(v.impressions),
          impressionsClickThroughRate: toNullableNumber(v.impressionsClickThroughRate ?? v.impressions_click_through_rate),
          likes: n(v.likes),

          cardImpressions: n(v.cardImpressions),

          adImpressions: n(v.adImpressions),

          annotationImpressions: n(v.annotationImpressions),

        }))

        .sort((a, b) => b.views - a.views), // 🔴 Sort table by views

    [videos]

  );

  const sortedRows = useMemo(() => {
    const getComparableValue = (row, key) => {
      if (key === "title") return String(row.title || "").toLowerCase();
      if (key === "published") {
        return row.published ? new Date(row.published).getTime() : Number.NEGATIVE_INFINITY;
      }
      const value = row[key];
      if (value === null || value === undefined || value === "") {
        return Number.NEGATIVE_INFINITY;
      }
      if (typeof value === "number") return value;
      return String(value).toLowerCase();
    };

    const directionFactor = sortDirection === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const aValue = getComparableValue(a, sortKey);
      const bValue = getComparableValue(b, sortKey);

      if (typeof aValue === "string" || typeof bValue === "string") {
        return String(aValue).localeCompare(String(bValue)) * directionFactor;
      }

      if (aValue === bValue) return 0;
      return (aValue - bValue) * directionFactor;
    });
  }, [rows, sortDirection, sortKey]);

  const totals = useMemo(() => {
    const acc = TABLE_METRIC_OPTIONS.reduce((out, item) => {
      if (NON_SUM_METRICS.has(item.value)) {
        out[item.value] = null;
        return out;
      }
      let sum = 0;
      let hasValue = false;
      rows.forEach((row) => {
        const value = toNullableNumber(row[item.value]);
        if (value === null) return;
        hasValue = true;
        sum += value;
      });
      out[item.value] = hasValue ? sum : null;
      return out;
    }, {});

    // Impressions/CTR are channel-level only (TOTAL row)
    if (channelMetrics?.supported) {
      if (typeof channelMetrics.impressions === "number") {
        acc.impressions = channelMetrics.impressions;
      }
      if (typeof channelMetrics.ctr === "number") {
        acc.impressionsClickThroughRate = channelMetrics.ctr;
      }
    }

    return acc;
  }, [rows, channelMetrics]);


  const pagedRows = useMemo(() => {

    const start = page * rowsPerPage;

    const end = start + rowsPerPage;

    return sortedRows.slice(start, end);

  }, [sortedRows, page, rowsPerPage]);

  const handleSort = useCallback((key) => {
    setPage(0);
    if (sortKey === key) {
      setSortDirection((currentDirection) =>
        currentDirection === "desc" ? "asc" : "desc"
      );
      return;
    }
    setSortKey(key);
    setSortDirection("desc");
  }, [sortKey]);



  /* ================================

     CHART DATA

  ================================= */

  const lineData = useMemo(() => {

    if (chartType !== "line") return [];



    // 🔴 1. Get Top 5 IDs based on the current metric to avoid rendering 100s of lines

    const topIds = sortedRows

      .slice(0, 5)

      .map(r => r.id);



    const topIdsSet = new Set(topIds);



    // 2. Identify all unique dates in the timeseries

    const allDatesSet = new Set();

    timeseries.forEach(t => {

      const d = dayjs(t.bucket).startOf('day').toDate().getTime();

      allDatesSet.add(d);

    });

    const allDatesSorted = Array.from(allDatesSet).sort((a, b) => a - b).map(t => new Date(t));



    const map = new Map();

    timeseries.forEach((t) => {

      const id = t.videoId;

      if (!id || !topIdsSet.has(id)) return; // 🔴 Only process top videos



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



    const titleMap = new Map(rows.map(r => [r.id, r.title]));



    return Array.from(map.entries()).map(([id, dataMap]) => {

      const videoTitle = titleMap.get(id) || id;

      const data = allDatesSorted.map(d => {

        const entry = dataMap.get(d.getTime());

        return {

          x: d,

          y: entry ? entry.y : 0,

          videoId: id,

          title: videoTitle

        };

      });

      return { id, data };

    });

  }, [timeseries, chartType, metric, rows, sortedRows]);



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

        estimatedMinutesWatched: "watchHours",

      }[metric] ?? "views";



    // 🔴 Limit to Top 5 for Bar chart too

    const topRows = sortedRows

      .slice(0, 5);



    return {

      keys: topRows.map((r) => r.id),

      data: topRows.map((r) => ({

        video: r.title,

        [r.id]: r[metricKey],

      })),

    };

  }, [sortedRows, chartType, metric]);



  const seriesColors = useMemo(() => {

    const palette = [

      "#e41a1c",

      "#377eb8",

      "#4daf4a",

      "#984ea3",

      "#facc15",

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



  const handleSliceMove = useCallback((datum) => {

    if (!datum || !Array.isArray(datum.points)) return;

    setHoverSlice((prev) => (prev?.id === datum.id ? prev : datum));

  }, []);



  const handleSliceLeave = useCallback(() => {

    setHoverSlice(null);

  }, []);



  /* ================================

     UI

  ================================= */

  return (

    <Stack spacing={2}>

      {/* FILTERS */}

      <Stack direction="row" spacing={2} flexWrap="wrap">

        {/* Channel */}
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Channel</InputLabel>
          <Select
            value={channelList.some((c) => c.id === channelId) ? channelId : ""}
            label="Channel"
            onChange={(e) => setChannelId(e.target.value)}
            renderValue={(v) => {
              const sel = channelList.find((c) => c.id === v);
              const label = sel?.title || v;
              return (
                <Stack direction="row" spacing={1} alignItems="center">
                  <Avatar
                    src={sel?.avatar || ""}
                    alt={label}
                    sx={{ width: 22, height: 22 }}
                  />
                  <Typography variant="body2" noWrap>
                    {label}
                  </Typography>
                </Stack>
              );
            }}
          >
            {channelList.map((c) => (
              <MenuItem key={c.id} value={c.id}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Avatar
                    src={c.avatar || ""}
                    alt={c.title || c.id}
                    sx={{ width: 24, height: 24 }}
                  />
                  <Typography variant="body2" noWrap>
                    {c.title}
                  </Typography>
                </Stack>
              </MenuItem>
            ))}
          </Select>
        </FormControl>

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


        <FormControl size="small" sx={{ minWidth: 320 }}>

          <InputLabel>Table Metrics</InputLabel>

          <Select

            multiple

            value={selectedTableMetrics}

            label="Table Metrics"

            onChange={(e) =>

              setSelectedTableMetrics(

                typeof e.target.value === "string"

                  ? e.target.value.split(",")

                  : e.target.value

              )

            }

            renderValue={(selected) => `Metrics (${selected.length})`}

          >

            {TABLE_METRIC_OPTIONS.map((m) => (

              <MenuItem key={m.value} value={m.value}>

                <Checkbox size="small" checked={selectedTableMetrics.includes(m.value)} />

                <ListItemText primary={m.label} />

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

          position: "relative",

        }}

      >

        {loadingTimeseries && (

          <Box

            sx={{

              position: "absolute",

              inset: 0,

              display: "flex",

              alignItems: "center",

              justifyContent: "center",

              bgcolor: "rgba(0,0,0,0.05)",

              zIndex: 10,

              borderRadius: 2,

              backdropFilter: "blur(2px)",

            }}

          >

            Loading...

          </Box>

        )}

        {chartType === "line" && lineData.length > 0 && (

          <LineChart

            data={lineData}

            margin={LINE_MARGIN}

            lineDateExtent={lineDateExtent}

            xTickValues={xTickValues}

            metric={metric}

            themeMode={theme.palette.mode}

            seriesColors={seriesColors}

            onSliceMove={handleSliceMove}

            onSliceLeave={handleSliceLeave}

          />

        )}



        {chartType === "line" && hoverSlice && (
          <Box
            sx={{
              position: "absolute",
              top: 10,
              left: 0,
              transform: `translate3d(${chartPaddingPx + LINE_MARGIN.left + hoverSlice.x}px, 0, 0) translateX(-50%)`,
              transition: "transform 140ms cubic-bezier(0.2, 0.9, 0.2, 1)",
              willChange: "transform",
              pointerEvents: "none",
              zIndex: 20,
              width: "min(360px, 92%)",
            }}
          >
            <Box

              sx={{

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

              }}

            >

              <Typography

                variant="subtitle2"

                sx={{

                  fontWeight: 800,

                  mb: 1,

                  color: theme.palette.mode === "dark" ? "#e5e7eb" : "#111827",

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

                  .map((p) => (

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

                            backgroundColor: seriesColors[p.serieId] || p.color,

                            flexShrink: 0,

                          }}

                        />

                        <Typography

                          variant="body2"

                          title={p.data.title || p.serieId}

                          noWrap

                          sx={{

                            fontSize: 12,

                            fontWeight: 600,

                            lineHeight: 1.25,

                            display: "block",

                            width: "100%",

                            minWidth: 0,

                            maxWidth: "100%",

                            color: theme.palette.mode === "dark" ? "#e5e7eb" : "#111827",

                          }}

                        >

                          {p.data.title || p.serieId}

                        </Typography>

                      </Box>



                      <Typography

                        variant="body2"

                        sx={{

                          fontSize: 12,

                          fontWeight: 800,

                          color: theme.palette.mode === "dark" ? "#e5e7eb" : "#111827",

                          flexShrink: 0,

                        }}

                      >

                        {formatMetricValue(metric, p.data.y)}

                      </Typography>

                    </Box>

                  ))}

              </Box>

            </Box>

          </Box>

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

              format: (v) => formatMetricValue(metric, v),

            }}

            labelSkipWidth={12}

            labelSkipHeight={12}

            labelTextColor={{

              from: "color",

              modifiers: [["darker", 2.5]],

            }}

            tooltip={({ id, indexValue }) => {

              // Get Top 5 data from rows (since barPrep is limited to 5)

              const top5 = barPrep.data.slice(0, 5);



              return (

                <Box

                  sx={{

                    px: 2,

                    py: 1.5,

                    borderRadius: 2,

                    minWidth: 280,

                    bgcolor:

                      theme.palette.mode === "dark"

                        ? "rgba(15,23,42,0.92)"

                        : "rgba(255,255,255,0.95)",

                    backdropFilter: "blur(8px)",

                    border: `1px solid ${theme.palette.divider}`,

                    boxShadow: "0 15px 35px rgba(0,0,0,0.25)",

                    transform: "translate(-50%, -100%)",

                    mb: 1.5,

                    pointerEvents: "none",

                    position: "relative",

                    zIndex: 100,

                  }}

                >

                  {/* Arrow pointing down */}

                  <Box

                    sx={{

                      position: "absolute",

                      bottom: -8,

                      left: "50%",

                      width: 0,

                      height: 0,

                      borderLeft: "8px solid transparent",

                      borderRight: "8px solid transparent",

                      borderTop: `8px solid ${theme.palette.divider}`,

                      transform: "translateX(-50%)",

                    }}

                  />

                  <Box sx={{ mb: 0.75, color: "text.secondary", fontWeight: 700 }}>TOP 5 {metric.toUpperCase()}</Box>

                  {top5.map((entry) => {

                    const videoId = Object.keys(entry).find(k => k !== "video");

                    const val = entry[videoId];

                    const isCurrent = videoId === id;



                    return (

                      <Box

                        key={videoId}

                        sx={{

                          display: "flex",

                          alignItems: "center",

                          justifyContent: "space-between",

                          gap: 1,

                          bgcolor: isCurrent ? (theme.palette.mode === "dark" ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.05)") : "transparent",

                          px: 0.5,

                          borderRadius: 0.5,

                          minWidth: 0,

                        }}

                      >

                        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, minWidth: 0, flex: 1 }}>

                          <span

                            style={{

                              width: 8,

                              height: 8,

                              borderRadius: 2,

                              background: seriesColors[videoId] || "#ccc",

                              display: "inline-block",

                              flexShrink: 0,

                            }}

                          />

                          <span style={{

                            fontSize: 12,

                            fontWeight: isCurrent ? 700 : 400,

                            overflow: "hidden",

                            textOverflow: "ellipsis",

                            whiteSpace: "nowrap",

                            flex: 1,

                          }}>

                            {entry.video}

                          </span>

                        </Box>

                        <span style={{ fontWeight: isCurrent ? 700 : 400, flexShrink: 0 }}>{formatMetricValue(metric, val)}</span>

                      </Box>

                    );

                  })}

                </Box>

              );

            }}

            theme={{

              axis: {

                ticks: {

                  text: {

                    fill: theme.palette.mode === "dark" ? "#e5e7eb" : "#374151",

                    fontSize: 11,

                    fontWeight: 600,

                  },

                },

              },

              tooltip: {

                container: {

                  background: 'transparent',

                  padding: 0,

                  boxShadow: 'none',

                  border: 'none',

                  borderRadius: 0,

                }

              }

            }}

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



        {/* 🔴 Performance Tip */}

        <Box sx={{ mt: 1, textAlign: "center", fontSize: "0.75rem", color: "text.secondary", opacity: 0.8 }}>

          Showing top 5 videos by {metric} for better performance.

        </Box>

      </Box>



      {/* TABLE */}

      {(loadingVideos || loadingChannelMetrics) && (
        <Typography
          variant="caption"
          sx={{ color: "text.secondary", ml: 0.5 }}
        >
          Updating content data...
        </Typography>
      )}

      <TableContainer component={Paper} elevation={0} sx={tablePaperSx}>

        <Table size="small">

          <TableHead sx={tableHeadSx}>

            <TableRow>

              <TableCell>Video</TableCell>

              <TableCell sortDirection={sortKey === "published" ? sortDirection : false}>
                <TableSortLabel
                  active={sortKey === "published"}
                  direction={sortKey === "published" ? sortDirection : "desc"}
                  onClick={() => handleSort("published")}
                >
                  Publish Date
                </TableSortLabel>
              </TableCell>

              {selectedTableMetrics.map((metricKey) => {

                const label =

                  TABLE_METRIC_OPTIONS.find((m) => m.value === metricKey)?.label || metricKey;

                return (

                  <TableCell
                    key={metricKey}
                    align="right"
                    sortDirection={sortKey === metricKey ? sortDirection : false}
                  >

                    <TableSortLabel
                      active={sortKey === metricKey}
                      direction={sortKey === metricKey ? sortDirection : "desc"}
                      onClick={() => handleSort(metricKey)}
                    >
                      {label}
                    </TableSortLabel>

                  </TableCell>

                );

              })}

            </TableRow>

          </TableHead>



          <TableBody>

            {/* TOTAL row at top */}
            <TableRow>
              <TableCell sx={{ fontWeight: 700 }}>TOTAL</TableCell>
              <TableCell />
              {selectedTableMetrics.map((metricKey) => (
                <TableCell key={metricKey} align="right">
                  {totals[metricKey] == null
                    ? "-"
                    : formatTableMetricValue(metricKey, totals[metricKey])}
                </TableCell>
              ))}
            </TableRow>

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

                    borderLeft: seriesColors[r.id]

                      ? `4px solid ${seriesColors[r.id]}`

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

                {selectedTableMetrics.map((metricKey) => (

                  <TableCell key={metricKey} align="right">

                    {formatTableMetricValue(metricKey, r[metricKey])}

                  </TableCell>

                ))}

              </TableRow>

            ))}



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

    </Stack >

  );

};



export default ContentAnalytics;

