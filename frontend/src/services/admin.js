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

  // Danger Zone
  emptyAppData: (confirmation, admin_password) =>
    api
      .post("/admin/danger/empty-app-data", { confirmation, admin_password })
      .then((r) => r.data),
  softDeleteUser: (mid, confirmation, options = {}, admin_password = null) =>
    api
      .delete(`/admin/danger/users/${mid}`, {
        data: { confirmation, admin_password, ...options },
      })
      .then((r) => r.data),

  // Backups
  listBackups: () => api.get("/admin/backups").then((r) => r.data),
  createBackup: (admin_password, reason) =>
    api
      .post("/admin/backups/create", { admin_password, reason })
      .then((r) => r.data),
  restoreBackup: (filename, admin_password) =>
    api
      .post(`/admin/backups/${filename}/restore`, { admin_password })
      .then((r) => r.data),
  deleteBackup: (filename, admin_password) =>
    api
      .delete(`/admin/backups/${filename}`, { data: { admin_password } })
      .then((r) => r.data),

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

  // Admin profile
  changeMyPassword: (old_password, new_password) =>
    api
      .post("/admin/change-password", { old_password, new_password })
      .then((r) => r.data),

  // Programs (admin ops go through /api/programs/admin*)
  listPrograms: (params = {}) => api.get("/programs", { params }).then((r) => r.data),
  getProgram: (id) => api.get(`/programs/${id}`).then((r) => r.data),
  createProgram: (body) => api.post("/programs/admin", body).then((r) => r.data),
  updateProgram: (id, body) => api.put(`/programs/admin/${id}`, body).then((r) => r.data),
  activateProgram: (id) => api.post(`/programs/admin/${id}/activate`).then((r) => r.data),
  deactivateProgram: (id) => api.post(`/programs/admin/${id}/deactivate`).then((r) => r.data),
  deleteProgram: (id) => api.delete(`/programs/admin/${id}`).then((r) => r.data),

  // Modules
  listModules: (params = {}) => api.get("/modules", { params }).then((r) => r.data),
  getModule: (id) => api.get(`/modules/${id}`).then((r) => r.data),
  createModule: (body) => api.post("/modules/admin", body).then((r) => r.data),
  updateModule: (id, body) => api.put(`/modules/admin/${id}`, body).then((r) => r.data),
  deleteModule: (id) => api.delete(`/modules/admin/${id}`).then((r) => r.data),

  // Program Categories
  listCategories: (params = {}) => api.get("/categories", { params }).then((r) => r.data),
  createCategory: (body) => api.post("/categories/admin", body).then((r) => r.data),
  updateCategory: (id, body) => api.put(`/categories/admin/${id}`, body).then((r) => r.data),
  deleteCategory: (id) => api.delete(`/categories/admin/${id}`).then((r) => r.data),
};
