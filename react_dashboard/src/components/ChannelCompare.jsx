import React, { useEffect, useMemo, useState, useCallback } from "react";
import {
  Box,
  Stack,
  Paper,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  CircularProgress,
  Divider,
  Switch,
  FormControlLabel,
  Checkbox,
  ListItemText,
  Avatar,
} from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import { ResponsiveBar } from "@nivo/bar";
import { LocalizationProvider, DatePicker } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import dayjs from "dayjs";
import { API_BASE } from "../config";
import { METRIC_OPTIONS, getRangeForPeriod, formatNumber, getChannelAvatarMap } from "./Module";
import {
  getSharedDatePickerSlotProps,
  getSharedFilterControlSx,
  getSharedSelectMenuProps,
} from "./filterStyles";

const PERIOD_OPTIONS = [
  { value: "last7", label: "Last 7 days" },
  { value: "last28", label: "Last 28 days" },
  { value: "last90", label: "Last 90 days" },
  { value: "last365", label: "Last 365 days" },
  { value: "custom", label: "Custom" },
];

const ANOMALY_PCT = 50;
const STORAGE_KEY = "channelCompare.filters";

const loadStoredCompare = () => {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
};

const ChannelCompare = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const filterControlSx = getSharedFilterControlSx(theme);
  const selectMenuProps = getSharedSelectMenuProps(theme);
  const datePickerSlotProps = getSharedDatePickerSlotProps(theme, {
    width: 170,
    minWidth: 170,
    flex: undefined,
  });
  const stored = loadStoredCompare();

  const [metric, setMetric] = useState("views");
  const [period, setPeriod] = useState("last28");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [limit, setLimit] = useState(20);
  const [manualPick, setManualPick] = useState(() => stored.manualPick ?? false);
  const [channels, setChannels] = useState([]);
  const [channelAvatarMap, setChannelAvatarMap] = useState({});
  const [selectedChannels, setSelectedChannels] = useState(
    () => stored.selectedChannels || []
  );

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const authHeaders = useMemo(() => {
    const token = localStorage.getItem("access_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  useEffect(() => {
    if (period === "custom") return;
    const r = getRangeForPeriod(period, new Date());
    if (r?.start && r?.end) {
      setStartDate(r.start);
      setEndDate(r.end);
    }
  }, [period]);

  const canFetch = useMemo(() => {
    if (!startDate || !endDate) return false;
    return true;
  }, [startDate, endDate]);

  useEffect(() => {
    if (!canFetch) return;

    const fetchData = async () => {
      setLoading(true);
      setErrorMsg("");
      try {
        const resp = await fetch(`${API_BASE}/api/channel_compare/rank`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders },
          body: JSON.stringify({
            start: startDate,
            end: endDate,
            metric,
            limit: manualPick ? 200 : limit,
          }),
        });
        if (!resp.ok) throw new Error((await resp.text()) || `HTTP ${resp.status}`);
        const data = await resp.json();
        setItems(Array.isArray(data?.items) ? data.items : []);
      } catch (e) {
        setItems([]);
        setErrorMsg(e?.message || "Failed to load data");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [canFetch, startDate, endDate, metric, limit, manualPick, authHeaders]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          manualPick,
          selectedChannels,
        })
      );
    } catch {
      // ignore storage errors
    }
  }, [manualPick, selectedChannels]);

  useEffect(() => {
    let stop = false;
    (async () => {
      try {
        const resp = await fetch(`${API_BASE}/api/traffic_source/channels`, {
          headers: authHeaders,
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        const list = (Array.isArray(data?.items) ? data.items : [])
          .map((item) => {
            if (typeof item === "string") return { value: item, label: item };
            const value = item?.value || item?.name || "";
            return {
              value,
              label: item?.label || item?.name || value,
            };
          })
          .filter((item) => item.value);
        if (!stop) setChannels(list);
      } catch {
        if (!stop) setChannels([]);
      }
    })();
    return () => {
      stop = true;
    };
  }, [authHeaders]);

  useEffect(() => {
    let active = true;
    getChannelAvatarMap().then((map) => {
      if (active) setChannelAvatarMap(map || {});
    });
    return () => {
      active = false;
    };
  }, []);

  const rows = useMemo(() => {
    return items.map((it, idx) => {
      const deltaPct = it.deltaPct;
      const isNew = it.trend === "new" && it.currentValue > 0;
      const isAnomaly = deltaPct !== null ? Math.abs(deltaPct) >= ANOMALY_PCT : isNew;

      return {
        rank: idx + 1,
        accountTag: it.accountTag,
        currentValue: it.currentValue || 0,
        previousValue: it.previousValue || 0,
        delta: it.delta || 0,
        deltaPct: deltaPct,
        trend: it.trend || "flat",
        isNew,
        isAnomaly,
      };
    });
  }, [items]);

  const visibleRows = useMemo(() => {
    if (!manualPick) return rows;
    if (!selectedChannels.length) return rows;
    return rows.filter((r) => selectedChannels.includes(r.accountTag));
  }, [rows, manualPick, selectedChannels]);

  const channelLabelMap = useMemo(() => {
    return new Map(
      (channels || []).map((c) => [String(c.value), c.label || c.value])
    );
  }, [channels]);

  const getChannelLabel = useCallback(
    (value) => channelLabelMap.get(String(value)) || value,
    [channelLabelMap]
  );

  const barData = useMemo(
    () =>
      visibleRows.map((r) => ({
        channel: r.accountTag,
        channelLabel: getChannelLabel(r.accountTag),
        value: r.currentValue,
        deltaPct: r.deltaPct,
        trend: r.trend,
        isAnomaly: r.isAnomaly,
      })),
    [visibleRows, getChannelLabel]
  );

  const barHeight = Math.max(320, visibleRows.length * 28);

  const barColor = (bar) => {
    const trend = bar.data.trend;
    const isAnomaly = bar.data.isAnomaly;

    if (trend === "up") return isAnomaly ? "#22c55e" : "#16a34a";
    if (trend === "down") return isAnomaly ? "#ef4444" : "#dc2626";
    if (trend === "new") return "#f59e0b";
    return theme.palette.mode === "dark" ? "#94a3b8" : "#64748b";
  };

  const rowHighlight = (row) => {
    if (!row.isAnomaly) return "transparent";
    if (row.trend === "up") return alpha("#22c55e", 0.15);
    if (row.trend === "down") return alpha("#ef4444", 0.15);
    return alpha("#f59e0b", 0.18);
  };

  const panelSx = useMemo(
    () => ({
      p: 2.5,
      borderRadius: 3,
      border: "1px solid",
      borderColor: isDark
        ? "rgba(148,163,184,0.2)"
        : "rgba(15,23,42,0.12)",
      background: isDark ? "rgba(15,23,42,0.88)" : "rgba(248,250,252,0.96)",
      boxShadow: isDark
        ? "0 18px 36px rgba(15,23,42,0.45)"
        : "0 18px 30px rgba(148,163,184,0.25)",
      transition: "transform 220ms ease, box-shadow 220ms ease",
      "&:hover": {
        transform: "translateY(-2px)",
        boxShadow: isDark
          ? "0 22px 40px rgba(15,23,42,0.6)"
          : "0 22px 34px rgba(148,163,184,0.32)",
      },
    }),
    [isDark]
  );

  const tablePaperSx = useMemo(
    () => ({
      borderRadius: 3,
      border: "1px solid",
      borderColor: isDark
        ? "rgba(148,163,184,0.22)"
        : "rgba(15,23,42,0.12)",
      background: isDark ? "rgba(10,15,24,0.82)" : "rgba(255,255,255,0.94)",
      boxShadow: isDark
        ? "0 14px 28px rgba(15,23,42,0.4)"
        : "0 14px 26px rgba(148,163,184,0.25)",
      overflow: "hidden",
    }),
    [isDark]
  );

  const tableHeadSx = useMemo(
    () => ({
      background: isDark ? "rgba(15,23,42,0.9)" : "rgba(226,232,240,0.85)",
      "& .MuiTableCell-root": {
        fontWeight: 700,
        textTransform: "uppercase",
        letterSpacing: "0.08em",
        fontSize: "0.72rem",
        color: isDark ? "rgba(226,232,240,0.85)" : "rgba(15,23,42,0.75)",
      },
    }),
    [isDark]
  );

  const deltaChip = (row) => {
    if (row.isNew) return <Chip size="small" label="NEW" color="warning" />;
    if (row.deltaPct === null) return <Chip size="small" label="-" />;
    if (row.deltaPct > 0) return <Chip size="small" label="UP" color="success" />;
    if (row.deltaPct < 0) return <Chip size="small" label="DOWN" color="error" />;
    return <Chip size="small" label="FLAT" />;
  };

  return (
    <Stack spacing={2.5}>
      <Paper
        elevation={0}
        sx={{
          ...panelSx,
          position: "relative",
        }}
      >
        <Stack spacing={2}>
          <FormControlLabel
            sx={{
              position: "absolute",
              top: 14,
              right: 16,
              ".MuiFormControlLabel-label": {
                fontWeight: 600,
                color: isDark ? "rgba(226,232,240,0.9)" : "rgba(30,41,59,0.9)",
                marginLeft: 1,
              },
              ".MuiSwitch-root": {
                width: 44,
                height: 24,
                padding: 0,
              },
              ".MuiSwitch-track": {
                borderRadius: 999,
                backgroundColor: isDark
                  ? "rgba(148,163,184,0.35)"
                  : "rgba(148,163,184,0.45)",
                opacity: 1,
                transition: "background-color 220ms ease",
              },
              ".MuiSwitch-thumb": {
                width: 20,
                height: 20,
                backgroundColor: isDark ? "#e2e8f0" : "#0f172a",
                boxShadow: isDark
                  ? "0 0 10px rgba(56,189,248,0.35)"
                  : "0 4px 10px rgba(15,23,42,0.2)",
                transition: "transform 220ms ease, box-shadow 220ms ease",
              },
              ".MuiSwitch-switchBase": {
                padding: 0,
                top: 2,
                left: 2,
                transition: "transform 220ms ease",
                "&.Mui-checked": {
                  color: "#38bdf8",
                  transform: "translateX(20px)",
                },
                "&.Mui-checked + .MuiSwitch-track": {
                  backgroundColor: isDark ? "#0ea5e9" : "#38bdf8",
                  boxShadow: isDark
                    ? "0 0 18px rgba(14,165,233,0.55)"
                    : "0 0 14px rgba(56,189,248,0.4)",
                },
                "&.Mui-checked .MuiSwitch-thumb": {
                  animation: "switchGlow 1.6s ease-in-out infinite",
                },
              },
              "@keyframes switchGlow": {
                "0%": { boxShadow: "0 0 8px rgba(56,189,248,0.35)" },
                "50%": { boxShadow: "0 0 14px rgba(56,189,248,0.65)" },
                "100%": { boxShadow: "0 0 8px rgba(56,189,248,0.35)" },
              },
            }}
            control={
              <Switch
                checked={manualPick}
                onChange={(e) => setManualPick(e.target.checked)}
              />
            }
            label="Pick channels"
          />
          <Box>
            <Typography variant="h6" fontWeight={700}>
              Channel Compare
            </Typography>
          </Box>

          <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
            <FormControl size="small" sx={{ ...filterControlSx, minWidth: 200 }}>
              <InputLabel id="metric-label">Metric</InputLabel>
              <Select
                labelId="metric-label"
                label="Metric"
                value={metric}
                onChange={(e) => setMetric(e.target.value)}
                MenuProps={selectMenuProps}
              >
                {METRIC_OPTIONS.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ ...filterControlSx, minWidth: 190 }}>
              <InputLabel id="period-label">Period</InputLabel>
              <Select
                labelId="period-label"
                label="Period"
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
                MenuProps={selectMenuProps}
              >
                {PERIOD_OPTIONS.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {period === "custom" && (
              <LocalizationProvider dateAdapter={AdapterDayjs}>
                <DatePicker
                  label="Start"
                  value={startDate ? dayjs(startDate) : null}
                  onChange={(v) =>
                    setStartDate(v ? v.format("YYYY-MM-DD") : "")
                  }
                  format="DD/MM/YYYY"
                  slotProps={datePickerSlotProps}
                />
                <DatePicker
                  label="End"
                  value={endDate ? dayjs(endDate) : null}
                  onChange={(v) => setEndDate(v ? v.format("YYYY-MM-DD") : "")}
                  format="DD/MM/YYYY"
                  slotProps={datePickerSlotProps}
                />
              </LocalizationProvider>
            )}

            {!manualPick ? (
              <FormControl size="small" sx={{ ...filterControlSx, minWidth: 120 }}>
                <InputLabel id="limit-label">Top</InputLabel>
                <Select
                  labelId="limit-label"
                  label="Top"
                  value={limit}
                  onChange={(e) => setLimit(Number(e.target.value))}
                  MenuProps={selectMenuProps}
                >
                  {[10, 20, 30, 50].map((n) => (
                    <MenuItem key={n} value={n}>
                      {n}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            ) : (
              <FormControl size="small" sx={{ ...filterControlSx, minWidth: 260 }}>
                <InputLabel id="channel-pick-label">Channels</InputLabel>
                <Select
                  labelId="channel-pick-label"
                  label="Channels"
                  multiple
                  value={selectedChannels}
                  onChange={(e) => setSelectedChannels(e.target.value)}
                  MenuProps={selectMenuProps}
                  renderValue={(selected) =>
                    selected.length
                      ? selected.slice(0, 2).join(", ") +
                        (selected.length > 2
                          ? ` (+${selected.length - 2})`
                          : "")
                      : "All"
                  }
                >
                  {channels.map((opt) => (
                    <MenuItem key={opt.value} value={opt.value}>
                      <Checkbox
                        size="small"
                        checked={selectedChannels.indexOf(opt.value) > -1}
                      />
                      <Avatar
                        src={channelAvatarMap[opt.value] || ""}
                        alt={opt.label || opt.value}
                        sx={{ width: 20, height: 20, mr: 1 }}
                      />
                      <ListItemText primary={opt.label || opt.value} />
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}

          </Stack>

        </Stack>
      </Paper>

      {errorMsg && (
        <Typography color="error" variant="body2">
          {errorMsg}
        </Typography>
      )}

      <Paper
        elevation={0}
        sx={{
          ...panelSx,
          position: "relative",
          overflow: "hidden",
        }}
      >
        <Stack spacing={1.5}>
          <Box>
            <Typography variant="subtitle1" fontWeight={700}>
              Ranking Chart
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Highlighted bars indicate abnormal changes vs previous period.
            </Typography>
          </Box>
          <Divider />
          {loading ? (
            <Box display="flex" justifyContent="center" mt={2}>
              <CircularProgress />
            </Box>
          ) : (
            <Box sx={{ height: barHeight }}>
              <ResponsiveBar
                data={barData}
                keys={["value"]}
                indexBy="channel"
                layout="horizontal"
                margin={{ top: 10, right: 40, bottom: 40, left: 180 }}
                padding={0.3}
                colors={barColor}
                enableGridX
                enableGridY={false}
                theme={{
                  textColor: isDark ? "#e2e8f0" : "#0f172a",
                  axis: {
                    ticks: {
                      text: { fill: isDark ? "#cbd5f5" : "#334155" },
                    },
                    legend: {
                      text: { fill: isDark ? "#e2e8f0" : "#0f172a" },
                    },
                  },
                  grid: {
                    line: { stroke: isDark ? "rgba(148,163,184,0.18)" : "rgba(148,163,184,0.35)" },
                  },
                  labels: {
                    text: { fill: isDark ? "#0b1020" : "#ffffff" },
                  },
                }}
                axisBottom={{
                  tickSize: 0,
                  tickPadding: 6,
                  legend: "Value",
                  legendOffset: 32,
                  legendPosition: "middle",
                }}
                axisLeft={{
                  tickSize: 0,
                  tickPadding: 8,
                  format: (v) => getChannelLabel(v),
                }}
                labelSkipWidth={120}
                labelTextColor={isDark ? "#f8fafc" : "#ffffff"}
                tooltip={({ data }) => (
                  <Box
                    sx={{
                      px: 1.25,
                      py: 0.75,
                      minWidth: 220,
                      maxWidth: 320,
                      borderRadius: 1,
                      boxShadow: 3,
                      bgcolor: isDark
                        ? "rgba(15,23,42,0.95)"
                        : "rgba(255,255,255,0.95)",
                      color: isDark ? "#e2e8f0" : "#0f172a",
                      fontSize: 13,
                    }}
                  >
                    <div style={{ fontWeight: 700, whiteSpace: "nowrap" }}>
                      {data.channelLabel || data.channel}
                    </div>
                    <div>Value: {formatNumber(data.value)}</div>
                    {Number.isFinite(data.deltaPct) && (
                      <div>Change: {data.deltaPct.toFixed(1)}%</div>
                    )}
                    {!Number.isFinite(data.deltaPct) && data.trend === "new" && (
                      <div>Change: New</div>
                    )}
                  </Box>
                )}
              />
            </Box>
          )}
        </Stack>
      </Paper>

      <TableContainer
        component={Paper}
        elevation={0}
        sx={tablePaperSx}
      >
        <Table size="small">
          <TableHead sx={tableHeadSx}>
            <TableRow>
              <TableCell>Rank</TableCell>
              <TableCell>Channel</TableCell>
              <TableCell align="right">Current</TableCell>
              <TableCell align="right">Previous</TableCell>
              <TableCell align="right">Delta %</TableCell>
              <TableCell align="center">Signal</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {visibleRows.map((row) => (
              <TableRow
                key={row.accountTag}
                sx={{
                  bgcolor: rowHighlight(row),
                  transition: "background-color 180ms ease",
                  "&:hover": {
                    bgcolor: isDark
                      ? alpha("#38bdf8", 0.12)
                      : alpha("#38bdf8", 0.08),
                  },
                }}
              >
                <TableCell>{row.rank}</TableCell>
                <TableCell>
                  <Box display="flex" alignItems="center" gap={1.25}>
                    <Avatar
                      src={channelAvatarMap[row.accountTag] || ""}
                      alt={getChannelLabel(row.accountTag)}
                      sx={{ width: 28, height: 28 }}
                    />
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {getChannelLabel(row.accountTag)}
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell align="right">{formatNumber(row.currentValue)}</TableCell>
                <TableCell align="right">{formatNumber(row.previousValue)}</TableCell>
                <TableCell align="right">
                  {row.isNew
                    ? "New"
                    : row.deltaPct === null
                    ? "-"
                    : `${row.deltaPct.toFixed(1)}%`}
                </TableCell>
                <TableCell align="center">{deltaChip(row)}</TableCell>
              </TableRow>
            ))}
            {!visibleRows.length && !loading && (
              <TableRow>
                <TableCell colSpan={6}>
                  <Typography variant="body2" color="text.secondary">
                    No data
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
};

export default ChannelCompare;
