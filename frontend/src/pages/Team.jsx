import { useState } from "react";
import TopBar from "@/components/TopBar";
import { TEAM } from "@/mock/data";
import { TID } from "@/constants/testIds";

const TABS = [
  { key: "direct", label: "Direct (L1)", testId: TID.teamTabDirect },
  { key: "level_2", label: "Level 2", testId: TID.teamTabL2 },
  { key: "level_3", label: "Level 3", testId: TID.teamTabL3 },
];

const STATUS_DOT = { active: "bg-green-500", grace: "bg-amber-500", inactive: "bg-rose-500" };

export default function Team() {
  const [tab, setTab] = useState("direct");
  const rows = TEAM[tab] || [];

  return (
    <div className="px-4 pt-3">
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
            {t.label} · {TEAM[t.key]?.length ?? 0}
          </button>
        ))}
      </div>

      <div className="mt-4 space-y-3" data-testid={TID.teamList}>
        {rows.length === 0 ? (
          <div className="rw-card p-6 text-center text-sm text-muted-foreground">
            No members at this level yet.
          </div>
        ) : (
          rows.map((m) => (
            <div key={m.id} className="rw-card flex items-center gap-3 p-4">
              <div className="grid h-11 w-11 place-items-center rounded-full bg-[hsl(var(--rw-sky-soft))] font-semibold text-[hsl(var(--rw-royal-deep))]">
                {m.name.split(" ").map((s) => s[0]).slice(0, 2).join("")}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate font-semibold">{m.name}</div>
                <div className="text-[11px] text-muted-foreground">{m.id} · {m.state} · joined {m.joined}</div>
              </div>
              <div className="flex items-center gap-1">
                <span className={`h-2 w-2 rounded-full ${STATUS_DOT[m.status]}`} />
                <span className="text-[11px] capitalize text-muted-foreground">{m.status}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
