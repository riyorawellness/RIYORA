import { Link, useNavigate } from "react-router-dom";
import {
  Award,
  BookOpen,
  ChevronRight,
  HelpCircle,
  Landmark,
  LogOut,
  Mail,
  Repeat,
  Settings as SettingsIcon,
  ShieldCheck,
  User2,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { TID } from "@/constants/testIds";
import { toast } from "sonner";

export default function Profile() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  const doLogout = async () => {
    await logout();
    nav("/welcome", { replace: true });
  };

  return (
    <div className="px-5 pt-6 pb-4">
      <p className="rw-eyebrow">Your account</p>
      <h1 className="mt-1 rw-serif text-4xl">Profile</h1>

      <div className="mt-5 rw-card p-5">
        <div className="flex items-center gap-4">
          <div className="grid h-16 w-16 place-items-center rounded-full bg-[hsl(var(--rw-royal))] font-semibold text-white">
            {user?.full_name?.split(" ").map((s) => s[0]).slice(0, 2).join("")}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate rw-serif text-2xl" data-testid={TID.profileFullName}>{user?.full_name}</div>
            <div className="text-xs text-muted-foreground" data-testid={TID.profileMembershipId}>
              {user?.membership_id} · {user?.city}, {user?.state}
            </div>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 text-xs">
          <Info k="Mobile" v={`+91 ${user?.mobile}`} />
          <Info k="Sponsor" v={user?.sponsor_name || "RIYORA Wellness"} />
        </div>

        <div className="mt-4 flex gap-2">
          <button
            onClick={() => toast.info("Inline profile edit coming next")}
            className="rw-btn-pill rw-btn-ghost flex-1"
            data-testid={TID.profileEditBtn}
          >
            <User2 className="h-4 w-4" /> Edit
          </button>
        </div>
      </div>

      {/* sections */}
      <Section title="Your journey">
        <Item to="/app/programs" icon={BookOpen} title="Purchased programs" hint="View your enrolments" />
        <Item to="/app/certificate/inner-peace" icon={Award} title="Certificates" hint="Achievements & completion" />
        <Item to="/app/programs/inner-peace" icon={Repeat} title="Subscription" hint="Inner Peace · Active" />
      </Section>

      <Section title="Account">
        <Item to="/app/bank" icon={Landmark} title="Bank details" hint="Payout account" />
        <Item to="/app/settings" icon={SettingsIcon} title="Settings" hint="Theme, language, privacy" />
        <Item to="/app/support" icon={HelpCircle} title="Support" hint="FAQ & contact" />
      </Section>

      <button
        onClick={doLogout}
        data-testid={TID.profileLogout}
        className="mt-6 w-full rounded-2xl border border-[hsl(var(--rw-grey-100))] p-4 text-left"
      >
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-full bg-[hsl(356_78%_95%)] text-[hsl(356_78%_45%)]">
            <LogOut className="h-4 w-4" />
          </div>
          <div className="flex-1 font-semibold text-[hsl(356_78%_45%)]">Log out</div>
        </div>
      </button>

      <p className="mt-6 text-center text-[10px] text-muted-foreground">
        <ShieldCheck className="mr-1 inline h-3 w-3" /> Secured with mobile OTP · JWT
      </p>
    </div>
  );
}

function Info({ k, v }) {
  return (
    <div className="rounded-xl bg-[hsl(var(--rw-grey-50))] p-3">
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">{k}</div>
      <div className="mt-0.5 text-sm font-medium">{v}</div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="mt-6">
      <p className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">{title}</p>
      <div className="rw-card divide-y overflow-hidden p-0" style={{ borderColor: "hsl(var(--rw-grey-100))" }}>
        {children}
      </div>
    </div>
  );
}

function Item({ to, icon: Icon, title, hint }) {
  return (
    <Link to={to} className="flex items-center gap-3 p-4">
      <div className="grid h-9 w-9 place-items-center rounded-full bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal))]">
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex-1">
        <div className="font-semibold">{title}</div>
        <div className="text-[11px] text-muted-foreground">{hint}</div>
      </div>
      <ChevronRight className="h-4 w-4 text-muted-foreground" />
    </Link>
  );
}
