import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  CircularProgress,
  Grid,
  Paper,
  Stack,
  Typography,
  useTheme,
} from "@mui/material";
import TimelineIcon from "@mui/icons-material/Timeline";
import {
  ResponsiveContainer,
  ComposedChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Bar,
} from "recharts";
import api from "../services/api";
import { tokens } from "../theme";
import ChannelSwitcher, { CHANNEL_SWITCHER_SX } from "./ChannelSwitcher";
import { getChannelAvatarMap } from "./Module";
import { sortByStoredTokenOrder } from "../utils/tokenOrder";
import {
  getStoredSharedChannelId,
  listenSharedChannelId,
  resolvePreferredSharedChannelId,
  setStoredSharedChannelId,
} from "../utils/sharedChannel";

const numberFormatter = new Intl.NumberFormat("en-US");

const formatCompact = (value) => {
  if (value == null) return "-";
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  if (Math.abs(num) >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
  if (Math.abs(num) >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
  return numberFormatter.format(Math.round(num));
};

const formatFull = (value) => {
  if (value == null) return "-";
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  return numberFormatter.format(Math.round(num));
};

const toDate = (iso) => {
  if (!iso) return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
};

const formatAxisLabel = (iso, mode) => {
  const date = toDate(iso);
  if (!date) return "";
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  if (mode === "minutes") return `${hh}:${mm}`;
  const dd = String(date.getDate()).padStart(2, "0");
  const mo = String(date.getMonth() + 1).padStart(2, "0");
  return `${dd}/${mo} ${hh}:${mm}`;
};

const formatDateTime = (iso) => {
  const date = toDate(iso);
  if (!date) return "-";
  const dd = String(date.getDate()).padStart(2, "0");
  const mo = String(date.getMonth() + 1).padStart(2, "0");
  const yyyy = date.getFullYear();
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${dd}/${mo}/${yyyy} ${hh}:${mm}`;
};

const buildChartRows = (rows, mode) => {
  let previous = null;
  return (rows || []).map((row, index) => {
    const totalViews = Number(row?.viewCount || 0);
    const deltaViews =
      previous == null ? 0 : Math.max(0, totalViews - previous);
    previous = totalViews;
    return {
      id: `${row?.capturedAt || "row"}-${index}`,
      capturedAt: row?.capturedAt || null,
      label: formatAxisLabel(row?.capturedAt, mode),
      deltaViews,
    };
  });
};

const ChartPanel = ({ title, subtitle, summary, rows, mode, colors, sx }) => {
  const chartRows = useMemo(() => buildChartRows(rows, mode), [rows, mode]);

  return (
    <Box
      sx={{
        p: { xs: 2, md: 2.25 },
        height: "100%",
        ...sx,
      }}
    >
      <Stack spacing={2}>
        <Box>
          <Typography variant="h6" fontWeight={800}>
            {title}
          </Typography>
          {subtitle ? (
            <Typography variant="body2" color="text.secondary">
              {subtitle}
            </Typography>
          ) : null}
        </Box>

        {!summary?.hasData ? (
          <Alert severity="info" sx={{ borderRadius: 2 }}>
            No recent snapshots for this channel yet.
          </Alert>
        ) : null}

        {summary?.hasData && !summary?.hasFullWindow ? (
          <Alert severity="warning" sx={{ borderRadius: 2 }}>
            Not enough history yet to calculate the full {mode === "minutes" ? "60-minute" : "40-hour"} window.
          </Alert>
        ) : null}

        <Box sx={{ height: { xs: 220, md: 250 } }}>
          {chartRows.length === 0 ? (
            <Box
              sx={{
                height: "100%",
                display: "grid",
                placeItems: "center",
                color: "text.secondary",
              }}
            >
              <Typography variant="body2">No chart data available.</Typography>
            </Box>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={chartRows}
                margin={{ top: 6, right: 8, left: -8, bottom: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
                <XAxis
                  dataKey="label"
                  minTickGap={mode === "minutes" ? 14 : 26}
                  tick={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: colors.axisText }}
                  tickFormatter={formatCompact}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: colors.tooltipBg,
                    border: `1px solid ${colors.tooltipBorder}`,
                    borderRadius: 10,
                    boxShadow: colors.shadow,
                  }}
                  formatter={(value, name) => [
                    formatFull(value),
                    name === "deltaViews" ? "Added views" : name,
                  ]}
                  labelFormatter={(_, payload) =>
                    payload?.[0]?.payload?.capturedAt
                      ? formatDateTime(payload[0].payload.capturedAt)
                      : ""
                  }
                />
                <Bar
                  dataKey="deltaViews"
                  name="Added views"
                  fill={colors.bar}
                  radius={[6, 6, 0, 0]}
                  maxBarSize={mode === "minutes" ? 24 : 18}
                />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </Box>
      </Stack>
    </Box>
  );
};

const LiveViews = () => {
  const theme = useTheme();
  const palette = tokens(theme.palette.mode);

  const chartColors = useMemo(
    () => ({
      panelBg:
        theme.palette.mode === "dark"
          ? "linear-gradient(180deg, rgba(15,23,42,0.92) 0%, rgba(30,41,59,0.88) 100%)"
          : "linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(248,250,252,0.98) 100%)",
      cardFrom:
        theme.palette.mode === "dark"
          ? "rgba(15,23,42,0.72)"
          : "rgba(255,255,255,0.96)",
      cardTo:
        theme.palette.mode === "dark"
          ? "rgba(30,41,59,0.84)"
          : "rgba(239,246,255,0.92)",
      bar: theme.palette.mode === "dark" ? "#38bdf8" : "#0284c7",
      line: theme.palette.mode === "dark" ? "#f59e0b" : "#ea580c",
      grid: theme.palette.mode === "dark" ? "rgba(148,163,184,0.18)" : "rgba(15,23,42,0.08)",
      axisText: theme.palette.mode === "dark" ? "#cbd5e1" : "#334155",
      tooltipBg: theme.palette.mode === "dark" ? "rgba(15,23,42,0.96)" : "#ffffff",
      tooltipBorder:
        theme.palette.mode === "dark" ? "rgba(148,163,184,0.24)" : "rgba(15,23,42,0.1)",
      shadow:
        theme.palette.mode === "dark"
          ? "0 18px 40px rgba(2,6,23,0.34)"
          : "0 16px 36px rgba(148,163,184,0.24)",
    }),
    [theme.palette.mode]
  );

  const [channels, setChannels] = useState([]);
  const [channelAvatarMap, setChannelAvatarMap] = useState({});
  const [selectedChannel, setSelectedChannel] = useState(() => {
    try {
      return getStoredSharedChannelId("liveViews.selectedChannelId", "overview.selectedChannelId");
    } catch {
      return "";
    }
  });
  const [loadingChannels, setLoadingChannels] = useState(true);
  const [loadingData, setLoadingData] = useState(false);
  const [error, setError] = useState("");
  const [liveData, setLiveData] = useState({
    summary40h: null,
    history40h: [],
    summary60m: null,
    history60m: [],
  });

  useEffect(() => {
    let active = true;
    const fetchChannels = async () => {
      try {
        setLoadingChannels(true);
        const res = await api.get("/api/video_overview/channels");
        const items = Array.isArray(res?.data?.items) ? res.data.items : [];
        const finalChannels = sortByStoredTokenOrder(items, (item) => item.value);
        if (!active) return;
        setChannels(finalChannels);
        setSelectedChannel((current) => {
          const preferred =
            getStoredSharedChannelId("liveViews.selectedChannelId", "overview.selectedChannelId") ||
            current;
          return resolvePreferredSharedChannelId(
            preferred,
            finalChannels,
            (item) => item.value
          );
        });
      } catch (err) {
        if (!active) return;
        setChannels([]);
        setError("Khong load duoc danh sach kenh.");
      } finally {
        if (active) setLoadingChannels(false);
      }
    };

    fetchChannels();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    setStoredSharedChannelId(selectedChannel, "liveViews.selectedChannelId", "overview.selectedChannelId");
  }, [selectedChannel]);

  useEffect(() => {
    return listenSharedChannelId((nextChannelId) => {
      setSelectedChannel((current) => {
        if (!nextChannelId || nextChannelId === current) return current;
        return nextChannelId;
      });
    });
  }, []);

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
    if (!selectedChannel) {
      setLiveData({
        summary40h: null,
        history40h: [],
        summary60m: null,
        history60m: [],
      });
      return;
    }

    let active = true;
    setLoadingData(true);
    setError("");

    const fetchData = async () => {
      try {
        const encoded = encodeURIComponent(selectedChannel);
        const [summary40hResp, history40hResp, summary60mResp, history60mResp] =
          await Promise.all([
            api.get(`/api/video_overview/live_counters/summary?accountTag=${encoded}&hours=40`),
            api.get(`/api/video_overview/live_counters/history?accountTag=${encoded}&hours=40`),
            api.get(`/api/video_overview/live_counters/summary?accountTag=${encoded}&minutes=60`),
            api.get(`/api/video_overview/live_counters/history?accountTag=${encoded}&minutes=60`),
          ]);

        if (!active) return;

        setLiveData({
          summary40h: summary40hResp?.data || null,
          history40h: Array.isArray(history40hResp?.data?.rows) ? history40hResp.data.rows : [],
          summary60m: summary60mResp?.data || null,
          history60m: Array.isArray(history60mResp?.data?.rows) ? history60mResp.data.rows : [],
        });
      } catch (err) {
        if (!active) return;
        setLiveData({
          summary40h: null,
          history40h: [],
          summary60m: null,
          history60m: [],
        });
        setError("Khong load duoc du lieu live views.");
      } finally {
        if (active) setLoadingData(false);
      }
    };

    fetchData();

    return () => {
      active = false;
    };
  }, [selectedChannel]);

  return (
    <Box>
      <Paper
        elevation={0}
        sx={{
          p: 2.2,
          mb: 3,
          borderRadius: 3,
          border: "1px solid",
          borderColor: "divider",
          background:
            theme.palette.mode === "dark"
              ? "linear-gradient(135deg, rgba(15,23,42,0.96) 0%, rgba(30,41,59,0.9) 58%, rgba(8,145,178,0.24) 100%)"
              : "linear-gradient(135deg, rgba(255,255,255,0.96) 0%, rgba(239,246,255,0.92) 58%, rgba(186,230,253,0.9) 100%)",
          boxShadow: chartColors.shadow,
        }}
      >
        <Stack
          direction={{ xs: "column", lg: "row" }}
          spacing={2}
          alignItems={{ xs: "stretch", lg: "center" }}
          justifyContent="space-between"
        >
          <Stack spacing={1}>
            <Stack direction="row" spacing={1.2} alignItems="center">
              <TimelineIcon sx={{ color: palette.greenAccent[400] }} />
              <Typography variant="h5" fontWeight={800}>
                Live Views
              </Typography>
            </Stack>
          </Stack>

          <ChannelSwitcher
            options={channels}
            value={selectedChannel}
            onChange={(option) => setSelectedChannel(option?.value || "")}
            sx={CHANNEL_SWITCHER_SX}
            disabled={loadingChannels}
            placeholder={loadingChannels ? "Loading channels..." : "Search by channel name"}
            noOptionsText={loadingChannels ? "Loading channels..." : "No channels found"}
            getOptionAvatar={(option) => channelAvatarMap[option?.value] || option?.avatar || ""}
          />
        </Stack>
      </Paper>

      {error ? (
        <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }}>
          {error}
        </Alert>
      ) : null}

      {loadingData && !liveData.summary40h && !liveData.summary60m ? (
        <Box
          sx={{
            minHeight: 280,
            display: "grid",
            placeItems: "center",
          }}
        >
          <CircularProgress />
        </Box>
      ) : (
        <Paper
          elevation={0}
          sx={{
            borderRadius: 3,
            border: "1px solid",
            borderColor: "divider",
            background: chartColors.panelBg,
            boxShadow: chartColors.shadow,
            overflow: "hidden",
          }}
        >
          <Grid container>
            <Grid size={{ xs: 12, lg: 6 }}>
              <ChartPanel
                title="last 40 hours"
                subtitle=""
                summary={liveData.summary40h}
                rows={liveData.history40h}
                mode="hours"
                colors={chartColors}
                sx={{
                  borderBottom: { xs: "1px solid", lg: "none" },
                  borderRight: { xs: "none", lg: "1px solid" },
                  borderColor: "divider",
                }}
              />
            </Grid>
            <Grid size={{ xs: 12, lg: 6 }}>
              <ChartPanel
                title="last 60 minutes"
                subtitle=""
                summary={liveData.summary60m}
                rows={liveData.history60m}
                mode="minutes"
                colors={chartColors}
              />
            </Grid>
          </Grid>
        </Paper>
      )}
    </Box>
  );
};

export default LiveViews;
