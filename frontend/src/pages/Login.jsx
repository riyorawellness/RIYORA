import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
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
    if (!/^[6-9]\d{9}$/.test(mobile)) {
      toast.error("Enter a valid 10-digit mobile.");
      return;
    }
    if (password.length < 8) {
      toast.error("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      const user = await loginUser(mobile, password);
      toast.success(`Welcome back, ${user.full_name}`);
      nav("/dashboard", { replace: true });
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen rw-hero-radial rw-grain">
      <div className="rw-container flex flex-col py-8">
        <Logo size="sm" />
        <div className="mx-auto mt-8 w-full max-w-md">
          <p className="rw-eyebrow">Welcome back</p>
          <h1 className="mt-2 rw-serif text-4xl text-foreground">Return to your practice.</h1>

          <Card className="mt-6 rw-card">
            <form className="space-y-4" onSubmit={submit}>
              <div>
                <Label htmlFor={TID.loginMobile}>Mobile number</Label>
                <Input
                  id={TID.loginMobile}
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
                  <Label htmlFor={TID.loginPassword}>Password</Label>
                  <Link
                    to="/forgot-password"
                    data-testid={TID.loginForgot}
                    className="text-xs font-medium text-primary hover:underline"
                  >
                    Forgot password?
                  </Link>
                </div>
                <Input
                  id={TID.loginPassword}
                  data-testid={TID.loginPassword}
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              <Button
                type="submit"
                className="w-full rounded-full"
                disabled={loading}
                data-testid={TID.loginSubmit}
              >
                {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Sign in <ArrowRight className="ml-1 h-4 w-4" />
              </Button>
            </form>
          </Card>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            New here?{" "}
            <Link to="/register" className="font-medium text-primary hover:underline">
              Create a membership
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
