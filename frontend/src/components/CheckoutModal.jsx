import { useEffect, useState } from "react";
import { CheckCircle2, CreditCard, IndianRupee, ShieldCheck, X, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { paymentsApi, loadRazorpayScript } from "@/services/payments";
import { formatApiError } from "@/lib/api";

/**
 * CheckoutModal — end-to-end Razorpay checkout in a bottom-sheet.
 *
 * Props:
 *   open       — boolean
 *   onOpenChange(bool)
 *   programId  — string
 *   onSuccess({ purchase_id, invoice_number, expiry_date, amount })
 */
export default function CheckoutModal({ open, onOpenChange, programId, onSuccess }) {
  const [order, setOrder] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | loading | ready | processing | success | error
  const [error, setError] = useState("");
  const [config, setConfig] = useState(null);

  useEffect(() => {
    if (!open || !programId) return;
    setStatus("loading");
    setError("");
    (async () => {
      try {
        const [cfg, ord] = await Promise.all([
          paymentsApi.config(),
          paymentsApi.createOrder(programId),
        ]);
        setConfig(cfg);
        setOrder(ord);
        setStatus("ready");
      } catch (e) {
        setError(formatApiError(e, "Could not initialise payment."));
        setStatus("error");
      }
    })();
  }, [open, programId]);

  const close = () => {
    if (status === "processing") return;
    onOpenChange(false);
    setTimeout(() => {
      setOrder(null);
      setStatus("idle");
      setError("");
    }, 200);
  };

  const runMockPayment = async () => {
    setStatus("processing");
    try {
      const res = await paymentsApi.verifyPayment({
        order_id: order.order_id,
        payment_id: `pay_mock_${Date.now()}`,
        signature: `mock_sig_${order.order_id}`,
      });
      setStatus("success");
      toast.success("Payment verified — access unlocked");
      onSuccess?.(res);
    } catch (e) {
      setStatus("ready");
      setError(formatApiError(e, "Payment verification failed"));
    }
  };

  const runLivePayment = async () => {
    const Rzp = await loadRazorpayScript();
    if (!Rzp) {
      setError("Could not load Razorpay Checkout. Check your connection.");
      return;
    }
    const opts = {
      key: order.key_id,
      amount: order.amount_paise,
      currency: order.currency,
      order_id: order.order_id,
      name: "RIYORA Wellness",
      description: order.program?.name || "Program purchase",
      image: undefined,
      prefill: {
        name: order.prefill?.name,
        contact: order.prefill?.contact,
      },
      notes: order.notes,
      theme: { color: config?.checkout_theme?.color || "#0B1A5B" },
      handler: async (rzpResponse) => {
        setStatus("processing");
        try {
          const res = await paymentsApi.verifyPayment({
            order_id: rzpResponse.razorpay_order_id,
            payment_id: rzpResponse.razorpay_payment_id,
            signature: rzpResponse.razorpay_signature,
          });
          setStatus("success");
          toast.success("Payment successful");
          onSuccess?.(res);
        } catch (e) {
          setStatus("ready");
          setError(formatApiError(e, "Payment verification failed"));
        }
      },
      modal: {
        ondismiss: () => {
          if (status === "processing") return;
          setStatus("ready");
        },
      },
    };
    const rzp = new Rzp(opts);
    rzp.open();
  };

  const pay = () => (order?.is_mock ? runMockPayment() : runLivePayment());

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-end justify-center bg-black/50 backdrop-blur-sm sm:items-center"
      onClick={close}
      data-testid="checkout-modal"
    >
      <div
        className="w-full max-w-md rounded-t-3xl bg-white p-6 sm:rounded-3xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-[hsl(var(--rw-royal))]" />
            <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-[hsl(var(--rw-royal))]">
              Secure Checkout
            </p>
          </div>
          <button
            onClick={close}
            className="grid h-9 w-9 place-items-center rounded-full bg-neutral-100"
            data-testid="checkout-close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {status === "loading" && (
          <div className="grid place-items-center py-14 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin" />
            <p className="mt-2 text-sm">Preparing your order…</p>
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

        {order && (status === "ready" || status === "processing" || status === "success") && (
          <>
            <h2 className="rw-serif text-3xl">{order.program?.name}</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {order.program?.validity_days
                ? `Valid ${order.program.validity_days} days`
                : "One-time purchase"}
            </p>

            <div className="mt-5 space-y-2 rounded-2xl bg-neutral-50 p-4 text-sm">
              <Row k="Price" v={inr(order.breakdown.price)} />
              {order.breakdown.discount > 0 && (
                <Row k="Discount" v={`- ${inr(order.breakdown.discount)}`} />
              )}
              <Row k="Sub-total" v={inr(order.breakdown.taxable)} />
              <Row
                k={`GST @ ${order.breakdown.gst_percent}%`}
                v={inr(order.breakdown.gst_amount)}
              />
              <div className="my-2 h-px bg-neutral-200" />
              <div className="flex items-baseline justify-between">
                <span className="text-xs uppercase tracking-widest text-muted-foreground">
                  Total
                </span>
                <span className="rw-serif text-2xl text-[hsl(var(--rw-royal-deep))]">
                  {inr(order.breakdown.total)}
                </span>
              </div>
            </div>

            {order.is_mock && (
              <div
                className="mt-4 flex items-start gap-2 rounded-xl border border-[hsl(var(--rw-gold))] bg-[hsl(var(--rw-gold-soft))] p-3 text-xs text-[hsl(35_60%_28%)]"
                data-testid="checkout-mock-banner"
              >
                <IndianRupee className="mt-0.5 h-3.5 w-3.5" />
                <div>
                  <b>Sandbox mode.</b> No real charge — Razorpay keys are not yet
                  configured. Tap Pay to simulate a successful transaction.
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
              data-testid="checkout-pay-btn"
            >
              {status === "processing" ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Verifying…
                </>
              ) : status === "success" ? (
                <>
                  <CheckCircle2 className="h-4 w-4" /> Access unlocked
                </>
              ) : (
                <>
                  <CreditCard className="h-4 w-4" /> Pay {inr(order.breakdown.total)}
                </>
              )}
            </button>

            <p className="mt-3 text-center text-[10px] text-muted-foreground">
              Powered by Razorpay · UPI · Cards · NetBanking · Wallets
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
