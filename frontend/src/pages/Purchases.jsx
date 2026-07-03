import { useEffect, useState } from "react";
import { Loader2, Download, FileText } from "lucide-react";
import { toast } from "sonner";

import { paymentsApi } from "@/services/payments";
import { formatApiError } from "@/lib/api";

export default function Purchases() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await paymentsApi.myPayments();
        setItems(data.items || []);
      } catch (e) {
        toast.error(formatApiError(e, "Could not load transactions"));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const download = async (item) => {
    setDownloading(item.id);
    try {
      const blob = await paymentsApi.downloadInvoiceBlob(item.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${item.invoice_number}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(formatApiError(e, "Could not download invoice"));
    } finally {
      setDownloading(null);
    }
  };

  if (loading) {
    return (
      <div className="grid place-items-center py-24 text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  return (
    <div className="px-5 pt-6 pb-24">
      <p className="rw-eyebrow">Wallet</p>
      <h1 className="mt-1 rw-serif text-4xl">Transactions</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Every payment and its downloadable GST invoice, in one place.
      </p>

      {items.length === 0 ? (
        <div className="mt-10 grid place-items-center rounded-2xl bg-neutral-50 p-10">
          <FileText className="h-6 w-6 text-muted-foreground" />
          <p className="mt-2 text-sm text-muted-foreground">
            No purchases yet.
          </p>
        </div>
      ) : (
        <div className="mt-6 space-y-3" data-testid="purchases-list">
          {items.map((t) => (
            <div
              key={t.id}
              className="rw-card p-4"
              data-testid={`purchase-item-${t.id}`}
            >
              <div className="flex items-baseline justify-between">
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
                    {formatDate(t.purchase_date)}
                  </p>
                  <h3 className="rw-serif text-lg">
                    {t.program?.name || "Program"}
                  </h3>
                </div>
                <StatusPill status={t.status} />
              </div>

              <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
                <Field k="Invoice" v={t.invoice_number} mono />
                <Field
                  k="Amount"
                  v={`₹${(t.total || 0).toLocaleString("en-IN")}`}
                />
                <Field k="Expires" v={formatDate(t.expiry_date)} />
                <Field
                  k="Payment"
                  v={t.razorpay_payment_id ? "Razorpay" : "Subscription"}
                />
              </div>

              <button
                className="mt-3 flex w-full items-center justify-center gap-2 rw-btn-pill bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal-deep))]"
                onClick={() => download(t)}
                disabled={downloading === t.id}
                data-testid={`invoice-download-${t.id}`}
              >
                {downloading === t.id ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Download className="h-4 w-4" />
                )}
                Download invoice
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    active: { cls: "rw-chip-sky", text: "Active" },
    expired: { cls: "rw-chip-grey", text: "Expired" },
    cancelled: { cls: "rw-chip-grey", text: "Cancelled" },
    refunded: { cls: "rw-chip-gold", text: "Refunded" },
  };
  const m = map[status] || map.active;
  return <span className={`rw-chip ${m.cls}`}>{m.text}</span>;
}

function Field({ k, v, mono }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
        {k}
      </div>
      <div className={`mt-0.5 font-semibold ${mono ? "font-mono" : ""}`}>
        {v || "—"}
      </div>
    </div>
  );
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return "—";
  }
}
