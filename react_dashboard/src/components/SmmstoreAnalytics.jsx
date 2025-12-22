import { useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  FormControlLabel,
  Paper,
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

const SmmstoreAnalytics = () => {
  const theme = useTheme();
  const [cookies, setCookies] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const [viewMode, setViewMode] = useState("orders");

  const totals = useMemo(() => data?.totals?.by_channel || [], [data]);
  const hasOrders = (data?.orders || []).length > 0;
  const hasTotals = totals.length > 0;
  const totalSum = data?.totals?.total;

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
        body: JSON.stringify({ cookies }),
      });
      if (!resp.ok) {
        const msg = await resp.text();
        throw new Error(msg || `HTTP ${resp.status}`);
      }
      const json = await resp.json();
      setData(json);
    } catch (err) {
      setError(err?.message || "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Stack spacing={2.5}>
      <Paper
        elevation={0}
        sx={{
          p: 2.5,
          borderRadius: 2.5,
          border:
            theme.palette.mode === "dark"
              ? "1px solid rgba(148,163,184,0.25)"
              : `1px solid ${theme.palette.divider}`,
          bgcolor:
            theme.palette.mode === "dark"
              ? "rgba(17,24,39,0.85)"
              : "rgba(255,255,255,0.92)",
        }}
      >
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
                borderRadius: 2,
              },
            }}
          />
          <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
            <Button
              variant="contained"
              onClick={handleLoad}
              disabled={loading || !cookies.trim()}
            >
              {loading ? "Loading..." : "Load last month"}
            </Button>
            {data?.month && (
              <Typography variant="body2" color="text.secondary">
                Month: {data.month}
              </Typography>
            )}
            {data?.count !== undefined && (
              <Typography variant="body2" color="text.secondary">
                Orders: {data.count}
              </Typography>
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
          sx={{
            borderRadius: 2.5,
            border:
              theme.palette.mode === "dark"
                ? "1px solid rgba(148,163,184,0.25)"
                : `1px solid ${theme.palette.divider}`,
            overflow: "hidden",
          }}
        >
          <TableContainer>
            {viewMode === "totals" ? (
              <Table size="small">
                <TableHead>
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
                <TableHead>
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
                      }}
                    >
                      {columns.map((col) => (
                        <TableCell key={col}>{row[col] ?? ""}</TableCell>
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
