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
import { tokens } from "../theme";
import Header from "./Header";
import { API_BASE } from "../config";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
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

const VideoList = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const textOnDark = "#fff";
  const apiBase = API_BASE;
  const authHeaders = useMemo(() => {
    const token = localStorage.getItem("access_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  const [channels, setChannels] = useState([]);
  const [selectedChannel, setSelectedChannel] = useState("");
  const [videos, setVideos] = useState([]);
  const [loadingChannels, setLoadingChannels] = useState(true);
  const [loadingVideos, setLoadingVideos] = useState(false);
  const [topKeywords, setTopKeywords] = useState([]);
  const [topSources, setTopSources] = useState([]);
  const [countryViews, setCountryViews] = useState([]);
  const [subscribersSeries, setSubscribersSeries] = useState([]);
  const [error, setError] = useState("");
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
    const last = sorted.slice(-30);
    const prev = sorted.slice(-60, -30);
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
  }, [subscribersSeries]);

  // Fetch danh sách account_tag
  useEffect(() => {
    const fetchChannels = async () => {
      try {
        setLoadingChannels(true);
        const res = await fetch(`${apiBase}/api/video_overview/channels`, {
          headers: authHeaders,
        });
        if (!res.ok) throw new Error("Failed to load channels");
        const data = await res.json();
        setChannels(data.items || []);
        if (data.items && data.items.length > 0) {
          setSelectedChannel(data.items[0].value);
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
  }, [apiBase, authHeaders]);

  // Fetch video theo accountTag
  useEffect(() => {
    if (!selectedChannel) return;

    const fetchVideos = async () => {
      try {
        setLoadingVideos(true);
        setError("");
        const res = await fetch(
          `${apiBase}/api/video_overview/videos?accountTag=${encodeURIComponent(
            selectedChannel
          )}`,
          { headers: authHeaders }
        );
        if (!res.ok) throw new Error("Failed to load videos");
        const data = await res.json();
        setVideos(data || []);
      } catch (err) {
        console.error(err);
        setError("Không load được danh sách video.");
      } finally {
        setLoadingVideos(false);
      }
    };

    fetchVideos();
  }, [apiBase, selectedChannel, authHeaders]);

  useEffect(() => {
    if (!selectedChannel) return;
    const fetchOverviewExtras = async () => {
      try {
        const [
          topKeywordsResp,
          topSourcesResp,
          countryResp,
          subsResp,
        ] = await Promise.all([
          fetch(
            `${apiBase}/api/video_overview/top_keywords?accountTag=${encodeURIComponent(
              selectedChannel
            )}&limit=5`,
            { headers: authHeaders }
          ),
          fetch(
            `${apiBase}/api/video_overview/top_sources?accountTag=${encodeURIComponent(
              selectedChannel
            )}&limit=5`,
            { headers: authHeaders }
          ),
          fetch(
            `${apiBase}/api/video_overview/views_by_country?accountTag=${encodeURIComponent(
              selectedChannel
            )}&range=28d`,
            { headers: authHeaders }
          ),
          fetch(
            `${apiBase}/api/video_overview/subscribers_timeseries?accountTag=${encodeURIComponent(
              selectedChannel
            )}&days=90`,
            { headers: authHeaders }
          ),
        ]);

        const [
          topKeywordsData,
          topSourcesData,
          countryData,
          subsData,
        ] = await Promise.all([
          topKeywordsResp.ok ? topKeywordsResp.json() : [],
          topSourcesResp.ok ? topSourcesResp.json() : [],
          countryResp.ok ? countryResp.json() : { rows: [] },
          subsResp.ok ? subsResp.json() : [],
        ]);

        setTopKeywords(Array.isArray(topKeywordsData) ? topKeywordsData : []);
        setTopSources(Array.isArray(topSourcesData) ? topSourcesData : []);
        setCountryViews(Array.isArray(countryData?.rows) ? countryData.rows : []);
        setSubscribersSeries(Array.isArray(subsData) ? subsData : []);
      } catch (err) {
        setTopKeywords([]);
        setTopSources([]);
        setCountryViews([]);
        setSubscribersSeries([]);
      }
    };

    fetchOverviewExtras();
  }, [apiBase, selectedChannel, authHeaders]);

  const formatNumber = (n) => {
    if (n == null) return "-";
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
    return n.toString();
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
    p: 2,
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

  const renderVideoCard = (v, idx) => (
    <Grid item xs={12} sm={6} md={4} lg={3} key={v.video_id || idx}>
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
              height: 160,
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
            zIndex: 2,
            "& .MuiTypography-root": {
              fontSize: "0.9rem",
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
    </Grid>
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
        </Box>

        {videos && videos.length > 0 && (
          <Typography variant="body2" color={colors.grey[300]}>
            Tổng:{" "}
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
        <Box sx={sectionSx}>
          <Typography variant="subtitle1" fontWeight={700} mb={1}>
            Latest 5 videos
          </Typography>
          <Grid container spacing={2}>
            {latestVideos.map((v, idx) => renderVideoCard(v, idx))}
          </Grid>
        </Box>

        <Grid container spacing={2} mt={2}>
          <Grid item xs={12}>
            <Box sx={{ ...sectionSx, p: 3 }}>
              <Typography variant="h5" fontWeight={700} mb={2}>
                Subscribers
              </Typography>
              {subscribersSeries.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No data
                </Typography>
              ) : (
                <>
                  <Grid container spacing={2} mb={2}>
                    <Grid item xs={12} sm={6} md={3}>
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
                    <Grid item xs={12} sm={6} md={3}>
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
                    <Grid item xs={12} sm={6} md={3}>
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
                    <Grid item xs={12} sm={6} md={3}>
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

                  <Grid container spacing={2}>
                    <Grid item xs={12} md={6}>
                      <Box sx={chartCardSx}>
                        <Typography variant="subtitle1" fontWeight={700} mb={1}>
                          Gained
                        </Typography>
                        <Box height={260}>
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={subscribersSummary.chart}>
                              <CartesianGrid
                                stroke="rgba(148,163,184,0.2)"
                                strokeDasharray="3 3"
                              />
                              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                              <YAxis tickFormatter={formatNumber} />
                              <Tooltip />
                              <Bar dataKey="gained" fill="#22c55e" radius={[6, 6, 0, 0]} />
                            </BarChart>
                          </ResponsiveContainer>
                        </Box>
                      </Box>
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <Box sx={chartCardSx}>
                        <Typography variant="subtitle1" fontWeight={700} mb={1}>
                          Change
                        </Typography>
                        <Box height={260}>
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={subscribersSummary.chart}>
                              <CartesianGrid
                                stroke="rgba(148,163,184,0.2)"
                                strokeDasharray="3 3"
                              />
                              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                              <YAxis tickFormatter={formatNumber} />
                              <Tooltip />
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
          </Grid>
        </Grid>

        <Grid container spacing={2} mt={2}>
          <Grid item xs={12} md={6} lg={4}>
            <Box sx={sectionSx}>
              <Typography variant="subtitle1" fontWeight={700} mb={1}>
                Top 5 keywords by views
              </Typography>
              {topKeywords.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No data
                </Typography>
              ) : (
                <Box display="flex" flexWrap="wrap" gap={1}>
                  {topKeywords.map((k) => (
                    <Chip
                      key={k.keyword}
                      label={`${k.keyword} • ${formatNumber(k.views)}`}
                      size="small"
                    />
                  ))}
                </Box>
              )}
            </Box>
          </Grid>

          <Grid item xs={12} md={6} lg={4}>
            <Box sx={sectionSx}>
              <Typography variant="subtitle1" fontWeight={700} mb={1}>
                Top 5 sources by views
              </Typography>
              {topSources.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No data
                </Typography>
              ) : (
                <Stack spacing={0.8}>
                  {topSources.map((s) => (
                    <Box key={s.source} display="flex" justifyContent="space-between">
                      <Typography variant="body2">{s.source}</Typography>
                      <Typography variant="body2" fontWeight={600}>
                        {formatNumber(s.views)}
                      </Typography>
                    </Box>
                  ))}
                </Stack>
              )}
            </Box>
          </Grid>

          <Grid item xs={12}>
            <Box sx={sectionSx}>
              <Typography variant="subtitle1" fontWeight={700} mb={1}>
                Views by country (last 28 days)
              </Typography>
              {countryViews.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No data
                </Typography>
              ) : (
                <Grid container spacing={1}>
                  {countryViews
                    .sort((a, b) => (b.views || 0) - (a.views || 0))
                    .slice(0, 12)
                    .map((row) => (
                      <Grid item xs={6} md={3} key={row.country}>
                        <Box display="flex" justifyContent="space-between">
                          <Typography variant="body2">{row.country}</Typography>
                          <Typography variant="body2" fontWeight={600}>
                            {formatNumber(row.views)}
                          </Typography>
                        </Box>
                      </Grid>
                    ))}
                </Grid>
              )}
            </Box>
          </Grid>
        </Grid>
        </>
      )}
    </Box>
  );
};

export default VideoList;
