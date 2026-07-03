import { useState } from "react";
import { Bell, BellOff } from "lucide-react";
import { NOTIFICATIONS } from "@/mock/data";
import EmptyState from "@/components/EmptyState";
import { TID } from "@/constants/testIds";

const CATEGORY_COLORS = {
  welcome: "bg-[hsl(var(--rw-gold-soft))] text-[hsl(35_60%_38%)]",
  programs: "bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal-deep))]",
  live: "bg-[hsl(var(--rw-gold-soft))] text-[hsl(35_60%_38%)]",
  referrals: "bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal-deep))]",
};

export default function Notifications() {
  const [items, setItems] = useState(NOTIFICATIONS);
  const [filter, setFilter] = useState("all");

  const shown = items.filter((n) =>
    filter === "all" ? true : filter === "unread" ? !n.is_read : n.is_read
  );

  const markAllRead = () => setItems((xs) => xs.map((x) => ({ ...x, is_read: true })));

  return (
    <div className="px-5 pt-6">
      <div className="flex items-baseline justify-between">
        <div>
          <p className="rw-eyebrow">Alerts</p>
          <h1 className="mt-1 rw-serif text-4xl">Notifications</h1>
        </div>
        <button onClick={markAllRead} className="text-xs font-semibold text-[hsl(var(--rw-royal))]">
          Mark all read
        </button>
      </div>

      <div className="mt-5 flex gap-1 rounded-2xl bg-[hsl(var(--rw-grey-50))] p-1">
        {["all", "unread", "read"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`flex-1 rounded-xl py-2 text-xs font-semibold capitalize transition-all ${
              filter === f ? "bg-white text-[hsl(var(--rw-royal-deep))] shadow-sm" : "text-muted-foreground"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {shown.length === 0 ? (
        <EmptyState icon={BellOff} title="Nothing here yet" body="New notifications will land here." />
      ) : (
        <div className="mt-5 space-y-2">
          {shown.map((n) => (
            <div
              key={n.id}
              onClick={() => setItems((xs) => xs.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)))}
              data-testid={TID.notificationItem(n.id)}
              className={`rw-card flex items-start gap-3 p-4 ${!n.is_read ? "border-[hsl(var(--rw-royal))]/25" : ""}`}
            >
              <div className={`grid h-10 w-10 place-items-center rounded-full ${CATEGORY_COLORS[n.category] || "bg-[hsl(var(--rw-grey-100))]"}`}>
                <Bell className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className={`text-sm ${!n.is_read ? "font-semibold" : ""}`}>{n.title}</span>
                  {!n.is_read && <span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--rw-royal))]" />}
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">{n.body}</p>
              </div>
              <span className="whitespace-nowrap text-[10px] text-muted-foreground">{n.when}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
