import api from "./api";

const mapUser = (data) => {
  if (!data) return null;

  return {
    ...data,
    avatar: data.avatar ?? data.avatar_url ?? null,
    name: data.name ?? data.username ?? "",
    smmstore_api_key: data.smmstore_api_key ?? data.smmstoreApiKey ?? "",
  };
};

export const uploadAvatar = (file) => {
  const formData = new FormData();
  formData.append("avatar", file);

  return api.post("/api/users/avatar", formData);
};

export const uploadCredentials = (accountTag) => {
  return api
    .post("/api/users/credentials", { account_tag: accountTag })
    .then((res) => res.data);
};

export const getOAuthState = async (state) => {
  const res = await api.get(`/api/users/credentials/state/${encodeURIComponent(state)}`);
  return res.data;
};

export const getMe = async () => {
  const res = await api.get("/api/users/me");
  return mapUser(res.data);
};

export const updateProfile = async (payload) => {
  const res = await api.put("/api/users/profile", payload);
  return mapUser(res.data);
};

export const listTokens = async () => {
  const res = await api.get("/api/users/tokens");
  return res.data;
};

export const deleteToken = async (tokenName) => {
  const res = await api.delete(`/api/users/tokens/${encodeURIComponent(tokenName)}`);
  return res.data;
};

export const getTokenProgress = async (tokenName) => {
  const res = await api.get(`/api/users/tokens/${encodeURIComponent(tokenName)}/progress`);
  return res.data;
};

export const runToken = async (tokenName) => {
  const res = await api.post(`/api/users/tokens/${encodeURIComponent(tokenName)}/run`);
  return res.data;
};

export const runTokenStage = async (tokenName, stage) => {
  const res = await api.post(
    `/api/users/tokens/${encodeURIComponent(tokenName)}/run-stage`,
    { stage }
  );
  return res.data;
};

export const setTokenVisibility = async (tokenName, hidden) => {
  const res = await api.post("/api/users/tokens/visibility", {
    token: tokenName,
    hidden,
  });
  return res.data;
};


export const listSchedules = async () => {
  const res = await api.get("/api/users/schedules");
  return res.data;
};

export const createSchedule = async (payload) => {
  const res = await api.post("/api/users/schedules", payload);
  return res.data;
};

export const updateSchedule = async (scheduleId, payload) => {
  const res = await api.patch(`/api/users/schedules/${scheduleId}`, payload);
  return res.data;
};

export const deleteSchedule = async (scheduleId) => {
  const res = await api.delete(`/api/users/schedules/${scheduleId}`);
  return res.data;
};

export const listScheduleRuns = async (limit = 10) => {
  const res = await api.get("/api/users/schedules/runs", {
    params: { limit },
  });
  return res.data;
};

export const stopScheduleRun = async (runId) => {
  const res = await api.post(`/api/users/schedules/runs/${runId}/stop`);
  return res.data;
};
