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
import { formatNumber, getChannelAvatarMap, getChannelRevenueMap } from "./Module";
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

const formatCurrency = (value) => {
  if (value == null) return "-";
  const num = Number(value);
  if (Number.isNaN(num)) return "-";
  return `$${num.toFixed(2)}`;
};

const RevenueTooltip = ({ title, children }) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  if (!title) return children;

  return (
    <MuiTooltip
      title={
        <Box
          sx={{
            fontSize: 13.5,
            lineHeight: 1.6,
            letterSpacing: 0.1,
          }}
        >
          {title}
        </Box>
      }
      arrow
      placement="top"
      enterDelay={120}
      slotProps={{
        tooltip: {
          sx: {
            maxWidth: 420,
            px: 1.5,
            py: 1.25,
            borderRadius: 2,
            backgroundColor: isDark ? "rgba(15,23,42,0.98)" : "rgba(255,255,255,0.98)",
            color: isDark ? "#e2e8f0" : "#0f172a",
            border: `1px solid ${
              isDark ? "rgba(148,163,184,0.28)" : "rgba(15,23,42,0.12)"
            }`,
            boxShadow: isDark
              ? "0 18px 34px rgba(2,6,23,0.42)"
              : "0 18px 34px rgba(15,23,42,0.14)",
          },
        },
        arrow: {
          sx: {
            color: isDark ? "rgba(15,23,42,0.98)" : "rgba(255,255,255,0.98)",
          },
        },
      }}
    >
      {children}
    </MuiTooltip>
  );
};

const MiniMetricCard = ({ label, value, accent, helper, isCurrency = true }) => {
  const cardContent = (
    <Box
      sx={{
        p: 1.35,
        borderRadius: 2.5,
        backgroundColor: alpha(accent, 0.1),
        border: `1px solid ${alpha(accent, 0.22)}`,
        minHeight: 84,
        cursor: helper ? "help" : "default",
        transition:
          "transform 180ms ease, box-shadow 180ms ease, background-color 180ms ease, border-color 180ms ease",
        "&:hover": {
          transform: "translateY(-3px)",
          boxShadow: `0 14px 26px ${alpha(accent, 0.16)}`,
          backgroundColor: alpha(accent, 0.14),
          borderColor: alpha(accent, 0.34),
        },
      }}
    >
      <Stack direction="row" spacing={0.75} alignItems="center">
        <Typography variant="body2" color="text.secondary">
          {label}
        </Typography>
      </Stack>
      <Typography variant="h6" fontWeight={800} mt={0.65}>
        {isCurrency ? formatCurrency(value) : formatNumber(value)}
      </Typography>
    </Box>
  );

  if (!helper) return cardContent;

  return <RevenueTooltip title={helper}>{cardContent}</RevenueTooltip>;
};

const MetricRow = ({ label, value, accent, helper, isCurrency = true }) => {
  const rowContent = (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 2,
        px: 1,
        py: 1.1,
        mx: -1,
        borderRadius: 2,
        cursor: helper ? "pointer" : "default",
        transition:
          "transform 180ms ease, background-color 180ms ease, box-shadow 180ms ease",
        "&:hover": helper
          ? {
              transform: "translateX(4px)",
              backgroundColor: alpha(accent, 0.08),
              boxShadow: `0 10px 22px ${alpha(accent, 0.12)}`,
            }
          : undefined,
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

  if (!helper) return rowContent;

  return <RevenueTooltip title={helper}>{rowContent}</RevenueTooltip>;
};

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
          setChannel((current) => {
            const preferredChannel =
              getStoredSharedChannelId("revenue.selectedChannelId") || current;
            return resolvePreferredSharedChannelId(
              preferredChannel,
              finalChannels,
              (item) => item.value
            );
          });
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
  }, [range]);

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
      helper:
        "The total estimated net revenue from all Google-sold advertising sources as well as from non-advertising sources for the selected date range and region. This is a core metric and is subject to the Deprecation Policy. Estimated revenue metrics are subject to month-end adjustment and don't include partner-sold and partner-served advertising.",
    },
    {
      label: "Estimated Ad Revenue",
      value: totals.ad,
      accent: "#38bdf8",
      helper:
        "The total estimated net revenue from all Google-sold advertising sources for the selected date range and region. Estimated revenue metrics are subject to month-end adjustment and don't include partner-sold and partner-served advertising.",
    },
    {
      label: "Gross Revenue",
      value: totals.gross,
      accent: "#a855f7",
      helper:
        "The estimated gross revenue, in USD, from all Google-sold or DoubleClick-partner-sold advertising for the selected date range and region. Gross revenue is subject to month-end adjustment and does not include partner-served advertising. Gross revenue shouldn't be confused with estimated revenue, or net revenue, which factors in your share of ownership and revenue-sharing agreements.",
    },
    {
      label: "Premium Revenue",
      value: totals.premium,
      accent: "#f59e0b",
      helper:
        "The total estimated revenue earned from YouTube Premium (previously known as YouTube Red) subscriptions for the selected report dimensions. The metric's value reflects revenue from both music and non-music content and is subject to month-end adjustment.",
    },
    {
      label: "Monetized Playbacks",
      value: totals.monetized,
      accent: "#14b8a6",
      helper:
        "The number of instances when a viewer played your video and was shown at least one ad impression. A monetized playback is counted if a viewer is shown a preroll ad but quits watching the ad before your video ever starts. The expected estimated error for this figure is 2.0%.",
      isCurrency: false,
    },
    {
      label: "Ad Impressions",
      value: totals.adImpressions,
      accent: "#6366f1",
      helper: "The number of verified ad impressions served.",
      isCurrency: false,
    },
  ];

  const efficiencyMetrics = [
    {
      label: "RPM",
      value: totals.rpm,
      accent: "#22c55e",
      helper: "Estimated revenue per 1,000 views",
    },
    {
      label: "CPM",
      value: totals.cpm,
      accent: "#38bdf8",
      helper: "The estimated gross revenue per thousand ad impressions.",
    },
    {
      label: "Playback CPM",
      value: totals.playbackCpm,
      accent: "#f59e0b",
      helper: "The estimated gross revenue per thousand playbacks.",
    },
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
        ? "rgba(15,23,42,0.82)"
        : "rgba(255,255,255,0.96)",
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
        <Grid container spacing={{ xs: 2, lg: 2.5 }} alignItems="stretch">
          <Grid size={{ xs: 12, lg: 7 }}>
            <Grid container spacing={1.5}>
              {revenueCards.map((item) => (
                <Grid key={item.label} size={{ xs: 12, sm: 6, md: 4 }}>
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
          </Grid>

          <Grid size={{ xs: 12, lg: 5 }}>
            <Box
              sx={{
                height: "100%",
                pt: { xs: 0.5, lg: 0 },
                pl: { lg: 0.75 },
              }}
            >
              <Stack spacing={0} sx={{ height: "100%", justifyContent: "center" }}>
                <Stack divider={<Divider flexItem sx={{ borderColor: "divider" }} />}>
                  {efficiencyMetrics.map((item) => (
                    <MetricRow
                      key={item.label}
                      label={item.label}
                      value={item.value}
                      accent={item.accent}
                      helper={item.helper}
                    />
                  ))}
                </Stack>
                <Divider flexItem sx={{ borderColor: "divider" }} />
              </Stack>
            </Box>
          </Grid>
        </Grid>
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
                  name="Estimated Ad Revenue"
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
