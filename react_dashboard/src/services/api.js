import axios from "axios";
import { API_BASE, getApiBase } from "../config";

const api = axios.create({
  baseURL: API_BASE,
});

const perfCallCounts = new Map();
const perfLastCallAt = new Map();
const PERF_REPEAT_WINDOW_MS = 3000;

const buildPerfKey = (response, detail) => {
  const method = String(
    detail?.method || response?.config?.method || "GET"
  ).toUpperCase();
  const url = String(response?.config?.url || detail?.path || "");
  const params = response?.config?.params;
  const query =
    params && typeof URLSearchParams !== "undefined"
      ? new URLSearchParams(params).toString()
      : "";
  return query ? `${method} ${url}?${query}` : `${method} ${url}`;
};

const nextPerfCallInfo = (key) => {
  const now =
    typeof performance !== "undefined" && typeof performance.now === "function"
      ? performance.now()
      : Date.now();
  const count = (perfCallCounts.get(key) || 0) + 1;
  const previousAt = perfLastCallAt.get(key) || 0;
  perfCallCounts.set(key, count);
  perfLastCallAt.set(key, now);
  return {
    count,
    isFastRepeat: count > 1 && now - previousAt <= PERF_REPEAT_WINDOW_MS,
  };
};

api.interceptors.request.use((config) => {
  const runtimeBase = getApiBase();
  config.baseURL = runtimeBase;
  const pageIsHttps =
    typeof window !== "undefined" && window.location?.protocol === "https:";
  if (
    pageIsHttps &&
    typeof config.url === "string" &&
    config.url.startsWith("http://")
  ) {
    config.url = config.url.replace(/^http:\/\//, "https://");
  }
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

const logPerfHeader = (response) => {
  try {
    const encoded = response?.headers?.["x-perf-log"];
    if (!encoded) return;
    const detail = JSON.parse(atob(encoded));
    const total = detail.total_ms ?? 0;
    const perfKey = buildPerfKey(response, detail);
    const { count, isFastRepeat } = nextPerfCallInfo(perfKey);
    const repeatLabel = isFastRepeat ? " repeat" : "";
    const color =
      total > 500 ? "color:#ef4444" : total > 200 ? "color:#f59e0b" : "color:#22c55e";
    console.groupCollapsed(
      `%c[perf #${count}${repeatLabel}] ${detail.method} ${detail.path} %c${total.toFixed(1)}ms`,
      "color:#94a3b8",
      `${color};font-weight:bold`
    );
    (detail.lines || []).forEach((line) => console.log(line));
    console.groupEnd();
  } catch {
    // ignore decoding errors
  }
};

api.interceptors.response.use(
  (response) => {
    logPerfHeader(response);
    return response;
  },
  (error) => {
    if (error?.response) logPerfHeader(error.response);
    return Promise.reject(error);
  }
);

export default api;
