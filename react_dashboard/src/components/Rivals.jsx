import { useEffect, useState } from "react";
import {
  Avatar,
  Box,
  Button,
  CircularProgress,
  FormControl,
  Grid,
  IconButton,
  InputLabel,
  ListItemText,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { API_BASE } from "../config";
import { formatNumber } from "./Module";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";

const pickThumb = (thumbs) =>
  thumbs?.high?.url || thumbs?.medium?.url || thumbs?.default?.url || "";

const formatStat = (value) =>
  value === undefined || value === null ? "-" : formatNumber(value);

const toDate = (iso) => {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const day = String(d.getDate()).padStart(2, "0");
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const year = String(d.getFullYear());
  return `${day}/${month}/${year}`;
};

const fadeUpSx = {
  animation: "rivalsFadeUp 0.55s ease-out",
  "@keyframes rivalsFadeUp": {
    "0%": { opacity: 0, transform: "translateY(14px)" },
    "100%": { opacity: 1, transform: "translateY(0)" },
  },
};

const RivalsChannel = () => {
  const [query, setQuery] = useState("");
  const [channel, setChannel] = useState(null);
  const [videos, setVideos] = useState([]);
  const [shorts, setShorts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [savedChannels, setSavedChannels] = useState([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [selectedSavedId, setSelectedSavedId] = useState("");

  const fetchChannel = async (q) => {
    try {
      setLoading(true);
      setError("");
      setChannel(null);
      setVideos([]);
      setShorts([]);

      const resp = await fetch(
        `${API_BASE}/api/youtube/channel?query=${encodeURIComponent(q)}`
      );
      if (!resp.ok) throw new Error((await resp.text()) || `HTTP ${resp.status}`);
      const data = await resp.json();
      setChannel(data.channel || null);
      setVideos(Array.isArray(data.videos) ? data.videos : []);
      setShorts(Array.isArray(data.shorts) ? data.shorts : []);
    } catch (e) {
      setError(e?.message || "Failed to load channel data");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const q = query.trim();
    if (!q) {
      setError("Please enter a channel ID or URL");
      return;
    }
    fetchChannel(q);
  };

  const loadSavedChannels = async () => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setSavedChannels([]);
      return;
    }
    try {
      const resp = await fetch(`${API_BASE}/api/users/rivals`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) throw new Error((await resp.text()) || `HTTP ${resp.status}`);
      const data = await resp.json();
      setSavedChannels(Array.isArray(data) ? data : []);
    } catch {
      setSavedChannels([]);
    }
  };

  const handleSave = async () => {
    if (!channel?.id) return;
    const token = localStorage.getItem("access_token");
    if (!token) {
      setSaveError("Please login to save channels.");
      return;
    }

    const channelUrl = channel.customUrl
      ? `https://www.youtube.com/${channel.customUrl}`
      : `https://www.youtube.com/channel/${channel.id}`;

    try {
      setSaving(true);
      setSaveError("");
      const resp = await fetch(`${API_BASE}/api/users/rivals`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          channel_id: channel.id,
          channel_name: channel.title,
          channel_url: channelUrl,
          channel_avatar_url: pickThumb(channel.thumbnails),
        }),
      });
      if (!resp.ok) throw new Error((await resp.text()) || `HTTP ${resp.status}`);
      await loadSavedChannels();
    } catch (e) {
      setSaveError(e?.message || "Failed to save channel");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (channelId) => {
    const token = localStorage.getItem("access_token");
    if (!token) return;
    try {
      const resp = await fetch(
        `${API_BASE}/api/users/rivals/${encodeURIComponent(channelId)}`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!resp.ok) throw new Error((await resp.text()) || `HTTP ${resp.status}`);
      await loadSavedChannels();
    } catch {
      // ignore delete errors
    }
  };

  const handleRemoveSaved = (row) => {
    if (!row?.channel_id) return;
    const ok = window.confirm(`Remove "${row.channel_name || row.channel_id}"?`);
    if (ok) {
      handleDelete(row.channel_id);
    }
  };

  const handleSavedSelect = (value) => {
    setSelectedSavedId(value);
    if (!value) return;
    setQuery(value);
    fetchChannel(value);
  };

  useEffect(() => {
    loadSavedChannels();
  }, []);

  useEffect(() => {
    if (
      selectedSavedId &&
      !savedChannels.some((row) => row.channel_id === selectedSavedId)
    ) {
      setSelectedSavedId("");
    }
  }, [savedChannels, selectedSavedId]);

  const stats = channel?.statistics || {};
  const subsHidden =
    stats.hiddenSubscriberCount === true ||
    stats.hiddenSubscriberCount === "true";

  return (
    <Stack spacing={2}>
      <Paper
        elevation={0}
        sx={(theme) => ({
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
          ...fadeUpSx,
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
        })}
      >
        <Stack spacing={1.5} component="form" onSubmit={handleSubmit}>
          <Typography variant="h6" fontWeight={700}>
            Channel lookup
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Enter a YouTube channel ID or URL.
          </Typography>

          <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap">
            <TextField
              size="small"
              label="Channel ID / URL"
              placeholder="https://www.youtube.com/channel/UC..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              sx={(theme) => ({
                minWidth: 260,
                flexGrow: 1,
                "& .MuiOutlinedInput-root": {
                  backgroundColor:
                    theme.palette.mode === "dark"
                      ? "rgba(15,23,42,0.45)"
                      : "rgba(255,255,255,0.9)",
                  borderRadius: 2,
                  transition: "box-shadow 0.2s ease, transform 0.2s ease",
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
              })}
            />

            <Button
              type="submit"
              variant="contained"
              color="warning"
              disabled={loading}
              sx={(theme) => ({
                textTransform: "none",
                fontWeight: 700,
                borderRadius: 2,
                px: 2.4,
                position: "relative",
                overflow: "hidden",
                color: theme.palette.mode === "dark" ? "#1f2937" : "#1f2937",
                backgroundColor:
                  theme.palette.mode === "dark" ? "#facc15" : "#fbbf24",
                boxShadow:
                  theme.palette.mode === "dark"
                    ? "0 12px 20px rgba(15,23,42,0.35)"
                    : "0 12px 20px rgba(15,23,42,0.22)",
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
                  boxShadow:
                    theme.palette.mode === "dark"
                      ? "0 16px 26px rgba(15,23,42,0.45)"
                      : "0 16px 26px rgba(15,23,42,0.28)",
                  backgroundColor:
                    theme.palette.mode === "dark" ? "#fde047" : "#f59e0b",
                },
                "&:hover:before": {
                  transform: "translateX(0%)",
                },
              })}
            >
              {loading ? "Loading..." : "Load"}
            </Button>
            <Button
              type="button"
              variant="contained"
              color="success"
              disabled={!channel || saving}
              onClick={handleSave}
              sx={(theme) => ({
                textTransform: "none",
                fontWeight: 700,
                borderRadius: 2,
                px: 2.2,
                color: theme.palette.mode === "dark" ? "#052e16" : "#052e16",
                backgroundColor:
                  theme.palette.mode === "dark" ? "#22c55e" : "#16a34a",
                position: "relative",
                overflow: "hidden",
                transition: "transform 0.2s ease, box-shadow 0.2s ease",
                "&:after": {
                  content: '""',
                  position: "absolute",
                  inset: 0,
                  background:
                    theme.palette.mode === "dark"
                      ? "linear-gradient(120deg, rgba(34,197,94,0.18), rgba(56,189,248,0.12))"
                      : "linear-gradient(120deg, rgba(34,197,94,0.14), rgba(59,130,246,0.12))",
                  opacity: 0,
                  transition: "opacity 0.3s ease",
                },
                "&:hover": {
                  transform: "translateY(-1px)",
                  boxShadow:
                    theme.palette.mode === "dark"
                      ? "0 14px 22px rgba(15,23,42,0.35)"
                      : "0 14px 22px rgba(15,23,42,0.2)",
                  backgroundColor:
                    theme.palette.mode === "dark" ? "#4ade80" : "#15803d",
                },
                "&:hover:after": {
                  opacity: 1,
                },
              })}
            >
              {saving ? "Saving..." : "Save"}
            </Button>
          </Stack>

          {!!savedChannels.length && (
            <Stack spacing={1} sx={{ pt: 0.5 }}>
              <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap">
                <FormControl
                  size="small"
                  sx={(theme) => ({
                    minWidth: 240,
                    flexGrow: 1,
                    "& .MuiOutlinedInput-root": {
                      backgroundColor:
                        theme.palette.mode === "dark"
                          ? "rgba(15,23,42,0.45)"
                          : "rgba(255,255,255,0.9)",
                      borderRadius: 2,
                      transition: "box-shadow 0.2s ease, transform 0.2s ease",
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
                  })}
                >
                  <InputLabel id="saved-channels-label">Saved channels</InputLabel>
                  <Select
                    labelId="saved-channels-label"
                    value={selectedSavedId}
                    label="Saved channels"
                    onChange={(e) => handleSavedSelect(e.target.value)}
                    renderValue={(value) => {
                      const row = savedChannels.find((item) => item.channel_id === value);
                      return row?.channel_name || value || "";
                    }}
                  >
                    <MenuItem value="">
                      <em>Select saved channel</em>
                    </MenuItem>
                    {savedChannels.map((row) => (
                      <MenuItem
                        key={row.id}
                        value={row.channel_id}
                        sx={{ pr: 1 }}
                      >
                        <Avatar
                          src={row.channel_avatar_url || ""}
                          alt={row.channel_name || row.channel_id}
                          sx={{
                            width: 28,
                            height: 28,
                            mr: 1,
                            bgcolor: "rgba(148,163,184,0.4)",
                            fontSize: "0.75rem",
                            fontWeight: 700,
                          }}
                        >
                          {(row.channel_name || row.channel_id || "?")
                            .trim()
                            .charAt(0)
                            .toUpperCase()}
                        </Avatar>
                        <ListItemText
                          primary={row.channel_name || row.channel_id}
                          secondary={row.channel_name ? row.channel_id : undefined}
                        />
                        <IconButton
                          size="small"
                          edge="end"
                          color="error"
                          onMouseDown={(e) => e.stopPropagation()}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRemoveSaved(row);
                          }}
                          aria-label={`Remove ${row.channel_name || row.channel_id}`}
                        >
                          <CloseRoundedIcon fontSize="small" />
                        </IconButton>
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Stack>
            </Stack>
          )}
        </Stack>
      </Paper>

      {error && (
        <Typography color="error" variant="body2">
          {error}
        </Typography>
      )}

      {saveError && (
        <Typography color="error" variant="body2">
          {saveError}
        </Typography>
      )}

      {loading && (
        <Box display="flex" justifyContent="center" mt={2}>
          <CircularProgress />
        </Box>
      )}

      {!loading && channel && (
        <Stack spacing={2}>
          <Paper
            elevation={0}
            sx={(theme) => ({
              p: 2.5,
              borderRadius: 3,
              border: "1px solid",
              borderColor:
                theme.palette.mode === "dark"
                  ? "rgba(148,163,184,0.2)"
                  : "rgba(15,23,42,0.12)",
              background:
                theme.palette.mode === "dark"
                  ? "linear-gradient(140deg, rgba(15,23,42,0.9) 0%, rgba(30,41,59,0.88) 60%, rgba(16,185,129,0.25) 100%)"
                  : "linear-gradient(140deg, rgba(255,255,255,0.92) 0%, rgba(226,232,240,0.95) 60%, rgba(191,219,254,0.6) 100%)",
              boxShadow:
                theme.palette.mode === "dark"
                  ? "0 18px 30px rgba(15,23,42,0.35)"
                  : "0 18px 30px rgba(148,163,184,0.3)",
              position: "relative",
              overflow: "hidden",
              ...fadeUpSx,
            })}
          >
            <Stack spacing={2}>
              <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
                <Avatar
                  src={pickThumb(channel.thumbnails)}
                  alt={channel.title}
                  sx={{
                    width: 72,
                    height: 72,
                    border: "2px solid rgba(255,255,255,0.4)",
                    boxShadow: "0 14px 26px rgba(15,23,42,0.45)",
                    animation: "rivalsFloat 4.5s ease-in-out infinite",
                    "@keyframes rivalsFloat": {
                      "0%": { transform: "translateY(0)" },
                      "50%": { transform: "translateY(-6px)" },
                      "100%": { transform: "translateY(0)" },
                    },
                  }}
                />
                <Box>
                  <Typography variant="h6" fontWeight={700}>
                    {channel.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {channel.customUrl || channel.id}
                  </Typography>
                </Box>
              </Stack>

              <Grid container spacing={2}>
                <Grid item xs={12} sm={6} md={3}>
                  <StatCard label="Subscribers" value={subsHidden ? "Hidden" : formatStat(stats.subscriberCount)} />
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <StatCard label="Total views" value={formatStat(stats.viewCount)} />
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <StatCard label="Total videos" value={formatStat(stats.videoCount)} />
                </Grid>
              </Grid>

              <Typography variant="body2" color="text.secondary">
                Published: {toDate(channel.publishedAt)}
              </Typography>

              {channel.description && (
                <Typography variant="body2">{channel.description}</Typography>
              )}
            </Stack>
          </Paper>

          <TableContainer
            component={Paper}
            elevation={0}
            sx={(theme) => ({
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
              ...fadeUpSx,
              "& a": {
                color: theme.palette.mode === "dark" ? "#7dd3fc" : "#0ea5e9",
                textDecoration: "none",
                fontWeight: 600,
              },
              "& a:hover": {
                textDecoration: "underline",
              },
            })}
          >
            <Table size="small">
              <TableHead
                sx={(theme) => ({
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
                })}
              >
                <TableRow>
                  <TableCell>Latest videos</TableCell>
                  <TableCell>Published</TableCell>
                  <TableCell align="right">Views</TableCell>
                  <TableCell align="right">Likes</TableCell>
                  <TableCell align="right">Comments</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {videos.map((v) => (
                  <TableRow
                    key={v.videoId}
                    sx={(theme) => ({
                      transition: "transform 0.2s ease, background-color 0.2s ease",
                      "&:hover": {
                        backgroundColor:
                          theme.palette.mode === "dark"
                            ? "rgba(51,65,85,0.55)"
                            : "rgba(226,232,240,0.6)",
                        transform: "translateY(-1px)",
                      },
                    })}
                  >
                    <TableCell>
                      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                        <a
                          href={`https://www.youtube.com/watch?v=${v.videoId}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {v.title}
                        </a>
                      </Stack>
                    </TableCell>
                    <TableCell>{toDate(v.publishedAt)}</TableCell>
                    <TableCell align="right">{formatNumber(v.views)}</TableCell>
                    <TableCell align="right">{formatNumber(v.likes)}</TableCell>
                    <TableCell align="right">{formatNumber(v.comments)}</TableCell>
                  </TableRow>
                ))}
                {!videos.length && (
                  <TableRow>
                    <TableCell colSpan={5}>
                      <Typography variant="body2" color="text.secondary">
                        No recent videos found.
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>

          <TableContainer
            component={Paper}
            elevation={0}
            sx={(theme) => ({
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
              ...fadeUpSx,
              "& a": {
                color: theme.palette.mode === "dark" ? "#7dd3fc" : "#0ea5e9",
                textDecoration: "none",
                fontWeight: 600,
              },
              "& a:hover": {
                textDecoration: "underline",
              },
            })}
          >
            <Table size="small">
              <TableHead
                sx={(theme) => ({
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
                })}
              >
                <TableRow>
                  <TableCell>Latest shorts</TableCell>
                  <TableCell>Published</TableCell>
                  <TableCell align="right">Views</TableCell>
                  <TableCell align="right">Likes</TableCell>
                  <TableCell align="right">Comments</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {shorts.map((v) => (
                  <TableRow
                    key={v.videoId}
                    sx={(theme) => ({
                      transition: "transform 0.2s ease, background-color 0.2s ease",
                      "&:hover": {
                        backgroundColor:
                          theme.palette.mode === "dark"
                            ? "rgba(51,65,85,0.55)"
                            : "rgba(226,232,240,0.6)",
                        transform: "translateY(-1px)",
                      },
                    })}
                  >
                    <TableCell>
                      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                        <a
                          href={`https://www.youtube.com/watch?v=${v.videoId}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {v.title}
                        </a>
                      </Stack>
                    </TableCell>
                    <TableCell>{toDate(v.publishedAt)}</TableCell>
                    <TableCell align="right">{formatNumber(v.views)}</TableCell>
                    <TableCell align="right">{formatNumber(v.likes)}</TableCell>
                    <TableCell align="right">{formatNumber(v.comments)}</TableCell>
                  </TableRow>
                ))}
                {!shorts.length && (
                  <TableRow>
                    <TableCell colSpan={5}>
                      <Typography variant="body2" color="text.secondary">
                        No recent shorts found.
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Stack>
      )}

    </Stack>
  );
};

const StatCard = ({ label, value }) => (
  <Paper
    elevation={0}
    sx={(theme) => ({
      p: 1.7,
      borderRadius: 2.5,
      border: "1px solid",
      borderColor:
        theme.palette.mode === "dark"
          ? "rgba(148,163,184,0.25)"
          : "rgba(148,163,184,0.35)",
      height: "100%",
      background:
        theme.palette.mode === "dark"
          ? "linear-gradient(160deg, rgba(30,41,59,0.9) 0%, rgba(15,23,42,0.85) 100%)"
          : "linear-gradient(160deg, rgba(255,255,255,0.95) 0%, rgba(226,232,240,0.9) 100%)",
      boxShadow:
        theme.palette.mode === "dark"
          ? "0 10px 20px rgba(15,23,42,0.4)"
          : "0 10px 20px rgba(148,163,184,0.25)",
      transition: "transform 0.2s ease, box-shadow 0.2s ease",
      "&:hover": {
        transform: "translateY(-2px)",
        boxShadow:
          theme.palette.mode === "dark"
            ? "0 16px 26px rgba(15,23,42,0.5)"
            : "0 16px 26px rgba(148,163,184,0.35)",
      },
    })}
  >
    <Typography variant="caption" color="text.secondary">
      {label}
    </Typography>
    <Typography variant="h6" fontWeight={700}>
      {value ?? "-"}
    </Typography>
  </Paper>
);

export default RivalsChannel;
