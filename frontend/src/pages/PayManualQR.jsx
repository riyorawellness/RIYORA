import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft, CheckCircle2, Copy, Loader2, Upload, Image as ImageIcon,
  ShieldCheck, Clock,
} from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { manualPaymentsApi, resolveUploadUrl } from "@/services/manualPayments";
import { formatApiError } from "@/lib/api";

export default function PayManualQR() {
  const { programId } = useParams();
  const nav = useNavigate();
  const [quote, setQuote] = useState(null);
  const [qr, setQr] = useState(null);
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState("pay"); // pay | form | done
  const [form, setForm] = useState({
    utr: "",
    transaction_date: new Date().toISOString().slice(0, 10),
    screenshot_url: "",
    remarks: "",
  });
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [q, k] = await Promise.all([
          manualPaymentsApi.getQuote(programId),
          manualPaymentsApi.getQR().catch(() => null),
        ]);
        setQuote(q);
        setQr(k);
        if (q.pending_request) setStep("done");
      } catch (e) {
        toast.error(formatApiError(e, "Could not load payment details"));
      } finally {
        setLoading(false);
      }
    })();
  }, [programId]);

  const copy = (text, label) => {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text);
      } else {
        // Fallback for non-secure contexts / older WebViews
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        ta.remove();
      }
      toast.success(`${label} copied`);
    } catch {
      toast.error("Could not copy — please copy manually");
    }
  };

  const doUpload = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const r = await manualPaymentsApi.uploadScreenshot(file);
      setForm((f) => ({ ...f, screenshot_url: r.url }));
      toast.success("Screenshot uploaded");
    } catch (e) {
      toast.error(formatApiError(e, "Upload failed"));
    } finally {
      setUploading(false);
    }
  };

  const doSubmit = async () => {
    if (!form.utr || form.utr.length < 6) return toast.error("Enter a valid UTR / RRN / Txn ID");
    if (!form.screenshot_url) return toast.error("Please upload the payment screenshot");
    setSubmitting(true);
    try {
      await manualPaymentsApi.submit({
        program_id: programId,
        utr: form.utr.trim(),
        transaction_date: form.transaction_date,
        screenshot_url: form.screenshot_url,
        remarks: form.remarks || undefined,
      });
      setStep("done");
      toast.success("Payment submitted. Awaiting verification.");
    } catch (e) {
      toast.error(formatApiError(e, "Could not submit payment"));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center bg-white text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  const program = quote?.program;
  const b = quote?.breakdown || {};

  return (
    <div className="min-h-screen bg-neutral-50 pb-24" data-testid="pay-manual-qr-page">
      {/* Header */}
      <div className="sticky top-0 z-10 border-b bg-white/95 backdrop-blur">
        <div className="rw-phone flex items-center gap-3 px-4 py-3">
          <button
            onClick={() => nav(-1)}
            className="grid h-9 w-9 place-items-center rounded-full hover:bg-neutral-100"
            data-testid="pay-back-btn"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div className="min-w-0 flex-1">
            <p className="rw-eyebrow">Complete payment</p>
            <h1 className="truncate rw-serif text-xl leading-tight">{program?.name}</h1>
          </div>
          <Badge variant="secondary">Manual QR</Badge>
        </div>
      </div>

      <div className="rw-phone space-y-4 px-4 pt-4">
        {/* Price breakdown */}
        <Card className="p-4" data-testid="pay-breakdown-card">
          <p className="rw-eyebrow">Amount to pay</p>
          <div className="mt-1 rw-serif text-4xl text-[hsl(var(--rw-royal))]">
            ₹{Number(b.total || 0).toLocaleString("en-IN")}
          </div>
          <div className="mt-3 space-y-1 text-xs text-muted-foreground">
            <Row k="Price" v={inr(b.price)} />
            <Row k="Discount" v={`-${inr(b.discount)}`} />
            <Row k={`GST @ ${b.gst_percent || 0}%`} v={inr(b.gst_amount)} />
            <div className="mt-2 border-t pt-2">
              <Row k={<span className="font-semibold text-foreground">Total</span>} v={<span className="font-semibold text-foreground">{inr(b.total)}</span>} />
            </div>
          </div>
        </Card>

        {step === "done" ? (
          <SuccessCard nav={nav} pending={quote?.pending_request} />
        ) : step === "form" ? (
          /* ============ Payment Submission Form ============ */
          <Card className="p-4" data-testid="pay-form-card">
            <p className="rw-eyebrow">Confirm your payment</p>
            <h2 className="rw-serif text-2xl">Enter transaction details</h2>

            <div className="mt-3 space-y-3">
              <Field label="UTR / RRN / Transaction ID *">
                <Input
                  value={form.utr}
                  onChange={(e) => setForm({ ...form, utr: e.target.value })}
                  placeholder="e.g. 428394857192"
                  maxLength={40}
                  data-testid="pay-utr-input"
                />
              </Field>
              <Field label="Transaction date *">
                <Input
                  type="date"
                  value={form.transaction_date}
                  onChange={(e) => setForm({ ...form, transaction_date: e.target.value })}
                  data-testid="pay-txndate-input"
                />
              </Field>
              <Field label="Payment screenshot *">
                <label className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed border-neutral-300 p-4 hover:border-[hsl(var(--rw-royal))]">
                  {form.screenshot_url ? (
                    <>
                      <img
                        src={resolveUploadUrl(form.screenshot_url)}
                        alt="screenshot"
                        className="h-32 rounded-md object-contain"
                      />
                      <span className="text-[11px] font-medium text-[hsl(var(--rw-royal))]">Replace image</span>
                    </>
                  ) : (
                    <>
                      {uploading ? (
                        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                      ) : (
                        <Upload className="h-6 w-6 text-muted-foreground" />
                      )}
                      <span className="text-xs text-muted-foreground">
                        {uploading ? "Uploading…" : "Tap to upload UPI receipt (PNG/JPG, ≤5 MB)"}
                      </span>
                    </>
                  )}
                  <input
                    type="file"
                    className="sr-only"
                    accept="image/*"
                    onChange={(e) => doUpload(e.target.files?.[0])}
                    data-testid="pay-screenshot-input"
                  />
                </label>
              </Field>
              <Field label="Remarks (optional)">
                <Textarea
                  rows={2}
                  value={form.remarks}
                  onChange={(e) => setForm({ ...form, remarks: e.target.value })}
                  placeholder="Any additional note for the admin"
                  data-testid="pay-remarks-input"
                />
              </Field>
            </div>

            <Button
              className="mt-4 w-full"
              onClick={doSubmit}
              disabled={submitting || uploading}
              data-testid="pay-submit-btn"
            >
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Submit for verification
            </Button>
          </Card>
        ) : (
          <>
            {/* ============ QR + UPI ============ */}
            <Card className="p-4" data-testid="pay-qr-card">
              <p className="rw-eyebrow">Scan &amp; pay</p>
              <h2 className="rw-serif text-2xl">{qr?.company_name || "RIYORA Wellness"}</h2>

              <div className="mt-3 flex flex-col items-center">
                {qr?.qr_image_url ? (
                  <img
                    src={resolveUploadUrl(qr.qr_image_url)}
                    alt="Company UPI QR"
                    className="h-64 w-64 rounded-2xl border-2 border-[hsl(var(--rw-royal))] bg-white p-2 object-contain"
                    data-testid="pay-qr-image"
                  />
                ) : (
                  <div className="grid h-64 w-64 place-items-center rounded-2xl border-2 border-dashed border-neutral-300 text-center text-xs text-muted-foreground">
                    <div>
                      <ImageIcon className="mx-auto mb-2 h-6 w-6" />
                      QR not configured.<br />Please contact support.
                    </div>
                  </div>
                )}

                {qr?.upi_id && (
                  <button
                    onClick={() => copy(qr.upi_id, "UPI ID")}
                    className="mt-3 flex items-center gap-2 rounded-full border bg-white px-4 py-2 text-sm font-medium hover:bg-neutral-50"
                    data-testid="pay-copy-upi-btn"
                  >
                    <span className="tabular-nums">{qr.upi_id}</span>
                    <Copy className="h-3.5 w-3.5" />
                  </button>
                )}

                {(qr?.account_number || qr?.ifsc) && (
                  <div className="mt-3 w-full space-y-1 rounded-lg bg-neutral-50 p-3 text-xs">
                    {qr?.account_holder_name && <Row k="Account holder" v={qr.account_holder_name} />}
                    {qr?.bank_name && <Row k="Bank" v={qr.bank_name} />}
                    {qr?.account_number && <Row k="A/C number" v={qr.account_number} />}
                    {qr?.ifsc && <Row k="IFSC" v={qr.ifsc} />}
                  </div>
                )}

                {qr?.payment_instructions && (
                  <div className="mt-3 w-full rounded-lg border-l-4 border-[hsl(var(--rw-gold))] bg-[hsl(var(--rw-sky-soft))] p-3 text-xs text-neutral-700" data-testid="pay-instructions">
                    <p className="font-semibold">Instructions</p>
                    <p className="mt-1 whitespace-pre-wrap">{qr.payment_instructions}</p>
                  </div>
                )}
              </div>
            </Card>

            <Card className="border-2 border-[hsl(var(--rw-royal))] p-4">
              <p className="text-xs text-muted-foreground">
                Complete the payment using any UPI app, then click below to submit the transaction details.
              </p>
              <Button
                className="mt-3 w-full"
                onClick={() => setStep("form")}
                data-testid="pay-done-btn"
              >
                <CheckCircle2 className="mr-2 h-4 w-4" /> I have completed the payment
              </Button>
            </Card>

            <p className="flex items-center justify-center gap-1 text-center text-[10px] text-muted-foreground">
              <ShieldCheck className="h-3 w-3" /> Access will be granted only after admin verification.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span>{k}</span>
      <span className="text-right tabular-nums">{v}</span>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function SuccessCard({ nav, pending }) {
  return (
    <Card className="border-2 border-amber-400 bg-amber-50 p-5" data-testid="pay-success-card">
      <div className="grid h-14 w-14 place-items-center rounded-full bg-amber-100 text-amber-700">
        <Clock className="h-6 w-6" />
      </div>
      <h2 className="mt-3 rw-serif text-2xl">Payment submitted</h2>
      <p className="mt-1 text-sm text-neutral-700">
        Your payment has been submitted successfully. Our team will verify your payment shortly.
        Access will be granted only after successful verification.
      </p>
      {pending?.utr && (
        <div className="mt-3 rounded-lg bg-white p-3 text-xs">
          <Row k="UTR" v={<span className="font-mono">{pending.utr}</span>} />
          <Row k="Amount" v={inr(pending.total)} />
          <Row k="Submitted" v={new Date(pending.submitted_at).toLocaleString()} />
        </div>
      )}
      <div className="mt-4 flex gap-2">
        <Button variant="secondary" className="flex-1" onClick={() => nav("/app/payment-history")} data-testid="pay-history-btn">
          Payment history
        </Button>
        <Button className="flex-1" onClick={() => nav("/app/home")} data-testid="pay-home-btn">
          Home
        </Button>
      </div>
    </Card>
  );
}

function inr(v) {
  if (v === null || v === undefined) return "—";
  return `₹${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}
