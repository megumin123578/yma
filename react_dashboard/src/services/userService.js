import api from "./api";

export const uploadAvatar = (file) => {
  const formData = new FormData();
  formData.append("avatar", file);

  return api.post("/users/avatar", formData);
};
