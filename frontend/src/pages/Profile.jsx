import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import Logo from "@/components/Logo";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { TID } from "@/constants/testIds";
import { ArrowLeft, Loader2 } from "lucide-react";

export default function Profile() {
  const { user, refreshProfile } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({
    full_name: user.full_name,
    state: user.state,
    city: user.city,
  });
  const [loading, setLoading] = useState(false);

  const save = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.put("/user/profile", form);
      await refreshProfile();
      toast.success("Profile updated");
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen rw-hero-radial rw-grain">
      <header className="rw-container flex items-center justify-between py-6">
        <Logo size="sm" />
        <Button variant="ghost" onClick={() => nav("/dashboard")} data-testid="profile-back">
          <ArrowLeft className="mr-1 h-4 w-4" /> Back
        </Button>
      </header>

      <main className="rw-container pb-16">
        <div className="mx-auto max-w-2xl">
          <p className="rw-eyebrow">Your profile</p>
          <h1 className="mt-2 rw-serif text-5xl text-foreground">Refine your details.</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Personal information you can edit. Mobile number, Membership ID and Referral chain are permanent.
          </p>

          <Card className="mt-6 rw-card">
            <div className="grid grid-cols-2 gap-4 rounded-xl bg-primary/5 p-4">
              <ReadRow label="Membership ID" value={user.membership_id} />
              <ReadRow label="Mobile" value={`+91 ${user.mobile}`} />
              <ReadRow label="Sponsor" value={user.sponsor_name} />
              <ReadRow label="Sponsor ID" value={user.sponsor_membership_id} />
            </div>

            <form className="mt-6 space-y-4" onSubmit={save}>
              <div>
                <Label htmlFor={TID.profileFullName}>Full name</Label>
                <Input
                  id={TID.profileFullName}
                  data-testid={TID.profileFullName}
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor={TID.profileState}>State</Label>
                  <Input
                    id={TID.profileState}
                    data-testid={TID.profileState}
                    value={form.state}
                    onChange={(e) => setForm({ ...form, state: e.target.value })}
                  />
                </div>
                <div>
                  <Label htmlFor={TID.profileCity}>City</Label>
                  <Input
                    id={TID.profileCity}
                    data-testid={TID.profileCity}
                    value={form.city}
                    onChange={(e) => setForm({ ...form, city: e.target.value })}
                  />
                </div>
              </div>
              <Button
                type="submit"
                className="rounded-full"
                disabled={loading}
                data-testid={TID.profileSave}
              >
                {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Save changes
              </Button>
            </form>
          </Card>
        </div>
      </main>
    </div>
  );
}

function ReadRow({ label, value }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-medium text-foreground">{value || "—"}</div>
    </div>
  );
}
