import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight, CheckCircle2, Loader2, Mail, RefreshCw } from "lucide-react";

import Logo from "@/components/Logo";
import {
  humanFirebaseError,
  reloadFirebaseUser,
  resendVerificationEmail,
  signInWithGoogle,
  signUpWithEmail,
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
 * Registration flow — two modes:
 *   1. Google → verified by Google → go straight to /complete-profile
 *   2. Email/password → Firebase sends verification email → we sit on the
 *      "Verify your email" screen, poll Firebase every 3 s, and only
 *      progress to /complete-profile once emailVerified turns true.
 *      No RIYORA membership is created before that.
 */
export default function Register() {
  const nav = useNavigate();
  const [mode, setMode] = useState("choose");            // choose | email | verifying
  const [form, setForm] = useState({ full_name: "", email: "", password: "", confirm: "" });
  const [busy, setBusy] = useState(null);
  const [emailUser, setEmailUser] = useState(null);      // Firebase user awaiting verification
  const pollRef = useRef(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const proceedVerified = (idToken, user) => {
    sessionStorage.setItem("rw_pending_firebase", JSON.stringify({
      id_token: idToken,
      summary: {
        uid: user.uid, email: user.email, name: user.displayName || form.full_name,
        picture: user.photoURL, login_method: "email", email_verified: true,
      },
      full_name_hint: form.full_name || user.displayName || "",
    }));
    if (pollRef.current) clearInterval(pollRef.current);
    toast.success("Email verified — let's complete your profile.");
    nav("/complete-profile", { replace: true });
  };

  const doGoogle = async () => {
    setBusy("google");
    try {
      const { idToken, user } = await signInWithGoogle();
      sessionStorage.setItem("rw_pending_firebase", JSON.stringify({
        id_token: idToken,
        summary: {
          uid: user.uid, email: user.email, name: user.displayName,
          picture: user.photoURL, login_method: "google",
          email_verified: user.emailVerified,
        },
        full_name_hint: form.full_name || user.displayName || "",
      }));
      nav("/complete-profile", { replace: true });
      toast.success("Google account verified — let's finish your profile.");
    } catch (err) {
      toast.error(humanFirebaseError(err));
    } finally {
      setBusy(null);
    }
  };

  const doEmailSignUp = async (e) => {
    e.preventDefault();
    if (!form.full_name || form.full_name.length < 2) return toast.error("Enter your name");
    if (!form.email) return toast.error("Enter your email");
    if (form.password.length < 6) return toast.error("Password must be 6+ characters");
    if (form.password !== form.confirm) return toast.error("Passwords don't match");
    setBusy("email");
    try {
      const { user } = await signUpWithEmail(form.email.trim(), form.password, form.full_name);
      setEmailUser(user);
      setMode("verifying");
      toast.success("Verification email sent. Please check your inbox.");
      // Poll Firebase every 3 s so the moment the user clicks the link
      // and returns here we auto-detect and progress.
      pollRef.current = setInterval(async () => {
        try {
          const res = await reloadFirebaseUser();
          if (res.emailVerified) proceedVerified(res.idToken, res.user);
        } catch (_) { /* transient — keep polling */ }
      }, 3000);
    } catch (err) {
      toast.error(humanFirebaseError(err));
    } finally {
      setBusy(null);
    }
  };

  const manualCheck = async () => {
    setChecking(true);
    try {
      const res = await reloadFirebaseUser();
      if (res.emailVerified) proceedVerified(res.idToken, res.user);
      else toast.error("Not verified yet. Check your inbox (and spam folder) and click the link.");
    } catch (err) {
      toast.error(humanFirebaseError(err) || "Please sign in again.");
    } finally {
      setChecking(false);
    }
  };

  const doResend = async () => {
    try {
      await resendVerificationEmail();
      toast.success("Verification email resent.");
    } catch (err) {
      toast.error(humanFirebaseError(err));
    }
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="min-h-screen bg-white">
      <div className="rw-phone rw-safe-top rw-safe-bottom min-h-screen px-6 py-6" data-testid="register-page">
        <Logo size="sm" />

        {mode !== "verifying" && (
          <div className="mt-10 rw-rise">
            <p className="rw-eyebrow">Start your journey</p>
            <h1 className="mt-1 rw-serif text-4xl text-foreground">Create your account.</h1>
            <p className="mt-1 text-sm text-muted-foreground">Takes 60 seconds. Email verification required.</p>
          </div>
        )}

        {mode === "choose" && (
          <div className="mt-8 space-y-3">
            <button
              onClick={doGoogle}
              disabled={busy !== null}
              className="rw-btn-pill w-full border border-neutral-200 bg-white text-foreground hover:bg-neutral-50"
              data-testid="register-google-btn"
            >
              {busy === "google" ? <Loader2 className="h-4 w-4 animate-spin" /> : <GoogleIcon />}
              Continue with Google
            </button>

            <button
              onClick={() => setMode("email")}
              disabled={busy !== null}
              className="rw-btn-pill rw-btn-primary w-full"
              data-testid="register-email-btn"
            >
              <Mail className="h-4 w-4" /> Sign up with email
            </button>

            <p className="pt-4 text-center text-sm text-muted-foreground">
              Already have an account?{" "}
              <Link to="/login" className="font-semibold text-[hsl(var(--rw-royal))]">
                Sign in
              </Link>
            </p>
          </div>
        )}

        {mode === "email" && (
          <form className="mt-8 space-y-4" onSubmit={doEmailSignUp}>
            <div>
              <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Full name</label>
              <input className="rw-input mt-1" value={form.full_name} onChange={set("full_name")} data-testid="register-name-input" />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Email</label>
              <input className="rw-input mt-1" type="email" autoComplete="email" value={form.email} onChange={set("email")} data-testid="register-email-input" />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Password (6+ chars)</label>
              <input className="rw-input mt-1" type="password" autoComplete="new-password" value={form.password} onChange={set("password")} data-testid="register-password-input" />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Confirm password</label>
              <input className="rw-input mt-1" type="password" autoComplete="new-password" value={form.confirm} onChange={set("confirm")} data-testid="register-confirm-input" />
            </div>
            <button type="submit" className="rw-btn-pill rw-btn-primary w-full" disabled={busy !== null} data-testid="register-submit-btn">
              {busy === "email" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
              Create account
            </button>
            <button type="button" onClick={() => setMode("choose")} className="w-full text-center text-xs font-semibold text-[hsl(var(--rw-royal))]" data-testid="register-back-btn">
              ← Back to options
            </button>
          </form>
        )}

        {mode === "verifying" && (
          <div className="mt-10 rw-rise" data-testid="register-verify-screen">
            <div className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal))]">
              <Mail className="h-8 w-8" />
            </div>
            <h1 className="mt-4 rw-serif text-3xl text-center">Verify your email</h1>
            <p className="mt-2 text-center text-sm text-muted-foreground">
              We&apos;ve sent a verification link to{" "}
              <span className="font-semibold text-foreground">{emailUser?.email}</span>.
              Please click it to activate your account.
            </p>
            <p className="mt-1 text-center text-xs text-muted-foreground">
              Your RIYORA profile, Member ID, Referral ID and wallet are created
              only after your email is verified.
            </p>

            <button
              onClick={manualCheck}
              disabled={checking}
              className="rw-btn-pill rw-btn-primary mt-6 w-full"
              data-testid="register-verify-check-btn"
            >
              {checking ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
              I&apos;ve verified — continue
            </button>

            <button
              onClick={doResend}
              className="mt-3 w-full rounded-full border border-neutral-200 py-3 text-sm font-semibold text-foreground hover:bg-neutral-50"
              data-testid="register-verify-resend-btn"
            >
              <RefreshCw className="mr-2 inline h-4 w-4" />
              Resend verification email
            </button>

            <p className="mt-6 text-center text-xs text-muted-foreground">
              Wrong email?{" "}
              <button
                onClick={() => {
                  if (pollRef.current) clearInterval(pollRef.current);
                  setEmailUser(null);
                  setMode("email");
                }}
                className="font-semibold text-[hsl(var(--rw-royal))]"
                data-testid="register-verify-back-btn"
              >
                Use a different one
              </button>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
