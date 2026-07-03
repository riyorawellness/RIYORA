import api from "@/lib/api";

export const adminApi = {
  // Dashboard
  overview: () => api.get("/admin/dashboard/overview").then((r) => r.data),
  revenueSeries: (days = 30) =>
    api.get("/admin/dashboard/revenue-series", { params: { days } }).then((r) => r.data),
  topPrograms: (limit = 5) =>
    api.get("/admin/dashboard/top-programs", { params: { limit } }).then((r) => r.data),
  topReferrers: (limit = 5) =>
    api.get("/admin/dashboard/top-referrers", { params: { limit } }).then((r) => r.data),
  recentActivity: (limit = 20) =>
    api.get("/admin/dashboard/recent-activity", { params: { limit } }).then((r) => r.data),
  recentTransactions: (limit = 10) =>
    api.get("/admin/dashboard/recent-transactions", { params: { limit } }).then((r) => r.data),

  // Users
  listUsers: (params) => api.get("/admin/users", { params }).then((r) => r.data),
  getUser: (mid) => api.get(`/admin/users/${mid}`).then((r) => r.data),
  updateUser: (mid, body) => api.patch(`/admin/users/${mid}`, body).then((r) => r.data),
  updateUserStatus: (mid, body) =>
    api.patch(`/admin/users/${mid}/status`, body).then((r) => r.data),
  resetUserPassword: (mid, new_password) =>
    api.post(`/admin/users/${mid}/reset-password`, { new_password }).then((r) => r.data),
  exportUsersBlob: () =>
    api.get("/admin/users/export", { responseType: "blob" }).then((r) => r.data),

  // CMS
  cmsList: () => api.get("/admin/cms/pages").then((r) => r.data),
  cmsGet: (slug) => api.get(`/admin/cms/pages/${slug}`).then((r) => r.data),
  cmsUpsert: (slug, body) =>
    api.put(`/admin/cms/pages/${slug}`, body).then((r) => r.data),
  cmsVersions: (slug) =>
    api.get(`/admin/cms/pages/${slug}/versions`).then((r) => r.data),

  // System / Security
  getSystem: () => api.get("/admin/system/settings").then((r) => r.data),
  updateSystem: (body) => api.put("/admin/system/settings", body).then((r) => r.data),
  getSecurity: () => api.get("/admin/security/settings").then((r) => r.data),
  updateSecurity: (body) => api.put("/admin/security/settings", body).then((r) => r.data),

  // Audit
  auditLog: (params) => api.get("/admin/audit-log", { params }).then((r) => r.data),

  // Banners
  banners: () => api.get("/admin/banners").then((r) => r.data),
  createBanner: (body) => api.post("/admin/banners", body).then((r) => r.data),
  updateBanner: (id, body) => api.put(`/admin/banners/${id}`, body).then((r) => r.data),
  deleteBanner: (id) => api.delete(`/admin/banners/${id}`).then((r) => r.data),

  // Notifications
  sendNotification: (body) => api.post("/admin/notifications", body).then((r) => r.data),
  notificationHistory: () =>
    api.get("/admin/notifications").then((r) => r.data),

  // Uploads
  upload: (file) => {
    const form = new FormData();
    form.append("file", file);
    return api
      .post("/admin/uploads", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },
  listUploads: () => api.get("/admin/uploads").then((r) => r.data),
  deleteUpload: (id) => api.delete(`/admin/uploads/${id}`).then((r) => r.data),
};
