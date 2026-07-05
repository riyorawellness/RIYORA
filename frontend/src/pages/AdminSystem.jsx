import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Save, ShieldCheck, Building2, AlertTriangle, KeyRound, Eye, EyeOff } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { adminApi } from "@/services/admin";
import { formatApiError } from "@/lib/api";
import AdminDangerZone from "@/pages/AdminDangerZone";

export default function AdminSystem() {
  const [sys, setSys] = useState(null);
  const [sec, setSec] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [s, sc] = await Promise.all([adminApi.getSystem(), adminApi.getSecurity()]);
        setSys(s);
        setSec(sc);
      } catch (e) {
        toast.error(formatApiError(e, "Load failed"));
      }
    })();
  }, []);

  const saveSys = async () => {
    setSaving(true);
    try {
      setSys(await adminApi.updateSystem(sys));
      toast.success("System settings saved");
    } catch (e) {
      toast.error(formatApiError(e, "Save failed"));
    } finally {
      setSaving(false);
    }
  };

  const saveSec = async () => {
    setSaving(true);
    try {
      setSec(await adminApi.updateSecurity({
        password_min_length: num(sec.password_min_length),
        otp_expiry_seconds: num(sec.otp_expiry_seconds),
        login_attempt_limit: num(sec.login_attempt_limit),
        session_timeout_minutes: num(sec.session_timeout_minutes),
      }));
      toast.success("Security settings saved");
    } catch (e) {
      toast.error(formatApiError(e, "Save failed"));
    } finally {
      setSaving(false);
    }
  };

  if (!sys || !sec) {
    return <div className="grid place-items-center py-24 text-muted-foreground"><Loader2 className="h-6 w-6 animate-spin" /></div>;
  }

  return (
    <div className="px-6 py-6">
      <p className="rw-eyebrow">Configuration</p>
      <h1 className="mt-1 rw-serif text-4xl">System & security</h1>

      <Tabs defaultValue="company" className="mt-6">
        <TabsList>
          <TabsTrigger value="company" data-testid="sys-tab-company"><Building2 className="mr-1 h-4 w-4" /> Company</TabsTrigger>
          <TabsTrigger value="social" data-testid="sys-tab-social">Social</TabsTrigger>
          <TabsTrigger value="app" data-testid="sys-tab-app">Application</TabsTrigger>
          <TabsTrigger value="security" data-testid="sys-tab-security"><ShieldCheck className="mr-1 h-4 w-4" /> Security</TabsTrigger>
          <TabsTrigger value="danger" data-testid="sys-tab-danger" className="data-[state=active]:bg-red-100 data-[state=active]:text-red-900"><AlertTriangle className="mr-1 h-4 w-4" /> Danger zone</TabsTrigger>
        </TabsList>

        <TabsContent value="company">
          <Card className="rw-card p-6">
            <Fields obj={sys} setObj={setSys} keys={[
              ["company_name", "Company name"],
              ["company_logo_url", "Company logo URL"],
              ["company_address", "Address"],
              ["company_gst_number", "GST number"],
              ["support_email", "Support email"],
              ["support_mobile", "Support mobile"],
              ["website", "Website"],
            ]} />
            <Button onClick={saveSys} disabled={saving} className="mt-4" data-testid="sys-save-company">
              {saving ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Save className="mr-1 h-4 w-4" />}
              Save
            </Button>
          </Card>
        </TabsContent>

        <TabsContent value="social">
          <Card className="rw-card p-6">
            <Fields obj={sys} setObj={setSys} keys={[
              ["social_facebook", "Facebook"],
              ["social_instagram", "Instagram"],
              ["social_youtube", "YouTube"],
              ["social_linkedin", "LinkedIn"],
              ["social_twitter", "X / Twitter"],
            ]} />
            <Button onClick={saveSys} disabled={saving} className="mt-4" data-testid="sys-save-social">
              {saving ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Save className="mr-1 h-4 w-4" />}
              Save
            </Button>
          </Card>
        </TabsContent>

        <TabsContent value="app">
          <Card className="rw-card p-6 space-y-4">
            <div>
              <Label>Application version</Label>
              <Input value={sys.application_version || ""} onChange={(e) => setSys({ ...sys, application_version: e.target.value })} data-testid="sys-app-version" />
            </div>
            <div className="flex items-center gap-3">
              <Switch checked={!!sys.maintenance_mode} onCheckedChange={(v) => setSys({ ...sys, maintenance_mode: v })} data-testid="sys-maintenance" />
              <span className="text-sm">{sys.maintenance_mode ? "Maintenance ON — users see banner" : "Maintenance OFF"}</span>
            </div>
            <Button onClick={saveSys} disabled={saving} data-testid="sys-save-app">
              {saving ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Save className="mr-1 h-4 w-4" />}
              Save
            </Button>
          </Card>
        </TabsContent>

        <TabsContent value="security">
          <div className="mt-4 space-y-4">
            <AdminChangePasswordCard />
            <Card className="rw-card p-6">
              <h3 className="mb-3 rw-serif text-lg">Security policy</h3>
              <Fields
                obj={sec}
                setObj={setSec}
                keys={[
                  ["password_min_length", "Password minimum length"],
                  ["otp_expiry_seconds", "OTP expiry (seconds)"],
                  ["login_attempt_limit", "Login attempts before lock"],
                  ["session_timeout_minutes", "Session timeout (minutes)"],
                ]}
                type="number"
              />
              <Button onClick={saveSec} disabled={saving} className="mt-4" data-testid="sec-save">
                {saving ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Save className="mr-1 h-4 w-4" />}
                Save
              </Button>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="danger">
          <div className="mt-4">
            <AdminDangerZone />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Fields({ obj, setObj, keys, type = "text" }) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {keys.map(([k, label]) => (
        <div key={k}>
          <Label>{label}</Label>
          <Input
            type={type}
            value={obj[k] ?? ""}
            onChange={(e) => setObj({ ...obj, [k]: e.target.value })}
            data-testid={`sys-field-${k}`}
          />
        </div>
      ))}
    </div>
  );
}
function num(v) {
  if (v === "" || v === null || v === undefined) return null;
  const n = Number(v);
  return isNaN(n) ? null : n;
}

