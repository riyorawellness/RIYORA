import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight, Loader2, Mail } from "lucide-react";

import Logo from "@/components/Logo";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";
import { TID } from "@/constants/testIds";
import {
  signInWithGoogle,
  signInWithEmail,
  humanFirebaseError,
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

export default function Login() {
  const nav = useNavigate();
  const { syncFirebaseToken } = useAuth();
  const [mode, setMode] = useState("choose"); // choose | email
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(null); // "google" | "email" | null

  const afterFirebase = async (idToken) => {
    const res = await syncFirebaseToken(idToken);
    if (res.needs_registration) {
      // Persist the Firebase user summary in session storage so the
      // complete-profile screen can hydrate it without re-verifying.
      sessionStorage.setItem("rw_pending_firebase", JSON.stringify({
        id_token: idToken,
        summary: res.firebase_user,
      }));
      toast.info("Almost there — let's complete your RIYORA profile.");
      nav("/complete-profile", { replace: true });
      return;
    }
    toast.success(`Welcome back, ${res.user.full_name.split(" ")[0]}`);
    nav("/app/home", { replace: true });
  };

  const doGoogle = async () => {
    setBusy("google");
    try {
      const { idToken } = await signInWithGoogle();
      await afterFirebase(idToken);
    } catch (err) {
      // Distinguish between Firebase errors and RIYORA API errors.
      const msg = err?.code ? humanFirebaseError(err) : formatApiError(err);
      toast.error(msg);
    } finally {
      setBusy(null);
    }
  };

  const doEmail = async (e) => {
    e.preventDefault();
    if (!email || !password) return toast.error("Enter email and password");
    setBusy("email");
    try {
      const { idToken } = await signInWithEmail(email.trim(), password);
      await afterFirebase(idToken);
    } catch (err) {
      const msg = err?.code ? humanFirebaseError(err) : formatApiError(err);
      toast.error(msg);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="min-h-screen bg-white">
      <div className="rw-phone rw-safe-top rw-safe-bottom min-h-screen px-6 py-6" data-testid="login-page">
        <Logo size="sm" />
        <div className="mt-10 rw-rise">
          <p className="rw-eyebrow">Welcome back</p>
          <h1 className="mt-1 rw-serif text-4xl text-foreground">Sign in.</h1>
          <p className="mt-1 text-sm text-muted-foreground">Continue your practice.</p>
        </div>

        {mode === "choose" && (
          <div className="mt-8 space-y-3">
            <button
              onClick={doGoogle}
              disabled={busy !== null}
              className="rw-btn-pill w-full border border-neutral-200 bg-white text-foreground hover:bg-neutral-50"
              data-testid="login-google-btn"
            >
              {busy === "google" ? <Loader2 className="h-4 w-4 animate-spin" /> : <GoogleIcon />}
              Continue with Google
            </button>

            <button
              onClick={() => setMode("email")}
              disabled={busy !== null}
              className="rw-btn-pill rw-btn-primary w-full"
              data-testid="login-email-btn"
            >
              <Mail className="h-4 w-4" /> Sign in with email
            </button>

            <p className="pt-4 text-center text-sm text-muted-foreground">
              New here?{" "}
              <Link to="/register" className="font-semibold text-[hsl(var(--rw-royal))]" data-testid="login-signup-link">
                Create your RIYORA account
              </Link>
            </p>
          </div>
        )}

        {mode === "email" && (
          <form className="mt-8 space-y-4" onSubmit={doEmail}>
            <div>
              <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Email
              </label>
              <input
                className="rw-input mt-1"
                data-testid={TID.loginMobile}
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </div>
            <div>
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Password
                </label>
                <Link
                  to="/forgot-password"
                  className="text-xs font-semibold text-[hsl(var(--rw-royal))]"
                  data-testid={TID.loginForgot}
                >
                  Forgot?
                </Link>
              </div>
              <input
                className="rw-input mt-1"
                data-testid={TID.loginPassword}
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            <button
              type="submit"
              className="rw-btn-pill rw-btn-primary w-full"
              disabled={busy !== null}
              data-testid={TID.loginSubmit}
            >
              {busy === "email" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
              Sign in
            </button>

            <button
              type="button"
              onClick={() => setMode("choose")}
              className="w-full text-center text-xs font-semibold text-[hsl(var(--rw-royal))]"
              data-testid="login-back-btn"
            >
              ← Back to options
            </button>
          </form>
        )}

        <p className="mt-8 text-center text-xs text-muted-foreground">
          Existing RIYORA member (registered before Feb&nbsp;2026)?{" "}
          <Link to="/link-account" className="font-semibold text-[hsl(var(--rw-royal))]" data-testid="login-link-existing">
            Link your old account
          </Link>
        </p>
        <p className="mt-3 text-center text-xs text-muted-foreground">
          Administrator?{" "}
          <Link
            to="/admin/login"
            className="font-semibold text-[hsl(var(--rw-royal))]"
            data-testid="login-admin-link"
          >
            Sign in to the admin panel →
          </Link>
        </p>
      </div>
    </div>
  );
}
