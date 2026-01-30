import { useEffect, useMemo, useState } from "react";
import {
  Box,
  Grid,
  Card,
  CardMedia,
  CardContent,
  Typography,
  Chip,
  Stack,
  Button,
  TextField,
  MenuItem,
  CircularProgress,
  useTheme,
} from "@mui/material";
import { motion } from "framer-motion";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import ThumbUpAltOutlinedIcon from "@mui/icons-material/ThumbUpAltOutlined";
import CommentOutlinedIcon from "@mui/icons-material/CommentOutlined";
import CalendarMonthOutlinedIcon from "@mui/icons-material/CalendarMonthOutlined";
import { ResponsiveChoropleth } from "@nivo/geo";
import { tokens } from "../theme";
import Header from "./Header";
import api from "../services/api";
import { COUNTRY_FALLBACK } from "../data/countryMapping";
import { geoFeatures } from "../data/mockGeoFeatures";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

const MotionCard = motion.create(Card);

// Variant cho card khi hover
const cardVariants = {
  rest: {
    y: 0,
    boxShadow: "0 4px 12px rgba(0,0,0,0.25)",
    scale: 1,
  },
  hover: {
    y: -4,
    boxShadow: "0 12px 30px rgba(0,0,0,0.35)",
    scale: 1.01,
  },
};

// Variant cho overlay khi hover
const overlayVariants = {
  rest: { opacity: 0, y: 10, pointerEvents: "none" },
  hover: { opacity: 1, y: 0, pointerEvents: "auto" },
};

const OVERVIEW_RANGES = [
  { value: "7d", label: "Last 7 days", days: 7 },
  { value: "28d", label: "Last 28 days", days: 28 },
  { value: "90d", label: "Last 90 days", days: 90 },
];
const OVERVIEW_LIMIT_STEP = 10;
const OVERVIEW_LIMIT_MAX = 50;
const OVERVIEW_LIMIT_DEFAULT = 10;

