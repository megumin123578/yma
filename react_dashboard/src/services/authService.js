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
