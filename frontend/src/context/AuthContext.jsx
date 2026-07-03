import React, { createContext, useContext, useEffect, useState } from "react";
import api from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // user object
  const [admin, setAdmin] = useState(null); // admin object
  const [status, setStatus] = useState("loading"); // loading | ready

  useEffect(() => {
    const access = localStorage.getItem("rw_access_token");
    const role = localStorage.getItem("rw_role");
    if (!access) {
      setStatus("ready");
      return;
    }
    (async () => {
      try {
        if (role === "admin") {
          const { data } = await api.get("/admin/profile");
          setAdmin(data);
        } else {
          const { data } = await api.get("/auth/me");
          setUser(data);
        }
      } catch (e) {
        // ignore – tokens will be cleaned up
      } finally {
        setStatus("ready");
      }
    })();
  }, []);

  const persistTokens = (tokens, role) => {
    localStorage.setItem("rw_access_token", tokens.access_token);
    localStorage.setItem("rw_refresh_token", tokens.refresh_token);
    localStorage.setItem("rw_role", role);
  };

  const loginUser = async (mobile, password) => {
    const { data } = await api.post("/auth/login", { mobile, password });
    persistTokens(data.tokens, "user");
    setUser(data.user);
    setAdmin(null);
    return data.user;
  };

  const registerUser = async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    persistTokens(data.tokens, "user");
    setUser(data.user);
    setAdmin(null);
    return data.user;
  };

  const loginAdmin = async (mobile, password) => {
    const { data } = await api.post("/admin/login", { mobile, password });
    persistTokens(data.tokens, "admin");
    setAdmin(data.admin);
    setUser(null);
    return data.admin;
  };

  const logout = async () => {
    const refresh = localStorage.getItem("rw_refresh_token");
    try {
      if (refresh) await api.post("/auth/logout", { refresh_token: refresh });
    } catch (e) {
      // swallow
    }
    localStorage.removeItem("rw_access_token");
    localStorage.removeItem("rw_refresh_token");
    localStorage.removeItem("rw_role");
    setUser(null);
    setAdmin(null);
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
