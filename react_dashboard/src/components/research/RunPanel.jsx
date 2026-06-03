// components/research/RunPanel.jsx — trigger Daily Run + theo dõi tiến trình (SSE)
import { useEffect, useRef, useState } from "react";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  FormControl,
  InputLabel,
  LinearProgress,
  MenuItem,
  Select,
  Typography,
  useTheme,
} from "@mui/material";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import StopRoundedIcon from "@mui/icons-material/StopRounded";
import { getRun, startRun, stopRun, streamRun } from "../../services/researchService";

const STATUS_COLOR = {
  done: "success",
  running: "warning",
  failed: "error",
  pending: "default",
  skipped: "info",
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

const RunPanel = ({ wlNameById = {} }) => {
  const theme = useTheme();
  const [runId, setRunId] = useState(null);
  const [progress, setProgress] = useState(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [selectedWid, setSelectedWid] = useState("");
  const unsubRef = useRef(null);
  const wlOptions = Object.entries(wlNameById);

  const alive = !!progress?.alive;

  const attach = (rid) => {
    if (unsubRef.current) unsubRef.current();
    unsubRef.current = streamRun(rid, {
      onMessage: ({ data }) => {
        if (data && typeof data === "object") setProgress(data);
      },
    });
  };

  useEffect(() => () => unsubRef.current?.(), []);

  const runWith = async (payload) => {
    setBusy(true);
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

  const handleStart = () => runWith({}); // tất cả WL chưa paused
  const handleRunOne = () => {
    if (selectedWid) runWith({ wlIds: [selectedWid] });
  };

  const handleStop = async () => {
    if (!runId) return;
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

  return (
    <Box
      sx={{
        p: 1.5,
        mb: 2,
        border: `1px solid ${theme.palette.divider}`,
        borderRadius: 2,
        bgcolor: theme.palette.background.paper,
      }}
    >
      <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
        <Button
          variant="contained"
          color="error"
          startIcon={busy ? <CircularProgress size={16} color="inherit" /> : <PlayArrowRoundedIcon />}
          onClick={handleStart}
          disabled={busy || alive}
        >
          ⚡ Daily Run
        </Button>

        <FormControl size="small" sx={{ minWidth: 220 }} disabled={busy || alive}>
          <InputLabel id="run-wl-label">Chọn watchlist</InputLabel>
          <Select
            labelId="run-wl-label"
            label="Chọn watchlist"
            value={selectedWid}
            onChange={(e) => setSelectedWid(e.target.value)}
          >
            {wlOptions.map(([id, name]) => (
              <MenuItem key={id} value={id}>
                {name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button
          variant="outlined"
          color="error"
          startIcon={<PlayArrowRoundedIcon />}
          onClick={handleRunOne}
          disabled={busy || alive || !selectedWid}
        >
          ▶ Chạy 1 WL
        </Button>

        {alive && (
          <Button variant="outlined" color="warning" startIcon={<StopRoundedIcon />} onClick={handleStop}>
            Dừng
          </Button>
        )}
        {runId && (
          <Typography variant="caption" color="text.secondary">
            {runId} · {alive ? "đang chạy…" : "kết thúc"}
          </Typography>
        )}
        {progress?.error && (
          <Typography variant="caption" color="error">
            {progress.error}
          </Typography>
        )}
        <Box flexGrow={1} />
        {(runId || progress) && (
          <Button size="small" onClick={() => setOpen((o) => !o)}>
            {open ? "Ẩn tiến trình" : "Xem tiến trình"}
          </Button>
        )}
      </Box>

      {totalStages > 0 && (
        <Box mt={1.25}>
          <LinearProgress variant="determinate" value={pct} sx={{ height: 6, borderRadius: 3 }} />
          <Typography variant="caption" color="text.secondary">
            {doneStages}/{totalStages} stage · done {counts.done || 0} · failed {counts.failed || 0} · running{" "}
            {counts.running || 0}
          </Typography>
        </Box>
      )}

      <Collapse in={open}>
        <Box mt={1.5} display="flex" flexDirection="column" gap={1}>
          {wls.length === 0 && <Typography variant="caption" color="text.secondary">Chưa có tiến trình.</Typography>}
          {wls.map((wl) => (
            <Box
              key={wl.wlId}
              sx={{ p: 1, border: `1px solid ${theme.palette.divider}`, borderRadius: 1.5 }}
            >
              <Typography variant="body2" fontWeight={600} mb={0.5}>
                {wlNameById[wl.wlId] || wl.wlId}
              </Typography>
              <StageChips stages={wl.stages} />
            </Box>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
};

export default RunPanel;
