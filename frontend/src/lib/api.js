import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

const api = axios.create({ baseURL: API_BASE, timeout: 20000 });

// Attach access token from localStorage
api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem("rw_access_token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

// Auto-refresh access token on 401 using the stored refresh token.
let refreshPromise = null;
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config || {};
    const status = error.response?.status;
    const isAuthCall = original.url?.includes("/auth/") || original.url?.includes("/admin/login");

    if (status === 401 && !original._retry && !isAuthCall) {
      const refresh = localStorage.getItem("rw_refresh_token");
      if (!refresh) return Promise.reject(error);
      original._retry = true;
      try {
        refreshPromise =
          refreshPromise ||
          axios.post(`${API_BASE}/auth/refresh`, { refresh_token: refresh });
        const { data } = await refreshPromise;
        refreshPromise = null;
        localStorage.setItem("rw_access_token", data.access_token);
        localStorage.setItem("rw_refresh_token", data.refresh_token);
        original.headers.Authorization = `Bearer ${data.access_token}`;
        return api(original);
      } catch (e) {
        refreshPromise = null;
        localStorage.removeItem("rw_access_token");
        localStorage.removeItem("rw_refresh_token");
        localStorage.removeItem("rw_role");
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
