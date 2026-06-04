// components/research/RunPanel.jsx — trigger Daily Run + theo dõi tiến trình (SSE)
import { useEffect, useRef, useState } from "react";
import {
  Autocomplete,
  Avatar,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Divider,
  LinearProgress,
  TextField,
  Typography,
  useTheme,
} from "@mui/material";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import StopRoundedIcon from "@mui/icons-material/StopRounded";
import WifiOffRoundedIcon from "@mui/icons-material/WifiOffRounded";
import { getActiveRuns, getRun, startRun, stopRun, streamRun } from "../../services/researchService";

const STATUS_COLOR = {
  done: "success",
  running: "warning",
  failed: "error",
  pending: "default",
  skipped: "info",
};

const ROLLUP_RANK = { running: 0, failed: 1, pending: 2, done: 3, skipped: 4 };

const rollup = (stages = []) => {
  if (stages.some((s) => s.status === "running")) return "running";
  if (stages.some((s) => s.status === "failed")) return "failed";
  if (stages.length && stages.every((s) => s.status === "done" || s.status === "skipped")) return "done";
  return "pending";
};

const fmtElapsed = (ms) => {
  const sec = Math.floor(ms / 1000);
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
};

const StageChips = ({ stages }) => (
  <Box display="flex" gap={0.5} flexWrap="wrap">
    {stages.map((s, i) => (
      <Chip
        key={i}
        size="small"
        variant="outlined"
        color={STATUS_COLOR[s.status] || "default"}
        label={s.stage}
        title={s.error || s.status}
      />
    ))}
  </Box>
);

const CountChips = ({ counts }) => {
  const items = [
    ["done", counts.done, "success"],
    ["running", counts.running, "warning"],
    ["failed", counts.failed, "error"],
    ["skipped", counts.skipped, "info"],
    ["pending", counts.pending, "default"],
  ].filter(([, n]) => n);
  return (
    <Box display="flex" gap={0.75} flexWrap="wrap" mt={0.75}>
      {items.map(([k, n, c]) => (
        <Chip key={k} size="small" variant="outlined" color={c} label={`${k} ${n}`} sx={{ height: 20 }} />
      ))}
    </Box>
  );
};

