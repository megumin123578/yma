import { useEffect, useMemo, useState } from "react";
import {
  Box,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  useTheme,
} from "@mui/material";
import api from "../services/api";
import { formatNumber } from "./Module";

const formatPct = (value) => {
  if (value === null || value === undefined) return "-";
  const num = Number(value);
  if (Number.isNaN(num)) return "-";
  return `${(num * 100).toFixed(2)}%`;
};

const ReachAnalytics = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const authHeaders = useMemo(() => {
    const token = localStorage.getItem("access_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);
  const [accounts, setAccounts] = useState([]);
  const [accountTag, setAccountTag] = useState(() => {
    try {
      return localStorage.getItem("reach.selectedChannelId") || "";
    } catch {
      return "";
    }
  });
  const [rows, setRows] = useState([]);
  const [range, setRange] = useState({ start: "", end: "" });
  const [breakdown, setBreakdown] = useState({
    range: { start: "", end: "" },
    external: [],
    playlist: 0,
    suggested: 0,
    browse: 0,
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const loadChannels = async () => {
      try {
        const resp = await api.get("/api/reach/channels", {
          headers: authHeaders,
        });
        const data = resp.data;
        const items = data?.items || [];
        const order = (() => {
          try {
            return JSON.parse(localStorage.getItem("tokens.order") || "[]");
          } catch {
            return [];
          }
        })()
          .map((name) => (name || "").replace(/\.pickle$/i, ""))
          .filter(Boolean);
        const orderKey = (value) => String(value || "").toLowerCase();
        const byName = new Map(items.map((acct) => [orderKey(acct), acct]));
        const ordered = order
          .map((name) => byName.get(orderKey(name)))
          .filter(Boolean);
        const remaining = items.filter(
          (acct) => !order.map(orderKey).includes(orderKey(acct))
        );
        const finalAccounts = [...ordered, ...remaining];
        setAccounts(finalAccounts);
        if (!finalAccounts.length) {
          setAccountTag("");
        } else if (!accountTag || !finalAccounts.includes(accountTag)) {
          setAccountTag(finalAccounts[0]);
        }
      } catch (err) {
        setAccounts([]);
      }
    };
    loadChannels();
  }, [accountTag, authHeaders]);

  useEffect(() => {
    if (!accountTag) return;
    try {
      localStorage.setItem("reach.selectedChannelId", accountTag);
    } catch {
      // ignore storage errors
    }
  }, [accountTag, authHeaders]);

  useEffect(() => {
    if (!accountTag) return;
    const loadReach = async () => {
      setLoading(true);
      try {
        const resp = await api.get(
          `/api/reach?accountTag=${encodeURIComponent(accountTag)}`,
          { headers: authHeaders }
        );
        const data = resp.data;
        setRows(data?.rows || []);
        setRange({ start: data?.start_date || "", end: data?.end_date || "" });
      } catch (err) {
        setRows([]);
        setRange({ start: "", end: "" });
      } finally {
        setLoading(false);
      }
    };
    loadReach();
  }, [accountTag, authHeaders]);

  useEffect(() => {
    if (!accountTag) return;
    const loadBreakdown = async () => {
      try {
        const resp = await api.get(
          `/api/reach/traffic_breakdown?accountTag=${encodeURIComponent(
            accountTag
          )}`,
          { headers: authHeaders }
        );
        const data = resp.data;
        setBreakdown({
          range: data?.range || { start: "", end: "" },
          external: data?.external || [],
          playlist: data?.playlist || 0,
          suggested: data?.suggested || 0,
          browse: data?.browse || 0,
        });
      } catch (err) {
        setBreakdown({
          range: { start: "", end: "" },
          external: [],
          playlist: 0,
          suggested: 0,
          browse: 0,
        });
      }
    };
    loadBreakdown();
  }, [accountTag, authHeaders]);

  const headerSx = {
    background: isDark ? "rgba(15,23,42,0.9)" : "rgba(226,232,240,0.85)",
    "& .MuiTableCell-root": {
      fontWeight: 700,
      textTransform: "uppercase",
      letterSpacing: "0.08em",
      fontSize: "0.7rem",
      color: isDark ? "rgba(226,232,240,0.85)" : "rgba(15,23,42,0.75)",
      whiteSpace: "nowrap",
    },
  };

  const displayRows = useMemo(() => rows.slice(0, 20), [rows]);
  const maxExternal = useMemo(
    () => Math.max(1, ...breakdown.external.map((row) => Number(row.views || 0))),
    [breakdown.external]
  );
  const maxSuggestedBrowse = useMemo(
    () => Math.max(1, Number(breakdown.suggested || 0), Number(breakdown.browse || 0)),
    [breakdown.suggested, breakdown.browse]
  );

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel>Channel</InputLabel>
          <Select
            label="Channel"
            value={accounts.includes(accountTag) ? accountTag : ""}
            onChange={(event) => setAccountTag(event.target.value)}
          >
            {accounts.map((acct) => (
              <MenuItem key={acct} value={acct}>
                {acct}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Typography variant="caption" color="text.secondary">
          {range.start && range.end ? "" : "No data"}
        </Typography>
      </Stack>

      {loading && (
        <Box display="flex" alignItems="center" gap={1}>
          <CircularProgress size={18} />
          <Typography variant="body2" color="text.secondary">
            Loading reach data...
          </Typography>
        </Box>
      )}

      <Box
        display="grid"
        gridTemplateColumns={{ xs: "1fr", md: "repeat(3, minmax(0, 1fr))" }}
        gap={2}
      >
        <Box
          sx={{
            p: 2,
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
          }}
        >
          <Stack direction="row" justifyContent="space-between" alignItems="baseline">
            <Box>
              <Typography variant="subtitle1" fontWeight={700}>
                External traffic
              </Typography>
            </Box>
            <Typography variant="caption" color="text.secondary">
              views
            </Typography>
          </Stack>
          {breakdown.external.length === 0 ? (
            <Typography variant="body2" color="text.secondary" mt={2}>
              No external traffic data.
            </Typography>
          ) : (
            <Stack spacing={1} mt={2}>
              {breakdown.external.map((row) => {
                const pct = Math.max(
                  6,
                  Math.round((row.views / maxExternal) * 100)
                );
                return (
                  <Box key={row.source}>
                    <Box display="flex" justifyContent="space-between" mb={0.5}>
                      <Typography variant="body2">{row.source}</Typography>
                      <Typography variant="body2" fontWeight={600}>
                        {formatNumber(row.views)}
                      </Typography>
                    </Box>
                    <Box
                      sx={{
                        height: 8,
                        borderRadius: 999,
                        bgcolor: isDark
                          ? "rgba(148,163,184,0.2)"
                          : "rgba(15,23,42,0.12)",
                        overflow: "hidden",
                      }}
                    >
                      <Box
                        sx={{
                          width: `${pct}%`,
                          height: "100%",
                          borderRadius: 999,
                          background: isDark
                            ? "linear-gradient(90deg, #38bdf8, #22d3ee)"
                            : "linear-gradient(90deg, #0ea5e9, #22d3ee)",
                        }}
                      />
                    </Box>
                  </Box>
                );
              })}
            </Stack>
          )}
        </Box>

        <Box
          sx={{
            p: 2,
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
          }}
        >
          <Stack direction="row" justifyContent="space-between" alignItems="baseline">
            <Box>
              <Typography variant="subtitle1" fontWeight={700}>
                Playlist traffic
              </Typography>
            </Box>
            <Typography variant="caption" color="text.secondary">
              views
            </Typography>
          </Stack>
          <Typography variant="h5" fontWeight={700} mt={2}>
            {formatNumber(breakdown.playlist)}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Views from playlist sources
          </Typography>
        </Box>

        <Box
          sx={{
            p: 2,
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
          }}
        >
          <Stack direction="row" justifyContent="space-between" alignItems="baseline">
            <Box>
              <Typography variant="subtitle1" fontWeight={700}>
                Suggested vs Browse
              </Typography>
            </Box>
            <Typography variant="caption" color="text.secondary">
              views
            </Typography>
          </Stack>
          <Stack spacing={1} mt={2}>
            {[
              { label: "Suggested", value: breakdown.suggested, color: "#22c55e" },
              { label: "Browse", value: breakdown.browse, color: "#a855f7" },
            ].map((item) => {
              const pct = Math.max(
                6,
                Math.round((Number(item.value || 0) / maxSuggestedBrowse) * 100)
              );
              return (
                <Box key={item.label}>
                  <Box display="flex" justifyContent="space-between" mb={0.5}>
                    <Typography variant="body2">{item.label}</Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {formatNumber(item.value)}
                    </Typography>
                  </Box>
                  <Box
                    sx={{
                      height: 8,
                      borderRadius: 999,
                      bgcolor: isDark
                        ? "rgba(148,163,184,0.2)"
                        : "rgba(15,23,42,0.12)",
                      overflow: "hidden",
                    }}
                  >
                    <Box
                      sx={{
                        width: `${pct}%`,
                        height: "100%",
                        borderRadius: 999,
                        background: isDark
                          ? `linear-gradient(90deg, ${item.color}, ${item.color}AA)`
                          : `linear-gradient(90deg, ${item.color}, ${item.color}AA)`,
                      }}
                    />
                  </Box>
                </Box>
              );
            })}
          </Stack>
        </Box>
      </Box>

      <TableContainer
        sx={{
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
          overflowX: "auto",
          overflowY: "hidden",
          "& .MuiTableCell-root": {
            px: 1,
            py: 0.6,
          },
        }}
      >
        <Table size="small" stickyHeader sx={{ minWidth: 1600 }}>
          <TableHead sx={headerSx}>
            <TableRow>
              <TableCell>Video</TableCell>
              <TableCell align="right">Views</TableCell>
              <TableCell align="right">Estimated minutes watched</TableCell>
              <TableCell align="right">Cards impressions</TableCell>
              <TableCell align="right">Teaser impressions</TableCell>
              <TableCell align="right">Total impressions</TableCell>
              <TableCell align="right">Cards clicks</TableCell>
              <TableCell align="right">Teaser clicks</TableCell>
              <TableCell align="right">Total clicks</TableCell>
              <TableCell align="right">Cards CTR</TableCell>
              <TableCell align="right">Teaser CTR</TableCell>
              <TableCell align="right">Total CTR</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {displayRows.map((row) => (
              <TableRow
                key={row.video_id}
                sx={{
                  "&:hover": {
                    backgroundColor: isDark
                      ? "rgba(51,65,85,0.55)"
                      : "rgba(226,232,240,0.6)",
                  },
                }}
              >
                <TableCell sx={{ minWidth: 260 }}>
                  <Stack direction="row" spacing={1.2} alignItems="flex-start">
                    {row.thumbnail ? (
                      <a
                        href={`https://www.youtube.com/watch?v=${row.video_id}`}
                        target="_blank"
                        rel="noreferrer"
                        style={{ display: "inline-flex" }}
                      >
                        <Box
                          component="img"
                          src={row.thumbnail}
                          alt={row.title || row.video_id}
                          sx={{
                            width: 72,
                            height: 42,
                            borderRadius: 1,
                            objectFit: "cover",
                            flexShrink: 0,
                          }}
                        />
                      </a>
                    ) : (
                      <Box
                        sx={{
                          width: 72,
                          height: 42,
                          borderRadius: 1,
                          bgcolor: isDark ? "rgba(148,163,184,0.2)" : "rgba(15,23,42,0.1)",
                          flexShrink: 0,
                        }}
                      />
                    )}
                    <Box>
                      <Typography variant="body2" fontWeight={600}>
                        <a
                          href={`https://www.youtube.com/watch?v=${row.video_id}`}
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: "inherit", textDecoration: "none" }}
                        >
                          {row.title || row.video_id}
                        </a>
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {row.video_id}
                      </Typography>
                    </Box>
                  </Stack>
                </TableCell>
                <TableCell align="right">{formatNumber(row.views)}</TableCell>
                <TableCell align="right">{formatNumber(row.estimated_minutes_watched)}</TableCell>
                <TableCell align="right">{formatNumber(row.card_impressions)}</TableCell>
                <TableCell align="right">{formatNumber(row.teaser_impressions)}</TableCell>
                <TableCell align="right">{formatNumber(row.total_impressions)}</TableCell>
                <TableCell align="right">{formatNumber(row.card_clicks)}</TableCell>
                <TableCell align="right">{formatNumber(row.teaser_clicks)}</TableCell>
                <TableCell align="right">{formatNumber(row.total_clicks)}</TableCell>
                <TableCell align="right">{formatPct(row.card_ctr)}</TableCell>
                <TableCell align="right">{formatPct(row.teaser_ctr)}</TableCell>
                <TableCell align="right">{formatPct(row.total_ctr)}</TableCell>
              </TableRow>
            ))}
            {!displayRows.length && !loading && (
              <TableRow>
                <TableCell colSpan={12}>
                  <Typography variant="body2" color="text.secondary">
                    No reach data available.
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

export default ReachAnalytics;
