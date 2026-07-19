import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { Bell, Clock, HelpCircle, Play, PlusCircle } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import Logo from "@/components/Logo";
import { TID } from "@/constants/testIds";
import { activityApi } from "@/services/referrals";
import { manualPaymentsApi } from "@/services/manualPayments";
import { notificationsApi } from "@/services/notifications";
import { programsApi } from "@/services/programs";
import ActiveBanners from "@/components/ActiveBanners";
import { formatApiError } from "@/lib/api";

const FALLBACK_THUMB =
  "https://images.unsplash.com/photo-1518241353330-0f7941c2d9b5?auto=format&fit=crop&w=800&q=60";
const FALLBACK_BANNER =
  "https://images.unsplash.com/photo-1506126613408-eca07ce68773?auto=format&fit=crop&w=1400&q=60";

const STATUS_COLOR = {
  green: "hsl(141 60% 42%)",
  yellow: "hsl(42 78% 55%)",
  red: "hsl(356 78% 55%)",
  no_plan: "hsl(220 10% 60%)",
  no_subscription: "hsl(220 10% 60%)",
};
const STATUS_LABEL = {
  green: "Active",
  yellow: "Active · Grace",
  red: "Inactive",
  no_plan: "No active plan",
  no_subscription: "No active plan",
};

