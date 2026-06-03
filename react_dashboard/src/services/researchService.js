// services/researchService.js — API nghiên cứu ngách (Phase 4)
import api from "./api";
import { subscribeSSE } from "./sse";

export const listWatchlists = async () => {
  const { data } = await api.get("/api/research/watchlists");
  return data?.items || [];
};

export const getReport = async (wid, { refresh = false } = {}) => {
  const { data } = await api.get(`/api/research/report/${wid}`, {
    params: refresh ? { refresh: true } : undefined,
  });
  return data;
};

export const startRun = async ({ wlIds = null, resume = null } = {}) => {
  const { data } = await api.post("/api/research/run", { wlIds, resume });
  return data;
};

export const getRun = async (runId) => {
  const { data } = await api.get(`/api/research/run/${runId}`);
  return data;
};

export const stopRun = async (runId) => {
  const { data } = await api.post(`/api/research/run/${runId}/stop`);
  return data;
};

// Sinh (lại) AI cho 1 watchlist (không monitor). Trả {runId, pid}.
export const generateAi = async (wid) => {
  const { data } = await api.post(`/api/research/report/${wid}/ai`);
  return data;
};

// Báo cáo SEO (Claude CLI). Trả {items, selected, generating}.
export const getSeoReports = async (wid, id = "") => {
  const { data } = await api.get(`/api/research/report/${wid}/seo`, {
    params: id ? { id } : undefined,
  });
  return data;
};

// Sinh báo cáo SEO mới (nền). Trả {status}.
export const generateSeoReport = async (wid) => {
  const { data } = await api.post(`/api/research/report/${wid}/seo`);
  return data;
};

// ----- Quản lý watchlist + kênh (Settings/Channel) -----
export const createWatchlist = async (name, description = "") => {
  const { data } = await api.post("/api/research/watchlists", { name, description });
  return data;
};

export const patchWatchlist = async (wid, patch) => {
  const { data } = await api.patch(`/api/research/watchlists/${wid}`, patch);
  return data;
};

export const removeChannel = async (wid, cid) => {
  const { data } = await api.delete(`/api/research/watchlists/${wid}/channels/${cid}`);
  return data;
};

// ----- Config + Scheduler -----
export const getConfig = async () => {
  const { data } = await api.get("/api/research/config");
  return data;
};

export const putConfig = async (values) => {
  const { data } = await api.put("/api/research/config", { values });
  return data;
};

// 1 list thống nhất: tất cả watchlist (kể cả chưa OAuth) + kênh phụ
export const getUnifiedChannels = async () => {
  const { data } = await api.get("/api/research/channels-unified");
  return data?.items || [];
};

export const getSchedule = async () => {
  const { data } = await api.get("/api/research/schedule");
  return data;
};

export const putSchedule = async (patch) => {
  const { data } = await api.put("/api/research/schedule", patch);
  return data;
};

// SSE tiến trình 1 run. Trả hàm hủy.
export const streamRun = (runId, { onMessage, onError } = {}) =>
  subscribeSSE(`/api/research/run/${runId}/stream`, { onMessage, onError });
