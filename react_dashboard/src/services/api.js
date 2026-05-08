import axios from "axios";
import { API_BASE, getApiBase } from "../config";

const api = axios.create({
  baseURL: API_BASE,
});

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
    const color =
      total > 500 ? "color:#ef4444" : total > 200 ? "color:#f59e0b" : "color:#22c55e";
    console.groupCollapsed(
      `%c[perf] ${detail.method} ${detail.path} %c${total.toFixed(1)}ms`,
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
