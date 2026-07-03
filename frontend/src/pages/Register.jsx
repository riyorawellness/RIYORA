import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import Logo from "@/components/Logo";
import { TID } from "@/constants/testIds";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { ArrowRight, CheckCircle2, Loader2 } from "lucide-react";

const STEPS = ["mobile", "otp", "details", "confirm"];

export default function Register() {
  const nav = useNavigate();
  const { registerUser } = useAuth();

  const [step, setStep] = useState("mobile");
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    mobile: "",
    otp: "",
    full_name: "",
    state: "",
    city: "",
    referral_id: "",
    password: "",
    confirm_password: "",
  });
  const [sponsor, setSponsor] = useState(null); // {referral_id, sponsor_name, sponsor_membership_id}
  const [devOtp, setDevOtp] = useState(null);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const sendOtp = async () => {
    if (!/^[6-9]\d{9}$/.test(form.mobile)) {
      toast.error("Enter a valid 10-digit Indian mobile number.");
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.post("/auth/send-otp", {
        mobile: form.mobile,
        purpose: "register",
      });
      setDevOtp(data.dev_code);
      setStep("otp");
      toast.success("OTP sent successfully.");
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };

  const verifyOtp = async () => {
    setLoading(true);
    try {
      await api.post("/auth/verify-otp", {
        mobile: form.mobile,
        purpose: "register",
        code: form.otp,
      });
      setStep("details");
      toast.success("Mobile number verified.");
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };

  const checkReferral = async () => {
    if (!/^RW\d{6}$/.test(form.referral_id)) {
      toast.error("Referral ID must look like RW123456.");
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.post("/membership/validate-referral", {
        referral_id: form.referral_id,
      });
      setSponsor(data);
      toast.success(`Sponsor found: ${data.sponsor_name}`);
    } catch (e) {
      setSponsor(null);
      toast.error(formatApiError(e, "Invalid Referral ID"));
    } finally {
      setLoading(false);
    }
  };

  const submit = async () => {
    if (form.password !== form.confirm_password) {
      toast.error("Passwords do not match.");
      return;
    }
    if (form.password.length < 8) {
      toast.error("Password must be at least 8 characters.");
      return;
    }
    if (!sponsor) {
      toast.error("Please validate your Referral ID first.");
      return;
    }
    setStep("confirm");
  };

  const finalize = async () => {
    setLoading(true);
    try {
      const payload = {
        full_name: form.full_name,
        mobile: form.mobile,
        state: form.state,
        city: form.city,
        referral_id: form.referral_id,
        password: form.password,
        confirm_password: form.confirm_password,
      };
      const user = await registerUser(payload);
      toast.success(`Welcome, ${user.full_name}!`);
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
        <div className="mx-auto mt-6 w-full max-w-md">
          <p className="rw-eyebrow">Create your membership</p>
          <h1 className="mt-2 rw-serif text-4xl text-foreground">Begin your journey.</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Membership is invitation-only. Please have a valid Referral ID ready.
          </p>

          <Stepper current={step} />

          <Card className="mt-6 rw-card">
            {step === "mobile" && (
              <div className="space-y-4">
                <div>
                  <Label htmlFor={TID.regMobile}>Mobile number</Label>
                  <Input
                    id={TID.regMobile}
                    data-testid={TID.regMobile}
                    inputMode="numeric"
                    maxLength={10}
                    value={form.mobile}
                    onChange={set("mobile")}
                    placeholder="10-digit mobile"
                  />
                </div>
                <Button
                  className="w-full rounded-full"
                  onClick={sendOtp}
                  disabled={loading}
                  data-testid={TID.regSendOtp}
                >
                  {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Send OTP <ArrowRight className="ml-1 h-4 w-4" />
                </Button>
              </div>
            )}

            {step === "otp" && (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  We&apos;ve sent a 6-digit code to <b>+91 {form.mobile}</b>. It expires in 5 minutes.
                </p>
                {devOtp && (
                  <div className="rounded-lg border border-dashed border-primary/40 bg-primary/5 p-3 text-xs text-primary">
                    Dev mode OTP: <b>{devOtp}</b> (any real code sent is also accepted)
                  </div>
                )}
                <div>
                  <Label htmlFor={TID.regOtp}>Enter OTP</Label>
                  <Input
                    id={TID.regOtp}
                    data-testid={TID.regOtp}
                    inputMode="numeric"
                    maxLength={6}
                    value={form.otp}
                    onChange={set("otp")}
                    placeholder="6-digit code"
                  />
                </div>
                <div className="flex gap-3">
                  <Button variant="ghost" onClick={() => setStep("mobile")} disabled={loading}>
                    Change number
                  </Button>
                  <Button
                    onClick={verifyOtp}
                    disabled={loading || form.otp.length < 4}
                    className="ml-auto rounded-full"
                    data-testid={TID.regVerifyOtp}
                  >
                    {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Verify
                  </Button>
                </div>
              </div>
            )}

            {step === "details" && (
              <div className="space-y-4">
                <div>
                  <Label htmlFor={TID.regFullName}>Full name</Label>
                  <Input
                    id={TID.regFullName}
                    data-testid={TID.regFullName}
                    value={form.full_name}
                    onChange={set("full_name")}
                    placeholder="e.g. Arjun Sharma"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label htmlFor={TID.regState}>State</Label>
                    <Input
                      id={TID.regState}
                      data-testid={TID.regState}
                      value={form.state}
                      onChange={set("state")}
                    />
                  </div>
                  <div>
                    <Label htmlFor={TID.regCity}>City</Label>
                    <Input
                      id={TID.regCity}
                      data-testid={TID.regCity}
                      value={form.city}
                      onChange={set("city")}
                    />
                  </div>
                </div>
                <div>
                  <Label htmlFor={TID.regReferral}>Referral ID</Label>
                  <div className="flex gap-2">
                    <Input
                      id={TID.regReferral}
                      data-testid={TID.regReferral}
                      value={form.referral_id}
                      onChange={(e) => {
                        setSponsor(null);
                        setForm({ ...form, referral_id: e.target.value.toUpperCase() });
                      }}
                      placeholder="RW000000"
                      maxLength={8}
                    />
                    <Button
                      variant="secondary"
                      onClick={checkReferral}
                      disabled={loading || form.referral_id.length !== 8}
                      data-testid={TID.regReferralCheck}
                    >
                      Verify
                    </Button>
                  </div>
                  {sponsor && (
                    <div
                      className="mt-2 flex items-start gap-2 rounded-lg bg-primary/5 p-3 text-xs"
                      data-testid={TID.regSponsorInfo}
                    >
                      <CheckCircle2 className="mt-0.5 h-4 w-4 text-primary" />
                      <div>
                        <div className="text-muted-foreground">Sponsored by</div>
                        <div className="text-sm font-semibold text-foreground">
                          {sponsor.sponsor_name}
                        </div>
                        <div className="text-muted-foreground">
                          Membership ID: {sponsor.sponsor_membership_id}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label htmlFor={TID.regPassword}>Password</Label>
                    <Input
                      id={TID.regPassword}
                      data-testid={TID.regPassword}
                      type="password"
                      value={form.password}
                      onChange={set("password")}
                    />
                  </div>
                  <div>
                    <Label htmlFor={TID.regConfirmPassword}>Confirm password</Label>
                    <Input
                      id={TID.regConfirmPassword}
                      data-testid={TID.regConfirmPassword}
                      type="password"
                      value={form.confirm_password}
                      onChange={set("confirm_password")}
                    />
                  </div>
                </div>
                <Button
                  className="w-full rounded-full"
                  onClick={submit}
                  disabled={loading || !sponsor || !form.full_name || !form.state || !form.city}
                  data-testid={TID.regSubmit}
                >
                  Continue <ArrowRight className="ml-1 h-4 w-4" />
                </Button>
              </div>
            )}

            {step === "confirm" && sponsor && (
              <div className="space-y-4">
                <div className="rounded-xl bg-primary/5 p-4 text-sm">
                  <p className="rw-eyebrow">Please confirm</p>
                  <div className="mt-3 space-y-1 text-foreground">
                    <Row label="Full name" value={form.full_name} />
                    <Row label="Mobile" value={`+91 ${form.mobile}`} />
                    <Row label="State / City" value={`${form.state} · ${form.city}`} />
                    <Row label="Sponsored by" value={`${sponsor.sponsor_name}`} />
                    <Row label="Sponsor ID" value={sponsor.sponsor_membership_id} />
                  </div>
                </div>
                <div className="flex gap-3">
                  <Button variant="ghost" onClick={() => setStep("details")} disabled={loading}>
                    Back
                  </Button>
                  <Button
                    onClick={finalize}
                    disabled={loading}
                    className="ml-auto rounded-full"
                    data-testid="reg-confirm-btn"
                  >
                    {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Confirm & create account
                  </Button>
                </div>
              </div>
            )}
          </Card>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Already a member?{" "}
            <Link to="/login" className="font-medium text-primary hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-xs uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className="text-sm font-medium text-foreground">{value}</span>
    </div>
  );
}

function Stepper({ current }) {
  const idx = STEPS.indexOf(current);
  return (
    <div className="mt-6 flex items-center gap-2">
      {STEPS.map((s, i) => (
        <div
          key={s}
          className={`h-1.5 flex-1 rounded-full transition-all ${
            i <= idx ? "bg-primary" : "bg-primary/15"
          }`}
        />
      ))}
    </div>
  );
}
