import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Save, ShieldCheck, Building2 } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { adminApi } from "@/services/admin";
import { formatApiError } from "@/lib/api";

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
          <Card className="rw-card p-6">
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
