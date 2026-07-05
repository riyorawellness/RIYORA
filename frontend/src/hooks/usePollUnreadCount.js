import { useEffect, useRef, useState } from "react";
import { notificationsApi } from "@/services/notifications";

/**
 * Poll the backend for unread-count every `intervalMs` (default 20 s) so
 * users see admin broadcasts land in near-real-time without needing to
 * refresh. Skips polling when the tab is hidden and refreshes immediately
 * when it becomes visible again.
 *
 * Enable via ``enabled=false`` (e.g. for logged-out users) to avoid 401s.
 */
export function usePollUnreadCount({ enabled = true, intervalMs = 20000 } = {}) {
  const [unread, setUnread] = useState(0);
  const [lastNew, setLastNew] = useState(null); // timestamp when count went UP
  const prev = useRef(0);
  const timer = useRef(null);

  useEffect(() => {
    if (!enabled) return undefined;

    let cancelled = false;
    const tick = async () => {
      if (document.hidden) return;
      try {
        const r = await notificationsApi.unreadCount();
        if (cancelled) return;
        const next = Number(r?.unread || 0);
        if (next > prev.current) setLastNew(Date.now());
        prev.current = next;
        setUnread(next);
      } catch {
        /* silent; user might be logged-out or offline */
      }
    };

    tick(); // first pull immediately
    timer.current = setInterval(tick, intervalMs);

    const onVisible = () => {
      if (!document.hidden) tick();
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      cancelled = true;
      if (timer.current) clearInterval(timer.current);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [enabled, intervalMs]);

  return { unread, lastNew };
}
