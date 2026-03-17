import { useEffect, useMemo, useState } from "react";
import {
  Box,
  Button,
  CircularProgress,
  Grid,
  Typography,
  useTheme,
} from "@mui/material";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import ChannelSwitcher, { CHANNEL_SWITCHER_SX } from "./ChannelSwitcher";
import api from "../services/api";
import { getChannelAvatarMap } from "./Module";

const sectionSx = (theme) => ({
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
  p: 2.5,
});

const statCardSx = (theme) => ({
  borderRadius: 2,
  p: 2.5,
  textAlign: "left",
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
});

const formatNumber = (n) => {
  if (n == null) return "-";
  const num = Number(n);
  if (Number.isNaN(num)) return "-";
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
  return `${num}`;
};

const formatFullNumber = (n) => {
  if (n == null) return "-";
  const num = Number(n);
  if (Number.isNaN(num)) return "-";
  return num.toLocaleString();
};

const formatDate = (iso) => {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const day = String(d.getDate()).padStart(2, "0");
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const year = d.getFullYear().toString();
  return `${day}-${month}-${year}`;
};

const formatTimestamp = (iso) => {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString([], {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const formatTimeTick = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

const LIVE_COUNTERS_POLL_INTERVAL_MS = 5 * 60 * 1000;

const LiveCounters = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const [channels, setChannels] = useState([]);
  const [selectedChannel, setSelectedChannel] = useState(() => {
    try {
      return localStorage.getItem("liveCounters.selectedChannelId") || "";
    } catch {
      return "";
    }
  });
  const [channelAvatarMap, setChannelAvatarMap] = useState({});
  const [liveCounters, setLiveCounters] = useState(null);
  const [history24Rows, setHistory24Rows] = useState([]);
  const [history60Rows, setHistory60Rows] = useState([]);
  const [historyMetric, setHistoryMetric] = useState("views");
  const [loadingChannels, setLoadingChannels] = useState(true);
  const [loadingLiveCounters, setLoadingLiveCounters] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchChannels = async () => {
      try {
        setLoadingChannels(true);
        const res = await api.get("/api/video_overview/channels");
        const items = res.data?.items || [];
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
        const ordered = order.map((name) => byId.get(orderKey(name))).filter(Boolean);
        const remaining = items.filter(
          (c) => !order.map(orderKey).includes(orderKey(c.value))
        );
        const finalChannels = [...ordered, ...remaining];
        setChannels(finalChannels);
        if (finalChannels.length > 0) {
          const exists = selectedChannel && finalChannels.some((c) => c.value === selectedChannel);
          if (!exists) {
            setSelectedChannel(finalChannels[0].value);
          }
        }
      } catch {
        setChannels([]);
        setError("Khong load duoc danh sach kenh.");
      } finally {
        setLoadingChannels(false);
      }
    };

    fetchChannels();
  }, [selectedChannel]);

  useEffect(() => {
    try {
      localStorage.setItem("liveCounters.selectedChannelId", selectedChannel);
    } catch {
      // ignore storage errors
    }
  }, [selectedChannel]);

  useEffect(() => {
    let active = true;
    getChannelAvatarMap().then((map) => {
      if (active) {
        setChannelAvatarMap(map || {});
      }
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedChannel) return;
    let cancelled = false;

    const fetchLiveCounters = async (silent = false) => {
      if (!silent) {
        setLoadingLiveCounters(true);
      }
      try {
        const [counterRes, history24Res, history60Res] = await Promise.all([
          api.get(
            `/api/video_overview/live_counters?accountTag=${encodeURIComponent(
              selectedChannel
            )}&limit=3`
          ),
          api.get(
            `/api/video_overview/live_counters/history?accountTag=${encodeURIComponent(
              selectedChannel
            )}&hours=24`
          ),
          api.get(
            `/api/video_overview/live_counters/history?accountTag=${encodeURIComponent(
              selectedChannel
            )}&hours=1`
          ),
        ]);
        if (!cancelled) {
          setLiveCounters(counterRes.data || null);
          setHistory24Rows(Array.isArray(history24Res.data?.rows) ? history24Res.data.rows : []);
          setHistory60Rows(Array.isArray(history60Res.data?.rows) ? history60Res.data.rows : []);
          setError("");
        }
      } catch {
        if (!cancelled) {
          setLiveCounters(null);
          setHistory24Rows([]);
          setHistory60Rows([]);
          setError("Khong load duoc live counters.");
        }
      } finally {
        if (!cancelled && !silent) {
          setLoadingLiveCounters(false);
        }
      }
    };

    fetchLiveCounters();
    const intervalId = setInterval(() => {
      fetchLiveCounters(true);
    }, LIVE_COUNTERS_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [selectedChannel]);

  const buildDeltaRows = (rows) =>
    rows.map((row, index) => {
      const prev = index > 0 ? rows[index - 1] : null;
      const currentViews = Number(row?.viewCount || 0);
      const previousViews = Number(prev?.viewCount || 0);
      const currentSubscribers = Number(row?.subscriberCount || 0);
      const previousSubscribers = Number(prev?.subscriberCount || 0);
      return {
        ...row,
        viewDelta: prev ? Math.max(0, currentViews - previousViews) : 0,
        subscriberDelta: prev ? currentSubscribers - previousSubscribers : 0,
      };
    });

  const history24DeltaRows = useMemo(
    () => buildDeltaRows(history24Rows),
    [history24Rows]
  );
  const history60DeltaRows = useMemo(
    () => buildDeltaRows(history60Rows),
    [history60Rows]
  );

  const renderHistoryChart = (title, rows, emptyText) => (
    <Box
      sx={{
        height: 280,
        borderRadius: 2,
        border: "1px solid",
        borderColor: isDark
          ? "rgba(148,163,184,0.16)"
          : "rgba(15,23,42,0.08)",
        background: isDark
          ? "rgba(15,23,42,0.45)"
          : "rgba(255,255,255,0.72)",
        p: 1.25,
      }}
    >
      <Typography variant="subtitle1" fontWeight={700} mb={1}>
        {title}
      </Typography>
      {!rows.length ? (
        <Box
          sx={{
            height: "calc(100% - 32px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Typography variant="body2" color="text.secondary">
            {emptyText}
          </Typography>
        </Box>
      ) : (
        <ResponsiveContainer width="100%" height="88%">
          <LineChart data={rows} margin={{ top: 16, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid
              stroke={isDark ? "rgba(148,163,184,0.16)" : "rgba(15,23,42,0.08)"}
              vertical={false}
            />
            <XAxis
              dataKey="capturedAt"
              tickFormatter={formatTimeTick}
              minTickGap={32}
              stroke={isDark ? "#94a3b8" : "#64748b"}
            />
            <YAxis
              tickFormatter={formatNumber}
              stroke={isDark ? "#94a3b8" : "#64748b"}
            />
            <Tooltip
              labelFormatter={(value) => formatTimestamp(value)}
              formatter={(value) => formatNumber(value)}
              contentStyle={{
                backgroundColor: isDark ? "rgba(15,23,42,0.92)" : "#ffffff",
                border: isDark
                  ? "1px solid rgba(148,163,184,0.35)"
                  : "1px solid rgba(15,23,42,0.12)",
                borderRadius: 8,
              }}
            />
            <Line
              type="monotone"
              dataKey={historyMetric === "views" ? "viewDelta" : "subscriberDelta"}
              name={historyMetric === "views" ? "View" : "Subcribe"}
              stroke={historyMetric === "views" ? "#38bdf8" : "#22c55e"}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Box>
  );

  return (
    <Box>
      <Box
        mb={2}
        display="flex"
        alignItems="center"
        justifyContent="space-between"
        flexWrap="wrap"
        gap={2}
      >
        {loadingChannels ? (
          <CircularProgress size={20} />
        ) : (
          <ChannelSwitcher
            options={channels}
            value={selectedChannel}
            onChange={(option) => setSelectedChannel(option?.value || "")}
            sx={CHANNEL_SWITCHER_SX}
            recentStorageKey="liveCounters.recentChannels"
            getOptionAvatar={(option) => channelAvatarMap[option?.value] || ""}
          />
        )}
      </Box>

      {error && (
        <Typography color="error" mb={2}>
          {error}
        </Typography>
      )}

      {!liveCounters?.channel ? (
        <Box sx={sectionSx(theme)}>
          <Typography variant="body2" color="text.secondary">
            {loadingLiveCounters ? "Loading live counters..." : "Live counters unavailable."}
          </Typography>
        </Box>
      ) : (
        <Box sx={sectionSx(theme)}>
          <Box sx={statCardSx(theme)}>
            <Box display="flex" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1} mb={2}>
              <Typography variant="subtitle1" fontWeight={700}>
                Metric
              </Typography>
              <Box display="flex" gap={1}>
                <Button
                  size="small"
                  variant={historyMetric === "views" ? "contained" : "outlined"}
                  onClick={() => setHistoryMetric("views")}
                  sx={{
                    ...(historyMetric === "views"
                      ? {
                          bgcolor: isDark ? "#38bdf8" : undefined,
                          color: isDark ? "#082f49" : undefined,
                          "&:hover": {
                            bgcolor: isDark ? "#22aee6" : undefined,
                          },
                        }
                      : {
                          borderColor: isDark ? "rgba(148,163,184,0.45)" : undefined,
                          color: isDark ? "#e2e8f0" : undefined,
                          bgcolor: isDark ? "rgba(15,23,42,0.35)" : undefined,
                          "&:hover": {
                            borderColor: isDark ? "rgba(56,189,248,0.65)" : undefined,
                            bgcolor: isDark ? "rgba(30,41,59,0.82)" : undefined,
                          },
                        }),
                  }}
                >
                  View
                </Button>
                <Button
                  size="small"
                  variant={historyMetric === "subscribers" ? "contained" : "outlined"}
                  onClick={() => setHistoryMetric("subscribers")}
                  sx={{
                    ...(historyMetric === "subscribers"
                      ? {
                          bgcolor: isDark ? "#22c55e" : undefined,
                          color: isDark ? "#052e16" : undefined,
                          "&:hover": {
                            bgcolor: isDark ? "#16a34a" : undefined,
                          },
                        }
                      : {
                          borderColor: isDark ? "rgba(148,163,184,0.45)" : undefined,
                          color: isDark ? "#e2e8f0" : undefined,
                          bgcolor: isDark ? "rgba(15,23,42,0.35)" : undefined,
                          "&:hover": {
                            borderColor: isDark ? "rgba(34,197,94,0.65)" : undefined,
                            bgcolor: isDark ? "rgba(30,41,59,0.82)" : undefined,
                          },
                        }),
                  }}
                >
                  Subcribe
                </Button>
              </Box>
            </Box>
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr", xl: "1fr 1fr" },
                gap: 1.5,
                mb: 2,
              }}
            >
              {renderHistoryChart("Last 24 hours", history24DeltaRows, "Waiting for 24h snapshots...")}
              {renderHistoryChart("Last 60 minutes", history60DeltaRows, "Waiting for 60-minute snapshots...")}
            </Box>

            <Box
              sx={{
                display: "flex",
                flexDirection: "column",
                gap: 2,
                mb: 2,
              }}
            >
              <Grid container spacing={1.5}>
                <Grid size={{ xs: 4 }}>
                  <Typography variant="caption" color="text.secondary">
                    Subscribers
                  </Typography>
                  <Typography variant="h6" fontWeight={700}>
                    {formatNumber(liveCounters.channel.subscriberCount)}
                  </Typography>
                </Grid>
                <Grid size={{ xs: 4 }}>
                  <Typography variant="caption" color="text.secondary">
                    Views
                  </Typography>
                  <Typography variant="h6" fontWeight={700}>
                    {formatNumber(liveCounters.channel.viewCount)}
                  </Typography>
                </Grid>
                <Grid size={{ xs: 4 }}>
                  <Typography variant="caption" color="text.secondary">
                    Videos
                  </Typography>
                  <Typography variant="h6" fontWeight={700}>
                    {formatNumber(liveCounters.channel.videoCount)}
                  </Typography>
                </Grid>
              </Grid>
            </Box>

            <Box
              sx={{
                display: "flex",
                flexDirection: "column",
                gap: 1,
              }}
            >
              {(liveCounters.videos || []).map((video) => (
                <Box
                  key={video.videoId}
                  sx={{
                    borderRadius: 2,
                    border: "1px solid",
                    borderColor: isDark
                      ? "rgba(148,163,184,0.16)"
                      : "rgba(15,23,42,0.08)",
                    background: isDark
                      ? "rgba(15,23,42,0.5)"
                      : "rgba(255,255,255,0.72)",
                    p: 1.25,
                    display: "grid",
                    gridTemplateColumns: { xs: "72px 1fr", md: "96px minmax(0, 1.8fr) repeat(3, minmax(0, 0.7fr))" },
                    gap: 1.25,
                    alignItems: "center",
                  }}
                >
                  <Box
                    component="img"
                    src={video.thumbnail || ""}
                    alt={video.title}
                    sx={{
                      width: { xs: 72, md: 96 },
                      height: { xs: 40, md: 54 },
                      objectFit: "cover",
                      borderRadius: 1.5,
                      bgcolor: "rgba(148,163,184,0.2)",
                    }}
                  />
                  <Box minWidth={0}>
                    <Typography variant="body2" fontWeight={700} noWrap>
                      {video.title}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDate(video.publishedAt)}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Views
                    </Typography>
                    <Typography variant="body2" fontWeight={700}>
                      {formatFullNumber(video.viewCount)}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Likes
                    </Typography>
                    <Typography variant="body2" fontWeight={700}>
                      {formatFullNumber(video.likeCount)}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Comments
                    </Typography>
                    <Typography variant="body2" fontWeight={700}>
                      {formatFullNumber(video.commentCount)}
                    </Typography>
                  </Box>
                </Box>
              ))}
            </Box>

            {!(liveCounters.videos || []).length && (
              <Typography variant="body2" color="text.secondary" mt={1.5}>
                No recent videos available for live counters.
              </Typography>
            )}
          </Box>
        </Box>
      )}
    </Box>
  );
};

export default LiveCounters;
