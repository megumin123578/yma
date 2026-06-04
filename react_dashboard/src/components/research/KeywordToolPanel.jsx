// components/research/KeywordToolPanel.jsx — Keywordtool: bật chạy trước runall + harvest thủ công
import { useEffect, useRef, useState } from "react";
import { Box, Button, Chip, CircularProgress, FormControlLabel, Switch, Typography, useTheme } from "@mui/material";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import { getConfig, putConfig, runKeywordtool, getKeywordtoolStatus } from "../../services/researchService";

const describe = (last) => {
  if (!last) return null;
  if (last.ok === false) {
    const reason =
      last.reason === "no_api_key" ? "No API key (restart backend?)" : last.reason || "failed";
    return { text: `Error: ${reason}`, color: "error" };
  }
  if (last.reason === "empty") return { text: "No pending seeds — bank already full", color: "info" };
  const bank = last.stats?.keywords_total;
  const bankStr = bank != null ? ` · bank ${bank} kw` : "";
  if ((last.done ?? 0) === 0) {
    const why = last.stopped ? "quota/limit reached" : last.error || "no seeds harvested";
    return { text: `Stopped — 0 new (${why})${bankStr}`, color: "warning" };
  }
  return { text: `Done: ${last.done} seeds, +${last.keywords ?? 0} kw${bankStr}`, color: "success" };
};

const KeywordToolPanel = () => {
  const theme = useTheme();
  const [kwFirst, setKwFirst] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [progress, setProgress] = useState(null);
  const [err, setErr] = useState("");
  const pollRef = useRef(null);

  const startPoll = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const s = await getKeywordtoolStatus();
        setProgress(s.progress || null);
        if (!s.running) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setRunning(false);
          setResult(s.last || null);
          setProgress(null);
        }
      } catch {
        /* keep polling */
      }
    }, 3000);
  };

  useEffect(() => {
    getConfig()
      .then((d) => setKwFirst(!!d.run_keywordtool))
      .catch(() => {})
      .finally(() => setLoaded(true));
    getKeywordtoolStatus()
      .then((s) => {
        if (s.running) {
          setRunning(true);
          setProgress(s.progress || null);
          startPoll();
        } else if (s.last) {
          setResult(s.last);
        }
      })
      .catch(() => {});
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const toggle = (v) => {
    setKwFirst(v);
    putConfig({ run_keywordtool: v }).catch(() => {});
  };

  const handleRun = async () => {
    setErr("");
    setResult(null);
    setProgress(null);
    try {
      const r = await runKeywordtool();
      if (r.status === "started" || r.status === "running") {
        setRunning(true);
        startPoll();
      }
    } catch (e) {
      setErr(e?.response?.data?.detail || e.message);
    }
  };

  const info = err ? { text: err, color: "error" } : describe(result);

  return (
    <Box
      sx={{
        p: 1.5,
        border: `1px solid ${theme.palette.divider}`,
        borderRadius: 2,
        bgcolor: theme.palette.background.paper,
      }}
    >
      <Box display="flex" alignItems="center" justifyContent="space-between" gap={1}>
        <Typography variant="subtitle2" fontWeight={700}>
          Keywordtool
        </Typography>
        <FormControlLabel
          sx={{ m: 0 }}
          labelPlacement="start"
          control={
            <Switch size="small" checked={kwFirst} disabled={!loaded} onChange={(e) => toggle(e.target.checked)} />
          }
          label={
            <Typography variant="caption" color="text.secondary">
              Run before runall
            </Typography>
          }
        />
      </Box>
      <Box display="flex" alignItems="center" gap={1.5} mt={1} flexWrap="wrap">
        <Button
          variant="outlined"
          size="small"
          color="primary"
          startIcon={running ? <CircularProgress size={14} color="inherit" /> : <PlayArrowRoundedIcon />}
          onClick={handleRun}
          disabled={running}
        >
          {running ? "Running…" : "Run now"}
        </Button>
        {running && (
          <Typography variant="caption" color="text.secondary">
            {progress
              ? `Harvesting… ${progress.done}/${progress.total} seeds · ${(progress.keywords ?? 0).toLocaleString()} kw`
              : "Harvesting seeds via Keywordtool API…"}
          </Typography>
        )}
        {!running && info && <Chip size="small" variant="outlined" color={info.color} label={info.text} />}
      </Box>
    </Box>
  );
};

export default KeywordToolPanel;
