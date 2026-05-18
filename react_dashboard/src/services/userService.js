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

export const uploadCredentials = () => {
  return api
    .post("/api/users/credentials")
    .then((res) => res.data);
};

export const startMailOAuth = (payload = { label_ids: ["INBOX"] }) => {
  return api
    .post("/api/mail/accounts/oauth/start", payload)
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

export const getMyPermissions = async () => {
  const res = await api.get("/api/users/me/permissions");
  return res.data;
};

export const listRoles = async () => {
  const res = await api.get("/api/users/admin/roles");
  return res.data;
};

export const createRole = async (payload) => {
  const res = await api.post("/api/users/admin/roles", payload);
  return res.data;
};

export const updateRole = async (roleId, payload) => {
  const res = await api.patch(`/api/users/admin/roles/${roleId}`, payload);
  return res.data;
};

export const deleteRole = async (roleId) => {
  const res = await api.delete(`/api/users/admin/roles/${roleId}`);
  return res.data;
};

export const setRolePermissions = async (roleId, permissions) => {
  const res = await api.put(`/api/users/admin/roles/${roleId}/permissions`, {
    permissions,
  });
  return res.data;
};

export const getAdminUserRoles = async (userId) => {
  const res = await api.get(`/api/users/admin/users/${userId}/roles`);
  return res.data;
};

export const setAdminUserRoles = async (userId, roleIds) => {
  const res = await api.put(`/api/users/admin/users/${userId}/roles`, {
    role_ids: roleIds,
  });
  return res.data;
};

export const updateProfile = async (payload) => {
  const res = await api.put("/api/users/profile", payload);
  return mapUser(res.data);
};

export const listAdminUsers = async () => {
  const res = await api.get("/api/users/admin/users");
  return res.data;
};

export const resetAdminUserPassword = async (userId, newPassword) => {
  const res = await api.post(`/api/users/admin/users/${userId}/reset-password`, {
    new_password: newPassword,
  });
  return res.data;
};

export const updateAdminUserRole = async (userId, isAdmin) => {
  const res = await api.post(`/api/users/admin/users/${userId}/admin`, {
    is_admin: isAdmin,
  });
  return res.data;
};

export const getAdminUserAccess = async (userId) => {
  const res = await api.get(`/api/users/admin/users/${userId}/access`);
  return res.data;
};

export const updateAdminUserAccess = async (userId, payload) => {
  const res = await api.put(`/api/users/admin/users/${userId}/access`, payload);
  return res.data;
};

export const deleteAdminUser = async (userId) => {
  const res = await api.delete(`/api/users/admin/users/${userId}`);
  return res.data;
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

export const listTokenProgress = async () => {
  const res = await api.get("/api/users/tokens/progress");
  return res.data;
};

export const runToken = async (tokenName) => {
  const res = await api.post(`/api/users/tokens/${encodeURIComponent(tokenName)}/run`);
  return res.data;
};

export const runAllTokens = async (stage = "") => {
  const payload = stage ? { stage } : {};
  const res = await api.post("/api/users/tokens/run-all", payload);
  return res.data;
};

export const runSelectedTokens = async (tokenNames) => {
  const res = await api.post("/api/users/tokens/run-selected", {
    token_names: tokenNames,
  });
  return res.data;
};

export const runTokenStage = async (tokenName, stage) => {
  const res = await api.post(
    `/api/users/tokens/${encodeURIComponent(tokenName)}/run-stage`,
    { stage }
  );
  return res.data;
};

export const runTokenFullBackfill = async (tokenName) => {
  const res = await api.post(
    `/api/users/tokens/${encodeURIComponent(tokenName)}/run-stage`,
    { stage: "full_backfill" }
  );
  return res.data;
};

export const refreshTokenAvatar = async (tokenName) => {
  const res = await api.post(
    `/api/users/tokens/${encodeURIComponent(tokenName)}/refresh-avatar`
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

export const listTokenProjects = async () => {
  const res = await api.get("/api/users/tokens/projects");
  return res.data;
};

export const createTokenProject = async (projectName) => {
  const res = await api.post("/api/users/tokens/projects", {
    project_name: projectName,
  });
  return res.data;
};

export const renameTokenProject = async (projectName, nextProjectName) => {
  const res = await api.patch(
    `/api/users/tokens/projects/${encodeURIComponent(projectName)}`,
    { project_name: nextProjectName }
  );
  return res.data;
};

export const deleteTokenProject = async (projectName) => {
  const res = await api.delete(
    `/api/users/tokens/projects/${encodeURIComponent(projectName)}`
  );
  return res.data;
};

export const assignTokenProject = async (tokenName, projectName) => {
  const res = await api.post(`/api/users/tokens/${encodeURIComponent(tokenName)}/project`, {
    project_name: projectName || null,
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

export const getLiveCounterSetting = async () => {
  const res = await api.get("/api/users/app_settings/live_counter");
  return res.data;
};

export const updateLiveCounterSetting = async (payload) => {
  const res = await api.patch("/api/users/app_settings/live_counter", payload);
  return res.data;
};

export const listLatestLiveCounterSnapshots = async () => {
  const res = await api.get("/api/users/app_settings/live_counter/latest");
  return res.data;
};

export const getGoogleApiQuota = async () => {
  const res = await api.get("/api/users/app_settings/google_api_quota");
  return res.data;
};

export const getCronScheduleSetting = async () => {
  const res = await api.get("/api/users/app_settings/cron_schedule");
  return res.data;
};

export const updateCronScheduleSetting = async (payload) => {
  const res = await api.patch("/api/users/app_settings/cron_schedule", payload);
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

export const resumeScheduleRun = async (runId) => {
  const res = await api.post(`/api/users/schedules/runs/${runId}/resume`);
  return res.data;
};
