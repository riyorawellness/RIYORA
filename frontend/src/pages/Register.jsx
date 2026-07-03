import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight, CheckCircle2, Loader2 } from "lucide-react";
import Logo from "@/components/Logo";
import { TID } from "@/constants/testIds";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const STEPS = ["mobile", "otp", "details", "confirm"];

export default function Register() {
  const nav = useNavigate();
  const { registerUser } = useAuth();
  const [step, setStep] = useState("mobile");
  const [loading, setLoading] = useState(false);
  const [devOtp, setDevOtp] = useState(null);
  const [sponsor, setSponsor] = useState(null);
  const [form, setForm] = useState({
    mobile: "",
    otp: "",
    full_name: "",
    state: "",
    city: "",
    referral_id: "",
    password: "",
    confirm_password: "",
  });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const sendOtp = async () => {
    if (!/^[6-9]\d{9}$/.test(form.mobile)) return toast.error("Enter a valid mobile");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/send-otp", { mobile: form.mobile, purpose: "register" });
      setDevOtp(data.dev_code);
      setStep("otp");
      toast.success("OTP sent");
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };
  const verifyOtp = async () => {
    setLoading(true);
    try {
      await api.post("/auth/verify-otp", { mobile: form.mobile, purpose: "register", code: form.otp });
      setStep("details");
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };
  const checkReferral = async () => {
    if (!/^RW\d{6}$/.test(form.referral_id)) return toast.error("Format is RW123456");
    setLoading(true);
    try {
      const { data } = await api.post("/membership/validate-referral", { referral_id: form.referral_id });
      setSponsor(data);
    } catch (e) {
      setSponsor(null);
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };
  const goConfirm = () => {
    if (!sponsor) return toast.error("Verify Referral ID");
    if (form.password.length < 8) return toast.error("Password must be at least 8 chars");
    if (form.password !== form.confirm_password) return toast.error("Passwords don’t match");
    setStep("confirm");
  };
  const finalize = async () => {
    setLoading(true);
    try {
      const u = await registerUser({
        full_name: form.full_name,
        mobile: form.mobile,
        state: form.state,
        city: form.city,
        referral_id: form.referral_id,
        password: form.password,
        confirm_password: form.confirm_password,
      });
      toast.success(`Welcome, ${u.full_name}!`);
      nav("/app/home", { replace: true });
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };

  const idx = STEPS.indexOf(step);
  return (
    <div className="min-h-screen bg-white">
      <div className="rw-phone rw-safe-top rw-safe-bottom min-h-screen px-6 py-6">
        <Logo size="sm" />
        <div className="mt-8 rw-rise">
          <p className="rw-eyebrow">Create membership</p>
          <h1 className="mt-1 rw-serif text-4xl text-foreground">Begin the journey.</h1>
        </div>

        <div className="mt-6 flex gap-1.5">
          {STEPS.map((s, i) => (
            <div key={s} className={`h-1.5 flex-1 rounded-full transition-all ${i <= idx ? "bg-[hsl(var(--rw-royal))]" : "bg-[hsl(var(--rw-grey-100))]"}`} />
          ))}
        </div>

        <div className="mt-6 rw-card p-5">
          {step === "mobile" && (
            <div className="space-y-4">
              <Field label="Mobile number">
                <input
                  className="rw-input" data-testid={TID.regMobile}
                  inputMode="numeric" maxLength={10}
                  value={form.mobile} onChange={set("mobile")} placeholder="10-digit mobile"
                />
              </Field>
              <button className="rw-btn-pill rw-btn-primary w-full" onClick={sendOtp} disabled={loading} data-testid={TID.regSendOtp}>
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
                Send OTP
              </button>
            </div>
          )}
          {step === "otp" && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Code sent to <b>+91 {form.mobile}</b>. Expires in 5 minutes.
              </p>
              {devOtp && (
                <div className="rounded-xl border border-dashed border-[hsl(var(--rw-royal))]/40 bg-[hsl(var(--rw-sky-soft))] p-3 text-xs text-[hsl(var(--rw-royal-deep))]">
                  Dev OTP: <b>{devOtp}</b>
                </div>
              )}
              <Field label="OTP">
                <input className="rw-input" data-testid={TID.regOtp} inputMode="numeric" maxLength={6}
                  value={form.otp} onChange={set("otp")} />
              </Field>
              <button className="rw-btn-pill rw-btn-primary w-full" onClick={verifyOtp} disabled={loading || form.otp.length < 4} data-testid={TID.regVerifyOtp}>
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Verify
              </button>
            </div>
          )}
          {step === "details" && (
            <div className="space-y-4">
              <Field label="Full name">
                <input className="rw-input" data-testid={TID.regFullName} value={form.full_name} onChange={set("full_name")} />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="State"><input className="rw-input" data-testid={TID.regState} value={form.state} onChange={set("state")} /></Field>
                <Field label="City"><input className="rw-input" data-testid={TID.regCity} value={form.city} onChange={set("city")} /></Field>
              </div>
              <Field label="Referral ID">
                <div className="flex gap-2">
                  <input className="rw-input" data-testid={TID.regReferral} value={form.referral_id} maxLength={8}
                    onChange={(e) => { setSponsor(null); setForm({ ...form, referral_id: e.target.value.toUpperCase() }); }}
                    placeholder="RW000000" />
                  <button type="button" className="rw-btn-pill rw-btn-ghost" onClick={checkReferral}
                    disabled={loading || form.referral_id.length !== 8} data-testid={TID.regReferralCheck}>
                    Verify
                  </button>
                </div>
                {sponsor && (
                  <div className="mt-2 flex items-start gap-2 rounded-xl bg-[hsl(var(--rw-sky-soft))] p-3 text-xs" data-testid={TID.regSponsorInfo}>
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-[hsl(var(--rw-royal))]" />
                    <div>
                      <div className="text-muted-foreground">Sponsored by</div>
                      <div className="text-sm font-semibold">{sponsor.sponsor_name}</div>
                      <div className="text-muted-foreground">Membership ID: {sponsor.sponsor_membership_id}</div>
                    </div>
                  </div>
                )}
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Password"><input className="rw-input" type="password" data-testid={TID.regPassword} value={form.password} onChange={set("password")} /></Field>
                <Field label="Confirm"><input className="rw-input" type="password" data-testid={TID.regConfirmPassword} value={form.confirm_password} onChange={set("confirm_password")} /></Field>
              </div>
              <button className="rw-btn-pill rw-btn-primary w-full" onClick={goConfirm}
                disabled={loading || !sponsor || !form.full_name || !form.state || !form.city}
                data-testid={TID.regSubmit}>
                Continue <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          )}
          {step === "confirm" && sponsor && (
            <div className="space-y-4">
              <div className="rounded-2xl bg-[hsl(var(--rw-sky-soft))] p-4 text-sm">
                <p className="rw-eyebrow">Please confirm</p>
                <div className="mt-3 space-y-1">
                  {[
                    ["Name", form.full_name],
                    ["Mobile", `+91 ${form.mobile}`],
                    ["Location", `${form.city}, ${form.state}`],
                    ["Sponsor", sponsor.sponsor_name],
                    ["Sponsor ID", sponsor.sponsor_membership_id],
                  ].map(([k, v]) => (
                    <div key={k} className="flex items-baseline justify-between gap-2">
                      <span className="text-[11px] uppercase tracking-widest text-muted-foreground">{k}</span>
                      <span className="text-sm font-medium">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="flex gap-3">
                <button type="button" className="rw-btn-pill rw-btn-ghost" onClick={() => setStep("details")} disabled={loading}>Back</button>
                <button className="rw-btn-pill rw-btn-primary ml-auto flex-1" onClick={finalize} disabled={loading} data-testid={TID.regConfirm}>
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  Confirm &amp; create
                </button>
              </div>
            </div>
          )}
        </div>

        <p className="mt-8 text-center text-sm text-muted-foreground">
          Already a member? <Link to="/login" className="font-semibold text-[hsl(var(--rw-royal))]">Sign in</Link>
        </p>
      </div>
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
