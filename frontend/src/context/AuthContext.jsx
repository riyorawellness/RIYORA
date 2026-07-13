import React, { createContext, useContext, useEffect, useState } from "react";
import api from "@/lib/api";
import {
  clearRoleTokens,
  getAccessToken,
  getActiveRole,
  getRefreshToken,
  setTokens,
} from "@/lib/tokenStore";
import { signOut as fbSignOut } from "@/lib/firebase";

const AuthContext = createContext(null);

/**
 * Auth context — supports admin AND user sessions IN THE SAME BROWSER,
 * side-by-side, without one clobbering the other. Token storage is keyed
 * per role in `tokenStore.js`; the axios interceptor picks the right key
 * based on the outgoing request URL.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [admin, setAdmin] = useState(null);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    // Hydrate any sessions we still have valid tokens for. Attempts BOTH
    // roles independently — if only one token pair exists, only that role
    // gets hydrated.
    (async () => {
      const tries = [];
      if (getAccessToken("admin")) {
        tries.push(
          api
            .get("/admin/profile")
            .then(({ data }) => setAdmin(data))
            .catch(() => clearRoleTokens("admin")),
        );
      }
      if (getAccessToken("user")) {
        tries.push(
          api
            .get("/auth/me")
            .then(({ data }) => setUser(data))
            .catch(() => clearRoleTokens("user")),
        );
      }
      // Legacy migration path — if only the old `rw_role` exists, the
      // tokenStore migration already copied tokens; nothing more to do.
      const legacyRole = getActiveRole();
      if (!tries.length && legacyRole) {
        // No tokens survived migration; drop the stale role marker.
        localStorage.removeItem("rw_role");
      }
      await Promise.all(tries);
      setStatus("ready");
    })();
  }, []);

  const loginUser = async (mobile, password) => {
    // Legacy path — kept for backward compat during Phase 1. New logins
    // should use signInWithFirebase() below.
    const { data } = await api.post("/auth/login", { mobile, password });
    setTokens("user", data.tokens);
    setUser(data.user);
    return data.user;
  };

  /**
   * Exchange a Firebase ID token for a RIYORA session.
   * Returns:
   *   { needs_registration: true, firebase_user: {...} }  → route to /complete-profile
   *   { user, tokens }                                     → session established
   */
  const syncFirebaseToken = async (idToken) => {
    const { data } = await api.post("/auth/firebase/sync", { id_token: idToken });
    if (!data.needs_registration) {
      setTokens("user", data.tokens);
      setUser(data.user);
    }
    return data;
  };

  const registerWithFirebase = async (payload) => {
    const { data } = await api.post("/auth/firebase/register", payload);
    setTokens("user", data.tokens);
    setUser(data.user);
    return data.user;
  };

  const linkExistingWithFirebase = async (payload) => {
    const { data } = await api.post("/auth/firebase/link-existing", payload);
    setTokens("user", data.tokens);
    setUser(data.user);
    return data.user;
  };

  const updateMyProfile = async (patch) => {
    const { data } = await api.patch("/users/me", patch);
    setUser(data);
    return data;
  };

  const submitChangeRequest = async (payload) => {
    const { data } = await api.post("/users/me/change-request", payload);
    return data;
  };

  const listMyChangeRequests = async () => {
    const { data } = await api.get("/users/me/change-requests");
    return data;
  };

  const registerUser = async () => {
    throw new Error("Legacy register removed. Use registerWithFirebase instead.");
  };

  const loginAdmin = async (mobile, password) => {
    const { data } = await api.post("/admin/login", { mobile, password });
    setTokens("admin", data.tokens);
    setAdmin(data.admin);
    return data.admin;
  };

  const logout = async () => {
    // Whichever role is "active" from the user's perspective — we log out
    // that one. If both are populated, prefer admin because admin logout
    // is the more explicit action (bottom nav has a user-specific logout).
    const roleToKill = admin ? "admin" : user ? "user" : null;
    if (!roleToKill) return;
    const refresh = getRefreshToken(roleToKill);
    try {
      if (refresh) await api.post("/auth/logout", { refresh_token: refresh });
    } catch {
      // swallow
    }
    clearRoleTokens(roleToKill);
    if (roleToKill === "admin") setAdmin(null);
    else {
      setUser(null);
      // Also sign out from Firebase so next visit doesn't auto-restore.
      try { await fbSignOut(); } catch (_) { /* ignore */ }
    }
  };

  const refreshProfile = async () => {
    const { data } = await api.get("/auth/me");
    setUser(data);
    return data;
  };

  const value = {
    user,
    admin,
    status,
    loginUser,
    loginAdmin,
    registerUser,
    syncFirebaseToken,
    registerWithFirebase,
    linkExistingWithFirebase,
    updateMyProfile,
    submitChangeRequest,
    listMyChangeRequests,
    logout,
    refreshProfile,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
