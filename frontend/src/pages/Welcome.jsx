import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check, Sparkles } from "lucide-react";
import Logo from "@/components/Logo";
import { TID } from "@/constants/testIds";
import { toast } from "sonner";
import { useSystemInfo } from "@/hooks/useSystemInfo";

export default function Welcome() {
  const [agreed, setAgreed] = useState(false);
  const sys = useSystemInfo();

  return (
    <div className="min-h-screen bg-white">
      <div className="rw-phone rw-safe-top rw-safe-bottom flex min-h-screen flex-col px-6">
        <div className="pt-6"><Logo size="md" /></div>

        <div className="relative mt-6 flex-1">
          <div className="relative overflow-hidden rounded-3xl">
            <img
              src="https://images.unsplash.com/photo-1506126613408-eca07ce68773?auto=format&fit=crop&w=900&q=70"
              alt=""
              className="h-[42vh] w-full object-cover"
            />
            <div
              className="absolute inset-0"
              style={{ background: "linear-gradient(180deg, transparent 0%, hsl(var(--rw-royal-deep)) 100%)" }}
            />
            <div className="absolute inset-x-0 bottom-0 p-6 text-white">
              <span className="rw-chip rw-chip-gold">
                <Sparkles className="h-3 w-3" /> Invitation only
              </span>
              <h1 className="mt-3 rw-serif text-5xl leading-[1.02]">
                A quieter path <br /> to <em className="not-italic text-[hsl(var(--rw-gold))]">wholeness.</em>
              </h1>
              <p className="mt-3 max-w-md text-sm text-white/80">
                Guided programs, live sessions and a mindful community — designed to
                heal, learn and earn in harmony.
              </p>
            </div>
          </div>

          {/* Consent block */}
          <div className="mt-6 rounded-2xl border border-neutral-200 bg-neutral-50 p-4">
            <p className="text-[12px] leading-relaxed text-neutral-700" data-testid="welcome-legal-text">
              By continuing, you agree to the RIYORA Wellness{" "}
              <Link
                to="/legal/terms"
                className="font-semibold text-[hsl(var(--rw-royal))] underline underline-offset-2"
                data-testid="welcome-terms-link"
              >
                Terms &amp; Conditions
              </Link>{" "}
              and{" "}
              <Link
                to="/legal/privacy"
                className="font-semibold text-[hsl(var(--rw-royal))] underline underline-offset-2"
                data-testid="welcome-privacy-link"
              >
                Privacy Policy
              </Link>
              .
            </p>

            <label
              className="mt-3 flex cursor-pointer items-start gap-3 rounded-xl border border-neutral-200 bg-white p-3"
              data-testid="welcome-consent-label"
            >
              <input
                type="checkbox"
                className="peer sr-only"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
                data-testid="welcome-consent-checkbox"
              />
              <span
                className={`grid h-5 w-5 flex-shrink-0 place-items-center rounded-md border-2 transition ${
                  agreed
                    ? "border-[hsl(var(--rw-royal))] bg-[hsl(var(--rw-royal))] text-white"
                    : "border-neutral-300 bg-white"
                }`}
                aria-hidden
              >
                {agreed && <Check className="h-3 w-3" strokeWidth={3} />}
              </span>
              <span className="text-[12px] font-medium text-neutral-800">
                I have read and agree to the Terms &amp; Conditions and Privacy Policy.
              </span>
            </label>
          </div>

          <div className="mt-5 space-y-3">
            <div
              onClickCapture={(e) => {
                if (!agreed) {
                  e.preventDefault();
                  e.stopPropagation();
                  toast.warning(
                    "Please accept the Terms & Conditions and Privacy Policy to continue."
                  );
                }
              }}
            >
              <Link
                to="/register"
                tabIndex={agreed ? 0 : -1}
                data-testid={TID.welcomeCtaRegister}
              >
                <button
                  type="button"
                  className={`rw-btn-pill rw-btn-primary w-full ${agreed ? "" : "cursor-not-allowed opacity-50"}`}
                  data-testid="welcome-create-account-btn"
                >
                  Create account <ArrowRight className="h-4 w-4" />
                </button>
              </Link>
              <div className="h-3" />
              <Link
                to="/login"
                tabIndex={agreed ? 0 : -1}
                data-testid={TID.welcomeCtaLogin}
              >
                <button
                  type="button"
                  className={`rw-btn-pill rw-btn-ghost w-full ${agreed ? "" : "cursor-not-allowed opacity-50"}`}
                  data-testid="welcome-signin-btn"
                >
                  Sign in
                </button>
              </Link>
            </div>
          </div>

          <p className="mt-4 text-center text-[11px] text-muted-foreground">
            <Link to="/admin/login" className="text-[hsl(var(--rw-royal))]">Admin portal</Link>
          </p>

          <p className="mt-4 text-center text-[10px] text-muted-foreground">
            © {new Date().getFullYear()} {sys?.company_name || "RIYORA Wellness"}. All Rights Reserved.
            {" · "}v{sys?.application_version || "1.0.0"}
          </p>
        </div>
      </div>
    </div>
  );
}
