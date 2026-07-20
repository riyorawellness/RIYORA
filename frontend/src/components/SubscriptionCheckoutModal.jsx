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
import api, { formatApiError } from "@/lib/api";

// Fire-and-forget diagnostic logger. Every state transition of the
// subscription checkout is captured backend-side so we can trace what
// happens on the user's phone without DevTools access.
function debugLog(stage, extra = {}) {
  try {
    api.post("/payments/subscription/debug-log", {
      stage,
      subscription_id: extra.subscription_id ?? null,
      program_id: extra.program_id ?? null,
      ok: extra.ok ?? true,
      message: extra.message ?? "",
      payload: extra.payload ?? null,
      error: extra.error ?? null,
    }).catch(() => {});
  } catch (_) {
    /* ignore — logging must never break the flow */
  }
}

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
    debugLog("modal.open", { program_id: programId });
    (async () => {
      try {
        const data = await paymentsApi.subscriptionInit(programId);
        setSession(data);
        setStatus("ready");
        debugLog("init.response_ok", {
          program_id: programId,
          subscription_id: data.subscription_id,
          payload: {
            is_mock: data.is_mock,
            status: data.status,
            plan_id: data.plan_id,
            amount_paise: data.amount_paise,
            short_url: data.short_url,
            reused: data.reused,
          },
        });
      } catch (e) {
        const msg = formatApiError(e, "Could not initialise subscription.");
        setError(msg);
        setStatus("error");
        debugLog("init.response_error", {
          program_id: programId,
          ok: false,
          message: msg,
          error: {
            status: e?.response?.status,
            data: e?.response?.data,
          },
        });
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
    debugLog("poll.start", { subscription_id: session.subscription_id });
    // 20 × 2s = 40s window. Razorpay Checkout SDK sometimes closes with a
    // misleading "Payment could not be completed" screen before the
    // subscription actually transitions to active on their side — the
    // backend verify endpoint now polls Razorpay's API directly and
    // materialises the purchase as soon as `paid_count >= 1`, independent
    // of the merchant's webhook plumbing.
    for (let attempt = 0; attempt < 20; attempt++) {
      try {
        const res = await paymentsApi.subscriptionVerify(session.subscription_id);
        debugLog("poll.tick", {
          subscription_id: session.subscription_id,
          payload: { attempt: attempt + 1, ...res },
        });
        const done = res.purchase_id || res.status === "active";
        if (done && res.purchase_id) {
          setStatus("success");
          toast.success("Mandate active — first cycle charged.");
          debugLog("poll.success", { subscription_id: session.subscription_id, payload: res });
          onSuccess?.(res);
          return;
        }
      } catch (e) {
        debugLog("poll.error", {
          subscription_id: session.subscription_id, ok: false,
          error: { status: e?.response?.status, data: e?.response?.data },
        });
      }
      await new Promise((r) => setTimeout(r, 2000));
    }
    setStatus("ready");
    setError(
      "We are still waiting for Razorpay to confirm your mandate. If you " +
      "received an SMS saying the payment was successful, your access will " +
      "activate automatically within a few minutes — refresh this page or " +
      "check My Subscriptions. Otherwise please try again.",
    );
    debugLog("poll.timeout", { subscription_id: session.subscription_id, ok: false });
  };

  const runLive = async () => {
    const Rzp = await loadRazorpayScript();
    if (!Rzp) {
      setError("Could not load Razorpay Checkout. Check your connection.");
      return;
    }
    // -----------------------------------------------------------------
    // Razorpay Subscription Checkout — key differences vs one-time:
    //   • method: { upi: true }          → force UPI as primary tender
    //     (without this Razorpay defaults to card and instantly closes
    //     because UPI mandates need explicit method selection)
    //   • recurring: 1                   → tells Checkout this is a mandate,
    //     not a one-shot payment
    //   • retry: { enabled: true, max_count: 4 } → Razorpay's own retry
    //     helps when the first UPI app times out
    //   • rzp.on('payment.failed', ...)  → capture the ACTUAL error
    //     ('International cards not allowed on subscriptions', 'AutoPay
    //     not enabled for merchant', 'Amount exceeds UPI mandate limit',
    //     etc.) instead of silently closing.
    // Ref: https://razorpay.com/docs/payments/subscriptions/ +
    //      https://razorpay.com/docs/payments/subscriptions/supported-payment-methods/
    // -----------------------------------------------------------------
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
      method: { upi: true, card: true, netbanking: false, wallet: false },
      retry: { enabled: true, max_count: 4 },
      handler: async (resp) => {
        debugLog("razorpay.handler_success", {
          subscription_id: session.subscription_id,
          payload: {
            razorpay_payment_id: resp?.razorpay_payment_id,
            razorpay_subscription_id: resp?.razorpay_subscription_id,
          },
        });
        pollVerify();
      },
      modal: {
        ondismiss: () => {
          debugLog("razorpay.modal_dismissed", {
            subscription_id: session.subscription_id,
            payload: { at_status: status },
          });
          if (status === "processing") return;
          pollVerify();
        },
      },
    };
    debugLog("razorpay.opts_built", {
      subscription_id: session.subscription_id,
      payload: {
        key: opts.key,
        subscription_id: opts.subscription_id,
        recurring: opts.recurring,
        method: opts.method,
        retry: opts.retry,
        // ⚠ diagnostic: UA + platform tells us if the phone browser is
        // rejecting the iframe / running out of memory / etc.
        ua: typeof navigator !== "undefined" ? navigator.userAgent : null,
      },
    });
    const rzp = new Rzp(opts);
    rzp.on("payment.failed", (resp) => {
      const err = resp?.error || {};
      const parts = [
        err.description,
        err.reason,
        err.source && `source=${err.source}`,
        err.step && `step=${err.step}`,
        err.code && `code=${err.code}`,
      ].filter(Boolean);
      const msg = parts.length ? parts.join(" · ") : "Razorpay declined the payment.";
      setStatus("ready");
      setError(msg);
      debugLog("razorpay.payment_failed", {
        subscription_id: session.subscription_id,
        ok: false,
        message: msg,
        error: {
          code: err.code,
          description: err.description,
          reason: err.reason,
          source: err.source,
          step: err.step,
          metadata: err.metadata,
        },
      });
      console.error("[Razorpay Subscription] payment.failed:", resp);
    });
    debugLog("razorpay.open_called", { subscription_id: session.subscription_id });
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
