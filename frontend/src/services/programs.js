import api from "@/lib/api";

export const programsApi = {
  list: (params = {}) => api.get("/programs", { params }).then((r) => r.data),
  get: (id) => api.get(`/programs/${id}`).then((r) => r.data),
  dashboard: () => api.get("/programs/me/dashboard").then((r) => r.data),
  status: (id) => api.get(`/programs/${id}/status`).then((r) => r.data),
  eligibility: (id) => api.get(`/programs/${id}/eligibility`).then((r) => r.data),
  modulesByProgram: (id) =>
    api.get(`/modules/me/by-program/${id}`).then((r) => r.data),
  continueLearning: () =>
    api.get("/programs/me/continue-learning").then((r) => r.data),
};
