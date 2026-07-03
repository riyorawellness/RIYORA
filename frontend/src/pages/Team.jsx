import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import TopBar from "@/components/TopBar";
import { referralsApi } from "@/services/referrals";
import { TID } from "@/constants/testIds";
import { formatApiError } from "@/lib/api";

const TABS = [
  { key: 1, label: "Direct (L1)", testId: TID.teamTabDirect },
  { key: 2, label: "Level 2", testId: TID.teamTabL2 },
  { key: 3, label: "Level 3", testId: TID.teamTabL3 },
];

const STATUS_DOT = {
  green: "bg-emerald-500",
  yellow: "bg-amber-500",
  red: "bg-rose-500",
  no_subscription: "bg-neutral-300",
};
const STATUS_LABEL = {
  green: "Active",
  yellow: "Grace",
  red: "Inactive",
  no_subscription: "No sub",
};

export default function Team() {
  const [tab, setTab] = useState(1);
  const [data, setData] = useState({ 1: null, 2: null, 3: null });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (data[tab]) return;
    setLoading(true);
    (async () => {
      try {
        const d = await referralsApi.team(tab);
        setData((prev) => ({ ...prev, [tab]: d }));
      } catch (e) {
        toast.error(formatApiError(e, "Could not load team"));
      } finally {
        setLoading(false);
      }
    })();
  }, [tab, data]);

  const rows = data[tab]?.items || [];

  return (
    <div className="px-4 pt-3 pb-24">
      <TopBar title="Your team" subtitle="3-level downline" />

      <div className="mt-4 flex gap-1 rounded-2xl bg-[hsl(var(--rw-grey-50))] p-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            data-testid={t.testId}
            className={`flex-1 rounded-xl py-2 text-xs font-semibold transition-all ${
              tab === t.key
                ? "bg-white text-[hsl(var(--rw-royal-deep))] shadow-sm"
                : "text-muted-foreground"
            }`}
          >
            {t.label} · {data[t.key]?.count ?? "…"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="mt-8 grid place-items-center text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      ) : (
        <div className="mt-4 space-y-3" data-testid={TID.teamList}>
          {rows.length === 0 ? (
            <div className="rw-card p-6 text-center text-sm text-muted-foreground">
              No members at this level yet.
            </div>
          ) : (
            rows.map((m) => (
              <div key={m.membership_id} className="rw-card flex items-center gap-3 p-4">
                <div className="grid h-11 w-11 place-items-center rounded-full bg-[hsl(var(--rw-sky-soft))] font-semibold text-[hsl(var(--rw-royal-deep))]">
                  {(m.full_name || "?")
                    .split(" ")
                    .map((s) => s[0])
                    .slice(0, 2)
                    .join("")}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-semibold">
                    {m.full_name || "—"}
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    <span className="font-mono">{m.membership_id}</span>
                    {m.state && ` · ${m.state}`}
                    {m.joining_date &&
                      ` · joined ${formatDate(m.joining_date)}`}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <div className="flex items-center gap-1">
                    <span
                      className={`h-2 w-2 rounded-full ${
                        STATUS_DOT[m.activity_status] || "bg-neutral-300"
                      }`}
                    />
                    <span className="text-[11px] capitalize text-muted-foreground">
                      {STATUS_LABEL[m.activity_status] || "—"}
                    </span>
                  </div>
                  {m.has_subscription && (
                    <span className="text-[10px] text-[hsl(35_60%_38%)]">
                      IP · subscribed
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "2-digit",
    });
  } catch {
    return iso;
  }
}