export default function Home() {
  const { user } = useAuth();
  const first = user?.full_name?.split(" ")[0] ?? "Seeker";
  const [meter, setMeter] = useState(null);
  const [logging, setLogging] = useState(false);
  const [pending, setPending] = useState([]);
  const [unreadNotifs, setUnreadNotifs] = useState(0);
  const [featured, setFeatured] = useState(null);
  const [continueCard, setContinueCard] = useState(null);

  const loadMeter = async () => {
    try {
      const m = await activityApi.meter();
      setMeter(m);
    } catch (e) {
      // silent
    }
  };

  const loadPending = async () => {
    try {
      const r = await manualPaymentsApi.myPending();
      setPending(r.items || []);
    } catch (e) {
      // silent
    }
  };

  const loadNotifCount = async () => {
    try {
      const r = await notificationsApi.unreadCount();
      setUnreadNotifs(r.unread || 0);
    } catch (e) {
      // silent
    }
  };

  const loadPrograms = async () => {
    try {
      const [others, cont] = await Promise.all([
        programsApi
          .list({ is_featured: true, is_active: true, page: 1, page_size: 6, sort: "order_index,level" })
          .catch(() => ({ items: [] })),
        programsApi.continueLearning().catch(() => null),
      ]);
      setFeatured((others?.items || [])[0] || null);
      setContinueCard(cont || null);
    } catch (e) {
      // silent
    }
  };

  useEffect(() => {
    loadMeter();
    loadPending();
    loadNotifCount();
    loadPrograms();
    // Refresh unread every 30s so newly-broadcast admin alerts show quickly
    const t = setInterval(loadNotifCount, 30000);
    return () => clearInterval(t);
  }, []);

  const logSession = async () => {
    setLogging(true);
    try {
      const res = await activityApi.logSession({ source: "manual" });
      setMeter(res.meter);
      toast.success("Session logged");
    } catch (e) {
      toast.error(formatApiError(e, "Could not log session"));
    } finally {
      setLogging(false);
    }
  };

  const completed = meter?.completed ?? 0;
  const required = meter?.required ?? 4;
  const percent = Math.min(100, Math.round((completed / (required || 1)) * 100));
  const status = meter?.status || "no_subscription";

  return (
    <div className="px-5 pt-4">
      {/* header */}
      <div className="flex items-center justify-between">
        <Logo size="sm" />
        <Link to="/app/notifications" className="relative grid h-10 w-10 place-items-center rounded-full bg-[hsl(var(--rw-grey-50))]" data-testid="home-notif-bell">
          <Bell className="h-4 w-4 text-[hsl(var(--rw-royal-deep))]" />
          {unreadNotifs > 0 && (
            <span
              className="absolute -right-1 -top-1 grid h-5 min-w-[20px] place-items-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white"
              data-testid="home-notif-badge"
            >
              {unreadNotifs > 99 ? "99+" : unreadNotifs}
            </span>
          )}
        </Link>
      </div>

      {/* welcome card */}
      <div className="mt-4 rw-card-royal p-5" data-testid={TID.homeMembershipId}>
        <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-white/70">Namaste, {first}</p>
        <div className="mt-2 flex items-end justify-between gap-3">
          <div>
            <div className="rw-serif text-3xl">{user?.membership_id}</div>
            <div className="mt-1 text-xs text-white/70">Your Membership · Referral ID</div>
          </div>
          <div className="text-right">
            <div className="text-[11px] uppercase tracking-widest text-white/70">Status</div>
            <div className="mt-1 inline-flex items-center gap-1 rounded-full bg-white/15 px-2.5 py-1 text-xs">
              <span className="h-2 w-2 rounded-full" style={{ background: STATUS_COLOR[status] }} />
              {STATUS_LABEL[status]}
            </div>
          </div>
        </div>
      </div>

      {/* Home banners */}
      <ActiveBanners placement="home" className="mt-4" />

      {/* Pending payment verification card (Phase 11) */}
      {pending.length > 0 && (
        <section className="mt-4 space-y-3" data-testid="home-pending-payments">
          {pending.map((r) => (
            <div key={r.id} className="rw-card overflow-hidden border-2 border-amber-400 bg-amber-50 p-0" data-testid={`home-pending-${r.program_id}`}>
              <div className="flex items-center gap-2 border-b border-amber-200 bg-amber-100 px-4 py-2 text-[11px] font-semibold uppercase tracking-widest text-amber-800">
                <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-amber-500" />
                Payment Verification Pending
              </div>
              <div className="p-4">
                <div className="flex items-start gap-3">
                  <div className="grid h-11 w-11 place-items-center rounded-full bg-amber-500 text-white">
                    <Clock className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="rw-serif truncate text-lg">{r.program_name}</h3>
                    <div className="mt-0.5 text-[11px] text-neutral-700">
                      {r.program_level != null && <>Level {r.program_level} · </>}
                      Amount ₹{Number(r.total).toLocaleString("en-IN")}
                    </div>
                    <div className="mt-1 text-[11px] text-neutral-600">
                      Submitted {new Date(r.submitted_at).toLocaleDateString()}
                      &nbsp;·&nbsp; UTR <span className="font-mono">{r.utr}</span>
                    </div>
                  </div>
                </div>
                <p className="mt-3 text-xs text-neutral-700">
                  Your payment has been received and is awaiting verification by the RIYORA Wellness team.
                  Program access will be activated immediately after successful verification.
                </p>
                <div className="mt-3 flex gap-2">
                  <Link
                    to="/app/payment-history"
                    className="flex-1 rounded-lg border border-amber-500 bg-white py-2 text-center text-xs font-semibold text-amber-800"
                    data-testid={`home-pending-view-${r.program_id}`}
                  >
                    View payment details
                  </Link>
                  <Link
                    to="/legal/contact"
                    className="flex-1 rounded-lg bg-amber-500 py-2 text-center text-xs font-semibold text-white"
                    data-testid={`home-pending-support-${r.program_id}`}
                  >
                    <HelpCircle className="mr-1 inline h-3 w-3" /> Contact support
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </section>
      )}

      {/* Account inactive banner (must play 4 sessions to reactivate) */}
      {meter && (meter.status === "red" || meter.status === "no_plan" || meter.status === "no_subscription") && (
        <section
          className="mt-4 rw-card overflow-hidden border-2 border-red-300 bg-red-50 p-0"
          data-testid="home-inactive-banner"
        >
          <div className="flex items-center gap-2 border-b border-red-200 bg-red-100 px-4 py-2 text-[11px] font-semibold uppercase tracking-widest text-red-800">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-red-500" />
            Account inactive
          </div>
          <div className="p-4">
            <p className="rw-serif text-lg text-red-900">
              {meter.status === "red"
                ? "You missed your last activity cycle."
                : "You don't have any active plan yet."}
            </p>
            <p className="mt-1 text-xs text-red-800/80">
              {meter.status === "red"
                ? `Complete ${meter.required} module sessions in the next ${meter.days_left ?? 30} days to reactivate. Referral rewards resume automatically.`
                : "Purchase any program (or subscribe) and complete 4 module sessions per 30-day cycle to earn referral rewards."}
            </p>
            <div className="mt-3">
              <Link
                to="/app/programs"
                className="inline-block rounded-lg bg-red-600 px-4 py-2 text-xs font-semibold text-white"
                data-testid="home-inactive-cta"
              >
                {meter.status === "red" ? "Play a session" : "Browse programs"}
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* activity meter */}
      <section className="mt-5 rw-card p-5" data-testid={TID.homeActivityMeter}>
        <div className="flex items-center gap-4">
          <div className="rw-ring" style={{ "--p": percent }}>
            <div className="text-center">
              <div className="rw-serif text-2xl leading-none text-[hsl(var(--rw-royal-deep))]">
                {completed}/{required}
              </div>
              <div className="mt-0.5 text-[10px] uppercase tracking-widest text-muted-foreground">sessions</div>
            </div>
          </div>
          <div className="flex-1">
            <p className="rw-eyebrow">Activity Meter</p>
            <h3 className="mt-1 rw-serif text-xl">Current cycle</h3>
            <p className="text-xs text-muted-foreground">
              {meter?.cycle_start
                ? `${formatDate(meter.cycle_start)} → ${formatDate(meter.cycle_end)}`
                : "Purchase or subscribe to start your activity cycle"}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {status === "green" ? (
                <span className="rw-chip rw-chip-gold">Eligible for rewards</span>
              ) : (
                <span className="rw-chip rw-chip-sky">
                  {meter?.remaining || required} session
                  {(meter?.remaining || required) !== 1 ? "s" : ""} remaining
                </span>
              )}
            </div>
          </div>
        </div>
        {meter && meter.has_active_plan && (
          <button
            onClick={logSession}
            disabled={logging || completed >= required}
            className="mt-4 flex w-full items-center justify-center gap-2 rw-btn-pill bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal-deep))] disabled:opacity-50"
            data-testid="home-log-session-btn"
          >
            <PlusCircle className="h-4 w-4" />
            {completed >= required ? "Cycle complete" : "Mark today's session"}
          </button>
        )}
      </section>

      {/* Continue-learning / featured card */}
      {(() => {
        const cardProgram = continueCard?.program || featured;
        if (!cardProgram) return null;
        const thumb =
          cardProgram.thumbnail_url ||
          cardProgram.banner_url ||
          FALLBACK_THUMB;
        const progressPct = Math.round(continueCard?.progress?.percentage || 0);
        const currentModule = continueCard?.current_module;
        const hasContinue = !!continueCard;
        const chipLabel = cardProgram.level != null
          ? `Level ${cardProgram.level}`
          : "Program";
        return (
          <Link
            to={`/app/programs/${cardProgram.id}`}
            className="mt-5 block rw-card overflow-hidden p-0"
            data-testid={TID.homeInnerPeaceCard}
          >
            <div className="relative">
              <img src={thumb} alt="" className="h-40 w-full object-cover" />
              <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
              <div className="absolute inset-x-0 bottom-0 p-4 text-white">
                <span className="rw-chip rw-chip-gold">{chipLabel}</span>
                <h3 className="mt-1 rw-serif text-2xl">{cardProgram.name}</h3>
                <p className="text-xs text-white/80">
                  {cardProgram.short_description || cardProgram.description || ""}
                </p>
              </div>
              <div className="absolute right-4 top-4 grid h-11 w-11 place-items-center rounded-full bg-white/95 text-[hsl(var(--rw-royal))] shadow-lg">
                <Play className="h-5 w-5 fill-current" />
              </div>
            </div>
            {hasContinue && (
              <div className="flex items-center justify-between p-4">
                <div className="text-sm">
                  <div className="font-semibold text-foreground">Continue learning</div>
                  <div className="text-xs text-muted-foreground">
                    {currentModule
                      ? `Module ${currentModule.module_number} · ${currentModule.name}`
                      : "Resume where you left off"}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-[11px] uppercase tracking-widest text-muted-foreground">
                    Progress
                  </div>
                  <div className="text-lg font-semibold text-[hsl(var(--rw-royal))]">
                    {progressPct}%
                  </div>
                </div>
              </div>
            )}
          </Link>
        );
      })()}

      {/* featured */}
      {featured && (
        <section className="mt-5" data-testid={TID.homeFeaturedProgram}>
          <div className="mb-2 flex items-baseline justify-between">
            <h2 className="rw-serif text-2xl">Featured program</h2>
            <Link to="/app/programs" className="text-xs font-semibold text-[hsl(var(--rw-royal))]">See all</Link>
          </div>
          <Link to={`/app/programs/${featured.id}`} className="block rw-card overflow-hidden p-0">
            <img
              src={featured.thumbnail_url || featured.banner_url || FALLBACK_BANNER}
              alt=""
              className="h-36 w-full object-cover"
            />
            <div className="p-4">
              <p className="rw-eyebrow">
                {featured.level != null ? `Level ${featured.level}` : "Program"}
              </p>
              <h3 className="mt-1 rw-serif text-xl">{featured.name}</h3>
              <p className="mt-1 text-xs text-muted-foreground">
                {featured.short_description || featured.description || ""}
              </p>
            </div>
          </Link>
        </section>
      )}
    </div>
  );
}

function formatDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
    });
  } catch {
    return iso;
  }
}
