import { useEffect, useState } from "react";
import { Loader2, TrendingUp, Filter } from "lucide-react";
import { toast } from "sonner";

import TopBar from "@/components/TopBar";
import { commissionsApi } from "@/services/referrals";
import { formatApiError } from "@/lib/api";

const STATUS_CHIP = {
  pending: "rw-chip-sky",
  approved: "rw-chip-gold",
  paid: "rw-chip-gold",
  rejected: "rw-chip-grey",
};

const STATUS_LABEL = {
  pending: "Pending",
  approved: "Approved",
  paid: "Paid",
  rejected: "Rejected",
};

const FILTERS = [
  { key: "", label: "All" },
  { key: "pending", label: "Pending" },
  { key: "approved", label: "Approved" },
  { key: "paid", label: "Paid" },
  { key: "rejected", label: "Rejected" },
];

export default function Commissions() {
  const [summary, setSummary] = useState(null);
  const [items, setItems] = useState([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [s, list] = await Promise.all([
        commissionsApi.summary(),
        commissionsApi.list(statusFilter ? { status: statusFilter, page_size: 100 } : { page_size: 100 }),
      ]);
      setSummary(s);
      setItems(list.items || []);
    } catch (e) {
      toast.error(formatApiError(e, "Could not load commissions"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  return (
    <div className="px-4 pt-3 pb-24">
      <TopBar title="Commissions" subtitle="L1 · L2 · L3 referral ledger" />

      {loading && !summary ? (
        <div className="grid place-items-center py-24 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <SummaryCell label="Lifetime" value={summary?.lifetime} accent="gold" />
            <SummaryCell label="This month" value={summary?.current_month} />
            <SummaryCell label="Pending" value={summary?.pending} />
            <SummaryCell label="Approved (payable)" value={summary?.approved} />
            <SummaryCell label="Paid" value={summary?.paid} />
            <SummaryCell label="Rejected" value={summary?.rejected} />
          </div>

          <div className="mt-5 flex items-center gap-2 overflow-x-auto pb-1">
            <Filter className="h-3.5 w-3.5 text-muted-foreground" />
            {FILTERS.map((f) => (
              <button
                key={f.key || "all"}
                onClick={() => setStatusFilter(f.key)}
                className={`whitespace-nowrap rounded-full px-3 py-1 text-xs font-semibold ${
                  statusFilter === f.key
                    ? "bg-[hsl(var(--rw-royal))] text-white"
                    : "bg-neutral-100 text-muted-foreground"
                }`}
                data-testid={`commissions-filter-${f.key || "all"}`}
              >
                {f.label}
              </button>
            ))}
          </div>

          <div className="mt-4 space-y-3" data-testid="commissions-list">
            {items.length === 0 ? (
              <div className="rw-card grid place-items-center p-10 text-center text-sm text-muted-foreground">
                <TrendingUp className="mb-2 h-5 w-5" />
                No commissions yet. Share your referral to start earning.
              </div>
            ) : (
              items.map((c) => (
                <div key={c.id} className="rw-card p-4" data-testid={`commission-item-${c.id}`}>
                  <div className="flex items-baseline justify-between">
                    <div>
                      <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
                        L{c.level} · {formatDate(c.created_at)}
                      </p>
                      <h3 className="mt-0.5 rw-serif text-lg">
                        {c.program_name || "Program"}
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        Buyer: {c.buyer_name || "—"}{" "}
                        <span className="font-mono">
                          ({c.buyer_membership_id})
                        </span>
                      </p>
                    </div>
                    <div className="text-right">
                      <div className="rw-serif text-xl text-[hsl(var(--rw-royal-deep))]">
                        ₹{Number(c.amount).toLocaleString("en-IN")}
                      </div>
                      <span className={`rw-chip ${STATUS_CHIP[c.status]}`}>
                        {STATUS_LABEL[c.status]}
                      </span>
                    </div>
                  </div>
                  {c.reason && (
                    <p className="mt-2 text-xs text-muted-foreground">
                      Note: {c.reason}
                    </p>
                  )}
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}

function SummaryCell({ label, value, accent }) {
  const isGold = accent === "gold";
  return (
    <div className="rw-card p-3">
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
      <div
        className={`mt-1 rw-serif text-xl ${
          isGold
            ? "text-[hsl(35_60%_38%)]"
            : "text-[hsl(var(--rw-royal-deep))]"
        }`}
      >
        ₹{Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
      </div>
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
