import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  TextField,
  Divider,
  Fade,
  Checkbox,
  Switch,
  useTheme,
} from "@mui/material";
import { useEffect, useState } from "react";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import RefreshIcon from "@mui/icons-material/Refresh";
import {
  uploadCredentials,
  listTokens,
  deleteToken,
  getTokenProgress,
  setTokenVisibility,
  listSchedules,
  createSchedule,
  updateSchedule,
  deleteSchedule,
} from "../../services/userService";

const CredentialsDialog = ({ open, onClose }) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const surface = isDark ? "rgba(17, 24, 39, 0.72)" : "rgba(255,255,255,0.82)";
  const panel = isDark ? "rgba(20, 28, 40, 0.55)" : "rgba(255,255,255,0.7)";
  const border = isDark ? "rgba(255,255,255,0.14)" : "rgba(0,0,0,0.08)";
  const accent = isDark ? "#7de0d2" : theme.palette.primary.main;
  const [file, setFile] = useState(null);
  const [filename, setFilename] = useState("");
  const [status, setStatus] = useState({ type: "", message: "" });
  const [uploading, setUploading] = useState(false);
  const [authUrl, setAuthUrl] = useState("");
  const [tokens, setTokens] = useState([]);
  const [loadingTokens, setLoadingTokens] = useState(false);
  const [, setTokenSyncing] = useState(false);
  const [progress, setProgress] = useState({ status: "idle", percent: 0, stage: "" });
  const [autoReloaded, setAutoReloaded] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState("");
  const [activeTab, setActiveTab] = useState("add");
  const [schedules, setSchedules] = useState([]);
  const [scheduleForm, setScheduleForm] = useState({
    time_of_day: "08:00",
  });

  useEffect(() => {
    if (open) {
      setFile(null);
      setFilename("");
      setStatus({ type: "", message: "" });
      setUploading(false);
      setAuthUrl("");
      setProgress({ status: "idle", percent: 0, stage: "" });
      setAutoReloaded(false);
      setActiveTab("add");
      loadTokens();
      loadSchedules();
    }
  }, [open]);

  useEffect(() => {
    if (activeTab === "schedule") {
      loadSchedules();
    }
  }, [activeTab]);

  useEffect(() => {
    if (!authUrl || !filename) return;
    let stopped = false;
    setTokenSyncing(true);

    const poll = async () => {
      try {
        const data = await listTokens();
        const nextTokens = data?.tokens || [];
        setTokens(nextTokens);
        if (nextTokens.some((t) => t.name === `${filename}.pickle`)) {
          stopped = true;
          setTokenSyncing(false);
        }
      } catch (err) {
        setTokens([]);
        setTokenSyncing(false);
      }
    };

    const intervalId = setInterval(() => {
      if (!stopped) {
        poll();
      }
    }, 2000);

    poll();

    return () => clearInterval(intervalId);
  }, [authUrl, filename, setTokenSyncing]);

  useEffect(() => {
    if (!filename) return;
    let canceled = false;
    const tokenName = `${filename}.pickle`;

    const pollProgress = async () => {
      try {
        const data = await getTokenProgress(tokenName);
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
  }, [filename]);

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

  const loadTokens = async () => {
    setLoadingTokens(true);
    try {
      const data = await listTokens();
      setTokens(data?.tokens || []);
    } catch (err) {
      setTokens([]);
    } finally {
      setLoadingTokens(false);
    }
  };

  const loadSchedules = async () => {
    try {
      const data = await listSchedules();
      setSchedules(data?.items || []);
    } catch (err) {
      setSchedules([]);
    }
  };

  const handleSelectFile = (event) => {
    const selected = event.target.files?.[0];
    if (!selected) return;

    if (!selected.name.toLowerCase().endsWith(".json")) {
      setStatus({
        type: "error",
        message: "Please select a .json credentials file.",
      });
      setFile(null);
      setFilename("");
      return;
    }

    setStatus({ type: "", message: "" });
    setFile(selected);
    setAuthUrl("");
    setProgress({ status: "idle", percent: 0, stage: "" });
    setAutoReloaded(false);
    const base = selected.name.toLowerCase().endsWith(".json")
      ? selected.name.slice(0, -5)
      : selected.name;
    setFilename(base);
    handleUpload(selected, base);
  };

  const handleFilenameChange = (event) => {
    const raw = event.target.value || "";
    setFilename(raw.toLowerCase().endsWith(".json") ? raw.slice(0, -5) : raw);
  };

  const handleUpload = async (fileOverride, nameOverride) => {
    const targetFile = fileOverride || file;
    const targetName = typeof nameOverride === "string" ? nameOverride : filename;
    if (!targetFile || uploading) return;

    setUploading(true);
    setStatus({ type: "", message: "" });
    setProgress({ status: "idle", percent: 0, stage: "" });
    setAutoReloaded(false);

    try {
      const safeName = targetName.trim() ? `${targetName.trim()}.json` : "";
      const data = await uploadCredentials(targetFile, safeName);
      const nextUrl = data?.auth_url || "";
      setAuthUrl(nextUrl);
      if (!nextUrl) {
        await loadTokens();
      }
      setStatus({
        type: "success",
        message: nextUrl
          ? "Credentials uploaded. Click the link to authorize."
          : "Credentials uploaded successfully.",
      });
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Upload failed. Please try again.";
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

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
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
          width: { xs: "95vw", md: 860 },
          maxWidth: "95vw",
          minHeight: 620,
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
            Add Channel
          </Typography>
          <Typography variant="body2" sx={{ color: isDark ? "#aab4c2" : "text.secondary" }}>
            Upload credentials, then authorize in your preferred browser profile.
          </Typography>
        </Box>
      </DialogTitle>
      <DialogContent sx={{ position: "relative", zIndex: 1, minHeight: 520 }}>
        <Box display="flex" gap={2} mt={1}>
          <Box
            sx={{
              minWidth: 140,
              display: "flex",
              flexDirection: "column",
              gap: 1,
            }}
          >
            <Button
              variant="text"
              onClick={() => setActiveTab("add")}
              sx={{
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
          </Box>

          <Box display="flex" flexDirection="column" gap={2} flex={1}>
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
                    Upload credentials
                  </Typography>

                  <Button
                    variant="outlined"
                    component="label"
                    startIcon={<UploadFileIcon />}
                    sx={{
                      borderColor: isDark ? "rgba(255,255,255,0.2)" : undefined,
                      color: isDark ? "#e9edf2" : undefined,
                      transition: "all 180ms ease",
                      "&:hover": {
                        borderColor: isDark ? "rgba(255,255,255,0.4)" : undefined,
                        backgroundColor: isDark ? "rgba(255,255,255,0.06)" : undefined,
                        transform: "translateY(-1px)",
                      },
                    }}
                  >
                    {file ? file.name : "Choose Credentials file"}
                    <input
                      hidden
                      type="file"
                      accept=".json,application/json"
                      onChange={handleSelectFile}
                    />
                  </Button>

                  {file && (
                    <TextField
                      label="File name"
                      size="small"
                      value={filename}
                      onChange={handleFilenameChange}
                      placeholder="example.json"
                      InputLabelProps={{ style: { color: isDark ? "#aab4c2" : undefined } }}
                      sx={{
                        input: { color: isDark ? "#e9edf2" : undefined },
                        "& .MuiOutlinedInput-notchedOutline": {
                          borderColor: isDark ? "rgba(255,255,255,0.2)" : undefined,
                        },
                      }}
                    />
                  )}
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
                    {status.message}
                  </Typography>
                )}

                {authUrl && (
                  <Button
                    variant="contained"
                    color="success"
                    href={authUrl}
                    target="_blank"
                    rel="noopener"
                    sx={{
                      bgcolor: isDark ? "#2b8a7b" : undefined,
                      transition: "transform 180ms ease",
                      "&:hover": {
                        bgcolor: isDark ? "#247468" : undefined,
                        transform: "translateY(-1px)",
                      },
                    }}
                  >
                    Open Authorization Link
                  </Button>
                )}

                {progress.status !== "idle" && (
                  <Box display="flex" flexDirection="column" gap={0.5}>
                    <Box display="flex" alignItems="center" justifyContent="space-between">
                      <Typography variant="body2" color="text.secondary">
                        {progress.stage || "Processing"}
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
                    {progress.message && (
                      <Typography variant="caption" color="text.secondary">
                        {progress.message}
                      </Typography>
                    )}
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
                    <Button
                      size="small"
                      onClick={loadTokens}
                      disabled={loadingTokens}
                      sx={{
                        minWidth: 0,
                        color: isDark ? "#9fe3d6" : undefined,
                      }}
                    >
                      <RefreshIcon fontSize="small" />
                    </Button>
                  </Box>

                  {tokens.length === 0 ? (
                    <Typography variant="body2" color="text.secondary">
                      {loadingTokens ? "Loading tokens..." : "No tokens found."}
                    </Typography>
                  ) : (
                    <Box display="flex" flexDirection="column" gap={1}>
                      {tokens.map((token) => {
                        const tokenName = typeof token === "string" ? token : token.name || "";
                        const displayName = tokenName.toLowerCase().endsWith(".pickle")
                          ? tokenName.slice(0, -7)
                          : tokenName;
                        const isHidden = typeof token === "string" ? false : !!token.hidden;
                        return (
                          <Box
                            key={tokenName}
                            display="flex"
                            alignItems="center"
                            justifyContent="space-between"
                            sx={{
                              border: `1px solid ${border}`,
                              borderRadius: 1,
                              p: 1,
                              bgcolor: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.75)",
                              backdropFilter: "blur(10px)",
                              WebkitBackdropFilter: "blur(10px)",
                              transition: "all 180ms ease",
                              "&:hover": {
                                bgcolor: isDark ? "rgba(255,255,255,0.12)" : "rgba(25,118,210,0.08)",
                                borderColor: isDark ? "rgba(255,255,255,0.2)" : "rgba(25,118,210,0.2)",
                              },
                            }}
                          >
                      <Box display="flex" alignItems="center" gap={1}>
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
                              <Typography variant="body2">{displayName}</Typography>
                            </Box>
                            <Button
                              size="small"
                              color="error"
                              onClick={() => requestDeleteToken(tokenName)}
                            >
                              Delete
                            </Button>
                          </Box>
                        );
                      })}
                    </Box>
                  )}
                </Box>
              </>
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
                      {status.message}
                    </Typography>
                  )}
                  <TextField
                    label="Time"
                    type="time"
                    size="small"
                    value={scheduleForm.time_of_day}
                    onChange={(e) => handleScheduleField("time_of_day", e.target.value)}
                    InputLabelProps={{ shrink: true }}
                  />

                  <Button variant="contained" onClick={handleCreateSchedule}>
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
            )}
          </Box>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button
          onClick={onClose}
          disabled={uploading}
          sx={{ color: isDark ? "#aab4c2" : "text.secondary" }}
        >
          Cancel
        </Button>
        <Button variant="contained" onClick={handleDone} disabled={uploading}>
          Done
        </Button>
      </DialogActions>
      <Dialog
        open={confirmOpen}
        onClose={handleConfirmClose}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Confirm Delete</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            This will delete the token and its matching credentials file. Continue?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleConfirmClose}>Cancel</Button>
          <Button color="error" variant="contained" onClick={handleConfirmDelete}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Dialog>
  );
};

export default CredentialsDialog;
