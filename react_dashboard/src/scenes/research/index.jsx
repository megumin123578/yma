import { useEffect, useMemo, useState } from "react";
import {
  Avatar,
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
import AutoAwesomeRoundedIcon from "@mui/icons-material/AutoAwesomeRounded";
import Header from "../../components/Header";
import { TABS, TAB_GROUPS } from "../../components/research/reportTabs";
import SeoReport from "../../components/research/SeoReport";
import useSeoReport from "../../components/research/useSeoReport";
import { EmptyState } from "../../components/research/primitives";
import { generateAi, getReport, listWatchlists } from "../../services/researchService";
import {
  getSharedFilterControlSx,
  getSharedSelectMenuProps,
} from "../../components/filterStyles";

const fmtDate = (s) => {
  const [y, m, d] = String(s || "").split("-");
  return y && m && d ? `${d}/${m}/${y}` : String(s || "");
};

const ResearchScene = ({ view = "report" }) => {
  const theme = useTheme();
  const filterControlSx = getSharedFilterControlSx(theme, { flex: "0 0 auto" });
  const selectMenuProps = getSharedSelectMenuProps(theme);
  const [watchlists, setWatchlists] = useState([]);
  const [wid, setWid] = useState("");
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [groupKey, setGroupKey] = useState("A");
  const [tabId, setTabId] = useState(null);
  const [aiMsg, setAiMsg] = useState("");

  const seo = useSeoReport(wid, view === "seo");

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

  const loadReport = (id, refresh = false, date = "") => {
    if (!id) return;
    setLoading(true);
    setError("");
    getReport(id, { refresh, date })
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
  // dark mode: primary.main trùng background → dùng secondary cho phần chọn
  const selColor = theme.palette.mode === "dark" ? "secondary" : "primary";

  return (
    <Box m="20px">
      <Header
        title={view === "seo" ? "Báo cáo SEO" : "Nghiên cứu ngách"}
        subtitle={
          view === "seo"
            ? "Báo cáo SEO theo watchlist (đối thủ, từ khoá, on-video, theo dõi)"
            : "Báo cáo watchlist (đối thủ, từ khoá, ngách)"
        }
      />

      {(view === "report" || view === "seo") && (
        <>
      <Box display="flex" alignItems="center" gap={1.5} mb={2} flexWrap="wrap">
        <FormControl size="small" sx={{ ...filterControlSx, minWidth: { xs: "100%", sm: 240 } }}>
          <InputLabel id="wl-label">Watchlist</InputLabel>
          <Select
            labelId="wl-label"
            label="Watchlist"
            value={wid}
            onChange={(e) => setWid(e.target.value)}
            MenuProps={selectMenuProps}
            renderValue={(val) => {
              const w = watchlists.find((x) => x.id === val);
              if (!w) return "";
              return (
                <Box display="flex" alignItems="center" gap={1} sx={{ minWidth: 0 }}>
                  <Avatar src={w.avatar || ""} sx={{ width: 22, height: 22 }}>
                    {(w.name || "?")[0]}
                  </Avatar>
                  <Typography variant="body2" noWrap>
                    {w.name}
                    {w.paused ? "  (paused)" : ""}
                  </Typography>
                </Box>
              );
            }}
          >
            {watchlists.map((w) => (
              <MenuItem key={w.id} value={w.id}>
                <Avatar src={w.avatar || ""} sx={{ width: 24, height: 24, mr: 1 }}>
                  {(w.name || "?")[0]}
                </Avatar>
                <Typography variant="body2" noWrap>
                  {w.name}
                  {w.paused ? "  (paused)" : ""}
                </Typography>
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        {view === "report" && report?.available_dates?.length > 0 && (
          <FormControl size="small" sx={{ ...filterControlSx, minWidth: { xs: "100%", sm: 175 } }}>
            <Select
              value={report.selected_date || ""}
              onChange={(e) => loadReport(wid, false, e.target.value)}
              disabled={loading}
              MenuProps={selectMenuProps}
              renderValue={(val) => `🗓 ${fmtDate(val)}`}
            >
              {report.available_dates.map((d) => (
                <MenuItem key={d} value={d}>
                  {fmtDate(d)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
        {view === "seo" && seo.items.length > 0 && (
          <FormControl size="small" sx={{ ...filterControlSx, minWidth: { xs: "100%", sm: 185 } }}>
            <Select
              value={seo.selId}
              onChange={(e) => seo.select(e.target.value)}
              MenuProps={selectMenuProps}
              renderValue={(val) => {
                const it = seo.items.find((i) => i.id === val);
                return `🗓 ${it?.date || ""}`;
              }}
            >
              {seo.items.map((it) => (
                <MenuItem key={it.id} value={it.id}>
                  {it.date}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
        {view === "seo" && (
          <Button
            size="small"
            variant="outlined"
            color="secondary"
            startIcon={<AutoAwesomeRoundedIcon />}
            onClick={seo.generate}
            disabled={!wid || seo.generating}
          >
            {seo.generating ? "Đang sinh…" : "Sinh báo cáo SEO"}
          </Button>
        )}
        {view === "report" && (
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
                setAiMsg(`Đang sinh AI (${r.runId})… tải lại trang khi xong để xem.`);
              } catch (e) {
                setAiMsg(e?.response?.data?.detail || e.message);
              }
            }}
            disabled={!wid}
          >
            Sinh AI
          </Button>
        )}
        {loading && <CircularProgress size={18} />}
        {error && (
          <Chip size="small" color="error" variant="outlined" label={error} />
        )}
        {view === "report" && aiMsg && (
          <Typography variant="caption" color="text.secondary">
            {aiMsg}
          </Typography>
        )}
      </Box>

      {view === "report" && !report && !loading && (
        <EmptyState text={error ? `Lỗi: ${error}` : "Chọn một watchlist để xem báo cáo."} />
      )}

      {view === "seo" && <SeoReport report={report} seo={seo} reportLoading={loading} />}

      {report && view === "report" && (
        <>
          <Tabs
            value={groupKey}
            onChange={(_, v) => setGroupKey(v)}
            variant="scrollable"
            scrollButtons="auto"
            textColor={selColor}
            indicatorColor={selColor}
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
                color={t.id === tabId ? selColor : "default"}
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
