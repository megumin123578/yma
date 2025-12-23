const resolvedHost =
  typeof window !== "undefined" && window.location?.hostname
    ? window.location.hostname
    : "localhost";

export const API_BASE =
  process.env.REACT_APP_API_BASE || `http://${resolvedHost}:8000`;
