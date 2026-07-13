import { Link, useNavigate } from "react-router-dom";
import {
  Award,
  BookOpen,
  ChevronRight,
  FileText,
  HelpCircle,
  Landmark,
  LogOut,
  Mail,
  Receipt,
  Repeat,
  ScrollText,
  Settings as SettingsIcon,
  ShieldCheck,
  ShieldQuestion,
  User2,
  Wallet,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useSystemInfo } from "@/hooks/useSystemInfo";
import { TID } from "@/constants/testIds";

export default function Profile() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const sys = useSystemInfo();

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
          {user?.email && <Info k="Email" v={user.email} />}
          {user?.login_method && (
            <Info k="Sign-in" v={
              user.login_method === "google" ? "Google" :
              user.login_method === "email" ? "Email + password" : "Legacy"
            } />
          )}
        </div>

        <div className="mt-4 flex gap-2">
          <button
            onClick={() => nav("/app/profile/edit")}
            className="rw-btn-pill rw-btn-primary flex-1"
            data-testid={TID.profileEditBtn}
          >
            <User2 className="h-4 w-4" /> Edit profile
          </button>
          <button
            onClick={() => nav("/app/profile/change-request")}
            className="rw-btn-pill rw-btn-ghost flex-1"
            data-testid="profile-change-request-btn"
          >
            <Mail className="h-4 w-4" /> Change email / mobile
          </button>
        </div>
      </div>

      {/* sections */}
      <Section title="Your journey">
        <Item to="/app/programs" icon={BookOpen} title="Purchased programs" hint="View your enrolments" />
        <Item to="/app/purchases" icon={Receipt} title="Transactions & invoices" hint="Payment history · GST invoices" testid="profile-nav-purchases" />
        <Item to="/app/commissions" icon={Wallet} title="Commissions" hint="Referral earnings ledger" testid="profile-nav-commissions" />
        <Item to="/app/payouts" icon={Landmark} title="Payouts" hint="Bank transfers · history" testid="profile-nav-payouts" />
        <Item to="/app/reports" icon={FileText} title="Reports" hint="Download PDF reports" testid="profile-nav-reports" />
        <Item to="/app/certificate/inner-peace" icon={Award} title="Certificates" hint="Achievements & completion" />
      </Section>

      <Section title="Account">
        <Item to="/app/payment-history" icon={Receipt} title="Payment history" hint="Your QR payment submissions" testid="profile-nav-payment-history" />
        <Item to="/app/bank" icon={Landmark} title="Bank details" hint="Payout account" />
        <Item to="/app/settings" icon={SettingsIcon} title="Settings" hint="Theme, language, privacy" />
      </Section>

      <Section title="Legal & Support">
        <Item to="/legal/privacy"       icon={ShieldCheck}   title="Privacy Policy"   hint="How we handle your data" testid="profile-nav-privacy" />
        <Item to="/legal/terms"         icon={ScrollText}    title="Terms of Service" hint="Rules of the platform"   testid="profile-nav-terms" />
        <Item to="/legal/data-security" icon={ShieldQuestion}title="Data & Security"  hint="Security controls we run" testid="profile-nav-datasecurity" />
        <Item to="/legal/faq"           icon={HelpCircle}    title="Help & FAQ"       hint="Common questions"        testid="profile-nav-faq" />
        <Item to="/legal/contact"       icon={Mail}          title="Contact Us"       hint={sys?.support_email || "info@riyorawellness.com"} testid="profile-nav-contact" />
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

      {/* App footer */}
      <div className="mt-8 border-t border-neutral-100 pt-6 text-center" data-testid="profile-app-footer">
        <div className="rw-eyebrow">RIYORA Wellness</div>
        <div className="mt-1 text-[11px] text-muted-foreground" data-testid="profile-app-version">
          Version {sys?.application_version || "1.0.0"}
        </div>
        <div className="mt-1 text-[10px] text-muted-foreground" data-testid="profile-app-copyright">
          © {new Date().getFullYear()} {sys?.company_name || "RIYORA Wellness"}. All Rights Reserved.
        </div>
      </div>

      <p className="mt-4 text-center text-[10px] text-muted-foreground">
        <ShieldCheck className="mr-1 inline h-3 w-3" /> Secured with Firebase Authentication · JWT
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

function Item({ to, icon: Icon, title, hint, testid }) {
  return (
    <Link to={to} className="flex items-center gap-3 p-4" data-testid={testid}>
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
