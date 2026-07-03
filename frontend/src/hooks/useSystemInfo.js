import { useEffect, useState } from "react";
import api from "@/lib/api";

/**
 * Fetch and cache the public system settings (support email, app version,
 * company name, etc). Refreshes at most once per 30s so admin edits propagate
 * quickly without pounding the API on every page.
 */
let _cache = null;
let _cachedAt = 0;
const TTL = 30_000;

export function useSystemInfo() {
  const [info, setInfo] = useState(_cache);

  useEffect(() => {
    const now = Date.now();
    if (_cache && now - _cachedAt < TTL) {
      setInfo(_cache);
      return;
    }
    let live = true;
    api.get("/system/public")
      .then((r) => {
        if (!live) return;
        _cache = r.data;
        _cachedAt = Date.now();
        setInfo(r.data);
      })
      .catch(() => {});
    return () => { live = false; };
  }, []);

  return info || {
    company_name: "RIYORA Wellness",
    application_version: "1.0.0",
    support_email: "info@riyorawellness.com",
  };
}
