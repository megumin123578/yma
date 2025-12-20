import { useEffect, useState } from "react";
import {
  Avatar,
  Box,
  Button,
  CircularProgress,
  Grid,
  Paper,
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

  useEffect(() => {
    loadSavedChannels();
  }, []);

  const stats = channel?.statistics || {};
  const subsHidden =
    stats.hiddenSubscriberCount === true ||
    stats.hiddenSubscriberCount === "true";

  return (
    <Stack spacing={2}>
      <Paper elevation={0} sx={{ p: 2, borderRadius: 2 }}>
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
              sx={{ minWidth: 260, flexGrow: 1 }}
            />

            <Button type="submit" variant="contained" disabled={loading}>
              {loading ? "Loading..." : "Load"}
            </Button>
            <Button
              type="button"
              variant="outlined"
              disabled={!channel || saving}
              onClick={handleSave}
            >
              {saving ? "Saving..." : "Save"}
            </Button>
          </Stack>
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
          <Paper elevation={0} sx={{ p: 2, borderRadius: 2 }}>
            <Stack spacing={2}>
              <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
                <Avatar
                  src={pickThumb(channel.thumbnails)}
                  alt={channel.title}
                  sx={{ width: 72, height: 72 }}
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
                <Grid item xs={12} sm={6} md={3}>
                  <StatCard label="Country" value={channel.country || "-"} />
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

          <TableContainer component={Paper} elevation={0} sx={{ borderRadius: 2 }}>
            <Table size="small">
              <TableHead>
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
                  <TableRow key={v.videoId}>
                    <TableCell>
                      <a
                        href={`https://www.youtube.com/watch?v=${v.videoId}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {v.title}
                      </a>
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

          <TableContainer component={Paper} elevation={0} sx={{ borderRadius: 2 }}>
            <Table size="small">
              <TableHead>
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
                  <TableRow key={v.videoId}>
                    <TableCell>
                      <a
                        href={`https://www.youtube.com/watch?v=${v.videoId}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {v.title}
                      </a>
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

      {!!savedChannels.length && (
        <TableContainer component={Paper} elevation={0} sx={{ borderRadius: 2 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Saved channels</TableCell>
                <TableCell>Channel ID</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {savedChannels.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>{row.channel_name || "-"}</TableCell>
                  <TableCell>{row.channel_id}</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={1}>
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => {
                          setQuery(row.channel_id);
                          fetchChannel(row.channel_id);
                        }}
                      >
                        Load
                      </Button>
                      <Button
                        size="small"
                        color="error"
                        variant="text"
                        onClick={() => handleDelete(row.channel_id)}
                      >
                        Remove
                      </Button>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Stack>
  );
};

const StatCard = ({ label, value }) => (
  <Paper
    elevation={0}
    sx={{
      p: 1.5,
      borderRadius: 2,
      border: "1px solid",
      borderColor: "divider",
      height: "100%",
    }}
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
