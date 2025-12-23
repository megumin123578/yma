import axios from "axios";
import api from "./api";
import { API_BASE } from "../config";

const API_URL = `${API_BASE}/api/auth`;

// ================= REGISTER =================
export const register = (data) => {
  return axios.post(`${API_URL}/register`, data);
};

// ================= LOGIN =================
export const login = async (username, password) => {
  const res = await api.post(`${API_URL}/login`, {
    username,
    password,
  });

  localStorage.setItem("access_token", res.data.access_token);
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

export const resetPassword = (username, newPassword) => {
  return axios.post(`${API_URL}/reset-password`, {
    username,
    new_password: newPassword,
  });
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
