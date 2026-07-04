import api from "@/lib/api";

export const manualPaymentsApi = {
  // Public / user
  getMode: () => api.get("/payments/mode").then((r) => r.data),
  getQR: () => api.get("/payments/manual/qr").then((r) => r.data),
  getQuote: (program_id) => api.get("/payments/manual/quote", { params: { program_id } }).then((r) => r.data),
  submit: (payload) => api.post("/payments/manual/submit", payload).then((r) => r.data),
  uploadScreenshot: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.post("/payments/manual/upload-screenshot", fd, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then((r) => r.data);
  },
  myHistory: (params = {}) => api.get("/payments/manual/me", { params }).then((r) => r.data),
  myPending: () => api.get("/payments/manual/pending").then((r) => r.data),

  // Admin
  adminGetSettings: () => api.get("/admin/payments/settings").then((r) => r.data),
  adminPutSettings: (payload) => api.put("/admin/payments/settings", payload).then((r) => r.data),
  adminSetMode: (payment_mode) => api.put("/admin/payments/mode", { payment_mode }).then((r) => r.data),
  adminUploadQR: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.post("/admin/payments/qr", fd, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then((r) => r.data);
  },
  adminDeleteQR: () => api.delete("/admin/payments/qr").then((r) => r.data),
  adminList: (params = {}) => api.get("/admin/payments/manual", { params }).then((r) => r.data),
  adminSummary: () => api.get("/admin/payments/manual/summary").then((r) => r.data),
  adminAction: (id, action, extras = {}) =>
    api.post(`/admin/payments/manual/${id}/action`, { action, ...extras }).then((r) => r.data),
};

/** Resolve a stored /api/uploads/screenshot/... URL to an absolute URL for <img>. */
export function resolveUploadUrl(url) {
  if (!url) return null;
  if (url.startsWith("http")) return url;
  return `${process.env.REACT_APP_BACKEND_URL}${url}`;
}
