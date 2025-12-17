import axios from "axios";

const API_URL = "http://localhost:8000/api/auth";

export const register = (data) =>
  axios.post(`${API_URL}/register`, data);

export const login = async (username, password) => {
  const res = await axios.post(`${API_URL}/login`, {
    username,
    password,
  });

  localStorage.setItem("token", res.data.access_token);
  return res.data;
};

export const logout = () => {
  localStorage.removeItem("token");
};

export const forgot = (username) => {
  return axios.post(`${API_URL}/forgot-password`, {
    username,
  });
}


export const changePassword = async (currentPassword, newPassword) => {
  const token = localStorage.getItem("token");

  const res = await fetch(`${API_URL}/change-password`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Change password failed");
  }

  return res.json();
};
