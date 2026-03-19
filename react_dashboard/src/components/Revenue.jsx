import { useEffect, useMemo, useState } from "react";
import {
  Box,
  Stack,
  Typography,
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid,
} from "@mui/material";
import { useTheme } from "@mui/material/styles";
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
import { getStoredSharedChannelId, setStoredSharedChannelId } from "../utils/sharedChannel";

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
        if (!stop) {
          setChannels(items);
          if (!items.length) {
            setChannel("");
          } else {
            const preferredChannel =
              getStoredSharedChannelId("revenue.selectedChannelId") || channel;
            if (!preferredChannel || !items.some((c) => c.value === preferredChannel)) {
              setChannel(items[0].value);
            } else if (preferredChannel !== channel) {
              setChannel(preferredChannel);
            }
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
      rpm: row.rpm != null ? Number(row.rpm) : null,
      cpm: row.cpm != null ? Number(row.cpm) : null,
      playbackCpm: row.playback_cpm != null ? Number(row.playback_cpm) : null,
      monetized: Number(row.monetized_playbacks || 0),
    }));
  }, [rows]);

  const totals = useMemo(() => {
    const base = {
      estimated: 0,
      ad: 0,
      gross: 0,
      monetized: 0,
      rpm: [],
      cpm: [],
      playbackCpm: [],
    };
    for (const row of chartData) {
      base.estimated += row.estimated;
      base.ad += row.ad;
      base.gross += row.gross;
      base.monetized += row.monetized;
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
      monetized: base.monetized,
      rpm: avg(base.rpm),
      cpm: avg(base.cpm),
      playbackCpm: avg(base.playbackCpm),
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
      labelFormatter: (label) => dayjs(label).format("DD-MM-YYYY"),
    };
  }, [theme.palette.mode]);

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
  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
        <ChannelSwitcher
          options={channels}
          value={channel}
          onChange={(option) => setChannel(option?.value || "")}
          sx={CHANNEL_SWITCHER_SX}
          recentStorageKey="revenue.recentChannels"
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

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper elevation={0} sx={cardSx}>
            <Typography variant="subtitle2" color="text.secondary">
              Estimated Revenue
            </Typography>
            <Typography variant="h5" fontWeight={700} mt={1}>
              {formatCurrency(totals.estimated)}
            </Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper elevation={0} sx={cardSx}>
            <Typography variant="subtitle2" color="text.secondary">
              Ad Revenue
            </Typography>
            <Typography variant="h5" fontWeight={700} mt={1}>
              {formatCurrency(totals.ad)}
            </Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper elevation={0} sx={cardSx}>
            <Typography variant="subtitle2" color="text.secondary">
              Gross Revenue
            </Typography>
            <Typography variant="h5" fontWeight={700} mt={1}>
              {formatCurrency(totals.gross)}
            </Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper elevation={0} sx={cardSx}>
            <Typography variant="subtitle2" color="text.secondary">
              RPM (avg)
            </Typography>
            <Typography variant="h5" fontWeight={700} mt={1}>
              {formatCurrency(totals.rpm)}
            </Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper elevation={0} sx={cardSx}>
            <Typography variant="subtitle2" color="text.secondary">
              CPM (avg)
            </Typography>
            <Typography variant="h5" fontWeight={700} mt={1}>
              {formatCurrency(totals.cpm)}
            </Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper elevation={0} sx={cardSx}>
            <Typography variant="subtitle2" color="text.secondary">
              Monetized Playbacks
            </Typography>
            <Typography variant="h5" fontWeight={700} mt={1}>
              {formatNumber(totals.monetized)}
            </Typography>
          </Paper>
        </Grid>
      </Grid>

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
              </LineChart>
            </ResponsiveContainer>
          )}
        </Box>
      </Paper>
    </Stack>
  );
};

export default RevenueAnalytics;
