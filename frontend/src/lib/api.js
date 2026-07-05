import axios from "axios";

import {
  clearRoleTokens,
  getAccessToken,
  getRefreshToken,
  roleForRequestUrl,
  setTokens,
} from "@/lib/tokenStore";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

const api = axios.create({ baseURL: API_BASE, timeout: 20000 });

// Attach the correct role's access token based on request URL.
api.interceptors.request.use((cfg) => {
  const role = roleForRequestUrl(cfg.url || "");
  const token = getAccessToken(role);
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  // Remember which role owned this request — the response interceptor
  // needs it to refresh the RIGHT token pair on 401.
  cfg._rwRole = role;
  return cfg;
});

// Auto-refresh access token on 401 using the stored refresh token for the
// SAME role that made the request. Keyed per role so parallel admin+user
// refreshes don't share a promise (which would swap their tokens).
const refreshPromises = { admin: null, user: null };
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config || {};
    const status = error.response?.status;
    const url = original.url || "";
    const isAuthCall =
      url.includes("/auth/refresh") ||
      url.includes("/auth/login") ||
      url.includes("/auth/register") ||
      url.includes("/admin/login");

    if (status === 401 && !original._retry && !isAuthCall) {
      const role = original._rwRole || roleForRequestUrl(url);
      const refresh = getRefreshToken(role);
      if (!refresh) return Promise.reject(error);
      original._retry = true;
      try {
        refreshPromises[role] =
          refreshPromises[role] ||
          axios.post(`${API_BASE}/auth/refresh`, { refresh_token: refresh });
        const { data } = await refreshPromises[role];
        refreshPromises[role] = null;
        setTokens(role, data);
        original.headers.Authorization = `Bearer ${data.access_token}`;
        return api(original);
      } catch (e) {
        refreshPromises[role] = null;
        clearRoleTokens(role);
      }
    }
    return Promise.reject(error);
  }
);

export const formatApiError = (err, fallback = "Something went wrong.") => {
  const d = err?.response?.data?.detail;
  if (!d) return err?.message || fallback;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => e?.msg || JSON.stringify(e)).join("; ");
  if (typeof d === "object" && d.msg) return d.msg;
  return fallback;
};

export default api;
