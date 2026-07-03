import api from "@/lib/api";

export const analyticsApi = {
  // Admin
  kpis: (params = {}) => api.get("/analytics/kpis", { params }).then((r) => r.data),
  revenue: (params = {}) => api.get("/analytics/revenue", { params }).then((r) => r.data),
  programs: (params = {}) => api.get("/analytics/programs", { params }).then((r) => r.data),
  states: (params = {}) => api.get("/analytics/states", { params }).then((r) => r.data),
  userGrowth: (params = {}) => api.get("/analytics/user-growth", { params }).then((r) => r.data),
  commissions: (params = {}) => api.get("/analytics/commissions", { params }).then((r) => r.data),
  leaderboard: (params = {}) => api.get("/analytics/leaderboard", { params }).then((r) => r.data),
  subscriptions: () => api.get("/analytics/subscriptions").then((r) => r.data),
  gst: (params = {}) => api.get("/analytics/gst", { params }).then((r) => r.data),
  dashboard: (params = {}) => api.get("/analytics/dashboard", { params }).then((r) => r.data),

  // User
  me: (params = {}) => api.get("/analytics/me", { params }).then((r) => r.data),
};

export const adminReportsApi = {
  list: (report_type, params = {}) =>
    api.get(`/admin/reports/${report_type}`, { params }).then((r) => r.data),
  exportBlob: (report_type, fmt, params = {}) =>
    api
      .get(`/admin/reports/${report_type}/export`, {
        params: { fmt, ...params },
        responseType: "blob",
      })
      .then((r) => r.data),
};

export const userReportsApi = {
  downloadReport: (type, fmt = "pdf") =>
    api
      .get(`/reports/${type}`, { params: { fmt }, responseType: "blob" })
      .then((r) => r.data),
};

/** Trigger a browser download from a blob. */
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
