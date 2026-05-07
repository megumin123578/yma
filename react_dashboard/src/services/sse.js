import { getApiBase } from "../config";

const decoder = new TextDecoder("utf-8");

const buildAbsoluteUrl = (path) => {
  if (/^https?:\/\//i.test(path)) return path;
  const base = (getApiBase() || "").replace(/\/$/, "");
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${base}${suffix}`;
};

const parseEvent = (rawBlock) => {
  let event = "message";
  const dataLines = [];
  for (const line of rawBlock.split("\n")) {
    if (!line || line.startsWith(":")) continue;
    const idx = line.indexOf(":");
    const field = idx === -1 ? line : line.slice(0, idx);
    const value = idx === -1 ? "" : line.slice(idx + 1).replace(/^ /, "");
    if (field === "event") event = value;
    else if (field === "data") dataLines.push(value);
  }
  if (!dataLines.length) return null;
  const data = dataLines.join("\n");
  let parsed = data;
  try {
    parsed = JSON.parse(data);
  } catch {
    // keep raw string
  }
  return { event, data: parsed };
};

export const subscribeSSE = (path, options = {}) => {
  const {
    onMessage,
    onError,
    onOpen,
    signal: externalSignal,
    reconnectDelayMs = 2000,
    maxReconnectDelayMs = 30000,
  } = options;

  const controller = new AbortController();
  if (externalSignal) {
    if (externalSignal.aborted) controller.abort();
    else externalSignal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  let attempt = 0;
  let stopped = false;

  const run = async () => {
    while (!stopped && !controller.signal.aborted) {
      try {
        const token = localStorage.getItem("access_token");
        const headers = { Accept: "text/event-stream" };
        if (token) headers.Authorization = `Bearer ${token}`;

        const response = await fetch(buildAbsoluteUrl(path), {
          method: "GET",
          headers,
          signal: controller.signal,
          credentials: "include",
        });

        if (!response.ok || !response.body) {
          throw new Error(`SSE request failed: ${response.status}`);
        }

        attempt = 0;
        onOpen?.();

        const reader = response.body.getReader();
        let buffer = "";

        while (!stopped && !controller.signal.aborted) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          let sepIdx;
          while ((sepIdx = buffer.indexOf("\n\n")) !== -1) {
            const block = buffer.slice(0, sepIdx);
            buffer = buffer.slice(sepIdx + 2);
            const parsed = parseEvent(block);
            if (parsed && onMessage) onMessage(parsed);
          }
        }
      } catch (err) {
        if (controller.signal.aborted || stopped) return;
        onError?.(err);
      }

      if (stopped || controller.signal.aborted) return;
      attempt += 1;
      const delay = Math.min(reconnectDelayMs * 2 ** Math.min(attempt - 1, 4), maxReconnectDelayMs);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  };

  run();

  return () => {
    stopped = true;
    controller.abort();
  };
};
