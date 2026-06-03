import { useEffect, useMemo, useState } from "react";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Tab,
  Tabs,
  Typography,
  useTheme,
} from "@mui/material";
import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";
import AutoAwesomeRoundedIcon from "@mui/icons-material/AutoAwesomeRounded";
import Header from "../../components/Header";
import RunPanel from "../../components/research/RunPanel";
import ConfigPanel from "../../components/research/ConfigPanel";
import SchedulePanel from "../../components/research/SchedulePanel";
import { TABS, TAB_GROUPS } from "../../components/research/reportTabs";
import { EmptyState } from "../../components/research/primitives";
import { generateAi, getReport, listWatchlists } from "../../services/researchService";

const ResearchScene = ({ view = "report" }) => {
  const theme = useTheme();
  const [watchlists, setWatchlists] = useState([]);
  const [wid, setWid] = useState("");
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [groupKey, setGroupKey] = useState("A");
  const [tabId, setTabId] = useState(null);
  const [aiMsg, setAiMsg] = useState("");

  const wlNameById = useMemo(
    () => Object.fromEntries(watchlists.map((w) => [w.id, w.name])),
    [watchlists]
  );

  // load watchlists
  useEffect(() => {
    let alive = true;
    listWatchlists()
      .then((items) => {
        if (!alive) return;
        setWatchlists(items);
        if (items.length && !wid) setWid(items[0].id);
      })
      .catch((e) => setError(e?.response?.data?.detail || e.message));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadReport = (id, refresh = false) => {
    if (!id) return;
    setLoading(true);
    setError("");
    getReport(id, { refresh })
      .then((d) => setReport(d))
      .catch((e) => {
        setReport(null);
        setError(e?.response?.data?.detail || e.message);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (wid) loadReport(wid);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wid]);

  const groupTabs = useMemo(() => TABS.filter((t) => t.group === groupKey), [groupKey]);

  // chọn tab đầu của nhóm khi đổi nhóm / load report
  useEffect(() => {
    if (groupTabs.length && !groupTabs.some((t) => t.id === tabId)) {
      setTabId(groupTabs[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groupKey, report]);

  const activeTab = TABS.find((t) => t.id === tabId);

  return (
    <Box m="20px">
      <Header
        title={view === "config" ? "Manage run" : "Nghiên cứu ngách"}
        subtitle={
          view === "config"
            ? "Daily run, quản lý watchlist, cấu hình và lịch chạy"
            : "Báo cáo watchlist (đối thủ, từ khoá, ngách)"
        }
      />

      {view === "config" && (
        <>
          <RunPanel wlNameById={wlNameById} />
          <ConfigPanel />
          <SchedulePanel />
        </>
      )}

      {view === "report" && (
        <>
      <Box display="flex" alignItems="center" gap={1.5} mb={2} flexWrap="wrap">
        <FormControl size="small" sx={{ minWidth: 280 }}>
          <InputLabel id="wl-label">Watchlist</InputLabel>
          <Select
            labelId="wl-label"
            label="Watchlist"
            value={wid}
            onChange={(e) => setWid(e.target.value)}
          >
            {watchlists.map((w) => (
              <MenuItem key={w.id} value={w.id}>
                {w.name}
                {w.paused ? "  (paused)" : ""}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button
          size="small"
          variant="outlined"
          startIcon={<RefreshRoundedIcon />}
          onClick={() => loadReport(wid, true)}
          disabled={loading || !wid}
        >
          Tải lại
        </Button>
        <Button
          size="small"
          variant="outlined"
          color="secondary"
          startIcon={<AutoAwesomeRoundedIcon />}
          onClick={async () => {
            if (!wid) return;
            setAiMsg("");
            try {
              const r = await generateAi(wid);
              setAiMsg(`Đang sinh AI (${r.runId})… bấm Tải lại khi xong.`);
            } catch (e) {
              setAiMsg(e?.response?.data?.detail || e.message);
            }
          }}
          disabled={!wid}
        >
          Sinh AI
        </Button>
        {report?.date && (
          <Typography variant="caption" color="text.secondary">
            Cập nhật: {report.date}
          </Typography>
        )}
        {loading && <CircularProgress size={18} />}
        {error && (
          <Chip size="small" color="error" variant="outlined" label={error} />
        )}
        {aiMsg && (
          <Typography variant="caption" color="text.secondary">
            {aiMsg}
          </Typography>
        )}
      </Box>

      {!report && !loading && (
        <EmptyState text={error ? `Lỗi: ${error}` : "Chọn một watchlist để xem báo cáo."} />
      )}

      {report && (
        <>
          <Tabs
            value={groupKey}
            onChange={(_, v) => setGroupKey(v)}
            variant="scrollable"
            scrollButtons="auto"
            sx={{ borderBottom: `1px solid ${theme.palette.divider}`, mb: 1.5 }}
          >
            {TAB_GROUPS.map((g) => (
              <Tab key={g.key} value={g.key} label={g.label} />
            ))}
          </Tabs>

          <Box display="flex" gap={0.75} flexWrap="wrap" mb={2}>
            {groupTabs.map((t) => (
              <Chip
                key={t.id}
                label={t.label}
                color={t.id === tabId ? "primary" : "default"}
                variant={t.id === tabId ? "filled" : "outlined"}
                onClick={() => setTabId(t.id)}
                sx={{ cursor: "pointer" }}
              />
            ))}
          </Box>

          <Box>
            {activeTab ? (
              (() => {
                try {
                  return activeTab.render(report);
                } catch (e) {
                  return <EmptyState text={`Lỗi render tab: ${e.message}`} />;
                }
              })()
            ) : (
              <EmptyState />
            )}
          </Box>
        </>
      )}
        </>
      )}
    </Box>
  );
};

export default ResearchScene;
