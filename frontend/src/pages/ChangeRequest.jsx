import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Clock, Loader2, ShieldAlert, XCircle, CheckCircle2 } from "lucide-react";

import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";

/**
 * User-side change request page. Users cannot directly change their email
 * or mobile — instead they submit a request here. An admin reviews and
 * approves/rejects it via the AdminChangeRequests screen.
 */
export default function ChangeRequestPage() {
  const nav = useNavigate();
  const { user, submitChangeRequest, listMyChangeRequests } = useAuth();
  const [field, setField] = useState("email");
  const [newValue, setNewValue] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const d = await listMyChangeRequests();
      setRequests(d.items || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!newValue.trim()) return toast.error("Enter the new value");
    if (field === "mobile" && !/^[6-9]\d{9}$/.test(newValue)) {
      return toast.error("Enter a valid 10-digit Indian mobile");
    }
    setBusy(true);
    try {
      await submitChangeRequest({ field, new_value: newValue.trim(), reason: reason.trim() || null });
      toast.success("Request submitted. An admin will review it shortly.");
      setNewValue("");
      setReason("");
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  if (!user) return null;
  const current = user[field];

  return (
    <div className="px-5 pt-6 pb-24" data-testid="change-request-page">
      <button
        onClick={() => nav("/app/profile")}
        className="mb-4 inline-flex items-center gap-2 text-xs font-semibold text-[hsl(var(--rw-royal))]"
        data-testid="cr-back"
      >
        <ArrowLeft className="h-3 w-3" /> Back to profile
      </button>
      <p className="rw-eyebrow">Request change</p>
      <h1 className="mt-1 rw-serif text-4xl">Email / Mobile</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        These identifiers can only be changed after admin approval. We keep a full audit trail.
      </p>

      <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-[11px] text-amber-900">
        <ShieldAlert className="mr-1 inline h-3.5 w-3.5" />
        Your <span className="font-semibold">current {field}</span>:{" "}
        <span className="font-mono">{current || "—"}</span>
      </div>

      <form className="mt-6 space-y-4" onSubmit={submit}>
        <div>
          <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Which field?</label>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {["email", "mobile"].map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setField(f)}
                className={`rw-btn-pill w-full text-sm ${field === f ? "rw-btn-primary" : "border border-neutral-200 bg-white text-foreground"}`}
                data-testid={`cr-field-${f}`}
              >
                {f === "email" ? "Email" : "Mobile"}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            New {field}
          </label>
          <input
            className="rw-input mt-1"
            type={field === "email" ? "email" : "tel"}
            inputMode={field === "mobile" ? "numeric" : "text"}
            maxLength={field === "mobile" ? 10 : 120}
            value={newValue}
            onChange={(e) => setNewValue(field === "mobile" ? e.target.value.replace(/\D/g, "").slice(0,10) : e.target.value)}
            data-testid="cr-new-value"
          />
        </div>

        <div>
          <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Reason (optional)</label>
          <textarea
            className="rw-input mt-1 min-h-[70px]"
            rows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            data-testid="cr-reason"
          />
        </div>

        <button type="submit" className="rw-btn-pill rw-btn-primary w-full" disabled={busy} data-testid="cr-submit">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Submit request
        </button>
      </form>

      <div className="mt-8">
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">Your requests</p>
        {loading ? (
          <div className="grid place-items-center p-6"><Loader2 className="h-5 w-5 animate-spin text-primary" /></div>
        ) : requests.length === 0 ? (
          <div className="rounded-xl border border-dashed border-neutral-200 p-6 text-center text-xs text-muted-foreground" data-testid="cr-empty">
            No requests yet.
          </div>
        ) : (
          <ul className="space-y-2" data-testid="cr-list">
            {requests.map((r) => (
              <li key={r.id} className="rounded-xl border border-neutral-200 p-3">
                <div className="flex items-center gap-2">
                  <StatusBadge s={r.status} />
                  <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{r.field}</span>
                  <span className="ml-auto text-[10px] text-muted-foreground">{r.requested_at?.slice(0,16).replace("T"," ")}</span>
                </div>
                <div className="mt-2 text-xs">
                  <span className="text-muted-foreground">From </span>
                  <span className="font-mono">{r.current_value || "—"}</span>
                  <span className="text-muted-foreground"> → </span>
                  <span className="font-mono">{r.new_value}</span>
                </div>
                {r.reason && <div className="mt-1 text-[11px] text-muted-foreground">Reason: {r.reason}</div>}
                {r.reviewer_note && <div className="mt-1 text-[11px] text-muted-foreground">Admin note: {r.reviewer_note}</div>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ s }) {
  if (s === "approved") return (
    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
      <CheckCircle2 className="h-3 w-3" /> Approved
    </span>
  );
  if (s === "rejected") return (
    <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-semibold text-red-700">
      <XCircle className="h-3 w-3" /> Rejected
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-800">
      <Clock className="h-3 w-3" /> Pending
    </span>
  );
}