function AdminChangePasswordCard() {
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [showOld, setShowOld] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!oldPw || !newPw) return toast.error("Enter both passwords");
    if (newPw.length < 8) return toast.error("New password must be at least 8 characters");
    if (newPw === oldPw) return toast.error("New password must differ from the current one");
    if (newPw !== confirmPw) return toast.error("Confirmation does not match");

    setBusy(true);
    try {
      await adminApi.changeMyPassword(oldPw, newPw);
      toast.success("Password changed. Other sessions have been signed out.");
      setOldPw("");
      setNewPw("");
      setConfirmPw("");
    } catch (err) {
      toast.error(formatApiError(err, "Change failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="rw-card p-6" data-testid="admin-change-password-card">
      <div className="flex items-start gap-3">
        <div className="rounded-full bg-primary/10 p-2">
          <KeyRound className="h-5 w-5 text-primary" />
        </div>
        <div className="flex-1">
          <h3 className="rw-serif text-lg">Change my password</h3>
          <p className="mt-0.5 text-sm text-muted-foreground">
            You must know your current password. All your other signed-in
            devices will be signed out.
          </p>
          <form onSubmit={submit} className="mt-4 grid gap-3 md:grid-cols-2">
            <div className="md:col-span-2">
              <Label>Current password</Label>
              <div className="relative">
                <Input
                  type={showOld ? "text" : "password"}
                  value={oldPw}
                  onChange={(e) => setOldPw(e.target.value)}
                  autoComplete="current-password"
                  className="pr-10"
                  data-testid="admin-pw-old"
                />
                <button
                  type="button"
                  onClick={() => setShowOld((v) => !v)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                  tabIndex={-1}
                >
                  {showOld ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            <div>
              <Label>New password</Label>
              <div className="relative">
                <Input
                  type={showNew ? "text" : "password"}
                  value={newPw}
                  onChange={(e) => setNewPw(e.target.value)}
                  autoComplete="new-password"
                  minLength={8}
                  className="pr-10"
                  data-testid="admin-pw-new"
                />
                <button
                  type="button"
                  onClick={() => setShowNew((v) => !v)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                  tabIndex={-1}
                >
                  {showNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground">Minimum 8 characters</p>
            </div>
            <div>
              <Label>Confirm new password</Label>
              <Input
                type={showNew ? "text" : "password"}
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                autoComplete="new-password"
                minLength={8}
                data-testid="admin-pw-confirm"
              />
            </div>
            <div className="md:col-span-2">
              <Button type="submit" disabled={busy} data-testid="admin-pw-submit">
                {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <KeyRound className="mr-2 h-4 w-4" />}
                Change password
              </Button>
            </div>
          </form>
        </div>
      </div>
    </Card>
  );
}
