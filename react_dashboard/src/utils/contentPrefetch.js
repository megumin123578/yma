import dayjs from "dayjs";
import api from "../services/api";
import { getMonthRange, getRangeForPeriod } from "../components/Module";

const STORAGE_KEY = "content.filters";
const PREFETCH_THROTTLE_MS = 30000;
const lastPrefetchAt = new Map();

const resolvePeriodRange = (period, startDate, endDate) => {
    const now = new Date();
    if (period === "custom") return { start: startDate, end: endDate };
    if (period === "month_current") return getMonthRange(0, now);
    if (period === "month_prev") return getMonthRange(1, now);
    if (period === "year_current") {
        return {
            start: dayjs().startOf("year").format("YYYY-MM-DD"),
            end: dayjs().endOf("year").format("YYYY-MM-DD"),
        };
    }
    if (period === "year_prev") {
        return {
            start: dayjs().subtract(1, "year").startOf("year").format("YYYY-MM-DD"),
            end: dayjs().subtract(1, "year").endOf("year").format("YYYY-MM-DD"),
        };
    }
    const r = getRangeForPeriod(period, now);
    if (period === "lifetime") {
        return {
            start: r.start || "2000-01-01",
            end: r.end || dayjs(now).format("YYYY-MM-DD"),
        };
    }
    return r;
};

const readStoredFilters = () => {
    if (typeof window === "undefined") return null;
    try {
        const raw = window.localStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
};

const fireAndForget = (key, fn) => {
    const now = Date.now();
    const last = lastPrefetchAt.get(key) || 0;
    if (now - last < PREFETCH_THROTTLE_MS) return;
    lastPrefetchAt.set(key, now);
    Promise.resolve()
        .then(fn)
        .catch(() => {
            // best-effort; ignore failures
        });
};

export const prefetchContentPage = ({ forceAllChannels = false } = {}) => {
    const stored = readStoredFilters();
    if (!stored) return;

    const channelId = forceAllChannels ? "__all__" : stored.channelId;
    if (!channelId) return;

    const period = stored.period || "last28";
    const { start, end } = resolvePeriodRange(period, stored.startDate, stored.endDate) || {};
    if (!start || !end) return;

    const contentType = stored.contentType || "all";
    const key = `${channelId}|${start}|${end}|${contentType}`;

    fireAndForget(key, () => {
        api.post("/api/content/list", { start, end, channelId, contentType });
        api.post("/api/content/timeseries", { start, end, channelId, contentType });
    });
};
