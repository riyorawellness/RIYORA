import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Copy, Landmark, QrCode, Share2, Users } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { EARNINGS, TEAM } from "@/mock/data";
import { TID } from "@/constants/testIds";

export default function ReferEarn() {
  const { user } = useAuth();
  const link = `${window.location.origin}/join/${user?.membership_id}`;

  const copyLink = async () => {
    await navigator.clipboard.writeText(link);
    toast.success("Referral link copied");
  };
  const share = async () => {
    if (navigator.share) {
      try {
        await navigator.share({ title: "RIYORA WELLNESS", text: "Join me on RIYORA", url: link });
      } catch {
        /* user cancelled share */
      }
    } else {
      copyLink();
    }
  };

  const totalTeam = TEAM.direct.length + TEAM.level_2.length + TEAM.level_3.length;

  return (
    <div className="px-5 pt-6">
      <p className="rw-eyebrow">Refer &amp; Earn</p>
      <h1 className="mt-1 rw-serif text-4xl">Your circle</h1>

      {/* Referral card */}
      <div className="mt-5 rw-card-royal p-5">
        <p className="text-[11px] uppercase tracking-[0.24em] text-white/70">Referral ID</p>
        <div className="mt-1 flex items-baseline gap-3">
          <div className="rw-serif text-4xl" data-testid={TID.referMembershipId}>{user?.membership_id}</div>
          <button
            onClick={() => { navigator.clipboard.writeText(user?.membership_id); toast.success("Copied"); }}
            className="rw-chip bg-white/15 text-white"
          >
            <Copy className="h-3 w-3" /> Copy
          </button>
        </div>

        <div className="mt-5">
          <p className="text-[11px] uppercase tracking-[0.24em] text-white/70">Referral link</p>
          <div className="mt-1 flex items-center gap-2 rounded-xl bg-white/10 p-2 text-xs">
            <span className="flex-1 truncate" data-testid={TID.referLink}>{link}</span>
            <button onClick={copyLink} className="rw-chip bg-white/20 text-white">Copy</button>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3">
          <button onClick={share} className="rw-btn-pill bg-white text-[hsl(var(--rw-royal))]" data-testid={TID.referShareBtn}>
            <Share2 className="h-4 w-4" /> Share
          </button>
          <button
            onClick={() => toast.info("QR generation coming soon")}
            className="rw-btn-pill bg-white/10 text-white"
          >
            <QrCode className="h-4 w-4" /> QR Code
          </button>
        </div>
      </div>

      {/* earnings */}
      <div className="mt-5 grid grid-cols-2 gap-3" data-testid={TID.referTotalEarnings}>
        <Stat label="Total earnings" value={`₹${EARNINGS.total.toLocaleString("en-IN")}`} accent="gold" />
        <Stat label="This month" value={`₹${EARNINGS.current_month.toLocaleString("en-IN")}`} />
        <Stat label="Pending payout" value={`₹${EARNINGS.pending.toLocaleString("en-IN")}`} />
        <Stat label="Paid payout" value={`₹${EARNINGS.paid.toLocaleString("en-IN")}`} />
      </div>

      {/* team summary */}
      <div className="mt-5 rw-card p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="rw-eyebrow">Team</p>
            <h3 className="mt-1 rw-serif text-xl">{totalTeam} members</h3>
            <p className="text-xs text-muted-foreground">
              L1: {TEAM.direct.length} · L2: {TEAM.level_2.length} · L3: {TEAM.level_3.length}
            </p>
          </div>
          <Link to="/app/team" className="rw-btn-pill rw-btn-ghost" data-testid={TID.referViewTeam}>
            <Users className="h-4 w-4" /> View team
          </Link>
        </div>
      </div>

      {/* quick actions */}
      <div className="mt-5 grid grid-cols-2 gap-3">
        <Link to="/app/bank" className="rw-card p-4">
          <div className="grid h-9 w-9 place-items-center rounded-full bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal))]">
            <Landmark className="h-4 w-4" />
          </div>
          <div className="mt-3 rw-serif text-lg">Bank details</div>
          <div className="text-[11px] text-muted-foreground">for future payouts</div>
        </Link>
        <Link to="/app/profile" className="rw-card p-4">
          <div className="grid h-9 w-9 place-items-center rounded-full bg-[hsl(var(--rw-gold-soft))] text-[hsl(35_60%_38%)]">
            <Users className="h-4 w-4" />
          </div>
          <div className="mt-3 rw-serif text-lg">Reports</div>
          <div className="text-[11px] text-muted-foreground">available soon</div>
        </Link>
      </div>
    </div>
  );
}

function Stat({ label, value, accent }) {
  const isGold = accent === "gold";
  return (
    <div className="rw-card p-4">
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className={`mt-1 rw-serif text-2xl ${isGold ? "text-[hsl(35_60%_38%)]" : "text-[hsl(var(--rw-royal-deep))]"}`}>
        {value}
      </div>
    </div>
  );
}
