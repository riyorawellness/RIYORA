import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import Logo from "@/components/Logo";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";
import { TID } from "@/constants/testIds";
import { ArrowRight, Loader2 } from "lucide-react";

export default function Login() {
  const nav = useNavigate();
  const { loginUser } = useAuth();
  const [mobile, setMobile] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!/^[6-9]\d{9}$/.test(mobile)) return toast.error("Enter a valid 10-digit mobile");
    if (password.length < 8) return toast.error("Password must be at least 8 characters");
    setLoading(true);
    try {
      const u = await loginUser(mobile, password);
      toast.success(`Welcome back, ${u.full_name.split(" ")[0]}`);
      nav("/app/home", { replace: true });
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-white">
      <div className="rw-phone rw-safe-top rw-safe-bottom min-h-screen px-6 py-6">
        <Logo size="sm" />
        <div className="mt-10 rw-rise">
          <p className="rw-eyebrow">Welcome back</p>
          <h1 className="mt-1 rw-serif text-4xl text-foreground">Sign in.</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Continue your practice.
          </p>
        </div>

        <form className="mt-8 space-y-4" onSubmit={submit}>
          <div>
            <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Mobile
            </label>
            <input
              className="rw-input mt-1"
              data-testid={TID.loginMobile}
              inputMode="numeric"
              maxLength={10}
              value={mobile}
              onChange={(e) => setMobile(e.target.value)}
              placeholder="10-digit mobile"
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
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button
            type="submit"
            className="rw-btn-pill rw-btn-primary w-full"
            disabled={loading}
            data-testid={TID.loginSubmit}
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
            Sign in
          </button>
        </form>

        <p className="mt-8 text-center text-sm text-muted-foreground">
          New here?{" "}
          <Link to="/register" className="font-semibold text-[hsl(var(--rw-royal))]">
            Create a membership
          </Link>
        </p>
      </div>
    </div>
  );
}
