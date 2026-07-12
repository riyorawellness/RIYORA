import { useEffect, useState, useCallback } from "react";
import { Bell, BellOff, Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Link } from "react-router-dom";

import EmptyState from "@/components/EmptyState";
import { Badge } from "@/components/ui/badge";
import { notificationsApi } from "@/services/notifications";
import { TID } from "@/constants/testIds";
import { formatApiError } from "@/lib/api";

const CATEGORY_COLORS = {
  welcome: "bg-[hsl(var(--rw-gold-soft))] text-[hsl(35_60%_38%)]",
  program: "bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal-deep))]",
  live: "bg-[hsl(var(--rw-gold-soft))] text-[hsl(35_60%_38%)]",
  referral: "bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal-deep))]",
  payment: "bg-emerald-50 text-emerald-700",
  system: "bg-neutral-100 text-neutral-700",
  announcement: "bg-[hsl(var(--rw-gold-soft))] text-[hsl(35_60%_38%)]",
  offer: "bg-amber-100 text-amber-800",
  renewal: "bg-red-50 text-red-700",
  activity: "bg-blue-50 text-blue-700",
};

export default function Notifications() {
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState("all");

  const load = useCallback(async (opts = { silent: false }) => {
    if (!opts.silent) setLoading(true);
    else setRefreshing(true);
    try {
      const r = await notificationsApi.list({ page_size: 100 });
      setItems(r.items || []);
      setUnread(r.unread ?? 0);
    } catch (e) {
      toast.error(formatApiError(e, "Could not load notifications"));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Real-time refresh: poll for new notifications every 15s while this page
  // is open, plus an immediate refresh when the tab regains focus.
  useEffect(() => {
    const tick = () => {
      if (!document.hidden) load({ silent: true });
    };
    const id = setInterval(tick, 15000);
    document.addEventListener("visibilitychange", tick);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [load]);

  const markOne = async (n) => {
    if (n.is_read) return;
    // Optimistic
    setItems((xs) => xs.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)));
    setUnread((u) => Math.max(0, u - 1));
    try {
      await notificationsApi.markRead(n);
    } catch (e) {
      toast.error("Couldn't mark as read");
      load();
    }
  };

  const markAll = async () => {
    if (!items.some((n) => !n.is_read)) return;
    setItems((xs) => xs.map((x) => ({ ...x, is_read: true })));
    setUnread(0);
    try {
      await notificationsApi.markAllRead();
      toast.success("All notifications marked as read");
    } catch (e) {
      toast.error("Couldn't mark all as read");
      load();
    }
  };

  const shown = items.filter((n) =>
    filter === "all" ? true : filter === "unread" ? !n.is_read : n.is_read
  );

  return (
    <div className="px-5 pb-24 pt-6" data-testid="user-notifications-page">
      <div className="flex items-baseline justify-between gap-3">
        <div className="min-w-0">
          <p className="rw-eyebrow">Alerts</p>
          <h1 className="mt-1 rw-serif text-4xl">
            Notifications
            {unread > 0 && (
              <Badge className="ml-2 align-middle" data-testid="notif-unread-badge">{unread}</Badge>
            )}
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => load({ silent: true })}
            className="grid h-8 w-8 place-items-center rounded-full text-muted-foreground hover:bg-neutral-100"
            aria-label="Refresh"
            data-testid="notif-refresh-btn"
            disabled={refreshing}
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={markAll}
            className="text-xs font-semibold text-[hsl(var(--rw-royal))] disabled:opacity-50"
            disabled={unread === 0}
            data-testid="notif-mark-all-btn"
          >
            Mark all read
          </button>
        </div>
      </div>

      <div className="mt-5 flex gap-1 rounded-2xl bg-[hsl(var(--rw-grey-50))] p-1">
        {["all", "unread", "read"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            data-testid={`notif-filter-${f}`}
            className={`flex-1 rounded-xl py-2 text-xs font-semibold capitalize transition-all ${
              filter === f ? "bg-white text-[hsl(var(--rw-royal-deep))] shadow-sm" : "text-muted-foreground"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="mt-16 grid place-items-center text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : shown.length === 0 ? (
        <EmptyState
          icon={BellOff}
          title={filter === "unread" ? "You're all caught up" : "Nothing here yet"}
          body="New notifications from RIYORA Wellness will land here."
        />
      ) : (
        <div className="mt-5 space-y-2" data-testid="notif-list">
          {shown.map((n) => {
            const catCls = CATEGORY_COLORS[n.category] || "bg-[hsl(var(--rw-grey-100))]";
            const inner = (
              <div
                onClick={() => markOne(n)}
                data-testid={TID.notificationItem ? TID.notificationItem(n.id) : `notif-item-${n.id}`}
                className={`rw-card flex items-start gap-3 p-4 cursor-pointer transition ${!n.is_read ? "border-[hsl(var(--rw-royal))]/40 bg-[hsl(var(--rw-sky-soft))]/40" : ""}`}
              >
                <div className={`grid h-10 w-10 flex-shrink-0 place-items-center rounded-full ${catCls}`}>
                  <Bell className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`min-w-0 truncate text-sm ${!n.is_read ? "font-semibold" : ""}`}>
                      {n.title}
                    </span>
                    {!n.is_read && (
                      <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[hsl(var(--rw-royal))]" />
                    )}
                    {n.is_broadcast && (
                      <Badge variant="secondary" className="text-[9px]">Broadcast</Badge>
                    )}
                  </div>
                  <p className="mt-0.5 whitespace-pre-wrap text-xs text-muted-foreground">{n.body}</p>
                  <div className="mt-1 flex items-center gap-2 text-[10px] text-muted-foreground">
                    <span className="capitalize">{n.category || "notification"}</span>
                    <span>·</span>
                    <span>{formatTime(n.created_at)}</span>
                  </div>
                  {n.cta_link && n.cta_label && (
                    <div className="mt-2">
                      <span
                        className="inline-block rounded-full bg-[hsl(var(--rw-royal))] px-3 py-1 text-[11px] font-semibold text-white"
                        data-testid={`notif-cta-${n.id}`}
                      >
                        {n.cta_label} →
                      </span>
                    </div>
                  )}
                </div>
              </div>
            );
            return n.cta_link ? (
              <Link key={n.id} to={n.cta_link} className="block">{inner}</Link>
            ) : (
              <div key={n.id}>{inner}</div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function formatTime(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const diffMs = Date.now() - d.getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 7) return `${days}d ago`;
    return d.toLocaleDateString();
  } catch {
    return "";
  }
}
