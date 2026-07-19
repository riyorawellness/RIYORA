import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  CalendarClock,
  CheckCircle2,
  ChevronLeft,
  Loader2,
  Pause,
  Repeat,
  RotateCw,
  XCircle,
} from "lucide-react";

import { paymentsApi } from "@/services/payments";
import { formatApiError } from "@/lib/api";
import SubscriptionCheckoutModal from "@/components/SubscriptionCheckoutModal";

const STATUS_STYLES = {
  active:        { label: "Active",         color: "bg-emerald-100 text-emerald-700", icon: CheckCircle2 },
  authenticated: { label: "Authenticated",  color: "bg-sky-100 text-sky-700",         icon: CheckCircle2 },
  created:       { label: "Awaiting UPI",   color: "bg-amber-100 text-amber-700",     icon: Loader2 },
  pending:       { label: "Pending",        color: "bg-amber-100 text-amber-700",     icon: Loader2 },
  halted:        { label: "Payment failed", color: "bg-red-100 text-red-700",         icon: XCircle },
  paused:        { label: "Paused",         color: "bg-neutral-100 text-neutral-700", icon: Pause },
  cancelled:     { label: "Cancelled",      color: "bg-neutral-100 text-neutral-700", icon: XCircle },
  completed:     { label: "Completed",      color: "bg-neutral-100 text-neutral-700", icon: CheckCircle2 },
  expired:       { label: "Expired",        color: "bg-neutral-100 text-neutral-700", icon: XCircle },
};
const TERMINAL = new Set(["cancelled", "completed", "expired"]);

