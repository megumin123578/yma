import { useEffect, useMemo, useState } from "react";
import {
    Box,
    Grid,
    Card,
    CardMedia,
    CardContent,
    Typography,
    Stack,
    Button,
    TextField,
    MenuItem,
    CircularProgress,
    Dialog,
    DialogContent,
    IconButton,
    useTheme,
} from "@mui/material";
import { motion } from "framer-motion";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import AssessmentOutlinedIcon from "@mui/icons-material/AssessmentOutlined";
import InsightsIcon from "@mui/icons-material/Insights";
import CloseIcon from "@mui/icons-material/Close";
import { ResponsiveChoropleth } from "@nivo/geo";
import { tokens } from "../theme";
import Header from "./Header";
import api from "../services/api";
import LiveViews from "./LiveViews";
import { COUNTRY_FALLBACK } from "../data/countryMapping";
import { geoFeatures } from "../data/mockGeoFeatures";
import { getChannelAvatarMap, getChannelRevenueMap } from "./Module";
import ChannelSwitcher, { CHANNEL_SWITCHER_SX } from "./ChannelSwitcher";
import {
    getStoredSharedChannelId,
    listenSharedChannelId,
    resolvePreferredSharedChannelId,
    setStoredSharedChannelId,
} from "../utils/sharedChannel";
import { sortByStoredTokenOrder } from "../utils/tokenOrder";
import {
    ResponsiveContainer,
    BarChart,
    Bar,
    LineChart,
    Line,
    XAxis,
    YAxis,
    Tooltip,
    CartesianGrid,
} from "recharts";

const MotionCard = motion.create(Card);

// Variant cho card khi hover
const cardVariants = {
    rest: {
        y: 0,
        boxShadow: "0 4px 12px rgba(0,0,0,0.25)",
        scale: 1,
    },
    hover: {
        y: -4,
        boxShadow: "0 12px 30px rgba(0,0,0,0.35)",
        scale: 1.01,
    },
};

// Variant cho overlay khi hover
const overlayVariants = {
    rest: { opacity: 0, y: "100%", pointerEvents: "none" },
    hover: { opacity: 1, y: 0, pointerEvents: "auto" },
};

const OVERVIEW_RANGES = [
    { value: "7d", label: "Last 7 days", days: 7 },
    { value: "28d", label: "Last 28 days", days: 28 },
    { value: "90d", label: "Last 90 days", days: 90 },
];
const OVERVIEW_LIMIT_STEP = 10;
const OVERVIEW_LIMIT_MAX = 50;
const OVERVIEW_LIMIT_DEFAULT = 10;

