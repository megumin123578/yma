import { useEffect, useMemo, useState } from "react";
import { Box, Typography, useTheme } from "@mui/material";
import { alpha } from "@mui/material/styles";
import { tokens } from "../../theme";
import Header from "../Header";
import api from "../../services/api";
import { COUNTRY_FALLBACK } from "../../data/countryMapping";
import { useGeoFeatures } from "../../utils/useGeoFeatures";
import { getChannelRevenueMap } from "../Module";
import {
    getStoredSharedChannelId,
    listenSharedChannelId,
    resolvePreferredSharedChannelId,
    setStoredSharedChannelId,
} from "../../utils/sharedChannel";
import { sortByStoredTokenOrder } from "../../utils/tokenOrder";
import CountryOverviewSection from "./CountryOverviewSection";
import DashboardFilters from "./DashboardFilters";
import DashboardSkeleton from "./DashboardSkeleton";
import LatestVideosSection from "./LatestVideosSection";
import MetricProgressSection from "./MetricProgressSection";
import RealtimeSection from "./RealtimeSection";
import RevenueOverviewSection from "./RevenueOverviewSection";
import SubscribersOverviewSection from "./SubscribersOverviewSection";
import {
    LATEST_VIDEOS_PAGE_SIZE,
    OVERVIEW_LIMIT_DEFAULT,
    OVERVIEW_LIMIT_MAX,
    OVERVIEW_LIMIT_STEP,
    OVERVIEW_RANGES,
    formatCurrency,
    getOverviewRangeDates,
    formatNumber,
} from "./dashboardUtils";

