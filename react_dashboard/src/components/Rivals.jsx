import { useEffect, useMemo, useState } from "react";
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
  Menu,
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
  useTheme,
} from "@mui/material";
import { API_BASE } from "../config";
import { formatNumber } from "./Module";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import CheckRoundedIcon from "@mui/icons-material/CheckRounded";
import GroupWorkOutlinedIcon from "@mui/icons-material/GroupWorkOutlined";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

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

const STORAGE_KEY = "rivals.ui.state";

const loadUiState = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
};

const RivalsChannel = ({ viewMode = "list" }) => {
  const theme = useTheme();
  const initialState = loadUiState();
  const [query, setQuery] = useState(initialState.query || "");
  const [channel, setChannel] = useState(null);
  const [videos, setVideos] = useState([]);
  const [shorts, setShorts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [savedChannels, setSavedChannels] = useState([]);
  const [savedLoaded, setSavedLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [assignGroup, setAssignGroup] = useState(initialState.assignGroup || "");
  const [newGroupName, setNewGroupName] = useState(
    initialState.newGroupName || ""
  );
  const [filterGroup, setFilterGroup] = useState(initialState.filterGroup || "");
  const [assignError, setAssignError] = useState("");
  const [selectedSavedId, setSelectedSavedId] = useState(
    initialState.selectedSavedId || ""
  );
  const [groupMenuAnchor, setGroupMenuAnchor] = useState(null);
  const [groupMenuChannel, setGroupMenuChannel] = useState(null);

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
      setSavedLoaded(true);
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
    } finally {
      setSavedLoaded(true);
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
    const row = savedChannels.find((item) => item.channel_id === value);
    setAssignGroup(row?.group_name || "");
    setNewGroupName("");
    setQuery(value);
    fetchChannel(value);
  };

  useEffect(() => {
    loadSavedChannels();
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          query,
          selectedSavedId,
          assignGroup,
          newGroupName,
          filterGroup,
        })
      );
    } catch {
      // ignore storage errors
    }
  }, [query, selectedSavedId, assignGroup, newGroupName, filterGroup]);

  const missingSelected =
    !!selectedSavedId &&
    !savedChannels.some((row) => row.channel_id === selectedSavedId);

  useEffect(() => {
    if (savedLoaded && selectedSavedId && !channel) {
      setQuery(selectedSavedId);
      const row = savedChannels.find((item) => item.channel_id === selectedSavedId);
      setAssignGroup(row?.group_name || "");
      setNewGroupName("");
      fetchChannel(selectedSavedId);
    }
  }, [savedLoaded, selectedSavedId, channel, savedChannels]);

  const groupOptions = useMemo(() => {
    const unique = new Set();
    savedChannels.forEach((row) => {
      const value = (row.group_name || "").trim();
      if (value) unique.add(value);
    });
    if (assignGroup === "__new__") {
      const fresh = (newGroupName || "").trim();
      if (fresh) unique.add(fresh);
    }
    return Array.from(unique).sort((a, b) => a.localeCompare(b));
  }, [savedChannels, assignGroup, newGroupName]);

  const filteredSavedChannels = useMemo(() => {
    const needle = (filterGroup || "").trim();
    if (!needle) return savedChannels;
    return savedChannels.filter(
      (row) => (row.group_name || "").trim() === needle
    );
  }, [savedChannels, filterGroup]);

  useEffect(() => {
    if (!filterGroup) return;
    if (!selectedSavedId) return;
    const stillVisible = filteredSavedChannels.some(
      (row) => row.channel_id === selectedSavedId
    );
    if (!stillVisible) {
      setSelectedSavedId("");
    }
  }, [filterGroup, filteredSavedChannels, selectedSavedId]);

  const closeGroupMenu = () => {
    setGroupMenuAnchor(null);
    setGroupMenuChannel(null);
  };

  const openGroupMenu = (event, row) => {
    setGroupMenuAnchor(event.currentTarget);
    setGroupMenuChannel(row);
  };

  const updateChannelGroup = async (channelId, groupName) => {
    if (!channelId) return;
    const token = localStorage.getItem("access_token");
    if (!token) {
      setAssignError("Please login to update groups.");
      return;
    }
    try {
      setAssignError("");
      const resp = await fetch(`${API_BASE}/api/users/rivals`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          channel_id: channelId,
          group_name: groupName || null,
        }),
      });
      if (!resp.ok) throw new Error((await resp.text()) || `HTTP ${resp.status}`);
      const updatedRow = await resp.json();
      if (updatedRow?.channel_id) {
        setSavedChannels((prev) =>
          prev.map((row) =>
            row.channel_id === updatedRow.channel_id
              ? { ...row, ...updatedRow }
              : row
          )
        );
      } else {
        await loadSavedChannels();
      }
      if (selectedSavedId === channelId) {
        setAssignGroup(groupName || "");
      }
    } catch (e) {
      setAssignError(e?.message || "Failed to update group");
    }
  };

  const deleteGroup = async (groupName) => {
    const name = (groupName || "").trim();
    if (!name) return;
    const token = localStorage.getItem("access_token");
    if (!token) {
      setAssignError("Please login to update groups.");
      return;
    }
    const ok = window.confirm(`Delete group "${name}" from all channels?`);
    if (!ok) return;
    try {
      setAssignError("");
      const resp = await fetch(
        `${API_BASE}/api/users/rivals/groups/${encodeURIComponent(name)}`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!resp.ok) throw new Error((await resp.text()) || `HTTP ${resp.status}`);
      setSavedChannels((prev) =>
        prev.map((row) =>
          row.group_name === name ? { ...row, group_name: null } : row
        )
      );
      if (filterGroup === name) {
        setFilterGroup("");
      }
      if (selectedSavedId) {
        const selectedRow = savedChannels.find(
          (row) => row.channel_id === selectedSavedId
        );
        if (selectedRow?.group_name === name) {
          setAssignGroup("");
        }
      }
    } catch (e) {
      setAssignError(e?.message || "Failed to delete group");
    }
  };

  const stats = channel?.statistics || {};
  const subsHidden =
    stats.hiddenSubscriberCount === true ||
    stats.hiddenSubscriberCount === "true";

  const toChartRows = (items) =>
    items
      .map((v) => ({
        name: v.title || "Untitled",
        date: toDate(v.publishedAt),
        publishedAt: v.publishedAt || "",
        views: Number(v.views || 0),
        likes: Number(v.likes || 0),
        comments: Number(v.comments || 0),
      }))
      .sort((a, b) => new Date(a.publishedAt) - new Date(b.publishedAt));

  const videoChartData = useMemo(() => toChartRows(videos), [videos]);
  const shortChartData = useMemo(() => toChartRows(shorts), [shorts]);

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
          transition: "transform 0.2s ease, box-shadow 0.2s ease",
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
          "&:hover": {
            transform: "translateY(-3px)",
            boxShadow:
              theme.palette.mode === "dark"
                ? "0 22px 38px rgba(15,23,42,0.5)"
                : "0 22px 34px rgba(148,163,184,0.45)",
          },
        })}
      >
        <Stack spacing={1.5} component="form" onSubmit={handleSubmit}>
          <Stack
            direction="row"
            spacing={1.5}
            alignItems="center"
            flexWrap="wrap"
            justifyContent="space-between"
          >
            <Typography variant="h6" fontWeight={700}>
              Channel lookup
            </Typography>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
              <Button
                type="button"
                variant="outlined"
                size="small"
                onClick={() => {
                  setAssignGroup("__new__");
                  setNewGroupName("");
                }}
                sx={{ textTransform: "none", borderRadius: 2 }}
              >
                Create group
              </Button>
              {assignGroup === "__new__" && (
                <TextField
                  size="small"
                  label="New group"
                  placeholder="Group name"
                  value={newGroupName}
                  onChange={(e) => setNewGroupName(e.target.value)}
                  sx={(theme) => ({
                    minWidth: 180,
                    "& .MuiOutlinedInput-root": {
                      backgroundColor:
                        theme.palette.mode === "dark"
                          ? "rgba(15,23,42,0.45)"
                          : "rgba(255,255,255,0.9)",
                      borderRadius: 2,
                    },
                  })}
                />
              )}
            </Stack>
          </Stack>
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
                    minWidth: 180,
                    "& .MuiOutlinedInput-root": {
                      backgroundColor:
                        theme.palette.mode === "dark"
                          ? "rgba(15,23,42,0.45)"
                          : "rgba(255,255,255,0.9)",
                      borderRadius: 2,
                    },
                  })}
                >
                  <InputLabel id="filter-group-label">Group</InputLabel>
                  <Select
                    labelId="filter-group-label"
                    value={filterGroup}
                    label="Group"
                    onChange={(e) => setFilterGroup(e.target.value)}
                    renderValue={(value) => value || "All groups"}
                  >
                    <MenuItem value="">
                      <em>All groups</em>
                    </MenuItem>
                  {groupOptions.map((group) => (
                    <MenuItem key={group} value={group}>
                      <ListItemText primary={group} />
                      <IconButton
                        size="small"
                        edge="end"
                        aria-label={`Delete group ${group}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteGroup(group);
                        }}
                      >
                        <CloseRoundedIcon fontSize="small" />
                      </IconButton>
                    </MenuItem>
                  ))}
                  </Select>
                </FormControl>
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
                      if (row) return row.channel_name || row.channel_id;
                      if (missingSelected) return `Missing: ${value}`;
                      return value || "";
                    }}
                  >
                    <MenuItem value="">
                      <em>Select saved channel</em>
                    </MenuItem>
                    {missingSelected && (
                      <MenuItem value={selectedSavedId}>
                        <ListItemText
                          primary={`Missing: ${selectedSavedId}`}
                          secondary="Channel not in saved list"
                        />
                      </MenuItem>
                    )}
                    {filteredSavedChannels.map((row) => (
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
                          secondary={
                            row.group_name
                              ? `${row.group_name}${row.channel_name ? " - " : ""}${row.channel_name ? row.channel_id : ""}`
                              : row.channel_name
                                ? row.channel_id
                                : undefined
                          }
                        />
                        <IconButton
                          size="small"
                          edge="end"
                          onMouseDown={(e) => e.stopPropagation()}
                          onClick={(e) => {
                            e.stopPropagation();
                            openGroupMenu(e, row);
                          }}
                          aria-label={`Add ${row.channel_name || row.channel_id} to group`}
                          sx={{ mr: 0.5 }}
                        >
                          <GroupWorkOutlinedIcon fontSize="small" />
                        </IconButton>
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
                <Menu
                  anchorEl={groupMenuAnchor}
                  open={Boolean(groupMenuAnchor)}
                  onClose={closeGroupMenu}
                  anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
                  transformOrigin={{ vertical: "top", horizontal: "left" }}
                  MenuListProps={{ dense: true }}
                >
                  <MenuItem disabled>Add to group</MenuItem>
                  <MenuItem
                    selected={!groupMenuChannel?.group_name}
                    onClick={() => {
                      updateChannelGroup(groupMenuChannel?.channel_id, "");
                      closeGroupMenu();
                    }}
                  >
                    <ListItemText primary="No group" />
                  </MenuItem>
                  {groupOptions.map((group) => (
                    <MenuItem
                      key={group}
                      selected={groupMenuChannel?.group_name === group}
                      onClick={() => {
                        updateChannelGroup(groupMenuChannel?.channel_id, group);
                        closeGroupMenu();
                      }}
                    >
                      <CheckRoundedIcon
                        fontSize="small"
                        sx={{
                          opacity: groupMenuChannel?.group_name === group ? 1 : 0,
                          mr: 1,
                        }}
                      />
                      <ListItemText primary={group} />
                    </MenuItem>
                  ))}
                </Menu>
              </Stack>
              {assignError && (
                <Typography color="error" variant="body2">
                  {assignError}
                </Typography>
              )}
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
              transition: "transform 0.2s ease, box-shadow 0.2s ease",
              ...fadeUpSx,
              "&:hover": {
                transform: "translateY(-3px)",
                boxShadow:
                  theme.palette.mode === "dark"
                    ? "0 22px 36px rgba(15,23,42,0.45)"
                    : "0 22px 34px rgba(148,163,184,0.4)",
              },
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

          {viewMode === "chart" ? (
            <Stack spacing={2}>
              <Paper
                elevation={0}
                sx={(theme) => ({
                  borderRadius: 3,
                  border: "1px solid",
                  borderColor: theme.palette.divider,
                  background:
                    theme.palette.mode === "dark"
                      ? "linear-gradient(140deg, rgba(15,23,42,0.95) 0%, rgba(30,41,59,0.9) 50%, rgba(13,148,136,0.5) 100%)"
                      : "rgba(255,255,255,0.94)",
                  boxShadow:
                    theme.palette.mode === "dark"
                      ? "0 14px 28px rgba(15,23,42,0.4)"
                      : "0 14px 26px rgba(148,163,184,0.25)",
                  overflow: "hidden",
                  p: 2,
                  transition: "transform 0.2s ease, box-shadow 0.2s ease",
                  ...fadeUpSx,
                  "&:hover": {
                    transform: "translateY(-3px)",
                    boxShadow:
                      theme.palette.mode === "dark"
                        ? "0 18px 30px rgba(15,23,42,0.5)"
                        : "0 18px 30px rgba(148,163,184,0.35)",
                  },
                })}
              >
                <Typography variant="subtitle2" fontWeight={700} mb={2}>
                  Videos over time
                </Typography>
                {videoChartData.length ? (
                  <Box height={320}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={videoChartData}
                        margin={{ top: 10, right: 20, left: 0, bottom: 50 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke="rgba(148,163,184,0.3)"
                        />
                        <XAxis
                          dataKey="date"
                          angle={-20}
                          textAnchor="end"
                          interval={0}
                          height={70}
                          tick={{ fontSize: 11 }}
                        />
                        <YAxis tickFormatter={formatNumber} />
                        <Tooltip
                          formatter={(value) => formatNumber(value)}
                          labelFormatter={(_, payload) =>
                            payload?.[0]?.payload?.name || ""
                          }
                          contentStyle={{
                            borderRadius: 12,
                            border: "1px solid rgba(148,163,184,0.35)",
                            boxShadow: "0 12px 24px rgba(15,23,42,0.2)",
                          }}
                          labelStyle={
                            theme.palette.mode === "dark"
                              ? { color: "#000000", fontWeight: 700 }
                              : undefined
                          }
                        />
                        <Legend />
                        <Line
                          type="monotone"
                          dataKey="views"
                          name="Views"
                          stroke="#f59e0b"
                          strokeWidth={2.5}
                          dot={{ r: 2 }}
                        />
                        <Line
                          type="monotone"
                          dataKey="likes"
                          name="Likes"
                          stroke="#22c55e"
                          strokeWidth={2}
                          dot={{ r: 2 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </Box>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    No video data to display.
                  </Typography>
                )}
              </Paper>

              <Paper
                elevation={0}
                sx={(theme) => ({
                  borderRadius: 3,
                  border: "1px solid",
                  borderColor: theme.palette.divider,
                  background:
                    theme.palette.mode === "dark"
                      ? "linear-gradient(140deg, rgba(15,23,42,0.95) 0%, rgba(30,41,59,0.9) 50%, rgba(13,148,136,0.5) 100%)"
                      : "rgba(255,255,255,0.94)",
                  boxShadow:
                    theme.palette.mode === "dark"
                      ? "0 14px 28px rgba(15,23,42,0.4)"
                      : "0 14px 26px rgba(148,163,184,0.25)",
                  overflow: "hidden",
                  p: 2,
                  transition: "transform 0.2s ease, box-shadow 0.2s ease",
                  ...fadeUpSx,
                  "&:hover": {
                    transform: "translateY(-3px)",
                    boxShadow:
                      theme.palette.mode === "dark"
                        ? "0 18px 30px rgba(15,23,42,0.5)"
                        : "0 18px 30px rgba(148,163,184,0.35)",
                  },
                })}
              >
                <Typography variant="subtitle2" fontWeight={700} mb={2}>
                  Shorts over time
                </Typography>
                {shortChartData.length ? (
                  <Box height={320}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={shortChartData}
                        margin={{ top: 10, right: 20, left: 0, bottom: 50 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke="rgba(148,163,184,0.3)"
                        />
                        <XAxis
                          dataKey="date"
                          angle={-20}
                          textAnchor="end"
                          interval={0}
                          height={70}
                          tick={{ fontSize: 11 }}
                        />
                        <YAxis tickFormatter={formatNumber} />
                        <Tooltip
                          formatter={(value) => formatNumber(value)}
                          labelFormatter={(_, payload) =>
                            payload?.[0]?.payload?.name || ""
                          }
                          contentStyle={{
                            borderRadius: 12,
                            border: "1px solid rgba(148,163,184,0.35)",
                            boxShadow: "0 12px 24px rgba(15,23,42,0.2)",
                          }}
                          labelStyle={
                            theme.palette.mode === "dark"
                              ? { color: "#000000", fontWeight: 700 }
                              : undefined
                          }
                        />
                        <Legend />
                        <Line
                          type="monotone"
                          dataKey="views"
                          name="Views"
                          stroke="#38bdf8"
                          strokeWidth={2.5}
                          dot={{ r: 2 }}
                        />
                        <Line
                          type="monotone"
                          dataKey="likes"
                          name="Likes"
                          stroke="#a855f7"
                          strokeWidth={2}
                          dot={{ r: 2 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </Box>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    No shorts data to display.
                  </Typography>
                )}
              </Paper>
            </Stack>
          ) : (
            <>
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
                  transition: "transform 0.2s ease, box-shadow 0.2s ease",
                  "&:hover": {
                    transform: "translateY(-3px)",
                    boxShadow:
                      theme.palette.mode === "dark"
                        ? "0 18px 30px rgba(15,23,42,0.5)"
                        : "0 18px 30px rgba(148,163,184,0.35)",
                  },
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
                  transition: "transform 0.2s ease, box-shadow 0.2s ease",
                  "&:hover": {
                    transform: "translateY(-3px)",
                    boxShadow:
                      theme.palette.mode === "dark"
                        ? "0 18px 30px rgba(15,23,42,0.5)"
                        : "0 18px 30px rgba(148,163,184,0.35)",
                  },
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
            </>
          )}
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
