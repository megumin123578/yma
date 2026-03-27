import { useEffect, useMemo, useState } from "react";
import {
  Box,
  Stack,
  Typography,
  Paper,
  Divider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid,
  Tooltip as MuiTooltip,
} from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import dayjs from "dayjs";
import api from "../services/api";
import { tokens } from "../theme";
import { getChannelAvatarMap, getChannelRevenueMap } from "./Module";
import ChannelSwitcher, { CHANNEL_SWITCHER_SX } from "./ChannelSwitcher";
import {
  getStoredSharedChannelId,
  listenSharedChannelId,
  resolvePreferredSharedChannelId,
  setStoredSharedChannelId,
} from "../utils/sharedChannel";
import { sortByStoredTokenOrder } from "../utils/tokenOrder";

const RANGE_OPTIONS = [
  { value: "7d", label: "Last 7 days" },
  { value: "28d", label: "Last 28 days" },
  { value: "90d", label: "Last 90 days" },
  { value: "365d", label: "Last 365 days" },
  { value: "lifetime", label: "Lifetime" },
];

const formatNumber = (value) => {
  if (value == null) return "-";
  const num = Number(value);
  if (Number.isNaN(num)) return "-";
  if (Math.abs(num) >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
  if (Math.abs(num) >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
  return num.toString();
};

const formatCurrency = (value) => {
  if (value == null) return "-";
  const num = Number(value);
  if (Number.isNaN(num)) return "-";
  return `$${num.toFixed(2)}`;
};

const MiniMetricCard = ({ label, value, accent, helper, isCurrency = true }) => (
  <Box
    sx={{
      p: 1.6,
      borderRadius: 2.5,
      background: `linear-gradient(135deg, ${alpha(accent, 0.18)} 0%, ${alpha(
        accent,
        0.06
      )} 100%)`,
      border: `1px solid ${alpha(accent, 0.22)}`,
      minHeight: 92,
    }}
  >
    <Stack direction="row" spacing={0.75} alignItems="center">
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
      {helper ? (
        <MuiTooltip title={helper} arrow placement="top">
          <InfoOutlinedIcon
            sx={{
              fontSize: 15,
              color: "text.secondary",
              cursor: "help",
              opacity: 0.75,
            }}
          />
        </MuiTooltip>
      ) : null}
    </Stack>
    <Typography variant="h6" fontWeight={800} mt={0.8}>
      {isCurrency ? formatCurrency(value) : formatNumber(value)}
    </Typography>
  </Box>
);

const MetricRow = ({ label, value, accent, isCurrency = true }) => (
  <Box
    sx={{
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 2,
      py: 1.1,
    }}
  >
    <Stack direction="row" spacing={1.2} alignItems="center">
      <Box
        sx={{
          width: 10,
          height: 10,
          borderRadius: "50%",
          backgroundColor: accent,
          boxShadow: `0 0 0 5px ${alpha(accent, 0.16)}`,
        }}
      />
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
    </Stack>
    <Typography variant="subtitle1" fontWeight={700}>
      {isCurrency ? formatCurrency(value) : formatNumber(value)}
    </Typography>
  </Box>
);

const RevenueAnalytics = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);

  const [channels, setChannels] = useState([]);
  const [channelAvatarMap, setChannelAvatarMap] = useState({});
  const [channelRevenueMap, setChannelRevenueMap] = useState({});
  const [channel, setChannel] = useState(() =>
    getStoredSharedChannelId("revenue.selectedChannelId")
  );
  const [range, setRange] = useState("28d");
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let stop = false;
    (async () => {
      try {
        const res = await api.get("/api/revenue/channels", {
          params: { range },
        });
        const data = res.data;
        const items = (data?.items || [])
          .map((item) => {
            if (typeof item === "string") return { value: item, label: item };
            const value = item?.value || item?.name || "";
            return {
              value,
              label: item?.label || item?.name || value,
            };
          })
          .filter((item) => item.value);
        const finalChannels = sortByStoredTokenOrder(items, (item) => item.value);
        if (!stop) {
          setChannels(finalChannels);
          const preferredChannel =
            getStoredSharedChannelId("revenue.selectedChannelId") || channel;
          const nextChannel = resolvePreferredSharedChannelId(
            preferredChannel,
            finalChannels,
            (item) => item.value
          );
          if (nextChannel !== channel) {
            setChannel(nextChannel);
          }
        }
      } catch (err) {
        console.error(err);
        if (!stop) {
          setChannels([]);
          setChannel("");
        }
      }
    })();
    return () => {
      stop = true;
    };
  }, [channel, range]);

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
    setStoredSharedChannelId(channel, "revenue.selectedChannelId");
  }, [channel]);

  useEffect(() => {
    return listenSharedChannelId((nextChannelId) => {
      setChannel((current) => {
        if (!nextChannelId || nextChannelId === current) return current;
        return nextChannelId;
      });
    });
  }, []);

  useEffect(() => {
    let active = true;
    getChannelRevenueMap(range).then((map) => {
      if (active) setChannelRevenueMap(map || {});
    });
    return () => {
      active = false;
    };
  }, [range]);

  useEffect(() => {
    if (!channel) {
      setRows([]);
      return;
    }
    let stop = false;
    (async () => {
      try {
        setError("");
        const res = await api.get(
          `/api/revenue?accountTag=${encodeURIComponent(
            channel
          )}&range=${range}`
        );
        const data = res.data;
        const list = Array.isArray(data?.rows) ? data.rows : [];
        if (!stop) {
          setRows(list);
        }
      } catch (err) {
        console.error(err);
        if (!stop) {
          setRows([]);
          setError("Failed to load revenue data.");
        }
      }
    })();
    return () => {
      stop = true;
    };
  }, [channel, range]);

  const chartData = useMemo(() => {
    return rows.map((row) => ({
      day: row.day,
      estimated: Number(row.estimated_revenue || 0),
      ad: Number(row.ad_revenue || 0),
      gross: Number(row.gross_revenue || 0),
      premium: Number(row.estimated_red_partner_revenue || 0),
      rpm: row.rpm != null ? Number(row.rpm) : null,
      cpm: row.cpm != null ? Number(row.cpm) : null,
      playbackCpm: row.playback_cpm != null ? Number(row.playback_cpm) : null,
      monetized: Number(row.monetized_playbacks || 0),
      adImpressions: Number(row.ad_impressions || 0),
      views: Number(row.views || 0),
    }));
  }, [rows]);

  const totals = useMemo(() => {
    const base = {
      estimated: 0,
      ad: 0,
      gross: 0,
      premium: 0,
      monetized: 0,
      adImpressions: 0,
      views: 0,
      rpm: [],
      cpm: [],
      playbackCpm: [],
    };
    for (const row of chartData) {
      base.estimated += row.estimated;
      base.ad += row.ad;
      base.gross += row.gross;
      base.premium += row.premium;
      base.monetized += row.monetized;
      base.adImpressions += row.adImpressions;
      base.views += row.views;
      if (row.rpm != null) base.rpm.push(row.rpm);
      if (row.cpm != null) base.cpm.push(row.cpm);
      if (row.playbackCpm != null) base.playbackCpm.push(row.playbackCpm);
    }
    const avg = (arr) =>
      arr.length ? arr.reduce((acc, v) => acc + v, 0) / arr.length : null;
    return {
      estimated: base.estimated,
      ad: base.ad,
      gross: base.gross,
      premium: base.premium,
      monetized: base.monetized,
      adImpressions: base.adImpressions,
      rpm: base.views > 0 ? (base.estimated * 1000) / base.views : avg(base.rpm),
      cpm:
        base.adImpressions > 0
          ? (base.gross * 1000) / base.adImpressions
          : avg(base.cpm),
      playbackCpm:
        base.monetized > 0
          ? (base.gross * 1000) / base.monetized
          : avg(base.playbackCpm),
    };
  }, [chartData]);

  const chartTooltip = useMemo(() => {
    const isDark = theme.palette.mode === "dark";
    return {
      contentStyle: {
        backgroundColor: isDark ? "rgba(15,23,42,0.92)" : "#ffffff",
        border: isDark
          ? "1px solid rgba(148,163,184,0.35)"
          : "1px solid rgba(15,23,42,0.12)",
        borderRadius: 8,
      },
      labelStyle: { color: isDark ? "#e2e8f0" : "#0f172a" },
      formatter: (value, name) => {
        if (name === "Monetized Playbacks") return [formatNumber(value), name];
        if (name === "RPM" || name === "CPM" || name === "Playback CPM") {
          return [formatCurrency(value), name];
        }
        return [formatCurrency(value), name];
      },
      labelFormatter: (label) => dayjs(label).format("DD/MM/YYYY"),
    };
  }, [theme.palette.mode]);

  const revenueCards = [
    {
      label: "Estimated Revenue",
      value: totals.estimated,
      accent: "#22c55e",
      helper: "Primary revenue estimate",
    },
    {
      label: "Ad Revenue",
      value: totals.ad,
      accent: "#38bdf8",
      helper: "Direct ad earnings",
    },
    {
      label: "Gross Revenue",
      value: totals.gross,
      accent: "#a855f7",
      helper: "Before deductions",
    },
    {
      label: "Premium Revenue",
      value: totals.premium,
      accent: "#f59e0b",
      helper: "YouTube Premium share",
    },
    {
      label: "Monetized Playbacks",
      value: totals.monetized,
      accent: "#14b8a6",
      helper: "Eligible revenue-generating plays",
      isCurrency: false,
    },
    {
      label: "Ad Impressions",
      value: totals.adImpressions,
      accent: "#6366f1",
      helper: "Served ad count",
      isCurrency: false,
    },
  ];

  const efficiencyMetrics = [
    { label: "RPM", value: totals.rpm, accent: "#22c55e" },
    { label: "CPM", value: totals.cpm, accent: "#38bdf8" },
    { label: "Playback CPM", value: totals.playbackCpm, accent: "#f59e0b" },
  ];

  const cardSx = {
    borderRadius: 2,
    border: "1px solid",
    borderColor:
      theme.palette.mode === "dark"
        ? "rgba(148,163,184,0.2)"
        : "rgba(15,23,42,0.12)",
    background:
      theme.palette.mode === "dark"
        ? "rgba(15,23,42,0.7)"
        : "rgba(248,250,252,0.9)",
    p: 2,
  };

  const heroCardSx = {
    ...cardSx,
    p: { xs: 2.2, md: 2.6 },
    borderRadius: 3,
    background:
      theme.palette.mode === "dark"
        ? "linear-gradient(135deg, rgba(15,23,42,0.96) 0%, rgba(30,41,59,0.92) 55%, rgba(34,197,94,0.22) 100%)"
        : "linear-gradient(135deg, rgba(255,255,255,0.98) 0%, rgba(240,253,244,0.96) 52%, rgba(219,234,254,0.94) 100%)",
    boxShadow:
      theme.palette.mode === "dark"
        ? "0 18px 38px rgba(2,6,23,0.32)"
        : "0 18px 34px rgba(148,163,184,0.24)",
  };

  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
        <ChannelSwitcher
          options={channels}
          value={channel}
          onChange={(option) => setChannel(option?.value || "")}
          sx={CHANNEL_SWITCHER_SX}
          getOptionAvatar={(option) => channelAvatarMap[option?.value] || ""}
          getOptionMeta={(option) => channelRevenueMap[option?.value] || ""}
        />
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Range</InputLabel>
          <Select
            value={range}
            label="Range"
            onChange={(event) => setRange(event.target.value)}
          >
            {RANGE_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Stack>

      {error && (
        <Typography color="error" fontSize={14}>
          {error}
        </Typography>
      )}

      <Paper elevation={0} sx={heroCardSx}>
        <Stack spacing={2.4}>
          <Grid container spacing={1.5}>
            {revenueCards.map((item) => (
              <Grid key={item.label} size={{ xs: 12, sm: 6, md: 4, lg: 2 }}>
                <MiniMetricCard
                  label={item.label}
                  value={item.value}
                  accent={item.accent}
                  helper={item.helper}
                  isCurrency={item.isCurrency}
                />
              </Grid>
            ))}
          </Grid>

          <Grid container spacing={2.5}>
            <Grid size={{ xs: 12 }}>
              <Stack divider={<Divider flexItem sx={{ borderColor: "divider" }} />}>
                {efficiencyMetrics.map((item) => (
                  <MetricRow
                    key={item.label}
                    label={item.label}
                    value={item.value}
                    accent={item.accent}
                  />
                ))}
              </Stack>
            </Grid>
          </Grid>
        </Stack>
      </Paper>

      <Paper elevation={0} sx={{ ...cardSx, p: 2 }}>
        <Typography variant="subtitle1" fontWeight={700} mb={2}>
          Revenue over time
        </Typography>
        <Box sx={{ height: 340, minHeight: 240 }}>
          {chartData.length === 0 ? (
            <Box
              sx={{
                height: "100%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: colors.grey[300],
              }}
            >
              No data
            </Box>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="rgba(148,163,184,0.2)" strokeDasharray="3 3" />
                <XAxis
                  dataKey="day"
                  tick={{ fontSize: 11 }}
                  tickFormatter={(value) => dayjs(value).format("DD-MM")}
                />
                <YAxis tickFormatter={formatCurrency} />
                <Tooltip {...chartTooltip} />
                <Line
                  type="monotone"
                  dataKey="estimated"
                  name="Estimated Revenue"
                  stroke="#22c55e"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="ad"
                  name="Ad Revenue"
                  stroke="#38bdf8"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="gross"
                  name="Gross Revenue"
                  stroke="#a855f7"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="premium"
                  name="Premium Revenue"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Box>
      </Paper>
    </Stack>
  );
};

export default RevenueAnalytics;
