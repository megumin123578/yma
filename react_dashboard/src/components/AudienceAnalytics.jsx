import { useEffect, useMemo, useState } from "react";
import {
  Box,
  CircularProgress,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Typography,
  useTheme,
} from "@mui/material";
import { ResponsiveLine } from "@nivo/line";
import { API_BASE } from "../config";

const AudienceAnalytics = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const [accountTag, setAccountTag] = useState("");
  const [accounts, setAccounts] = useState([]);
  const [demoRows, setDemoRows] = useState([]);
  const [demoRange, setDemoRange] = useState({ start: "", end: "" });
  const [retentionRows, setRetentionRows] = useState([]);
  const [retentionRange, setRetentionRange] = useState({ start: "", end: "" });
  const [videos, setVideos] = useState([]);
  const [videoId, setVideoId] = useState("");
  const [loading, setLoading] = useState(false);

  const authHeaders = useMemo(() => {
    const token = localStorage.getItem("access_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  useEffect(() => {
    const loadAccounts = async () => {
      try {
        const resp = await fetch(`${API_BASE}/api/audience/demographics`, {
          headers: authHeaders,
        });
        const data = await resp.json();
        const nextAccounts = data?.availableAccounts || [];
        setAccounts(nextAccounts);
        if (!accountTag && nextAccounts.length > 0) {
          setAccountTag(nextAccounts[0]);
        }
      } catch (err) {
        setAccounts([]);
      }
    };
    loadAccounts();
  }, [accountTag, authHeaders]);

  useEffect(() => {
    if (!accountTag) return;
    const loadDemographics = async () => {
      setLoading(true);
      try {
        const resp = await fetch(
          `${API_BASE}/api/audience/demographics?accountTag=${encodeURIComponent(accountTag)}`,
          { headers: authHeaders }
        );
        const data = await resp.json();
        setDemoRows(data?.rows || []);
        setDemoRange({ start: data?.start_date || "", end: data?.end_date || "" });
      } catch (err) {
        setDemoRows([]);
        setDemoRange({ start: "", end: "" });
      } finally {
        setLoading(false);
      }
    };
    loadDemographics();
  }, [accountTag, authHeaders]);

  useEffect(() => {
    if (!accountTag) return;
    const loadVideos = async () => {
      try {
        const resp = await fetch(
          `${API_BASE}/api/audience/retention?accountTag=${encodeURIComponent(accountTag)}`,
          { headers: authHeaders }
        );
        const data = await resp.json();
        const list = data?.videos || [];
        setVideos(list);
        if (list.length > 0) {
          setVideoId((prev) => (list.find((v) => v.video_id === prev) ? prev : list[0].video_id));
        } else {
          setVideoId("");
        }
      } catch (err) {
        setVideos([]);
        setVideoId("");
      }
    };
    loadVideos();
  }, [accountTag, authHeaders]);

  useEffect(() => {
    if (!accountTag || !videoId) {
      setRetentionRows([]);
      return;
    }
    const loadRetention = async () => {
      setLoading(true);
      try {
        const resp = await fetch(
          `${API_BASE}/api/audience/retention?accountTag=${encodeURIComponent(
            accountTag
          )}&videoId=${encodeURIComponent(videoId)}`,
          { headers: authHeaders }
        );
        const data = await resp.json();
        setRetentionRows(data?.rows || []);
        setRetentionRange({ start: data?.start_date || "", end: data?.end_date || "" });
      } catch (err) {
        setRetentionRows([]);
        setRetentionRange({ start: "", end: "" });
      } finally {
        setLoading(false);
      }
    };
    loadRetention();
  }, [accountTag, videoId, authHeaders]);

  const demoTable = useMemo(() => {
    const map = {};
    demoRows.forEach((row) => {
      const age = row.age_group || "unknown";
      const gender = row.gender || "unknown";
      if (!map[age]) map[age] = {};
      map[age][gender] = row.viewer_percentage;
    });
    return Object.keys(map)
      .sort()
      .map((age) => ({
        age,
        ...map[age],
      }));
  }, [demoRows]);

  const formatAgeLabel = (value) => {
    if (!value) return "";
    const trimmed = String(value).trim();
    if (/^age\d/i.test(trimmed)) {
      return trimmed.replace(/^age/i, "");
    }
    return trimmed;
  };

  const retentionSeries = useMemo(() => {
    const ordered = [...retentionRows]
      .filter((row) => row.elapsed_video_time_ratio !== null)
      .sort((a, b) => a.elapsed_video_time_ratio - b.elapsed_video_time_ratio);
    const unique = [];
    const seen = new Set();
    for (const row of ordered) {
      const key = `${row.elapsed_video_time_ratio}`;
      if (seen.has(key)) continue;
      seen.add(key);
      unique.push(row);
    }

    const watch = {
      id: "Audience Watch Ratio",
      data: unique.map((row) => ({
        x: row.elapsed_video_time_ratio,
        y: row.audience_watch_ratio,
      })),
    };
    const relative = {
      id: "Relative Retention",
      data: unique
        .filter((row) => row.relative_retention_performance !== null)
        .map((row) => ({
          x: row.elapsed_video_time_ratio,
          y: row.relative_retention_performance,
        })),
    };
    return relative.data.length > 0 ? [watch, relative] : [watch];
  }, [retentionRows]);

  const legendItems = useMemo(() => {
    const seriesIds = new Set(retentionSeries.map((serie) => serie.id));
    const items = [
      { id: "Audience Watch Ratio", color: "#22d3ee" },
      { id: "Relative Retention", color: "#f97316" },
    ];
    return items.filter((item) => seriesIds.has(item.id));
  }, [retentionSeries]);

  return (
    <Box display="flex" flexDirection="column" gap={3}>
      <Box
        display="flex"
        gap={2}
        flexWrap="wrap"
        sx={{
          animation: "audienceFade 420ms ease-out",
          "@keyframes audienceFade": {
            from: { opacity: 0, transform: "translateY(8px)" },
            to: { opacity: 1, transform: "translateY(0)" },
          },
        }}
      >
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel>Channel</InputLabel>
          <Select
            label="Channel"
            value={accountTag}
            onChange={(event) => setAccountTag(event.target.value)}
          >
            {accounts.map((acct) => (
              <MenuItem key={acct} value={acct}>
                {acct}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl size="small" sx={{ minWidth: 260 }}>
          <InputLabel>Video</InputLabel>
          <Select
            label="Video"
            value={videoId}
            onChange={(event) => setVideoId(event.target.value)}
            disabled={!videos.length}
          >
            {videos.map((v) => (
              <MenuItem key={v.video_id} value={v.video_id}>
                {v.title ? `${v.title} (${v.video_id})` : v.video_id}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {loading && (
        <Box display="flex" alignItems="center" gap={1}>
          <CircularProgress size={18} />
          <Typography variant="body2" color="text.secondary">
            Loading analytics...
          </Typography>
        </Box>
      )}

      <Box
        sx={{
          p: 2,
          borderRadius: 3,
          border: `1px solid ${isDark ? "rgba(148,163,184,0.2)" : "rgba(15,23,42,0.12)"}`,
          background: isDark
            ? "linear-gradient(140deg, rgba(15,23,42,0.95) 0%, rgba(30,41,59,0.9) 55%, rgba(13,148,136,0.45) 100%)"
            : "linear-gradient(140deg, rgba(248,250,252,0.95) 0%, rgba(226,232,240,0.92) 55%, rgba(186,230,253,0.75) 100%)",
          transition: "transform 180ms ease, box-shadow 180ms ease",
          boxShadow: isDark ? "0 18px 35px rgba(15,23,42,0.4)" : "0 18px 30px rgba(148,163,184,0.35)",
          position: "relative",
          overflow: "hidden",
          "&:hover": {
            transform: "translateY(-2px)",
            boxShadow: isDark ? "0 20px 40px rgba(15,23,42,0.5)" : "0 20px 34px rgba(148,163,184,0.45)",
          },
          "&:before": {
            content: '""',
            position: "absolute",
            inset: 0,
            background: isDark
              ? "radial-gradient(600px 200px at 10% 0%, rgba(56,189,248,0.2), transparent 60%), radial-gradient(400px 200px at 80% 0%, rgba(16,185,129,0.18), transparent 60%)"
              : "radial-gradient(600px 200px at 10% 0%, rgba(14,165,233,0.2), transparent 60%), radial-gradient(400px 200px at 80% 0%, rgba(251,191,36,0.22), transparent 60%)",
            opacity: 0.75,
            pointerEvents: "none",
          },
        }}
      >
        <Stack direction="row" justifyContent="space-between" alignItems="baseline">
          <Box>
            <Typography variant="h6">Demographics</Typography>
            <Typography variant="caption" color="text.secondary">
              {demoRange.start && demoRange.end
                ? `Viewer distribution · ${demoRange.start} → ${demoRange.end}`
                : "No data"}
            </Typography>
          </Box>
          <Typography variant="caption" color="text.secondary">
            % of total viewers
          </Typography>
        </Stack>

        {demoTable.length === 0 ? (
          <Typography variant="body2" color="text.secondary" mt={2}>
            No demographics data available.
          </Typography>
        ) : (
          <Box mt={2}>
            <Box
              display="grid"
              gridTemplateColumns="repeat(4, minmax(0, 1fr))"
              gap={1}
              sx={{
                p: 1,
                borderRadius: 1.5,
                bgcolor: isDark ? "rgba(15,23,42,0.45)" : "rgba(255,255,255,0.9)",
                boxShadow: isDark
                  ? "0 0 0 1px rgba(56,189,248,0.2)"
                  : "0 0 0 1px rgba(14,165,233,0.2)",
              }}
            >
              <Typography variant="subtitle2">Age Group</Typography>
              <Typography variant="subtitle2">Male</Typography>
              <Typography variant="subtitle2">Female</Typography>
              <Typography variant="subtitle2">Unspecified</Typography>
              {demoTable.map((row) => (
                <Box
                  key={row.age}
                  display="contents"
                >
                  <Typography variant="body2">
                    {formatAgeLabel(row.age)}
                  </Typography>
                  <Typography variant="body2">{(row.male ?? 0).toFixed(2)}%</Typography>
                  <Typography variant="body2">{(row.female ?? 0).toFixed(2)}%</Typography>
                  <Typography variant="body2">
                    {(row.genderUnspecified ?? 0).toFixed(2)}%
                  </Typography>
                </Box>
              ))}
            </Box>
          </Box>
        )}
      </Box>

      <Box
        sx={{
          p: 2,
          borderRadius: 3,
          border: `1px solid ${isDark ? "rgba(148,163,184,0.2)" : "rgba(15,23,42,0.12)"}`,
          background: isDark
            ? "linear-gradient(140deg, rgba(15,23,42,0.95) 0%, rgba(30,41,59,0.9) 55%, rgba(13,148,136,0.45) 100%)"
            : "linear-gradient(140deg, rgba(248,250,252,0.95) 0%, rgba(226,232,240,0.92) 55%, rgba(186,230,253,0.75) 100%)",
          height: 520,
          transition: "transform 180ms ease, box-shadow 180ms ease",
          boxShadow: isDark ? "0 18px 35px rgba(15,23,42,0.4)" : "0 18px 30px rgba(148,163,184,0.35)",
          position: "relative",
          overflow: "hidden",
          "&:hover": {
            transform: "translateY(-2px)",
            boxShadow: isDark ? "0 20px 40px rgba(15,23,42,0.5)" : "0 20px 34px rgba(148,163,184,0.45)",
          },
          "&:before": {
            content: '""',
            position: "absolute",
            inset: 0,
            background: isDark
              ? "radial-gradient(600px 200px at 10% 0%, rgba(56,189,248,0.2), transparent 60%), radial-gradient(400px 200px at 80% 0%, rgba(16,185,129,0.18), transparent 60%)"
              : "radial-gradient(600px 200px at 10% 0%, rgba(14,165,233,0.2), transparent 60%), radial-gradient(400px 200px at 80% 0%, rgba(251,191,36,0.22), transparent 60%)",
            opacity: 0.75,
            pointerEvents: "none",
          },
        }}
      >
        <Stack direction="row" justifyContent="space-between" alignItems="baseline">
          <Box>
            <Typography variant="h6">Retention Curve</Typography>
            <Typography variant="caption" color="text.secondary">
              {retentionRange.start && retentionRange.end
                ? `Video-level retention · ${retentionRange.start} → ${retentionRange.end}`
                : "No data"}
            </Typography>
          </Box>
          <Typography variant="caption" color="text.secondary">
            Higher is better
          </Typography>
        </Stack>
        {legendItems.length > 0 && (
          <Stack direction="row" spacing={2} mt={1} flexWrap="wrap">
            {legendItems.map((item) => (
              <Stack key={item.id} direction="row" spacing={1} alignItems="center">
                <Box
                  sx={{
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    bgcolor: item.color,
                  }}
                />
                <Typography variant="caption" color="text.secondary">
                  {item.id}
                </Typography>
              </Stack>
            ))}
          </Stack>
        )}
        <Divider sx={{ my: 1, borderColor: isDark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.08)" }} />

        {retentionSeries[0].data.length === 0 ? (
          <Typography variant="body2" color="text.secondary" mt={2}>
            No retention data available.
          </Typography>
        ) : (
          <Box sx={{ height: 380 }}>
            <ResponsiveLine
            data={retentionSeries}
            margin={{ top: 40, right: 20, bottom: 70, left: 70 }}
            xScale={{ type: "linear", min: 0, max: 1 }}
            yScale={{ type: "linear", min: 0, max: "auto" }}
            curve="monotoneX"
            axisBottom={{
              legend: "Video progress (0% → 100%)",
              legendOffset: 44,
              legendPosition: "middle",
              format: (value) => `${Math.round(value * 100)}%`,
              tickValues: [0, 0.25, 0.5, 0.75, 1],
              tickSize: 10,
              tickPadding: 10,
              tickRotation: 0,
            }}
            axisLeft={{
              legend: "Audience retention (%)",
              legendOffset: -58,
              legendPosition: "middle",
              format: (value) => `${Math.round(value * 100)}%`,
              tickValues: 6,
              tickSize: 8,
              tickPadding: 8,
            }}
            colors={["#22d3ee", "#f97316"]}
            enableArea
            areaOpacity={0.18}
            lineWidth={3}
            enablePoints={false}
            useMesh
            enableSlices="x"
            enableGridX
            gridXValues={[0, 0.25, 0.5, 0.75, 1]}
            defs={[
              {
                id: "retentionGradient",
                type: "linearGradient",
                colors: [
                  { offset: 0, color: "#22d3ee", opacity: 0.35 },
                  { offset: 100, color: "#22d3ee", opacity: 0 },
                ],
              },
              {
                id: "relativeGradient",
                type: "linearGradient",
                colors: [
                  { offset: 0, color: "#f97316", opacity: 0.3 },
                  { offset: 100, color: "#f97316", opacity: 0 },
                ],
              },
            ]}
            fill={[
              { match: { id: "Audience Watch Ratio" }, id: "retentionGradient" },
              { match: { id: "Relative Retention" }, id: "relativeGradient" },
            ]}
            sliceTooltip={({ slice }) => (
              <Box
                sx={{
                  px: 1.4,
                  py: 0.8,
                  borderRadius: 1.5,
                  minWidth: 180,
                  bgcolor: isDark ? "rgba(15, 23, 42, 0.95)" : "rgba(255,255,255,0.98)",
                  border: `1px solid ${isDark ? "rgba(148, 163, 184, 0.25)" : "rgba(15,23,42,0.15)"}`,
                  color: isDark ? "#e5e7eb" : "#111827",
                  boxShadow: isDark
                    ? "0 12px 26px rgba(0,0,0,0.45)"
                    : "0 12px 26px rgba(15,23,42,0.18)",
                  backdropFilter: "blur(6px)",
                }}
              >
                <Typography variant="caption" sx={{ fontWeight: 600, letterSpacing: 0.3 }}>
                  {`${Math.round(slice.points[0].data.x * 100)}% video`}
                </Typography>
                {slice.points.map((point) => (
                  <Box
                    key={point.id}
                    display="flex"
                    alignItems="center"
                    justifyContent="space-between"
                    gap={2}
                  >
                    <Box display="flex" alignItems="center" gap={1}>
                      <Box
                        sx={{
                          width: 8,
                          height: 8,
                          borderRadius: "50%",
                          bgcolor: point.color,
                        }}
                      />
                      <Typography variant="caption">{point.serieId}</Typography>
                    </Box>
                    <Typography variant="caption" sx={{ fontWeight: 700, color: point.color }}>
                      {`${Math.round(point.data.y * 100)}%`}
                    </Typography>
                  </Box>
                ))}
              </Box>
            )}
            theme={{
              textColor: isDark ? "#e5e7eb" : "#111827",
              axis: {
                domain: {
                  line: { stroke: isDark ? "#e2e8f0" : "#334155", strokeWidth: 2 },
                },
                ticks: {
                  line: { stroke: isDark ? "#e2e8f0" : "#334155", strokeWidth: 1 },
                  text: { fill: isDark ? "#e5e7eb" : "#111827" },
                },
                legend: { text: { fill: isDark ? "#e5e7eb" : "#111827" } },
              },
              grid: {
                line: { stroke: isDark ? "#1f2937" : "#e2e8f0" },
              },
              legends: {
                text: { fill: isDark ? "#e5e7eb" : "#111827" },
              },
              tooltip: {
                container: {
                  background: isDark ? "#111827" : "#ffffff",
                  color: isDark ? "#e5e7eb" : "#111827",
                },
              },
            }}
            />
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default AudienceAnalytics;
