import axios from "axios";
import { getApiBaseUrl } from "@/config/runtime";

export const platformTokenKey = "indian-servers-platform-token";
export const platformApi = axios.create({baseURL: getApiBaseUrl(), timeout: 60000});
platformApi.interceptors.request.use(config => {
  const token = sessionStorage.getItem(platformTokenKey);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
platformApi.interceptors.response.use(response => response, error => {
  if (error.response?.status === 401) {
    sessionStorage.removeItem(platformTokenKey);
    if (window.location.pathname !== "/platform/login") window.location.assign("/platform/login");
  }
  return Promise.reject(error);
});
