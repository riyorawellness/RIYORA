import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight, Loader2, MailCheck } from "lucide-react";

import Logo from "@/components/Logo";
import { humanFirebaseError, sendResetEmail } from "@/lib/firebase";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return toast.error("Enter your email");
    setBusy(true);
    try {
      await sendResetEmail(email.trim());
      setSent(true);
      toast.success("Reset link sent — check your inbox.");
    } catch (err) {
      toast.error(humanFirebaseError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-white">
      <div className="rw-phone rw-safe-top rw-safe-bottom min-h-screen px-6 py-6" data-testid="forgot-password-page">
        <Logo size="sm" />
        <div className="mt-10 rw-rise">
          <p className="rw-eyebrow">Reset password</p>
          <h1 className="mt-1 rw-serif text-4xl">Forgot your password?</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            We'll send a secure reset link to your registered email.
          </p>
        </div>

        {sent ? (
          <div className="mt-8 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900" data-testid="forgot-password-sent">
            <MailCheck className="mb-2 h-6 w-6" />
            <p className="font-semibold">Check your email.</p>
            <p className="mt-1 text-xs">
              If <span className="font-mono">{email}</span> is registered with RIYORA, a password reset link has been sent. It expires in 1 hour.
            </p>
            <Link to="/login" className="mt-4 inline-flex text-xs font-semibold text-[hsl(var(--rw-royal))]">
              ← Back to sign in
            </Link>
          </div>
        ) : (
          <form className="mt-8 space-y-4" onSubmit={submit}>
            <div>
              <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Email</label>
              <input
                className="rw-input mt-1"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                data-testid="forgot-email-input"
              />
            </div>
            <button type="submit" className="rw-btn-pill rw-btn-primary w-full" disabled={busy} data-testid="forgot-submit-btn">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
              Send reset link
            </button>
            <p className="text-center text-xs text-muted-foreground">
              Remembered? <Link to="/login" className="font-semibold text-[hsl(var(--rw-royal))]">Back to sign in</Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
