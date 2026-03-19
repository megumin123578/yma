const SHARED_CHANNEL_STORAGE_KEY = "shared.selectedChannelId";
const SHARED_CHANNEL_EVENT = "shared-channel-change";

export const getSharedChannelStorageKey = () => SHARED_CHANNEL_STORAGE_KEY;

export const getStoredSharedChannelId = (...fallbackKeys) => {
  if (typeof window === "undefined") return "";
  try {
    const sharedValue = window.localStorage.getItem(SHARED_CHANNEL_STORAGE_KEY);
    if (sharedValue) return sharedValue;
    for (const key of fallbackKeys) {
      if (!key) continue;
      const value = window.localStorage.getItem(key);
      if (value) return value;
    }
  } catch {
    return "";
  }
  return "";
};

export const setStoredSharedChannelId = (value, ...legacyKeys) => {
  if (typeof window === "undefined") return;
  try {
    const nextValue = value ? String(value) : "";
    if (nextValue) {
      window.localStorage.setItem(SHARED_CHANNEL_STORAGE_KEY, nextValue);
    } else {
      window.localStorage.removeItem(SHARED_CHANNEL_STORAGE_KEY);
    }
    legacyKeys.forEach((key) => {
      if (!key) return;
      if (nextValue) {
        window.localStorage.setItem(key, nextValue);
      } else {
        window.localStorage.removeItem(key);
      }
    });
    window.dispatchEvent(
      new CustomEvent(SHARED_CHANNEL_EVENT, {
        detail: { value: nextValue },
      })
    );
  } catch {
    // ignore storage errors
  }
};

export const listenSharedChannelId = (callback) => {
  if (typeof window === "undefined" || typeof callback !== "function") {
    return () => {};
  }

  const onCustomEvent = (event) => {
    callback(event?.detail?.value || "");
  };

  const onStorage = (event) => {
    if (event.key === SHARED_CHANNEL_STORAGE_KEY) {
      callback(event.newValue || "");
    }
  };

  window.addEventListener(SHARED_CHANNEL_EVENT, onCustomEvent);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(SHARED_CHANNEL_EVENT, onCustomEvent);
    window.removeEventListener("storage", onStorage);
  };
};
