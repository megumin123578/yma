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
  Tooltip,
  Tabs,
  Tab,
  Checkbox,
  Switch,
  TextField,
  Chip,
  useTheme,
  useMediaQuery,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import { useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import dayjs from "dayjs";
import { LocalizationProvider, TimePicker } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import AddIcon from "@mui/icons-material/Add";
import RefreshIcon from "@mui/icons-material/Refresh";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import DragIndicatorIcon from "@mui/icons-material/DragIndicator";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import CheckIcon from "@mui/icons-material/Check";
import CloseIcon from "@mui/icons-material/Close";
import {
  uploadCredentials,
  listTokens,
  deleteToken,
  listTokenProgress,
  setTokenVisibility,
  runToken,
  runAllTokens,
  runSelectedTokens,
  runTokenStage,
  runTokenFullBackfill,
  refreshTokenAvatar,
  listTokenGroups,
  createTokenGroup,
  renameTokenGroup,
  deleteTokenGroup,
  getOAuthState,
  listSchedules,
  createSchedule,
  updateSchedule,
  deleteSchedule,
  listScheduleRuns,
  stopScheduleRun,
  resumeScheduleRun,
} from "../../services/userService";
import { UserContext } from "../../context/UserContext";
import ManageUserRequests from "../ManageUserRequests";

import { getApiBase } from "../../config";
import { setStoredHiddenTokens } from "../../utils/tokenOrder";
export const CREDENTIALS_CHANGED_EVENT = "credentials-data-changed";

const CredentialsDialog = ({
  open,
  onClose,
  inline = false,
  defaultTokenView = "list",
  onDataChanged,
}) => {
  const theme = useTheme();
  const { user } = useContext(UserContext);
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const isDark = theme.palette.mode === "dark";
  const isAdmin = !!user?.is_admin;
  const surface = isDark ? "rgba(17, 24, 39, 0.72)" : "rgba(255,255,255,0.82)";
  const panel = isDark ? "rgba(20, 28, 40, 0.55)" : "rgba(255,255,255,0.7)";
  const border = isDark ? "rgba(255,255,255,0.14)" : "rgba(0,0,0,0.08)";
  const accent = isDark ? "#7de0d2" : theme.palette.primary.main;
  const [status, setStatus] = useState({ type: "", message: "" });
  const [uploading, setUploading] = useState(false);
  const [authUrl, setAuthUrl] = useState("");
  const [oauthState, setOauthState] = useState("");
  const [tokens, setTokens] = useState([]);
  const [loadingTokens, setLoadingTokens] = useState(false);
  const [runningAll, setRunningAll] = useState(false);
  const [, setTokenSyncing] = useState(false);
  const [tokenProgress, setTokenProgress] = useState({});
  const [tokenUpdatedAtMap, setTokenUpdatedAtMap] = useState({});
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState("");
  const [activeTab, setActiveTab] = useState("add");
  const [dragTokenName, setDragTokenName] = useState("");
  const [dragOverTokenName, setDragOverTokenName] = useState("");
  const [tokenView, setTokenView] = useState(defaultTokenView);
  const [menuAnchorEl, setMenuAnchorEl] = useState(null);
  const [menuTokenName, setMenuTokenName] = useState("");
  const [tokenGroups, setTokenGroups] = useState([]);
  const [groupDraft, setGroupDraft] = useState("");
  const [editingGroupName, setEditingGroupName] = useState("");
  const [editingGroupDraft, setEditingGroupDraft] = useState("");
  const [savingGroup, setSavingGroup] = useState(false);
  const [runSelectedMode, setRunSelectedMode] = useState(false);
  const [selectedTokenNames, setSelectedTokenNames] = useState([]);
  const [runningSelected, setRunningSelected] = useState(false);
  const [schedules, setSchedules] = useState([]);
  const [schedulesError, setSchedulesError] = useState("");
  const [scheduleRuns, setScheduleRuns] = useState([]);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [runsError, setRunsError] = useState("");
  const [stoppingRunId, setStoppingRunId] = useState(null);
  const [resumingRunId, setResumingRunId] = useState(null);
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
  const resumeButtonSx = {
    ...shimmerSx,
    color: isDark ? "#7dd3fc" : "#1976d2",
  };
  const avatarRefreshQueueRef = useRef(new Set());
  const hydratedProgressOnceRef = useRef(false);
  const progress = { status: "idle", percent: 0, stage: "", message: "" };

  const resolveAvatarSrc = useCallback((value) => {
    const raw = String(value || "").trim();
    if (!raw) return "";
    if (/^https?:\/\//i.test(raw)) return raw;
    const base = getApiBase() || "";
    const cleanBase = base.endsWith("/") ? base.slice(0, -1) : base;
    const cleanRaw = raw.startsWith("/") ? raw : `/${raw}`;
    return `${cleanBase}${cleanRaw}`;
  }, []);

  const notifyDataChanged = useCallback(() => {
    onDataChanged?.();
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(CREDENTIALS_CHANGED_EVENT));
    }
  }, [onDataChanged]);

  const cleanError = (msg) => {
    if (!msg) return "";
    let s = String(msg).trim();
    if (s.startsWith("(") && s.endsWith(")")) {
      s = s.slice(1, -1).trim();
    }
    return s;
  };

  const applyTokenOrder = (items) => {
    const moveHiddenTokensToBottom = (list) => {
      const visible = [];
      const hidden = [];
      (Array.isArray(list) ? list : []).forEach((item) => {
        const isHiddenItem = typeof item === "object" && item?.hidden;
        if (isHiddenItem) {
          hidden.push(item);
        } else {
          visible.push(item);
        }
      });
      return [...visible, ...hidden];
    };

    let order = [];
    try {
      order = JSON.parse(localStorage.getItem("tokens.order") || "[]");
    } catch {
      order = [];
    }
    if (!order.length) return moveHiddenTokensToBottom(items);
    const byName = new Map(items.map((t) => [t.name || t, t]));
    const ordered = order.map((name) => byName.get(name)).filter(Boolean);
    const remaining = items.filter((t) => !order.includes(t.name || t));
    return moveHiddenTokensToBottom([...ordered, ...remaining]);
  };

  const saveTokenOrder = (items) => {
    try {
      const order = items.map((t) => t.name || t);
      localStorage.setItem("tokens.order", JSON.stringify(order));
    } catch {
      // ignore storage errors
    }
  };

  const isProgressFromToday = useCallback((updatedAt) => {
    const value = String(updatedAt || "").trim();
    if (!value) return false;
    const parsed = dayjs(value);
    return parsed.isValid() && parsed.isSame(dayjs(), "day");
  }, []);

  const getCompletedUpdatedAt = useCallback((entry) => {
    const finishedAt = String(entry?.finished_at || "").trim();
    if (finishedAt) return finishedAt;
    const percent = Number(entry?.percent ?? 0);
    if (!Number.isFinite(percent) || percent < 100) return "";
    return String(entry?.updated_at || "").trim();
  }, []);

  const isProgressCompleteToday = useCallback(
    (entry) => {
      const percent = Number(entry?.percent ?? 0);
      if (!Number.isFinite(percent) || percent < 100) return false;
      return isProgressFromToday(getCompletedUpdatedAt(entry));
    },
    [getCompletedUpdatedAt, isProgressFromToday]
  );

  const normalizeDailyProgressEntry = useCallback(
    (entry) => {
      if (isProgressCompleteToday(entry)) {
        return entry;
      }
      const percent = Number(entry?.percent ?? 0);
      if (Number.isFinite(percent) && percent >= 100) {
        return {
          ...entry,
          status: "queued",
          percent: 0,
          stage: "queued",
          message: "Not run today yet",
        };
      }
      return entry;
    },
    [isProgressCompleteToday]
  );

  const toProgressEntry = useCallback(
    (data) => ({
      status: data?.status || "idle",
      percent: data?.percent ?? 0,
      stage: data?.stage || "",
      message: data?.message || "",
      updated_at: data?.updated_at || "",
      finished_at: data?.finished_at || "",
      run_id: data?.run_id || "",
    }),
    []
  );

  const buildLatestProgressByToken = useCallback(
    (items) => {
      const latest = new Map();
      (Array.isArray(items) ? items : []).forEach((item) => {
        const tokenName = String(item?.token_name || "").trim();
        if (!tokenName || latest.has(tokenName)) return;
        latest.set(tokenName, toProgressEntry(item));
      });
      return latest;
    },
    [toProgressEntry]
  );

  const isVisibleHydratedProgress = (entry, isRunAllToken = false) => {
    const status = String(entry?.status || "").toLowerCase();
    if (!status || status === "idle") return false;
    if (isRunAllToken) return true;
    return status === "queued" || status === "running";
  };

  const getProgressRunId = useCallback((entry) => {
    const raw = String(entry?.run_id || "").trim();
    return raw || "";
  }, []);

  const getIncompleteRunIds = useCallback((progressMap) => {
    const runState = new Map();
    Object.values(progressMap || {}).forEach((entry) => {
      const runId = getProgressRunId(entry);
      if (!runId) return;
      const state = runState.get(runId) || { hasEntries: false, allComplete: true };
      state.hasEntries = true;
      state.allComplete = state.allComplete && isProgressCompleteToday(entry);
      runState.set(runId, state);
    });
    return new Set(
      Array.from(runState.entries())
        .filter(([, state]) => state.hasEntries && !state.allComplete)
        .map(([runId]) => runId)
    );
  }, [getProgressRunId, isProgressCompleteToday]);

  const reconcileRunProgress = useCallback((nextProgress) => {
    const incompleteRunIds = getIncompleteRunIds(nextProgress);
    const cleaned = {};
    Object.entries(nextProgress || {}).forEach(([tokenName, entry]) => {
      const runId = getProgressRunId(entry);
      if (runId) {
        if (incompleteRunIds.has(runId) || !isProgressCompleteToday(entry)) {
          cleaned[tokenName] = entry;
        }
        return;
      }
      if (isVisibleHydratedProgress(entry, false)) {
        cleaned[tokenName] = entry;
      }
    });
    return cleaned;
  }, [getIncompleteRunIds, getProgressRunId, isProgressCompleteToday]);

  const loadTokens = useCallback(async () => {
    setLoadingTokens(true);
    try {
      const data = await listTokens();
      const nextTokens = data?.tokens || [];
      setStoredHiddenTokens(nextTokens);
      const ordered = applyTokenOrder(nextTokens);
      setTokens(ordered);
    } catch (err) {
      setStoredHiddenTokens([]);
      setTokens([]);
    } finally {
      setLoadingTokens(false);
    }
  }, []);

  const loadSchedules = useCallback(async () => {
    if (!isAdmin) {
      setSchedules([]);
      setSchedulesError("Permission Denied");
      return;
    }
    try {
      setSchedulesError("");
      const data = await listSchedules();
      setSchedules(data?.items || []);
    } catch (err) {
      setSchedules([]);
      const msg = err?.response?.data?.detail || "Permission Denied";
      setSchedulesError(msg);
    }
  }, [isAdmin]);

  const loadTokenGroups = useCallback(async () => {
    try {
      const data = await listTokenGroups();
      const groups = Array.isArray(data?.groups) ? data.groups : [];
      setTokenGroups(
        groups
          .map((group) =>
            typeof group === "string"
              ? { group_name: group, color: "" }
              : {
                  group_name: group?.group_name || "",
                  color: group?.color || "",
                }
          )
          .filter((group) => group.group_name)
      );
    } catch {
      setTokenGroups([]);
    }
  }, []);

  useEffect(() => {
    if (open) {
      hydratedProgressOnceRef.current = false;
      setStatus({ type: "", message: "" });
      setUploading(false);
      setAuthUrl("");
      setOauthState("");
      setActiveTab("add");
      setTokenView(defaultTokenView);
      setRunSelectedMode(false);
      setSelectedTokenNames([]);
      loadTokens();
      loadTokenGroups();
      loadSchedules();
    }
  }, [open, loadSchedules, loadTokenGroups, loadTokens, defaultTokenView]);

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
          setScheduleRuns(
            (data?.items || []).map((run) => ({
              ...run,
              status: normalizeRunStatus(run.status),
            }))
          );
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
    if (!open) {
      avatarRefreshQueueRef.current = new Set();
      hydratedProgressOnceRef.current = false;
      return;
    }
    const missingAvatarToken = tokens.find((token) => {
      if (typeof token !== "object") return false;
      if (token.owned === false) return false;
      const tokenName = token.name || "";
      if (!tokenName) return false;
      if ((token.avatar || "").trim()) return false;
      if (avatarRefreshQueueRef.current.has(tokenName)) return false;
      return true;
    });
    if (!missingAvatarToken) return;

    const tokenName = missingAvatarToken.name || "";
    avatarRefreshQueueRef.current.add(tokenName);
    let canceled = false;

    const syncAvatar = async () => {
      try {
        await refreshTokenAvatar(tokenName);
        if (!canceled) {
          await loadTokens();
        }
      } catch {
        // Ignore refresh failures and avoid retry loops for the same token.
      }
    };

    syncAvatar();

    return () => {
      canceled = true;
    };
  }, [open, tokens, loadTokens]);

  // Hydrate visible token progress from the backend DB when the dialog reopens.
  useEffect(() => {
    if (!open || !tokens.length || hydratedProgressOnceRef.current) return;
    hydratedProgressOnceRef.current = true;
    const ownedTokens = tokens.filter((token) => {
      if (typeof token === "string") return true;
      return token.owned !== false;
    });
    hydrateTokenProgress(ownedTokens);
    // hydrateTokenProgress intentionally stays outside deps to avoid rerunning on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, tokens]);

  useEffect(() => {
    if (!authUrl || !oauthState) return;
    let stopped = false;
    setTokenSyncing(true);

    const poll = async () => {
      try {
        const data = await getOAuthState(oauthState);
        if (data?.ready && data?.token_name) {
          setOauthState("");
          setTokenSyncing(false);
          await loadTokens();
          notifyDataChanged();
          setStatus({ type: "success", message: "Channel synced." });
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
  }, [authUrl, oauthState, loadTokens, notifyDataChanged, setTokenSyncing]);

  const handleStartOAuth = async () => {
    if (uploading) return;

    setUploading(true);
    setStatus({ type: "", message: "" });

    try {
      const data = await uploadCredentials();
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
      notifyDataChanged();
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
      notifyDataChanged();
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Update failed. Please try again.";
      setStatus({ type: "error", message });
    }
  };

  const handleCreateTokenGroup = async () => {
    const name = groupDraft.trim();
    if (!name || savingGroup) return;
    setSavingGroup(true);
    try {
      await createTokenGroup(name);
      await loadTokenGroups();
      setGroupDraft("");
      setStatus({ type: "success", message: "Group created." });
      notifyDataChanged();
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Failed to create group.";
      setStatus({ type: "error", message });
    } finally {
      setSavingGroup(false);
    }
  };

  const handleRenameTokenGroup = async (groupName) => {
    const nextName = editingGroupDraft.trim();
    if (!groupName || !nextName || savingGroup) return;
    setSavingGroup(true);
    try {
      await renameTokenGroup(groupName, nextName);
      await Promise.all([loadTokenGroups(), loadTokens()]);
      setEditingGroupName("");
      setEditingGroupDraft("");
      setStatus({ type: "success", message: "Group renamed." });
      notifyDataChanged();
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Failed to rename group.";
      setStatus({ type: "error", message });
    } finally {
      setSavingGroup(false);
    }
  };

  const handleDeleteTokenGroup = async (groupName) => {
    if (!groupName || savingGroup) return;
    setSavingGroup(true);
    try {
      await deleteTokenGroup(groupName);
      await Promise.all([loadTokenGroups(), loadTokens()]);
      if (editingGroupName === groupName) {
        setEditingGroupName("");
        setEditingGroupDraft("");
      }
      setStatus({ type: "success", message: "Group deleted." });
      notifyDataChanged();
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Failed to delete group.";
      setStatus({ type: "error", message });
    } finally {
      setSavingGroup(false);
    }
  };

  const hydrateTokenProgress = useCallback(async (tokenItems) => {
    const ownedTokenNames = tokenItems
      .map((token) => (typeof token === "string" ? token : token?.name || ""))
      .filter(Boolean);
    if (!ownedTokenNames.length) return;
    let items = [];
    try {
      const data = await listTokenProgress();
      items = Array.isArray(data?.items) ? data.items : [];
    } catch {
      items = [];
    }
    const progressByToken = buildLatestProgressByToken(items);
    setTokenUpdatedAtMap(() => {
      const next = {};
      progressByToken.forEach((entry, tokenName) => {
        next[tokenName] = getCompletedUpdatedAt(entry);
      });
      return next;
    });

    const hydrated = {};
    const normalizedEntries = {};
    ownedTokenNames.forEach((tokenName) => {
      normalizedEntries[tokenName] = normalizeDailyProgressEntry(
        progressByToken.get(tokenName) || toProgressEntry(null)
      );
    });
    const incompleteRunIds = getIncompleteRunIds(normalizedEntries);
    ownedTokenNames.forEach((tokenName) => {
      const nextEntry = normalizedEntries[tokenName];
      const runId = getProgressRunId(nextEntry);
      const keepVisibleForRun = !!runId && incompleteRunIds.has(runId);
      if (!isVisibleHydratedProgress(nextEntry, keepVisibleForRun)) return;
      hydrated[tokenName] = nextEntry;
    });

    setTokenProgress((prev) => reconcileRunProgress({ ...prev, ...hydrated }));
  }, [
    buildLatestProgressByToken,
    getCompletedUpdatedAt,
    getIncompleteRunIds,
    getProgressRunId,
    normalizeDailyProgressEntry,
    reconcileRunProgress,
    toProgressEntry,
  ]);

  useEffect(() => {
    if (!open || !tokens.length) return;
    hydrateTokenProgress(tokens);
    const intervalId = setInterval(() => {
      hydrateTokenProgress(tokens);
    }, 5000);
    return () => clearInterval(intervalId);
  }, [open, tokens, hydrateTokenProgress]);

  const handleRunToken = async (tokenName) => {
    try {
      const data = await runToken(tokenName);
      setTokenProgress((prev) => ({
        ...prev,
        [tokenName]: {
          status: "queued",
          percent: 0,
          stage: "queued",
          message: "",
          run_id: String(data?.run_id || ""),
          updated_at: "",
          finished_at: "",
        },
      }));
      setStatus({ type: "success", message: "Refresh queued." });
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Failed to start refresh.";
      setStatus({ type: "error", message });
    } finally {
      closeTokenMenu();
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
              run_id: String(data?.run_id || ""),
              updated_at: "",
              finished_at: "",
            };
          });
          return next;
        });
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
      const data = await runTokenStage(menuTokenName, stage);
      setTokenProgress((prev) => ({
        ...prev,
        [menuTokenName]: {
          status: "queued",
          percent: 0,
          stage: "queued",
          message: "",
          run_id: String(data?.run_id || ""),
          updated_at: "",
          finished_at: "",
        },
      }));
      setStatus({ type: "success", message: `Refresh queued (${stage}).` });
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Failed to start refresh.";
      setStatus({ type: "error", message });
    } finally {
      closeTokenMenu();
    }
  };

  const handleRunFullBackfill = async () => {
    if (!menuTokenName) return;
    try {
      const data = await runTokenFullBackfill(menuTokenName);
      setTokenProgress((prev) => ({
        ...prev,
        [menuTokenName]: {
          status: "queued",
          percent: 0,
          stage: "queued",
          message: "",
          run_id: String(data?.run_id || ""),
          updated_at: "",
          finished_at: "",
        },
      }));
      setStatus({ type: "success", message: "Full backfill queued." });
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Failed to start full backfill.";
      setStatus({ type: "error", message });
    } finally {
      closeTokenMenu();
    }
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
      setScheduleRuns((prev) =>
        prev.map((run) =>
          run.id === runId
            ? {
                ...run,
                status: "stopped",
                message: "Stopped by admin",
                finished_at: run.finished_at || new Date().toISOString(),
              }
            : run
        )
      );
      const data = await listScheduleRuns(10);
      setScheduleRuns(
        (data?.items || []).map((run) => ({
          ...run,
          status: normalizeRunStatus(run.status),
        }))
      );
    } catch (err) {
      const msg = err?.response?.data?.detail || "Failed to stop run.";
      setRunsError(msg);
    } finally {
      setStoppingRunId(null);
    }
  };

  const handleResumeRun = async (runId) => {
    setResumingRunId(runId);
    setRunsError("");
    try {
      await resumeScheduleRun(runId);
      const data = await listScheduleRuns(10);
      setScheduleRuns(
        (data?.items || []).map((run) => ({
          ...run,
          status: normalizeRunStatus(run.status),
        }))
      );
    } catch (err) {
      const msg = err?.response?.data?.detail || "Failed to resume run.";
      setRunsError(msg);
    } finally {
      setResumingRunId(null);
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
    notifyDataChanged();
  };

  useEffect(() => {
    if (open) return;
    setTokenProgress({});
    setTokenUpdatedAtMap({});
  }, [open]);

  const formatRunTime = (value) =>
    value ? dayjs(value).format("DD/MM HH:mm") : "--";

  const formatTokenUpdatedAt = useCallback((value) => {
    const raw = String(value || "").trim();
    if (!raw) return "--";
    const parsed = dayjs(raw);
    return parsed.isValid() ? parsed.format("DD/MM - HH:mm") : "--";
  }, []);

  const formatTokenName = (value) => {
    if (!value) return "All tokens";
    return String(value).replace(/\.pickle$/i, "");
  };

  const formatRunType = (value) => {
    const raw = String(value || "").trim();
    if (!raw) return "run";
    if (raw === "manual_all") return "manual all";
    if (raw === "manual_selected") return "manual selected";
    if (raw === "manual_single") return "manual";
    if (raw.startsWith("manual_stage:")) {
      return `stage: ${raw.split(":").slice(1).join(":")}`;
    }
    if (raw === "scheduled") return "scheduled";
    return raw.replace(/_/g, " ");
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
    };
    return Object.prototype.hasOwnProperty.call(map, key) ? map[key] : stage;
  };

  const statusStyles = (status) => {
    const lower = String(status || "").toLowerCase() === "stopping" ? "stopped" : String(status || "").toLowerCase();
    if (lower === "done") return { bg: "rgba(34,197,94,0.18)", fg: "#22c55e" };
    if (lower === "queued") return { bg: "rgba(245,158,11,0.18)", fg: "#f59e0b" };
    if (lower === "running") return { bg: "rgba(59,130,246,0.18)", fg: "#3b82f6" };
    if (lower === "stopped") return { bg: "rgba(148,163,184,0.28)", fg: "#94a3b8" };
    if (lower === "error") return { bg: "rgba(239,68,68,0.18)", fg: "#ef4444" };
    return { bg: "rgba(148,163,184,0.2)", fg: "#94a3b8" };
  };

  const normalizeRunStatus = (status) => {
    const lower = String(status || "").toLowerCase();
    if (lower === "stopping") return "stopped";
    return lower || "unknown";
  };

  const visibleTokenCount = tokens.filter((token) => {
    if (typeof token === "string") return true;
    return !token.hidden && token.owned !== false;
  }).length;
  const visibleOwnedTokenNames = useMemo(
    () =>
      tokens
        .filter((token) => {
          if (typeof token === "string") return true;
          return !token.hidden && token.owned !== false;
        })
        .map((token) => (typeof token === "string" ? token : token?.name || ""))
        .filter(Boolean),
    [tokens]
  );

  useEffect(() => {
    setSelectedTokenNames((prev) =>
      prev.filter((tokenName) => visibleOwnedTokenNames.includes(tokenName))
    );
  }, [tokens, visibleOwnedTokenNames]);

  const toggleSelectedToken = (tokenName, checked) => {
    setSelectedTokenNames((prev) => {
      if (checked) {
        return prev.includes(tokenName) ? prev : [...prev, tokenName];
      }
      return prev.filter((name) => name !== tokenName);
    });
  };

  const handleToggleRunSelectedMode = () => {
    setRunSelectedMode((prev) => {
      const next = !prev;
      if (!next) {
        setSelectedTokenNames([]);
      }
      return next;
    });
  };

  const handleConfirmRunSelected = async () => {
    if (!selectedTokenNames.length || runningSelected) return;
    setRunningSelected(true);
    try {
      const data = await runSelectedTokens(selectedTokenNames);
      const queuedTokenNames = Array.isArray(data?.token_names) ? data.token_names : selectedTokenNames;
      setTokenProgress((prev) => {
        const next = { ...prev };
        queuedTokenNames.forEach((tokenName) => {
          next[tokenName] = {
            status: "queued",
            percent: 0,
            stage: "queued",
            message: "",
            run_id: String(data?.run_id || ""),
            updated_at: "",
            finished_at: "",
          };
        });
        return next;
      });
      setStatus({
        type: "success",
        message: `Queued ${queuedTokenNames.length} selected channel(s).`,
      });
      setRunSelectedMode(false);
      setSelectedTokenNames([]);
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Failed to start selected refresh.";
      setStatus({ type: "error", message });
    } finally {
      setRunningSelected(false);
    }
  };

  const renderTokenControls = (tokenName, displayName, isOwned, isHidden, layout = "list") => (
    <Box display="flex" alignItems="center" gap={0.5} flexWrap="wrap">
      <Button
        size="small"
        variant="outlined"
        onClick={(event) => {
          event.stopPropagation();
          openTokenMenu(event, tokenName);
        }}
        disabled={!isOwned}
        sx={{
          ...shimmerSx,
          borderColor: isDark ? "rgba(255,255,255,0.2)" : undefined,
          color: isDark ? "#e9edf2" : undefined,
          minWidth: 32,
          px: 1,
        }}
        aria-label={`Run ${displayName}`}
        endIcon={<ExpandMoreIcon fontSize="small" />}
      >
        <PlayArrowIcon fontSize="small" />
      </Button>
      {layout === "card" ? (
        <Tooltip title="Delete this token">
          <IconButton
            size="small"
            onClick={(event) => {
              event.stopPropagation();
              requestDeleteToken(tokenName);
            }}
            disabled={!isOwned}
            sx={{
              p: 0.35,
              borderRadius: 999,
              color: "#ef4444",
              bgcolor: "rgba(239,68,68,0.12)",
              "&:hover": {
                bgcolor: "rgba(239,68,68,0.18)",
              },
            }}
            aria-label={`Delete ${displayName}`}
          >
            <DeleteOutlineIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      ) : (
        <Button
          size="small"
          color="error"
          onClick={(event) => {
            event.stopPropagation();
            requestDeleteToken(tokenName);
          }}
          disabled={!isOwned}
          sx={shimmerSx}
        >
          Delete
        </Button>
      )}
      {layout !== "card" && (
        <Box display="flex" alignItems="center" gap={0.5}>
          <Checkbox
            size="small"
            checked={!isHidden}
            onChange={(event) => handleToggleToken(tokenName, event.target.checked)}
            onClick={(event) => event.stopPropagation()}
            sx={{
              color: isDark ? "#7ed6ff" : undefined,
              "&.Mui-checked": { color: isDark ? "#43c2ff" : undefined },
            }}
          />
        </Box>
      )}
    </Box>
  );

  const renderTokenProgress = (tokenName) =>
    tokenProgress[tokenName] ? (
      <Box display="flex" flexDirection="column" gap={0.4} mt={1}>
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
              width: `${Math.min(100, Math.max(0, tokenProgress[tokenName]?.percent ?? 0))}%`,
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
    ) : null;

  const renderTokenItem = (token, layout = "list") => {
    const tokenName = typeof token === "string" ? token : token.name || "";
    const displayName =
      (typeof token === "object" && token.label) ||
      (tokenName.toLowerCase().endsWith(".pickle") ? tokenName.slice(0, -7) : tokenName);
    const isHidden = typeof token === "string" ? false : !!token.hidden;
    const isOwned = typeof token === "string" ? true : token.owned !== false;
    const avatarSrc = typeof token === "object" ? resolveAvatarSrc(token.avatar) : "";
    const groupName = typeof token === "object" ? token.group_name || "" : "";
    const groupColor = typeof token === "object" ? token.group_color || "" : "";
    const isSelected = selectedTokenNames.includes(tokenName);
    const tokenUpdatedAt = tokenUpdatedAtMap[tokenName] || tokenProgress[tokenName]?.updated_at || "";
    const canToggleSelectedFromCard = runSelectedMode && isOwned && !isHidden;
    const handleSelectFromCard = () => {
      if (!canToggleSelectedFromCard) return;
      toggleSelectedToken(tokenName, !isSelected);
    };

    if (layout === "card") {
      const cardBg = groupColor
        ? alpha(groupColor, isDark ? 0.16 : 0.1)
        : isDark
          ? "rgba(255,255,255,0.06)"
          : "rgba(255,255,255,0.85)";
      const cardBorder = groupColor
        ? alpha(groupColor, isDark ? 0.42 : 0.26)
        : border;
      const cardHoverBg = groupColor
        ? alpha(groupColor, isDark ? 0.22 : 0.14)
        : isDark
          ? "rgba(255,255,255,0.09)"
          : "rgba(255,255,255,1)";
      return (
        <Box
          key={tokenName}
          onClick={handleSelectFromCard}
          sx={{
            width: "100%",
            maxWidth: 440,
            border: `1px solid ${border}`,
            borderRadius: 3,
            p: 2,
            minHeight: 180,
            display: "flex",
            flexDirection: "column",
            bgcolor: cardBg,
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            transition: "all 200ms cubic-bezier(0.4, 0, 0.2, 1)",
            boxShadow: isDark ? "0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1)" : "0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -2px rgba(0,0,0,0.05)",
            borderColor: cardBorder,
            "&:hover": {
              transform: "translateY(-4px)",
              boxShadow: isDark ? "0 10px 25px -5px rgba(0,0,0,0.3)" : "0 10px 25px -5px rgba(25,118,210,0.15)",
              bgcolor: cardHoverBg,
              borderColor: groupColor
                ? alpha(groupColor, isDark ? 0.58 : 0.38)
                : isDark
                  ? "rgba(125,224,210,0.4)"
                  : "rgba(25,118,210,0.3)",
            },
            opacity: isHidden ? 0.7 : 1,
            position: "relative",
            overflow: "hidden",
            justifyContent: "space-between",
            cursor: canToggleSelectedFromCard ? "pointer" : "default",
          }}
        >
          {runSelectedMode && isOwned && !isHidden && (
            <Box
              sx={{
                position: "absolute",
                top: 10,
                left: 10,
                zIndex: 2,
                borderRadius: 999,
                bgcolor: isDark ? "rgba(15,23,42,0.72)" : "rgba(255,255,255,0.88)",
              }}
            >
              <Checkbox
                size="small"
                checked={isSelected}
                onChange={(event) => toggleSelectedToken(tokenName, event.target.checked)}
                onClick={(event) => event.stopPropagation()}
                sx={{
                  color: isDark ? "#7ed6ff" : accent,
                  "&.Mui-checked": { color: isDark ? "#7de0d2" : accent },
                }}
              />
            </Box>
          )}
          {isHidden && (
            <Box
              sx={{
                position: "absolute",
                inset: 0,
                bgcolor: isDark ? "rgba(0,0,0,0.2)" : "rgba(255,255,255,0.4)",
                pointerEvents: "none",
                zIndex: 0,
              }}
            />
          )}
          <Box sx={{ position: "relative", zIndex: 1, display: "flex", flexDirection: "column", height: "100%" }}>
            <Box display="flex" alignItems="flex-start" justifyContent="space-between" gap={1.5}>
              <Box display="flex" alignItems="center" gap={2}>
                <Avatar
                  src={avatarSrc}
                  alt={displayName}
                  sx={{
                    width: 56,
                    height: 56,
                    fontSize: 22,
                    fontWeight: 700,
                    bgcolor: isDark ? "rgba(125,224,210,0.15)" : "rgba(25,118,210,0.1)",
                    color: isDark ? "#7de0d2" : accent,
                    border: `1.5px solid ${isDark ? "rgba(125,224,210,0.3)" : "rgba(25,118,210,0.2)"}`,
                    boxShadow: isDark ? "0 0 10px rgba(125,224,210,0.1)" : "0 0 10px rgba(25,118,210,0.05)",
                  }}
                >
                  {displayName.slice(0, 1).toUpperCase()}
                </Avatar>
                <Box>
                  <Typography
                    variant="h6"
                    fontWeight={700}
                    sx={{
                      lineHeight: 1.2,
                      mb: 0.5,
                      fontSize: "1.05rem",
                      display: "-webkit-box",
                      overflow: "hidden",
                      WebkitBoxOrient: "vertical",
                      WebkitLineClamp: 2,
                    }}
                  >
                    {displayName}
                  </Typography>
                  {!isOwned && (
                    <Typography
                      variant="caption"
                      sx={{
                        color: "text.secondary",
                        bgcolor: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.05)",
                        px: 1,
                        py: 0.25,
                        borderRadius: 1,
                      }}
                    >
                      View only
                    </Typography>
                  )}
                  {!!groupName && (
                    <Chip
                      size="small"
                      label={groupName}
                      sx={{
                        mt: 0.75,
                        bgcolor: isDark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.06)",
                        color: isDark ? "#e5e7eb" : "rgba(15,23,42,0.78)",
                      }}
                    />
                  )}
                </Box>
              </Box>
              
              <Box display="flex" alignItems="center" gap={0.5}>
                <Tooltip title={isHidden ? "Hidden. Click to show." : "Visible. Click to hide."}>
                  <IconButton
                    size="small"
                    onClick={(event) => {
                      event.stopPropagation();
                      handleToggleToken(tokenName, isHidden);
                    }}
                    disabled={!isOwned}
                    sx={{
                      p: 0.5,
                      bgcolor: isHidden ? "rgba(239,68,68,0.1)" : "rgba(34,197,94,0.1)",
                      color: isHidden ? "#ef4444" : "#22c55e",
                      "&:hover": {
                        bgcolor: isHidden ? "rgba(239,68,68,0.18)" : "rgba(34,197,94,0.18)",
                      },
                    }}
                    aria-label={isHidden ? "Show token" : "Hide token"}
                  >
                    {isHidden ? <VisibilityOffIcon fontSize="small" /> : <VisibilityIcon fontSize="small" />}
                  </IconButton>
                </Tooltip>
                <Tooltip title="Delete this token">
                  <IconButton
                    size="small"
                    onClick={(event) => {
                      event.stopPropagation();
                      requestDeleteToken(tokenName);
                    }}
                    disabled={!isOwned}
                    sx={{
                      p: 0.5,
                      color: "#ef4444",
                      "&:hover": {
                        bgcolor: "rgba(239,68,68,0.12)",
                      },
                    }}
                    aria-label={`Delete ${displayName}`}
                  >
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
            </Box>

            <Box mt={1.5} mb={2} flex={1}>{renderTokenProgress(tokenName)}</Box>

            <Box display="flex" alignItems="center" justifyContent="space-between" mt="auto">
              <Typography
                variant="caption"
                sx={{
                  color: isDark ? "rgba(233,237,242,0.72)" : "text.secondary",
                  pr: 1,
                }}
              >
                Updated {formatTokenUpdatedAt(tokenUpdatedAt)}
              </Typography>
              <Button
                size="small"
                variant="contained"
                onClick={(event) => {
                  event.stopPropagation();
                  openTokenMenu(event, tokenName);
                }}
                disabled={!isOwned}
                startIcon={<PlayArrowIcon />}
                endIcon={<ExpandMoreIcon fontSize="small" />}
                sx={{
                  ...shimmerSx,
                  bgcolor: isDark ? "rgba(125,224,210,0.15)" : "rgba(25,118,210,0.1)",
                  color: isDark ? "#7de0d2" : accent,
                  boxShadow: "none",
                  fontWeight: 600,
                  px: 2,
                  py: 0.5,
                  borderRadius: 2,
                  "&:hover": {
                    bgcolor: isDark ? "rgba(125,224,210,0.25)" : "rgba(25,118,210,0.18)",
                    boxShadow: "none",
                  },
                }}
                aria-label={`Run ${displayName}`}
              >
                Run
              </Button>
            </Box>
          </Box>
        </Box>
      );
    }

    return (
      <Box
        key={tokenName}
        display="flex"
        alignItems="center"
        gap={1}
        onClick={handleSelectFromCard}
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
            return applyTokenOrder(next);
          });
          setDragOverTokenName("");
        }}
        sx={{
          transition: "transform 180ms ease, background-color 180ms ease",
          ...(dragTokenName === tokenName ? { transform: "scale(1.01)" } : {}),
          ...(dragOverTokenName === tokenName ? { transform: "translateY(6px)" } : {}),
          cursor: canToggleSelectedFromCard ? "pointer" : "default",
        }}
      >
        {runSelectedMode && isOwned && !isHidden && (
          <Checkbox
            size="small"
            checked={isSelected}
            onChange={(event) => toggleSelectedToken(tokenName, event.target.checked)}
            onClick={(event) => event.stopPropagation()}
            sx={{
              color: isDark ? "#7ed6ff" : accent,
              "&.Mui-checked": { color: isDark ? "#43c2ff" : accent },
            }}
          />
        )}
        <Tooltip title="Drag to reorder tokens when you switch to List view.">
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
        </Tooltip>
        <Box
          display="flex"
          flexDirection="column"
          gap={0.75}
          sx={{
            flex: 1,
            border: `1px solid ${border}`,
            borderRadius: 1,
            p: 1,
            bgcolor: groupColor
              ? alpha(groupColor, isDark ? 0.14 : 0.1)
              : isDark
                ? "rgba(255,255,255,0.08)"
                : "rgba(255,255,255,0.75)",
            backdropFilter: "blur(10px)",
            WebkitBackdropFilter: "blur(10px)",
            opacity: isHidden ? 0.5 : 1,
            transition: "opacity 220ms ease, border-color 180ms ease, background-color 180ms ease",
            borderColor: groupColor
              ? alpha(groupColor, isDark ? 0.38 : 0.24)
              : border,
            "&:hover": {
              bgcolor: groupColor
                ? alpha(groupColor, isDark ? 0.2 : 0.14)
                : isDark
                  ? "rgba(255,255,255,0.12)"
                  : "rgba(25,118,210,0.08)",
              borderColor: groupColor
                ? alpha(groupColor, isDark ? 0.52 : 0.34)
                : isDark
                  ? "rgba(255,255,255,0.2)"
                  : "rgba(25,118,210,0.2)",
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
              <Avatar
                src={avatarSrc}
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
              {!isOwned && (
                <Typography variant="caption" color="text.secondary">
                  View only
                </Typography>
              )}
              {!!groupName && (
                <Chip
                  size="small"
                  label={groupName}
                  sx={{
                    bgcolor: isDark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.06)",
                    color: isDark ? "#e5e7eb" : "rgba(15,23,42,0.78)",
                  }}
                />
              )}
            </Box>
            {renderTokenControls(tokenName, displayName, isOwned, isHidden, "list")}
          </Box>
          {renderTokenProgress(tokenName)}
        </Box>
      </Box>
    );
  };


  const Shell = inline ? Box : Dialog;
  const shellProps = inline
    ? {
        sx: {
          position: "relative",
          zIndex: 0,
          color: isDark ? "#e9edf2" : "inherit",
        },
      }
    : {
        open,
        onClose,
        maxWidth: "md",
        fullWidth: true,
        fullScreen: isMobile,
        TransitionComponent: Fade,
        transitionDuration: 220,
        PaperProps: {
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
        },
      };

  return (
    <Shell {...shellProps}>
      {!inline && <DialogTitle sx={{ pb: 0.5, position: "relative", zIndex: 1 }} />}
      <DialogContent sx={{ position: "relative", zIndex: 1, minHeight: { xs: "calc(100vh - 140px)", sm: 520 }, display: "flex", flexDirection: "column", overflow: "hidden", px: { xs: 1.5, sm: 3 } }}>
          <Tabs
            value={activeTab}
            onChange={(_, next) => setActiveTab(next)}
            variant="scrollable"
            scrollButtons="auto"
            allowScrollButtonsMobile
            textColor="inherit"
            indicatorColor="primary"
            sx={{
              mt: 1,
              mb: 2,
              borderBottom: `1px solid ${border}`,
              minHeight: 44,
              "& .MuiTabs-flexContainer": {
                gap: 0.5,
              },
              "& .MuiTab-root": {
                minHeight: 44,
                textTransform: "none",
                fontWeight: 600,
                borderRadius: 2,
                px: 2,
                color: isDark ? "#d6deea" : "rgba(15,23,42,0.75)",
              },
              "& .Mui-selected": {
                color: "#fff !important",
                bgcolor: accent,
              },
              "& .MuiTabs-indicator": {
                display: "none",
              },
            }}
          >
            <Tab value="add" label="Manage Channel" />
            <Tab value="groups" label="Groups" />
            <Tab value="schedule" label="Schedule" />
            <Tab value="logs" label="Run logs" />
            {isAdmin && <Tab value="manage-user" label="Manage User" />}
          </Tabs>

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
                    Add new channel
                  </Typography>

                  <Tooltip title="Start Google sign-in. The app will auto-select the connected channel and begin syncing.">
                    <Button
                      variant="contained"
                      color="success"
                      startIcon={<AddIcon />}
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
                  </Tooltip>
                </Box>

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
                {progress.status !== "idle" && (
                  <Box display="flex" flexDirection="column" gap={0.5}>
                    <Box display="flex" alignItems="center" justifyContent="space-between">
                      <Typography
                        variant="body2"
                        color={status.message ? theme.palette.success.main : "text.secondary"}
                      >
                        {status.message
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
                    <Tooltip
                      title={
                        tokenView === "card"
                          ? "Switch to List view. List view exposes drag handles so you can reorder tokens."
                          : "Switch to Cards view. Compact cards are better for quick scanning."
                      }
                    >
                      <Box display="flex" alignItems="center" gap={0.75}>
                        <Typography
                          variant="caption"
                          sx={{ color: tokenView === "card" ? accent : "text.secondary", fontWeight: 700 }}
                        >
                          Cards
                        </Typography>
                        <Switch
                          checked={tokenView === "list"}
                          onChange={() => setTokenView((prev) => (prev === "card" ? "list" : "card"))}
                          size="small"
                          sx={{
                            mx: 0.25,
                            "& .MuiSwitch-switchBase.Mui-checked": {
                              color: accent,
                            },
                            "& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track": {
                              bgcolor: accent,
                              opacity: 1,
                            },
                            "& .MuiSwitch-track": {
                              bgcolor: isDark ? "rgba(255,255,255,0.25)" : "rgba(15,23,42,0.18)",
                              opacity: 1,
                            },
                          }}
                        />
                        <Typography
                          variant="caption"
                          sx={{ color: tokenView === "list" ? accent : "text.secondary", fontWeight: 700 }}
                        >
                          List
                        </Typography>
                      </Box>
                    </Tooltip>
                    <Box display="flex" alignItems="center" gap={1} flexWrap="wrap">
                      <Tooltip title={runSelectedMode ? "Exit selected-run mode." : "Choose specific visible channels to run."}>
                        <Button
                          size="small"
                          variant={runSelectedMode ? "contained" : "outlined"}
                          startIcon={<CheckIcon fontSize="small" />}
                          onClick={handleToggleRunSelectedMode}
                          disabled={loadingTokens || runningSelected || visibleOwnedTokenNames.length === 0}
                          sx={{
                            ...shimmerSx,
                            borderColor: isDark ? "rgba(255,255,255,0.2)" : undefined,
                            color: runSelectedMode ? "#fff" : isDark ? "#e9edf2" : undefined,
                            bgcolor: runSelectedMode ? accent : undefined,
                            "&:hover": runSelectedMode
                              ? {
                                  bgcolor: accent,
                                  opacity: 0.92,
                                }
                              : undefined,
                          }}
                        >
                          Run selected
                        </Button>
                      </Tooltip>
                      <Tooltip title="Run all visible tokens using the normal incremental content sync.">
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
                      </Tooltip>
                      <Tooltip title="Reload the token list from the server.">
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
                      </Tooltip>
                    </Box>
                  </Box>

                  {tokens.length === 0 ? (
                    <Typography variant="body2" color="text.secondary">
                      {loadingTokens ? "Loading tokens..." : "No tokens found."}
                    </Typography>
                  ) : (
                    tokenView === "card" ? (
                      <Box
                        display="grid"
                        gap={1.5}
                        sx={{
                          justifyContent: "start",
                          justifyItems: "start",
                          gridTemplateColumns: {
                            xs: "1fr",
                            sm: "repeat(auto-fill, minmax(220px, 1fr))",
                            lg: "repeat(auto-fill, minmax(240px, 1fr))",
                          },
                        }}
                      >
                        {tokens.map((token) => renderTokenItem(token, "card"))}
                      </Box>
                    ) : (
                      <Box display="flex" flexDirection="column" gap={1}>
                        {tokens.map((token) => renderTokenItem(token, "list"))}
                      </Box>
                    )
                  )}
                </Box>
              </>
            ) : (
              <>
                {activeTab === "groups" ? (
                  <Box
                    sx={{
                      bgcolor: panel,
                      border: `1px solid ${border}`,
                      borderRadius: 2,
                      p: 2,
                      display: "flex",
                      flexDirection: "column",
                      gap: 1.5,
                    }}
                  >
                    <Typography variant="subtitle2" sx={{ color: accent, letterSpacing: 0.3 }}>
                      Manage groups
                    </Typography>

                    <Box display="flex" gap={1} flexWrap="wrap">
                      <TextField
                        size="small"
                        label="New group"
                        value={groupDraft}
                        onChange={(event) => setGroupDraft(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            handleCreateTokenGroup();
                          }
                        }}
                        sx={{ minWidth: 220, flex: 1 }}
                      />
                      <Button
                        variant="contained"
                        onClick={handleCreateTokenGroup}
                        disabled={!groupDraft.trim() || savingGroup}
                        sx={shimmerSx}
                      >
                        Add group
                      </Button>
                    </Box>

                    {tokenGroups.length === 0 ? (
                      <Typography variant="body2" color="text.secondary">
                        No groups yet.
                      </Typography>
                    ) : (
                      <Box display="flex" flexDirection="column" gap={1}>
                        {tokenGroups.map((group) => {
                          const groupName = group.group_name;
                          const isEditing = editingGroupName === groupName;
                          return (
                            <Box
                              key={groupName}
                              display="flex"
                              alignItems="center"
                              gap={1}
                              flexWrap="wrap"
                              sx={{
                                p: 1,
                                border: `1px solid ${group.color ? alpha(group.color, isDark ? 0.42 : 0.26) : border}`,
                                borderRadius: 1.5,
                                bgcolor: group.color
                                  ? alpha(group.color, isDark ? 0.16 : 0.1)
                                  : isDark
                                    ? "rgba(255,255,255,0.04)"
                                    : "rgba(255,255,255,0.72)",
                              }}
                            >
                              {isEditing ? (
                                <TextField
                                  size="small"
                                  value={editingGroupDraft}
                                  onChange={(event) => setEditingGroupDraft(event.target.value)}
                                  sx={{ minWidth: 220, flex: 1 }}
                                />
                              ) : (
                                <Typography
                                  variant="body2"
                                  sx={{
                                    fontWeight: 600,
                                    color: isDark ? "#e5e7eb" : "rgba(15,23,42,0.78)",
                                    flex: 1,
                                    minWidth: 0,
                                  }}
                                >
                                  {groupName}
                                </Typography>
                              )}
                              <Box display="flex" alignItems="center" gap={0.5} flexWrap="wrap">
                                {isEditing ? (
                                  <>
                                    <Tooltip title="Save group name">
                                      <IconButton
                                        size="small"
                                        color="primary"
                                        onClick={() => handleRenameTokenGroup(groupName)}
                                        disabled={!editingGroupDraft.trim() || savingGroup}
                                        sx={{
                                          border: `1px solid ${border}`,
                                          bgcolor: isDark ? "rgba(125,224,210,0.12)" : "rgba(25,118,210,0.08)",
                                        }}
                                      >
                                        <CheckIcon fontSize="small" />
                                      </IconButton>
                                    </Tooltip>
                                    <Tooltip title="Cancel editing">
                                      <IconButton
                                        size="small"
                                        onClick={() => {
                                          setEditingGroupName("");
                                          setEditingGroupDraft("");
                                        }}
                                        sx={{
                                          border: `1px solid ${border}`,
                                        }}
                                      >
                                        <CloseIcon fontSize="small" />
                                      </IconButton>
                                    </Tooltip>
                                  </>
                                ) : (
                                  <Tooltip title="Rename group">
                                    <IconButton
                                      size="small"
                                      onClick={() => {
                                        setEditingGroupName(groupName);
                                        setEditingGroupDraft(groupName);
                                      }}
                                      sx={{
                                        border: `1px solid ${border}`,
                                      }}
                                    >
                                      <EditOutlinedIcon fontSize="small" />
                                    </IconButton>
                                  </Tooltip>
                                )}
                                <Tooltip title="Delete group">
                                  <IconButton
                                    size="small"
                                    color="error"
                                    onClick={() => handleDeleteTokenGroup(groupName)}
                                    disabled={savingGroup}
                                    sx={{
                                      border: `1px solid ${border}`,
                                      bgcolor: "rgba(239,68,68,0.08)",
                                    }}
                                  >
                                    <DeleteOutlineIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              </Box>
                            </Box>
                          );
                        })}
                      </Box>
                    )}
                  </Box>
                ) : activeTab === "manage-user" ? (
                  <ManageUserRequests active={activeTab === "manage-user"} />
                ) : activeTab === "schedule" ? (
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
                      {!isAdmin ? (
                        <Typography variant="body2" color="text.secondary">
                          Permission Denied
                        </Typography>
                      ) : schedulesError ? (
                        <Typography variant="body2" color="text.secondary">
                          {cleanError(schedulesError)}
                        </Typography>
                      ) : (
                        <>
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
                        </>
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
                            const normalizedStatus = normalizeRunStatus(run.status);
                            const styles = statusStyles(normalizedStatus);
                            const processed = run.processed ?? 0;
                            const total = run.total ?? 0;
                            const tokenName = formatTokenName(run.token_name);
                            const runType = formatRunType(run.run_type);
                            const runMessage = cleanError(run.message);
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
                                      {normalizedStatus}
                                    </Box>
                                    <Box display="flex" flexDirection="column" gap={0.25}>
                                      <Box display="flex" alignItems="center" gap={0.5} flexWrap="wrap">
                                        <Box
                                          sx={{
                                            px: 1,
                                            py: 0.2,
                                            borderRadius: 999,
                                            fontSize: 12,
                                            fontWeight: 600,
                                            bgcolor: isDark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.06)",
                                            color: isDark ? "#d6deea" : "rgba(15,23,42,0.72)",
                                          }}
                                        >
                                          {tokenName}
                                        </Box>
                                        <Box
                                          sx={{
                                            px: 1,
                                            py: 0.2,
                                            borderRadius: 999,
                                            fontSize: 12,
                                            fontWeight: 600,
                                            bgcolor: isDark ? "rgba(125,224,210,0.14)" : "rgba(25,118,210,0.08)",
                                            color: isDark ? "#7de0d2" : "#1976d2",
                                          }}
                                        >
                                          {runType}
                                        </Box>
                                      </Box>
                                    </Box>
                                  </Box>
                                  <Box display="flex" flexDirection="column" alignItems="flex-end" gap={0.5}>
                                    <Box display="flex" alignItems="center" gap={0.75} flexWrap="wrap" justifyContent="flex-end">
                                    {(normalizedStatus === "running" || normalizedStatus === "queued") && (
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
                                    {normalizedStatus !== "running" && normalizedStatus !== "queued" && (
                                      <Button
                                        size="small"
                                        onClick={() => handleResumeRun(run.id)}
                                        disabled={resumingRunId === run.id}
                                        sx={resumeButtonSx}
                                      >
                                        Resume
                                      </Button>
                                    )}
                                    </Box>
                                    <Typography variant="caption" color="text.secondary">
                                      {`${formatRunTime(run.started_at)} -> ${formatRunTime(
                                        run.finished_at
                                      )}`}
                                    </Typography>
                                  </Box>
                                </Box>
                                <Box
                                  display="flex"
                                  alignItems="center"
                                  justifyContent="space-between"
                                  gap={1}
                                >
                                  {normalizedStatus !== "running" && normalizedStatus !== "queued" ? (
                                    <Typography variant="caption" color="text.secondary">
                                      {`Accounts: ${processed}/${total}`}
                                    </Typography>
                                  ) : (
                                    <Box />
                                  )}
                                  {runMessage && runMessage.toLowerCase() !== "completed" ? (
                                    <Typography variant="body2" color="text.secondary">
                                      {runMessage}
                                    </Typography>
                                  ) : (
                                    <Box />
                                  )}
                                </Box>
                                {normalizedStatus === "running" && total > 0 && (
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
          <Fade in={runSelectedMode && selectedTokenNames.length > 0} unmountOnExit>
            <Box
              sx={{
                position: "fixed",
                right: { xs: 12, sm: 20 },
                bottom: { xs: 16, sm: 24 },
                zIndex: 3000,
                display: "flex",
                alignItems: "center",
                gap: 1,
                px: 1.25,
                py: 1,
                borderRadius: 999,
                border: `1px solid ${isDark ? "rgba(125,224,210,0.24)" : "rgba(25,118,210,0.14)"}`,
                bgcolor: isDark ? "rgba(17,24,39,0.94)" : "rgba(255,255,255,0.98)",
                boxShadow: isDark
                  ? "0 16px 40px rgba(0,0,0,0.45)"
                  : "0 16px 40px rgba(15,23,42,0.16)",
                backdropFilter: "blur(14px)",
                WebkitBackdropFilter: "blur(14px)",
                animation: "runSelectedFloatUp 220ms ease-out",
                "@keyframes runSelectedFloatUp": {
                  "0%": {
                    opacity: 0,
                    transform: "translateY(16px) scale(0.98)",
                  },
                  "100%": {
                    opacity: 1,
                    transform: "translateY(0) scale(1)",
                  },
                },
              }}
            >
              <Typography variant="body2" sx={{ fontWeight: 700 }}>
                {selectedTokenNames.length} selected
              </Typography>
              <Button
                size="small"
                variant="contained"
                color="success"
                startIcon={<PlayArrowIcon fontSize="small" />}
                onClick={handleConfirmRunSelected}
                disabled={runningSelected}
                sx={{
                  ...shimmerSx,
                  borderRadius: 999,
                  px: 1.5,
                  textTransform: "none",
                  fontWeight: 700,
                }}
              >
                Confirm
              </Button>
            </Box>
          </Fade>
      </DialogContent>
      {!inline && (
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
      )}
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
        <MenuItem onClick={() => handleRunToken(menuTokenName)}>
          Run incremental
        </MenuItem>
        <MenuItem onClick={handleRunFullBackfill}>
          Run full backfill
        </MenuItem>
      </Menu>
    </Shell>
  );
};

export default CredentialsDialog;
