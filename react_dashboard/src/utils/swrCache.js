// Simple stale-while-revalidate cache backed by localStorage.
// Usage: readSwrCache(endpoint, payload) → cached data or null
//        writeSwrCache(endpoint, payload, data)

const PREFIX = "swr.";
const DEFAULT_MAX_AGE_MS = 60 * 60 * 1000; // 1 hour

const makeKey = (endpoint, payload) => {
    try {
        return PREFIX + endpoint + ":" + JSON.stringify(payload);
    } catch {
        return PREFIX + endpoint + ":?";
    }
};

export const readSwrCache = (endpoint, payload, maxAgeMs = DEFAULT_MAX_AGE_MS) => {
    if (typeof window === "undefined") return null;
    try {
        const raw = window.localStorage.getItem(makeKey(endpoint, payload));
        if (!raw) return null;
        const entry = JSON.parse(raw);
        if (!entry || typeof entry.ts !== "number") return null;
        if (Date.now() - entry.ts > maxAgeMs) return null;
        return entry.data;
    } catch {
        return null;
    }
};

export const writeSwrCache = (endpoint, payload, data) => {
    if (typeof window === "undefined") return;
    try {
        const key = makeKey(endpoint, payload);
        window.localStorage.setItem(
            key,
            JSON.stringify({ ts: Date.now(), data })
        );
    } catch {
        // quota exceeded or serialization failure — best-effort cache only
    }
};
