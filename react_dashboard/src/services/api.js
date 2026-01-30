import axios from "axios";
import { API_BASE, getApiBase } from "../config";

const api = axios.create({
  baseURL: API_BASE,
});

api.interceptors.request.use((config) => {
  const runtimeBase = getApiBase();
  config.baseURL = runtimeBase;
  if (typeof config.url === "string" && config.url.startsWith("http://")) {
    config.url = config.url.replace(/^http:\/\//, "https://");
  }
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
