import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  Copy,
  FileText,
  Landmark,
  Loader2,
  Users,
  Wallet,
} from "lucide-react";

import { useAuth } from "@/context/AuthContext";
import { TID } from "@/constants/testIds";
import { referralsApi } from "@/services/referrals";
import { formatApiError } from "@/lib/api";

const STATUS_TINT = {
  green: "bg-emerald-500",
  yellow: "bg-amber-500",
  red: "bg-rose-500",
  no_subscription: "bg-neutral-300",
};

const STATUS_LABEL = {
  green: "Active",
  yellow: "Grace",
  red: "Inactive",
  no_subscription: "No subscription",
};

export default function ReferEarn() {
  const { user } = useAuth();
  const [dash, setDash] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const d = await referralsApi.dashboard();
        setDash(d);
      } catch (e) {
        toast.error(formatApiError(e, "Could not load dashboard"));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const copy = async (value, label = "Copied") => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success(label);
    } catch {
      // Fallback for restrictive WebView contexts.
      try {
        const ta = document.createElement("textarea");
        ta.value = value;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        toast.success(label);
      } catch {
        toast.error("Copy failed — copy manually.");
      }
    }
  };

  if (loading) {
    return (
      <div className="grid place-items-center py-24 text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  const e = dash?.earnings || {};
  const activity = dash?.activity || { status: "no_subscription" };
  const teamCounts = dash?.team_counts || { L1: 0, L2: 0, L3: 0 };

  return (
    <div className="px-5 pt-6 pb-24">
      <p className="rw-eyebrow">Refer &amp; Earn</p>
      <h1 className="mt-1 rw-serif text-4xl">Your circle</h1>

      {/* Referral card */}
      <div className="mt-5 rw-card-royal p-5">
        <div className="flex items-baseline justify-between">
          <div>
            <p className="text-[11px] uppercase tracking-[0.24em] text-white/70">
              Referral ID
            </p>
            <div
              className="mt-1 rw-serif text-4xl"
              data-testid={TID.referMembershipId}
            >
              {dash?.membership_id}
            </div>
          </div>
          <div className="inline-flex items-center gap-1 rounded-full bg-white/15 px-2.5 py-1 text-[11px]">
            <span
              className={`h-2 w-2 rounded-full ${STATUS_TINT[activity.status]}`}
            />
            {STATUS_LABEL[activity.status]}
          </div>
        </div>

        <button
          onClick={() => copy(dash?.membership_id, "Referral ID copied")}
          className="rw-btn-pill mt-4 w-full bg-white text-[hsl(var(--rw-royal))]"
          data-testid="refer-copy-id-btn"
        >
          <Copy className="h-4 w-4" /> Copy referral ID
        </button>
      </div>

      {/* earnings */}
      <div
        className="mt-5 grid grid-cols-2 gap-3"
        data-testid={TID.referTotalEarnings}
      >
        <Stat label="Lifetime earnings" value={inr(e.lifetime)} accent="gold" />
        <Stat label="This month" value={inr(e.current_month)} />
        <Stat label="Pending" value={inr(e.pending)} />
        <Stat label="Approved (payable)" value={inr(e.approved)} />
        <Stat label="Paid out" value={inr(e.paid)} />
        <Stat
          label="Downline"
          value={`${dash?.total_downline || 0} members`}
        />
      </div>

      {/* activity ring */}
      <div className="mt-5 rw-card p-4">
        <div className="flex items-center gap-4">
          <div className="rw-ring" style={{ "--p": pctOf(activity.completed, activity.required) }}>
            <div className="text-center">
              <div className="rw-serif text-2xl leading-none text-[hsl(var(--rw-royal-deep))]">
                {activity.completed || 0}/{activity.required || 4}
              </div>
              <div className="mt-0.5 text-[10px] uppercase tracking-widest text-muted-foreground">
                sessions
              </div>
            </div>
          </div>
          <div className="flex-1">
            <p className="rw-eyebrow">Eligibility</p>
            <h3 className="mt-1 rw-serif text-xl">Referral status</h3>
            <p className="text-xs text-muted-foreground">
              {activity.status === "green"
                ? "You're active — commissions credited on purchases."
                : activity.status === "yellow"
                ? `Complete ${activity.remaining} more Inner Peace session(s) to activate.`
                : activity.status === "red"
                ? "Cycle ended. Renew Inner Peace to re-activate."
                : "Subscribe to Inner Peace to start earning referral rewards."}
            </p>
          </div>
        </div>
      </div>

      {/* team summary */}
      <div className="mt-5 rw-card p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="rw-eyebrow">Team</p>
            <h3 className="mt-1 rw-serif text-xl">
              {dash?.total_downline || 0} members
            </h3>
            <p className="text-xs text-muted-foreground">
              L1: {teamCounts.L1} · L2: {teamCounts.L2} · L3: {teamCounts.L3}
            </p>
          </div>
          <Link
            to="/app/team"
            className="rw-btn-pill rw-btn-ghost"
            data-testid={TID.referViewTeam}
          >
            <Users className="h-4 w-4" /> View team
          </Link>
        </div>
      </div>

      {/* quick actions */}
      <div className="mt-5 grid grid-cols-2 gap-3">
        <Link to="/app/commissions" className="rw-card p-4" data-testid="refer-nav-commissions">
          <div className="grid h-9 w-9 place-items-center rounded-full bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal))]">
            <Wallet className="h-4 w-4" />
          </div>
          <div className="mt-3 rw-serif text-lg">Commissions</div>
          <div className="text-[11px] text-muted-foreground">
            Ledger with L1 · L2 · L3
          </div>
        </Link>
        <Link to="/app/payouts" className="rw-card p-4" data-testid="refer-nav-payouts">
          <div className="grid h-9 w-9 place-items-center rounded-full bg-[hsl(var(--rw-gold-soft))] text-[hsl(35_60%_38%)]">
            <Landmark className="h-4 w-4" />
          </div>
          <div className="mt-3 rw-serif text-lg">Payouts</div>
          <div className="text-[11px] text-muted-foreground">
            Bank transfers · history
          </div>
        </Link>
        <Link to="/app/bank" className="rw-card p-4">
          <div className="grid h-9 w-9 place-items-center rounded-full bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal))]">
            <Landmark className="h-4 w-4" />
          </div>
          <div className="mt-3 rw-serif text-lg">Bank details</div>
          <div className="text-[11px] text-muted-foreground">
            For payouts
          </div>
        </Link>
        <Link to="/app/reports" className="rw-card p-4" data-testid="refer-nav-reports">
          <div className="grid h-9 w-9 place-items-center rounded-full bg-[hsl(var(--rw-gold-soft))] text-[hsl(35_60%_38%)]">
            <FileText className="h-4 w-4" />
          </div>
          <div className="mt-3 rw-serif text-lg">Reports</div>
          <div className="text-[11px] text-muted-foreground">
            PDF export · 5 reports
          </div>
        </Link>
      </div>

    </div>
  );
}

function Stat({ label, value, accent }) {
  const isGold = accent === "gold";
  return (
    <div className="rw-card p-4">
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
      <div
        className={`mt-1 rw-serif text-2xl ${
          isGold
            ? "text-[hsl(35_60%_38%)]"
            : "text-[hsl(var(--rw-royal-deep))]"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function inr(v) {
  if (typeof v === "string") return v;
  return `₹${Number(v || 0).toLocaleString("en-IN", {
    maximumFractionDigits: 0,
  })}`;
}

function pctOf(a, b) {
  const num = Number(a) || 0;
  const den = Number(b) || 1;
  return Math.min(100, Math.round((num / den) * 100));
}
