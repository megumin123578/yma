import React, { useEffect, useMemo, useState } from "react";
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
} from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import { ResponsiveBar } from "@nivo/bar";
import { LocalizationProvider, DatePicker } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import dayjs from "dayjs";
import { API_BASE } from "../config";
import { METRIC_OPTIONS, getRangeForPeriod, formatNumber } from "./Module";

const PERIOD_OPTIONS = [
  { value: "last7", label: "Last 7 days" },
  { value: "last28", label: "Last 28 days" },
  { value: "last90", label: "Last 90 days" },
  { value: "last365", label: "Last 365 days" },
  { value: "custom", label: "Custom" },
];

const ANOMALY_PCT = 50;

const ChannelCompare = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  const [metric, setMetric] = useState("views");
  const [period, setPeriod] = useState("last28");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [limit, setLimit] = useState(20);

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [rangeInfo, setRangeInfo] = useState(null);

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
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            start: startDate,
            end: endDate,
            metric,
            limit,
          }),
        });
        if (!resp.ok) throw new Error((await resp.text()) || `HTTP ${resp.status}`);
        const data = await resp.json();
        setItems(Array.isArray(data?.items) ? data.items : []);
        setRangeInfo({
          start: data?.start || startDate,
          end: data?.end || endDate,
          prev_start: data?.prev_start,
          prev_end: data?.prev_end,
        });
      } catch (e) {
        setItems([]);
        setRangeInfo(null);
        setErrorMsg(e?.message || "Failed to load data");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [canFetch, startDate, endDate, metric, limit]);

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

  const barData = useMemo(
    () =>
      rows.map((r) => ({
        channel: r.accountTag,
        value: r.currentValue,
        deltaPct: r.deltaPct,
        trend: r.trend,
        isAnomaly: r.isAnomaly,
      })),
    [rows]
  );

  const barHeight = Math.max(320, rows.length * 28);

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
          p: 2.5,
          borderRadius: 2.5,
          border: isDark
            ? "1px solid rgba(148,163,184,0.25)"
            : `1px solid ${theme.palette.divider}`,
          bgcolor: isDark ? "rgba(15,23,42,0.6)" : "background.paper",
          boxShadow: isDark
            ? "0 18px 36px rgba(2,6,23,0.45)"
            : "0 16px 30px rgba(15,23,42,0.08)",
          transition: "transform 220ms ease, box-shadow 220ms ease",
          "&:hover": {
            transform: "translateY(-2px)",
            boxShadow: isDark
              ? "0 22px 40px rgba(2,6,23,0.6)"
              : "0 20px 34px rgba(15,23,42,0.12)",
          },
        }}
      >
        <Stack spacing={2}>
          <Box>
            <Typography variant="h6" fontWeight={700}>
              Channel Compare
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Rank channels by metric and mark unusual changes across periods.
            </Typography>
          </Box>

          <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
            <FormControl size="small" sx={{ minWidth: 200 }}>
              <InputLabel id="metric-label">Metric</InputLabel>
              <Select
                labelId="metric-label"
                label="Metric"
                value={metric}
                onChange={(e) => setMetric(e.target.value)}
              >
                {METRIC_OPTIONS.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 190 }}>
              <InputLabel id="period-label">Period</InputLabel>
              <Select
                labelId="period-label"
                label="Period"
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
              >
                {PERIOD_OPTIONS.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <LocalizationProvider dateAdapter={AdapterDayjs}>
              <DatePicker
                label="Start"
                value={startDate ? dayjs(startDate) : null}
                onChange={(v) => setStartDate(v ? v.format("YYYY-MM-DD") : "")}
                format="DD/MM/YYYY"
                disabled={period !== "custom"}
                slotProps={{ textField: { size: "small", sx: { width: 170 } } }}
              />
              <DatePicker
                label="End"
                value={endDate ? dayjs(endDate) : null}
                onChange={(v) => setEndDate(v ? v.format("YYYY-MM-DD") : "")}
                format="DD/MM/YYYY"
                disabled={period !== "custom"}
                slotProps={{ textField: { size: "small", sx: { width: 170 } } }}
              />
            </LocalizationProvider>

            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel id="limit-label">Top</InputLabel>
              <Select
                labelId="limit-label"
                label="Top"
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
              >
                {[10, 20, 30, 50].map((n) => (
                  <MenuItem key={n} value={n}>
                    {n}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>

          {rangeInfo && (
            <Box
              sx={{
                p: 1.25,
                borderRadius: 1.5,
                bgcolor: isDark
                  ? "rgba(30,41,59,0.6)"
                  : alpha(theme.palette.primary.main, 0.06),
                border: isDark
                  ? "1px solid rgba(148,163,184,0.2)"
                  : `1px solid ${theme.palette.divider}`,
              }}
            >
              <Typography variant="body2" color="text.secondary">
                Current: {rangeInfo.start} ~ {rangeInfo.end}
                {rangeInfo.prev_start && rangeInfo.prev_end
                  ? ` | Previous: ${rangeInfo.prev_start} ~ ${rangeInfo.prev_end}`
                  : ""}
              </Typography>
            </Box>
          )}
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
          p: 2.5,
          borderRadius: 2.5,
          border: isDark
            ? "1px solid rgba(148,163,184,0.2)"
            : `1px solid ${theme.palette.divider}`,
          bgcolor: isDark ? "rgba(17,24,39,0.65)" : "background.paper",
          position: "relative",
          overflow: "hidden",
          transition: "transform 220ms ease, box-shadow 220ms ease",
          "&::after": {
            content: '""',
            position: "absolute",
            inset: 0,
            background: isDark
              ? "radial-gradient(circle at 15% 0%, rgba(56,189,248,0.12), transparent 45%)"
              : "radial-gradient(circle at 15% 0%, rgba(56,189,248,0.12), transparent 50%)",
            opacity: 0,
            transition: "opacity 260ms ease",
            pointerEvents: "none",
          },
          "&:hover": {
            transform: "translateY(-2px)",
            boxShadow: isDark
              ? "0 22px 40px rgba(2,6,23,0.6)"
              : "0 20px 34px rgba(15,23,42,0.12)",
            "&::after": { opacity: 1 },
          },
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
                }}
                labelSkipWidth={120}
                labelTextColor={isDark ? "#f8fafc" : "#ffffff"}
                tooltip={({ data }) => (
                  <Box
                    sx={{
                      px: 1.25,
                      py: 0.75,
                      borderRadius: 1,
                      boxShadow: 3,
                      bgcolor: isDark
                        ? "rgba(15,23,42,0.95)"
                        : "rgba(255,255,255,0.95)",
                      color: isDark ? "#e2e8f0" : "#0f172a",
                      fontSize: 13,
                    }}
                  >
                    <div style={{ fontWeight: 700 }}>{data.channel}</div>
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
        sx={{
          borderRadius: 2.5,
          border: isDark
            ? "1px solid rgba(148,163,184,0.2)"
            : `1px solid ${theme.palette.divider}`,
          overflow: "hidden",
          transition: "transform 220ms ease, box-shadow 220ms ease",
          "&:hover": {
            transform: "translateY(-2px)",
            boxShadow: isDark
              ? "0 20px 38px rgba(2,6,23,0.55)"
              : "0 18px 30px rgba(15,23,42,0.1)",
          },
        }}
      >
        <Table size="small">
          <TableHead>
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
            {rows.map((row) => (
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
                <TableCell>{row.accountTag}</TableCell>
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
            {!rows.length && !loading && (
              <TableRow>
                <TableCell colSpan={7}>
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
