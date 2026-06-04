// components/research/ConfigPanel.jsx — cấu hình research (~/.youtube_research/config.json)
import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControlLabel,
  MenuItem,
  Paper,
  Switch,
  TextField,
  Typography,
  useTheme,
} from "@mui/material";
import SaveRoundedIcon from "@mui/icons-material/SaveRounded";
import { getConfig, putConfig } from "../../services/researchService";

// type: text | password | number | switch | select(options)
const FIELDS = [
  { key: "chrome_mode", label: "Chrome mode", type: "select", options: ["headless", "show", "minimized"] },
  { key: "parallel_workers", label: "Parallel workers", type: "number" },
  { key: "auto_discover_competitors", label: "Auto-discover competitors", type: "switch" },
  { key: "auto_discover_threshold", label: "Discover threshold (%)", type: "number" },
  { key: "auto_discover_max", label: "Max competitors per run", type: "number" },
  { key: "keywordtool_api_key", label: "Keywordtool API key", type: "password" },
];

const ConfigPanel = () => {
  const theme = useTheme();
  const [cfg, setCfg] = useState(null);
  const [form, setForm] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const load = () => {
    setLoading(true);
    getConfig()
      .then((d) => {
        setCfg(d);
        const f = {};
        FIELDS.forEach((fld) => {
          if (fld.type === "password") f[fld.key] = "";
          else f[fld.key] = d[fld.key] ?? "";
        });
        setForm(f);
      })
      .catch((e) => setMsg(e?.response?.data?.detail || e.message))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const setVal = (k, v) => setForm((s) => ({ ...s, [k]: v }));

  const handleSave = async () => {
    setSaving(true);
    setMsg("");
    try {
      const values = {};
      FIELDS.forEach((fld) => {
        const v = form[fld.key];
        if (fld.type === "password") {
          if (v && String(v).trim()) values[fld.key] = v; // chỉ gửi khi nhập mới
        } else {
          values[fld.key] = v;
        }
      });
      const updated = await putConfig(values);
      setCfg(updated);
      setMsg("Config saved.");
    } catch (e) {
      setMsg(e?.response?.data?.detail || e.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading || !cfg) return <CircularProgress size={20} sx={{ m: 2 }} />;

  return (
    <Paper elevation={0} sx={{ p: 2, mt: 3, border: `1px solid ${theme.palette.divider}`, borderRadius: 2 }}>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={1.5} flexWrap="wrap" gap={1}>
        <Typography variant="h6" fontWeight={700}>Research config</Typography>
        <FormControlLabel
          control={
            <Switch
              checked={!!form.auto_discover_competitors}
              onChange={(e) => setVal("auto_discover_competitors", e.target.checked)}
            />
          }
          label="Discover competitors"
        />
      </Box>
      {msg && <Chip size="small" label={msg} sx={{ mb: 1.5 }} />}
      <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 2 }}>
        {FIELDS.filter((fld) => fld.key !== "auto_discover_competitors").map((fld) => {
          if (fld.type === "switch") {
            return (
              <FormControlLabel
                key={fld.key}
                control={<Switch checked={!!form[fld.key]} onChange={(e) => setVal(fld.key, e.target.checked)} />}
                label={fld.label}
              />
            );
          }
          if (fld.type === "select") {
            return (
              <TextField
                key={fld.key}
                select
                size="small"
                label={fld.label}
                value={form[fld.key] ?? ""}
                onChange={(e) => setVal(fld.key, e.target.value)}
              >
                {fld.options.map((o) => (
                  <MenuItem key={o} value={o}>{o === "" ? "(off)" : o}</MenuItem>
                ))}
              </TextField>
            );
          }
          const isPw = fld.type === "password";
          return (
            <TextField
              key={fld.key}
              size="small"
              type={isPw ? "password" : fld.type === "number" ? "number" : "text"}
              label={fld.label}
              value={form[fld.key] ?? ""}
              placeholder={isPw && cfg[`${fld.key}_set`] ? "•••••• (set — leave blank to keep)" : ""}
              InputLabelProps={isPw ? { shrink: true } : undefined}
              onChange={(e) => setVal(fld.key, e.target.value)}
            />
          );
        })}
      </Box>
      <Box display="flex" justifyContent="flex-end" mt={2}>
        <Button
          size="small"
          variant="contained"
          startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <SaveRoundedIcon />}
          onClick={handleSave}
          disabled={saving}
        >
          Save
        </Button>
      </Box>
    </Paper>
  );
};

export default ConfigPanel;
