import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Clock, XCircle, RefreshCw, Loader2 } from "lucide-react";

import TopBar from "@/components/TopBar";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { manualPaymentsApi, resolveUploadUrl } from "@/services/manualPayments";

const STATUS_META = {
  pending:  { label: "Pending Verification", tone: "bg-amber-100 text-amber-700", Icon: Clock },
  approved: { label: "Approved",             tone: "bg-emerald-100 text-emerald-700", Icon: CheckCircle2 },
  rejected: { label: "Rejected",             tone: "bg-red-100 text-red-700", Icon: XCircle },
};

export default function PaymentHistory() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const r = await manualPaymentsApi.myHistory({ page_size: 50 });
      setItems(r.items || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="px-4 pt-3 pb-24" data-testid="payment-history-page">
      <TopBar title="Payment History" subtitle="Your manual QR payments" />

      <div className="mt-3 flex justify-end">
        <Button variant="ghost" size="sm" onClick={load} disabled={loading} data-testid="ph-refresh">
          <RefreshCw className={`mr-1 h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
        </Button>
      </div>

      {loading ? (
        <div className="grid place-items-center py-16 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <Card className="mt-4 border-dashed p-8 text-center text-sm text-muted-foreground">
          You haven&apos;t submitted any manual payments yet.
        </Card>
      ) : (
        <div className="mt-2 space-y-3">
          {items.map((r) => {
            const meta = STATUS_META[r.status] || STATUS_META.pending;
            const Icon = meta.Icon;
            return (
              <Card key={r.id} className="p-4" data-testid={`ph-item-${r.status}`}>
                <div className="flex items-start gap-3">
                  <div className={`grid h-10 w-10 place-items-center rounded-full ${meta.tone}`}>
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="rw-serif truncate text-lg">{r.program_name}</h3>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                      <Badge variant="secondary">{meta.label}</Badge>
                      <span>·</span>
                      <span>{new Date(r.submitted_at).toLocaleString()}</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="rw-serif text-lg tabular-nums">₹{Number(r.total).toLocaleString("en-IN")}</div>
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  <Field k="UTR" v={<span className="font-mono">{r.utr}</span>} />
                  <Field k="Level" v={r.program_level != null ? `L${r.program_level}` : "—"} />
                </div>

                {r.status === "rejected" && r.rejection_reason && (
                  <div className="mt-3 rounded-lg border-l-4 border-red-500 bg-red-50 p-3 text-xs text-red-800">
                    <p className="font-semibold">Reason</p>
                    <p className="mt-0.5">{r.rejection_reason}</p>
                    <div className="mt-2">
                      <Link
                        to={`/app/pay/${r.program_id}`}
                        className="font-semibold text-red-700 underline"
                        data-testid="ph-resubmit-link"
                      >
                        Resubmit payment →
                      </Link>
                    </div>
                  </div>
                )}

                {r.screenshot_url && (
                  <a
                    href={resolveUploadUrl(r.screenshot_url)}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-3 inline-block text-[11px] font-semibold text-[hsl(var(--rw-royal))] underline"
                  >
                    View screenshot →
                  </a>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Field({ k, v }) {
  return (
    <div className="rounded-md bg-neutral-50 p-2">
      <div className="text-[9px] uppercase tracking-widest text-muted-foreground">{k}</div>
      <div className="mt-0.5 text-sm font-medium">{v}</div>
    </div>
  );
}
