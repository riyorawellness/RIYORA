import React, { createContext, useContext, useEffect, useState } from "react";
import api from "@/lib/api";
import {
  clearRoleTokens,
  getAccessToken,
  getActiveRole,
  getRefreshToken,
  setTokens,
} from "@/lib/tokenStore";

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
    const { data } = await api.post("/auth/login", { mobile, password });
    setTokens("user", data.tokens);
    setUser(data.user);
    return data.user;
  };

  const registerUser = async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    setTokens("user", data.tokens);
    setUser(data.user);
    return data.user;
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
    else setUser(null);
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