const RunPanel = ({ wlNameById = {}, wlAvatarById = {} }) => {
  const theme = useTheme();
  const [runId, setRunId] = useState(null);
  const [progress, setProgress] = useState(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [selectedWid, setSelectedWid] = useState("");
  const [connLost, setConnLost] = useState(false);
  const [, setTick] = useState(0);
  const unsubRef = useRef(null);
  const startTsRef = useRef(null);

  const wlList = Object.entries(wlNameById).map(([id, name]) => ({
    id,
    label: name,
    avatar: wlAvatarById[id] || "",
  }));
  const selectedOption = wlList.find((o) => o.id === selectedWid) || null;
  const alive = !!progress?.alive;

  const attach = (rid) => {
    if (unsubRef.current) unsubRef.current();
    unsubRef.current = streamRun(rid, {
      onOpen: () => setConnLost(false),
      onMessage: ({ data }) => {
        setConnLost(false);
        if (data && typeof data === "object") setProgress(data);
      },
      onError: () => setConnLost(true),
    });
  };

  // Mở lại panel: re-attach vào run còn sống (panel hoặc scheduler đã khởi tạo).
  useEffect(() => {
    let cancelled = false;
    getActiveRuns()
      .then((runs) => {
        if (cancelled || !runs.length) return;
        const r = runs[0];
        setRunId(r.runId);
        setProgress(r);
        setOpen(true);
        attach(r.runId);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      unsubRef.current?.();
    };
  }, []);

  // Ticker cho elapsed (chỉ chạy khi còn sống).
  useEffect(() => {
    if (!alive) return undefined;
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, [alive]);

  const runWith = async (payload) => {
    setBusy(true);
    setConnLost(false);
    startTsRef.current = Date.now();
    try {
      const res = await startRun(payload);
      setRunId(res.runId);
      setOpen(true);
      const snap = await getRun(res.runId).catch(() => null);
      if (snap) setProgress(snap);
      attach(res.runId);
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message;
      setProgress({ error: msg });
      setOpen(true);
    } finally {
      setBusy(false);
    }
  };

  const handleStart = () => {
    const n = wlList.length;
    const hint = n ? ` (≈${n} watchlists)` : "";
    if (!window.confirm(`Run all non-paused watchlists${hint}?\nThis may take 1–2 hours.`)) return;
    runWith({});
  };
  const handleRunOne = () => {
    if (!selectedWid) return;
    const name = wlNameById[selectedWid] || selectedWid;
    if (!window.confirm(`Run watchlist "${name}"?`)) return;
    runWith({ wlIds: [selectedWid] });
  };

  const handleStop = async () => {
    if (!runId) return;
    if (!window.confirm("Stop the running job?")) return;
    try {
      await stopRun(runId);
    } catch {
      /* ignore */
    }
  };

  const counts = progress?.counts || {};
  const wls = progress?.watchlists || [];
  const totalStages = Object.values(counts).reduce((a, b) => a + b, 0);
  const doneStages = (counts.done || 0) + (counts.skipped || 0);
  const pct = totalStages ? Math.round((doneStages / totalStages) * 100) : 0;
  const elapsed = alive && startTsRef.current ? fmtElapsed(Date.now() - startTsRef.current) : null;

  const sortedWls = [...wls].sort(
    (a, b) => (ROLLUP_RANK[rollup(a.stages)] ?? 9) - (ROLLUP_RANK[rollup(b.stages)] ?? 9)
  );

  return (
    <Box
      sx={{
        p: 1.5,
        border: `1px solid ${theme.palette.divider}`,
        borderRadius: 2,
        bgcolor: theme.palette.background.paper,
      }}
    >
      {/* Header: tiêu đề + trạng thái run hiện tại */}
      <Box display="flex" alignItems="center" gap={1} mb={1.25} flexWrap="wrap">
        <Typography variant="subtitle2" fontWeight={700}>
          Manual run
        </Typography>
        <Box flexGrow={1} />
        {connLost && (
          <Chip
            size="small"
            color="warning"
            variant="outlined"
            icon={<WifiOffRoundedIcon />}
            label="Connection lost — retrying…"
          />
        )}
        {alive ? (
          <>
            <Box
              sx={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                bgcolor: "warning.main",
                animation: "rpPulse 1.2s ease-in-out infinite",
                "@keyframes rpPulse": { "0%,100%": { opacity: 1 }, "50%": { opacity: 0.25 } },
              }}
            />
            <Typography variant="caption" color="warning.main" fontWeight={600}>
              Running{elapsed ? ` · ${elapsed}` : ""}
            </Typography>
            <Button
              size="small"
              variant="outlined"
              color="warning"
              startIcon={<StopRoundedIcon />}
              onClick={handleStop}
            >
              Stop
            </Button>
          </>
        ) : runId ? (
          <Typography variant="caption" color="text.secondary">
            Finished
          </Typography>
        ) : null}
      </Box>

      {/* Controls — ẩn khi đang chạy để gọn */}
      {!alive && (
        <Box display="flex" flexDirection="column" gap={1.25}>
          <Button
            variant="contained"
            color="error"
            startIcon={busy ? <CircularProgress size={16} color="inherit" /> : <PlayArrowRoundedIcon />}
            onClick={handleStart}
            disabled={busy}
            sx={{ alignSelf: "flex-start" }}
          >
            ⚡ runall
          </Button>

          <Divider textAlign="center" sx={{ "& .MuiDivider-wrapper": { px: 1 } }}>
            <Typography variant="caption" color="text.secondary">
              or run a single watchlist
            </Typography>
          </Divider>

          <Box display="flex" gap={1} alignItems="flex-start" flexWrap="wrap">
            <Autocomplete
              size="small"
              sx={{ flex: 1, minWidth: 220 }}
              options={wlList}
              value={selectedOption}
              onChange={(_, v) => setSelectedWid(v?.id || "")}
              isOptionEqualToValue={(o, v) => o.id === v.id}
              disabled={busy}
              noOptionsText="No watchlists"
              renderOption={(props, option) => {
                const { key, ...rest } = props;
                return (
                  <Box component="li" key={key} {...rest} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <Avatar src={option.avatar || undefined} sx={{ width: 22, height: 22, fontSize: 11 }}>
                      {(option.label || "?").charAt(0).toUpperCase()}
                    </Avatar>
                    <Typography variant="body2" noWrap>
                      {option.label}
                    </Typography>
                  </Box>
                );
              }}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Select watchlist"
                  placeholder="Type to search…"
                  InputProps={{
                    ...params.InputProps,
                    startAdornment: selectedOption ? (
                      <Avatar
                        src={selectedOption.avatar || undefined}
                        sx={{ width: 20, height: 20, fontSize: 10, ml: 0.5 }}
                      >
                        {(selectedOption.label || "?").charAt(0).toUpperCase()}
                      </Avatar>
                    ) : (
                      params.InputProps.startAdornment
                    ),
                  }}
                />
              )}
            />
            <Button
              variant="outlined"
              size="small"
              color="error"
              startIcon={<PlayArrowRoundedIcon />}
              onClick={handleRunOne}
              disabled={busy || !selectedWid}
              sx={{ height: 40 }}
            >
              Run
            </Button>
          </Box>
        </Box>
      )}

      {progress?.error && (
        <Typography variant="caption" color="error" sx={{ display: "block", mt: 1 }}>
          {progress.error}
        </Typography>
      )}

      {/* Tiến trình */}
      {totalStages > 0 && (
        <Box mt={1.5}>
          <Box display="flex" alignItems="center" gap={1}>
            <Box flexGrow={1}>
              <LinearProgress variant="determinate" value={pct} sx={{ height: 8, borderRadius: 4 }} />
            </Box>
            <Typography variant="caption" fontWeight={700} sx={{ minWidth: 34, textAlign: "right" }}>
              {pct}%
            </Typography>
            <Button size="small" onClick={() => setOpen((o) => !o)}>
              {open ? "Hide" : "Details"}
            </Button>
          </Box>
          <CountChips counts={counts} />
        </Box>
      )}

      <Collapse in={open}>
        <Box mt={1.5} display="flex" flexDirection="column" gap={1}>
          {sortedWls.length === 0 && (
            <Typography variant="caption" color="text.secondary">
              No progress yet.
            </Typography>
          )}
          {sortedWls.map((wl) => {
            const st = rollup(wl.stages);
            const errs = (wl.stages || []).filter((s) => s.status === "failed" && s.error);
            return (
              <Box key={wl.wlId} sx={{ p: 1, border: `1px solid ${theme.palette.divider}`, borderRadius: 1.5 }}>
                <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                  <Chip size="small" color={STATUS_COLOR[st] || "default"} label={st} sx={{ height: 18 }} />
                  <Typography variant="body2" fontWeight={600}>
                    {wlNameById[wl.wlId] || wl.wlId}
                  </Typography>
                </Box>
                <StageChips stages={wl.stages} />
                {errs.map((s, i) => (
                  <Typography key={i} variant="caption" color="error" sx={{ display: "block", mt: 0.5 }}>
                    {s.stage}: {s.error}
                  </Typography>
                ))}
              </Box>
            );
          })}
        </Box>
      </Collapse>
    </Box>
  );
};

export default RunPanel;