function StatusChip({ status }) {
  const meta = STATUS_STYLES[status] || {
    label: status || "unknown",
    color: "bg-neutral-100 text-neutral-700",
    icon: Repeat,
  };
  const Icon = meta.icon;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${meta.color}`}
      data-testid="subscription-status-chip"
    >
      <Icon className="h-3 w-3" /> {meta.label}
    </span>
  );
}

function frequencyLabel(freq) {
  const map = { monthly: "Monthly", quarterly: "Quarterly", half_yearly: "Half-yearly", yearly: "Yearly" };
  return map[freq] || freq;
}

function formatDate(v) {
  if (!v) return "—";
  try {
    const d = typeof v === "number" ? new Date(v * 1000) : new Date(v);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
  } catch {
    return "—";
  }
}

function inr(v) {
  return `₹${Number(v || 0).toLocaleString("en-IN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

function SubscriptionCard({ sub, onCancel, onRetry, cancelling, retrying }) {
  const status = String(sub.status || "").toLowerCase();
  const isTerminal = TERMINAL.has(status);
  const isHalted = status === "halted";
  const amount = sub.amount_rupees ?? (sub.breakdown && sub.breakdown.total) ?? 0;
  const paid = sub.paid_count ?? 0;
  const total = sub.total_count ?? "-";
  const nextCharge = sub.current_end;

  return (
    <div className="rw-card p-4" data-testid={`subscription-card-${sub.subscription_id}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Repeat className="h-4 w-4 text-[hsl(var(--rw-royal))]" />
            <h3 className="rw-serif truncate text-lg text-[hsl(var(--rw-royal-deep))]">
              {sub.program_name || "Subscription"}
            </h3>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <StatusChip status={status} />
            <span className="text-[11px] text-muted-foreground">
              {frequencyLabel(sub.frequency)} · {inr(amount)} / cycle
            </span>
          </div>
          {sub.is_mock && (
            <span className="mt-1 inline-block rounded bg-neutral-100 px-1.5 py-0.5 text-[10px] font-mono text-neutral-500">
              sandbox
            </span>
          )}
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-lg bg-neutral-50 p-2">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Cycles charged</div>
          <div className="mt-0.5 font-semibold">{paid} / {total}</div>
        </div>
        <div className="rounded-lg bg-neutral-50 p-2">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Next charge</div>
          <div className="mt-0.5 flex items-center gap-1 font-semibold">
            <CalendarClock className="h-3 w-3" />
            {isTerminal ? "—" : formatDate(nextCharge)}
          </div>
        </div>
      </div>

      {sub.cancel_at_cycle_end && !isTerminal && (
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-2 text-[11px] text-amber-800">
          Cancellation scheduled — access continues until {formatDate(nextCharge)}.
        </div>
      )}

      {isHalted && (
        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-2 text-[11px] text-red-800">
          Auto-renewal stopped after multiple failed charges. Your current cycle
          access continues until it naturally expires. Start a fresh mandate to
          keep the subscription alive.
        </div>
      )}

      {isHalted && onRetry && (
        <button
          onClick={() => onRetry(sub)}
          disabled={retrying === sub.subscription_id}
          className="mt-3 w-full rounded-lg bg-red-600 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-60"
          data-testid={`subscription-retry-btn-${sub.subscription_id}`}
        >
          {retrying === sub.subscription_id ? (
            <span className="inline-flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Starting new mandate…
            </span>
          ) : (
            <span className="inline-flex items-center gap-2">
              <RotateCw className="h-3.5 w-3.5" /> Retry with new mandate
            </span>
          )}
        </button>
      )}

      {!isTerminal && !isHalted && (
        <button
          onClick={() => onCancel(sub)}
          disabled={cancelling === sub.subscription_id}
          className="mt-3 w-full rounded-lg border border-red-200 py-2 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:opacity-60"
          data-testid={`subscription-cancel-btn-${sub.subscription_id}`}
        >
          {cancelling === sub.subscription_id ? (
            <span className="inline-flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Cancelling…
            </span>
          ) : (
            "Cancel subscription"
          )}
        </button>
      )}

      <div className="mt-3 flex items-center justify-between text-[10px] font-mono text-muted-foreground">
        <span>Since {formatDate(sub.created_at)}</span>
        <span className="truncate">{sub.subscription_id}</span>
      </div>
    </div>
  );
}

function ConfirmDialog({ open, sub, onConfirm, onClose, working }) {
  if (!open || !sub) return null;
  const s = String(sub.status || "").toLowerCase();
  const isPending = s === "created" || s === "pending";
  return (
    <div
      className="fixed inset-0 z-[100] flex items-end justify-center bg-black/50 backdrop-blur-sm sm:items-center"
      onClick={() => (!working ? onClose() : null)}
      data-testid="subscription-cancel-dialog"
    >
      <div
        className="w-full max-w-md rounded-t-3xl bg-white p-6 sm:rounded-3xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="rw-serif text-2xl text-[hsl(var(--rw-royal-deep))]">Cancel subscription?</h2>
        <p className="mt-2 text-sm text-muted-foreground">{sub.program_name}</p>
        <div className="mt-4 rounded-lg bg-neutral-50 p-3 text-xs text-muted-foreground">
          {isPending ? (
            <>The mandate is not yet authenticated — cancelling now stops the setup. No cycles will be charged.</>
          ) : (
            <>
              Access continues until <b>{formatDate(sub.current_end)}</b>. No further cycles will be charged. This can&apos;t be undone.
            </>
          )}
        </div>
        <div className="mt-5 flex items-center justify-end gap-2">
          <button
            onClick={onClose}
            disabled={working}
            className="rw-btn-pill rw-btn-ghost"
            data-testid="subscription-cancel-dismiss"
          >
            Keep subscription
          </button>
          <button
            onClick={onConfirm}
            disabled={working}
            className="rw-btn-pill bg-red-600 text-white hover:bg-red-700 disabled:opacity-60"
            data-testid="subscription-cancel-confirm"
          >
            {working ? (
              <span className="inline-flex items-center gap-2">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Cancelling…
              </span>
            ) : (
              "Cancel now"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function MySubscriptions() {
  const nav = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState("");
  const [retrying, setRetrying] = useState("");
  const [confirm, setConfirm] = useState({ open: false, sub: null });
  const [retryModal, setRetryModal] = useState({ open: false, programId: null });

  const load = async () => {
    setLoading(true);
    try {
      const r = await paymentsApi.mySubscriptions();
      setItems(r.items || []);
    } catch (e) {
      toast.error(formatApiError(e, "Could not load subscriptions"));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const openCancel = (sub) => setConfirm({ open: true, sub });
  const closeCancel = () => setConfirm({ open: false, sub: null });

  const doCancel = async () => {
    const sub = confirm.sub;
    if (!sub) return;
    setCancelling(sub.subscription_id);
    try {
      const res = await paymentsApi.subscriptionCancel(sub.subscription_id);
      if (res.already_terminal) toast.info(`Subscription is already ${res.status}.`);
      else if (res.cancel_at_cycle_end) toast.success("Cancellation scheduled — access continues until the current cycle ends.");
      else toast.success("Subscription cancelled.");
      closeCancel();
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Could not cancel subscription"));
    } finally {
      setCancelling("");
    }
  };

  // Retry after a halted subscription — opens the checkout modal with the
  // original program_id. The old halted row is left as-is; the reuse logic
  // in /subscription/init skips terminal-status rows and creates a fresh
  // mandate on Razorpay.
  const doRetry = (sub) => {
    if (!sub.program_id) {
      toast.error("Cannot retry — program reference missing.");
      return;
    }
    setRetrying(sub.subscription_id);
    setRetryModal({ open: true, programId: sub.program_id });
    setTimeout(() => setRetrying(""), 500);
  };

  const active = items.filter((s) => !TERMINAL.has(String(s.status || "").toLowerCase()));
  const past = items.filter((s) => TERMINAL.has(String(s.status || "").toLowerCase()));

  return (
    <div className="px-5 pb-24 pt-4" data-testid="my-subscriptions-page">
      <div className="flex items-center gap-3">
        <button
          onClick={() => nav(-1)}
          className="grid h-10 w-10 place-items-center rounded-full bg-neutral-100"
          data-testid="subscriptions-back"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <div className="flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-[hsl(var(--rw-royal))]">
            My subscriptions
          </p>
          <h1 className="rw-serif text-3xl text-[hsl(var(--rw-royal-deep))]">AutoPay mandates</h1>
        </div>
      </div>

      <p className="mt-2 text-xs text-muted-foreground">
        Manage the Razorpay UPI mandates that renew your subscription programs each cycle. You can cancel any time.
      </p>

      {loading ? (
        <div className="mt-10 grid place-items-center py-10 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <div className="mt-6 rounded-2xl border border-dashed p-8 text-center" data-testid="subscriptions-empty">
          <Repeat className="mx-auto h-8 w-8 text-muted-foreground" />
          <p className="mt-3 text-sm text-muted-foreground">
            You don&apos;t have any subscriptions yet.
          </p>
          <button onClick={() => nav("/app/programs")} className="mt-4 rw-btn-pill rw-btn-primary" data-testid="subscriptions-browse">
            Browse programs
          </button>
        </div>
      ) : (
        <>
          {active.length > 0 && (
            <section className="mt-6">
              <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                Active · {active.length}
              </h2>
              <div className="mt-3 space-y-3" data-testid="subscriptions-active-list">
                {active.map((s) => (
                  <SubscriptionCard
                    key={s.id || s.subscription_id}
                    sub={s}
                    onCancel={openCancel}
                    onRetry={doRetry}
                    cancelling={cancelling}
                    retrying={retrying}
                  />
                ))}
              </div>
            </section>
          )}
          {past.length > 0 && (
            <section className="mt-8">
              <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                Past · {past.length}
              </h2>
              <div className="mt-3 space-y-3" data-testid="subscriptions-past-list">
                {past.map((s) => (
                  <SubscriptionCard
                    key={s.id || s.subscription_id}
                    sub={s}
                    onCancel={openCancel}
                    onRetry={doRetry}
                    cancelling={cancelling}
                    retrying={retrying}
                  />
                ))}
              </div>
            </section>
          )}
        </>
      )}

      <ConfirmDialog
        open={confirm.open}
        sub={confirm.sub}
        working={cancelling === confirm.sub?.subscription_id}
        onConfirm={doCancel}
        onClose={closeCancel}
      />

      <SubscriptionCheckoutModal
        open={retryModal.open}
        onOpenChange={(v) => setRetryModal({ open: v, programId: retryModal.programId })}
        programId={retryModal.programId}
        onSuccess={() => {
          setRetryModal({ open: false, programId: null });
          toast.success("New mandate started · welcome back!");
          load();
        }}
      />
    </div>
  );
}
