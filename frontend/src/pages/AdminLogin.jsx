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
import { ArrowRight, Loader2, ShieldCheck } from "lucide-react";

export default function AdminLogin() {
  const { loginAdmin } = useAuth();
  const nav = useNavigate();
  const [mobile, setMobile] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await loginAdmin(mobile, password);
      toast.success("Admin signed in");
      nav("/admin/dashboard", { replace: true });
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
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" />
            <p className="rw-eyebrow">Admin portal</p>
          </div>
          <h1 className="mt-2 rw-serif text-4xl text-foreground">Administrator sign in.</h1>

          <Card className="mt-6 rw-card">
            <form className="space-y-4" onSubmit={submit}>
              <div>
                <Label htmlFor={TID.adminLoginMobile}>Mobile number</Label>
                <Input
                  id={TID.adminLoginMobile}
                  data-testid={TID.adminLoginMobile}
                  inputMode="numeric"
                  maxLength={10}
                  value={mobile}
                  onChange={(e) => setMobile(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor={TID.adminLoginPassword}>Password</Label>
                <Input
                  id={TID.adminLoginPassword}
                  data-testid={TID.adminLoginPassword}
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              <Button
                type="submit"
                className="w-full rounded-full"
                disabled={loading}
                data-testid={TID.adminLoginSubmit}
              >
                {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Sign in <ArrowRight className="ml-1 h-4 w-4" />
              </Button>
            </form>
          </Card>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            <Link to="/" className="hover:text-primary">
              ← back to public site
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
