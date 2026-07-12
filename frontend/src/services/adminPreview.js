import api from "@/lib/api";
import { setTokens, clearRoleTokens } from "@/lib/tokenStore";

const PREVIEW_META_KEY = "rw_preview_mode";
const SAVED_USER_KEY = "rw_preview_saved_user";

/**
 * Impersonate a user. Called with the current admin token; the response
 * contains a short-lived user-role access token that we store in the normal
 * user slot so every `/api/...` call transparently uses it.
 *
 * We stash the previous user session (if any) so we can restore it on exit.
 */
export async function startAdminPreview(membershipId) {
  const { data } = await api.post(`/admin/preview/impersonate/${membershipId}`);
  // Save any previously logged-in user tokens so we can restore them on exit.
  const prev = {
    access: localStorage.getItem("rw_user_access") || null,
    refresh: localStorage.getItem("rw_user_refresh") || null,
    user: localStorage.getItem("rw_user") || null,
  };
  localStorage.setItem(SAVED_USER_KEY, JSON.stringify(prev));
  // Install the impersonation token in the user slot.
  setTokens("user", {
    access_token: data.access_token,
    refresh_token: null, // preview tokens are non-refreshable
  });
  localStorage.setItem("rw_user", JSON.stringify(data.user));
  localStorage.setItem(
    PREVIEW_META_KEY,
    JSON.stringify({
      membership_id: data.user.membership_id,
      full_name: data.user.full_name,
      admin_mobile: data.impersonated_by,
      expires_in_minutes: data.expires_in_minutes,
      started_at: new Date().toISOString(),
    }),
  );
  return data;
}

export function exitAdminPreview() {
  clearRoleTokens("user");
  localStorage.removeItem("rw_user");
  localStorage.removeItem(PREVIEW_META_KEY);
  // Restore previous user session if we had one.
  try {
    const raw = localStorage.getItem(SAVED_USER_KEY);
    if (raw) {
      const prev = JSON.parse(raw);
      if (prev?.access) localStorage.setItem("rw_user_access", prev.access);
      if (prev?.refresh) localStorage.setItem("rw_user_refresh", prev.refresh);
      if (prev?.user) localStorage.setItem("rw_user", prev.user);
    }
  } catch {
    /* ignore corrupt payload */
  }
  localStorage.removeItem(SAVED_USER_KEY);
}

export function getPreviewMeta() {
  try {
    const raw = localStorage.getItem(PREVIEW_META_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function isInPreview() {
  return !!getPreviewMeta();
}

export async function markPaidPreview(programId) {
  const { data } = await api.post("/admin/preview/mark-paid", {
    program_id: programId,
  });
  return data;
}
