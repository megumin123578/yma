const normalizeConfigValue = (value) => {
  const normalized = String(value || "").trim();
  if (!normalized || /^%VITE_[A-Z0-9_]+%$/.test(normalized)) return "";
  return normalized.replace(/\/$/, "");
};

const resolveRuntimeApiBase = () => {
  const envApiUrl = normalizeConfigValue(import.meta.env.VITE_API_URL);
  if (envApiUrl) return envApiUrl;

  const runtimeApiUrl = normalizeConfigValue(
    typeof window !== "undefined" ? window.__APP_CONFIG__?.API_BASE : ""
  );
  if (runtimeApiUrl) return runtimeApiUrl;

  return "";
};

const resolveRuntimeSpreadsheetId = () => {
  const envSpreadsheetId = normalizeConfigValue(import.meta.env.VITE_SPREADSHEET_ID);
  if (envSpreadsheetId) return envSpreadsheetId;

  if (
    typeof window !== "undefined" &&
    window.__SPREADSHEET_ID__
  ) {
    return window.__SPREADSHEET_ID__;
  }

  return "";
};

export const getApiBase = () => {
  const resolvedOrigin =
    typeof window !== "undefined" && window.location?.origin
      ? window.location.origin
      : "http://localhost:3001";

  return (
    resolveRuntimeApiBase() ||
    resolvedOrigin
  );
};

export const API_BASE = getApiBase();

export const SHEET_ENDPOINT =
  normalizeConfigValue(import.meta.env.VITE_SHEET_ENDPOINT) ||
  "/api/sheet/append";

export const SPREADSHEET_ID = resolveRuntimeSpreadsheetId();

export const resolveApiAssetUrl = (value) => {
  if (!value) return "";
  const rawValue = String(value);
  if (/^(blob:|data:|https?:\/\/)/i.test(rawValue)) return rawValue;
  const base = (getApiBase() || "").replace(/\/$/, "");
  const path = rawValue.startsWith("/") ? rawValue : `/${rawValue}`;
  return `${base}${path}`;
};
