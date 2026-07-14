import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight, Loader2, ShieldCheck } from "lucide-react";

import Logo from "@/components/Logo";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";

/**
 * Step 2 of registration — after Firebase auth succeeds we land here with
 * {id_token, summary} in sessionStorage under `rw_pending_firebase`. Ask
 * for the RIYORA-specific fields (mobile mandatory, referral mandatory,
 * everything else optional) and post to /auth/firebase/register.
 */
export default function CompleteProfile() {
  const nav = useNavigate();
  const { registerWithFirebase } = useAuth();
  const [pending, setPending] = useState(null);
  const [form, setForm] = useState({
    full_name: "",
    mobile: "",
    referral_id: "",
    state: "",
    city: "",
    pincode: "",
    gender: "",
    dob: "",
    address: "",
  });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const raw = sessionStorage.getItem("rw_pending_firebase");
    if (!raw) {
      toast.error("Session expired — please sign in again.");
      nav("/register", { replace: true });
      return;
    }
    const p = JSON.parse(raw);
    setPending(p);
    setForm((f) => ({ ...f, full_name: p.full_name_hint || p.summary?.name || "" }));
  }, [nav]);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    if (!/^[6-9]\d{9}$/.test(form.mobile)) return toast.error("Enter a valid 10-digit Indian mobile");
    if (!/^RW\d{6}$/.test(form.referral_id)) return toast.error("Referral ID must be RW followed by 6 digits (e.g. RW000000).");
    if (!form.full_name || form.full_name.length < 2) return toast.error("Enter your full name");

    setBusy(true);
    try {
      await registerWithFirebase({
        id_token: pending.id_token,
        mobile: form.mobile,
        referral_id: form.referral_id.trim().toUpperCase(),
        full_name: form.full_name,
        state: form.state,
        city: form.city,
        pincode: form.pincode || null,
        gender: form.gender || null,
        dob: form.dob || null,
        address: form.address || null,
      });
      sessionStorage.removeItem("rw_pending_firebase");
      toast.success("Welcome to RIYORA!");
      nav("/app/home", { replace: true });
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  if (!pending) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="rw-phone rw-safe-top rw-safe-bottom min-h-screen px-6 py-6" data-testid="complete-profile-page">
        <Logo size="sm" />
        <div className="mt-8 rw-rise">
          <p className="rw-eyebrow">One last step</p>
          <h1 className="mt-1 rw-serif text-3xl">Complete your RIYORA profile.</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Signed in as <span className="font-medium">{pending.summary?.email || pending.summary?.name}</span>. This information is required to activate your membership.
          </p>
        </div>

        <form className="mt-6 space-y-4 pb-8" onSubmit={submit}>
          <Section label="Mandatory">
            <Field label="Full name">
              <input className="rw-input" value={form.full_name} onChange={set("full_name")} data-testid="cp-name" />
            </Field>
            <Field label="Mobile number (Indian, 10-digit)">
              <input className="rw-input" inputMode="numeric" maxLength={10} value={form.mobile} onChange={(e) => setForm({ ...form, mobile: e.target.value.replace(/\D/g, "").slice(0, 10) })} data-testid="cp-mobile" placeholder="9XXXXXXXXX" />
              <p className="mt-1 text-[11px] text-muted-foreground">
                One mobile per RIYORA account. No verification code required.
              </p>
            </Field>
            <Field label="Referral code (RW + 6 digits — 8 chars total)">
              <input
                className="rw-input uppercase font-mono"
                value={form.referral_id}
                onChange={(e) => {
                  // Force uppercase, strip non-alphanumeric, cap at 8 chars.
                  const cleaned = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 8);
                  setForm({ ...form, referral_id: cleaned });
                }}
                maxLength={8}
                placeholder="RW000000"
                pattern="RW\d{6}"
                inputMode="text"
                data-testid="cp-referral"
              />
              <p className="mt-1 text-[11px] text-muted-foreground">
                Exactly <span className="font-mono">RW</span> followed by 6 digits. Use{" "}
                <span className="font-mono">RW000000</span> if you don&apos;t have a sponsor.
              </p>
            </Field>
          </Section>

          <Section label="Optional (you can edit later)">
            <div className="grid grid-cols-2 gap-3">
              <Field label="State"><input className="rw-input" value={form.state} onChange={set("state")} data-testid="cp-state" /></Field>
              <Field label="City"><input className="rw-input" value={form.city} onChange={set("city")} data-testid="cp-city" /></Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Pincode"><input className="rw-input" value={form.pincode} onChange={set("pincode")} data-testid="cp-pincode" /></Field>
              <Field label="Gender">
                <select className="rw-input" value={form.gender} onChange={set("gender")} data-testid="cp-gender">
                  <option value="">—</option>
                  <option>Male</option>
                  <option>Female</option>
                  <option>Other</option>
                  <option>Prefer not to say</option>
                </select>
              </Field>
            </div>
            <Field label="Date of birth"><input className="rw-input" type="date" value={form.dob} onChange={set("dob")} data-testid="cp-dob" /></Field>
            <Field label="Address"><textarea className="rw-input min-h-[60px]" rows={2} value={form.address} onChange={set("address")} data-testid="cp-address" /></Field>
          </Section>

          <button type="submit" className="rw-btn-pill rw-btn-primary w-full" disabled={busy} data-testid="cp-submit">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
            Activate my membership
          </button>

          <div className="mt-3 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-[11px] text-emerald-900">
            <ShieldCheck className="h-4 w-4 shrink-0" />
            Your Firebase account secures the login. RIYORA never sees or stores your password.
          </div>

          <p className="text-center text-xs text-muted-foreground">
            Wrong account? <Link to="/login" className="font-semibold text-[hsl(var(--rw-royal))]" onClick={() => sessionStorage.removeItem("rw_pending_firebase")}>Sign out and try again</Link>
          </p>
        </form>
      </div>
    </div>
  );
}

function Section({ label, children }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">{label}</p>
      <div className="mt-2 space-y-3">{children}</div>
    </div>
  );
}
function Field({ label, children }) {
  return (
    <div>
      <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{label}</label>
      <div className="mt-1">{children}</div>
    </div>
  );
}
