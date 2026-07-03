import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import Logo from "@/components/Logo";
import { useAuth } from "@/context/AuthContext";
import { TID } from "@/constants/testIds";
import { LogOut, User2, Sparkles, ShieldCheck, Copy } from "lucide-react";
import { toast } from "sonner";

export default function Dashboard() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  const doLogout = async () => {
    await logout();
    nav("/", { replace: true });
  };

  const copyMembership = async () => {
    await navigator.clipboard.writeText(user.membership_id);
    toast.success("Membership ID copied");
  };

  return (
    <div className="min-h-screen rw-hero-radial rw-grain">
      <header className="rw-container flex items-center justify-between py-6">
        <Logo size="sm" />
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            onClick={() => nav("/profile")}
            data-testid={TID.dashProfileLink}
          >
            <User2 className="mr-1 h-4 w-4" /> Profile
          </Button>
          <Button
            variant="secondary"
            onClick={doLogout}
            data-testid={TID.dashLogout}
          >
            <LogOut className="mr-1 h-4 w-4" /> Log out
          </Button>
        </div>
      </header>

      <main className="rw-container pb-16">
        <section className="rw-rise" data-testid={TID.dashWelcome}>
          <p className="rw-eyebrow">Namaste</p>
          <h1 className="mt-2 rw-serif text-5xl text-foreground sm:text-6xl">
            Welcome, <span className="text-primary">{user.full_name.split(" ")[0]}</span>.
          </h1>
          <p className="mt-2 max-w-xl text-muted-foreground">
            Your sanctuary is being prepared. Programs, sessions and your referral
            circle will unlock as the platform rolls out.
          </p>
        </section>

        <section className="mt-10 grid gap-5 md:grid-cols-3">
          <Card className="rw-card md:col-span-2">
            <p className="rw-eyebrow">Your identity</p>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <div
                className="rw-serif text-4xl tracking-tight text-foreground"
                data-testid={TID.dashMembershipId}
              >
                {user.membership_id}
              </div>
              <Button size="sm" variant="ghost" onClick={copyMembership} data-testid="copy-membership-btn">
                <Copy className="mr-1 h-3.5 w-3.5" /> Copy
              </Button>
              <Badge variant="secondary" className="ml-auto">
                <ShieldCheck className="mr-1 h-3.5 w-3.5" /> Active member
              </Badge>
            </div>
            <div className="rw-divider my-5" />
            <div className="grid grid-cols-2 gap-4 text-sm">
              <Info label="Sponsored by" value={user.sponsor_name || "RIYORA Wellness"} />
              <Info label="Sponsor ID" value={user.sponsor_membership_id} />
              <Info label="Mobile" value={`+91 ${user.mobile}`} />
              <Info label="Location" value={`${user.city}, ${user.state}`} />
            </div>
          </Card>

          <Card className="rw-card">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Sparkles className="h-5 w-5" />
            </div>
            <h3 className="mt-5 rw-serif text-2xl text-foreground">Your Referral ID</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Share this with seekers you invite. It&apos;s the same as your Membership ID.
            </p>
            <div className="mt-4 rounded-xl border border-dashed border-primary/40 bg-primary/5 p-4 text-center">
              <div className="rw-serif text-3xl text-primary">{user.membership_id}</div>
            </div>
          </Card>
        </section>

        <section className="mt-10">
          <div className="rw-card">
            <p className="rw-eyebrow">Coming soon</p>
            <h3 className="mt-2 rw-serif text-3xl text-foreground">
              Programs, Activity Meter, Refer &amp; Earn
            </h3>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              This foundation release focuses on secure access, membership and identity.
              The full experience — Inner Peace subscription, Levels 1–5, activity tracking,
              certificates and referral rewards — will unlock in the next phase.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">{label}</div>
      <div className="mt-1 text-foreground">{value}</div>
    </div>
  );
}
