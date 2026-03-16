import { useEffect, useMemo, useState } from "react";
import {
  Box,
  CircularProgress,
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
import { motion } from "framer-motion";
import InsertLinkIcon from "@mui/icons-material/InsertLink";
import PlaylistPlayIcon from "@mui/icons-material/PlaylistPlay";
import ExploreIcon from "@mui/icons-material/Explore";

import api from "../services/api";
import { formatNumber } from "./Module";
import { getChannelAvatarMap } from "./Module";
import ChannelSwitcher, { CHANNEL_SWITCHER_SX } from "./ChannelSwitcher";

const formatPct = (value) => {
  if (value === null || value === undefined) return "-";
  const num = Number(value);
  if (Number.isNaN(num)) return "-";
  return `${(num * 100).toFixed(2)}%`;
};

const ReachAnalytics = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  // === Styles ===
  const glassSx = useMemo(() => ({
    bgcolor: isDark ? "rgba(15, 23, 42, 0.65)" : "rgba(255, 255, 255, 0.8)",
    backdropFilter: "blur(12px)",
    borderRadius: 4,
    border: "1px solid",
    borderColor: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)",
    boxShadow: isDark ? "0 8px 32px rgba(0,0,0,0.4)" : "0 8px 24px rgba(15,23,42,0.08)",
  }), [isDark]);

  const headerSx = {
    background: isDark ? "#0f172a" : "#f1f5f9",
    "& .MuiTableCell-root": {
      fontWeight: 800,
      textTransform: "uppercase",
      letterSpacing: "0.05em",
      fontSize: "0.7rem",
      color: isDark ? "#e2e8f0" : "#0f172a",
      whiteSpace: "nowrap",
      py: 2,
      borderBottom: isDark ? "1px solid rgba(255,255,255,0.1)" : "1px solid rgba(0,0,0,0.1)",
    },
  };

  const authHeaders = useMemo(() => {
    const token = localStorage.getItem("access_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  // === State ===
  const [accounts, setAccounts] = useState([]);
  const [channelAvatarMap, setChannelAvatarMap] = useState({});
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
  // === Data Fetching ===
  useEffect(() => {
    const loadChannels = async () => {
      try {
        const resp = await api.get("/api/reach/channels", {
          headers: authHeaders,
        });
        const data = resp.data;
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

        // Sorting logic
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
        const byName = new Map(items.map((acct) => [orderKey(acct.value), acct]));
        const ordered = order
          .map((name) => byName.get(orderKey(name)))
          .filter(Boolean);
        const orderKeys = new Set(order.map(orderKey));
        const remaining = items.filter(
          (acct) => !orderKeys.has(orderKey(acct.value))
        );
        const finalAccounts = [...ordered, ...remaining];

        setAccounts(finalAccounts);
        if (!finalAccounts.length) {
          setAccountTag("");
        } else if (!accountTag || !finalAccounts.some((a) => a.value === accountTag)) {
          setAccountTag(finalAccounts[0].value);
        }
      } catch (err) {
        setAccounts([]);
      }
    };
    loadChannels();
  }, [accountTag, authHeaders]);

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
    if (!accountTag) return;
    try {
      localStorage.setItem("reach.selectedChannelId", accountTag);
    } catch {
      // ignore storage errors
    }
  }, [accountTag]);

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

  const displayRows = useMemo(() => rows.slice(0, 50), [rows]); // Increased limit slightly
  const maxExternal = useMemo(
    () => Math.max(1, ...breakdown.external.map((row) => Number(row.views || 0))),
    [breakdown.external]
  );
  const maxSuggestedBrowse = useMemo(
    () => Math.max(1, Number(breakdown.suggested || 0), Number(breakdown.browse || 0)),
    [breakdown.suggested, breakdown.browse]
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
    >
      <Stack spacing={3}>
        {/* Controls */}
        <Stack
          direction="row"
          spacing={2}
          alignItems="center"
          sx={{ flexWrap: "wrap", rowGap: 2 }}
        >
          <ChannelSwitcher
            options={accounts}
            value={accounts.some((acct) => acct.value === accountTag) ? accountTag : ""}
            onChange={(option) => setAccountTag(option?.value || "")}
            sx={CHANNEL_SWITCHER_SX}
            recentStorageKey="reachAnalytics.recentChannels"
            getOptionAvatar={(option) => channelAvatarMap[option?.value] || ""}
          />

          {loading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <Box display="flex" alignItems="center" gap={1} sx={{ color: "text.secondary" }}>
                <CircularProgress size={16} color="inherit" />
                <Typography variant="body2" sx={{ fontStyle: "italic" }}>
                  Refreshing data...
                </Typography>
              </Box>
            </motion.div>
          )}

          <Box sx={{ flexGrow: 1 }} />

          <Box sx={{
            px: 2, py: 0.5,
            borderRadius: 99,
            bgcolor: isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.04)",
            border: "1px solid",
            borderColor: isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.05)"
          }}>
            <Typography variant="caption" color="text.secondary" fontWeight={500}>
              {range.start && range.end
                ? `Range: ${range.start} ~ ${range.end}`
                : "No Date Range"}
            </Typography>
          </Box>
        </Stack>

        {/* Breakdown Cards */}
        <Box
          display="grid"
          gridTemplateColumns={{ xs: "1fr", md: "repeat(3, minmax(0, 1fr))" }}
          gap={3}
        >
          {/* External Traffic Card */}
          <Box sx={{ ...glassSx, p: 3, display: "flex", flexDirection: "column" }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
              <Stack direction="row" spacing={1} alignItems="center">
                <Box
                  sx={{
                    p: 0.8,
                    borderRadius: 1.5,
                    bgcolor: isDark ? "rgba(56, 189, 248, 0.15)" : "rgba(14, 165, 233, 0.1)",
                    color: isDark ? "#38bdf8" : "#0ea5e9",
                    display: "flex"
                  }}
                >
                  <InsertLinkIcon fontSize="small" />
                </Box>
                <Typography variant="subtitle1" fontWeight={700}>
                  External
                </Typography>
              </Stack>
              <Typography variant="caption" color="text.secondary" fontWeight={600} textTransform="uppercase">
                Top Sources
              </Typography>
            </Stack>

            {breakdown.external.length === 0 ? (
              <Box flex={1} display="flex" alignItems="center" justifyContent="center">
                <Typography variant="body2" color="text.secondary">
                  No external traffic data.
                </Typography>
              </Box>
            ) : (
              <Stack spacing={2} sx={{ mt: 1 }}>
                {breakdown.external.map((row) => {
                  const pct = Math.max(
                    6,
                    Math.round((row.views / maxExternal) * 100)
                  );
                  return (
                    <Box key={row.source}>
                      <Box display="flex" justifyContent="space-between" mb={0.5}>
                        <Typography variant="body2" fontWeight={600} sx={{ fontSize: "0.85rem" }}>
                          {row.source}
                        </Typography>
                        <Typography variant="body2" fontWeight={700}>
                          {formatNumber(row.views)}
                        </Typography>
                      </Box>
                      <Box
                        sx={{
                          height: 6,
                          borderRadius: 999,
                          bgcolor: isDark
                            ? "rgba(148,163,184,0.15)"
                            : "rgba(15,23,42,0.06)",
                          overflow: "hidden",
                        }}
                      >
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ duration: 0.8, ease: "easeOut" }}
                          style={{
                            height: "100%",
                            borderRadius: 999,
                            background: isDark
                              ? "linear-gradient(90deg, #38bdf8, #22d3ee)"
                              : "linear-gradient(90deg, #0ea5e9, #06b6d4)",
                          }}
                        />
                      </Box>
                    </Box>
                  );
                })}
              </Stack>
            )}
          </Box>

          {/* Playlist Traffic Card */}
          <Box sx={{ ...glassSx, p: 3, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
            <Stack direction="row" spacing={1} alignItems="center" mb={1}>
              <Box
                sx={{
                  p: 0.8,
                  borderRadius: 1.5,
                  bgcolor: isDark ? "rgba(244, 114, 182, 0.15)" : "rgba(236, 72, 153, 0.1)",
                  color: isDark ? "#f472b6" : "#ec4899",
                  display: "flex"
                }}
              >
                <PlaylistPlayIcon fontSize="small" />
              </Box>
              <Typography variant="subtitle1" fontWeight={700}>
                Playlist
              </Typography>
            </Stack>

            <Box mt={2} mb={1}>
              <Typography variant="h3" fontWeight={800} sx={{ letterSpacing: "-0.02em" }}>
                {formatNumber(breakdown.playlist)}
              </Typography>
              <Typography variant="body2" color="text.secondary" mt={0.5}>
                Total views from playlist sources within the selected range.
              </Typography>
            </Box>

            <Box sx={{
              mt: "auto",
              pt: 2,
              borderTop: "1px dashed",
              borderColor: theme.palette.divider
            }}>
              <Box display="flex" alignItems="center" gap={1}>
                <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: isDark ? "#f472b6" : "#ec4899" }} />
                <Typography variant="caption" fontWeight={600} color="text.secondary">
                  PLAYLIST TRAFFIC SOURCE
                </Typography>
              </Box>
            </Box>
          </Box>

          {/* Suggested vs Browse Card */}
          <Box sx={{ ...glassSx, p: 3, display: "flex", flexDirection: "column" }}>
            <Stack direction="row" spacing={1} alignItems="center" mb={2}>
              <Box
                sx={{
                  p: 0.8,
                  borderRadius: 1.5,
                  bgcolor: isDark ? "rgba(168, 85, 247, 0.15)" : "rgba(147, 51, 234, 0.1)",
                  color: isDark ? "#a855f7" : "#9333ea",
                  display: "flex"
                }}
              >
                <ExploreIcon fontSize="small" />
              </Box>
              <Typography variant="subtitle1" fontWeight={700}>
                Discovery
              </Typography>
            </Stack>

            <Stack spacing={3} sx={{ mt: 1 }}>
              {[
                { label: "Suggested Videos", value: breakdown.suggested, color: "#22c55e", bg: "rgba(34, 197, 94, 0.15)" },
                { label: "Browse Features", value: breakdown.browse, color: "#8b5cf6", bg: "rgba(139, 92, 246, 0.15)" },
              ].map((item) => {
                const pct = Math.max(
                  6,
                  Math.round((Number(item.value || 0) / maxSuggestedBrowse) * 100)
                );
                return (
                  <Box key={item.label}>
                    <Box display="flex" justifyContent="space-between" mb={1}>
                      <Typography variant="body2" fontWeight={600}>{item.label}</Typography>
                      <Typography variant="body2" fontWeight={800} sx={{ color: item.color }}>
                        {formatNumber(item.value)}
                      </Typography>
                    </Box>
                    <Box
                      sx={{
                        height: 10,
                        borderRadius: 999,
                        bgcolor: isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)",
                        overflow: "hidden",
                        position: "relative"
                      }}
                    >
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${pct}%` }}
                        transition={{ duration: 1.2, ease: "easeOut" }}
                        style={{
                          height: "100%",
                          borderRadius: 999,
                          background: item.color,
                          boxShadow: `0 0 10px ${item.color}66` // Glow effect
                        }}
                      />
                    </Box>
                  </Box>
                );
              })}
            </Stack>
          </Box>
        </Box>

        {/* Detailed Table */}
        <Box sx={{ ...glassSx, p: 1, overflow: "hidden" }}>
          <TableContainer sx={{ maxHeight: 800 }}>
            <Table size="small" stickyHeader>
              <TableHead sx={headerSx}>
                <TableRow>
                  <TableCell>Video</TableCell>
                  <TableCell align="right">Views</TableCell>
                  <TableCell align="right">Est. Minutes</TableCell>
                  <TableCell align="right">Card Imp.</TableCell>
                  <TableCell align="right">Teaser Imp.</TableCell>
                  <TableCell align="right">Total Imp.</TableCell>
                  <TableCell align="right">Card Clicks</TableCell>
                  <TableCell align="right">Teaser Clicks</TableCell>
                  <TableCell align="right">Total Clicks</TableCell>
                  <TableCell align="right">Card CTR</TableCell>
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
                          ? "rgba(255,255,255,0.05)"
                          : "rgba(0,0,0,0.04)",
                      },
                      transition: "background-color 0.2s"
                    }}
                  >
                    <TableCell sx={{ minWidth: 360, py: 2 }}>
                      <Stack direction="row" spacing={2} alignItems="flex-start">
                        {row.thumbnail ? (
                          <a
                            href={`https://www.youtube.com/watch?v=${row.video_id}`}
                            target="_blank"
                            rel="noreferrer"
                            style={{ display: "inline-block", position: "relative", borderRadius: 8, overflow: "hidden", boxShadow: "0 4px 12px rgba(0,0,0,0.2)" }}
                          >
                            <Box
                              component="img"
                              src={row.thumbnail}
                              alt={row.title || row.video_id}
                              sx={{
                                width: 120,
                                height: 68,
                                objectFit: "cover",
                                display: "block"
                              }}
                            />
                            <Box sx={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", bgcolor: "rgba(0,0,0,0.1)", opacity: 0, "&:hover": { opacity: 1 }, transition: "opacity 0.2s" }} />
                          </a>
                        ) : (
                          <Box
                            sx={{
                              width: 120,
                              height: 68,
                              borderRadius: 1,
                              bgcolor: isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)",
                              flexShrink: 0,
                            }}
                          />
                        )}
                        <Box sx={{ minWidth: 0 }}>
                          <Typography
                            variant="body2"
                            fontWeight={600}
                            sx={{
                              display: "-webkit-box",
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: "vertical",
                              overflow: "hidden",
                              lineHeight: 1.2,
                              mb: 0.5
                            }}
                          >
                            <a
                              href={`https://www.youtube.com/watch?v=${row.video_id}`}
                              target="_blank"
                              rel="noreferrer"
                              style={{ color: "inherit", textDecoration: "none" }}
                            >
                              {row.title || row.video_id}
                            </a>
                          </Typography>
                          <Typography variant="caption" color="text.secondary" sx={{ fontFamily: "monospace", bgcolor: isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)", px: 0.5, borderRadius: 0.5 }}>
                            {row.video_id}
                          </Typography>
                        </Box>
                      </Stack>
                    </TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600 }}>{formatNumber(row.views)}</TableCell>
                    <TableCell align="right">{formatNumber(row.estimated_minutes_watched)}</TableCell>
                    <TableCell align="right">{formatNumber(row.card_impressions)}</TableCell>
                    <TableCell align="right">{formatNumber(row.teaser_impressions)}</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600 }}>{formatNumber(row.total_impressions)}</TableCell>
                    <TableCell align="right">{formatNumber(row.card_clicks)}</TableCell>
                    <TableCell align="right">{formatNumber(row.teaser_clicks)}</TableCell>
                    <TableCell align="right">{formatNumber(row.total_clicks)}</TableCell>
                    <TableCell align="right">{formatPct(row.card_ctr)}</TableCell>
                    <TableCell align="right">{formatPct(row.teaser_ctr)}</TableCell>
                    <TableCell align="right" sx={{ color: isDark ? "#4ade80" : "#16a34a", fontWeight: 700 }}>
                      {formatPct(row.total_ctr)}
                    </TableCell>
                  </TableRow>
                ))}
                {!displayRows.length && !loading && (
                  <TableRow>
                    <TableCell colSpan={12} align="center" sx={{ py: 8 }}>
                      <Typography variant="body1" color="text.secondary">
                        No data available for the selected channel.
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      </Stack>
    </motion.div>
  );
};

export default ReachAnalytics;