const VideoList = () => {
    const theme = useTheme();
    const isDark = theme.palette.mode === "dark";
    const colors = tokens(theme.palette.mode);

    const [channels, setChannels] = useState([]);
    const [channelAvatarMap, setChannelAvatarMap] = useState({});
    const [channelRevenueMap, setChannelRevenueMap] = useState({});
    const [selectedChannel, setSelectedChannel] = useState(() => {
        try {
            return getStoredSharedChannelId("overview.selectedChannelId");
        } catch {
            return "";
        }
    });
    const [overviewRange, setOverviewRange] = useState(() => {
        try {
            const stored = localStorage.getItem("overview.range") || "28d";
            const exists = OVERVIEW_RANGES.some((range) => range.value === stored);
            return exists ? stored : "28d";
        } catch {
            return "28d";
        }
    });
    const [videos, setVideos] = useState([]);
    const [loadingChannels, setLoadingChannels] = useState(true);
    const [loadingVideos, setLoadingVideos] = useState(false);
    const [topKeywords, setTopKeywords] = useState([]);
    const [topSources, setTopSources] = useState([]);
    const [keywordLimit, setKeywordLimit] = useState(OVERVIEW_LIMIT_DEFAULT);
    const [sourceLimit, setSourceLimit] = useState(OVERVIEW_LIMIT_DEFAULT);
    const [countryViews, setCountryViews] = useState([]);
    const [subscribersSeries, setSubscribersSeries] = useState([]);
    const [revenueRows, setRevenueRows] = useState([]);
    const [animateOverviewBars, setAnimateOverviewBars] = useState(false);
    const [liveViewsOpen, setLiveViewsOpen] = useState(false);
    const [error, setError] = useState("");
    const activeRange =
        OVERVIEW_RANGES.find((range) => range.value === overviewRange) ||
        OVERVIEW_RANGES[1];
    const rangeDays = activeRange.days;
    const rangeLabel = activeRange.label;
    const canLoadMoreKeywords =
        topKeywords.length >= keywordLimit && keywordLimit < OVERVIEW_LIMIT_MAX;
    const canLoadMoreSources =
        topSources.length >= sourceLimit && sourceLimit < OVERVIEW_LIMIT_MAX;
    const latestVideos = useMemo(() => {
        const sorted = [...videos].sort((a, b) => {
            const aTime = a?.publish_date ? new Date(a.publish_date).getTime() : 0;
            const bTime = b?.publish_date ? new Date(b.publish_date).getTime() : 0;
            return bTime - aTime;
        });
        return sorted.slice(0, 5);
    }, [videos]);
    const subscribersSummary = useMemo(() => {
        const sorted = [...subscribersSeries].sort((a, b) => {
            const aTime = a?.day ? new Date(a.day).getTime() : 0;
            const bTime = b?.day ? new Date(b.day).getTime() : 0;
            return aTime - bTime;
        });
        const last = sorted.slice(-rangeDays);
        const prev = sorted.slice(-(rangeDays * 2), -rangeDays);
        const sum = (rows, key) =>
            rows.reduce((acc, row) => acc + Number(row?.[key] || 0), 0);
        const gained = sum(last, "subscribers_gained");
        const lost = sum(last, "subscribers_lost");
        const change = gained - lost;
        const avg = last.length ? change / last.length : 0;
        const prevGained = sum(prev, "subscribers_gained");
        const prevLost = sum(prev, "subscribers_lost");
        const prevChange = prevGained - prevLost;
        const prevAvg = prev.length ? prevChange / prev.length : 0;
        const pct = (cur, prevVal) =>
            prevVal ? ((cur - prevVal) / prevVal) * 100 : 0;

        return {
            stats: {
                gained,
                lost,
                change,
                avg,
                gainedPct: pct(gained, prevGained),
                lostPct: pct(lost, prevLost),
                changePct: pct(change, prevChange),
                avgPct: pct(avg, prevAvg),
            },
            chart: last.map((row) => ({
                day: row.day,
                gained: Number(row?.subscribers_gained || 0),
                change:
                    Number(row?.subscribers_gained || 0) -
                    Number(row?.subscribers_lost || 0),
            })),
        };
    }, [subscribersSeries, rangeDays]);
    const countryResolvers = useMemo(() => {
        const iso2ToFeatureId = new Map();
        const idToName = new Map();

        for (const f of geoFeatures.features) {
            const id = String(f.id || f.properties?.iso_a3 || "");
            const iso2 = f.properties?.iso_a2?.toUpperCase() || "";
            const name = f.properties?.name || id;

            if (iso2) iso2ToFeatureId.set(iso2, id);
            idToName.set(id, name);
        }

        return {
            resolveId: (code) => {
                const c = String(code).toUpperCase();
                return iso2ToFeatureId.get(c) || COUNTRY_FALLBACK[c] || c;
            },
            nameOf: (id) => idToName.get(id) || id,
        };
    }, []);
    const countryMapData = useMemo(() => {
        return (countryViews || []).map((row) => {
            const id = countryResolvers.resolveId(row.country);
            return {
                id,
                value: Number(row.views) || 0,
                label: countryResolvers.nameOf(id),
            };
        });
    }, [countryViews, countryResolvers]);
    const countryDomainMax = useMemo(() => {
        const vals = countryMapData.map((d) => Number(d.value) || 0);
        return Math.max(1, ...vals);
    }, [countryMapData]);
    const topCountries = useMemo(() => {
        return [...(countryMapData || [])]
            .sort((a, b) => (b.value || 0) - (a.value || 0))
            .slice(0, 5);
    }, [countryMapData]);
    const topKeywordMax = useMemo(() => {
        return Math.max(1, ...topKeywords.map((k) => Number(k.views) || 0));
    }, [topKeywords]);
    const topSourceMax = useMemo(() => {
        return Math.max(1, ...topSources.map((s) => Number(s.views) || 0));
    }, [topSources]);
    const revenueSummary = useMemo(() => {
        const sum = (rows, key) =>
            rows.reduce((acc, row) => acc + Number(row?.[key] || 0), 0);
        const avg = (rows, key) => {
            let total = 0;
            let count = 0;
            rows.forEach((row) => {
                const raw = row?.[key];
                if (raw == null || raw === "") return;
                const value = Number(raw);
                if (!Number.isNaN(value)) {
                    total += value;
                    count += 1;
                }
            });
            return count ? total / count : null;
        };
        return {
            estimated: sum(revenueRows, "estimated_revenue"),
            ad: sum(revenueRows, "ad_revenue"),
            gross: sum(revenueRows, "gross_revenue"),
            rpmAvg: avg(revenueRows, "rpm"),
        };
    }, [revenueRows]);
    const revenueChartData = useMemo(() => {
        return (revenueRows || []).map((row) => ({
            day: row.day,
            estimated: Number(row?.estimated_revenue || 0),
        }));
    }, [revenueRows]);
    const revenueXAxisTicks = useMemo(() => {
        const days = revenueChartData
            .map((row) => row.day)
            .filter(Boolean);
        if (!days.length) return [];
        if (overviewRange !== "28d") return days;

        return days.filter((day, index) => {
            if (index === 0 || index === days.length - 1) return true;
            return index % 2 === 0;
        });
    }, [overviewRange, revenueChartData]);
    const subscribersXAxisTicks = useMemo(() => {
        const days = subscribersSummary.chart
            .map((row) => row.day)
            .filter(Boolean);
        if (!days.length) return [];
        const first = days[0];
        const last = days[days.length - 1];
        if (first === last) return [first];
        return [first, last];
    }, [subscribersSummary.chart]);
    const chartTooltipStyles = useMemo(() => {
        const isDark = theme.palette.mode === "dark";
        return {
            contentStyle: {
                backgroundColor: isDark ? "rgba(15,23,42,0.92)" : "#ffffff",
                border: isDark
                    ? "1px solid rgba(148,163,184,0.35)"
                    : "1px solid rgba(15,23,42,0.12)",
                borderRadius: 8,
                boxShadow: isDark
                    ? "0 10px 18px rgba(2,6,23,0.45)"
                    : "0 10px 18px rgba(15,23,42,0.12)",
            },
            labelStyle: { color: isDark ? "#e2e8f0" : "#0f172a" },
        };
    }, [theme.palette.mode]);

    // Fetch danh sách account_tag
    useEffect(() => {
        const fetchChannels = async () => {
            try {
                setLoadingChannels(true);
                const res = await api.get("/api/video_overview/channels");
                const data = res.data;
                const items = data.items || [];
                const finalChannels = sortByStoredTokenOrder(items, (item) => item.value);
                setChannels(finalChannels);
                setSelectedChannel((current) =>
                    resolvePreferredSharedChannelId(
                        getStoredSharedChannelId("overview.selectedChannelId") || current,
                        finalChannels,
                        (item) => item.value
                    )
                );
            } catch (err) {
                console.error(err);
                setError(
                    "Không load được danh sách kênh. Hãy chạy backend: uvicorn python_backend.main:app --host 0.0.0.0 --port 8000 --reload"
                );
            } finally {
                setLoadingChannels(false);
            }
        };

        fetchChannels();
    }, [selectedChannel]);

    useEffect(() => {
        setStoredSharedChannelId(selectedChannel, "overview.selectedChannelId");
    }, [selectedChannel]);

    useEffect(() => {
        return listenSharedChannelId((nextChannelId) => {
            setSelectedChannel((current) => {
                if (!nextChannelId || nextChannelId === current) return current;
                return nextChannelId;
            });
        });
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
        getChannelRevenueMap(overviewRange).then((map) => {
            if (active) setChannelRevenueMap(map || {});
        });
        return () => {
            active = false;
        };
    }, [overviewRange]);

    useEffect(() => {
        try {
            localStorage.setItem("overview.range", overviewRange);
        } catch {
            // ignore storage errors
        }
    }, [overviewRange]);

    useEffect(() => {
        setKeywordLimit(OVERVIEW_LIMIT_DEFAULT);
        setSourceLimit(OVERVIEW_LIMIT_DEFAULT);
    }, [selectedChannel, overviewRange]);

    // Fetch video theo accountTag
    useEffect(() => {
        if (!selectedChannel) return;

        const fetchVideos = async () => {
            try {
                setLoadingVideos(true);
                setError("");
                const res = await api.get(
                    `/api/video_overview/videos?accountTag=${encodeURIComponent(
                        selectedChannel
                    )}`
                );
                const data = res.data;
                setVideos(data || []);
            } catch (err) {
                console.error(err);
                setError("Không load được danh sách video.");
            } finally {
                setLoadingVideos(false);
            }
        };

        fetchVideos();
    }, [selectedChannel]);

    useEffect(() => {
        if (!selectedChannel) return;
        const fetchOverviewExtras = async () => {
            try {
                const [
                    topKeywordsResp,
                    topSourcesResp,
                    countryResp,
                    subsResp,
                    revenueResp,
                ] = await Promise.all([
                    api.get(
                        `/api/video_overview/top_keywords?accountTag=${encodeURIComponent(
                            selectedChannel
                        )}&limit=${keywordLimit}&range=${overviewRange}`
                    ),
                    api.get(
                        `/api/video_overview/top_sources?accountTag=${encodeURIComponent(
                            selectedChannel
                        )}&limit=${sourceLimit}&range=${overviewRange}`
                    ),
                    api.get(
                        `/api/video_overview/views_by_country?accountTag=${encodeURIComponent(
                            selectedChannel
                        )}&range=${overviewRange}`
                    ),
                    api.get(
                        `/api/video_overview/subscribers_timeseries?accountTag=${encodeURIComponent(
                            selectedChannel
                        )}&days=${rangeDays}`
                    ),
                    api.get(
                        `/api/revenue?accountTag=${encodeURIComponent(
                            selectedChannel
                        )}&range=${overviewRange}`
                    ),
                ]);

                const topKeywordsData = topKeywordsResp.data;
                const topSourcesData = topSourcesResp.data;
                const countryData = countryResp.data;
                const subsData = subsResp.data;
                const revenueData = revenueResp.data;

                setAnimateOverviewBars(false);
                setTopKeywords(Array.isArray(topKeywordsData) ? topKeywordsData : []);
                setTopSources(Array.isArray(topSourcesData) ? topSourcesData : []);
                setCountryViews(Array.isArray(countryData?.rows) ? countryData.rows : []);
                setSubscribersSeries(Array.isArray(subsData) ? subsData : []);
                setRevenueRows(Array.isArray(revenueData?.rows) ? revenueData.rows : []);
                requestAnimationFrame(() => setAnimateOverviewBars(true));
            } catch (err) {
                setTopKeywords([]);
                setTopSources([]);
                setCountryViews([]);
                setSubscribersSeries([]);
                setRevenueRows([]);
                setAnimateOverviewBars(false);
            }
        };

        fetchOverviewExtras();
    }, [
        selectedChannel,
        overviewRange,
        rangeDays,
        keywordLimit,
        sourceLimit,
    ]);

    const formatNumber = (n) => {
        if (n == null) return "-";
        if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
        if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
        return n.toString();
    };
    const formatCurrency = (value) => {
        if (value == null) return "-";
        const num = Number(value);
        if (Number.isNaN(num)) return "-";
        return `$${num.toFixed(2)}`;
    };

    const formatDate = (iso) => {
        if (!iso) return "-";
        const d = new Date(iso);
        if (Number.isNaN(d.getTime())) return iso;

        const day = d.getDate().toString().padStart(2, "0");
        const month = (d.getMonth() + 1).toString().padStart(2, "0");
        const year = d.getFullYear().toString().slice(-2); // "YY"

        return `${day}/${month}/${year}`; // dd/mm/YY
    };

    const formatDateFull = (iso) => {
        if (!iso) return "-";
        const d = new Date(iso);
        if (Number.isNaN(d.getTime())) return iso;

        const day = d.getDate().toString().padStart(2, "0");
        const month = (d.getMonth() + 1).toString().padStart(2, "0");
        const year = d.getFullYear().toString(); // YYYY

        return `${day}-${month}-${year}`; // dd-mm-yyyy
    };
    const formatDateMonth = (iso) => {
        if (!iso) return "-";
        const d = new Date(iso);
        if (Number.isNaN(d.getTime())) return iso;

        const day = d.getDate().toString().padStart(2, "0");
        const month = (d.getMonth() + 1).toString().padStart(2, "0");

        return `${day}/${month}`; // dd/mm
    };

    const sectionSx = {
        borderRadius: 3,
        border: "1px solid",
        borderColor:
            theme.palette.mode === "dark"
                ? "rgba(148,163,184,0.2)"
                : "rgba(15,23,42,0.12)",
        background:
            theme.palette.mode === "dark"
                ? "rgba(10,15,24,0.8)"
                : "rgba(255,255,255,0.94)",
        boxShadow:
            theme.palette.mode === "dark"
                ? "0 14px 28px rgba(15,23,42,0.4)"
                : "0 14px 26px rgba(148,163,184,0.25)",
        p: 2,
    };
    const statCardSx = {
        borderRadius: 2,
        p: 2,
        textAlign: "center",
        border: "1px solid",
        borderColor:
            theme.palette.mode === "dark"
                ? "rgba(148,163,184,0.2)"
                : "rgba(15,23,42,0.12)",
        background:
            theme.palette.mode === "dark"
                ? "rgba(15,23,42,0.7)"
                : "rgba(248,250,252,0.9)",
        boxShadow:
            theme.palette.mode === "dark"
                ? "0 12px 22px rgba(2,6,23,0.55)"
                : "0 10px 20px rgba(148,163,184,0.25)",
    };
    const chartCardSx = {
        borderRadius: 2,
        p: 0.5,
        border: "1px solid",
        borderColor:
            theme.palette.mode === "dark"
                ? "rgba(148,163,184,0.2)"
                : "rgba(15,23,42,0.12)",
        background:
            theme.palette.mode === "dark"
                ? "rgba(15,23,42,0.6)"
                : "rgba(248,250,252,0.9)",
    };
    const pctColor = (value) =>
        value >= 0 ? "rgb(34,197,94)" : "rgb(239,68,68)";
    const formatPct = (value) => `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;

    const latestRowSx = {
        display: "grid",
        gridTemplateColumns: {
            xs: "1fr",
            sm: "repeat(2, 1fr)",
            md: "repeat(3, 1fr)",
            lg: "repeat(5, 1fr)"
        },
        gap: 3,
        width: "100%",
    };

    const renderVideoCard = (v, idx) => {
        const engagementRate = (((Number(v.likes) + Number(v.comments)) / (Number(v.views) || 1)) * 100).toFixed(1);

        return (
            <Box key={v.video_id || idx} sx={{ width: "100%" }}>
                <MotionCard
                    variants={cardVariants}
                    initial="rest"
                    whileHover="hover"
                    transition={{ duration: 0.3, delay: idx * 0.05 }}
                    onClick={() =>
                        window.open(`https://www.youtube.com/watch?v=${v.video_id}`, "_blank")
                    }
                    sx={{
                        position: "relative",
                        borderRadius: 4,
                        border: "1px solid",
                        borderColor: isDark ? "rgba(255,255,255,0.1)" : "rgba(15,23,42,0.1)",
                        background: isDark ? "rgba(30,41,59,0.4)" : "#fff",
                        overflow: "hidden",
                        cursor: "pointer",
                        display: "flex",
                        flexDirection: "column",
                        height: "100%",
                        boxShadow: isDark ? "0 10px 30px rgba(0,0,0,0.3)" : "0 8px 24px rgba(148,163,184,0.1)",
                    }}
                >
                    <Box sx={{ position: "relative", overflow: 'hidden' }}>
                        {v.thumbnail && (
                            <CardMedia
                                component="img"
                                image={v.thumbnail}
                                alt={v.title}
                                sx={{
                                    width: "100%",
                                    aspectRatio: "16/9",
                                    objectFit: "cover",
                                    transition: "transform 0.5s ease",
                                    ".MuiCard-root:hover &": { transform: "scale(1.08)" }
                                }}
                            />
                        )}
                        <Box sx={{
                            position: "absolute", top: 10, right: 10, bgcolor: "rgba(15,23,42,0.8)",
                            color: "#fff", px: 1.2, py: 0.5, borderRadius: 1.5, fontSize: "0.65rem",
                            fontWeight: 800, backdropFilter: "blur(4px)", border: '1px solid rgba(255,255,255,0.1)', zIndex: 2
                        }}>
                            {formatDate(v.publish_date)}
                        </Box>
                        <Box className="play-overlay" sx={{
                            position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
                            bgcolor: "rgba(0,0,0,0.3)", opacity: 0, transition: "opacity 0.3s ease", zIndex: 1,
                            ".MuiCard-root:hover &": { opacity: 1 }
                        }}>
                            <Box sx={{
                                width: 50, height: 50, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.2)',
                                display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(8px)',
                                border: '1px solid rgba(255,255,255,0.3)'
                            }}>
                                <PlayArrowRoundedIcon sx={{ fontSize: 32, color: "#fff" }} />
                            </Box>
                        </Box>
                    </Box>

                    <CardContent sx={{ p: 2, flex: 1, display: "flex", flexDirection: "column" }}>
                        <Typography variant="body1" color="text.primary" fontWeight={700} sx={{
                            display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
                            overflow: "hidden", lineHeight: 1.3, mb: 2, minHeight: "2.6em", fontSize: "0.92rem"
                        }}>
                            {v.title}
                        </Typography>

                        <Stack direction="row" spacing={1} justifyContent="space-between" mt="auto">
                            <Box>
                                <Typography variant="caption" color="text.secondary" display="block" sx={{ fontSize: '0.7rem' }}>Views</Typography>
                                <Typography variant="body2" fontWeight={700} display="flex" alignItems="center" gap={0.5}>
                                    {formatNumber(v.views)}
                                    <TrendingUpIcon sx={{ fontSize: 14, color: "#22c55e" }} />
                                </Typography>
                            </Box>
                            <Box>
                                <Typography variant="caption" color="text.secondary" display="block" sx={{ fontSize: '0.7rem' }}>Likes</Typography>
                                <Typography variant="body2" fontWeight={700}>
                                    {formatNumber(v.likes)}
                                </Typography>
                            </Box>
                            <Box>
                                <Typography variant="caption" color="text.secondary" display="block" sx={{ fontSize: '0.7rem' }}>Eng.</Typography>
                                <Typography variant="body2" fontWeight={700} color="primary.main">
                                    {engagementRate}%
                                </Typography>
                            </Box>
                        </Stack>
                    </CardContent>

                    <Box
                        component={motion.div}
                        variants={overlayVariants}
                        transition={{ type: "spring", damping: 25, stiffness: 120 }}
                        sx={{
                            position: "absolute", inset: 0, background: isDark ? "rgba(15,23,42,0.92)" : "rgba(255,255,255,0.95)",
                            backdropFilter: "blur(12px)", p: 2.5, display: "flex", flexDirection: "column", zIndex: 3,
                        }}
                    >
                        <Typography variant="subtitle2" fontWeight={800} mb={2} color="primary" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <AssessmentOutlinedIcon fontSize="small" />
                            Performance Details
                        </Typography>
                        <Grid container spacing={1.5}>
                            {[
                                { label: "Engaged views", val: formatNumber(v.engaged_views) },
                                { label: "Shares", val: formatNumber(v.shares) },
                                { label: "Sub. Gained", val: formatNumber(v.subscribers_gained) },
                                { label: "Sub. Lost", val: formatNumber(v.subscribers_lost) },
                                { label: "Avg Duration", val: `${v.average_view_duration_seconds}s` },
                                { label: "CTR", val: `${v.annotation_click_through_rate || 0}%` },
                            ].map((item) => (
                                <Grid size={{ xs: 6 }} key={item.label}>
                                    <Typography variant="caption" color="text.secondary" display="block" sx={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                                        {item.label}
                                    </Typography>
                                    <Typography variant="body2" fontWeight={700}>
                                        {item.val}
                                    </Typography>
                                </Grid>
                            ))}
                        </Grid>
                        <Box mt="auto">
                            <Button fullWidth variant="contained" size="small" startIcon={<PlayArrowRoundedIcon />} sx={{ borderRadius: 2, textTransform: 'none', background: "linear-gradient(90deg, #38bdf8, #6366f1)" }}>
                                Watch on YouTube
                            </Button>
                        </Box>
                    </Box>
                </MotionCard>
            </Box>
        );
    };


    return (
        <Box mx="20px" mt="0" mb="20px">
            <Header title="Overview" subtitle="Overview Channel Statistic" />

            {/* Filter hàng đầu */}
            <Box
                mb={2}
                display="flex"
                alignItems={{ xs: "stretch", md: "center" }}
                justifyContent="space-between"
                flexWrap="wrap"
                gap={2}
            >
                <Box
                    display="flex"
                    alignItems={{ xs: "stretch", sm: "center" }}
                    gap={2}
                    flexWrap="wrap"
                    sx={{ width: { xs: "100%", lg: "auto" }, flex: "1 1 520px" }}
                >
                    <ChannelSwitcher
                        options={channels}
                        value={selectedChannel}
                        onChange={(option) => setSelectedChannel(option?.value || "")}
                        sx={CHANNEL_SWITCHER_SX}
                        disabled={loadingChannels}
                        placeholder={loadingChannels ? "Loading channels..." : "Search by channel name"}
                        noOptionsText={loadingChannels ? "Loading channels..." : "No channels found"}
                        getOptionAvatar={(option) => channelAvatarMap[option?.value] || ""}
                        getOptionMeta={(option) => channelRevenueMap[option?.value] || ""}
                    />

                    <TextField
                        select
                        size="small"
                        label="Date range"
                        value={overviewRange}
                        onChange={(e) => setOverviewRange(e.target.value)}
                        sx={{ minWidth: { xs: "100%", sm: 160 } }}
                    >
                        {OVERVIEW_RANGES.map((range) => (
                            <MenuItem key={range.value} value={range.value}>
                                {range.label}
                            </MenuItem>
                        ))}
                    </TextField>

                </Box>

                {videos && videos.length > 0 && (
                    <Typography variant="body2" color={colors.grey[300]}>
                        Total:{" "}
                        <span style={{ fontWeight: 600 }}>{videos.length} video</span>
                    </Typography>
                )}
            </Box>

            {error && (
                <Typography color="error" mb={2}>
                    {error}
                </Typography>
            )}

            {/* Loading */}
            {loadingVideos && videos.length === 0 ? (
                <Box
                    mt={4}
                    display="flex"
                    justifyContent="center"
                    alignItems="center"
                >
                    <CircularProgress />
                </Box>
            ) : videos.length === 0 ? (
                <Box mt={4} textAlign="center">
                    <Typography color={colors.grey[300]}>
                        This channel has no data
                    </Typography>
                </Box>
            ) : (
                <>
                    <Box
                        mt={2}
                        sx={{
                            display: "grid",
                            gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
                            gap: 2,
                            width: "100%",
                        }}
                    >
                        <Box sx={{ display: "flex" }}>
                            <Box sx={{ ...sectionSx, p: 4, minHeight: 560, width: "100%" }}>
                                <Typography variant="h5" fontWeight={700} mb={2}>
                                    Subscribers ({rangeLabel})
                                </Typography>
                                {subscribersSeries.length === 0 ? (
                                    <Typography variant="body2" color="text.secondary">
                                        No data
                                    </Typography>
                                ) : (
                                    <>
                                        <Grid container spacing={2} mb={2}>
                                            <Grid size={{ xs: 12, md: 3 }}>
                                                <Box sx={statCardSx}>
                                                    <Typography variant="body2" color="text.secondary">
                                                        Gained
                                                    </Typography>
                                                    <Typography variant="h5" fontWeight={700}>
                                                        {formatNumber(subscribersSummary.stats.gained)}
                                                    </Typography>
                                                    <Typography
                                                        variant="body2"
                                                        sx={{ color: pctColor(subscribersSummary.stats.gainedPct) }}
                                                    >
                                                        {formatPct(subscribersSummary.stats.gainedPct)}
                                                    </Typography>
                                                </Box>
                                            </Grid>
                                            <Grid size={{ xs: 12, md: 3 }}>
                                                <Box sx={statCardSx}>
                                                    <Typography variant="body2" color="text.secondary">
                                                        Lost
                                                    </Typography>
                                                    <Typography variant="h5" fontWeight={700}>
                                                        {formatNumber(subscribersSummary.stats.lost)}
                                                    </Typography>
                                                    <Typography
                                                        variant="body2"
                                                        sx={{ color: pctColor(-subscribersSummary.stats.lostPct) }}
                                                    >
                                                        {formatPct(subscribersSummary.stats.lostPct)}
                                                    </Typography>
                                                </Box>
                                            </Grid>
                                            <Grid size={{ xs: 12, md: 3 }}>
                                                <Box sx={statCardSx}>
                                                    <Typography variant="body2" color="text.secondary">
                                                        Change
                                                    </Typography>
                                                    <Typography variant="h5" fontWeight={700}>
                                                        {formatNumber(subscribersSummary.stats.change)}
                                                    </Typography>
                                                    <Typography
                                                        variant="body2"
                                                        sx={{ color: pctColor(subscribersSummary.stats.changePct) }}
                                                    >
                                                        {formatPct(subscribersSummary.stats.changePct)}
                                                    </Typography>
                                                </Box>
                                            </Grid>
                                            <Grid size={{ xs: 12, md: 3 }}>
                                                <Box sx={statCardSx}>
                                                    <Typography variant="body2" color="text.secondary">
                                                        Avg daily change
                                                    </Typography>
                                                    <Typography variant="h5" fontWeight={700}>
                                                        {formatNumber(Math.round(subscribersSummary.stats.avg))}
                                                    </Typography>
                                                    <Typography
                                                        variant="body2"
                                                        sx={{ color: pctColor(subscribersSummary.stats.avgPct) }}
                                                    >
                                                        {formatPct(subscribersSummary.stats.avgPct)}
                                                    </Typography>
                                                </Box>
                                            </Grid>
                                        </Grid>

                                        <Grid container spacing={2} sx={{ minWidth: 0 }}>
                                            <Grid size={{ xs: 12, md: 6 }} sx={{ minWidth: 0 }}>
                                                <Box sx={{ ...chartCardSx, minWidth: 0, width: "100%" }}>
                                                    <Typography variant="subtitle1" fontWeight={700} mb={0.5}>
                                                        Gained
                                                    </Typography>
                                                    <Box sx={{ width: "100%", minWidth: 0, minHeight: 0 }}>
                                                        <ResponsiveContainer width="100%" height={320} minWidth={0} minHeight={0}>
                                                            <BarChart
                                                                data={subscribersSummary.chart}
                                                                margin={{ top: 4, right: 6, left: -30, bottom: -6 }}
                                                            >
                                                                <CartesianGrid
                                                                    stroke="rgba(148,163,184,0.2)"
                                                                    strokeDasharray="3 3"
                                                                />
                                                                <XAxis
                                                                    dataKey="day"
                                                                    tick={{ fontSize: 11 }}
                                                                    ticks={subscribersXAxisTicks}
                                                                    tickFormatter={formatDateMonth}
                                                                    allowDuplicatedCategory={false}
                                                                />
                                                                <YAxis tickFormatter={formatNumber} />
                                                                <Tooltip
                                                                    {...chartTooltipStyles}
                                                                    labelFormatter={formatDateFull}
                                                                />
                                                                <Bar dataKey="gained" fill="#22c55e" radius={[6, 6, 0, 0]} />
                                                            </BarChart>
                                                        </ResponsiveContainer>
                                                    </Box>
                                                </Box>
                                            </Grid>
                                            <Grid size={{ xs: 12, md: 6 }} sx={{ minWidth: 0 }}>
                                                <Box sx={{ ...chartCardSx, minWidth: 0, width: "100%" }}>
                                                    <Typography variant="subtitle1" fontWeight={700} mb={0.5}>
                                                        Change
                                                    </Typography>
                                                    <Box sx={{ width: "100%", minWidth: 0, minHeight: 0 }}>
                                                        <ResponsiveContainer width="100%" height={320} minWidth={0} minHeight={0}>
                                                            <BarChart
                                                                data={subscribersSummary.chart}
                                                                margin={{ top: 4, right: 6, left: -30, bottom: -6 }}
                                                            >
                                                                <CartesianGrid
                                                                    stroke="rgba(148,163,184,0.2)"
                                                                    strokeDasharray="3 3"
                                                                />
                                                                <XAxis
                                                                    dataKey="day"
                                                                    tick={{ fontSize: 11 }}
                                                                    ticks={subscribersXAxisTicks}
                                                                    tickFormatter={formatDateMonth}
                                                                    allowDuplicatedCategory={false}
                                                                />
                                                                <YAxis tickFormatter={formatNumber} />
                                                                <Tooltip
                                                                    {...chartTooltipStyles}
                                                                    labelFormatter={formatDateFull}
                                                                />
                                                                <Bar dataKey="change" fill="#7c3aed" radius={[6, 6, 0, 0]} />
                                                            </BarChart>
                                                        </ResponsiveContainer>
                                                    </Box>
                                                </Box>
                                            </Grid>
                                        </Grid>
                                    </>
                                )}
                            </Box>
                        </Box>
                        <Box sx={{ display: "flex" }}>
                            <Box sx={{ ...sectionSx, p: 4, minHeight: 560, width: "100%" }}>
                                <Typography variant="subtitle1" fontWeight={700} mb={1}>
                                    Revenue ({rangeLabel})
                                </Typography>
                                {revenueRows.length === 0 ? (
                                    <Typography variant="body2" color="text.secondary">
                                        No data
                                    </Typography>
                                ) : (
                                    <>
                                        <Stack spacing={1.5} alignItems="flex-end">
                                            <Box display="flex" alignItems="baseline" gap={1.5} sx={{ textAlign: "left", minWidth: 100 }}>
                                                <Typography variant="body2" color="text.secondary">
                                                    Estimated
                                                </Typography>
                                                <Typography variant="body2" fontWeight={600}>
                                                    {formatCurrency(revenueSummary.estimated)}
                                                </Typography>
                                            </Box>
                                            <Box display="flex" alignItems="baseline" gap={1.5} sx={{ textAlign: "left", minWidth: 100 }}>
                                                <Typography variant="body2" color="text.secondary">
                                                    Ad revenue
                                                </Typography>
                                                <Typography variant="body2" fontWeight={600}>
                                                    {formatCurrency(revenueSummary.ad)}
                                                </Typography>
                                            </Box>
                                            <Box display="flex" alignItems="baseline" gap={1.5} sx={{ textAlign: "left", minWidth: 100 }}>
                                                <Typography variant="body2" color="text.secondary">
                                                    Gross revenue
                                                </Typography>
                                                <Typography variant="body2" fontWeight={600}>
                                                    {formatCurrency(revenueSummary.gross)}
                                                </Typography>
                                            </Box>
                                            <Box display="flex" alignItems="baseline" gap={1.5} sx={{ textAlign: "left", minWidth: 100 }}>
                                                <Typography variant="body2" color="text.secondary">
                                                    Avg RPM
                                                </Typography>
                                                <Typography variant="body2" fontWeight={600}>
                                                    {formatCurrency(revenueSummary.rpmAvg)}
                                                </Typography>
                                            </Box>
                                        </Stack>
                                        {revenueChartData.length > 0 && (
                                            <Box mt={2} sx={{ ml: -3, minWidth: 0, width: "100%" }}>
                                                <ResponsiveContainer width="100%" height={320} minWidth={0} minHeight={0}>
                                                    <LineChart data={revenueChartData}>
                                                        <CartesianGrid
                                                            strokeDasharray="3 3"
                                                            stroke={
                                                                theme.palette.mode === "dark"
                                                                    ? "rgba(148,163,184,0.2)"
                                                                    : "rgba(15,23,42,0.1)"
                                                            }
                                                        />
                                                        <XAxis
                                                            dataKey="day"
                                                            ticks={revenueXAxisTicks}
                                                            tickFormatter={formatDateMonth}
                                                            tick={{ fontSize: 11 }}
                                                            interval={0}
                                                            allowDuplicatedCategory={false}
                                                        />
                                                        <YAxis
                                                            tickFormatter={(value) => formatCurrency(value)}
                                                            tick={{ fontSize: 11 }}
                                                        />
                                                        <Tooltip
                                                            formatter={(value) => [
                                                                formatCurrency(value),
                                                                "Estimated",
                                                            ]}
                                                            labelFormatter={formatDate}
                                                            contentStyle={chartTooltipStyles.contentStyle}
                                                            labelStyle={chartTooltipStyles.labelStyle}
                                                        />
                                                        <Line
                                                            type="monotone"
                                                            dataKey="estimated"
                                                            stroke="#f59e0b"
                                                            strokeWidth={2}
                                                            dot={false}
                                                        />
                                                    </LineChart>
                                                </ResponsiveContainer>
                                            </Box>
                                        )}
                                    </>
                                )}
                            </Box>
                        </Box>
                    </Box>

                    <Box
                        mt={2}
                        sx={{
                            display: "grid",
                            gridTemplateColumns: { xs: "1fr", md: "0.9fr 0.9fr 1.2fr" },
                            gap: 2,
                            width: "100%",
                        }}
                    >
                        <Box sx={{ ...sectionSx, p: 3 }}>
                            <Typography variant="subtitle1" fontWeight={700} mb={1}>
                                Top 10 keywords by views ({rangeLabel})
                            </Typography>
                            {topKeywords.length === 0 ? (
                                <Typography variant="body2" color="text.secondary">
                                    No data
                                </Typography>
                            ) : (
                                <>
                                    <Stack spacing={1}>
                                        {topKeywords.map((k) => {
                                            const value = Number(k.views) || 0;
                                            const pct = Math.max(
                                                6,
                                                Math.round((value / topKeywordMax) * 100)
                                            );
                                            return (
                                                <Box key={k.keyword}>
                                                    <Box display="flex" justifyContent="space-between" mb={0.5}>
                                                        <Typography variant="body2">{k.keyword}</Typography>
                                                        <Typography variant="body2" fontWeight={600}>
                                                            {formatNumber(value)}
                                                        </Typography>
                                                    </Box>
                                                    <Box
                                                        sx={{
                                                            height: 8,
                                                            borderRadius: 999,
                                                            bgcolor:
                                                                theme.palette.mode === "dark"
                                                                    ? "rgba(148,163,184,0.2)"
                                                                    : "rgba(15,23,42,0.12)",
                                                            overflow: "hidden",
                                                        }}
                                                    >
                                                        <Box
                                                            sx={{
                                                                width: animateOverviewBars ? `${pct}%` : 0,
                                                                height: "100%",
                                                                borderRadius: 999,
                                                                background:
                                                                    theme.palette.mode === "dark"
                                                                        ? "linear-gradient(90deg, #f59e0b, #f97316)"
                                                                        : "linear-gradient(90deg, #f59e0b, #fb923c)",
                                                                transition: "width 0.5s ease",
                                                            }}
                                                        />
                                                    </Box>
                                                </Box>
                                            );
                                        })}
                                    </Stack>
                                    {canLoadMoreKeywords && (
                                        <Box mt={2} display="flex" justifyContent="center">
                                            <Button
                                                size="small"
                                                variant="outlined"
                                                sx={{
                                                    transition: "transform 0.2s ease, box-shadow 0.2s ease",
                                                    color:
                                                        theme.palette.mode === "dark" ? "#e2e8f0" : "#0f172a",
                                                    borderColor:
                                                        theme.palette.mode === "dark"
                                                            ? "rgba(148,163,184,0.5)"
                                                            : "rgba(15,23,42,0.25)",
                                                    "&:hover": {
                                                        transform: "translateY(-1px)",
                                                        boxShadow:
                                                            theme.palette.mode === "dark"
                                                                ? "0 8px 18px rgba(2,6,23,0.5)"
                                                                : "0 8px 18px rgba(15,23,42,0.12)",
                                                        borderColor:
                                                            theme.palette.mode === "dark"
                                                                ? "rgba(148,163,184,0.9)"
                                                                : "rgba(15,23,42,0.5)",
                                                        backgroundColor:
                                                            theme.palette.mode === "dark"
                                                                ? "rgba(148,163,184,0.12)"
                                                                : "rgba(15,23,42,0.04)",
                                                    },
                                                }}
                                                onClick={() =>
                                                    setKeywordLimit((prev) =>
                                                        Math.min(prev + OVERVIEW_LIMIT_STEP, OVERVIEW_LIMIT_MAX)
                                                    )
                                                }
                                            >
                                                Load more
                                            </Button>
                                        </Box>
                                    )}
                                </>
                            )}
                        </Box>

                        <Box sx={{ ...sectionSx, p: 3 }}>
                            <Typography variant="subtitle1" fontWeight={700} mb={1}>
                                Top 10 sources by views ({rangeLabel})
                            </Typography>
                            {topSources.length === 0 ? (
                                <Typography variant="body2" color="text.secondary">
                                    No data
                                </Typography>
                            ) : (
                                <>
                                    <Stack spacing={1}>
                                        {topSources.map((s) => {
                                            const value = Number(s.views) || 0;
                                            const pct = Math.max(
                                                6,
                                                Math.round((value / topSourceMax) * 100)
                                            );
                                            return (
                                                <Box key={s.source}>
                                                    <Box display="flex" justifyContent="space-between" mb={0.5}>
                                                        <Typography variant="body2">{s.source}</Typography>
                                                        <Typography variant="body2" fontWeight={600}>
                                                            {formatNumber(value)}
                                                        </Typography>
                                                    </Box>
                                                    <Box
                                                        sx={{
                                                            height: 8,
                                                            borderRadius: 999,
                                                            bgcolor:
                                                                theme.palette.mode === "dark"
                                                                    ? "rgba(148,163,184,0.2)"
                                                                    : "rgba(15,23,42,0.12)",
                                                            overflow: "hidden",
                                                        }}
                                                    >
                                                        <Box
                                                            sx={{
                                                                width: animateOverviewBars ? `${pct}%` : 0,
                                                                height: "100%",
                                                                borderRadius: 999,
                                                                background:
                                                                    theme.palette.mode === "dark"
                                                                        ? "linear-gradient(90deg, #22c55e, #06b6d4)"
                                                                        : "linear-gradient(90deg, #22c55e, #0ea5e9)",
                                                                transition: "width 0.5s ease",
                                                            }}
                                                        />
                                                    </Box>
                                                </Box>
                                            );
                                        })}
                                    </Stack>
                                    {canLoadMoreSources && (
                                        <Box mt={2} display="flex" justifyContent="center">
                                            <Button
                                                size="small"
                                                variant="outlined"
                                                sx={{
                                                    transition: "transform 0.2s ease, box-shadow 0.2s ease",
                                                    color:
                                                        theme.palette.mode === "dark" ? "#e2e8f0" : "#0f172a",
                                                    borderColor:
                                                        theme.palette.mode === "dark"
                                                            ? "rgba(148,163,184,0.5)"
                                                            : "rgba(15,23,42,0.25)",
                                                    "&:hover": {
                                                        transform: "translateY(-1px)",
                                                        boxShadow:
                                                            theme.palette.mode === "dark"
                                                                ? "0 8px 18px rgba(2,6,23,0.5)"
                                                                : "0 8px 18px rgba(15,23,42,0.12)",
                                                        borderColor:
                                                            theme.palette.mode === "dark"
                                                                ? "rgba(148,163,184,0.9)"
                                                                : "rgba(15,23,42,0.5)",
                                                        backgroundColor:
                                                            theme.palette.mode === "dark"
                                                                ? "rgba(148,163,184,0.12)"
                                                                : "rgba(15,23,42,0.04)",
                                                    },
                                                }}
                                                onClick={() =>
                                                    setSourceLimit((prev) =>
                                                        Math.min(prev + OVERVIEW_LIMIT_STEP, OVERVIEW_LIMIT_MAX)
                                                    )
                                                }
                                            >
                                                Load more
                                            </Button>
                                        </Box>
                                    )}
                                </>
                            )}
                        </Box>

                        <Box sx={{ ...sectionSx, p: 3 }}>
                            <Typography variant="subtitle1" fontWeight={700} mb={1}>
                                Views by country ({rangeLabel})
                            </Typography>
                            {countryViews.length === 0 ? (
                                <Typography variant="body2" color="text.secondary">
                                    No data
                                </Typography>
                            ) : (
                                <>
                                    <Box height={240}>
                                        <ResponsiveChoropleth
                                            debounceResize={150}
                                            data={countryMapData}
                                            features={geoFeatures.features}
                                            valueFormat={formatNumber}
                                            domain={[0, countryDomainMax]}
                                            tooltip={({ feature }) => {
                                                const label = countryResolvers.nameOf(feature.id);
                                                const value = feature.value || 0;

                                                return (
                                                    <Box
                                                        sx={{
                                                            px: 1.2,
                                                            py: 0.75,
                                                            borderRadius: 1,
                                                            fontSize: 13,
                                                            fontWeight: 600,
                                                            bgcolor:
                                                                theme.palette.mode === "dark"
                                                                    ? "rgba(0,0,0,0.75)"
                                                                    : "rgba(255,255,255,0.95)",
                                                            boxShadow: 3,
                                                        }}
                                                    >
                                                        <div>{label}</div>
                                                        <div>Views: {formatNumber(value)}</div>
                                                    </Box>
                                                );
                                            }}
                                            unknownColor="#999"
                                            projectionScale={80}
                                            projectionTranslation={[0.5, 0.65]}
                                            borderWidth={1}
                                            borderColor="#fff"
                                        />
                                    </Box>
                                    <Box mt={2}>
                                        <Stack>
                                            {topCountries.map((row) => {
                                                const pct =
                                                    countryDomainMax > 0
                                                        ? Math.max(6, Math.round((row.value / countryDomainMax) * 100))
                                                        : 0;
                                                return (
                                                    <Box key={row.id}>
                                                        <Box display="flex" justifyContent="space-between" mb={0.5}>
                                                            <Typography variant="body2">
                                                                {countryResolvers.nameOf(row.id)}
                                                            </Typography>
                                                            <Typography variant="body2" fontWeight={600}>
                                                                {formatNumber(row.value)}
                                                            </Typography>
                                                        </Box>
                                                        <Box
                                                            sx={{
                                                                height: 8,
                                                                borderRadius: 999,
                                                                bgcolor:
                                                                    theme.palette.mode === "dark"
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
                                                                    background:
                                                                        theme.palette.mode === "dark"
                                                                            ? "linear-gradient(90deg, #38bdf8, #a855f7)"
                                                                            : "linear-gradient(90deg, #0ea5e9, #6366f1)",
                                                                }}
                                                            />
                                                        </Box>
                                                    </Box>
                                                );
                                            })}
                                        </Stack>
                                    </Box>
                                </>
                            )}
                        </Box>
                    </Box>

                    {/* Latest 5 Videos Section - KEPT MODERN UPDATE */}
                    <Box mt={4} sx={{ ...sectionSx, p: 4 }}>
                        <Box display="flex" alignItems="center" justifyContent="space-between" mb={3}>
                            <Typography variant="h5" fontWeight={800} display="flex" alignItems="center" gap={1.5}>
                                <InsightsIcon color="primary" /> Latest Video Performance
                            </Typography>
                            <Typography variant="body2" color="text.secondary">Highlights from your recent uploads</Typography>
                        </Box>
                        <Box sx={latestRowSx}>
                            {latestVideos.map((v, idx) => renderVideoCard(v, idx))}
                        </Box>
                    </Box>
                </>
            )}

            <Dialog
                open={liveViewsOpen}
                onClose={() => setLiveViewsOpen(false)}
                fullWidth
                maxWidth="xl"
                scroll="paper"
                PaperProps={{
                    sx: {
                        borderRadius: 3,
                        overflow: "hidden",
                        background:
                            theme.palette.mode === "dark"
                                ? "linear-gradient(180deg, rgba(2,6,23,0.98) 0%, rgba(15,23,42,0.98) 100%)"
                                : "linear-gradient(180deg, rgba(248,250,252,0.98) 0%, rgba(255,255,255,0.98) 100%)",
                    },
                }}
            >
                <Box
                    sx={{
                        px: 2.5,
                        py: 1.5,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        borderBottom: "1px solid",
                        borderColor:
                            theme.palette.mode === "dark"
                                ? "rgba(148,163,184,0.18)"
                                : "rgba(15,23,42,0.08)",
                    }}
                >
                    <Box />
                    <IconButton onClick={() => setLiveViewsOpen(false)}>
                        <CloseIcon />
                    </IconButton>
                </Box>
                <DialogContent sx={{ p: 2.5 }}>
                    <LiveViews />
                </DialogContent>
            </Dialog>
        </Box>
    );
};

export default VideoList;
