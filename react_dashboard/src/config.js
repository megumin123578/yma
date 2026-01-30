const resolveRuntimeApiBase = () => {
  if (process.env.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL;
  }
  if (
    typeof window !== "undefined" &&
    window.__APP_CONFIG__ &&
    window.__APP_CONFIG__.API_BASE
  ) {
    return window.__APP_CONFIG__.API_BASE;
  }
  return "";
};

export const getApiBase = () => {
  const resolvedHost =
    typeof window !== "undefined" && window.location?.hostname
      ? window.location.hostname
      : "localhost";
  const resolvedProtocol =
    typeof window !== "undefined" && window.location?.protocol
      ? window.location.protocol
      : "http:";

  // Hardcode for production to ensure using the correct HTTPS endpoint
  // and avoid Mixed Content errors if configuration is stale/incorrect
  if (resolvedHost === "app.tuanfmcaa.site") {
    return "https://api.tuanfmcaa.site";
  }

  return (
    resolveRuntimeApiBase() ||
    `${resolvedProtocol}//${resolvedHost}`
  );
};

export const API_BASE = getApiBase();
