import { useEffect, useState } from "react";
import { Loader2, Wallet } from "lucide-react";
import { toast } from "sonner";

import TopBar from "@/components/TopBar";
import { payoutsApi } from "@/services/referrals";
import { formatApiError } from "@/lib/api";

const STATUS_CHIP = {
  pending: "rw-chip-sky",
  paid: "rw-chip-gold",
  cancelled: "rw-chip-grey",
};

export default function Payouts() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const d = await payoutsApi.myPayouts();
        setItems(d.items || []);
      } catch (e) {
        toast.error(formatApiError(e, "Could not load payouts"));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="px-4 pt-3 pb-24">
      <TopBar title="Payouts" subtitle="Admin-managed transfers" />

      {loading ? (
        <div className="grid place-items-center py-24 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <div className="mt-6 rw-card grid place-items-center p-10 text-center text-sm text-muted-foreground">
          <Wallet className="mb-2 h-5 w-5" />
          No payouts issued yet. Admin schedules payouts weekly / fortnightly.
        </div>
      ) : (
        <div className="mt-4 space-y-3" data-testid="payouts-list">
          {items.map((p) => (
            <div key={p.id} className="rw-card p-4" data-testid={`payout-item-${p.id}`}>
              <div className="flex items-baseline justify-between">
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
                    {formatDate(p.created_at)}
                  </p>
                  <h3 className="rw-serif text-lg">
                    ₹{Number(p.amount).toLocaleString("en-IN")}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    {p.commission_ids?.length || 0} commission(s) · {p.method}
                  </p>
                </div>
                <span className={`rw-chip ${STATUS_CHIP[p.status]}`}>
                  {p.status}
                </span>
              </div>
              {p.reference && (
                <div className="mt-2 text-xs text-muted-foreground">
                  Reference: <span className="font-mono">{p.reference}</span>
                </div>
              )}
              {p.notes && (
                <p className="mt-1 text-xs text-muted-foreground">{p.notes}</p>
              )}
              {p.paid_at && (
                <p className="mt-1 text-[11px] text-[hsl(35_60%_38%)]">
                  Paid on {formatDate(p.paid_at)}
                </p>
              )}
            </div>
          ))}
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
      year: "numeric",
    });
  } catch {
    return iso;
  }
}
