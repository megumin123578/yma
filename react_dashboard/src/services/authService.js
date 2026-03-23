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

// ================= CHANGE PASSWORD =================
export const changePassword = async (currentPassword, newPassword) => {
  const res = await api.post(`${API_URL}/change-password`, {
    current_password: currentPassword,
    new_password: newPassword,
  });
  return res.data;
};

export const listPasswordChangeRequests = async () => {
  const res = await api.get(`${API_URL}/password-change-requests`);
  return res.data;
};

export const approvePasswordChangeRequest = async (requestId) => {
  const res = await api.post(`${API_URL}/password-change-requests/${requestId}/approve`);
  return res.data;
};

export const rejectPasswordChangeRequest = async (requestId) => {
  const res = await api.post(`${API_URL}/password-change-requests/${requestId}/reject`);
  return res.data;
};
