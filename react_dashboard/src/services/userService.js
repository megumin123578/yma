import api from "./api";

const mapUser = (data) => {
  if (!data) return null;

  return {
    ...data,
    // Normalize fields so the UI always has what it expects
    avatar: data.avatar ?? data.avatar_url ?? null,
    name: data.name ?? data.username ?? "",
  };
};

export const uploadAvatar = (file) => {
  const formData = new FormData();
  formData.append("avatar", file);

  return api.post("/api/users/avatar", formData);
};

export const getMe = async () => {
  const res = await api.get("/api/users/me");
  return mapUser(res.data);
};
