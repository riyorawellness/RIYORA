import { Link } from "react-router-dom";
import { ArrowRight, Sparkles } from "lucide-react";
import Logo from "@/components/Logo";
import { TID } from "@/constants/testIds";

export default function Welcome() {
  return (
    <div className="min-h-screen bg-white">
      <div className="rw-phone rw-safe-top rw-safe-bottom flex min-h-screen flex-col px-6">
        <div className="pt-6"><Logo size="md" /></div>

        <div className="relative mt-6 flex-1">
          <div className="relative overflow-hidden rounded-3xl">
            <img
              src="https://images.unsplash.com/photo-1506126613408-eca07ce68773?auto=format&fit=crop&w=900&q=70"
              alt=""
              className="h-[52vh] w-full object-cover"
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

          <div className="mt-6 space-y-3">
            <Link to="/register" data-testid={TID.welcomeCtaRegister}>
              <button className="rw-btn-pill rw-btn-primary w-full">
                Create account <ArrowRight className="h-4 w-4" />
              </button>
            </Link>
            <Link to="/login" data-testid={TID.welcomeCtaLogin}>
              <button className="rw-btn-pill rw-btn-ghost w-full">Sign in</button>
            </Link>
          </div>

          <p className="mt-6 text-center text-[11px] text-muted-foreground">
            By continuing you agree to our{" "}
            <span className="text-[hsl(var(--rw-royal))]">Terms</span> and{" "}
            <span className="text-[hsl(var(--rw-royal))]">Privacy</span>.
          </p>

          <p className="mt-3 text-center text-[11px] text-muted-foreground">
            <Link to="/admin/login" className="text-[hsl(var(--rw-royal))]">Admin portal</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
