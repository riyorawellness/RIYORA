import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  Copy,
  FileText,
  Landmark,
  Loader2,
  MessageCircle,
  Users,
  QrCode,
  Share2,
  Wallet,
  Mail,
  Send,
  X,
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
  const [shareOpen, setShareOpen] = useState(false);
  const [qrOpen, setQrOpen] = useState(false);
  const [qr, setQr] = useState(null);

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

  const link = dash?.referral_link || `${window.location.origin}/join/${user?.membership_id || ""}`;
  const shareText = useMemo(
    () =>
      `Join me on RIYORA Wellness — heal, learn and earn together. Sign up with my referral: ${user?.membership_id}\n${link}`,
    [user, link]
  );

  const copy = async (value, label = "Copied") => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success(label);
    } catch {
      toast.error("Copy failed — copy manually.");
    }
  };

  const openQR = async () => {
    setQrOpen(true);
    if (qr) return;
    try {
      const d = await referralsApi.shareQR();
      setQr(d);
    } catch (e) {
      toast.error(formatApiError(e, "Could not generate QR"));
    }
  };

  const nativeShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: "RIYORA WELLNESS",
          text: shareText,
          url: link,
        });
        return;
      } catch {
        // fall through to modal
      }
    }
    setShareOpen(true);
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

        <div className="mt-4 flex items-center gap-2 rounded-xl bg-white/10 p-2 text-xs">
          <span className="flex-1 truncate" data-testid={TID.referLink}>
            {link}
          </span>
          <button
            onClick={() => copy(link, "Referral link copied")}
            className="rw-chip bg-white/20 text-white"
            data-testid="refer-copy-link-btn"
          >
            <Copy className="h-3 w-3" /> Copy
          </button>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3">
          <button
            onClick={nativeShare}
            className="rw-btn-pill bg-white text-[hsl(var(--rw-royal))]"
            data-testid={TID.referShareBtn}
          >
            <Share2 className="h-4 w-4" /> Share
          </button>
          <button
            onClick={openQR}
            className="rw-btn-pill bg-white/10 text-white"
            data-testid="refer-qr-btn"
          >
            <QrCode className="h-4 w-4" /> QR Code
          </button>
        </div>
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

      {/* Share sheet */}
      {shareOpen && (
        <div
          className="fixed inset-0 z-50 flex items-end bg-black/50 backdrop-blur-sm"
          onClick={() => setShareOpen(false)}
          data-testid="share-sheet"
        >
          <div
            className="w-full rounded-t-3xl bg-white p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between">
              <h3 className="rw-serif text-xl">Share your referral</h3>
              <button onClick={() => setShareOpen(false)}>
                <X className="h-5 w-5 text-muted-foreground" />
              </button>
            </div>
            <div className="grid grid-cols-4 gap-3 text-center">
              <ShareBtn
                icon={MessageCircle}
                label="WhatsApp"
                onClick={() =>
                  window.open(
                    `https://wa.me/?text=${encodeURIComponent(shareText)}`,
                    "_blank"
                  )
                }
                testid="share-whatsapp"
              />
              <ShareBtn
                icon={Send}
                label="SMS"
                onClick={() =>
                  (window.location.href = `sms:?&body=${encodeURIComponent(
                    shareText
                  )}`)
                }
                testid="share-sms"
              />
              <ShareBtn
                icon={Mail}
                label="Email"
                onClick={() =>
                  (window.location.href = `mailto:?subject=${encodeURIComponent(
                    "Join RIYORA Wellness"
                  )}&body=${encodeURIComponent(shareText)}`)
                }
                testid="share-email"
              />
              <ShareBtn
                icon={Copy}
                label="Copy"
                onClick={() => copy(shareText, "Message copied")}
                testid="share-copy"
              />
            </div>
          </div>
        </div>
      )}

      {/* QR modal */}
      {qrOpen && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-6"
          onClick={() => setQrOpen(false)}
          data-testid="qr-modal"
        >
          <div
            className="w-full max-w-xs rounded-3xl bg-white p-5 text-center"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-widest text-[hsl(var(--rw-royal))]">
                RIYORA WELLNESS
              </span>
              <button onClick={() => setQrOpen(false)}>
                <X className="h-4 w-4 text-muted-foreground" />
              </button>
            </div>
            <h3 className="rw-serif text-xl">Scan to join with</h3>
            <div className="rw-serif text-2xl text-[hsl(var(--rw-royal-deep))]">
              {dash?.membership_id}
            </div>
            <div className="mt-3 grid place-items-center rounded-2xl bg-neutral-50 p-4">
              {qr?.data_url ? (
                <img
                  src={qr.data_url}
                  alt="QR"
                  className="h-56 w-56"
                  data-testid="refer-qr-image"
                />
              ) : (
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              )}
            </div>
            <button
              onClick={() => copy(link, "Referral link copied")}
              className="mt-3 w-full rw-btn-pill rw-btn-primary"
              data-testid="qr-copy-link-btn"
            >
              <Copy className="h-4 w-4" /> Copy link
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ShareBtn({ icon: Icon, label, onClick, testid }) {
  return (
    <button
      onClick={onClick}
      className="flex flex-col items-center gap-2 rounded-2xl bg-neutral-50 p-3"
      data-testid={testid}
    >
      <div className="grid h-11 w-11 place-items-center rounded-full bg-white shadow-sm">
        <Icon className="h-5 w-5 text-[hsl(var(--rw-royal))]" />
      </div>
      <span className="text-xs">{label}</span>
    </button>
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
