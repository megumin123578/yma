import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  FormControlLabel,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
  useTheme,
} from "@mui/material";
import { API_BASE } from "../config";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";

const columns = [
  "ID",
  "Date",
  "Link",
  "Charge",
  "Start count",
  "Quantity",
  "Service",
  "Status",
  "Remains",
];

const formatDateTime = (value) => {
  if (!value) return "";
  const cleaned = String(value)
    .replace("\u00a0", " ")
    .replace(/(\d{4}-\d{2}-\d{2})(\d{2}:\d{2}:\d{2})/, "$1 $2")
    .trim();
  const parsed = new Date(cleaned);
  if (Number.isNaN(parsed.getTime())) return cleaned;
  const pad = (n) => String(n).padStart(2, "0");
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(
    parsed.getDate()
  )} ${pad(parsed.getHours())}:${pad(parsed.getMinutes())}:${pad(
    parsed.getSeconds()
  )}`;
};

const renderCell = (col, value) => {
  if (col === "Date") {
    return formatDateTime(value);
  }
  if (col === "Link" && typeof value === "string" && value.startsWith("http")) {
    return (
      <a
        href={value}
        target="_blank"
        rel="noreferrer"
        style={{ color: "#38bdf8" }}
      >
        {value}
      </a>
    );
  }
  return value ?? "";
};

const formatMonthLabel = (value) => {
  if (!value) return value;
  const match = String(value).match(/^(\d{4})-(\d{2})$/);
  if (!match) return value;
  return `${match[2]}-${match[1]}`;
};

const SmmstoreAnalytics = () => {
  const theme = useTheme();
  const [cookies, setCookies] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const [viewMode, setViewMode] = useState("orders");
  const [months, setMonths] = useState([]);
  const [selectedMonth, setSelectedMonth] = useState("");

  const totals = useMemo(() => data?.totals?.by_channel || [], [data]);
  const hasOrders = (data?.orders || []).length > 0;
  const hasTotals = totals.length > 0;
  const totalSum = data?.totals?.total;
  const cardSx = useMemo(
    () => ({
      p: 2.5,
      borderRadius: 3,
      border: "1px solid",
      borderColor:
        theme.palette.mode === "dark"
          ? "rgba(148,163,184,0.2)"
          : "rgba(15,23,42,0.12)",
      background:
        theme.palette.mode === "dark"
          ? "linear-gradient(140deg, rgba(15,23,42,0.95) 0%, rgba(30,41,59,0.9) 50%, rgba(13,148,136,0.5) 100%)"
          : "linear-gradient(140deg, rgba(248,250,252,0.95) 0%, rgba(226,232,240,0.92) 50%, rgba(186,230,253,0.75) 100%)",
      boxShadow:
        theme.palette.mode === "dark"
          ? "0 18px 35px rgba(15,23,42,0.4)"
          : "0 18px 30px rgba(148,163,184,0.35)",
      position: "relative",
      overflow: "hidden",
      "&:before": {
        content: '""',
        position: "absolute",
        inset: 0,
        background:
          theme.palette.mode === "dark"
            ? "radial-gradient(600px 200px at 10% 0%, rgba(56,189,248,0.2), transparent 60%), radial-gradient(400px 200px at 80% 0%, rgba(16,185,129,0.18), transparent 60%)"
            : "radial-gradient(600px 200px at 10% 0%, rgba(14,165,233,0.2), transparent 60%), radial-gradient(400px 200px at 80% 0%, rgba(251,191,36,0.22), transparent 60%)",
        opacity: 0.75,
        pointerEvents: "none",
      },
    }),
    [theme.palette.mode]
  );

  const tablePaperSx = useMemo(
    () => ({
      borderRadius: 3,
      border: "1px solid",
      borderColor: theme.palette.divider,
      background:
        theme.palette.mode === "dark"
          ? "rgba(10,15,24,0.8)"
          : "rgba(255,255,255,0.94)",
      boxShadow:
        theme.palette.mode === "dark"
          ? "0 14px 28px rgba(15,23,42,0.4)"
          : "0 14px 26px rgba(148,163,184,0.25)",
      overflow: "hidden",
    }),
    [theme.palette.divider, theme.palette.mode]
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

  const fetchMonths = useCallback(async () => {
    const token = localStorage.getItem("access_token");
    if (!token) return;
    try {
      const resp = await fetch(`${API_BASE}/api/smmstore/analytics/months`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) return;
      const json = await resp.json();
      setMonths(Array.isArray(json) ? json : []);
    } catch {
      // ignore
    }
  }, []);

  const handleLoad = async () => {
    setError("");
    setLoading(true);
    setData(null);

    const token = localStorage.getItem("access_token");
    if (!token) {
      setError("Missing access token. Please login again.");
      setLoading(false);
      return;
    }

    try {
      const resp = await fetch(`${API_BASE}/api/smmstore/analytics`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          cookies,
          month: selectedMonth || null,
        }),
      });
      if (!resp.ok) {
        const msg = await resp.text();
        throw new Error(msg || `HTTP ${resp.status}`);
      }
      const json = await resp.json();
      setData(json);
      fetchMonths();
    } catch (err) {
      setError(err?.message || "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) return;

    const fetchCached = async () => {
      setError("");
      setLoading(true);
      try {
        const resp = await fetch(`${API_BASE}/api/smmstore/analytics`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ cookies: "", month: selectedMonth || null }),
        });
        if (!resp.ok) {
          setLoading(false);
          return;
        }
        const json = await resp.json();
        setData(json);
        fetchMonths();
      } catch {
        // ignore cache load errors
      } finally {
        setLoading(false);
      }
    };

    fetchCached();
  }, [fetchMonths, selectedMonth]);

  useEffect(() => {
    fetchMonths();
  }, [fetchMonths]);

  const handleDeleteMonth = async () => {
    if (!selectedMonth) return;
    const ok = window.confirm(`Delete cached month ${selectedMonth}?`);
    if (!ok) return;
    const token = localStorage.getItem("access_token");
    if (!token) return;
    try {
      const resp = await fetch(
        `${API_BASE}/api/smmstore/analytics/months/${selectedMonth}`,
        { method: "DELETE", headers: { Authorization: `Bearer ${token}` } }
      );
      if (!resp.ok) return;
      setMonths((prev) => prev.filter((m) => m.month !== selectedMonth));
      setSelectedMonth("");
      setData(null);
    } catch {
      // ignore
    }
  };

  return (
    <Stack spacing={2.5}>
      <Paper elevation={0} sx={cardSx}>
        <Stack spacing={2}>
          <Typography variant="subtitle1" fontWeight={700}>
            Cookies
          </Typography>
          <TextField
            placeholder="Paste cookie string here..."
            value={cookies}
            onChange={(e) => setCookies(e.target.value)}
            multiline
            minRows={4}
            sx={{
              "& .MuiOutlinedInput-root": {
                backgroundColor:
                  theme.palette.mode === "dark"
                    ? "rgba(15,23,42,0.45)"
                    : "rgba(255,255,255,0.9)",
                borderRadius: 2,
                transition: "box-shadow 0.2s ease",
                "&:hover": {
                  boxShadow:
                    theme.palette.mode === "dark"
                      ? "0 0 0 1px rgba(56,189,248,0.35)"
                      : "0 0 0 1px rgba(14,165,233,0.3)",
                },
                "&.Mui-focused": {
                  boxShadow:
                    theme.palette.mode === "dark"
                      ? "0 0 0 2px rgba(56,189,248,0.45)"
                      : "0 0 0 2px rgba(14,165,233,0.45)",
                },
              },
            }}
          />
          <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
            <Button
              variant="contained"
              onClick={handleLoad}
              disabled={loading || (!cookies.trim() && !selectedMonth)}
              sx={{
                textTransform: "none",
                fontWeight: 700,
                borderRadius: 2,
                px: 2.6,
                position: "relative",
                overflow: "hidden",
                backgroundColor:
                  theme.palette.mode === "dark" ? "#22c55e" : "#16a34a",
                color: theme.palette.mode === "dark" ? "#052e16" : "#052e16",
                boxShadow: "0 12px 20px rgba(15,23,42,0.25)",
                transition: "transform 0.2s ease, box-shadow 0.2s ease",
                "&:before": {
                  content: '""',
                  position: "absolute",
                  top: "-50%",
                  left: "-20%",
                  width: "140%",
                  height: "200%",
                  background:
                    "linear-gradient(120deg, transparent 0%, rgba(255,255,255,0.45) 45%, transparent 90%)",
                  transform: "translateX(-120%)",
                  transition: "transform 0.6s ease",
                  opacity: 0.8,
                },
                "&:hover": {
                  transform: "translateY(-1px)",
                  boxShadow: "0 16px 26px rgba(15,23,42,0.3)",
                  backgroundColor:
                    theme.palette.mode === "dark" ? "#4ade80" : "#15803d",
                },
                "&:hover:before": {
                  transform: "translateX(0%)",
                },
              }}
            >
              {loading ? "Loading..." : "Get last month"}
            </Button>
            {data?.month && (
              <Typography variant="body2" color="text.secondary">
                Month: {formatMonthLabel(data.month)}
              </Typography>
            )}
            {data?.count !== undefined && (
              <Typography variant="body2" color="text.secondary">
                Orders: {data.count}
              </Typography>
            )}
            {!!months.length && (
              <Stack direction="row" spacing={1} alignItems="center">
                <InputLabel shrink>Month</InputLabel>
                <Select
                  size="small"
                  value={selectedMonth}
                  displayEmpty
                  onChange={(e) => setSelectedMonth(e.target.value)}
                  sx={{ minWidth: 140 }}
                >
                  <MenuItem value="">
                    <em>Last month</em>
                  </MenuItem>
                  {months.map((item) => (
                    <MenuItem key={item.month} value={item.month}>
                      {formatMonthLabel(item.month)}
                    </MenuItem>
                  ))}
                </Select>
                <IconButton
                  size="small"
                  onClick={handleDeleteMonth}
                  disabled={!selectedMonth}
                  aria-label="Delete cached month"
                >
                  <DeleteOutlineIcon fontSize="small" />
                </IconButton>
              </Stack>
            )}
            {(hasOrders || hasTotals) && (
              <FormControlLabel
                control={
                  <Switch
                    checked={viewMode === "totals"}
                    onChange={(e) =>
                      setViewMode(e.target.checked ? "totals" : "orders")
                    }
                    color="warning"
                  />
                }
                label={viewMode === "totals" ? "Totals by channel" : "Orders"}
              />
            )}
          </Stack>
          {error && <Alert severity="error">{error}</Alert>}
        </Stack>
      </Paper>

      {(data?.orders || totals.length) && (
        <Paper
          elevation={0}
          sx={tablePaperSx}
        >
          <TableContainer>
            {viewMode === "totals" ? (
              <Table size="small">
                <TableHead sx={tableHeadSx}>
                  <TableRow
                    sx={{
                      bgcolor:
                        theme.palette.mode === "dark"
                          ? "rgba(30,41,59,0.7)"
                          : "action.hover",
                    }}
                  >
                    <TableCell>Channel</TableCell>
                    <TableCell align="right">Charge</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {totals.map((item, index) => (
                    <TableRow
                      key={`${item.link}-${index}`}
                      sx={{
                        bgcolor: index % 2 === 0 ? "transparent" : "action.hover",
                        transition: "transform 0.2s ease, background-color 0.2s ease",
                        "&:hover": {
                          backgroundColor:
                            theme.palette.mode === "dark"
                              ? "rgba(51,65,85,0.55)"
                              : "rgba(226,232,240,0.6)",
                          transform: "translateY(-1px)",
                        },
                      }}
                    >
                      <TableCell>{item.link}</TableCell>
                      <TableCell align="right">
                        ${Number(item.charge).toFixed(2)}
                      </TableCell>
                    </TableRow>
                  ))}
                  {!totals.length && (
                    <TableRow>
                      <TableCell colSpan={2}>
                        <Typography variant="body2" color="text.secondary">
                          No totals available.
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                  {totalSum !== undefined && totals.length > 0 && (
                    <TableRow>
                      <TableCell>
                        <Typography variant="subtitle2" fontWeight={700}>
                          Total
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="subtitle2" fontWeight={700}>
                          ${Number(totalSum).toFixed(2)}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            ) : (
              <Table size="small">
                <TableHead sx={tableHeadSx}>
                  <TableRow
                    sx={{
                      bgcolor:
                        theme.palette.mode === "dark"
                          ? "rgba(30,41,59,0.7)"
                          : "action.hover",
                    }}
                  >
                    {columns.map((col) => (
                      <TableCell key={col}>{col}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(data?.orders || []).map((row, index) => (
                    <TableRow
                      key={`${row.ID}-${index}`}
                      sx={{
                        bgcolor: index % 2 === 0 ? "transparent" : "action.hover",
                        transition: "transform 0.2s ease, background-color 0.2s ease",
                        "&:hover": {
                          backgroundColor:
                            theme.palette.mode === "dark"
                              ? "rgba(51,65,85,0.55)"
                              : "rgba(226,232,240,0.6)",
                          transform: "translateY(-1px)",
                        },
                      }}
                    >
                      {columns.map((col) => (
                        <TableCell
                          key={col}
                          sx={
                            col === "Date"
                              ? {
                                  minWidth: 160,
                                  whiteSpace: "nowrap",
                                }
                              : col === "Link"
                              ? {
                                  maxWidth: 220,
                                  whiteSpace: "nowrap",
                                  overflow: "hidden",
                                  textOverflow: "ellipsis",
                                }
                              : col === "Service"
                              ? {
                                  minWidth: 320,
                                }
                              : undefined
                          }
                        >
                          {renderCell(col, row[col])}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                  {!(data?.orders || []).length && (
                    <TableRow>
                      <TableCell colSpan={columns.length}>
                        <Typography variant="body2" color="text.secondary">
                          No orders for last month.
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            )}
          </TableContainer>
        </Paper>
      )}
    </Stack>
  );
};

export default SmmstoreAnalytics;
