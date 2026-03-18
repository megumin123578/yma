import { useEffect, useMemo, useState, useRef } from "react";
import {
  Avatar,
  Box,
  CircularProgress,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Skeleton,
  Stack,
  Typography,
  useTheme,
  useMediaQuery,
} from "@mui/material";
import { ResponsiveLine } from "@nivo/line";
import api from "../services/api";
import { getChannelAvatarMap, getChannelRevenueMap } from "./Module";
import ChannelSwitcher, { CHANNEL_SWITCHER_SX } from "./ChannelSwitcher";

const formatRangeLabel = (range) => {
  if (!range?.start || !range?.end) return "No data";
  if (range.start === "2005-02-14") return "Lifetime";
  return `${range.start} -> ${range.end}`;
};



const AudienceAnalytics = () => {
  const theme = useTheme();
  const chartRef = useRef(null);
  const isDark = theme.palette.mode === "dark";
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const [accountTag, setAccountTag] = useState("");
  const [accounts, setAccounts] = useState([]);
  const [channelAvatarMap, setChannelAvatarMap] = useState({});
  const [channelRevenueMap, setChannelRevenueMap] = useState({});
  const [demoRows, setDemoRows] = useState([]);
  const [demoRange, setDemoRange] = useState({ start: "", end: "" });
  const [deviceRows, setDeviceRows] = useState([]);
  const [deviceRange, setDeviceRange] = useState({ start: "", end: "" });
  const [viewerTypeRows, setViewerTypeRows] = useState([]);
  const [viewerTypeRange, setViewerTypeRange] = useState({ start: "", end: "" });
  const [retentionRows, setRetentionRows] = useState([]);
  const [, setRetentionRange] = useState({ start: "", end: "" });
  const [videos, setVideos] = useState([]);
  const [videoId, setVideoId] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const loadAccounts = async () => {
      try {
        const resp = await api.get("/api/audience/demographics");
        const data = resp.data;
        const nextAccounts = (data?.availableAccounts || [])
          .map((item) => {
            if (typeof item === "string") return { value: item, label: item };
            const value = item?.value || item?.name || "";
            return {
              value,
              label: item?.label || item?.name || value,
            };
          })
          .filter((item) => item.value);
        const order = (() => {
          try {
            return JSON.parse(localStorage.getItem("tokens.order") || "[]");
          } catch {
            return [];
          }
        })()
          .map((name) => (name || "").replace(/\.pickle$/i, ""))
          .filter(Boolean);
        const orderKey = (value) => String(value || "").toLowerCase();
        const byName = new Map(nextAccounts.map((acct) => [orderKey(acct.value), acct]));
        const ordered = order
          .map((name) => byName.get(orderKey(name)))
          .filter(Boolean);
        const orderKeys = new Set(order.map(orderKey));
        const remaining = nextAccounts.filter(
          (acct) => !orderKeys.has(orderKey(acct.value))
        );
        const finalAccounts = [...ordered, ...remaining];
        setAccounts(finalAccounts);
        setAccountTag((current) => {
          if (!finalAccounts.length) return "";
          if (!current || !finalAccounts.some((item) => item.value === current)) {
            const next = ordered.length ? ordered[0] : finalAccounts[0];
            return next?.value || "";
          }
          return current;
        });
      } catch (err) {
        setAccounts([]);
      }
    };
    loadAccounts();
  }, []);

  useEffect(() => {
    let active = true;
    getChannelAvatarMap().then((map) => {
      if (active) setChannelAvatarMap(map || {});
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    getChannelRevenueMap().then((map) => {
      if (active) setChannelRevenueMap(map || {});
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!accountTag) return;
    const loadDemographics = async () => {
      setLoading(true);
      try {
        const resp = await api.get(
          `/api/audience/demographics?accountTag=${encodeURIComponent(accountTag)}`
        );
        const data = resp.data;
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
  }, [accountTag]);

  useEffect(() => {
    if (!accountTag) return;
    const loadDevices = async () => {
      setLoading(true);
      try {
        const resp = await api.get(
          `/api/audience/devices?accountTag=${encodeURIComponent(accountTag)}`
        );
        const data = resp.data;
        setDeviceRows(data?.rows || []);
        setDeviceRange({ start: data?.start_date || "", end: data?.end_date || "" });
      } catch (err) {
        setDeviceRows([]);
        setDeviceRange({ start: "", end: "" });
      } finally {
        setLoading(false);
      }
    };
    loadDevices();
  }, [accountTag]);

  useEffect(() => {
    if (!accountTag) return;
    const loadViewerTypes = async () => {
      setLoading(true);
      try {
        const resp = await api.get(
          `/api/audience/viewer_types?accountTag=${encodeURIComponent(accountTag)}`
        );
        const data = resp.data;
        setViewerTypeRows(data?.rows || []);
        setViewerTypeRange({ start: data?.start_date || "", end: data?.end_date || "" });
      } catch (err) {
        setViewerTypeRows([]);
        setViewerTypeRange({ start: "", end: "" });
      } finally {
        setLoading(false);
      }
    };
    loadViewerTypes();
  }, [accountTag]);

  useEffect(() => {
    if (!accountTag) return;
    const loadVideos = async () => {
      try {
        const resp = await api.get(
          `/api/audience/retention?accountTag=${encodeURIComponent(accountTag)}`
        );
        const data = resp.data;
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
  }, [accountTag]);

  useEffect(() => {
    if (!accountTag || !videoId) {
      setRetentionRows([]);
      return;
    }
    const loadRetention = async () => {
      setLoading(true);
      try {
        const resp = await api.get(
          `/api/audience/retention?accountTag=${encodeURIComponent(
            accountTag
          )}&videoId=${encodeURIComponent(videoId)}`
        );
        const data = resp.data;
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
  }, [accountTag, videoId]);

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

  const formatViewerType = (value) => {
    const raw = String(value || "").toUpperCase();
    if (raw === "SUBSCRIBED") return "Subscribed";
    if (raw === "UNSUBSCRIBED") return "Not subscribed";
    return value || "";
  };

  const deviceList = useMemo(() => {
    return [...deviceRows].sort(
      (a, b) => (b.viewer_percentage || 0) - (a.viewer_percentage || 0)
    );
  }, [deviceRows]);

  const viewerTypeList = useMemo(() => {
    return [...viewerTypeRows].sort(
      (a, b) => (b.viewer_percentage || 0) - (a.viewer_percentage || 0)
    );
  }, [viewerTypeRows]);

  const deviceMax = useMemo(
    () => Math.max(1, ...deviceList.map((row) => Number(row.viewer_percentage || 0))),
    [deviceList]
  );
  const viewerTypeMax = useMemo(
    () => Math.max(1, ...viewerTypeList.map((row) => Number(row.viewer_percentage || 0))),
    [viewerTypeList]
  );


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

  const showDemoSkeleton = loading && demoRows.length === 0;
  const showDeviceSkeleton = loading && deviceRows.length === 0;
  const showViewerSkeleton = loading && viewerTypeRows.length === 0;
  const showRetentionSkeleton =
    loading && retentionSeries[0].data.length === 0;
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
        <ChannelSwitcher
          options={accounts}
          value={accountTag}
          onChange={(option) => setAccountTag(option?.value || "")}
          sx={CHANNEL_SWITCHER_SX}
          recentStorageKey="audienceAnalytics.recentChannels"
          getOptionAvatar={(option) => channelAvatarMap[option?.value] || ""}
          getOptionMeta={(option) => channelRevenueMap[option?.value] || ""}
        />

        <FormControl size="small" sx={{ minWidth: { xs: "100%", sm: 260 }, flex: 1 }}>
          <InputLabel>Video</InputLabel>
          <Select
            label="Video"
            value={videoId}
            onChange={(event) => setVideoId(event.target.value)}
            disabled={!videos.length}
            renderValue={(value) => {
              const selected = videos.find((v) => v.video_id === value);
              if (!selected) return "";
              return (
                <Stack direction="row" spacing={1} alignItems="center">
                  <Avatar
                    src={selected.thumbnail || ""}
                    alt={selected.title || selected.video_id}
                    variant="rounded"
                    sx={{ width: 28, height: 20 }}
                  />
                  <Typography variant="body2" noWrap>
                    {selected.title
                      ? `${selected.title} (${selected.video_id})`
                      : selected.video_id}
                  </Typography>
                </Stack>
              );
            }}
          >
            {videos.map((v) => (
              <MenuItem key={v.video_id} value={v.video_id}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Avatar
                    src={v.thumbnail || ""}
                    alt={v.title || v.video_id}
                    variant="rounded"
                    sx={{ width: 40, height: 24 }}
                  />
                  <Typography variant="body2" noWrap>
                    {v.title ? `${v.title} (${v.video_id})` : v.video_id}
                  </Typography>
                </Stack>
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
        <Stack
          direction={{ xs: "column", sm: "row" }}
          justifyContent="space-between"
          alignItems={{ xs: "flex-start", sm: "baseline" }}
          spacing={{ xs: 0.75, sm: 2 }}
        >
          <Box>
            <Typography variant="h6">Demographics</Typography>
            <Typography variant="caption" color="text.secondary">
              {formatRangeLabel(demoRange) === "No data"
                ? "No data"
                : `Viewer distribution at ${formatRangeLabel(demoRange)}`}
            </Typography>
          </Box>
          <Typography variant="caption" color="text.secondary">
            % of total viewers
          </Typography>
        </Stack>

        {showDemoSkeleton ? (
          <Box mt={2}>
            <Box
              display="grid"
              gridTemplateColumns={{ xs: "1fr", sm: "repeat(4, minmax(0, 1fr))" }}
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
              {Array.from({ length: 16 }).map((_, idx) => (
                <Skeleton
                  key={`demo-skel-${idx}`}
                  height={18}
                  animation="wave"
                  sx={{ borderRadius: 1 }}
                />
              ))}
            </Box>
          </Box>
        ) : demoTable.length === 0 ? (
          <Typography variant="body2" color="text.secondary" mt={2}>
            No demographics data available.
          </Typography>
        ) : isMobile ? (
          <Stack spacing={1.25} mt={2}>
            {demoTable.map((row) => (
              <Box
                key={row.age}
                sx={{
                  p: 1.25,
                  borderRadius: 1.5,
                  bgcolor: isDark ? "rgba(15,23,42,0.45)" : "rgba(255,255,255,0.9)",
                  boxShadow: isDark
                    ? "0 0 0 1px rgba(56,189,248,0.2)"
                    : "0 0 0 1px rgba(14,165,233,0.2)",
                }}
              >
                <Typography variant="subtitle2" sx={{ mb: 0.75 }}>
                  {formatAgeLabel(row.age)}
                </Typography>
                <Stack spacing={0.5}>
                  <Box display="flex" justifyContent="space-between" gap={2}>
                    <Typography variant="body2" color="text.secondary">Male</Typography>
                    <Typography variant="body2">{(row.male ?? 0).toFixed(2)}%</Typography>
                  </Box>
                  <Box display="flex" justifyContent="space-between" gap={2}>
                    <Typography variant="body2" color="text.secondary">Female</Typography>
                    <Typography variant="body2">{(row.female ?? 0).toFixed(2)}%</Typography>
                  </Box>
                  <Box display="flex" justifyContent="space-between" gap={2}>
                    <Typography variant="body2" color="text.secondary">Unspecified</Typography>
                    <Typography variant="body2">
                      {(
                        row.genderUnspecified ??
                        row.genderUserSpecified ??
                        row.unknown ??
                        0
                      ).toFixed(2)}%
                    </Typography>
                  </Box>
                </Stack>
              </Box>
            ))}
          </Stack>
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
                <Box key={row.age} display="contents">
                  <Typography variant="body2">
                    {formatAgeLabel(row.age)}
                  </Typography>
                  <Typography variant="body2">{(row.male ?? 0).toFixed(2)}%</Typography>
                  <Typography variant="body2">{(row.female ?? 0).toFixed(2)}%</Typography>
                  <Typography variant="body2">
                    {(
                      row.genderUnspecified ??
                      row.genderUserSpecified ??
                      row.unknown ??
                      0
                    ).toFixed(2)}%
                  </Typography>
                </Box>
              ))}
            </Box>
          </Box>
        )}
      </Box>

      <Box
        display="grid"
        gridTemplateColumns={{ xs: "1fr", md: "repeat(2, minmax(0, 1fr))" }}
        gap={2}
      >
        <Box
          sx={{
            p: 2,
            borderRadius: 3,
            border: `1px solid ${isDark ? "rgba(148,163,184,0.2)" : "rgba(15,23,42,0.12)"}`,
            background: isDark
              ? "rgba(15,23,42,0.85)"
              : "rgba(248,250,252,0.95)",
            boxShadow: isDark
              ? "0 14px 26px rgba(15,23,42,0.35)"
              : "0 12px 22px rgba(148,163,184,0.25)",
          }}
        >
          <Stack
            direction={{ xs: "column", sm: "row" }}
            justifyContent="space-between"
            alignItems={{ xs: "flex-start", sm: "baseline" }}
            spacing={{ xs: 0.75, sm: 2 }}
          >
            <Box>
              <Typography variant="subtitle1" fontWeight={600}>
                Devices
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {formatRangeLabel(deviceRange)}
              </Typography>
            </Box>
            <Typography variant="caption" color="text.secondary">
              % viewers
            </Typography>
          </Stack>
          {showDeviceSkeleton ? (
            <Stack spacing={1.2} mt={2}>
              {Array.from({ length: 5 }).map((_, idx) => (
                <Box key={`device-skel-${idx}`}>
                  <Box display="flex" justifyContent="space-between" mb={0.6}>
                    <Skeleton width={120} height={18} />
                    <Skeleton width={48} height={18} />
                  </Box>
                  <Skeleton height={10} sx={{ borderRadius: 999 }} />
                </Box>
              ))}
            </Stack>
          ) : deviceList.length === 0 ? (
            <Typography variant="body2" color="text.secondary" mt={2}>
              No device data available.
            </Typography>
          ) : (
            <Stack spacing={1} mt={2}>
              {deviceList.slice(0, 5).map((row) => {
                const pct = Math.max(
                  6,
                  Math.round((row.viewer_percentage / deviceMax) * 100)
                );
                return (
                  <Box key={row.device_type}>
                    <Box display="flex" justifyContent="space-between" mb={0.5}>
                      <Typography variant="body2">{row.device_type}</Typography>
                      <Typography variant="body2" fontWeight={600}>
                        {(row.viewer_percentage || 0).toFixed(2)}%
                      </Typography>
                    </Box>
                    <Box
                      sx={{
                        height: 8,
                        borderRadius: 999,
                        bgcolor: isDark
                          ? "rgba(148,163,184,0.2)"
                          : "rgba(15,23,42,0.12)",
                        overflow: "hidden",
                      }}
                    >
                      <Box
                        sx={{
                          width: `${pct}%`,
                          height: "100%",
                          borderRadius: 999,
                          background: isDark
                            ? "linear-gradient(90deg, #38bdf8, #22d3ee)"
                            : "linear-gradient(90deg, #0ea5e9, #22d3ee)",
                        }}
                      />
                    </Box>
                  </Box>
                );
              })}
            </Stack>
          )}
        </Box>

        <Box
          sx={{
            p: 2,
            borderRadius: 3,
            border: `1px solid ${isDark ? "rgba(148,163,184,0.2)" : "rgba(15,23,42,0.12)"}`,
            background: isDark
              ? "rgba(15,23,42,0.85)"
              : "rgba(248,250,252,0.95)",
            boxShadow: isDark
              ? "0 14px 26px rgba(15,23,42,0.35)"
              : "0 12px 22px rgba(148,163,184,0.25)",
          }}
        >
          <Stack
            direction={{ xs: "column", sm: "row" }}
            justifyContent="space-between"
            alignItems={{ xs: "flex-start", sm: "baseline" }}
            spacing={{ xs: 0.75, sm: 2 }}
          >
            <Box>
              <Typography variant="subtitle1" fontWeight={600}>
                Subscribed vs Not subscribed
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {formatRangeLabel(viewerTypeRange)}
              </Typography>
            </Box>
            <Typography variant="caption" color="text.secondary">
              % viewers
            </Typography>
          </Stack>
          {showViewerSkeleton ? (
            <Stack spacing={1.2} mt={2}>
              {Array.from({ length: 3 }).map((_, idx) => (
                <Box key={`viewer-skel-${idx}`}>
                  <Box display="flex" justifyContent="space-between" mb={0.6}>
                    <Skeleton width={140} height={18} />
                    <Skeleton width={48} height={18} />
                  </Box>
                  <Skeleton height={10} sx={{ borderRadius: 999 }} />
                </Box>
              ))}
            </Stack>
          ) : viewerTypeList.length === 0 ? (
            <Typography variant="body2" color="text.secondary" mt={2}>
              No viewer type data available.
            </Typography>
          ) : (
            <Stack spacing={1} mt={2}>
              {viewerTypeList.map((row) => {
                const pct = Math.max(
                  6,
                  Math.round((row.viewer_percentage / viewerTypeMax) * 100)
                );
                return (
                  <Box key={row.viewer_type}>
                    <Box display="flex" justifyContent="space-between" mb={0.5}>
                      <Typography variant="body2">
                        {formatViewerType(row.viewer_type)}
                      </Typography>
                      <Typography variant="body2" fontWeight={600}>
                        {(row.viewer_percentage || 0).toFixed(2)}%
                      </Typography>
                    </Box>
                    <Box
                      sx={{
                        height: 8,
                        borderRadius: 999,
                        bgcolor: isDark
                          ? "rgba(148,163,184,0.2)"
                          : "rgba(15,23,42,0.12)",
                        overflow: "hidden",
                      }}
                    >
                      <Box
                        sx={{
                          width: `${pct}%`,
                          height: "100%",
                          borderRadius: 999,
                          background: isDark
                            ? "linear-gradient(90deg, #a855f7, #f472b6)"
                            : "linear-gradient(90deg, #8b5cf6, #f472b6)",
                        }}
                      />
                    </Box>
                  </Box>
                );
              })}
            </Stack>
          )}
        </Box>
      </Box>
      <Box
        sx={{
          p: 2,
          borderRadius: 3,
          border: `1px solid ${isDark ? "rgba(148,163,184,0.2)" : "rgba(15,23,42,0.12)"}`,
          background: isDark
            ? "linear-gradient(140deg, rgba(15,23,42,0.95) 0%, rgba(30,41,59,0.9) 55%, rgba(13,148,136,0.45) 100%)"
            : "linear-gradient(140deg, rgba(248,250,252,0.95) 0%, rgba(226,232,240,0.92) 55%, rgba(186,230,253,0.75) 100%)",
          height: { xs: 440, sm: 520 },
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
        <Stack
          direction={{ xs: "column", sm: "row" }}
          justifyContent="space-between"
          alignItems={{ xs: "flex-start", sm: "baseline" }}
          spacing={{ xs: 0.75, sm: 2 }}
        >
          <Box>
            <Typography variant="h6">Retention Curve</Typography>

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

        {showRetentionSkeleton ? (
          <Box mt={2}>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2} mb={1}>
              <Skeleton width={140} height={18} />
              <Skeleton width={140} height={18} />
            </Stack>
            <Skeleton height={360} sx={{ borderRadius: 2 }} />
          </Box>
        ) : retentionSeries[0].data.length === 0 ? (
          <Typography variant="body2" color="text.secondary" mt={2}>
            No retention data available.
          </Typography>
        ) : (
          <Box ref={chartRef} sx={{ height: { xs: 300, sm: 380 } }}>
            <ResponsiveLine
              data={retentionSeries}
              margin={
                isMobile
                  ? { top: 24, right: 12, bottom: 56, left: 48 }
                  : { top: 40, right: 20, bottom: 70, left: 70 }
              }
              xScale={{ type: "linear", min: 0, max: 1 }}
              yScale={{ type: "linear", min: 0, max: "auto" }}
              curve="monotoneX"
              axisBottom={{
                legend: "Video progress (0% → 100%)",
                legendOffset: isMobile ? 0 : 44,
                legendPosition: "middle",
                format: (value) => `${Math.round(value * 100)}%`,
                tickValues: [0, 0.25, 0.5, 0.75, 1],
                tickSize: isMobile ? 6 : 10,
                tickPadding: isMobile ? 6 : 10,
                tickRotation: 0,
              }}
              axisLeft={{
                legend: "Audience retention (%)",
                legendOffset: isMobile ? 0 : -58,
                legendPosition: "middle",
                format: (value) => `${Math.round(value * 100)}%`,
                tickValues: isMobile ? 4 : 6,
                tickSize: isMobile ? 6 : 8,
                tickPadding: isMobile ? 6 : 8,
              }}
              colors={["#22d3ee", "#f97316"]}
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
              sliceTooltip={({ slice }) => {
                const isRightSide =
                  chartRef.current && slice.x > chartRef.current.offsetWidth / 2;
                return (
                  <Box
                    sx={{
                      px: 1.4,
                      py: 0.8,
                      borderRadius: 1.5,
                      minWidth: isMobile ? 150 : 180,
                      maxWidth: isMobile ? 220 : 320,
                      bgcolor: isDark ? "rgba(15, 23, 42, 0.95)" : "rgba(255,255,255,0.98)",
                      border: `1px solid ${isDark ? "rgba(148, 163, 184, 0.25)" : "rgba(15,23,42,0.15)"}`,
                      color: isDark ? "#e5e7eb" : "#111827",
                      boxShadow: isDark
                        ? "0 12px 26px rgba(0,0,0,0.45)"
                        : "0 12px 26px rgba(15,23,42,0.18)",
                      backdropFilter: "blur(6px)",
                      transform: isRightSide ? "translateX(-110%)" : "translateX(10%)",
                      transition: "transform 0.15s ease-out",
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
                        gap={1}
                      >
                        <Box display="flex" alignItems="center" gap={1}>
                          <Box
                            sx={{
                              width: 8,
                              height: 8,
                              borderRadius: "50%",
                              bgcolor: point.serieId === "Relative Retention" ? "#f97316" : "#22d3ee",
                            }}
                          />
                          <Typography variant="body2" sx={{ fontSize: "0.80rem" }}>
                            {point.serieId}
                          </Typography>
                        </Box>
                        <Typography variant="body2" sx={{ fontWeight: 700 }}>
                          {`${(point.data.y * 100).toFixed(1)}%`}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                )
              }}
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
