/**
 * Token storage — keeps ADMIN and USER sessions strictly separated.
 *
 * Previously we stored a single `rw_access_token` key which meant logging
 * into either role overwrote the other's tokens. That let a user session
 * silently downgrade the admin's requests to "Admin access required" 403s.
 *
 * Rule:
 *   - Admin session → keys `rw_admin_access` + `rw_admin_refresh`.
 *   - User session  → keys `rw_user_access`  + `rw_user_refresh`.
 *   - The axios interceptor picks the right key based on the request URL
 *     (admin routes get the admin token; everything else gets user).
 */

const KEYS = {
  admin: { access: "rw_admin_access", refresh: "rw_admin_refresh" },
  user: { access: "rw_user_access", refresh: "rw_user_refresh" },
};

// One-time migration of the old `rw_access_token` / `rw_refresh_token` /
// `rw_role` keys into the new per-role keys. Runs once per page load.
let migrated = false;
function migrateOnce() {
  if (migrated) return;
  migrated = true;
  try {
    const oldAccess = localStorage.getItem("rw_access_token");
    const oldRefresh = localStorage.getItem("rw_refresh_token");
    const oldRole = localStorage.getItem("rw_role");
    if (oldAccess && oldRole && (oldRole === "admin" || oldRole === "user")) {
      if (!localStorage.getItem(KEYS[oldRole].access)) {
        localStorage.setItem(KEYS[oldRole].access, oldAccess);
        if (oldRefresh) localStorage.setItem(KEYS[oldRole].refresh, oldRefresh);
      }
    }
    localStorage.removeItem("rw_access_token");
    localStorage.removeItem("rw_refresh_token");
    // Keep `rw_role` for AuthContext until it also migrates.
  } catch {
    // localStorage disabled — ignore.
  }
}

/**
 * Decide which role's token to send with an outgoing request.
 *
 * Strategy:
 *   1. If the URL is unambiguously an admin route (`/admin/...`, or path
 *      segments ending in `/admin`, `/admin/{id}` etc.) → admin.
 *   2. Otherwise fall back to the CURRENT BROWSER ROUTE — anything under
 *      `/admin` in the URL bar is treated as an admin session context.
 *   3. Otherwise → user.
 *
 * URL is the axios `config.url` (relative to API_BASE) e.g. `/programs/admin`
 * or `/auth/me`. Endpoints like `/programs` and `/modules` are shared by
 * user + admin, so route-context is what disambiguates them.
 */
export function roleForRequestUrl(url = "") {
  const u = String(url);
  const urlLooksAdmin =
    u.startsWith("/admin") ||
    u.startsWith("admin") ||
    /\/admin(\/|$)/.test(u);
  if (urlLooksAdmin) return "admin";
  if (typeof window !== "undefined") {
    const path = window.location.pathname || "";
    if (path.startsWith("/admin")) return "admin";
  }
  return "user";
}

export function getAccessToken(role) {
  migrateOnce();
  return localStorage.getItem(KEYS[role].access);
}

export function getRefreshToken(role) {
  migrateOnce();
  return localStorage.getItem(KEYS[role].refresh);
}

export function setTokens(role, tokens) {
  localStorage.setItem(KEYS[role].access, tokens.access_token);
  if (tokens.refresh_token) localStorage.setItem(KEYS[role].refresh, tokens.refresh_token);
  // Also stamp the "active role" so AuthContext boot knows what to hydrate.
  localStorage.setItem("rw_active_role", role);
}

export function clearRoleTokens(role) {
  localStorage.removeItem(KEYS[role].access);
  localStorage.removeItem(KEYS[role].refresh);
  if (localStorage.getItem("rw_active_role") === role) {
    localStorage.removeItem("rw_active_role");
  }
}

export function getActiveRole() {
  migrateOnce();
  const explicit = localStorage.getItem("rw_active_role");
  if (explicit) return explicit;
  // Legacy fallback — will disappear on next login.
  return localStorage.getItem("rw_role");
}