const VideoList = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const textOnDark = "#fff";

  const [channels, setChannels] = useState([]);
  const [selectedChannel, setSelectedChannel] = useState(() => {
    try {
      return localStorage.getItem("overview.selectedChannelId") || "";
    } catch {
      return "";
    }
  });
  const [overviewRange, setOverviewRange] = useState(() => {
    try {
      const stored = localStorage.getItem("overview.range") || "28d";
      const exists = OVERVIEW_RANGES.some((range) => range.value === stored);
      return exists ? stored : "28d";
    } catch {
      return "28d";
    }
  });
  const [videos, setVideos] = useState([]);
  const [loadingChannels, setLoadingChannels] = useState(true);
  const [loadingVideos, setLoadingVideos] = useState(false);
  const [topKeywords, setTopKeywords] = useState([]);
  const [topSources, setTopSources] = useState([]);
  const [keywordLimit, setKeywordLimit] = useState(OVERVIEW_LIMIT_DEFAULT);
  const [sourceLimit, setSourceLimit] = useState(OVERVIEW_LIMIT_DEFAULT);
  const [countryViews, setCountryViews] = useState([]);
  const [subscribersSeries, setSubscribersSeries] = useState([]);
  const [revenueRows, setRevenueRows] = useState([]);
  const [animateOverviewBars, setAnimateOverviewBars] = useState(false);
  const [error, setError] = useState("");
  const activeRange =
    OVERVIEW_RANGES.find((range) => range.value === overviewRange) ||
    OVERVIEW_RANGES[1];
  const rangeDays = activeRange.days;
  const rangeLabel = activeRange.label;
  const canLoadMoreKeywords =
    topKeywords.length >= keywordLimit && keywordLimit < OVERVIEW_LIMIT_MAX;
  const canLoadMoreSources =
    topSources.length >= sourceLimit && sourceLimit < OVERVIEW_LIMIT_MAX;
  const latestVideos = useMemo(() => {
    const sorted = [...videos].sort((a, b) => {
      const aTime = a?.publish_date ? new Date(a.publish_date).getTime() : 0;
      const bTime = b?.publish_date ? new Date(b.publish_date).getTime() : 0;
      return bTime - aTime;
    });
    return sorted.slice(0, 5);
  }, [videos]);
  const subscribersSummary = useMemo(() => {
    const sorted = [...subscribersSeries].sort((a, b) => {
      const aTime = a?.day ? new Date(a.day).getTime() : 0;
      const bTime = b?.day ? new Date(b.day).getTime() : 0;
      return aTime - bTime;
    });
    const last = sorted.slice(-rangeDays);
    const prev = sorted.slice(-(rangeDays * 2), -rangeDays);
    const sum = (rows, key) =>
      rows.reduce((acc, row) => acc + Number(row?.[key] || 0), 0);
    const gained = sum(last, "subscribers_gained");
    const lost = sum(last, "subscribers_lost");
    const change = gained - lost;
    const avg = last.length ? change / last.length : 0;
    const prevGained = sum(prev, "subscribers_gained");
    const prevLost = sum(prev, "subscribers_lost");
    const prevChange = prevGained - prevLost;
    const prevAvg = prev.length ? prevChange / prev.length : 0;
    const pct = (cur, prevVal) =>
      prevVal ? ((cur - prevVal) / prevVal) * 100 : 0;

    return {
      stats: {
        gained,
        lost,
        change,
        avg,
        gainedPct: pct(gained, prevGained),
        lostPct: pct(lost, prevLost),
        changePct: pct(change, prevChange),
        avgPct: pct(avg, prevAvg),
      },
      chart: last.map((row) => ({
        day: row.day,
        gained: Number(row?.subscribers_gained || 0),
        change:
          Number(row?.subscribers_gained || 0) -
          Number(row?.subscribers_lost || 0),
      })),
    };
  }, [subscribersSeries, rangeDays]);
  const countryResolvers = useMemo(() => {
    const iso2ToFeatureId = new Map();
    const idToName = new Map();

    for (const f of geoFeatures.features) {
      const id = String(f.id || f.properties?.iso_a3 || "");
      const iso2 = f.properties?.iso_a2?.toUpperCase() || "";
      const name = f.properties?.name || id;

      if (iso2) iso2ToFeatureId.set(iso2, id);
      idToName.set(id, name);
    }

    return {
      resolveId: (code) => {
        const c = String(code).toUpperCase();
        return iso2ToFeatureId.get(c) || COUNTRY_FALLBACK[c] || c;
      },
      nameOf: (id) => idToName.get(id) || id,
    };
  }, []);
  const countryMapData = useMemo(() => {
    return (countryViews || []).map((row) => {
      const id = countryResolvers.resolveId(row.country);
      return {
        id,
        value: Number(row.views) || 0,
        label: countryResolvers.nameOf(id),
      };
    });
  }, [countryViews, countryResolvers]);
  const countryDomainMax = useMemo(() => {
    const vals = countryMapData.map((d) => Number(d.value) || 0);
    return Math.max(1, ...vals);
  }, [countryMapData]);
  const topCountries = useMemo(() => {
    return [...(countryMapData || [])]
      .sort((a, b) => (b.value || 0) - (a.value || 0))
      .slice(0, 5);
  }, [countryMapData]);
  const topKeywordMax = useMemo(() => {
    return Math.max(1, ...topKeywords.map((k) => Number(k.views) || 0));
  }, [topKeywords]);
  const topSourceMax = useMemo(() => {
    return Math.max(1, ...topSources.map((s) => Number(s.views) || 0));
  }, [topSources]);
  const revenueSummary = useMemo(() => {
    const sum = (rows, key) =>
      rows.reduce((acc, row) => acc + Number(row?.[key] || 0), 0);
    const avg = (rows, key) => {
      let total = 0;
      let count = 0;
      rows.forEach((row) => {
        const raw = row?.[key];
        if (raw == null || raw === "") return;
        const value = Number(raw);
        if (!Number.isNaN(value)) {
          total += value;
          count += 1;
        }
      });
      return count ? total / count : null;
    };
    return {
      estimated: sum(revenueRows, "estimated_revenue"),
      ad: sum(revenueRows, "ad_revenue"),
      gross: sum(revenueRows, "gross_revenue"),
      rpmAvg: avg(revenueRows, "rpm"),
    };
  }, [revenueRows]);
  const revenueChartData = useMemo(() => {
    return (revenueRows || []).map((row) => ({
      day: row.day,
      estimated: Number(row?.estimated_revenue || 0),
    }));
  }, [revenueRows]);
  const subscribersXAxisTicks = useMemo(() => {
    const days = subscribersSummary.chart
      .map((row) => row.day)
      .filter(Boolean);
    if (!days.length) return [];
    return [days[0], days[days.length - 1]];
  }, [subscribersSummary.chart]);
  const chartTooltipStyles = useMemo(() => {
    const isDark = theme.palette.mode === "dark";
    return {
      contentStyle: {
        backgroundColor: isDark ? "rgba(15,23,42,0.92)" : "#ffffff",
        border: isDark
          ? "1px solid rgba(148,163,184,0.35)"
          : "1px solid rgba(15,23,42,0.12)",
        borderRadius: 8,
        boxShadow: isDark
          ? "0 10px 18px rgba(2,6,23,0.45)"
          : "0 10px 18px rgba(15,23,42,0.12)",
      },
      labelStyle: { color: isDark ? "#e2e8f0" : "#0f172a" },
    };
  }, [theme.palette.mode]);

  // Fetch danh sách account_tag
  useEffect(() => {
    const fetchChannels = async () => {
      try {
        setLoadingChannels(true);
        const res = await api.get("/api/video_overview/channels");
        const data = res.data;
        const items = data.items || [];
        const order = (() => {
          try {
            return JSON.parse(localStorage.getItem("tokens.order") || "[]");
          } catch {
            return [];
          }
        })()
          .map((name) => String(name || "").replace(/\.pickle$/i, ""))
          .filter(Boolean);
        const orderKey = (value) => String(value || "").toLowerCase();
        const byId = new Map(items.map((c) => [orderKey(c.value), c]));
        const ordered = order
          .map((name) => byId.get(orderKey(name)))
          .filter(Boolean);
        const remaining = items.filter(
          (c) => !order.map(orderKey).includes(orderKey(c.value))
        );
        const finalChannels = [...ordered, ...remaining];
        setChannels(finalChannels);
        if (finalChannels.length > 0) {
          const exists = selectedChannel && finalChannels.some((c) => c.value === selectedChannel);
          if (!exists) setSelectedChannel(finalChannels[0].value);
        }
      } catch (err) {
        console.error(err);
        setError(
          "Không load được danh sách kênh. Hãy chạy backend: uvicorn python_backend.main:app --host 0.0.0.0 --port 8000 --reload"
        );
      } finally {
        setLoadingChannels(false);
      }
    };

    fetchChannels();
  }, [selectedChannel]);

  useEffect(() => {
    if (!selectedChannel) return;
    try {
      localStorage.setItem("overview.selectedChannelId", selectedChannel);
    } catch {
      // ignore storage errors
    }
  }, [selectedChannel]);

  useEffect(() => {
    try {
      localStorage.setItem("overview.range", overviewRange);
    } catch {
      // ignore storage errors
    }
  }, [overviewRange]);

  useEffect(() => {
    setKeywordLimit(OVERVIEW_LIMIT_DEFAULT);
    setSourceLimit(OVERVIEW_LIMIT_DEFAULT);
  }, [selectedChannel, overviewRange]);

  // Fetch video theo accountTag
  useEffect(() => {
    if (!selectedChannel) return;

    const fetchVideos = async () => {
      try {
        setLoadingVideos(true);
        setError("");
        const res = await api.get(
          `/api/video_overview/videos?accountTag=${encodeURIComponent(
            selectedChannel
          )}`
        );
        const data = res.data;
        setVideos(data || []);
      } catch (err) {
        console.error(err);
        setError("Không load được danh sách video.");
      } finally {
        setLoadingVideos(false);
      }
    };

    fetchVideos();
  }, [selectedChannel]);

  useEffect(() => {
    if (!selectedChannel) return;
    const fetchOverviewExtras = async () => {
      try {
        const [
          topKeywordsResp,
          topSourcesResp,
          countryResp,
          subsResp,
          revenueResp,
        ] = await Promise.all([
          api.get(
            `/api/video_overview/top_keywords?accountTag=${encodeURIComponent(
              selectedChannel
            )}&limit=${keywordLimit}&range=${overviewRange}`
          ),
          api.get(
            `/api/video_overview/top_sources?accountTag=${encodeURIComponent(
              selectedChannel
            )}&limit=${sourceLimit}&range=${overviewRange}`
          ),
          api.get(
            `/api/video_overview/views_by_country?accountTag=${encodeURIComponent(
              selectedChannel
            )}&range=${overviewRange}`
          ),
          api.get(
            `/api/video_overview/subscribers_timeseries?accountTag=${encodeURIComponent(
              selectedChannel
            )}&days=${rangeDays}`
          ),
          api.get(
            `/api/revenue?accountTag=${encodeURIComponent(
              selectedChannel
            )}&range=${overviewRange}`
          ),
        ]);

        const topKeywordsData = topKeywordsResp.data;
        const topSourcesData = topSourcesResp.data;
        const countryData = countryResp.data;
        const subsData = subsResp.data;
        const revenueData = revenueResp.data;

        setAnimateOverviewBars(false);
        setTopKeywords(Array.isArray(topKeywordsData) ? topKeywordsData : []);
        setTopSources(Array.isArray(topSourcesData) ? topSourcesData : []);
        setCountryViews(Array.isArray(countryData?.rows) ? countryData.rows : []);
        setSubscribersSeries(Array.isArray(subsData) ? subsData : []);
        setRevenueRows(Array.isArray(revenueData?.rows) ? revenueData.rows : []);
        requestAnimationFrame(() => setAnimateOverviewBars(true));
      } catch (err) {
        setTopKeywords([]);
        setTopSources([]);
        setCountryViews([]);
        setSubscribersSeries([]);
        setRevenueRows([]);
        setAnimateOverviewBars(false);
      }
    };

    fetchOverviewExtras();
  }, [
    selectedChannel,
    overviewRange,
    rangeDays,
    keywordLimit,
    sourceLimit,
  ]);

  const formatNumber = (n) => {
    if (n == null) return "-";
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
    return n.toString();
  };
  const formatCurrency = (value) => {
    if (value == null) return "-";
    const num = Number(value);
    if (Number.isNaN(num)) return "-";
    return `$${num.toFixed(2)}`;
  };

  const formatDate = (iso) => {
    if (!iso) return "-";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;

    const day = d.getDate().toString().padStart(2, "0");
    const month = (d.getMonth() + 1).toString().padStart(2, "0");
    const year = d.getFullYear().toString().slice(-2); // "YY"

    return `${day}/${month}/${year}`; // dd/mm/YY
  };

  const formatDateFull = (iso) => {
    if (!iso) return "-";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;

    const day = d.getDate().toString().padStart(2, "0");
    const month = (d.getMonth() + 1).toString().padStart(2, "0");
    const year = d.getFullYear().toString(); // YYYY

    return `${day}-${month}-${year}`; // dd-mm-yyyy
  };
  const formatDateMonth = (iso) => {
    if (!iso) return "-";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;

    const day = d.getDate().toString().padStart(2, "0");
    const month = (d.getMonth() + 1).toString().padStart(2, "0");

    return `${day}/${month}`; // dd/mm
  };

  const sectionSx = {
    borderRadius: 3,
    border: "1px solid",
    borderColor:
      theme.palette.mode === "dark"
        ? "rgba(148,163,184,0.2)"
        : "rgba(15,23,42,0.12)",
    background:
      theme.palette.mode === "dark"
        ? "rgba(10,15,24,0.8)"
        : "rgba(255,255,255,0.94)",
    boxShadow:
      theme.palette.mode === "dark"
        ? "0 14px 28px rgba(15,23,42,0.4)"
        : "0 14px 26px rgba(148,163,184,0.25)",
    p: 2,
  };
  const statCardSx = {
    borderRadius: 2,
    p: 2,
    textAlign: "center",
    border: "1px solid",
    borderColor:
      theme.palette.mode === "dark"
        ? "rgba(148,163,184,0.2)"
        : "rgba(15,23,42,0.12)",
    background:
      theme.palette.mode === "dark"
        ? "rgba(15,23,42,0.7)"
        : "rgba(248,250,252,0.9)",
    boxShadow:
      theme.palette.mode === "dark"
        ? "0 12px 22px rgba(2,6,23,0.55)"
        : "0 10px 20px rgba(148,163,184,0.25)",
  };
  const chartCardSx = {
    borderRadius: 2,
    p: 0.5,
    border: "1px solid",
    borderColor:
      theme.palette.mode === "dark"
        ? "rgba(148,163,184,0.2)"
        : "rgba(15,23,42,0.12)",
    background:
      theme.palette.mode === "dark"
        ? "rgba(15,23,42,0.6)"
        : "rgba(248,250,252,0.9)",
  };
  const pctColor = (value) =>
    value >= 0 ? "rgb(34,197,94)" : "rgb(239,68,68)";
  const formatPct = (value) => `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
  const latestRowSx = {
    display: "grid",
    gridTemplateColumns: "repeat(5, minmax(0, 1fr))",
    gap: 2,
    width: "100%",
  };

  const renderVideoCard = (v, idx) => (
    <Box key={v.video_id || idx} sx={{ width: "100%" }}>
      <MotionCard
        variants={cardVariants}
        initial="rest"
        whileHover="hover"
        transition={{ duration: 0.2, delay: idx * 0.03 }}
        onClick={() =>
          window.open(`https://www.youtube.com/watch?v=${v.video_id}`, "_blank")
        }
        sx={{
          position: "relative",
          borderRadius: 3,
          border: "1px solid",
          borderColor:
            theme.palette.mode === "dark"
              ? "rgba(148,163,184,0.2)"
              : "rgba(15,23,42,0.12)",
          background:
            theme.palette.mode === "dark"
              ? "linear-gradient(140deg, rgba(15,23,42,0.92) 0%, rgba(30,41,59,0.88) 60%, rgba(14,165,233,0.18) 100%)"
              : "linear-gradient(140deg, rgba(248,250,252,0.96) 0%, rgba(226,232,240,0.92) 55%, rgba(191,219,254,0.6) 100%)",
          overflow: "hidden",
          cursor: "pointer",
          display: "flex",
          flexDirection: "column",
          height: "100%",
        }}
      >
        {v.thumbnail && (
          <CardMedia
            component="img"
            image={v.thumbnail}
            alt={v.title}
            sx={{
              width: "100%",
              aspectRatio: "2",
              objectFit: "cover",
            }}
          />
        )}

        <CardContent
          sx={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            gap: 1,
          }}
        >
          <Typography
            variant="subtitle1"
            color={theme.palette.text.primary}
            fontWeight={600}
            noWrap
            title={v.title}
          >
            {v.title}
          </Typography>

          <Box display="flex" alignItems="center" gap={1}>
            <CalendarMonthOutlinedIcon
              sx={{ fontSize: 16, color: colors.grey[300] }}
            />
            <Typography
              variant="caption"
              color={colors.grey[300]}
              sx={{ opacity: 0.8 }}
            >
              {formatDate(v.publish_date)}
            </Typography>
          </Box>

          <Box
            display="flex"
            alignItems="center"
            justifyContent="space-between"
            mt={1}
          >
            <Box display="flex" gap={1}>
              <Chip
                size="small"
                icon={
                  <VisibilityOutlinedIcon
                    sx={{ fontSize: 16, color: textOnDark }}
                  />
                }
                label={formatNumber(v.views)}
                sx={{
                  bgcolor: colors.primary[500],
                  color: textOnDark,
                  "& .MuiChip-icon": { ml: 0.5, color: textOnDark },
                }}
              />
              <Chip
                size="small"
                icon={
                  <ThumbUpAltOutlinedIcon
                    sx={{ fontSize: 16, color: textOnDark }}
                  />
                }
                label={formatNumber(v.likes)}
                sx={{
                  bgcolor: colors.primary[500],
                  color: textOnDark,
                  "& .MuiChip-icon": { ml: 0.5, color: textOnDark },
                }}
              />
              <Chip
                size="small"
                icon={
                  <CommentOutlinedIcon
                    sx={{ fontSize: 16, color: textOnDark }}
                  />
                }
                label={formatNumber(v.comments)}
                sx={{
                  bgcolor: colors.primary[500],
                  color: textOnDark,
                  "& .MuiChip-icon": { ml: 0.5, color: textOnDark },
                }}
              />
            </Box>
          </Box>
        </CardContent>

        <Box
          component={motion.div}
          variants={overlayVariants}
          sx={{
            position: "absolute",
            inset: 0,
            bgcolor: "rgba(0,0,0,0.9)",
            color: textOnDark,
            p: 2,
            display: "flex",
            flexDirection: "column",
            gap: 0.5,
            overflowY: "auto",
            pr: 1.5,
            pb: 2,
            zIndex: 2,
            "& .MuiTypography-root": {
              fontSize: "0.8rem",
            },
          }}
        >
          <Box mt={1} />

          <Typography variant="caption">
            <strong>Engaged views:</strong> {formatNumber(v.engaged_views)}
          </Typography>

          <Box mt={1} />

          <Typography variant="caption">
            <strong>Annotation CTR:</strong>{" "}
            {v.annotation_click_through_rate ?? "-"}
          </Typography>
          <Typography variant="caption">
            <strong>Annotation close rate:</strong>{" "}
            {v.annotation_close_rate ?? "-"}
          </Typography>
          <Typography variant="caption">
            <strong>Avg view duration (s):</strong>{" "}
            {v.average_view_duration_seconds ?? "-"}
          </Typography>
          <Typography variant="caption">
            <strong>Shares:</strong> {formatNumber(v.shares)}
          </Typography>
          <Typography variant="caption">
            <strong>Subscribers gained:</strong>{" "}
            {formatNumber(v.subscribers_gained)}
          </Typography>
          <Typography variant="caption">
            <strong>Subscribers lost:</strong>{" "}
            {formatNumber(v.subscribers_lost)}
          </Typography>

          <Box mt={1} />
        </Box>
      </MotionCard>
    </Box>
  );


  return (
    <Box mx="20px" mt="0" mb="20px">
      <Header title="Overview" subtitle="Overview Channel Statistic" />

      {/* Filter hàng đầu */}
      <Box
        mb={2}
        display="flex"
        alignItems="center"
        justifyContent="space-between"
        flexWrap="wrap"
        gap={2}
      >
        <Box display="flex" alignItems="center" gap={2}>
          <Typography
            variant="subtitle1"
            color={colors.grey[100]}
            fontWeight={600}
          >
            Choose Channel:
          </Typography>

          {loadingChannels ? (
            <CircularProgress size={20} />
          ) : (
            <TextField
              select
              size="small"
              value={selectedChannel}
              onChange={(e) => setSelectedChannel(e.target.value)}
              sx={{ minWidth: 220 }}
            >
              {channels.map((c) => (
                <MenuItem key={c.value} value={c.value}>
                  {c.label}
                </MenuItem>
              ))}
            </TextField>
          )}

          <Typography
            variant="subtitle1"
            color={colors.grey[100]}
            fontWeight={600}
          >
            Date Range:
          </Typography>
          <TextField
            select
            size="small"
            value={overviewRange}
            onChange={(e) => setOverviewRange(e.target.value)}
            sx={{ minWidth: 160 }}
          >
            {OVERVIEW_RANGES.map((range) => (
              <MenuItem key={range.value} value={range.value}>
                {range.label}
              </MenuItem>
            ))}
          </TextField>
        </Box>

        {videos && videos.length > 0 && (
          <Typography variant="body2" color={colors.grey[300]}>
            Total:{" "}
            <span style={{ fontWeight: 600 }}>{videos.length} video</span>
          </Typography>
        )}
      </Box>

      {error && (
        <Typography color="error" mb={2}>
          {error}
        </Typography>
      )}

      {/* Loading */}
      {loadingVideos && videos.length === 0 ? (
        <Box
          mt={4}
          display="flex"
          justifyContent="center"
          alignItems="center"
        >
          <CircularProgress />
        </Box>
      ) : videos.length === 0 ? (
        <Box mt={4} textAlign="center">
          <Typography color={colors.grey[300]}>
            This channel has no data
          </Typography>
        </Box>
      ) : (
        <>
          <Box
            mt={2}
            sx={{
              display: "grid",
              gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
              gap: 2,
              width: "100%",
            }}
          >
            <Box sx={{ display: "flex" }}>
              <Box sx={{ ...sectionSx, p: 4, minHeight: 560, width: "100%" }}>
                <Typography variant="h5" fontWeight={700} mb={2}>
                  Subscribers ({rangeLabel})
                </Typography>
                {subscribersSeries.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    No data
                  </Typography>
                ) : (
                  <>
                    <Grid container spacing={2} mb={2}>
                      <Grid size={{ xs: 12, md: 3 }}>
                        <Box sx={statCardSx}>
                          <Typography variant="body2" color="text.secondary">
                            Gained
                          </Typography>
                          <Typography variant="h5" fontWeight={700}>
                            {formatNumber(subscribersSummary.stats.gained)}
                          </Typography>
                          <Typography
                            variant="body2"
                            sx={{ color: pctColor(subscribersSummary.stats.gainedPct) }}
                          >
                            {formatPct(subscribersSummary.stats.gainedPct)}
                          </Typography>
                        </Box>
                      </Grid>
                      <Grid size={{ xs: 12, md: 3 }}>
                        <Box sx={statCardSx}>
                          <Typography variant="body2" color="text.secondary">
                            Lost
                          </Typography>
                          <Typography variant="h5" fontWeight={700}>
                            {formatNumber(subscribersSummary.stats.lost)}
                          </Typography>
                          <Typography
                            variant="body2"
                            sx={{ color: pctColor(-subscribersSummary.stats.lostPct) }}
                          >
                            {formatPct(subscribersSummary.stats.lostPct)}
                          </Typography>
                        </Box>
                      </Grid>
                      <Grid size={{ xs: 12, md: 3 }}>
                        <Box sx={statCardSx}>
                          <Typography variant="body2" color="text.secondary">
                            Change
                          </Typography>
                          <Typography variant="h5" fontWeight={700}>
                            {formatNumber(subscribersSummary.stats.change)}
                          </Typography>
                          <Typography
                            variant="body2"
                            sx={{ color: pctColor(subscribersSummary.stats.changePct) }}
                          >
                            {formatPct(subscribersSummary.stats.changePct)}
                          </Typography>
                        </Box>
                      </Grid>
                      <Grid size={{ xs: 12, md: 3 }}>
                        <Box sx={statCardSx}>
                          <Typography variant="body2" color="text.secondary">
                            Avg daily change
                          </Typography>
                          <Typography variant="h5" fontWeight={700}>
                            {formatNumber(Math.round(subscribersSummary.stats.avg))}
                          </Typography>
                          <Typography
                            variant="body2"
                            sx={{ color: pctColor(subscribersSummary.stats.avgPct) }}
                          >
                            {formatPct(subscribersSummary.stats.avgPct)}
                          </Typography>
                        </Box>
                      </Grid>
                    </Grid>

                    <Grid container spacing={2} sx={{ minWidth: 0 }}>
                      <Grid size={{ xs: 12, md: 6 }} sx={{ minWidth: 0 }}>
                        <Box sx={{ ...chartCardSx, minWidth: 0, width: "100%" }}>
                          <Typography variant="subtitle1" fontWeight={700} mb={0.5}>
                            Gained
                          </Typography>
                          <Box sx={{ width: "100%", minWidth: 0, minHeight: 0 }}>
                            <ResponsiveContainer width="100%" height={320} minWidth={0} minHeight={0}>
                              <BarChart
                                data={subscribersSummary.chart}
                                margin={{ top: 4, right: 6, left: -30, bottom: -6 }}
                              >
                                <CartesianGrid
                                  stroke="rgba(148,163,184,0.2)"
                                  strokeDasharray="3 3"
                                />
                                <XAxis
                                  dataKey="day"
                                  tick={{ fontSize: 11 }}
                                  ticks={subscribersXAxisTicks}
                                  tickFormatter={formatDateMonth}
                                />
                                <YAxis tickFormatter={formatNumber} />
                                <Tooltip
                                  {...chartTooltipStyles}
                                  labelFormatter={formatDateFull}
                                />
                                <Bar dataKey="gained" fill="#22c55e" radius={[6, 6, 0, 0]} />
                              </BarChart>
                            </ResponsiveContainer>
                          </Box>
                        </Box>
                      </Grid>
                      <Grid size={{ xs: 12, md: 6 }} sx={{ minWidth: 0 }}>
                        <Box sx={{ ...chartCardSx, minWidth: 0, width: "100%" }}>
                          <Typography variant="subtitle1" fontWeight={700} mb={0.5}>
                            Change
                          </Typography>
                          <Box sx={{ width: "100%", minWidth: 0, minHeight: 0 }}>
                            <ResponsiveContainer width="100%" height={320} minWidth={0} minHeight={0}>
                              <BarChart
                                data={subscribersSummary.chart}
                                margin={{ top: 4, right: 6, left: -30, bottom: -6 }}
                              >
                                <CartesianGrid
                                  stroke="rgba(148,163,184,0.2)"
                                  strokeDasharray="3 3"
                                />
                                <XAxis
                                  dataKey="day"
                                  tick={{ fontSize: 11 }}
                                  ticks={subscribersXAxisTicks}
                                  tickFormatter={formatDateMonth}
                                />
                                <YAxis tickFormatter={formatNumber} />
                                <Tooltip
                                  {...chartTooltipStyles}
                                  labelFormatter={formatDateFull}
                                />
                                <Bar dataKey="change" fill="#7c3aed" radius={[6, 6, 0, 0]} />
                              </BarChart>
                            </ResponsiveContainer>
                          </Box>
                        </Box>
                      </Grid>
                    </Grid>
                  </>
                )}
              </Box>
            </Box>
            <Box sx={{ display: "flex" }}>
              <Box sx={{ ...sectionSx, p: 4, minHeight: 560, width: "100%" }}>
                <Typography variant="subtitle1" fontWeight={700} mb={1}>
                  Revenue ({rangeLabel})
                </Typography>
                {revenueRows.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    No data
                  </Typography>
                ) : (
                  <>
                    <Stack spacing={1.5} alignItems="flex-end">
                      <Box display="flex" alignItems="baseline" gap={1.5} sx={{ textAlign: "left", minWidth: 100 }}>
                        <Typography variant="body2" color="text.secondary">
                          Estimated
                        </Typography>
                        <Typography variant="body2" fontWeight={600}>
                          {formatCurrency(revenueSummary.estimated)}
                        </Typography>
                      </Box>
                      <Box display="flex" alignItems="baseline" gap={1.5} sx={{ textAlign: "left", minWidth: 100 }}>
                        <Typography variant="body2" color="text.secondary">
                          Ad revenue
                        </Typography>
                        <Typography variant="body2" fontWeight={600}>
                          {formatCurrency(revenueSummary.ad)}
                        </Typography>
                      </Box>
                      <Box display="flex" alignItems="baseline" gap={1.5} sx={{ textAlign: "left", minWidth: 100 }}>
                        <Typography variant="body2" color="text.secondary">
                          Gross revenue
                        </Typography>
                        <Typography variant="body2" fontWeight={600}>
                          {formatCurrency(revenueSummary.gross)}
                        </Typography>
                      </Box>
                      <Box display="flex" alignItems="baseline" gap={1.5} sx={{ textAlign: "left", minWidth: 100 }}>
                        <Typography variant="body2" color="text.secondary">
                          Avg RPM
                        </Typography>
                        <Typography variant="body2" fontWeight={600}>
                          {formatCurrency(revenueSummary.rpmAvg)}
                        </Typography>
                      </Box>
                    </Stack>
                    {revenueChartData.length > 0 && (
                      <Box mt={2} height={340} sx={{ ml: -3 }}>
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={revenueChartData}>
                            <CartesianGrid
                              strokeDasharray="3 3"
                              stroke={
                                theme.palette.mode === "dark"
                                  ? "rgba(148,163,184,0.2)"
                                  : "rgba(15,23,42,0.1)"
                              }
                            />
                            <XAxis
                              dataKey="day"
                              tickFormatter={formatDateMonth}
                              tick={{ fontSize: 11 }}
                              interval="preserveStartEnd"
                            />
                            <YAxis
                              tickFormatter={(value) => formatCurrency(value)}
                              tick={{ fontSize: 11 }}
                            />
                            <Tooltip
                              formatter={(value) => [
                                formatCurrency(value),
                                "Estimated",
                              ]}
                              labelFormatter={formatDate}
                              contentStyle={chartTooltipStyles.contentStyle}
                              labelStyle={chartTooltipStyles.labelStyle}
                            />
                            <Line
                              type="monotone"
                              dataKey="estimated"
                              stroke="#f59e0b"
                              strokeWidth={2}
                              dot={false}
                            />
                          </LineChart>
                        </ResponsiveContainer>
                      </Box>
                    )}
                  </>
                )}
              </Box>
            </Box>
          </Box>

          <Box
            mt={2}
            sx={{
              display: "grid",
              gridTemplateColumns: { xs: "1fr", md: "0.9fr 0.9fr 1.2fr" },
              gap: 2,
              width: "100%",
            }}
          >
            <Box sx={{ ...sectionSx, p: 3 }}>
              <Typography variant="subtitle1" fontWeight={700} mb={1}>
                Top 10 keywords by views ({rangeLabel})
              </Typography>
              {topKeywords.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No data
                </Typography>
              ) : (
                <>
                  <Stack spacing={1}>
                    {topKeywords.map((k) => {
                      const value = Number(k.views) || 0;
                      const pct = Math.max(
                        6,
                        Math.round((value / topKeywordMax) * 100)
                      );
                      return (
                        <Box key={k.keyword}>
                          <Box display="flex" justifyContent="space-between" mb={0.5}>
                            <Typography variant="body2">{k.keyword}</Typography>
                            <Typography variant="body2" fontWeight={600}>
                              {formatNumber(value)}
                            </Typography>
                          </Box>
                          <Box
                            sx={{
                              height: 8,
                              borderRadius: 999,
                              bgcolor:
                                theme.palette.mode === "dark"
                                  ? "rgba(148,163,184,0.2)"
                                  : "rgba(15,23,42,0.12)",
                              overflow: "hidden",
                            }}
                          >
                            <Box
                              sx={{
                                width: animateOverviewBars ? `${pct}%` : 0,
                                height: "100%",
                                borderRadius: 999,
                                background:
                                  theme.palette.mode === "dark"
                                    ? "linear-gradient(90deg, #f59e0b, #f97316)"
                                    : "linear-gradient(90deg, #f59e0b, #fb923c)",
                                transition: "width 0.5s ease",
                              }}
                            />
                          </Box>
                        </Box>
                      );
                    })}
                  </Stack>
                  {canLoadMoreKeywords && (
                    <Box mt={2} display="flex" justifyContent="center">
                      <Button
                        size="small"
                        variant="outlined"
                        sx={{
                          transition: "transform 0.2s ease, box-shadow 0.2s ease",
                          color:
                            theme.palette.mode === "dark" ? "#e2e8f0" : "#0f172a",
                          borderColor:
                            theme.palette.mode === "dark"
                              ? "rgba(148,163,184,0.5)"
                              : "rgba(15,23,42,0.25)",
                          "&:hover": {
                            transform: "translateY(-1px)",
                            boxShadow:
                              theme.palette.mode === "dark"
                                ? "0 8px 18px rgba(2,6,23,0.5)"
                                : "0 8px 18px rgba(15,23,42,0.12)",
                            borderColor:
                              theme.palette.mode === "dark"
                                ? "rgba(148,163,184,0.9)"
                                : "rgba(15,23,42,0.5)",
                            backgroundColor:
                              theme.palette.mode === "dark"
                                ? "rgba(148,163,184,0.12)"
                                : "rgba(15,23,42,0.04)",
                          },
                        }}
                        onClick={() =>
                          setKeywordLimit((prev) =>
                            Math.min(prev + OVERVIEW_LIMIT_STEP, OVERVIEW_LIMIT_MAX)
                          )
                        }
                      >
                        Load more
                      </Button>
                    </Box>
                  )}
                </>
              )}
            </Box>

            <Box sx={{ ...sectionSx, p: 3 }}>
              <Typography variant="subtitle1" fontWeight={700} mb={1}>
                Top 10 sources by views ({rangeLabel})
              </Typography>
              {topSources.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No data
                </Typography>
              ) : (
                <>
                  <Stack spacing={1}>
                    {topSources.map((s) => {
                      const value = Number(s.views) || 0;
                      const pct = Math.max(
                        6,
                        Math.round((value / topSourceMax) * 100)
                      );
                      return (
                        <Box key={s.source}>
                          <Box display="flex" justifyContent="space-between" mb={0.5}>
                            <Typography variant="body2">{s.source}</Typography>
                            <Typography variant="body2" fontWeight={600}>
                              {formatNumber(value)}
                            </Typography>
                          </Box>
                          <Box
                            sx={{
                              height: 8,
                              borderRadius: 999,
                              bgcolor:
                                theme.palette.mode === "dark"
                                  ? "rgba(148,163,184,0.2)"
                                  : "rgba(15,23,42,0.12)",
                              overflow: "hidden",
                            }}
                          >
                            <Box
                              sx={{
                                width: animateOverviewBars ? `${pct}%` : 0,
                                height: "100%",
                                borderRadius: 999,
                                background:
                                  theme.palette.mode === "dark"
                                    ? "linear-gradient(90deg, #22c55e, #06b6d4)"
                                    : "linear-gradient(90deg, #22c55e, #0ea5e9)",
                                transition: "width 0.5s ease",
                              }}
                            />
                          </Box>
                        </Box>
                      );
                    })}
                  </Stack>
                  {canLoadMoreSources && (
                    <Box mt={2} display="flex" justifyContent="center">
                      <Button
                        size="small"
                        variant="outlined"
                        sx={{
                          transition: "transform 0.2s ease, box-shadow 0.2s ease",
                          color:
                            theme.palette.mode === "dark" ? "#e2e8f0" : "#0f172a",
                          borderColor:
                            theme.palette.mode === "dark"
                              ? "rgba(148,163,184,0.5)"
                              : "rgba(15,23,42,0.25)",
                          "&:hover": {
                            transform: "translateY(-1px)",
                            boxShadow:
                              theme.palette.mode === "dark"
                                ? "0 8px 18px rgba(2,6,23,0.5)"
                                : "0 8px 18px rgba(15,23,42,0.12)",
                            borderColor:
                              theme.palette.mode === "dark"
                                ? "rgba(148,163,184,0.9)"
                                : "rgba(15,23,42,0.5)",
                            backgroundColor:
                              theme.palette.mode === "dark"
                                ? "rgba(148,163,184,0.12)"
                                : "rgba(15,23,42,0.04)",
                          },
                        }}
                        onClick={() =>
                          setSourceLimit((prev) =>
                            Math.min(prev + OVERVIEW_LIMIT_STEP, OVERVIEW_LIMIT_MAX)
                          )
                        }
                      >
                        Load more
                      </Button>
                    </Box>
                  )}
                </>
              )}
            </Box>

            <Box sx={{ ...sectionSx, p: 3 }}>
              <Typography variant="subtitle1" fontWeight={700} mb={1}>
                Views by country ({rangeLabel})
              </Typography>
              {countryViews.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No data
                </Typography>
              ) : (
                <>
                  <Box height={240}>
                    <ResponsiveChoropleth
                      debounceResize={150}
                      data={countryMapData}
                      features={geoFeatures.features}
                      valueFormat={formatNumber}
                      domain={[0, countryDomainMax]}
                      tooltip={({ feature }) => {
                        const label = countryResolvers.nameOf(feature.id);
                        const value = feature.value || 0;

                        return (
                          <Box
                            sx={{
                              px: 1.2,
                              py: 0.75,
                              borderRadius: 1,
                              fontSize: 13,
                              fontWeight: 600,
                              bgcolor:
                                theme.palette.mode === "dark"
                                  ? "rgba(0,0,0,0.75)"
                                  : "rgba(255,255,255,0.95)",
                              boxShadow: 3,
                            }}
                          >
                            <div>{label}</div>
                            <div>Views: {formatNumber(value)}</div>
                          </Box>
                        );
                      }}
                      unknownColor="#999"
                      projectionScale={80}
                      projectionTranslation={[0.5, 0.65]}
                      borderWidth={1}
                      borderColor="#fff"
                    />
                  </Box>
                  <Box mt={2}>
                    <Stack>
                      {topCountries.map((row) => {
                        const pct =
                          countryDomainMax > 0
                            ? Math.max(6, Math.round((row.value / countryDomainMax) * 100))
                            : 0;
                        return (
                          <Box key={row.id}>
                            <Box display="flex" justifyContent="space-between" mb={0.5}>
                              <Typography variant="body2">
                                {countryResolvers.nameOf(row.id)}
                              </Typography>
                              <Typography variant="body2" fontWeight={600}>
                                {formatNumber(row.value)}
                              </Typography>
                            </Box>
                            <Box
                              sx={{
                                height: 8,
                                borderRadius: 999,
                                bgcolor:
                                  theme.palette.mode === "dark"
                                    ? "rgba(148,163,184,0.2)"
                                    : "rgba(15,23,42,0.12)",
                                overflow: "hidden",
                              }}
                            >
                              <Box
                                sx={{
                                  width: `${pct}%`,
                                  height: "100%",
                                  borderRadius: 999,
                                  background:
                                    theme.palette.mode === "dark"
                                      ? "linear-gradient(90deg, #38bdf8, #a855f7)"
                                      : "linear-gradient(90deg, #0ea5e9, #6366f1)",
                                }}
                              />
                            </Box>
                          </Box>
                        );
                      })}
                    </Stack>
                  </Box>
                </>
              )}
            </Box>
          </Box>

          <Box mt={2} sx={sectionSx}>
            <Typography variant="subtitle1" fontWeight={700} mb={1}>
              Latest 5 videos
            </Typography>
            <Box sx={latestRowSx}>
              {latestVideos.map((v, idx) => renderVideoCard(v, idx))}
            </Box>
          </Box>


        </>
      )}
    </Box>
  );
};

export default VideoList;
