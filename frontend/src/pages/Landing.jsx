import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import Logo from "@/components/Logo";
import { TID } from "@/constants/testIds";
import {
  ArrowRight,
  HeartPulse,
  BookOpen,
  Coins,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

const pillars = [
  {
    icon: HeartPulse,
    title: "Heal",
    body: "Guided meditation, breath-work and inner-peace practices led by senior mentors.",
  },
  {
    icon: BookOpen,
    title: "Learn",
    body: "Structured levels — from Chitta Shuddhi to Param Siddhi — with modular videos, audios & workbooks.",
  },
  {
    icon: Coins,
    title: "Earn",
    body: "Refer authentic seekers, stay active, and earn a mindful residual through your circle.",
  },
];

export default function Landing() {
  return (
    <div className="min-h-screen rw-hero-radial rw-grain">
      {/* nav */}
      <nav className="rw-container flex items-center justify-between py-6">
        <Logo size="md" />
        <div className="flex items-center gap-3">
          <Link to="/login">
            <Button variant="ghost" data-testid={TID.landingCtaLogin} className="rounded-full">
              Log in
            </Button>
          </Link>
          <Link to="/register">
            <Button data-testid={TID.landingCtaGetStarted} className="rounded-full">
              Begin the journey <ArrowRight className="ml-1 h-4 w-4" />
            </Button>
          </Link>
        </div>
      </nav>

      {/* hero */}
      <section className="rw-container pb-20 pt-10 md:pt-20" data-testid={TID.landingHero}>
        <div className="grid grid-cols-1 items-center gap-14 md:grid-cols-12">
          <div className="md:col-span-7 rw-rise">
            <p className="rw-eyebrow">est. in stillness</p>
            <h1 className="mt-3 rw-serif text-5xl leading-[1.05] text-foreground sm:text-6xl lg:text-7xl">
              A quieter path to <em className="not-italic text-primary">wholeness.</em>
            </h1>
            <p className="mt-6 max-w-xl text-base text-muted-foreground sm:text-lg">
              RIYORA WELLNESS is a members-only sanctuary of guided programs, live sessions
              and a referral circle designed for those who want to <span className="text-foreground">heal</span>,{" "}
              <span className="text-foreground">learn</span> and{" "}
              <span className="text-foreground">earn</span> in harmony.
            </p>

            <div className="mt-9 flex flex-wrap items-center gap-4">
              <Link to="/register">
                <Button size="lg" className="rounded-full px-7">
                  Join with a Referral ID
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
              <Link to="/login" className="text-sm font-medium text-foreground/80 hover:text-primary transition">
                Already a member? Sign in →
              </Link>
            </div>

            <div className="mt-10 flex flex-wrap items-center gap-6 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-primary" /> Mobile OTP secured
              </span>
              <span className="inline-flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" /> Invitation-only membership
              </span>
            </div>
          </div>

          <div className="md:col-span-5">
            <div className="relative mx-auto max-w-md rw-rise">
              <div className="absolute -inset-6 -z-10 rounded-[3rem] bg-primary/10 blur-3xl" />
              <div className="rw-card overflow-hidden p-0">
                <div className="aspect-[4/5] w-full bg-[url('https://images.unsplash.com/photo-1508672019048-805c876b67e2?auto=format&fit=crop&w=1000&q=70')] bg-cover bg-center" />
                <div className="border-t border-border/60 bg-card/80 p-5 backdrop-blur">
                  <p className="rw-eyebrow">Today · Live at 6:30 AM</p>
                  <p className="mt-1 rw-serif text-2xl text-foreground">
                    Inner Peace — Session 04
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Breath as the return to the centre.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* pillars */}
        <div className="mt-24">
          <div className="rw-divider" />
          <div className="mt-16 grid gap-6 md:grid-cols-3">
            {pillars.map(({ icon: Icon, title, body }) => (
              <Card key={title} className="rw-card">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="mt-5 rw-serif text-3xl text-foreground">{title}.</h3>
                <p className="mt-2 text-sm text-muted-foreground">{body}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* footer */}
      <footer className="rw-container border-t border-border/60 py-8 text-xs text-muted-foreground">
        <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
          <span>© {new Date().getFullYear()} RIYORA WELLNESS. Heal. Learn. Earn.</span>
          <Link to="/admin/login" className="hover:text-primary transition" data-testid="admin-portal-link">
            Admin portal
          </Link>
        </div>
      </footer>
    </div>
  );
}
