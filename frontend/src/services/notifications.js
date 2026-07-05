import api from "@/lib/api";

/**
 * User + admin notifications API.
 *
 * Backend materialises one notification row per user for broadcasts, so we
 * can safely mark/unmark server-side without cross-user leakage. No more
 * localStorage read-tracking hack.
 */
export const notificationsApi = {
  list: (params = {}) =>
    api.get("/notifications/me", { params }).then((r) => r.data),

  unreadCount: () =>
    api.get("/notifications/me/unread-count").then((r) => r.data),

  markRead: (n) =>
    api
      .post("/notifications/me/mark-read", { ids: [n.id] })
      .then((r) => r.data),

  markAllRead: () =>
    api.post("/notifications/me/read-all").then((r) => r.data),
};
