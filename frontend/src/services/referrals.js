import api from "@/lib/api";

const APP_URL = () => window.location.origin;

export const referralsApi = {
  dashboard: () =>
    api
      .get("/referrals/dashboard", { params: { app_url: APP_URL() } })
      .then((r) => r.data),

  shareQR: () =>
    api
      .get("/referrals/share/qr", { params: { app_url: APP_URL(), format: "dataurl" } })
      .then((r) => r.data),

  team: (level) =>
    api.get("/referrals/team", { params: { level } }).then((r) => r.data),

  adminGetSettings: () =>
    api.get("/referrals/admin/settings").then((r) => r.data),
  adminUpdateSettings: (payload) =>
    api.put("/referrals/admin/settings", payload).then((r) => r.data),
};

export const activityApi = {
  meter: () => api.get("/activity/meter").then((r) => r.data),
  logSession: (payload = { source: "manual" }) =>
    api.post("/activity/session", payload).then((r) => r.data),
  sessions: () => api.get("/activity/sessions/me").then((r) => r.data),
  generateReminders: () =>
    api.post("/activity/reminders/generate").then((r) => r.data),
};

export const commissionsApi = {
  summary: () => api.get("/commissions/me/summary").then((r) => r.data),
  list: (params = {}) =>
    api.get("/commissions/me", { params }).then((r) => r.data),

  adminList: (params = {}) =>
    api.get("/commissions/admin", { params }).then((r) => r.data),
  adminSummary: () =>
    api.get("/commissions/admin/summary").then((r) => r.data),
  adminApprove: (id, reason) =>
    api.post(`/commissions/admin/${id}/approve`, { reason }).then((r) => r.data),
  adminReject: (id, reason) =>
    api.post(`/commissions/admin/${id}/reject`, { reason }).then((r) => r.data),
  adminBulkApprove: (ids) =>
    api.post("/commissions/admin/bulk-approve", { ids }).then((r) => r.data),
};

export const payoutsApi = {
  myPayouts: (params = {}) =>
    api.get("/payouts/me", { params }).then((r) => r.data),

  adminList: (params = {}) =>
    api.get("/payouts/admin", { params }).then((r) => r.data),
  adminPendingByUser: () =>
    api.get("/payouts/admin/pending-by-user").then((r) => r.data),
  adminCreate: (payload) =>
    api.post("/payouts/admin", payload).then((r) => r.data),
  adminMarkPaid: (id, payload) =>
    api.post(`/payouts/admin/${id}/mark-paid`, payload).then((r) => r.data),
  adminCancel: (id) =>
    api.post(`/payouts/admin/${id}/cancel`).then((r) => r.data),
};

export const reportsApi = {
  downloadReport: (type) =>
    api
      .get(`/reports/${type}`, { responseType: "blob" })
      .then((r) => r.data),
};
