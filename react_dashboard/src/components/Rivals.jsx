import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Autocomplete,
  Avatar,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  Grid,
  IconButton,
  InputAdornment,
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
import AddRoundedIcon from "@mui/icons-material/AddRounded";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import GroupWorkOutlinedIcon from "@mui/icons-material/GroupWorkOutlined";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
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
  const [query, setQuery] = useState("");
  const [channel, setChannel] = useState(null);
  const [videos, setVideos] = useState([]);
  const [shorts, setShorts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [savedChannels, setSavedChannels] = useState([]);
  const [savedLoaded, setSavedLoaded] = useState(false);
  const [savedGroups, setSavedGroups] = useState([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [createGroupOpen, setCreateGroupOpen] = useState(
    initialState.createGroupOpen || false
  );
  const [newGroupName, setNewGroupName] = useState(
    initialState.newGroupName || ""
  );
  const [filterGroup, setFilterGroup] = useState(initialState.filterGroup || "");
  const [assignError, setAssignError] = useState("");
  const [selectedSavedId, setSelectedSavedId] = useState(
    initialState.selectedSavedId || ""
  );
  const [groupMenuAnchor, setGroupMenuAnchor] = useState(null);
  const [groupMenuChannelId, setGroupMenuChannelId] = useState(null);

  // YouTube search-as-you-type state
  const [searchOptions, setSearchOptions] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const searchTimerRef = useRef(null);
  const searchSeqRef = useRef(0);

  const isLikelyUrlOrId = (text) => {
    const s = (text || "").trim();
    if (!s) return false;
    if (s.startsWith("http") || s.includes("youtube.com") || s.includes("youtu.be")) return true;
    if (/^UC[a-zA-Z0-9_-]{22}$/.test(s)) return true;
    if (s.startsWith("@")) return true;
    return false;
  };

  const triggerSearch = useCallback((text) => {
    if (searchTimerRef.current) {
      clearTimeout(searchTimerRef.current);
      searchTimerRef.current = null;
    }
    const trimmed = (text || "").trim();
    if (trimmed.length < 2 || isLikelyUrlOrId(trimmed)) {
      setSearchOptions([]);
      setSearchLoading(false);
      return;
    }
    setSearchLoading(true);
    searchTimerRef.current = setTimeout(async () => {
      const seq = ++searchSeqRef.current;
      try {
        const resp = await fetch(
          `${API_BASE}/api/youtube/search?q=${encodeURIComponent(trimmed)}&limit=8`
        );
        if (!resp.ok) throw new Error();
        const data = await resp.json();
        if (seq !== searchSeqRef.current) return;
        setSearchOptions(Array.isArray(data?.items) ? data.items : []);
      } catch {
        if (seq !== searchSeqRef.current) return;
        setSearchOptions([]);
      } finally {
        if (seq === searchSeqRef.current) setSearchLoading(false);
      }
    }, 500);
  }, []);

  useEffect(() => {
    return () => {
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    };
  }, []);

  const fetchChannel = useCallback(async (q) => {
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
  }, []);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const q = query.trim();
    if (!q) {
      setError("Please enter a channel name, URL, or ID");
      return;
    }
    setQuery("");
    setSearchOptions([]);
    setSearchOpen(false);
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

  const loadSavedGroups = async () => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setSavedGroups([]);
      return;
    }
    try {
      const resp = await fetch(`${API_BASE}/api/users/rivals/groups`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) throw new Error((await resp.text()) || `HTTP ${resp.status}`);
      const data = await resp.json();
      setSavedGroups(Array.isArray(data?.groups) ? data.groups : []);
    } catch {
      setSavedGroups([]);
    }
  };

  const handleFollowToggle = async () => {
    if (!channel?.id) return;
    const token = localStorage.getItem("access_token");
    if (!token) {
      setSaveError("Please login to follow channels.");
      return;
    }

    const alreadyFollowed = savedChannels.some(
      (row) => row.channel_id === channel.id
    );

    try {
      setSaving(true);
      setSaveError("");
      if (alreadyFollowed) {
        const resp = await fetch(
          `${API_BASE}/api/users/rivals/${encodeURIComponent(channel.id)}`,
          {
            method: "DELETE",
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        if (!resp.ok)
          throw new Error((await resp.text()) || `HTTP ${resp.status}`);
      } else {
        const channelUrl = channel.customUrl
          ? `https://www.youtube.com/${channel.customUrl}`
          : `https://www.youtube.com/channel/${channel.id}`;
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
        if (!resp.ok)
          throw new Error((await resp.text()) || `HTTP ${resp.status}`);
      }
      await loadSavedChannels();
      await loadSavedGroups();
    } catch (e) {
      setSaveError(
        e?.message ||
          (alreadyFollowed ? "Failed to unfollow channel" : "Failed to follow channel")
      );
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

  const handleCreateGroup = async () => {
    const name = newGroupName.trim();
    if (!name) return;
    const token = localStorage.getItem("access_token");
    if (!token) {
      setAssignError("Please login to create groups.");
      return;
    }
    try {
      setAssignError("");
      const resp = await fetch(`${API_BASE}/api/users/rivals/groups`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ group_name: name }),
      });
      if (!resp.ok) throw new Error((await resp.text()) || `HTTP ${resp.status}`);
      setSavedGroups((prev) =>
        prev.includes(name) ? prev : [...prev, name]
      );
      setCreateGroupOpen(false);
      setNewGroupName("");
    } catch (e) {
      setAssignError(e?.message || "Failed to create group");
    }
  };

  const handleSavedSelect = useCallback((value) => {
    setSelectedSavedId(value);
    if (!value) return;
    setNewGroupName("");
    fetchChannel(value);
  }, [fetchChannel]);

  useEffect(() => {
    loadSavedChannels();
    loadSavedGroups();
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          selectedSavedId,
          createGroupOpen,
          newGroupName,
          filterGroup,
        })
      );
    } catch {
      // ignore storage errors
    }
  }, [selectedSavedId, createGroupOpen, newGroupName, filterGroup]);

  const missingSelected =
    !!selectedSavedId &&
    !savedChannels.some((row) => row.channel_id === selectedSavedId);
  const showSavedSelectors =
    savedLoaded && (!!savedChannels.length || !!selectedSavedId);

  useEffect(() => {
    if (savedLoaded && selectedSavedId && !channel) {
      setNewGroupName("");
      fetchChannel(selectedSavedId);
    }
  }, [savedLoaded, selectedSavedId, channel, savedChannels, fetchChannel]);

  const getChannelGroups = (row) => {
    if (!row) return [];
    if (Array.isArray(row.group_names)) return row.group_names;
    if (row.group_name) return [row.group_name];
    return [];
  };

  const groupOptions = useMemo(() => {
    const unique = new Set();
    savedGroups.forEach((name) => {
      const value = (name || "").trim();
      if (value) unique.add(value);
    });
    savedChannels.forEach((row) => {
      const names = Array.isArray(row.group_names)
        ? row.group_names
        : row.group_name
          ? [row.group_name]
          : [];
      names.forEach((name) => {
        const value = (name || "").trim();
        if (value) unique.add(value);
      });
    });
    const fresh = (newGroupName || "").trim();
    if (fresh) unique.add(fresh);
    return Array.from(unique).sort((a, b) => a.localeCompare(b));
  }, [savedChannels, savedGroups, newGroupName]);
  const shimmerHoverSx = (theme) => ({
    position: "relative",
    overflow: "hidden",
    "&:before": {
      content: '""',
      position: "absolute",
      top: "-50%",
      left: "-20%",
      width: "140%",
      height: "200%",
      background:
        "linear-gradient(120deg, transparent 0%, rgba(255,255,255,0.35) 45%, transparent 90%)",
      transform: "translateX(-120%)",
      transition: "transform 0.6s ease",
      opacity: 0.75,
      pointerEvents: "none",
    },
    "&:hover:before": {
      transform: "translateX(0%)",
    },
  });

  const filteredSavedChannels = useMemo(() => {
    const needle = (filterGroup || "").trim();
    if (!needle) return savedChannels;
    return savedChannels.filter(
      (row) => {
        const names = Array.isArray(row.group_names)
          ? row.group_names
          : row.group_name
            ? [row.group_name]
            : [];
        return names.some((name) => (name || "").trim() === needle);
      }
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

  useEffect(() => {
    if (!filterGroup) return;
    if (!filteredSavedChannels.length) return;
    const first = filteredSavedChannels[0];
    if (!first?.channel_id) return;
    if (selectedSavedId === first.channel_id) return;
    handleSavedSelect(first.channel_id);
  }, [filterGroup, filteredSavedChannels, selectedSavedId, handleSavedSelect]);

  const closeGroupMenu = () => {
    setGroupMenuAnchor(null);
    setGroupMenuChannelId(null);
  };

  const openGroupMenu = (event, row) => {
    setGroupMenuAnchor(event.currentTarget);
    setGroupMenuChannelId(row?.channel_id || null);
  };

  const updateChannelGroups = async (channelId, groupNames) => {
    if (!channelId) return;
    const token = localStorage.getItem("access_token");
    if (!token) {
      setAssignError("Please login to update groups.");
      return;
    }
    const cleaned = Array.from(
      new Set(
        (groupNames || [])
          .map((name) => (name || "").trim())
          .filter(Boolean)
      )
    );
    setSavedChannels((prev) =>
      prev.map((row) =>
        row.channel_id === channelId
          ? {
              ...row,
              group_names: cleaned,
              group_name: cleaned[0] || null,
            }
          : row
      )
    );
    setSavedGroups((prev) => {
      const next = new Set(prev);
      cleaned.forEach((name) => next.add(name));
      return Array.from(next);
    });
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
          group_names: cleaned,
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
    } catch (e) {
      setAssignError(e?.message || "Failed to update group");
      await loadSavedChannels();
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
          Array.isArray(row.group_names)
            ? {
                ...row,
                group_names: row.group_names.filter((g) => g !== name),
                group_name:
                  row.group_name === name ? null : row.group_name,
              }
            : row.group_name === name
              ? { ...row, group_name: null, group_names: [] }
              : row
        )
      );
      setSavedGroups((prev) => prev.filter((g) => g !== name));
      if (filterGroup === name) {
        setFilterGroup("");
      }
      if (selectedSavedId) {
        const selectedRow = savedChannels.find(
          (row) => row.channel_id === selectedSavedId
        );
        if (
          selectedRow &&
          (selectedRow.group_name === name ||
            (Array.isArray(selectedRow.group_names) &&
              selectedRow.group_names.includes(name)))
        ) {
          setNewGroupName("");
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
      <Stack spacing={2.25} component="form" onSubmit={handleSubmit}>
          <Box>
            <Autocomplete
              freeSolo
              fullWidth
              sx={{ flexGrow: 1 }}
              options={searchOptions}
              loading={searchLoading}
              open={searchOpen && (searchOptions.length > 0 || searchLoading)}
              onOpen={() => setSearchOpen(true)}
              onClose={() => setSearchOpen(false)}
              filterOptions={(x) => x}
              inputValue={query}
              onInputChange={(_, newValue, reason) => {
                setQuery(newValue);
                if (reason === "input") triggerSearch(newValue);
              }}
              onChange={(_, value) => {
                if (!value || typeof value === "string") return;
                setQuery("");
                setSearchOptions([]);
                setSearchOpen(false);
                fetchChannel(value.id);
              }}
              getOptionLabel={(option) =>
                typeof option === "string"
                  ? option
                  : option?.title || option?.id || ""
              }
              isOptionEqualToValue={(opt, val) =>
                (opt?.id || "") === (val?.id || "")
              }
              noOptionsText={
                query.trim().length < 2
                  ? "Type at least 2 characters"
                  : isLikelyUrlOrId(query)
                    ? "Press Enter to load by URL/ID"
                    : "No channels found"
              }
              renderOption={(props, option) => {
                const { key, ...rest } = props;
                const subs = option.subscriberCount
                  ? formatNumber(Number(option.subscriberCount))
                  : null;
                const handle = option.customUrl
                  ? option.customUrl.startsWith("@")
                    ? option.customUrl
                    : `@${option.customUrl}`
                  : null;
                return (
                  <li key={option.id} {...rest}>
                    <Avatar
                      src={option.thumbnail || ""}
                      alt={option.title}
                      sx={{ width: 36, height: 36, mr: 1.5 }}
                    >
                      {(option.title || option.id || "?").charAt(0).toUpperCase()}
                    </Avatar>
                    <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                      <Typography variant="body2" fontWeight={600} noWrap>
                        {option.title || option.id}
                      </Typography>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        noWrap
                        component="div"
                      >
                        {[handle, subs && `${subs} subs`]
                          .filter(Boolean)
                          .join(" · ") || option.id}
                      </Typography>
                    </Box>
                  </li>
                );
              }}
              renderInput={(params) => (
                <TextField
                  {...params}
                  size="small"
                  placeholder="Search a channel name, paste URL, or @handle"
                  InputProps={{
                    ...params.InputProps,
                    startAdornment: (
                      <>
                        <InputAdornment position="start" sx={{ ml: 0.5 }}>
                          <SearchRoundedIcon fontSize="small" />
                        </InputAdornment>
                        {params.InputProps.startAdornment}
                      </>
                    ),
                    endAdornment: (
                      <>
                        {searchLoading ? (
                          <CircularProgress size={16} sx={{ mr: 1 }} />
                        ) : null}
                        {params.InputProps.endAdornment}
                      </>
                    ),
                  }}
                />
              )}
            />
          </Box>

          {showSavedSelectors && (
            <>
              <Divider sx={{ opacity: 0.6 }} />
              <Stack spacing={1.25}>
                <Stack
                  direction="row"
                  alignItems="center"
                  justifyContent="space-between"
                  spacing={1}
                >
                  <Button
                    type="button"
                    size="small"
                    startIcon={<AddRoundedIcon />}
                    onClick={() => {
                      setNewGroupName("");
                      setCreateGroupOpen(true);
                    }}
                    sx={{ textTransform: "none" }}
                  >
                    New group
                  </Button>
                </Stack>

                <Stack
                  direction={{ xs: "column", sm: "row" }}
                  spacing={1.25}
                  alignItems={{ xs: "stretch", sm: "center" }}
                >
                  <FormControl size="small" sx={{ minWidth: 180 }}>
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
                            color="error"
                            aria-label={`Delete group ${group}`}
                            onMouseDown={(e) => e.stopPropagation()}
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

                  <FormControl size="small" sx={{ flexGrow: 1, minWidth: 240 }}>
                    <InputLabel id="saved-channels-label">Channel</InputLabel>
                    <Select
                      labelId="saved-channels-label"
                      value={selectedSavedId}
                      label="Channel"
                      onChange={(e) => handleSavedSelect(e.target.value)}
                      renderValue={(value) => {
                        const row = savedChannels.find((item) => item.channel_id === value);
                        if (row) return row.channel_name || row.channel_id;
                        if (missingSelected) return `Missing: ${value}`;
                        return value || "";
                      }}
                    >
                      <MenuItem value="">
                        <em>Select a channel...</em>
                      </MenuItem>
                      {missingSelected && (
                        <MenuItem value={selectedSavedId}>
                          <ListItemText
                            primary={`Missing: ${selectedSavedId}`}
                            secondary="Channel not in saved list"
                          />
                        </MenuItem>
                      )}
                      {filteredSavedChannels.map((row) => {
                        const groups = Array.isArray(row.group_names)
                          ? row.group_names
                          : row.group_name
                            ? [row.group_name]
                            : [];
                        return (
                          <MenuItem
                            key={row.id}
                            value={row.channel_id}
                            sx={{
                              pr: 1,
                              "&:hover .saved-row-actions": { opacity: 1 },
                            }}
                          >
                            <Avatar
                              src={row.channel_avatar_url || ""}
                              alt={row.channel_name || row.channel_id}
                              sx={{
                                width: 28,
                                height: 28,
                                mr: 1.25,
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
                            <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                              <Typography variant="body2" fontWeight={600} noWrap>
                                {row.channel_name || row.channel_id}
                              </Typography>
                              {(row.channel_name || groups.length > 0) && (
                                <Stack
                                  direction="row"
                                  spacing={0.5}
                                  alignItems="center"
                                  sx={{ mt: 0.25, flexWrap: "wrap", rowGap: 0.5 }}
                                >
                                  {groups.map((g) => (
                                    <Chip
                                      key={g}
                                      label={g}
                                      size="small"
                                      sx={{
                                        height: 18,
                                        fontSize: "0.65rem",
                                        "& .MuiChip-label": { px: 0.75 },
                                      }}
                                    />
                                  ))}
                                  {row.channel_name && (
                                    <Typography
                                      variant="caption"
                                      color="text.secondary"
                                      noWrap
                                    >
                                      {row.channel_id}
                                    </Typography>
                                  )}
                                </Stack>
                              )}
                            </Box>
                            <Stack
                              direction="row"
                              className="saved-row-actions"
                              sx={{
                                opacity: { xs: 1, md: 0 },
                                transition: "opacity 0.15s ease",
                              }}
                            >
                              <IconButton
                                size="small"
                                edge="end"
                                onMouseDown={(e) => e.stopPropagation()}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  openGroupMenu(e, row);
                                }}
                                aria-label={`Edit groups for ${row.channel_name || row.channel_id}`}
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
                            </Stack>
                          </MenuItem>
                        );
                      })}
                    </Select>
                  </FormControl>
                </Stack>

                {assignError && (
                  <Typography color="error" variant="body2">
                    {assignError}
                  </Typography>
                )}
              </Stack>

              <Menu
                anchorEl={groupMenuAnchor}
                open={Boolean(groupMenuAnchor)}
                onClose={closeGroupMenu}
                anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
                transformOrigin={{ vertical: "top", horizontal: "left" }}
                MenuListProps={{ dense: true }}
              >
                {(() => {
                  const menuChannel = savedChannels.find(
                    (item) => item.channel_id === groupMenuChannelId
                  );
                  return [
                    <MenuItem key="groups-title" disabled>
                      Add to groups
                    </MenuItem>,
                    <MenuItem
                      key="groups-clear"
                      onClick={() => {
                        updateChannelGroups(groupMenuChannelId, []);
                        closeGroupMenu();
                      }}
                    >
                      <ListItemText primary="Clear groups" />
                    </MenuItem>,
                    ...groupOptions.map((group) => {
                      const current = getChannelGroups(menuChannel);
                      const checked = current.includes(group);
                      const next = checked
                        ? current.filter((name) => name !== group)
                        : [...current, group];
                      return (
                        <MenuItem
                          key={group}
                          onClick={() => {
                            updateChannelGroups(groupMenuChannelId, next);
                          }}
                        >
                          <Checkbox size="small" checked={checked} />
                          <ListItemText primary={group} />
                        </MenuItem>
                      );
                    }),
                  ];
                })()}
              </Menu>
            </>
          )}
      </Stack>

      <Dialog
        open={createGroupOpen}
        onClose={() => setCreateGroupOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle sx={{ pb: 1 }}>New group</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            size="small"
            label="Group name"
            value={newGroupName}
            onChange={(e) => setNewGroupName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && newGroupName.trim()) {
                e.preventDefault();
                handleCreateGroup();
              }
            }}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button
            onClick={() => setCreateGroupOpen(false)}
            sx={{ textTransform: "none" }}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleCreateGroup}
            disabled={!newGroupName.trim()}
            sx={{ textTransform: "none" }}
          >
            Create
          </Button>
        </DialogActions>
      </Dialog>

      {error && (
        <Typography color="error" variant="body2">
          {error}
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
                  ? "rgba(15,23,42,0.85)"
                  : "rgba(255,255,255,0.96)",
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
              <Stack direction="row" spacing={2} alignItems="flex-start" flexWrap="wrap">
                <Stack alignItems="flex-start" spacing={1} sx={{ minWidth: 0, flexGrow: 1 }}>
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
                    <Box sx={{ minWidth: 0 }}>
                      <Typography variant="h6" fontWeight={700}>
                        {channel.title}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {channel.customUrl || channel.id}
                      </Typography>
                    </Box>
                  </Stack>
                  {channel.description && (
                    <Typography variant="body2" color="text.secondary">
                      {channel.description}
                    </Typography>
                  )}
                </Stack>
                {(() => {
                  const isFollowed =
                    !!channel?.id &&
                    savedChannels.some((row) => row.channel_id === channel.id);
                  let label;
                  if (saving) {
                    label = isFollowed ? "Unfollowing…" : "Following…";
                  } else {
                    label = isFollowed ? "Unfollow" : "Follow";
                  }
                  return (
                    <Button
                      type="button"
                      variant={isFollowed ? "outlined" : "contained"}
                      color={isFollowed ? "inherit" : "success"}
                      onClick={handleFollowToggle}
                      disabled={saving}
                      sx={{
                        textTransform: "none",
                        minWidth: 120,
                        fontWeight: 600,
                        alignSelf: "center",
                      }}
                    >
                      {label}
                    </Button>
                  );
                })()}
              </Stack>
              {saveError && (
                <Typography color="error" variant="body2">
                  {saveError}
                </Typography>
              )}

              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                  <StatCard label="Subscribers" value={subsHidden ? "Hidden" : formatStat(stats.subscriberCount)} />
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                  <StatCard label="Total views" value={formatStat(stats.viewCount)} />
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                  <StatCard label="Total videos" value={formatStat(stats.videoCount)} />
                </Grid>
              </Grid>

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
                      ? "rgba(15,23,42,0.85)"
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
                      ? "rgba(15,23,42,0.85)"
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
          ? "rgba(15,23,42,0.85)"
          : "rgba(255,255,255,0.95)",
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
