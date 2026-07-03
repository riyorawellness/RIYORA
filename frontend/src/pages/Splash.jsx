import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { TID } from "@/constants/testIds";

export default function Splash() {
  const nav = useNavigate();
  const { user, admin, status } = useAuth();

  useEffect(() => {
    const t = setTimeout(() => {
      if (status === "loading") return;
      if (admin) nav("/admin/dashboard", { replace: true });
      else if (user) nav("/app/home", { replace: true });
      else nav("/welcome", { replace: true });
    }, 1500);
    return () => clearTimeout(t);
  }, [status, user, admin, nav]);

  return (
    <div className="grid min-h-screen place-items-center bg-[hsl(var(--rw-royal-deep))] text-white">
      <div className="text-center rw-fade" data-testid={TID.splashLogo}>
        <div className="mx-auto mb-6 flex h-2 w-16 items-center justify-center gap-1">
          <span className="rw-splash-dot inline-block h-2 w-2 rounded-full bg-white/80" style={{ animationDelay: "0s" }} />
          <span className="rw-splash-dot inline-block h-2 w-2 rounded-full bg-white/80" style={{ animationDelay: "0.2s" }} />
          <span className="rw-splash-dot inline-block h-2 w-2 rounded-full bg-white/80" style={{ animationDelay: "0.4s" }} />
        </div>
        <div className="rw-serif text-6xl font-light tracking-tight">RIYORA</div>
        <div className="mt-1 rw-serif text-2xl italic text-white/70">wellness</div>
        <div className="mt-8 text-[11px] font-semibold uppercase tracking-[0.4em] text-[hsl(var(--rw-gold))]">
          Heal · Learn · Earn
        </div>
      </div>
    </div>
  );
}
