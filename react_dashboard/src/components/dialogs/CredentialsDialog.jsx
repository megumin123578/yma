import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Avatar,
  Button,
  IconButton,
  Menu,
  MenuItem,
  Box,
  Typography,
  Divider,
  Fade,
  Checkbox,
  Switch,
  useTheme,
  useMediaQuery,
} from "@mui/material";
import { useCallback, useEffect, useRef, useState } from "react";
import dayjs from "dayjs";
import { LocalizationProvider, TimePicker } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import LinkIcon from "@mui/icons-material/Link";
import RefreshIcon from "@mui/icons-material/Refresh";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import MoreVertIcon from "@mui/icons-material/MoreVert";
import DragIndicatorIcon from "@mui/icons-material/DragIndicator";
import {
  uploadCredentials,
  listTokens,
  deleteToken,
  getTokenProgress,
  setTokenVisibility,
  runToken,
  runAllTokens,
  runTokenStage,
  getOAuthState,
  listSchedules,
  createSchedule,
  updateSchedule,
  deleteSchedule,
  listScheduleRuns,
  stopScheduleRun,
} from "../../services/userService";

const CredentialsDialog = ({ open, onClose }) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const isDark = theme.palette.mode === "dark";
  const surface = isDark ? "rgba(17, 24, 39, 0.72)" : "rgba(255,255,255,0.82)";
  const panel = isDark ? "rgba(20, 28, 40, 0.55)" : "rgba(255,255,255,0.7)";
  const border = isDark ? "rgba(255,255,255,0.14)" : "rgba(0,0,0,0.08)";
  const accent = isDark ? "#7de0d2" : theme.palette.primary.main;
  const [status, setStatus] = useState({ type: "", message: "" });
  const [uploading, setUploading] = useState(false);
  const [authUrl, setAuthUrl] = useState("");
  const [oauthState, setOauthState] = useState("");
  const [latestTokenName, setLatestTokenName] = useState("");
  const [tokens, setTokens] = useState([]);
  const [loadingTokens, setLoadingTokens] = useState(false);
  const [runningAll, setRunningAll] = useState(false);
  const [, setTokenSyncing] = useState(false);
  const [tokenProgress, setTokenProgress] = useState({});
  const [progress, setProgress] = useState({ status: "idle", percent: 0, stage: "" });
  const [autoReloaded, setAutoReloaded] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState("");
  const [activeTab, setActiveTab] = useState("add");
  const [dragTokenName, setDragTokenName] = useState("");
  const [dragOverTokenName, setDragOverTokenName] = useState("");
  const [menuAnchorEl, setMenuAnchorEl] = useState(null);
  const [menuTokenName, setMenuTokenName] = useState("");
  const [schedules, setSchedules] = useState([]);
  const [scheduleRuns, setScheduleRuns] = useState([]);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [runsError, setRunsError] = useState("");
  const [stoppingRunId, setStoppingRunId] = useState(null);
  const [scheduleForm, setScheduleForm] = useState({
    time_of_day: "08:00",
  });
  const shimmerSx = {
    position: "relative",
    overflow: "hidden",
    "&:before": {
      content: '""',
      position: "absolute",
      top: "-50%",
      left: "-120%",
      width: "80%",
      height: "200%",
      background:
        "linear-gradient(120deg, transparent 0%, rgba(255,255,255,0.45) 45%, transparent 90%)",
      transform: "translateX(0)",
      transition: "transform 0.7s ease",
      opacity: 0.8,
      pointerEvents: "none",
    },
    "&:hover:before": {
      transform: "translateX(260%)",
    },
  };
  const progressTimersRef = useRef({});

  const cleanError = (msg) => {
    if (!msg) return "";
    let s = String(msg).trim();
    if (s.startsWith("(") && s.endsWith(")")) {
      s = s.slice(1, -1).trim();
    }
    return s;
  };

  const applyTokenOrder = (items) => {
    let order = [];
    try {
      order = JSON.parse(localStorage.getItem("tokens.order") || "[]");
    } catch {
      order = [];
    }
    if (!order.length) return items;
    const byName = new Map(items.map((t) => [t.name || t, t]));
    const ordered = order.map((name) => byName.get(name)).filter(Boolean);
    const remaining = items.filter((t) => !order.includes(t.name || t));
    return [...ordered, ...remaining];
  };

  const saveTokenOrder = (items) => {
    try {
      const order = items.map((t) => t.name || t);
      localStorage.setItem("tokens.order", JSON.stringify(order));
    } catch {
      // ignore storage errors
    }
  };

  const loadTokens = useCallback(async () => {
    setLoadingTokens(true);
    try {
      const data = await listTokens();
      const nextTokens = data?.tokens || [];
      const ordered = applyTokenOrder(nextTokens);
      setTokens(ordered);
    } catch (err) {
      setTokens([]);
    } finally {
      setLoadingTokens(false);
    }
  }, []);

  const loadSchedules = useCallback(async () => {
    try {
      const data = await listSchedules();
      setSchedules(data?.items || []);
    } catch (err) {
      setSchedules([]);
    }
  }, []);

  useEffect(() => {
    if (open) {
      setStatus({ type: "", message: "" });
      setUploading(false);
      setAuthUrl("");
      setOauthState("");
      setLatestTokenName("");
      setProgress({ status: "idle", percent: 0, stage: "" });
      setAutoReloaded(false);
      setActiveTab("add");
      loadTokens();
      loadSchedules();
    }
  }, [open, loadSchedules, loadTokens]);

  useEffect(() => {
    if (activeTab === "schedule") {
      loadSchedules();
    }
  }, [activeTab, loadSchedules]);

  useEffect(() => {
    if (!open || activeTab !== "logs") return;
    let canceled = false;

    const loadRuns = async () => {
      setLoadingRuns(true);
      setRunsError("");
      try {
        const data = await listScheduleRuns(10);
        if (!canceled) {
          setScheduleRuns(data?.items || []);
        }
      } catch (err) {
        if (!canceled) {
          setScheduleRuns([]);
          const msg = err?.response?.data?.detail || "Permission Denied";
          setRunsError(msg);
        }
      } finally {
        if (!canceled) {
          setLoadingRuns(false);
        }
      }
    };

    loadRuns();
    const intervalId = setInterval(loadRuns, 5000);

    return () => {
      canceled = true;
      clearInterval(intervalId);
    };
  }, [open, activeTab]);

  useEffect(() => {
    if (!authUrl || !oauthState) return;
    let stopped = false;
    setTokenSyncing(true);

    const poll = async () => {
      try {
        const data = await getOAuthState(oauthState);
        if (data?.ready && data?.token_name) {
          setLatestTokenName(data.token_name);
          setOauthState("");
          setTokenSyncing(false);
          await loadTokens();
          return true;
        }
      } catch {
        // ignore
      }
      return false;
    };

    const intervalId = setInterval(async () => {
      if (!stopped) {
        const done = await poll();
        if (done) {
          stopped = true;
          clearInterval(intervalId);
        }
      }
    }, 2000);

    poll();

    return () => clearInterval(intervalId);
  }, [authUrl, oauthState, loadTokens, setTokenSyncing]);

  useEffect(() => {
    if (!latestTokenName) return;
    let canceled = false;

    const pollProgress = async () => {
      try {
        const data = await getTokenProgress(latestTokenName);
        if (!canceled) {
          setProgress({
            status: data?.status || "idle",
            percent: data?.percent ?? 0,
            stage: data?.stage || "",
            message: data?.message || "",
          });
        }
        if (data?.status === "done" || data?.status === "error") {
          return true;
        }
      } catch (err) {
        if (!canceled) {
          setProgress({ status: "idle", percent: 0, stage: "" });
        }
      }
      return false;
    };

    const intervalId = setInterval(async () => {
      const done = await pollProgress();
      if (done) {
        clearInterval(intervalId);
      }
    }, 2000);

    pollProgress();

    return () => {
      canceled = true;
      clearInterval(intervalId);
    };
  }, [latestTokenName]);

  useEffect(() => {
    const shouldReload =
      !autoReloaded &&
      (progress.status === "done" || (progress.percent >= 100 && progress.status !== "error"));
    if (!shouldReload) return;
    setAutoReloaded(true);
    const timer = setTimeout(() => {
      window.location.reload();
    }, 800);
    return () => clearTimeout(timer);
  }, [progress.status, progress.percent, autoReloaded]);

  const handleStartOAuth = async () => {
    const targetName = "";
    if (uploading) return;

    setUploading(true);
    setStatus({ type: "", message: "" });
    setProgress({ status: "idle", percent: 0, stage: "" });
    setAutoReloaded(false);

    try {
      const data = await uploadCredentials(targetName);
      const nextUrl = data?.auth_url || "";
      const nextState = data?.state || "";
      setAuthUrl(nextUrl);
      setOauthState(nextState);
      if (!nextUrl) {
        await loadTokens();
      }
      setStatus({
        type: "success",
        message: nextUrl ? "Redirecting to Google..." : "Authorization started.",
      });
      if (nextUrl) {
        window.open(nextUrl, "_blank", "noopener");
      }
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Authorization failed. Please try again.";
      setStatus({ type: "error", message });
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteToken = async (tokenName) => {
    try {
      await deleteToken(tokenName);
      await loadTokens();
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Delete failed. Please try again.";
      setStatus({ type: "error", message });
    }
  };

  const handleToggleToken = async (tokenName, checked) => {
    try {
      await setTokenVisibility(tokenName, !checked);
      await loadTokens();
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Update failed. Please try again.";
      setStatus({ type: "error", message });
    }
  };


  const loadTokenProgress = async (tokenName) => {
    try {
      const data = await getTokenProgress(tokenName);
      setTokenProgress((prev) => ({
        ...prev,
        [tokenName]: {
          status: data?.status || "idle",
          percent: data?.percent ?? 0,
          stage: data?.stage || "",
          message: data?.message || "",
        },
      }));
      return data?.status === "done" || data?.status === "error";
    } catch {
      return false;
    }
  };

  const handleRunToken = async (tokenName) => {
    try {
      await runToken(tokenName);
      setTokenProgress((prev) => ({
        ...prev,
        [tokenName]: { status: "queued", percent: 0, stage: "queued", message: "" },
      }));
      startProgressPolling(tokenName);
      setStatus({ type: "success", message: "Refresh queued." });
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Failed to start refresh.";
      setStatus({ type: "error", message });
    }
  };

  const handleRunAllTokens = async () => {
    setRunningAll(true);
    try {
      const data = await runAllTokens();
      const tokenNames = Array.isArray(data?.token_names) ? data.token_names : [];
      if (tokenNames.length) {
        setTokenProgress((prev) => {
          const next = { ...prev };
          tokenNames.forEach((tokenName) => {
            next[tokenName] = {
              status: "queued",
              percent: 0,
              stage: "queued",
              message: "",
            };
          });
          return next;
        });
        tokenNames.forEach((tokenName) => startProgressPolling(tokenName));
      }
      setStatus({
        type: "success",
        message: tokenNames.length
          ? `Queued ${tokenNames.length} channel(s).`
          : "Refresh queued.",
      });
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Failed to start refresh.";
      setStatus({ type: "error", message });
    } finally {
      setRunningAll(false);
    }
  };

  const openTokenMenu = (event, tokenName) => {
    setMenuAnchorEl(event.currentTarget);
    setMenuTokenName(tokenName);
  };

  const closeTokenMenu = () => {
    setMenuAnchorEl(null);
    setMenuTokenName("");
  };

  const handleRunTokenStage = async (stage) => {
    if (!menuTokenName) return;
    try {
      await runTokenStage(menuTokenName, stage);
      setTokenProgress((prev) => ({
        ...prev,
        [menuTokenName]: { status: "queued", percent: 0, stage: "queued", message: "" },
      }));
      startProgressPolling(menuTokenName);
      setStatus({ type: "success", message: `Refresh queued (${stage}).` });
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Failed to start refresh.";
      setStatus({ type: "error", message });
    } finally {
      closeTokenMenu();
    }
  };

  const startProgressPolling = (tokenName) => {
    const existing = progressTimersRef.current[tokenName];
    if (existing) {
      clearInterval(existing);
    }
    const intervalId = setInterval(async () => {
      const done = await loadTokenProgress(tokenName);
      if (done) {
        clearInterval(intervalId);
        delete progressTimersRef.current[tokenName];
      }
    }, 2000);
    progressTimersRef.current[tokenName] = intervalId;
  };

  const handleScheduleField = (field, value) => {
    setScheduleForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleCreateSchedule = async () => {
    if (!scheduleForm.time_of_day) {
      setStatus({ type: "error", message: "Please set a time." });
      return;
    }
    try {
      await createSchedule({
        time_of_day: scheduleForm.time_of_day,
        enabled: true,
      });
      setStatus({ type: "success", message: "Schedule saved." });
      await loadSchedules();
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Failed to save schedule.";
      setStatus({ type: "error", message });
    }
  };

  const handleScheduleToggle = async (id, enabled) => {
    try {
      await updateSchedule(id, { enabled });
      await loadSchedules();
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Failed to update schedule.";
      setStatus({ type: "error", message });
    }
  };

  const handleDeleteSchedule = async (id) => {
    try {
      await deleteSchedule(id);
      await loadSchedules();
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Failed to delete schedule.";
      setStatus({ type: "error", message });
    }
  };

  const handleStopRun = async (runId) => {
    setStoppingRunId(runId);
    setRunsError("");
    try {
      await stopScheduleRun(runId);
      const data = await listScheduleRuns(10);
      setScheduleRuns(data?.items || []);
    } catch (err) {
      const msg = err?.response?.data?.detail || "Failed to stop run.";
      setRunsError(msg);
    } finally {
      setStoppingRunId(null);
    }
  };

  const requestDeleteToken = (tokenName) => {
    setPendingDelete(tokenName);
    setConfirmOpen(true);
  };

  const handleConfirmClose = () => {
    setConfirmOpen(false);
    setPendingDelete("");
  };

  const handleConfirmDelete = async () => {
    if (!pendingDelete) return;
    await handleDeleteToken(pendingDelete);
    handleConfirmClose();
  };

  const handleDone = () => {
    onClose();
    window.location.reload();
  };

  useEffect(() => {
    if (open) return;
    Object.values(progressTimersRef.current).forEach((timerId) => {
      clearInterval(timerId);
    });
    progressTimersRef.current = {};
    setTokenProgress({});
  }, [open]);

  const formatRunTime = (value) =>
    value ? dayjs(value).format("MMM D, HH:mm") : "--";

  const statusStyles = (status) => {
    const lower = (status || "").toLowerCase();
    if (lower === "done") return { bg: "rgba(34,197,94,0.18)", fg: "#22c55e" };
    if (lower === "queued") return { bg: "rgba(245,158,11,0.18)", fg: "#f59e0b" };
    if (lower === "running") return { bg: "rgba(59,130,246,0.18)", fg: "#3b82f6" };
    if (lower === "stopping") return { bg: "rgba(234,179,8,0.18)", fg: "#eab308" };
    if (lower === "stopped") return { bg: "rgba(148,163,184,0.28)", fg: "#94a3b8" };
    if (lower === "error") return { bg: "rgba(239,68,68,0.18)", fg: "#ef4444" };
    return { bg: "rgba(148,163,184,0.2)", fg: "#94a3b8" };
  };

  const formatProgressStage = (stage) => {
    const key = String(stage || "").toLowerCase();
    const map = {
      traffic_source: "Traffic Source",
      geography: "Geography",
      content: "Content",
      overview: "Overview",
      audience: "Audience",
      reach: "Reach",
      revenue: "Revenue",
      subscribers: "Subscribers",
      queued: "Queued",
      running: "Running",
      done: "Completed",
    };
    return map[key] || stage;
  };

  const visibleTokenCount = tokens.filter((token) => {
    if (typeof token === "string") return true;
    return !token.hidden;
  }).length;


  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      fullScreen={isMobile}
      TransitionComponent={Fade}
      transitionDuration={220}
      PaperProps={{
        sx: {
          bgcolor: surface,
          color: isDark ? "#e9edf2" : "inherit",
          border: `1px solid ${border}`,
          boxShadow: isDark ? "0 18px 60px rgba(0,0,0,0.55)" : undefined,
          overflow: "hidden",
          position: "relative",
          backdropFilter: "blur(16px)",
          WebkitBackdropFilter: "blur(16px)",
          width: { xs: "100vw", md: 860 },
          maxWidth: { xs: "100vw", md: "95vw" },
          minHeight: { xs: "100vh", sm: 620 },
          borderRadius: { xs: 0, sm: undefined },
          "&:before": {
            content: '""',
            position: "absolute",
            inset: 0,
            background: isDark
              ? "radial-gradient(600px 300px at 110% -10%, rgba(125,224,210,0.24), transparent 55%)"
              : "radial-gradient(600px 300px at 110% -10%, rgba(25,118,210,0.1), transparent 55%)",
            pointerEvents: "none",
          },
        },
      }}
    >
      <DialogTitle sx={{ pb: 1, position: "relative", zIndex: 1 }}>
        <Box display="flex" flexDirection="column" gap={0.5}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>
            Setting
          </Typography>
          <Typography variant="body2" sx={{ color: isDark ? "#aab4c2" : "text.secondary" }}>
            Connect Google accounts and schedules for automatic data fetching.
          </Typography>
        </Box>
      </DialogTitle>
      <DialogContent sx={{ position: "relative", zIndex: 1, minHeight: { xs: "calc(100vh - 140px)", sm: 520 }, display: "flex", flexDirection: "column", overflow: "hidden", px: { xs: 1.5, sm: 3 } }}>
        <Box display="flex" flexDirection={{ xs: "column", sm: "row" }} gap={2} mt={1} flex={1} overflow="hidden">
          <Box
            sx={{
              minWidth: { xs: "100%", sm: 140 },
              display: "flex",
              flexDirection: { xs: "row", sm: "column" },
              flexWrap: "wrap",
              gap: 1,
              flexShrink: 0,
              overflowX: { xs: "auto", sm: "visible" },
            }}
          >
            <Button
              variant="text"
              onClick={() => setActiveTab("add")}
              sx={{
                ...shimmerSx,
                justifyContent: "flex-start",
                border: "1px solid transparent",
                color:
                  activeTab === "add"
                    ? "#ffffff"
                    : isDark
                      ? "#ffffff"
                      : "rgba(15,23,42,0.9)",
                bgcolor: activeTab === "add" ? accent : "transparent",
                "&:hover": {
                  bgcolor: activeTab === "add"
                    ? accent
                    : isDark
                      ? "rgba(255,255,255,0.06)"
                      : "rgba(15,23,42,0.06)",
                },
              }}
            >
              Add channel
            </Button>
            <Button
              variant="text"
              onClick={() => setActiveTab("schedule")}
              sx={{
                ...shimmerSx,
                justifyContent: "flex-start",
                border: "1px solid transparent",
                color:
                  activeTab === "schedule"
                    ? "#ffffff"
                    : isDark
                      ? "#ffffff"
                      : "rgba(15,23,42,0.9)",
                bgcolor: activeTab === "schedule" ? accent : "transparent",
                "&:hover": {
                  bgcolor: activeTab === "schedule"
                    ? accent
                    : isDark
                      ? "rgba(255,255,255,0.06)"
                      : "rgba(15,23,42,0.06)",
                },
              }}
            >
              Schedule
            </Button>
            <Button
              variant="text"
              onClick={() => setActiveTab("logs")}
              sx={{
                ...shimmerSx,
                justifyContent: "flex-start",
                border: "1px solid transparent",
                color:
                  activeTab === "logs"
                    ? "#ffffff"
                    : isDark
                      ? "#ffffff"
                      : "rgba(15,23,42,0.9)",
                bgcolor: activeTab === "logs" ? accent : "transparent",
                "&:hover": {
                  bgcolor: activeTab === "logs"
                    ? accent
                    : isDark
                      ? "rgba(255,255,255,0.06)"
                      : "rgba(15,23,42,0.06)",
                },
              }}
            >
              Run logs
            </Button>
          </Box>

          <Box display="flex" flexDirection="column" gap={2} flex={1} sx={{ overflowY: "auto", pr: 1.5, py: 0.5 }}>
            {activeTab === "add" ? (
              <>
                <Box
                  sx={{
                    bgcolor: panel,
                    border: `1px solid ${border}`,
                    borderRadius: 2,
                    p: 2,
                    display: "flex",
                    flexDirection: "column",
                    gap: 1.5,
                    transition: "transform 200ms ease, box-shadow 200ms ease",
                    boxShadow: isDark ? "0 10px 24px rgba(0,0,0,0.35)" : "0 10px 24px rgba(0,0,0,0.08)",
                    backdropFilter: "blur(12px)",
                    WebkitBackdropFilter: "blur(12px)",
                    "&:hover": {
                      transform: "translateY(-2px)",
                    },
                  }}
                >
                  <Typography variant="subtitle2" sx={{ color: accent, letterSpacing: 0.3 }}>
                    Connect Google account
                  </Typography>

                  <Button
                    variant="contained"
                    color="success"
                    startIcon={<LinkIcon />}
                    onClick={handleStartOAuth}
                    disabled={uploading}
                    sx={{
                      ...shimmerSx,
                      bgcolor: isDark ? "#2b8a7b" : undefined,
                      color: isDark ? "#e9edf2" : undefined,
                      transition: "all 180ms ease",
                      "&:hover": {
                        bgcolor: isDark ? "#247468" : undefined,
                        transform: "translateY(-1px)",
                      },
                    }}
                  >
                    Add Channel
                  </Button>
                </Box>

                {progress.status === "idle" && status.message && (
                  <Typography
                    variant="body2"
                    color={
                      status.type === "error"
                        ? theme.palette.error.main
                        : theme.palette.success.main
                    }
                  >
                    {cleanError(status.message)}
                  </Typography>
                )}

                {null}

                {progress.status !== "idle" && (
                  <Box display="flex" flexDirection="column" gap={0.5}>
                    <Box display="flex" alignItems="center" justifyContent="space-between">
                      <Typography
                        variant="body2"
                        color={
                          progress.status === "done"
                            ? "text.secondary"
                            : status.message
                              ? theme.palette.success.main
                              : "text.secondary"
                        }
                      >
                        {progress.status === "done"
                          ? "Completed"
                          : status.message
                            ? `${cleanError(status.message)}${progress.stage ? ` • ${formatProgressStage(progress.stage)}` : ""}`
                            : formatProgressStage(progress.stage) || "Processing"}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {progress.percent}%
                      </Typography>
                    </Box>
                    <Box
                      sx={{
                        height: 6,
                        borderRadius: 999,
                        overflow: "hidden",
                        bgcolor: isDark ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.1)",
                      }}
                    >
                      <Box
                        sx={{
                          height: "100%",
                          width: `${Math.min(100, Math.max(0, progress.percent))}%`,
                          bgcolor: isDark ? "#7de0d2" : "#1aa86c",
                          transition: "width 200ms ease",
                        }}
                      />
                    </Box>
                  </Box>
                )}

                <Divider />

                <Box
                  sx={{
                    bgcolor: panel,
                    border: `1px solid ${border}`,
                    borderRadius: 2,
                    p: 2,
                    display: "flex",
                    flexDirection: "column",
                    gap: 1.5,
                    transition: "transform 200ms ease, box-shadow 200ms ease",
                    boxShadow: isDark ? "0 10px 24px rgba(0,0,0,0.35)" : "0 10px 24px rgba(0,0,0,0.08)",
                    backdropFilter: "blur(12px)",
                    WebkitBackdropFilter: "blur(12px)",
                    "&:hover": {
                      transform: "translateY(-2px)",
                    },
                  }}
                >
                  <Box display="flex" alignItems="center" justifyContent="space-between">
                    <Typography variant="subtitle2" sx={{ color: accent, letterSpacing: 0.3 }}>
                      Tokens
                    </Typography>
                    <Box display="flex" alignItems="center" gap={1}>
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<PlayArrowIcon fontSize="small" />}
                        onClick={handleRunAllTokens}
                        disabled={loadingTokens || runningAll || visibleTokenCount === 0}
                        sx={{
                          ...shimmerSx,
                          borderColor: isDark ? "rgba(255,255,255,0.2)" : undefined,
                          color: isDark ? "#e9edf2" : undefined,
                        }}
                      >
                        Run all
                      </Button>
                      <Button
                        size="small"
                        onClick={loadTokens}
                        disabled={loadingTokens}
                        sx={{
                          ...shimmerSx,
                          minWidth: 0,
                          color: isDark ? "#9fe3d6" : undefined,
                        }}
                      >
                        <RefreshIcon fontSize="small" />
                      </Button>
                    </Box>
                  </Box>

                  {tokens.length === 0 ? (
                    <Typography variant="body2" color="text.secondary">
                      {loadingTokens ? "Loading tokens..." : "No tokens found."}
                    </Typography>
                  ) : (
                    <Box display="flex" flexDirection="column" gap={1}>
                      {tokens.map((token) => {
                        const tokenName = typeof token === "string" ? token : token.name || "";
                        const displayName =
                          (typeof token === "object" && token.label) ||
                          (tokenName.toLowerCase().endsWith(".pickle")
                            ? tokenName.slice(0, -7)
                            : tokenName);
                        const isHidden = typeof token === "string" ? false : !!token.hidden;
                        return (
                          <Box
                            key={tokenName}
                            display="flex"
                            alignItems="center"
                            gap={1}
                            draggable
                            onDragStart={() => setDragTokenName(tokenName)}
                            onDragEnd={() => {
                              setDragTokenName("");
                              setDragOverTokenName("");
                            }}
                            onDragOver={(event) => event.preventDefault()}
                            onDragEnter={() => {
                              if (dragTokenName && dragTokenName !== tokenName) {
                                setDragOverTokenName(tokenName);
                              }
                            }}
                            onDrop={() => {
                              if (!dragTokenName || dragTokenName === tokenName) return;
                              setTokens((prev) => {
                                const next = [...prev];
                                const from = next.findIndex((t) => (t.name || t) === dragTokenName);
                                const to = next.findIndex((t) => (t.name || t) === tokenName);
                                if (from < 0 || to < 0) return prev;
                                const [moved] = next.splice(from, 1);
                                next.splice(to, 0, moved);
                                saveTokenOrder(next);
                                return next;
                              });
                              setDragOverTokenName("");
                            }}
                            sx={{
                              transition: "transform 180ms ease, background-color 180ms ease",
                              ...(dragTokenName === tokenName
                                ? { transform: "scale(1.01)" }
                                : {}),
                              ...(dragOverTokenName === tokenName
                                ? { transform: "translateY(6px)" }
                                : {}),
                            }}
                          >
                            <IconButton
                              size="small"
                              sx={{
                                color: isDark ? "#9fe3d6" : "rgba(15,23,42,0.6)",
                                cursor: "grab",
                              }}
                              aria-label={`Drag ${displayName}`}
                            >
                              <DragIndicatorIcon fontSize="small" />
                            </IconButton>
                            <Checkbox
                              size="small"
                              checked={!isHidden}
                              onChange={(event) =>
                                handleToggleToken(tokenName, event.target.checked)
                              }
                              sx={{
                                color: isDark ? "#7ed6ff" : undefined,
                                "&.Mui-checked": { color: isDark ? "#43c2ff" : undefined },
                              }}
                            />
                            <Box
                              display="flex"
                              flexDirection="column"
                              gap={0.75}
                              sx={{
                                flex: 1,
                                border: `1px solid ${border}`,
                                borderRadius: 1,
                                p: 1,
                                bgcolor: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.75)",
                                backdropFilter: "blur(10px)",
                                WebkitBackdropFilter: "blur(10px)",
                                opacity: isHidden ? 0.5 : 1,
                                transition: "opacity 220ms ease, border-color 180ms ease, background-color 180ms ease",
                                "&:hover": {
                                  bgcolor: isDark ? "rgba(255,255,255,0.12)" : "rgba(25,118,210,0.08)",
                                  borderColor: isDark ? "rgba(255,255,255,0.2)" : "rgba(25,118,210,0.2)",
                                  opacity: isHidden ? 0.6 : 1,
                                },
                                cursor: "grab",
                                ...(dragTokenName === tokenName
                                  ? { borderColor: isDark ? "#7de0d2" : "#1aa86c" }
                                  : {}),
                              }}
                            >
                              <Box display="flex" alignItems="center" justifyContent="space-between" gap={0.5}>
                                <Box display="flex" alignItems="center" gap={1.5}>
                                  <Button
                                    size="small"
                                    variant="outlined"
                                    onClick={() => handleRunToken(tokenName)}
                                    sx={{
                                      ...shimmerSx,
                                      borderColor: isDark ? "rgba(255,255,255,0.2)" : undefined,
                                      color: isDark ? "#e9edf2" : undefined,
                                      minWidth: 32,
                                      px: 0.75,
                                    }}
                                    aria-label={`Run ${displayName}`}
                                  >
                                    <PlayArrowIcon fontSize="small" />
                                  </Button>
                                  <IconButton
                                    size="small"
                                    onClick={(event) => openTokenMenu(event, tokenName)}
                                    sx={{
                                      ...shimmerSx,
                                      border: `1px solid ${border}`,
                                      color: isDark ? "#e9edf2" : undefined,
                                    }}
                                    aria-label={`Run options for ${displayName}`}
                                  >
                                    <MoreVertIcon fontSize="small" />
                                  </IconButton>
                                  <Avatar
                                    src={typeof token === "object" ? token.avatar || "" : ""}
                                    alt={displayName}
                                    sx={{
                                      width: 26,
                                      height: 26,
                                      fontSize: 12,
                                      bgcolor: isDark ? "rgba(125,224,210,0.18)" : "rgba(25,118,210,0.12)",
                                      color: isDark ? "#d7fff7" : "rgba(15,23,42,0.8)",
                                    }}
                                  >
                                    {displayName.slice(0, 1).toUpperCase()}
                                  </Avatar>
                                  <Typography variant="body2">{displayName}</Typography>
                                </Box>
                                <Button
                                  size="small"
                                  color="error"
                                  onClick={() => requestDeleteToken(tokenName)}
                                  sx={shimmerSx}
                                >
                                  Delete
                                </Button>
                              </Box>
                              {tokenProgress[tokenName] && (
                                <Box display="flex" flexDirection="column" gap={0.4}>
                                  <Box
                                    sx={{
                                      height: 6,
                                      borderRadius: 999,
                                      overflow: "hidden",
                                      bgcolor: isDark ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.1)",
                                    }}
                                  >
                                    <Box
                                      sx={{
                                        height: "100%",
                                        width: `${Math.min(
                                          100,
                                          Math.max(0, tokenProgress[tokenName]?.percent ?? 0)
                                        )}%`,
                                        bgcolor: isDark ? "#7de0d2" : "#1aa86c",
                                        transition: "width 200ms ease",
                                      }}
                                    />
                                  </Box>
                                  {tokenProgress[tokenName]?.stage && (
                                    <Typography variant="caption" color="text.secondary">
                                      {tokenProgress[tokenName].stage}
                                    </Typography>
                                  )}
                                </Box>
                              )}
                            </Box>
                          </Box>
                        );
                      })}
                    </Box>
                  )}
                </Box>
              </>
            ) : (
              <>
                {activeTab === "schedule" ? (
                  <Box
                    sx={{
                      bgcolor: panel,
                      border: `1px solid ${border}`,
                      borderRadius: 2,
                      p: 2,
                    }}
                  >
                    <Typography variant="subtitle2" sx={{ color: accent, letterSpacing: 0.3 }}>
                      Schedule
                    </Typography>
                    <Box display="flex" flexDirection="column" gap={2} mt={1}>
                      {status.message && (
                        <Typography
                          variant="body2"
                          color={
                            status.type === "error"
                              ? theme.palette.error.main
                              : theme.palette.success.main
                          }
                        >
                          {cleanError(status.message)}
                        </Typography>
                      )}
                      <LocalizationProvider dateAdapter={AdapterDayjs}>
                        <TimePicker
                          label="Time"
                          value={
                            scheduleForm.time_of_day
                              ? dayjs(`2000-01-01T${scheduleForm.time_of_day}`)
                              : null
                          }
                          onChange={(value) => {
                            if (!value || !value.isValid?.()) return;
                            handleScheduleField("time_of_day", value.format("HH:mm"));
                          }}
                          ampm={false}
                          minutesStep={5}
                          localeText={{ cancelButtonLabel: "X" }}
                          slotProps={{
                            textField: { size: "small" },
                            popper: {
                              sx: {
                                "& .MuiPaper-root": {
                                  bgcolor: isDark ? "rgba(16,22,32,0.96)" : "#ffffff",
                                  border: `1px solid ${border}`,
                                  borderRadius: 2,
                                  boxShadow: isDark
                                    ? "0 18px 40px rgba(0,0,0,0.6)"
                                    : "0 16px 32px rgba(15,23,42,0.15)",
                                },
                                "& .MuiPickersLayout-root": {
                                  color: isDark ? "#e5e7eb" : "#111827",
                                },
                                "& .MuiMultiSectionDigitalClock-root": {
                                  justifyContent: "space-between",
                                  gap: 1,
                                  p: 1,
                                },
                                "& .MuiMultiSectionDigitalClock-section": {
                                  flex: 1,
                                  minWidth: 120,
                                  borderRadius: 1,
                                  background: isDark ? "rgba(255,255,255,0.04)" : "rgba(15,23,42,0.03)",
                                },
                                "& .MuiDigitalClock-item": {
                                  color: isDark ? "#cbd5f5" : "#1f2937",
                                  borderRadius: 1,
                                },
                                "& .MuiDigitalClock-item.Mui-selected": {
                                  bgcolor: isDark ? "rgba(125,224,210,0.25)" : "rgba(25,118,210,0.15)",
                                  color: isDark ? "#eafff9" : "#0b1f3b",
                                },
                                "& .MuiPickersToolbar-root": {
                                  color: isDark ? "#e5e7eb" : "#111827",
                                },
                                "& .MuiDialogActions-root button": {
                                  color: isDark ? "#ffffff" : "#111827",
                                },
                              },
                            },
                          }}
                        />
                      </LocalizationProvider>

                      <Button variant="contained" onClick={handleCreateSchedule} sx={shimmerSx}>
                        Save Schedule
                      </Button>

                      <Divider />

                      {schedules.length === 0 ? (
                        <Typography variant="body2" color="text.secondary">
                          No schedules yet.
                        </Typography>
                      ) : (
                        <Box display="flex" flexDirection="column" gap={1}>
                          {schedules.map((s) => (
                            <Box
                              key={s.id}
                              display="flex"
                              alignItems="center"
                              justifyContent="space-between"
                              sx={{
                                border: `1px solid ${border}`,
                                borderRadius: 1,
                                p: 1,
                                bgcolor: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.75)",
                              }}
                            >
                              <Box display="flex" flexDirection="column">
                                <Typography variant="body2">
                                  {`Daily at ${s.time_of_day || "--:--"}`}
                                </Typography>
                              </Box>
                              <Box display="flex" alignItems="center" gap={1}>
                                <Switch
                                  size="small"
                                  checked={!!s.enabled}
                                  onChange={(e) => handleScheduleToggle(s.id, e.target.checked)}
                                />
                                <Button
                                  size="small"
                                  color="error"
                                  onClick={() => handleDeleteSchedule(s.id)}
                                  sx={shimmerSx}
                                >
                                  Delete
                                </Button>
                              </Box>
                            </Box>
                          ))}
                        </Box>
                      )}
                    </Box>
                  </Box>
                ) : (
                  <Box
                    sx={{
                      bgcolor: panel,
                      border: `1px solid ${border}`,
                      borderRadius: 2,
                      p: 2,
                    }}
                  >
                    <Typography variant="subtitle2" sx={{ color: accent, letterSpacing: 0.3 }}>
                      Run Logs
                    </Typography>
                    <Box display="flex" flexDirection="column" gap={1} mt={1}>
                      {runsError ? (
                        <Typography variant="body2" color="text.secondary">
                          {cleanError(runsError)}
                        </Typography>
                      ) : scheduleRuns.length === 0 ? (
                        <Typography variant="body2" color="text.secondary">
                          {loadingRuns ? "Loading logs..." : "No runs yet."}
                        </Typography>
                      ) : (
                        <Box display="flex" flexDirection="column" gap={1}>
                          {scheduleRuns.map((run) => {
                            const styles = statusStyles(run.status);
                            const processed = run.processed ?? 0;
                            const total = run.total ?? 0;
                            return (
                              <Box
                                key={run.id}
                                display="flex"
                                flexDirection="column"
                                gap={0.5}
                                sx={{
                                  border: `1px solid ${border}`,
                                  borderRadius: 1,
                                  p: 1,
                                  bgcolor: isDark
                                    ? "rgba(255,255,255,0.06)"
                                    : "rgba(255,255,255,0.75)",
                                }}
                              >
                                <Box display="flex" alignItems="center" justifyContent="space-between" gap={1}>
                                  <Box display="flex" alignItems="center" gap={1}>
                                    <Box
                                      sx={{
                                        px: 1,
                                        py: 0.25,
                                        borderRadius: 999,
                                        fontSize: 12,
                                        fontWeight: 700,
                                        letterSpacing: 0.4,
                                        textTransform: "uppercase",
                                        bgcolor: styles.bg,
                                        color: styles.fg,
                                      }}
                                    >
                                      {run.status || "unknown"}
                                    </Box>
                                    <Typography variant="body2">
                                      {cleanError(run.message) || "No details"}
                                    </Typography>
                                  </Box>
                                  {(run.status === "running" || run.status === "queued") && (
                                    <Button
                                      size="small"
                                      color="error"
                                      onClick={() => handleStopRun(run.id)}
                                      disabled={stoppingRunId === run.id}
                                      sx={shimmerSx}
                                    >
                                      Stop
                                    </Button>
                                  )}
                                </Box>
                                <Box
                                  display="flex"
                                  alignItems="center"
                                  justifyContent="space-between"
                                >
                                  <Typography variant="caption" color="text.secondary">
                                    {`Accounts: ${processed}/${total}`}
                                  </Typography>
                                  <Typography variant="caption" color="text.secondary">
                                    {`${formatRunTime(run.started_at)} -> ${formatRunTime(
                                      run.finished_at
                                    )}`}
                                  </Typography>
                                </Box>
                                {run.status === "running" && total > 0 && (
                                  <Box
                                    sx={{
                                      height: 6,
                                      borderRadius: 999,
                                      overflow: "hidden",
                                      bgcolor: isDark ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.1)",
                                    }}
                                  >
                                    <Box
                                      sx={{
                                        height: "100%",
                                        width: `${Math.min(
                                          100,
                                          Math.max(0, Math.round((processed / total) * 100))
                                        )}%`,
                                        bgcolor: isDark ? "#7de0d2" : "#1aa86c",
                                        transition: "width 200ms ease",
                                      }}
                                    />
                                  </Box>
                                )}
                              </Box>
                            );
                          })}
                        </Box>
                      )}
                    </Box>
                  </Box>
                )}
              </>
            )}
          </Box>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button
          onClick={onClose}
          disabled={uploading}
          sx={{ ...shimmerSx, color: isDark ? "#aab4c2" : "text.secondary" }}
        >
          Cancel
        </Button>
        <Button variant="contained" onClick={handleDone} disabled={uploading} sx={shimmerSx}>
          Done
        </Button>
      </DialogActions>
      <Dialog
        open={confirmOpen}
        onClose={handleConfirmClose}
        maxWidth="xs"
        fullWidth
        PaperProps={{
          sx: {
            bgcolor: isDark ? "rgba(15, 23, 42, 0.95)" : "background.paper",
            color: isDark ? "#e9edf2" : "inherit",
          },
        }}
      >
        <DialogTitle>Confirm Delete</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            This will delete the token. Continue?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={handleConfirmClose}
            sx={{ ...shimmerSx, color: isDark ? "#e2e8f0" : "text.secondary" }}
          >
            Cancel
          </Button>
          <Button color="error" variant="contained" onClick={handleConfirmDelete} sx={shimmerSx}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
      <Menu
        anchorEl={menuAnchorEl}
        open={Boolean(menuAnchorEl)}
        onClose={closeTokenMenu}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
      >
        <MenuItem onClick={() => handleRunTokenStage("content")}>
          Run content
        </MenuItem>
        <MenuItem onClick={() => handleRunTokenStage("traffic_source")}>
          Run traffic source
        </MenuItem>
        <MenuItem onClick={() => handleRunTokenStage("audience")}>
          Run audience
        </MenuItem>
        <MenuItem onClick={() => handleRunTokenStage("reach")}>
          Run reach
        </MenuItem>
        <MenuItem onClick={() => handleRunTokenStage("revenue")}>
          Run revenue
        </MenuItem>
        <MenuItem onClick={() => handleRunTokenStage("subscribers")}>
          Run subscribers
        </MenuItem>
      </Menu>
    </Dialog>
  );
};

export default CredentialsDialog;
