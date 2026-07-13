import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight, Loader2, Mail, Link2 } from "lucide-react";

import Logo from "@/components/Logo";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";
import {
  humanFirebaseError,
  signInWithGoogle,
  signUpWithEmail,
  signInWithEmail,
} from "@/lib/firebase";

function GoogleIcon(props) {
  return (
    <svg viewBox="0 0 48 48" width="18" height="18" aria-hidden="true" {...props}>
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
    </svg>
  );
}

/**
 * Migration path for existing legacy users who registered before Firebase
 * was added. They already have (mobile + password) in RIYORA. Here we
 * make them:
 *   1. Sign up on Firebase (Google or email/password).
 *   2. Prove ownership of their old RIYORA account (mobile + old password).
 * On success we graft the Firebase UID onto their existing membership so
 * every future sign-in uses Firebase.
 */
export default function LinkAccount() {
  const nav = useNavigate();
  const { linkExistingWithFirebase } = useAuth();

  const [step, setStep] = useState("firebase"); // firebase | prove
  const [busy, setBusy] = useState(null);
  const [idToken, setIdToken] = useState(null);
  const [fbEmail, setFbEmail] = useState("");
  const [emailForm, setEmailForm] = useState({ email: "", password: "", mode: "signup" });
  const [proof, setProof] = useState({ mobile: "", password: "" });

  const captured = (token, email) => {
    setIdToken(token);
    setFbEmail(email || "");
    setStep("prove");
  };

  const doGoogle = async () => {
    setBusy("google");
    try {
      const { idToken: t, user } = await signInWithGoogle();
      captured(t, user.email);
      toast.success("Firebase account verified. Now prove your legacy account.");
    } catch (err) { toast.error(humanFirebaseError(err)); }
    finally { setBusy(null); }
  };

  const doEmail = async (e) => {
    e.preventDefault();
    setBusy("email");
    try {
      const fn = emailForm.mode === "signup" ? signUpWithEmail : signInWithEmail;
      const { idToken: t, user } = await fn(emailForm.email.trim(), emailForm.password);
      captured(t, user.email);
      toast.success("Firebase account verified. Now prove your legacy account.");
    } catch (err) { toast.error(humanFirebaseError(err)); }
    finally { setBusy(null); }
  };

  const doLink = async (e) => {
    e.preventDefault();
    if (!/^[6-9]\d{9}$/.test(proof.mobile)) return toast.error("Enter a valid 10-digit mobile");
    if (!proof.password) return toast.error("Enter your old RIYORA password");
    setBusy("link");
    try {
      await linkExistingWithFirebase({
        id_token: idToken,
        mobile: proof.mobile,
        password: proof.password,
      });
      toast.success("Account linked. Welcome back!");
      nav("/app/home", { replace: true });
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setBusy(null); }
  };

  return (
    <div className="min-h-screen bg-white">
      <div className="rw-phone rw-safe-top rw-safe-bottom min-h-screen px-6 py-6" data-testid="link-account-page">
        <Logo size="sm" />
        <div className="mt-10 rw-rise">
          <p className="rw-eyebrow">Link existing account</p>
          <h1 className="mt-1 rw-serif text-3xl">Bring your RIYORA account into the new sign-in.</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Registered before Feb&nbsp;2026? Link your membership to a Firebase (Google or email/password) account. Nothing is lost — your programs, wallet, referrals and progress stay intact.
          </p>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-2 text-center text-[11px] font-semibold uppercase tracking-widest">
          <span className={`rounded-full px-3 py-1 ${step === "firebase" ? "bg-primary text-white" : "bg-neutral-100 text-muted-foreground"}`}>1 · Firebase</span>
          <span className={`rounded-full px-3 py-1 ${step === "prove" ? "bg-primary text-white" : "bg-neutral-100 text-muted-foreground"}`}>2 · Verify legacy</span>
        </div>

        {step === "firebase" && (
          <div className="mt-6 space-y-3">
            <button onClick={doGoogle} disabled={busy !== null} className="rw-btn-pill w-full border border-neutral-200 bg-white text-foreground hover:bg-neutral-50" data-testid="link-google-btn">
              {busy === "google" ? <Loader2 className="h-4 w-4 animate-spin" /> : <GoogleIcon />}
              Continue with Google
            </button>

            <form className="rounded-2xl border p-4 space-y-3" onSubmit={doEmail}>
              <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground flex items-center gap-2">
                <Mail className="h-3 w-3" /> Email / Password
              </div>
              <input className="rw-input" type="email" placeholder="Email" value={emailForm.email} onChange={(e) => setEmailForm({ ...emailForm, email: e.target.value })} data-testid="link-email-input" />
              <input className="rw-input" type="password" placeholder="Password" value={emailForm.password} onChange={(e) => setEmailForm({ ...emailForm, password: e.target.value })} data-testid="link-email-password" />
              <div className="flex items-center gap-3 text-xs">
                <label className="flex items-center gap-1">
                  <input type="radio" checked={emailForm.mode === "signup"} onChange={() => setEmailForm({ ...emailForm, mode: "signup" })} data-testid="link-mode-signup" /> Create new
                </label>
                <label className="flex items-center gap-1">
                  <input type="radio" checked={emailForm.mode === "signin"} onChange={() => setEmailForm({ ...emailForm, mode: "signin" })} data-testid="link-mode-signin" /> Already Firebase user
                </label>
              </div>
              <button type="submit" className="rw-btn-pill rw-btn-primary w-full" disabled={busy !== null} data-testid="link-email-submit">
                {busy === "email" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
                Continue with email
              </button>
            </form>
          </div>
        )}

        {step === "prove" && (
          <form className="mt-6 space-y-4" onSubmit={doLink}>
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-[11px] text-emerald-900">
              Firebase verified for <span className="font-mono">{fbEmail}</span>. Now prove ownership of your legacy RIYORA account.
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Old RIYORA mobile</label>
              <input className="rw-input mt-1" inputMode="numeric" maxLength={10} value={proof.mobile} onChange={(e) => setProof({ ...proof, mobile: e.target.value.replace(/\D/g, "").slice(0, 10) })} data-testid="link-legacy-mobile" />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Old RIYORA password</label>
              <input className="rw-input mt-1" type="password" value={proof.password} onChange={(e) => setProof({ ...proof, password: e.target.value })} data-testid="link-legacy-password" />
            </div>
            <button type="submit" className="rw-btn-pill rw-btn-primary w-full" disabled={busy !== null} data-testid="link-submit-btn">
              {busy === "link" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Link2 className="h-4 w-4" />}
              Link my account
            </button>
            <button type="button" onClick={() => setStep("firebase")} className="w-full text-center text-xs font-semibold text-[hsl(var(--rw-royal))]" data-testid="link-back-btn">
              ← Use a different Firebase account
            </button>
          </form>
        )}

        <p className="mt-8 text-center text-xs text-muted-foreground">
          Not a legacy user?{" "}
          <Link to="/register" className="font-semibold text-[hsl(var(--rw-royal))]">Create a fresh account</Link>
        </p>
      </div>
    </div>
  );
}
