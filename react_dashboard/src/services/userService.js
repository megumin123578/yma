import api from "./api";

export const uploadAvatar = (file) => {
  const formData = new FormData();
  formData.append("avatar", file);

  return api.post("/api/users/avatar", formData);
};

export const getMe = () => {
  return api.get("/api/users/me");
};