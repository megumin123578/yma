// components/research/SchedulePanel.jsx — lịch chạy daily run tự động
import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControlLabel,
  Paper,
  Switch,
  TextField,
  Typography,
  useTheme,
} from "@mui/material";
import SaveRoundedIcon from "@mui/icons-material/SaveRounded";
import { getSchedule, putSchedule } from "../../services/researchService";

const SchedulePanel = () => {
  const theme = useTheme();
  const [sch, setSch] = useState(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    getSchedule().then(setSch).catch((e) => setMsg(e?.response?.data?.detail || e.message));
  }, []);

  const set = (k, v) => setSch((s) => ({ ...s, [k]: v }));

  const handleSave = async () => {
    setSaving(true);
    setMsg("");
    try {
      const updated = await putSchedule({
        enabled: !!sch.enabled,
        time: sch.time || "04:00",
        aiOnly: !!sch.aiOnly,
        wlIds: null, // null = tất cả WL chưa paused
      });
      setSch(updated);
      setMsg("Đã lưu lịch.");
    } catch (e) {
      setMsg(e?.response?.data?.detail || e.message);
    } finally {
      setSaving(false);
    }
  };

  if (!sch) return <CircularProgress size={20} sx={{ m: 2 }} />;

  return (
    <Paper elevation={0} sx={{ p: 2, mt: 3, border: `1px solid ${theme.palette.divider}`, borderRadius: 2 }}>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={1.5} flexWrap="wrap" gap={1}>
        <Box>
          <Typography variant="h6" fontWeight={700}>Lịch chạy tự động</Typography>
          <Typography variant="caption" color="text.secondary">
            Đến giờ, hệ thống tự chạy daily run cho tất cả watchlist chưa tạm dừng (giờ máy chủ).
          </Typography>
        </Box>
        <Button
          size="small"
          variant="contained"
          startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <SaveRoundedIcon />}
          onClick={handleSave}
          disabled={saving}
        >
          Lưu
        </Button>
      </Box>
      {msg && <Chip size="small" label={msg} sx={{ mb: 1.5 }} />}
      <Box display="flex" gap={3} alignItems="center" flexWrap="wrap">
        <FormControlLabel
          control={<Switch checked={!!sch.enabled} onChange={(e) => set("enabled", e.target.checked)} />}
          label="Bật lịch"
        />
        <TextField
          size="small"
          type="time"
          label="Giờ chạy"
          value={sch.time || "04:00"}
          onChange={(e) => set("time", e.target.value)}
          InputLabelProps={{ shrink: true }}
          sx={{ width: 150 }}
        />
        <FormControlLabel
          control={<Switch checked={!!sch.aiOnly} onChange={(e) => set("aiOnly", e.target.checked)} />}
          label="Chỉ sinh AI (không monitor)"
        />
        {sch.lastRunDate && (
          <Typography variant="caption" color="text.secondary">
            Lần chạy gần nhất: {sch.lastRunDate}
          </Typography>
        )}
      </Box>
    </Paper>
  );
};

export default SchedulePanel;
