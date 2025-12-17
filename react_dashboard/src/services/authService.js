import axios from "axios";

const API_URL = "http://localhost:8000/api/auth";

// ================= REGISTER =================
export const register = (data) => {
  return axios.post(`${API_URL}/register`, data);
};

// ================= LOGIN =================
export const login = async (username, password) => {
  const res = await axios.post(`${API_URL}/login`, {
    username,
    password,
  });

  //  DÙNG 1 KEY DUY NHẤT
  localStorage.setItem("access_token", res.data.access_token);

  // Nếu backend có trả user thì lưu luôn
  if (res.data.user) {
    localStorage.setItem("userProfile", JSON.stringify(res.data.user));
  }

  return res.data;
};

// ================= LOGOUT =================
export const logout = () => {
  localStorage.removeItem("access_token");
  localStorage.removeItem("userProfile");
};

// ================= FORGOT PASSWORD =================
export const forgot = (username) => {
  return axios.post(`${API_URL}/forgot-password`, { username });
};

// ================= CHANGE PASSWORD =================
export const changePassword = async (currentPassword, newPassword) => {
  const token = localStorage.getItem("access_token");

  if (!token) {
    throw new Error("Not authenticated");
  }

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
