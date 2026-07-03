import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import Logo from "@/components/Logo";
import api, { formatApiError } from "@/lib/api";
import { TID } from "@/constants/testIds";
import { ArrowRight, Loader2 } from "lucide-react";

export default function ForgotPassword() {
  const nav = useNavigate();
  const [step, setStep] = useState("mobile");
  const [loading, setLoading] = useState(false);
  const [mobile, setMobile] = useState("");
  const [otp, setOtp] = useState("");
  const [pwd, setPwd] = useState("");
  const [cpwd, setCpwd] = useState("");
  const [devOtp, setDevOtp] = useState(null);

  const sendOtp = async () => {
    if (!/^[6-9]\d{9}$/.test(mobile)) {
      toast.error("Enter a valid 10-digit mobile.");
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.post("/auth/send-otp", { mobile, purpose: "forgot_password" });
      setDevOtp(data.dev_code);
      setStep("otp");
      toast.success("OTP sent.");
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };

  const verify = async () => {
    setLoading(true);
    try {
      await api.post("/auth/verify-otp", { mobile, purpose: "forgot_password", code: otp });
      setStep("password");
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };

  const reset = async () => {
    if (pwd !== cpwd) {
      toast.error("Passwords do not match");
      return;
    }
    setLoading(true);
    try {
      await api.post("/auth/reset-password", {
        mobile,
        new_password: pwd,
        confirm_password: cpwd,
      });
      toast.success("Password updated. Please sign in.");
      nav("/login", { replace: true });
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
          <p className="rw-eyebrow">Recover access</p>
          <h1 className="mt-2 rw-serif text-4xl text-foreground">Reset your password.</h1>

          <Card className="mt-6 rw-card">
            {step === "mobile" && (
              <div className="space-y-4">
                <div>
                  <Label htmlFor={TID.fpMobile}>Mobile number</Label>
                  <Input
                    id={TID.fpMobile}
                    data-testid={TID.fpMobile}
                    inputMode="numeric"
                    maxLength={10}
                    value={mobile}
                    onChange={(e) => setMobile(e.target.value)}
                    placeholder="10-digit mobile"
                  />
                </div>
                <Button
                  className="w-full rounded-full"
                  onClick={sendOtp}
                  disabled={loading}
                  data-testid={TID.fpSendOtp}
                >
                  {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Send OTP <ArrowRight className="ml-1 h-4 w-4" />
                </Button>
              </div>
            )}

            {step === "otp" && (
              <div className="space-y-4">
                {devOtp && (
                  <div className="rounded-lg border border-dashed border-primary/40 bg-primary/5 p-3 text-xs text-primary">
                    Dev mode OTP: <b>{devOtp}</b>
                  </div>
                )}
                <div>
                  <Label htmlFor={TID.fpOtp}>Enter OTP</Label>
                  <Input
                    id={TID.fpOtp}
                    data-testid={TID.fpOtp}
                    inputMode="numeric"
                    maxLength={6}
                    value={otp}
                    onChange={(e) => setOtp(e.target.value)}
                  />
                </div>
                <Button
                  className="w-full rounded-full"
                  onClick={verify}
                  disabled={loading || otp.length < 4}
                  data-testid={TID.fpVerify}
                >
                  Verify
                </Button>
              </div>
            )}

            {step === "password" && (
              <div className="space-y-4">
                <div>
                  <Label htmlFor={TID.fpNewPassword}>New password</Label>
                  <Input
                    id={TID.fpNewPassword}
                    data-testid={TID.fpNewPassword}
                    type="password"
                    value={pwd}
                    onChange={(e) => setPwd(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor={TID.fpConfirmPassword}>Confirm password</Label>
                  <Input
                    id={TID.fpConfirmPassword}
                    data-testid={TID.fpConfirmPassword}
                    type="password"
                    value={cpwd}
                    onChange={(e) => setCpwd(e.target.value)}
                  />
                </div>
                <Button
                  className="w-full rounded-full"
                  onClick={reset}
                  disabled={loading || pwd.length < 8}
                  data-testid={TID.fpSubmit}
                >
                  {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Update password
                </Button>
              </div>
            )}
          </Card>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Remembered it?{" "}
            <Link to="/login" className="font-medium text-primary hover:underline">
              Back to sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