const DashboardContainer = () => {
    const theme = useTheme();
    const isDark = theme.palette.mode === "dark";
    const colors = tokens(theme.palette.mode);
    const geoFeatures = useGeoFeatures();
    const dashboardPalette = useMemo(
        () => ({
            surface: alpha(theme.palette.background.paper, isDark ? 0.28 : 0.94),
            surfaceStrong: alpha(theme.palette.background.paper, isDark ? 0.92 : 0.98),
            tooltipBg: alpha(theme.palette.background.paper, isDark ? 0.92 : 0.98),
            tooltipLabel: theme.palette.text.primary,
            white: theme.palette.common.white,
            black: theme.palette.common.black,
            badgeBg: alpha(theme.palette.background.default, isDark ? 0.82 : 0.76),
            badgeBorder: alpha(theme.palette.common.white, 0.12),
            playOverlayBg: alpha(theme.palette.common.black, 0.3),
            playButtonBg: alpha(theme.palette.common.white, 0.2),
            playButtonBorder: alpha(theme.palette.common.white, 0.3),
            positive: theme.palette.success.main,
            info: theme.palette.info.main,
            warning: theme.palette.warning.main,
            warningSoft: theme.palette.warning.light,
            error: theme.palette.error.main,
            accent: theme.palette.primary.main,
            accentAlt: colors.blueAccent[500],
            accentSoft: colors.blueAccent[400],
            accentLight: colors.blueAccent[300],
            secondary: theme.palette.secondary.main,
            muted: theme.palette.text.secondary,
            revenueMetricColors: {
                estimated: theme.palette.success.main,
                ad: theme.palette.info.main,
                gross: colors.blueAccent[400],
                premium: theme.palette.warning.main,
                monetized: theme.palette.secondary.main,
                adImpressions: colors.blueAccent[500],
                rpm: theme.palette.error.main,
                cpm: theme.palette.text.secondary,
                playbackCpm: colors.blueAccent[300],
            },
        }),
        [colors, isDark, theme]
    );

    const actionButtonSx = {
        transition: "transform 0.2s ease, box-shadow 0.2s ease",
        color: theme.palette.text.primary,
        borderColor: alpha(theme.palette.divider, isDark ? 0.7 : 0.55),
        "&:hover": {
            transform: "translateY(-1px)",
            boxShadow: isDark
                ? `0 8px 18px ${alpha(theme.palette.common.black, 0.5)}`
                : `0 8px 18px ${alpha(colors.primary[200], 0.16)}`,
            borderColor: alpha(theme.palette.divider, isDark ? 1 : 0.8),
            backgroundColor: alpha(theme.palette.text.primary, isDark ? 0.08 : 0.04),
        },
    };

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
            return OVERVIEW_RANGES.some((range) => range.value === stored) ? stored : "28d";
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
    const [error, setError] = useState("");
    const [latestVisibleCount, setLatestVisibleCount] = useState(LATEST_VIDEOS_PAGE_SIZE);
    const [realtime48h, setRealtime48h] = useState({ rows: [], totals: {} });
    const [realtime60m, setRealtime60m] = useState({ rows: [], totals: {} });

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

        const toNumberOrNull = (value) => {
            if (value == null || value === "") return null;
            const num = Number(value);
            return Number.isFinite(num) ? num : null;
        };

        return sorted.map((video) => {
            const views = Math.max(0, toNumberOrNull(video?.views) ?? 0);
            const likes = Math.max(0, toNumberOrNull(video?.likes) ?? 0);
            const comments = Math.max(0, toNumberOrNull(video?.comments) ?? 0);
            const shares = Math.max(0, toNumberOrNull(video?.shares) ?? 0);
            const engagementRate =
                views > 0 ? ((likes + comments + shares) / views) * 100 : null;

            return {
                ...video,
                views,
                likes,
                comments,
                shares,
                engaged_views: Math.max(0, toNumberOrNull(video?.engaged_views) ?? 0),
                thumbnail_impressions: Math.max(
                    0,
                    toNumberOrNull(video?.thumbnail_impressions) ?? 0
                ),
                subscribers_gained: Math.max(
                    0,
                    toNumberOrNull(video?.subscribers_gained) ?? 0
                ),
                subscribers_lost: Math.max(
                    0,
                    toNumberOrNull(video?.subscribers_lost) ?? 0
                ),
                average_view_duration_seconds: toNumberOrNull(
                    video?.average_view_duration_seconds
                ),
                thumbnail_ctr: toNumberOrNull(video?.thumbnail_ctr),
                engagementRate,
            };
        });
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

        for (const feature of geoFeatures?.features || []) {
            const id = String(feature.id || feature.properties?.iso_a3 || "");
            const iso2 = feature.properties?.iso_a2?.toUpperCase() || "";
            const name = feature.properties?.name || id;

            if (iso2) iso2ToFeatureId.set(iso2, id);
            idToName.set(id, name);
        }

        return {
            resolveId: (code) => {
                const normalizedCode = String(code).toUpperCase();
                return (
                    iso2ToFeatureId.get(normalizedCode) ||
                    COUNTRY_FALLBACK[normalizedCode] ||
                    normalizedCode
                );
            },
            nameOf: (id) => idToName.get(id) || id,
        };
    }, [geoFeatures]);

    const countryMapData = useMemo(
        () =>
            (countryViews || []).map((row) => {
                const id = countryResolvers.resolveId(row.country);
                return {
                    id,
                    value: Number(row.views) || 0,
                    label: countryResolvers.nameOf(id),
                };
            }),
        [countryViews, countryResolvers]
    );

    const countryDomainMax = useMemo(() => {
        const values = countryMapData.map((item) => Number(item.value) || 0);
        return Math.max(1, ...values);
    }, [countryMapData]);

    const topCountries = useMemo(
        () =>
            [...countryMapData]
                .sort((a, b) => (b.value || 0) - (a.value || 0))
                .slice(0, 5),
        [countryMapData]
    );

    const topKeywordMax = useMemo(
        () => Math.max(1, ...topKeywords.map((item) => Number(item.views) || 0)),
        [topKeywords]
    );

    const topSourceMax = useMemo(
        () => Math.max(1, ...topSources.map((item) => Number(item.views) || 0)),
        [topSources]
    );

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
            premium: sum(revenueRows, "estimated_red_partner_revenue"),
            monetized: sum(revenueRows, "monetized_playbacks"),
            adImpressions: sum(revenueRows, "ad_impressions"),
            views: sum(revenueRows, "views"),
            rpm:
                sum(revenueRows, "views") > 0
                    ? (sum(revenueRows, "estimated_revenue") * 1000) /
                      sum(revenueRows, "views")
                    : avg(revenueRows, "rpm"),
            cpm:
                sum(revenueRows, "ad_impressions") > 0
                    ? (sum(revenueRows, "gross_revenue") * 1000) /
                      sum(revenueRows, "ad_impressions")
                    : avg(revenueRows, "cpm"),
            playbackCpm:
                sum(revenueRows, "monetized_playbacks") > 0
                    ? (sum(revenueRows, "gross_revenue") * 1000) /
                      sum(revenueRows, "monetized_playbacks")
                    : avg(revenueRows, "playback_cpm"),
        };
    }, [revenueRows]);

    const revenueChartData = useMemo(
        () =>
            (revenueRows || []).map((row) => ({
                day: row.day,
                estimated: Number(row?.estimated_revenue || 0),
                ad: Number(row?.ad_revenue || 0),
                gross: Number(row?.gross_revenue || 0),
                premium: Number(row?.estimated_red_partner_revenue || 0),
            })),
        [revenueRows]
    );

    const revenueXAxisTicks = useMemo(() => {
        const days = revenueChartData.map((row) => row.day).filter(Boolean);
        if (!days.length) return [];
        if (overviewRange !== "28d") return days;

        return days.filter((day, index) => {
            if (index === 0 || index === days.length - 1) return true;
            return index % 2 === 0;
        });
    }, [overviewRange, revenueChartData]);

    const subscribersXAxisTicks = useMemo(() => {
        const days = subscribersSummary.chart.map((row) => row.day).filter(Boolean);
        if (!days.length) return [];
        const first = days[0];
        const last = days[days.length - 1];
        if (first === last) return [first];
        return [first, last];
    }, [subscribersSummary.chart]);

    const chartTooltipStyles = useMemo(
        () => ({
            contentStyle: {
                backgroundColor: dashboardPalette.tooltipBg,
                border: isDark
                    ? "1px solid rgba(148,163,184,0.35)"
                    : "1px solid rgba(15,23,42,0.12)",
                borderRadius: 8,
                boxShadow: isDark
                    ? "0 10px 18px rgba(2,6,23,0.45)"
                    : "0 10px 18px rgba(15,23,42,0.12)",
            },
            labelStyle: { color: dashboardPalette.tooltipLabel },
        }),
        [dashboardPalette.tooltipBg, dashboardPalette.tooltipLabel, isDark]
    );

    useEffect(() => {
        let active = true;

        const fetchChannels = async () => {
            try {
                setLoadingChannels(true);
                const res = await api.get("/api/content/channels");
                const data = res.data;
                const items = data.items || [];
                const finalChannels = sortByStoredTokenOrder(items, (item) => item.value);
                if (!active) return;
                setChannels(finalChannels);
                setChannelAvatarMap(
                    finalChannels.reduce((map, item) => {
                        const value = item?.value || "";
                        if (value) map[value] = item?.avatar || "";
                        return map;
                    }, {})
                );
                setSelectedChannel((current) =>
                    resolvePreferredSharedChannelId(
                        getStoredSharedChannelId("overview.selectedChannelId") || current,
                        finalChannels,
                        (item) => item.value
                    )
                );
            } catch (err) {
                if (!active) return;
                console.error(err);
                setError(
                    "Khong load duoc danh sach kenh. Hay chay backend: uvicorn python_backend.main:app --host 0.0.0.0 --port 8000 --reload"
                );
            } finally {
                if (active) setLoadingChannels(false);
            }
        };

        fetchChannels();
        return () => {
            active = false;
        };
    }, []);

    useEffect(() => {
        if (!selectedChannel) return;
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
            return undefined;
        }
        return undefined;
    }, [overviewRange]);

    useEffect(() => {
        setKeywordLimit(OVERVIEW_LIMIT_DEFAULT);
        setSourceLimit(OVERVIEW_LIMIT_DEFAULT);
        setLatestVisibleCount(LATEST_VIDEOS_PAGE_SIZE);
    }, [selectedChannel, overviewRange]);

    useEffect(() => {
        if (!selectedChannel) return;

        const fetchVideos = async () => {
            try {
                setLoadingVideos(true);
                setError("");
                const { start, end } = getOverviewRangeDates(overviewRange);
                const res = await api.post("/api/content/list", {
                    start,
                    end,
                    channelId: selectedChannel,
                    contentType: "all",
                });
                const items = Array.isArray(res.data?.items) ? res.data.items : [];
                setVideos(
                    items.map((item) => ({
                        account_tag: item?.channelId || selectedChannel,
                        video_id: item?.videoId || "",
                        title: item?.title || "",
                        thumbnail: item?.thumbnail || "",
                        publish_date: item?.publishedAt || item?.published || "",
                        views: item?.views,
                        likes: item?.likes,
                        comments: item?.comments,
                        engaged_views: item?.engagedViews ?? item?.engaged_views,
                        thumbnail_impressions: item?.impressions,
                        thumbnail_ctr:
                            item?.impressionsClickThroughRate ??
                            item?.impressions_click_through_rate,
                        average_view_duration_seconds:
                            item?.averageViewDuration ?? item?.average_view_duration,
                        shares: item?.shares,
                        subscribers_gained: item?.subscribers,
                        subscribers_lost: item?.subscribers_lost,
                    }))
                );
            } catch (err) {
                console.error(err);
                setError("Khong load duoc danh sach video.");
            } finally {
                setLoadingVideos(false);
            }
        };

        fetchVideos();
    }, [selectedChannel, overviewRange]);

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

                setAnimateOverviewBars(false);
                setTopKeywords(Array.isArray(topKeywordsResp.data) ? topKeywordsResp.data : []);
                setTopSources(Array.isArray(topSourcesResp.data) ? topSourcesResp.data : []);
                setCountryViews(
                    Array.isArray(countryResp.data?.rows) ? countryResp.data.rows : []
                );
                setSubscribersSeries(Array.isArray(subsResp.data) ? subsResp.data : []);
                setRevenueRows(
                    Array.isArray(revenueResp.data?.rows) ? revenueResp.data.rows : []
                );
                requestAnimationFrame(() => setAnimateOverviewBars(true));
            } catch {
                setTopKeywords([]);
                setTopSources([]);
                setCountryViews([]);
                setSubscribersSeries([]);
                setRevenueRows([]);
                setAnimateOverviewBars(false);
            }
        };

        fetchOverviewExtras();
    }, [selectedChannel, overviewRange, rangeDays, keywordLimit, sourceLimit]);

    useEffect(() => {
        if (!selectedChannel) {
            setRealtime48h({ rows: [], totals: {} });
            setRealtime60m({ rows: [], totals: {} });
            return undefined;
        }

        let active = true;
        const fetchRealtime = async () => {
            try {
                const [r48, r60] = await Promise.all([
                    api.get(
                        `/api/video_overview/realtime_48h?accountTag=${encodeURIComponent(
                            selectedChannel
                        )}`
                    ),
                    api.get(
                        `/api/video_overview/realtime_60m?accountTag=${encodeURIComponent(
                            selectedChannel
                        )}`
                    ),
                ]);
                if (!active) return;
                setRealtime48h({
                    rows: Array.isArray(r48.data?.rows) ? r48.data.rows : [],
                    totals: r48.data?.totals || {},
                });
                setRealtime60m({
                    rows: Array.isArray(r60.data?.rows) ? r60.data.rows : [],
                    totals: r60.data?.totals || {},
                });
            } catch {
                if (!active) return;
                setRealtime48h({ rows: [], totals: {} });
                setRealtime60m({ rows: [], totals: {} });
            }
        };

        fetchRealtime();
        const intervalId = setInterval(fetchRealtime, 60_000);
        return () => {
            active = false;
            clearInterval(intervalId);
        };
    }, [selectedChannel]);

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
        value >= 0 ? dashboardPalette.positive : dashboardPalette.error;
    const formatPct = (value) => `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;

    const revenueMetricCards = [
        {
            label: "Estimated Revenue",
            value: formatCurrency(revenueSummary.estimated),
            color: dashboardPalette.revenueMetricColors.estimated,
        },
        {
            label: "Estimated Ad Revenue",
            value: formatCurrency(revenueSummary.ad),
            color: dashboardPalette.revenueMetricColors.ad,
        },
        {
            label: "Gross Revenue",
            value: formatCurrency(revenueSummary.gross),
            color: dashboardPalette.revenueMetricColors.gross,
        },
        {
            label: "Premium Revenue",
            value: formatCurrency(revenueSummary.premium),
            color: dashboardPalette.revenueMetricColors.premium,
        },
        {
            label: "Monetized Playbacks",
            value: formatNumber(revenueSummary.monetized),
            color: dashboardPalette.revenueMetricColors.monetized,
        },
        {
            label: "Ad Impressions",
            value: formatNumber(revenueSummary.adImpressions),
            color: dashboardPalette.revenueMetricColors.adImpressions,
        },
        {
            label: "RPM",
            value: formatCurrency(revenueSummary.rpm),
            color: dashboardPalette.revenueMetricColors.rpm,
        },
        {
            label: "CPM",
            value: formatCurrency(revenueSummary.cpm),
            color: dashboardPalette.revenueMetricColors.cpm,
        },
        {
            label: "Playback CPM",
            value: formatCurrency(revenueSummary.playbackCpm),
            color: dashboardPalette.revenueMetricColors.playbackCpm,
        },
    ];

    const latestRowSx = {
        display: "grid",
        gridTemplateColumns: {
            xs: "1fr",
            sm: "repeat(2, 1fr)",
            md: "repeat(3, 1fr)",
            lg: "repeat(5, 1fr)",
        },
        gap: 3,
        width: "100%",
    };

    const visibleLatestVideos = latestVideos.slice(0, latestVisibleCount);
    const canLoadMoreLatestVideos = visibleLatestVideos.length < latestVideos.length;
    const canCollapseLatestVideos = latestVisibleCount > LATEST_VIDEOS_PAGE_SIZE;

    return (
        <Box mx="20px" mt="0" mb="20px">
            <Header title="Dashboard" subtitle="Overview Channel Statistic" />

            <DashboardFilters
                channels={channels}
                selectedChannel={selectedChannel}
                onChannelChange={setSelectedChannel}
                channelAvatarMap={channelAvatarMap}
                channelRevenueMap={channelRevenueMap}
                loadingChannels={loadingChannels}
                overviewRange={overviewRange}
                onOverviewRangeChange={setOverviewRange}
                totalVideos={videos.length}
                colors={colors}
            />

            {error && (
                <Typography color="error" mb={2}>
                    {error}
                </Typography>
            )}

            {loadingVideos && videos.length === 0 ? (
                <DashboardSkeleton
                    sectionSx={sectionSx}
                    statCardSx={statCardSx}
                    chartCardSx={chartCardSx}
                    latestRowSx={latestRowSx}
                    isDark={isDark}
                    dashboardPalette={dashboardPalette}
                />
            ) : videos.length === 0 ? (
                <Box mt={4} textAlign="center">
                    <Typography color={colors.grey[300]}>
                        This channel has no data
                    </Typography>
                </Box>
            ) : (
                <>
                    <RealtimeSection
                        sectionSx={sectionSx}
                        chartCardSx={chartCardSx}
                        chartTooltipStyles={chartTooltipStyles}
                        dashboardPalette={dashboardPalette}
                        realtime48h={realtime48h}
                        realtime60m={realtime60m}
                    />

                    <Box
                        mt={2}
                        sx={{
                            display: "grid",
                            gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
                            gap: 2,
                            width: "100%",
                        }}
                    >
                        <SubscribersOverviewSection
                            rangeLabel={rangeLabel}
                            sectionSx={sectionSx}
                            statCardSx={statCardSx}
                            chartCardSx={chartCardSx}
                            subscribersSeries={subscribersSeries}
                            subscribersSummary={subscribersSummary}
                            pctColor={pctColor}
                            formatPct={formatPct}
                            subscribersXAxisTicks={subscribersXAxisTicks}
                            chartTooltipStyles={chartTooltipStyles}
                            dashboardPalette={dashboardPalette}
                        />

                        <RevenueOverviewSection
                            rangeLabel={rangeLabel}
                            sectionSx={sectionSx}
                            revenueRows={revenueRows}
                            revenueMetricCards={revenueMetricCards}
                            revenueChartData={revenueChartData}
                            revenueXAxisTicks={revenueXAxisTicks}
                            chartTooltipStyles={chartTooltipStyles}
                            dashboardPalette={dashboardPalette}
                        />
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
                        <MetricProgressSection
                            title="Top 10 keywords by views"
                            rangeLabel={rangeLabel}
                            items={topKeywords}
                            labelKey="keyword"
                            valueKey="views"
                            maxValue={topKeywordMax}
                            animateBars={animateOverviewBars}
                            gradient={`linear-gradient(90deg, ${dashboardPalette.warning}, ${dashboardPalette.warningSoft})`}
                            canLoadMore={canLoadMoreKeywords}
                            onLoadMore={() =>
                                setKeywordLimit((prev) =>
                                    Math.min(prev + OVERVIEW_LIMIT_STEP, OVERVIEW_LIMIT_MAX)
                                )
                            }
                            sectionSx={sectionSx}
                            actionButtonSx={actionButtonSx}
                        />

                        <MetricProgressSection
                            title="Top 10 sources by views"
                            rangeLabel={rangeLabel}
                            items={topSources}
                            labelKey="source"
                            valueKey="views"
                            maxValue={topSourceMax}
                            animateBars={animateOverviewBars}
                            gradient={`linear-gradient(90deg, ${dashboardPalette.positive}, ${dashboardPalette.info})`}
                            canLoadMore={canLoadMoreSources}
                            onLoadMore={() =>
                                setSourceLimit((prev) =>
                                    Math.min(prev + OVERVIEW_LIMIT_STEP, OVERVIEW_LIMIT_MAX)
                                )
                            }
                            sectionSx={sectionSx}
                            actionButtonSx={actionButtonSx}
                        />

                        <CountryOverviewSection
                            rangeLabel={rangeLabel}
                            sectionSx={sectionSx}
                            countryViews={countryViews}
                            countryMapData={countryMapData}
                            countryDomainMax={countryDomainMax}
                            countryResolvers={countryResolvers}
                            topCountries={topCountries}
                            dashboardPalette={dashboardPalette}
                            geoFeatures={geoFeatures}
                        />
                    </Box>

                    <LatestVideosSection
                        sectionSx={sectionSx}
                        latestVideos={latestVideos}
                        visibleLatestVideos={visibleLatestVideos}
                        latestVisibleCount={visibleLatestVideos.length}
                        canLoadMoreLatestVideos={canLoadMoreLatestVideos}
                        canCollapseLatestVideos={canCollapseLatestVideos}
                        onLoadMore={() =>
                            setLatestVisibleCount((current) =>
                                Math.min(current + LATEST_VIDEOS_PAGE_SIZE, latestVideos.length)
                            )
                        }
                        onCollapse={() => setLatestVisibleCount(LATEST_VIDEOS_PAGE_SIZE)}
                        latestRowSx={latestRowSx}
                        isDark={isDark}
                        dashboardPalette={dashboardPalette}
                    />
                </>
            )}
        </Box>
    );
};

export default DashboardContainer;
