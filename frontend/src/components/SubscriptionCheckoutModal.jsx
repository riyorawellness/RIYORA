import { useEffect, useState } from "react";
import {
  CheckCircle2,
  IndianRupee,
  Loader2,
  Repeat,
  ShieldCheck,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { paymentsApi, loadRazorpayScript } from "@/services/payments";
import { formatApiError } from "@/lib/api";

/**
 * SubscriptionCheckoutModal — Razorpay AutoPay / UPI mandate checkout.
 *
 *   1. /payments/subscription/init  → subscription_id + plan_id + key_id
 *   2. Razorpay Checkout opens with { subscription_id }
 *   3. handler / dismiss → /payments/subscription/{sid}/verify polls for
 *      authoritative status. If mandate authenticated AND first charge
 *      captured, the backend materialises a program_purchases row and
 *      returns { purchase_id, expiry_date }.
 */
export default function SubscriptionCheckoutModal({
  open,
  onOpenChange,
  programId,
  onSuccess,
}) {
  const [session, setSession] = useState(null);
  const [status, setStatus] = useState("idle"); // idle|loading|ready|processing|success|error
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open || !programId) return;
    setStatus("loading");
    setError("");
    (async () => {
      try {
        const data = await paymentsApi.subscriptionInit(programId);
        setSession(data);
        setStatus("ready");
      } catch (e) {
        setError(formatApiError(e, "Could not initialise subscription."));
        setStatus("error");
      }
    })();
  }, [open, programId]);

  const close = () => {
    if (status === "processing") return;
    onOpenChange(false);
    setTimeout(() => {
      setSession(null);
      setStatus("idle");
      setError("");
    }, 200);
  };

  const runMock = async () => {
    setStatus("processing");
    try {
      const res = await paymentsApi.subscriptionVerify(session.subscription_id);
      setStatus("success");
      toast.success("Mandate active — first cycle charged.");
      onSuccess?.(res);
    } catch (e) {
      setStatus("ready");
      setError(formatApiError(e, "Could not verify subscription"));
    }
  };

  const pollVerify = async () => {
    setStatus("processing");
    // Poll up to 8 × 2s = 16s to let subscription.charged webhook arrive.
    for (let attempt = 0; attempt < 8; attempt++) {
      try {
        const res = await paymentsApi.subscriptionVerify(session.subscription_id);
        const done = res.purchase_id || res.status === "active";
        if (done && res.purchase_id) {
          setStatus("success");
          toast.success("Mandate active — first cycle charged.");
          onSuccess?.(res);
          return;
        }
      } catch (_) {
        /* transient — retry */
      }
      await new Promise((r) => setTimeout(r, 2000));
    }
    setStatus("ready");
    setError(
      "The mandate could not be confirmed. Common reasons: you cancelled the UPI approval, your bank declined the mandate, or the app timed out. Please tap Subscribe again and use a different UPI ID if the issue continues.",
    );
  };

  const runLive = async () => {
    const Rzp = await loadRazorpayScript();
    if (!Rzp) {
      setError("Could not load Razorpay Checkout. Check your connection.");
      return;
    }
    const opts = {
      key: session.key_id,
      subscription_id: session.subscription_id,
      name: "RIYORA Wellness",
      description: `${session.program?.name || "Subscription"} · ${
        session.program?.subscription_frequency || ""
      }`,
      prefill: {
        name: session.prefill?.name,
        email: session.prefill?.email,
        contact: session.prefill?.contact,
      },
      notes: {
        program_id: session.program?.id,
        subscription_id: session.subscription_id,
      },
      theme: { color: "#0B1A5B" },
      recurring: 1,
      retry: { enabled: false },
      handler: async () => {
        pollVerify();
      },
      modal: {
        ondismiss: () => {
          if (status === "processing") return;
          pollVerify();
        },
      },
    };
    const rzp = new Rzp(opts);
    rzp.open();
  };

  const pay = () => (session?.is_mock ? runMock() : runLive());

  if (!open) return null;
  const breakdown = session?.breakdown || {};
  const freqLabel = (session?.program?.subscription_frequency || "").replace("_", "-");

  return (
    <div
      className="fixed inset-0 z-[100] flex items-end justify-center bg-black/50 backdrop-blur-sm sm:items-center"
      onClick={close}
      data-testid="subscription-checkout-modal"
    >
      <div
        className="w-full max-w-md rounded-t-3xl bg-white p-6 sm:rounded-3xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-[hsl(var(--rw-royal))]" />
            <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-[hsl(var(--rw-royal))]">
              AutoPay Mandate
            </p>
          </div>
          <button
            onClick={close}
            className="grid h-9 w-9 place-items-center rounded-full bg-neutral-100"
            data-testid="subscription-close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {status === "loading" && (
          <div className="grid place-items-center py-14 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin" />
            <p className="mt-2 text-sm">Setting up your mandate…</p>
          </div>
        )}

        {status === "error" && (
          <div className="rounded-2xl bg-red-50 p-4 text-sm text-red-700">
            {error || "Something went wrong."}
            <button className="mt-3 rw-btn-pill rw-btn-primary" onClick={close}>
              Close
            </button>
          </div>
        )}

        {session && (status === "ready" || status === "processing" || status === "success") && (
          <>
            <h2 className="rw-serif text-3xl">{session.program?.name}</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Renews {freqLabel} · You can cancel anytime.
            </p>

            <div className="mt-5 space-y-2 rounded-2xl bg-neutral-50 p-4 text-sm">
              <Row k="Cycle price" v={inr(breakdown.price)} />
              {breakdown.discount > 0 && <Row k="Discount" v={`- ${inr(breakdown.discount)}`} />}
              <Row k="Sub-total" v={inr(breakdown.taxable)} />
              <Row k={`GST @ ${breakdown.gst_percent ?? 18}%`} v={inr(breakdown.gst_amount)} />
              <div className="my-2 h-px bg-neutral-200" />
              <div className="flex items-baseline justify-between">
                <span className="text-xs uppercase tracking-widest text-muted-foreground">
                  Charged each {freqLabel}
                </span>
                <span className="rw-serif text-2xl text-[hsl(var(--rw-royal-deep))]">
                  {inr(breakdown.total)}
                </span>
              </div>
            </div>

            <div className="mt-4 flex items-start gap-2 rounded-xl border border-[hsl(var(--rw-royal))]/20 bg-[hsl(var(--rw-sky-soft))] p-3 text-xs text-[hsl(var(--rw-royal-deep))]">
              <Repeat className="mt-0.5 h-3.5 w-3.5" />
              <div>
                First cycle is charged as soon as you approve the mandate on your
                UPI app. Every subsequent cycle debits automatically until you
                cancel.
              </div>
            </div>

            {session.is_mock && (
              <div
                className="mt-3 flex items-start gap-2 rounded-xl border border-[hsl(var(--rw-gold))] bg-[hsl(var(--rw-gold-soft))] p-3 text-xs text-[hsl(35_60%_28%)]"
                data-testid="subscription-mock-banner"
              >
                <IndianRupee className="mt-0.5 h-3.5 w-3.5" />
                <div>
                  <b>Sandbox mode.</b> Tap Subscribe to simulate a successful mandate.
                </div>
              </div>
            )}

            {error && (
              <div className="mt-3 rounded-xl bg-red-50 p-3 text-xs text-red-700">
                {error}
              </div>
            )}

            <button
              className="mt-5 flex w-full items-center justify-center gap-2 rw-btn-pill rw-btn-primary py-3 disabled:opacity-60"
              disabled={status === "processing" || status === "success"}
              onClick={pay}
              data-testid="subscription-pay-btn"
            >
              {status === "processing" ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Verifying mandate…
                </>
              ) : status === "success" ? (
                <>
                  <CheckCircle2 className="h-4 w-4" /> Mandate active
                </>
              ) : (
                <>
                  <Repeat className="h-4 w-4" /> Subscribe · {inr(breakdown.total)}
                </>
              )}
            </button>

            <p className="mt-3 text-center text-[10px] text-muted-foreground">
              Powered by Razorpay AutoPay · UPI Mandate · NPCI-compliant
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{k}</span>
      <span className="font-medium">{v}</span>
    </div>
  );
}

function inr(v) {
  return `₹${Number(v || 0).toLocaleString("en-IN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}
