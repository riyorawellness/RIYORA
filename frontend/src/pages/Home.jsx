import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { Bell, Calendar, Droplet, Play, Sparkles, PlusCircle } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import Logo from "@/components/Logo";
import { TID } from "@/constants/testIds";
import { activityApi } from "@/services/referrals";
import { formatApiError } from "@/lib/api";
import {
  ANNOUNCEMENT,
  DAILY_QUOTE,
  PROGRAMS,
  UPCOMING_LIVE,
  WATER_REMINDER,
} from "@/mock/data";

const STATUS_COLOR = {
  green: "hsl(141 60% 42%)",
  yellow: "hsl(42 78% 55%)",
  red: "hsl(356 78% 55%)",
  no_subscription: "hsl(220 10% 60%)",
};
const STATUS_LABEL = {
  green: "Active",
  yellow: "Grace",
  red: "Inactive",
  no_subscription: "No subscription",
};

export default function Home() {
  const { user } = useAuth();
  const first = user?.full_name?.split(" ")[0] ?? "Seeker";
  const [meter, setMeter] = useState(null);
  const [logging, setLogging] = useState(false);
  const innerPeace = PROGRAMS.find((p) => p.id === "inner-peace");
  const featured = PROGRAMS.find((p) => p.id === "level-1");

  const loadMeter = async () => {
    try {
      const m = await activityApi.meter();
      setMeter(m);
    } catch (e) {
      // silent
    }
  };

  useEffect(() => {
    loadMeter();
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
        <Link to="/app/notifications" className="grid h-10 w-10 place-items-center rounded-full bg-[hsl(var(--rw-grey-50))]">
          <Bell className="h-4 w-4 text-[hsl(var(--rw-royal-deep))]" />
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
                : "No active Inner Peace subscription"}
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
        {meter && meter.status !== "no_subscription" && (
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

      {/* Inner Peace card */}
      <Link to={`/app/programs/${innerPeace.id}`} className="mt-5 block rw-card overflow-hidden p-0" data-testid={TID.homeInnerPeaceCard}>
        <div className="relative">
          <img src={innerPeace.thumbnail} alt="" className="h-40 w-full object-cover" />
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
          <div className="absolute inset-x-0 bottom-0 p-4 text-white">
            <span className="rw-chip rw-chip-gold">Subscription</span>
            <h3 className="mt-1 rw-serif text-2xl">Inner Peace</h3>
            <p className="text-xs text-white/80">{innerPeace.tagline}</p>
          </div>
          <div className="absolute right-4 top-4 grid h-11 w-11 place-items-center rounded-full bg-white/95 text-[hsl(var(--rw-royal))] shadow-lg">
            <Play className="h-5 w-5 fill-current" />
          </div>
        </div>
        <div className="flex items-center justify-between p-4">
          <div className="text-sm">
            <div className="font-semibold text-foreground">Continue learning</div>
            <div className="text-xs text-muted-foreground">Module 3 · Companion Notes</div>
          </div>
          <div className="text-right">
            <div className="text-[11px] uppercase tracking-widest text-muted-foreground">Progress</div>
            <div className="text-lg font-semibold text-[hsl(var(--rw-royal))]">{innerPeace.progress}%</div>
          </div>
        </div>
      </Link>

      {/* quote + water */}
      <div className="mt-5 grid grid-cols-2 gap-3">
        <div className="rw-card p-4" data-testid={TID.homeDailyQuote}>
          <p className="rw-eyebrow">Daily quote</p>
          <p className="mt-2 rw-serif text-base leading-snug">“{DAILY_QUOTE.quote}”</p>
          <p className="mt-2 text-[11px] text-muted-foreground">{DAILY_QUOTE.author}</p>
        </div>
        <div className="rw-card p-4" data-testid={TID.homeWaterReminder}>
          <p className="rw-eyebrow">Water reminder</p>
          <div className="mt-3 flex items-center gap-1">
            {Array.from({ length: WATER_REMINDER.glasses_target }).map((_, i) => (
              <Droplet
                key={i}
                className={`h-4 w-4 ${
                  i < WATER_REMINDER.glasses_done
                    ? "fill-[hsl(var(--rw-sky))] text-[hsl(var(--rw-sky))]"
                    : "text-[hsl(var(--rw-grey-200))]"
                }`}
              />
            ))}
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">{WATER_REMINDER.glasses_done} / {WATER_REMINDER.glasses_target} glasses</p>
        </div>
      </div>

      {/* upcoming live */}
      <section className="mt-5 rw-card overflow-hidden p-0" data-testid={TID.homeUpcomingLive}>
        <img src={UPCOMING_LIVE.cover} alt="" className="h-32 w-full object-cover" />
        <div className="p-4">
          <div className="flex items-center gap-2">
            <span className="rw-chip rw-chip-sky"><Calendar className="h-3 w-3" /> Upcoming live</span>
          </div>
          <h3 className="mt-2 rw-serif text-xl">{UPCOMING_LIVE.title}</h3>
          <p className="text-xs text-muted-foreground">{UPCOMING_LIVE.starts_at} · {UPCOMING_LIVE.host}</p>
        </div>
      </section>

      {/* announcement */}
      <section className="mt-5 flex items-start gap-3 rw-card p-4" data-testid={TID.homeAnnouncement}>
        <div className="grid h-10 w-10 place-items-center rounded-full bg-[hsl(var(--rw-gold-soft))] text-[hsl(35_60%_38%)]">
          <Sparkles className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="rw-eyebrow">Announcement</p>
          <p className="mt-1 text-sm font-semibold">{ANNOUNCEMENT.title}</p>
          <p className="text-xs text-muted-foreground">{ANNOUNCEMENT.body}</p>
        </div>
        <span className="whitespace-nowrap text-[10px] text-muted-foreground">{ANNOUNCEMENT.when}</span>
      </section>

      {/* featured */}
      <section className="mt-5" data-testid={TID.homeFeaturedProgram}>
        <div className="mb-2 flex items-baseline justify-between">
          <h2 className="rw-serif text-2xl">Featured program</h2>
          <Link to="/app/programs" className="text-xs font-semibold text-[hsl(var(--rw-royal))]">See all</Link>
        </div>
        <Link to={`/app/programs/${featured.id}`} className="block rw-card overflow-hidden p-0">
          <img src={featured.thumbnail} alt="" className="h-36 w-full object-cover" />
          <div className="p-4">
            <p className="rw-eyebrow">Level {featured.level}</p>
            <h3 className="mt-1 rw-serif text-xl">{featured.name}</h3>
            <p className="mt-1 text-xs text-muted-foreground">{featured.tagline}</p>
          </div>
        </Link>
      </section>
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
