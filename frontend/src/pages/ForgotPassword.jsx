import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight, Loader2 } from "lucide-react";
import Logo from "@/components/Logo";
import api, { formatApiError } from "@/lib/api";
import { TID } from "@/constants/testIds";

export default function ForgotPassword() {
  const nav = useNavigate();
  const [step, setStep] = useState("mobile");
  const [loading, setLoading] = useState(false);
  const [devOtp, setDevOtp] = useState(null);
  const [mobile, setMobile] = useState("");
  const [otp, setOtp] = useState("");
  const [pwd, setPwd] = useState("");
  const [cpwd, setCpwd] = useState("");

  const sendOtp = async () => {
    if (!/^[6-9]\d{9}$/.test(mobile)) return toast.error("Enter valid mobile");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/send-otp", { mobile, purpose: "forgot_password" });
      setDevOtp(data.dev_code);
      setStep("otp");
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setLoading(false); }
  };
  const verify = async () => {
    setLoading(true);
    try {
      await api.post("/auth/verify-otp", { mobile, purpose: "forgot_password", code: otp });
      setStep("password");
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setLoading(false); }
  };
  const reset = async () => {
    if (pwd !== cpwd) return toast.error("Passwords don't match");
    setLoading(true);
    try {
      await api.post("/auth/reset-password", { mobile, new_password: pwd, confirm_password: cpwd });
      toast.success("Password updated");
      nav("/login", { replace: true });
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-white">
      <div className="rw-phone rw-safe-top rw-safe-bottom min-h-screen px-6 py-6">
        <Logo size="sm" />
        <div className="mt-10">
          <p className="rw-eyebrow">Recover access</p>
          <h1 className="mt-1 rw-serif text-4xl text-foreground">Reset password.</h1>
        </div>

        <div className="mt-6 rw-card p-5">
          {step === "mobile" && (
            <div className="space-y-4">
              <F label="Mobile"><input className="rw-input" data-testid={TID.fpMobile} inputMode="numeric" maxLength={10} value={mobile} onChange={(e) => setMobile(e.target.value)} /></F>
              <button className="rw-btn-pill rw-btn-primary w-full" onClick={sendOtp} disabled={loading} data-testid={TID.fpSendOtp}>
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />} Send OTP
              </button>
            </div>
          )}
          {step === "otp" && (
            <div className="space-y-4">
              {devOtp && (
                <div className="rounded-xl border border-dashed border-[hsl(var(--rw-royal))]/40 bg-[hsl(var(--rw-sky-soft))] p-3 text-xs text-[hsl(var(--rw-royal-deep))]">
                  Dev OTP: <b>{devOtp}</b>
                </div>
              )}
              <F label="OTP"><input className="rw-input" data-testid={TID.fpOtp} inputMode="numeric" maxLength={6} value={otp} onChange={(e) => setOtp(e.target.value)} /></F>
              <button className="rw-btn-pill rw-btn-primary w-full" onClick={verify} disabled={loading || otp.length < 4} data-testid={TID.fpVerify}>Verify</button>
            </div>
          )}
          {step === "password" && (
            <div className="space-y-4">
              <F label="New password"><input className="rw-input" type="password" data-testid={TID.fpNewPassword} value={pwd} onChange={(e) => setPwd(e.target.value)} /></F>
              <F label="Confirm"><input className="rw-input" type="password" data-testid={TID.fpConfirmPassword} value={cpwd} onChange={(e) => setCpwd(e.target.value)} /></F>
              <button className="rw-btn-pill rw-btn-primary w-full" onClick={reset} disabled={loading || pwd.length < 8} data-testid={TID.fpSubmit}>Update password</button>
            </div>
          )}
        </div>

        <p className="mt-8 text-center text-sm text-muted-foreground">
          Remembered it? <Link to="/login" className="font-semibold text-[hsl(var(--rw-royal))]">Back to sign in</Link>
        </p>
      </div>
    </div>
  );
}

function F({ label, children }) {
  return (
    <div>
      <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{label}</label>
      <div className="mt-1">{children}</div>
    </div>
  );
}
