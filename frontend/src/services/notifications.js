import api from "@/lib/api";

/**
 * User + admin notifications API.
 *
 * IMPORTANT server-side note (see /app/backend/app/routes/notifications.py):
 * Broadcast notifications (`is_broadcast=true`) are SHARED across all users —
 * a single document per broadcast, not one per recipient. That means calling
 * `markRead` or `readAll` mutates the shared row's `is_read` field, which
 * would flip the flag for every other user too.  To avoid that leak, this
 * client keeps a **per-user read-log** in localStorage for broadcast IDs and
 * derives `is_read` client-side. Personal notifications continue to use the
 * server flag directly.
 */

const LS_KEY = "rw.notifRead";

function loadReadIds() {
  try {
    return new Set(JSON.parse(localStorage.getItem(LS_KEY) || "[]"));
  } catch {
    return new Set();
  }
}
function saveReadIds(set) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify([...set]));
  } catch {
    /* localStorage disabled — degrade silently */
  }
}

function applyReadState(items) {
  const readIds = loadReadIds();
  return items.map((n) =>
    n.is_broadcast ? { ...n, is_read: readIds.has(n.id) || !!n.is_read } : n
  );
}

export const notificationsApi = {
  list: async (params = {}) => {
    const r = await api.get("/notifications/me", { params });
    const items = applyReadState(r.data.items || []);
    const unread = items.filter((n) => !n.is_read).length;
    return { ...r.data, items, unread };
  },

  unreadCount: async () => {
    const r = await api.get("/notifications/me?page_size=200");
    const items = applyReadState(r.data.items || []);
    return { unread: items.filter((n) => !n.is_read).length };
  },

  markRead: async (n) => {
    if (n.is_broadcast) {
      const set = loadReadIds();
      set.add(n.id);
      saveReadIds(set);
      return { success: true };
    }
    const r = await api.post("/notifications/me/mark-read", { ids: [n.id] });
    return r.data;
  },

  markAllRead: async () => {
    // For broadcasts: add all currently-visible broadcast IDs to LS.
    // For personal: call server /read-all with a narrower query (personal only).
    const listing = await api.get("/notifications/me", { params: { page_size: 200 } });
    const items = listing.data.items || [];
    const readSet = loadReadIds();
    items.forEach((n) => { if (n.is_broadcast) readSet.add(n.id); });
    saveReadIds(readSet);

    // Personal-only server flip
    const personalUnread = items.filter((n) => !n.is_broadcast && !n.is_read).map((n) => n.id);
    if (personalUnread.length) {
      await api.post("/notifications/me/mark-read", { ids: personalUnread });
    }
    return { success: true, count: items.length };
  },
};
