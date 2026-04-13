import { Fragment, useState, useEffect, useCallback, useMemo, useRef, memo, startTransition, useDeferredValue } from "react";
import { motion } from "framer-motion";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowRightIcon from "@mui/icons-material/KeyboardArrowRight";

import { useTheme } from "@mui/material/styles";

import {

  Avatar,
  Box,
  Stack,
  Typography,
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
import { sortByStoredTokenOrder } from "../utils/tokenOrder";
import {
  getStoredSharedChannelId,
  listenSharedChannelId,
  resolvePreferredSharedChannelId,
  setStoredSharedChannelId,
} from "../utils/sharedChannel";

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
import { getChannelRevenueMap } from "./Module";

import api from "../services/api";
import ChannelSwitcher, { CHANNEL_SWITCHER_SX } from "./ChannelSwitcher";


/* Extra periods – chỉ khai báo value + label (không chứa ngày) */

const EXTRA_PERIODS = [

  { value: "month_current", label: "This month" },

  { value: "month_prev", label: "Last month" },

  { value: "year_current", label: "This year" },

  { value: "year_prev", label: "Last year" },

  { value: "last14", label: "Last 14 days" },

  { value: "last180", label: "Last 180 days" },

];

const CONTENT_PERIOD_OPTION_ORDER = [
  "last7",
  "last14",
  "last28",
  "last90",
  "last180",
  "last365",
  "month_current",
  "month_prev",
  "year_current",
  "year_prev",
  "lifetime",
  "custom",
];

const CONTENT_PERIOD_OPTIONS = CONTENT_PERIOD_OPTION_ORDER
  .map((value) =>
    [...PERIOD_OPTIONS, ...EXTRA_PERIODS].find((option) => option.value === value)
  )
  .filter(Boolean);

const CONTENT_ALL_CHANNELS_VALUE = "__all__";
const CONTENT_LOCAL_CHANNEL_STORAGE_KEY = "content.selectedChannelId";
const CONTENT_FILTERS_STORAGE_KEY = "content.filters";
const CONTENT_ROWS_PER_PAGE_OPTIONS = [20, 50, 100, 200];
const CHANNEL_SUMMARY_WEIGHT_BY_METRIC = {
  averageViewDuration: "views",
  averagePercentageViewed: "views",
  stayedToWatch: "views",
  averageViewsPerViewer: "uniqueViewers",
  impressionsClickThroughRate: "impressions",
};

const getChartMetricRowKey = (selectedMetric) =>
  (
    {
      views: "views",
      estimatedMinutesWatched: "watchTimeHours",
      averageViewDuration: "averageViewDuration",
      averageViewPercentage: "averagePercentageViewed",
      engagedViews: "engagedViews",
    }[selectedMetric] || "views"
  );

const getStoredContentChannelId = () => {
  try {
    if (typeof window !== "undefined") {
      const localValue = window.localStorage.getItem(CONTENT_LOCAL_CHANNEL_STORAGE_KEY);
      if (localValue) return localValue;
    }
  } catch {
    return "";
  }
  return getStoredSharedChannelId(CONTENT_LOCAL_CHANNEL_STORAGE_KEY);
};

const loadStoredContentFilters = () => {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(CONTENT_FILTERS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

const normalizeContentChartType = (value) => (value === "bar" ? "bar" : "line");

const normalizeContentMetric = (value) =>
  METRIC_OPTIONS.some((option) => option.value === value) ? value : "views";

const normalizeContentPeriod = (value) =>
  CONTENT_PERIOD_OPTIONS.some((option) => option.value === value) ? value : "last28";

const normalizeSelectedTableMetrics = (value) => {
  if (!Array.isArray(value)) return DEFAULT_TABLE_METRICS;
  const allowed = new Set(TABLE_METRIC_OPTIONS.map((item) => item.value));
  const filtered = value.filter((metricKey) => allowed.has(metricKey));
  return Array.from(new Set(filtered));
};

const normalizeRowsPerPage = (value) => {
  const parsed = Number(value);
  return CONTENT_ROWS_PER_PAGE_OPTIONS.includes(parsed) ? parsed : 20;
};

const normalizeSortKey = (value) => {
  const allowed = new Set(["videoCount", "published", ...TABLE_METRIC_OPTIONS.map((item) => item.value)]);
  return allowed.has(value) ? value : "views";
};



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

  { value: "impressions", label: "Impressions", type: "number" },

  { value: "impressionsClickThroughRate", label: "Impressions click-through rate", type: "percent" },

];



const DEFAULT_TABLE_METRICS = [

  "views",

  "watchTimeHours",

  "subscribers",

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

      animate={true}

      motionConfig="gentle"

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
  const storedFilters = useMemo(() => loadStoredContentFilters(), []);

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
  const [channelRevenueMap, setChannelRevenueMap] = useState({});

  const [channelMetrics, setChannelMetrics] = useState(null);

  const chartRef = useRef(null);
  const hoverTooltipRef = useRef(null);

  const [hoverSlice, setHoverSlice] = useState(null);
  const [hoverTooltipLayout, setHoverTooltipLayout] = useState({
    tooltipWidth: 0,
    chartWidth: 0,
  });



  const [chartType, setChartType] = useState(() =>
    normalizeContentChartType(storedFilters?.chartType)
  );

  const [metric, setMetric] = useState(() =>
    normalizeContentMetric(storedFilters?.metric)
  );

  const [period, setPeriod] = useState(() =>
    normalizeContentPeriod(storedFilters?.period)
  );

  const [selectedTableMetrics, setSelectedTableMetrics] = useState(() =>
    normalizeSelectedTableMetrics(storedFilters?.selectedTableMetrics)
  );

  const [page, setPage] = useState(0);

  const [rowsPerPage, setRowsPerPage] = useState(() =>
    normalizeRowsPerPage(storedFilters?.rowsPerPage)
  );
  const contentRequestSeqRef = useRef(0);
  const [expandedChannelIds, setExpandedChannelIds] = useState({});
  const [sortKey, setSortKey] = useState(() =>
    normalizeSortKey(storedFilters?.sortKey)
  );
  const [sortDirection] = useState("desc");



  const [channelId, setChannelId] = useState(() => {
    try {

      return getStoredContentChannelId();

    } catch {

      return "";

    }

  });

  const [startDate, setStartDate] = useState(() => storedFilters?.startDate || "");

  const [endDate, setEndDate] = useState(() => storedFilters?.endDate || "");

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


        const finalChannels = sortByStoredTokenOrder(items, (item) => item.id);

        setChannelList(finalChannels);

        setChannelId((current) => {
          const preferredChannel = getStoredContentChannelId() || current;
          if (preferredChannel === CONTENT_ALL_CHANNELS_VALUE) {
            return finalChannels.length ? CONTENT_ALL_CHANNELS_VALUE : "";
          }
          return resolvePreferredSharedChannelId(
            preferredChannel,
            finalChannels,
            (item) => item.id
          );
        });

      } catch (err) {

        console.error("Load channels failed:", err);

      }

    })();
  }, []);

  useEffect(() => {

    if (channelId === CONTENT_ALL_CHANNELS_VALUE) {
      try {
        window.localStorage.setItem(CONTENT_LOCAL_CHANNEL_STORAGE_KEY, channelId);
      } catch {
        // ignore storage errors
      }
      return;
    }

    setStoredSharedChannelId(channelId, CONTENT_LOCAL_CHANNEL_STORAGE_KEY);

  }, [channelId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(
        CONTENT_FILTERS_STORAGE_KEY,
        JSON.stringify({
          chartType,
          metric,
          period,
          selectedTableMetrics,
          rowsPerPage,
          sortKey,
          startDate,
          endDate,
        })
      );
    } catch {
      // ignore storage errors
    }
  }, [chartType, metric, period, selectedTableMetrics, rowsPerPage, sortKey, startDate, endDate]);

  useEffect(() => {
    return listenSharedChannelId((nextChannelId) => {
      setChannelId((current) => {
        if (
          current === CONTENT_ALL_CHANNELS_VALUE ||
          !nextChannelId ||
          nextChannelId === current ||
          !channelList.some((item) => item.id === nextChannelId)
        ) {
          return current;
        }
        return nextChannelId;
      });
    });
  }, [channelList]);

  const showAllMode = channelId === CONTENT_ALL_CHANNELS_VALUE;
  const channelMetaById = useMemo(
    () => new Map(channelList.map((item) => [item.id, item])),
    [channelList]
  );



  /* ================================

     API CALLS

  ================================= */

  const fetchVideos = useCallback(

    async (start, end, requestSeq) => {

      if (!channelId) return;

      try {

        const resp = await api.post("/api/content/list", {

          start,

          end,

          channelId,

        });



        const raw = resp.data;

        if (requestSeq !== contentRequestSeqRef.current) return;
        startTransition(() => {
          setVideos(raw.items ?? []);
          setChannelMetrics(raw.channelMetrics ?? null);
        });

      } catch (err) {

        console.error("Fetch videos failed:", err);

        if (requestSeq !== contentRequestSeqRef.current) return;
        startTransition(() => {
          setVideos([]);
          setChannelMetrics(null);
        });

      }

    },

    [channelId]

  );



  const fetchTimeseries = useCallback(

    async (start, end, requestSeq) => {

      if (!channelId) return;

      try {

        const resp = await api.post("/api/content/timeseries", {

          start,

          end,

          channelId,

        });



        const raw = resp.data;

        if (requestSeq !== contentRequestSeqRef.current) return;
        startTransition(() => {
          setTimeseries(raw.items ?? []);
        });

      } catch (err) {

        console.error("Fetch timeseries failed:", err);

        if (requestSeq !== contentRequestSeqRef.current) return;
        startTransition(() => {
          setTimeseries([]);
        });

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

    setVideos([]);

    setTimeseries([]);

    setHoverSlice(null);

    setChannelMetrics(null);
    const requestSeq = contentRequestSeqRef.current + 1;
    contentRequestSeqRef.current = requestSeq;
    fetchVideos(start, end, requestSeq);
    fetchTimeseries(start, end, requestSeq);

    return undefined;

  }, [resolvePeriod, fetchVideos, fetchTimeseries, channelId]);

  useEffect(() => {
    let active = true;
    getChannelRevenueMap().then((map) => {
      if (active) setChannelRevenueMap(map || {});
    });
    return () => {
      active = false;
    };
  }, [period, resolvePeriod]);



  /* ================================

     TABLE ROWS

  ================================= */

  const rows = useMemo(

    () =>

      videos

        .map((v) => ({

          id: v.videoId,

          title: v.title,
          displayTitle:
            showAllMode && v.channelTitle
              ? `${v.title} (${v.channelTitle})`
              : v.title,
          channelId: v.channelId || "",
          channelTitle: v.channelTitle || "",
          channelAvatar: v.channelAvatar || "",

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
          impressions: toNullableNumber(v.impressions),
          impressionsClickThroughRate: toNullableNumber(v.impressionsClickThroughRate ?? v.impressions_click_through_rate),
          likes: n(v.likes),

          cardImpressions: n(v.cardImpressions),
          adImpressions: n(v.adImpressions),
        })),

    [showAllMode, videos]

  );
  const deferredRows = useDeferredValue(rows);

  const channelSummaryRows = useMemo(() => {
    const groups = new Map();

    deferredRows.forEach((row) => {
      const channelKey = String(row.channelId || "").trim();
      if (!channelKey) return;

      if (!groups.has(channelKey)) {
        const channelMeta = channelMetaById.get(channelKey);
        groups.set(channelKey, {
          id: channelKey,
          title: channelMeta?.title || row.channelTitle || channelKey,
          displayTitle: channelMeta?.title || row.channelTitle || channelKey,
          channelTitle: channelMeta?.title || row.channelTitle || channelKey,
          channelAvatar: channelMeta?.avatar || row.channelAvatar || "",
          published: row.published || null,
          videoCount: 0,
          _weighted: {},
          _weights: {},
          _sumFlags: {},
        });
      }

      const entry = groups.get(channelKey);
      entry.videoCount += 1;

      if (row.published) {
        const currentPublished = entry.published ? new Date(entry.published).getTime() : 0;
        const nextPublished = new Date(row.published).getTime();
        if (!entry.published || nextPublished > currentPublished) {
          entry.published = row.published;
        }
      }

      TABLE_METRIC_OPTIONS.forEach(({ value }) => {
        const numericValue = toNullableNumber(row[value]);
        if (numericValue === null) return;

        if (NON_SUM_METRICS.has(value)) {
          const weightKey = CHANNEL_SUMMARY_WEIGHT_BY_METRIC[value];
          const weightValue = toNullableNumber(weightKey ? row[weightKey] : null);
          const effectiveWeight = weightValue !== null && weightValue > 0 ? weightValue : 1;
          entry._weighted[value] = (entry._weighted[value] || 0) + numericValue * effectiveWeight;
          entry._weights[value] = (entry._weights[value] || 0) + effectiveWeight;
          return;
        }

        entry[value] = (entry[value] || 0) + numericValue;
        entry._sumFlags[value] = true;
      });
    });

    return Array.from(groups.values()).map((entry) => {
      const finalized = { ...entry };

      TABLE_METRIC_OPTIONS.forEach(({ value }) => {
        if (NON_SUM_METRICS.has(value)) {
          finalized[value] =
            entry._weights[value] > 0
              ? entry._weighted[value] / entry._weights[value]
              : null;
          return;
        }

        if (!entry._sumFlags[value]) {
          finalized[value] = null;
        }
      });

      delete finalized._weighted;
      delete finalized._weights;
      delete finalized._sumFlags;
      return finalized;
    });
  }, [channelMetaById, deferredRows]);

  const tableRows = showAllMode ? channelSummaryRows : deferredRows;

  const channelExpandedVideos = useMemo(() => {
    const compareVideoRows = (left, right) => {
      const childSortKey = sortKey === "videoCount" ? "views" : sortKey;

      const getComparableValue = (row, key) => {
        if (key === "title") return String(row.displayTitle || row.title || "").toLowerCase();
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

      const leftValue = getComparableValue(left, childSortKey);
      const rightValue = getComparableValue(right, childSortKey);
      const directionFactor = sortDirection === "asc" ? 1 : -1;

      if (typeof leftValue === "string" || typeof rightValue === "string") {
        return String(leftValue).localeCompare(String(rightValue)) * directionFactor;
      }
      if (leftValue === rightValue) return 0;
      return (leftValue - rightValue) * directionFactor;
    };

    const grouped = deferredRows.reduce((acc, row) => {
      const channelKey = String(row.channelId || "").trim();
      if (!channelKey) return acc;
      if (!acc[channelKey]) acc[channelKey] = [];
      acc[channelKey].push(row);
      return acc;
    }, {});

    return Object.fromEntries(
      Object.entries(grouped).map(([channelKey, channelRows]) => [
        channelKey,
        [...channelRows].sort(compareVideoRows).slice(0, 5),
      ])
    );
  }, [deferredRows, sortDirection, sortKey]);

  const sortedRows = useMemo(() => {
    const getComparableValue = (row, key) => {
      if (key === "title") return String(row.displayTitle || row.title || "").toLowerCase();
      if (key === "published") {
        return row.published ? new Date(row.published).getTime() : Number.NEGATIVE_INFINITY;
      }
      if (key === "videoCount") {
        return Number(row.videoCount || 0);
      }
      const value = row[key];
      if (value === null || value === undefined || value === "") {
        return Number.NEGATIVE_INFINITY;
      }
      if (typeof value === "number") return value;
      return String(value).toLowerCase();
    };

    const directionFactor = sortDirection === "asc" ? 1 : -1;
    return [...tableRows].sort((a, b) => {
      const aValue = getComparableValue(a, sortKey);
      const bValue = getComparableValue(b, sortKey);

      if (typeof aValue === "string" || typeof bValue === "string") {
        return String(aValue).localeCompare(String(bValue)) * directionFactor;
      }

      if (aValue === bValue) return 0;
      return (aValue - bValue) * directionFactor;
    });
  }, [sortDirection, sortKey, tableRows]);
  const deferredSortedRows = useDeferredValue(sortedRows);

  const totals = useMemo(() => {
    const acc = TABLE_METRIC_OPTIONS.reduce((out, item) => {
      if (NON_SUM_METRICS.has(item.value)) {
        out[item.value] = null;
        return out;
      }
      let sum = 0;
      let hasValue = false;
      deferredRows.forEach((row) => {
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
  }, [deferredRows, channelMetrics]);

  const showAllSummaryCards = useMemo(
    () => [
      {
        label: "Channels",
        value: formatNumber(channelSummaryRows.length),
      },
      {
        label: "Videos",
        value: formatNumber(deferredRows.length),
      },
      {
        label: "Views",
        value:
          totals.views == null ? "-" : formatTableMetricValue("views", totals.views),
      },
      {
        label: "Watch time (hours)",
        value:
          totals.watchTimeHours == null
            ? "-"
            : formatTableMetricValue("watchTimeHours", totals.watchTimeHours),
      },
      {
        label: "Subscribers",
        value:
          totals.subscribers == null
            ? "-"
            : formatTableMetricValue("subscribers", totals.subscribers),
      },
      {
        label: "Impressions",
        value:
          totals.impressions == null
            ? "-"
            : formatTableMetricValue("impressions", totals.impressions),
      },
    ],
    [channelSummaryRows.length, deferredRows.length, totals]
  );



  const pagedRows = useMemo(() => {

    const start = page * rowsPerPage;

    const end = start + rowsPerPage;

    return deferredSortedRows.slice(start, end);

  }, [deferredSortedRows, page, rowsPerPage]);

  const deferredTimeseries = useDeferredValue(timeseries);

  const handleSort = useCallback((key) => {
    setPage(0);
    setSortKey(key);
  }, []);

  const handleToggleChannelExpand = useCallback((channelIdValue) => {
    if (!channelIdValue) return;
    setExpandedChannelIds((current) => ({
      ...current,
      [channelIdValue]: !current[channelIdValue],
    }));
  }, []);

  useEffect(() => {
    if (!showAllMode) {
      setExpandedChannelIds({});
    }
  }, [showAllMode]);



  /* ================================

     CHART DATA

  ================================= */

  const lineData = useMemo(() => {

    if (chartType !== "line") return [];

    const lineMetricKey =
      metric === "estimatedMinutesWatched" ? "watch_hours" : "views";

    const allDatesSet = new Set();

    deferredTimeseries.forEach(t => {

      const d = dayjs(t.bucket).startOf('day').toDate().getTime();

      allDatesSet.add(d);

    });

    const allDatesSorted = Array.from(allDatesSet).sort((a, b) => a - b).map(t => new Date(t));

    if (showAllMode) {
      const visibleVideoIds = new Set(deferredRows.map((row) => row.id));
      const dailyTotals = new Map();

      deferredTimeseries.forEach((t) => {
        const videoId = String(t.videoId || "").trim();
        if (videoId && !visibleVideoIds.has(videoId)) return;
        const d = dayjs(t.bucket).startOf("day").toDate().getTime();
        dailyTotals.set(d, (dailyTotals.get(d) || 0) + n(t[lineMetricKey]));
      });

      if (!allDatesSorted.length) return [];

      return [
        {
          id: CONTENT_ALL_CHANNELS_VALUE,
          data: allDatesSorted.map((d) => ({
            x: d,
            y: dailyTotals.get(d.getTime()) || 0,
            title: "All channels",
          })),
        },
      ];
    }



    // 🔴 1. Get Top 5 IDs based on the current metric to avoid rendering 100s of lines

    const timeseriesVideoIds = new Set(
      deferredTimeseries
        .map((t) => String(t.videoId || "").trim())
        .filter(Boolean)
    );

    const topIds = deferredSortedRows

      .map((r) => String(r.id || "").trim())

      .filter((id, index, source) => source.indexOf(id) === index && timeseriesVideoIds.has(id))

      .slice(0, 5);



    const topIdsSet = new Set(topIds);

    const map = new Map();

    deferredTimeseries.forEach((t) => {

      const id = t.videoId;

      if (!id || !topIdsSet.has(id)) return; // 🔴 Only process top videos



      const title = t.displayTitle || t.title || id;

      if (!map.has(id)) {

        map.set(id, new Map());

      }
      const d = dayjs(t.bucket).startOf('day').toDate().getTime();

      map.get(id).set(d, { y: n(t[lineMetricKey]), title });

    });



    const titleMap = new Map(deferredRows.map(r => [r.id, r.displayTitle || r.title]));



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

  }, [chartType, metric, deferredRows, showAllMode, deferredSortedRows, deferredTimeseries]);



  const lineDateExtent = useMemo(() => {

    if (!lineData.length || !lineData[0].data.length) return { min: "auto", max: "auto" };

    const first = lineData[0].data[0].x;

    const last = lineData[0].data[lineData[0].data.length - 1].x;

    return { min: first, max: last };

  }, [lineData]);



  // Chọn tick ngày thưa để không đè chữ

  const xTickValues = useMemo(() => {

    if (!deferredTimeseries.length) return [];

    const allDates = deferredTimeseries.map((t) => dayjs(t.bucket).startOf("day").toDate());

    return pickTicks(allDates, 7); // tối đa 7 tick

  }, [deferredTimeseries]);



  const barPrep = useMemo(() => {

    if (chartType !== "bar") return { keys: [], data: [] };



    const metricKey = showAllMode
      ? getChartMetricRowKey(metric)
      : ({

        views: "views",

        estimatedMinutesWatched: "watchHours",

      }[metric] ?? "views");



    // 🔴 Limit to Top 5 for Bar chart too

    const sourceRows = showAllMode
      ? [...channelSummaryRows].sort((a, b) => n(b[metricKey]) - n(a[metricKey]))
      : deferredSortedRows;

    const topRows = sourceRows

      .slice(0, 5);



    return {

      keys: topRows.map((r) => r.id),

      data: topRows.map((r) => ({

        label: r.displayTitle || r.title,

        [r.id]: n(r[metricKey]),

      })),

    };

  }, [channelSummaryRows, chartType, metric, showAllMode, deferredSortedRows]);



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
    const sourceIds =
      lineData.length > 0 ? lineData.map((serie) => serie.id) : barPrep.keys || [];

    sourceIds.forEach((id, index) => {

      map[id] = palette[index % palette.length];

    });

    return map;

  }, [barPrep.keys, lineData]);



  const hasBarData =

    barPrep.data && barPrep.data.length > 0 && barPrep.keys && barPrep.keys.length > 0;

  const formatBarTickLabel = useCallback((value) => {
    const label = String(value || "").trim();
    if (label.length <= 18) return label;
    return `${label.slice(0, 18).trimEnd()}...`;
  }, []);



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

  useEffect(() => {

    if (chartType !== "line" || !hoverSlice) {

      setHoverTooltipLayout((current) =>

        current.tooltipWidth === 0 && current.chartWidth === 0

          ? current

          : { tooltipWidth: 0, chartWidth: 0 }

      );

      return undefined;

    }



    const measure = () => {

      const tooltipWidth = hoverTooltipRef.current?.offsetWidth || 0;

      const chartWidth = chartRef.current?.clientWidth || 0;

      setHoverTooltipLayout((current) => {

        if (

          current.tooltipWidth === tooltipWidth &&

          current.chartWidth === chartWidth

        ) {

          return current;

        }

        return { tooltipWidth, chartWidth };

      });

    };



    measure();

    const frameId = window.requestAnimationFrame(measure);

    let resizeObserver;



    if (typeof ResizeObserver !== "undefined") {

      resizeObserver = new ResizeObserver(measure);

      if (chartRef.current) resizeObserver.observe(chartRef.current);

      if (hoverTooltipRef.current) resizeObserver.observe(hoverTooltipRef.current);

    } else {

      window.addEventListener("resize", measure);

    }



    return () => {

      window.cancelAnimationFrame(frameId);

      resizeObserver?.disconnect();

      window.removeEventListener("resize", measure);

    };

  }, [chartType, hoverSlice]);



  const hoverTooltipPosition = useMemo(() => {

    if (chartType !== "line" || !hoverSlice) return null;



    const anchorX = chartPaddingPx + LINE_MARGIN.left + hoverSlice.x;

    const chartWidth =

      hoverTooltipLayout.chartWidth || chartRef.current?.clientWidth || 0;

    const tooltipWidth =

      hoverTooltipLayout.tooltipWidth ||

      Math.min(360, Math.max(280, chartWidth ? chartWidth - 24 : 320));

    const edgePadding = 12;

    const pointerGap = 14;



    let x = anchorX - tooltipWidth / 2;



    if (chartWidth > 0) {
      const centeredLeft = x;

      const centeredRight = x + tooltipWidth;



      if (centeredLeft < edgePadding) {
        x = Math.min(

          Math.max(edgePadding, anchorX + pointerGap),

          Math.max(edgePadding, chartWidth - tooltipWidth - edgePadding)

        );

      } else if (centeredRight > chartWidth - edgePadding) {
        x = Math.max(

          edgePadding,

          Math.min(

            anchorX - tooltipWidth - pointerGap,

            chartWidth - tooltipWidth - edgePadding

          )

        );

      }

    }



    return { x };

  }, [LINE_MARGIN.left, chartPaddingPx, chartType, hoverSlice, hoverTooltipLayout]);



  /* ================================

     UI

  ================================= */

  return (

    <Stack spacing={2}>

      {/* FILTERS */}

      <Stack direction="row" spacing={2} flexWrap="wrap">

        {/* Channel */}
        <ChannelSwitcher
          options={channelList.map((channelOption) => ({
            value: channelOption.id,
            label: channelOption.title,
            avatar: channelOption.avatar,
          }))}
          value={channelId}
          onChange={(option) => setChannelId(option?.value || "")}
          sx={CHANNEL_SWITCHER_SX}
          getOptionMeta={(option) => channelRevenueMap[option?.value] || ""}
          showAllDisabled={!channelList.length}
          showAllVisible={false}
          showAllActive={showAllMode}
          showAllSelectedLabel="All channels"
          onShowAllClick={() => setChannelId(CONTENT_ALL_CHANNELS_VALUE)}
        />

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
            {CONTENT_PERIOD_OPTIONS.map((p) => (
              <MenuItem key={p.value} value={p.value}>
                {p.label}
              </MenuItem>
            ))}
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

      {showAllMode && (
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: {
              xs: "repeat(2, minmax(0, 1fr))",
              md: "repeat(3, minmax(0, 1fr))",
              xl: "repeat(6, minmax(0, 1fr))",
            },
            gap: 1.5,
          }}
        >
          {showAllSummaryCards.map((item) => (
            <Paper
              key={item.label}
              elevation={0}
              sx={{
                p: 1.75,
                borderRadius: 2.5,
                border: "1px solid",
                borderColor:
                  theme.palette.mode === "dark"
                    ? "rgba(148,163,184,0.2)"
                    : "rgba(15,23,42,0.1)",
                background:
                  theme.palette.mode === "dark"
                    ? "linear-gradient(180deg, rgba(15,23,42,0.88), rgba(10,15,24,0.78))"
                    : "linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.95))",
              }}
            >
              <Typography
                variant="caption"
                sx={{
                  display: "block",
                  mb: 0.6,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color: "text.secondary",
                  fontWeight: 700,
                }}
              >
                {item.label}
              </Typography>
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 800,
                  color: "text.primary",
                }}
              >
                {item.value}
              </Typography>
            </Paper>
          ))}
        </Box>
      )}



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
        {chartType === "line" && lineData.length > 0 && (
          <Box
            component={motion.div}
            key={`${channelId}-${period}-${metric}-${lineData.length}`}
            initial={{ opacity: 0, y: 16, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            sx={{ width: "100%", height: "100%" }}
          >
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
          </Box>

        )}



        {chartType === "line" && hoverSlice && (
          <Box
            ref={hoverTooltipRef}
            sx={{
              position: "absolute",
              top: 10,
              left: 0,
              transform: `translate3d(${hoverTooltipPosition?.x ?? 0}px, 0, 0)`,
              transition: "transform 180ms cubic-bezier(0.22, 1, 0.36, 1)",
              willChange: "transform",
              pointerEvents: "none",
              zIndex: 20,
              width: "max-content",
              maxWidth: "min(360px, calc(100% - 24px))",
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
            component={motion.div}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.28, ease: "easeOut" }}
            sx={{
              height: 1,
              minHeight: 120,
              width: "100%",
            }}
          />

        )}



        {chartType === "bar" && hasBarData && (
          <Box
            component={motion.div}
            key={`${channelId}-${period}-${metric}-${barPrep.keys.join("|")}`}
            initial={{ opacity: 0, y: 16, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            sx={{ width: "100%", height: "100%" }}
          >
          <ResponsiveBar

            debounceResize={150}

            data={barPrep.data}

            keys={barPrep.keys}

            animate={true}

            motionConfig="gentle"

            indexBy="label"

            margin={{ top: 32, right: 16, bottom: 112, left: 56 }}

            padding={0.2}

            valueScale={{ type: "linear" }}

            indexScale={{ type: "band", round: true }}

            enableGridX={false}

            axisBottom={{

              tickRotation: -40,

              tickPadding: 6,

              renderTick: (tick) => {

                const fullLabel = String(tick.value || "");
                const label = formatBarTickLabel(fullLabel);

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

                      <title>{fullLabel}</title>

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

                    const videoId = Object.keys(entry).find(k => k !== "label");

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

                            {entry.label}

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
          </Box>

        )}



        {chartType === "bar" && !hasBarData && (

          <Box
            component={motion.div}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.28, ease: "easeOut" }}
            sx={{
              height: 1,
              minHeight: 120,
              width: "100%",
            }}
          />

        )}



        {/* 🔴 Performance Tip */}

      </Box>



      {/* TABLE */}

      <TableContainer component={Paper} elevation={0} sx={tablePaperSx}>

        <Table size="small">

          <TableHead sx={tableHeadSx}>

            <TableRow>

              <TableCell>{showAllMode ? "Channel" : "Video"}</TableCell>

              {showAllMode ? (
                <TableCell sortDirection={sortKey === "videoCount" ? sortDirection : false}>
                  <TableSortLabel
                    active={sortKey === "videoCount"}
                    direction={sortKey === "videoCount" ? sortDirection : "desc"}
                    onClick={() => handleSort("videoCount")}
                  >
                    Videos
                  </TableSortLabel>
                </TableCell>
              ) : null}

              <TableCell sortDirection={sortKey === "published" ? sortDirection : false}>
                <TableSortLabel
                  active={sortKey === "published"}
                  direction={sortKey === "published" ? sortDirection : "desc"}
                  onClick={() => handleSort("published")}
                >
                  {showAllMode ? "Latest Publish" : "Publish Date"}
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
              {showAllMode ? (
                <TableCell align="right" sx={{ fontWeight: 700 }}>
                  {formatNumber(rows.length)}
                </TableCell>
              ) : null}
              <TableCell />
              {selectedTableMetrics.map((metricKey) => (
                <TableCell key={metricKey} align="right">
                  {totals[metricKey] == null
                    ? "-"
                    : formatTableMetricValue(metricKey, totals[metricKey])}
                </TableCell>
              ))}
            </TableRow>

            {pagedRows.map((r) => {
              const isExpanded = !!expandedChannelIds[r.id];
              const expandedVideos = showAllMode ? channelExpandedVideos[r.id] || [] : [];

              return (
                <Fragment key={r.id}>
                  <TableRow

                    key={r.id}
                    onClick={showAllMode ? () => handleToggleChannelExpand(r.id) : undefined}

                    sx={{

                      transition: "transform 0.2s ease, background-color 0.2s ease",
                      cursor: showAllMode ? "pointer" : "default",

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

                      {showAllMode ? (
                        <Stack direction="row" spacing={1} alignItems="center">
                          <Box
                            sx={{
                              width: 18,
                              height: 18,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              color: "text.secondary",
                              flexShrink: 0,
                            }}
                          >
                            {isExpanded ? (
                              <KeyboardArrowDownIcon fontSize="small" />
                            ) : (
                              <KeyboardArrowRightIcon fontSize="small" />
                            )}
                          </Box>
                          <Avatar
                            src={r.channelAvatar || ""}
                            alt={r.displayTitle || r.title}
                            sx={{ width: 28, height: 28, fontSize: 13, fontWeight: 700 }}
                          >
                            {String(r.displayTitle || r.title || "?").trim().charAt(0).toUpperCase()}
                          </Avatar>
                          <Box sx={{ minWidth: 0 }}>
                            <Typography
                              sx={{
                                display: "block",
                                fontWeight: 700,
                                color: "text.primary",
                              }}
                            >
                              {r.displayTitle || r.title}
                            </Typography>
                          </Box>
                        </Stack>
                      ) : (
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

                            style={{ color: "inherit", textDecoration: "none", minWidth: 0 }}

                          >

                            <Box sx={{ minWidth: 0 }}>
                              <Typography
                                component="span"
                                sx={{
                                  display: "block",
                                  fontWeight: 600,
                                  color: "inherit",
                                }}
                              >
                                {r.title}
                              </Typography>
                            </Box>

                          </a>

                        </Stack>
                      )}

                    </TableCell>

                    {showAllMode ? (
                      <TableCell align="right">{formatNumber(r.videoCount)}</TableCell>
                    ) : null}


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

                  {showAllMode && isExpanded
                    ? expandedVideos.map((videoRow) => (
                        <TableRow
                          key={`${r.id}:${videoRow.id}`}
                          sx={{
                            backgroundColor:
                              theme.palette.mode === "dark"
                                ? "rgba(15,23,42,0.48)"
                                : "rgba(248,250,252,0.95)",
                            "&:hover": {
                              backgroundColor:
                                theme.palette.mode === "dark"
                                  ? "rgba(30,41,59,0.58)"
                                  : "rgba(241,245,249,0.98)",
                            },
                          }}
                        >
                          <TableCell sx={{ pl: 5.5 }}>
                            <Stack direction="row" spacing={1} alignItems="center">
                              <a
                                href={`https://www.youtube.com/watch?v=${videoRow.id}`}
                                target="_blank"
                                rel="noreferrer"
                                style={{ display: "inline-flex" }}
                              >
                                <VideoThumbnail
                                  src={videoRow.thumbnail}
                                  duration={videoRow.duration}
                                  videoId={videoRow.id}
                                />
                              </a>
                              <a
                                href={`https://www.youtube.com/watch?v=${videoRow.id}`}
                                target="_blank"
                                rel="noreferrer"
                                style={{ color: "inherit", textDecoration: "none", minWidth: 0 }}
                              >
                                <Box sx={{ minWidth: 0 }}>
                                  <Typography
                                    component="span"
                                    sx={{
                                      display: "block",
                                      fontWeight: 600,
                                      color: "inherit",
                                    }}
                                  >
                                    {videoRow.title}
                                  </Typography>
                                </Box>
                              </a>
                            </Stack>
                          </TableCell>

                          <TableCell align="right" />

                          <TableCell>
                            {videoRow.published
                              ? dayjs(videoRow.published).format("DD-MM-YYYY")
                              : ""}
                          </TableCell>

                          {selectedTableMetrics.map((metricKey) => (
                            <TableCell key={`${videoRow.id}:${metricKey}`} align="right">
                              {formatTableMetricValue(metricKey, videoRow[metricKey])}
                            </TableCell>
                          ))}
                        </TableRow>
                      ))
                    : null}
                </Fragment>
              );
            })}



          </TableBody>

        </Table>

        <TablePagination

          component="div"

          count={tableRows.length}

          page={page}

          onPageChange={(_, nextPage) => setPage(nextPage)}

          rowsPerPage={rowsPerPage}

          onRowsPerPageChange={(e) => {

            setRowsPerPage(normalizeRowsPerPage(e.target.value));

            setPage(0);

          }}

          rowsPerPageOptions={CONTENT_ROWS_PER_PAGE_OPTIONS}

        />

      </TableContainer>

    </Stack >

  );

};



export default ContentAnalytics;

