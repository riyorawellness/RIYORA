import { useEffect, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";

import ProgramCard from "@/components/ProgramCard";
import ActiveBanners from "@/components/ActiveBanners";
import { programsApi } from "@/services/programs";
import { TID } from "@/constants/testIds";
import { formatApiError } from "@/lib/api";

const BUCKETS = [
  { key: "purchased", label: "In progress", tint: "sky" },
  { key: "available", label: "Available for you", tint: "sky" },
  { key: "locked", label: "Locked", tint: "grey" },
  { key: "completed", label: "Completed", tint: "gold" },
  { key: "expired", label: "Expired · Repurchase", tint: "grey" },
];

export default function Programs() {
  const [buckets, setBuckets] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const data = await programsApi.dashboard();
        setBuckets(data);
      } catch (e) {
        toast.error(formatApiError(e, "Could not load programs"));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div className="grid place-items-center py-24 text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  const anyProgram =
    buckets &&
    BUCKETS.some((b) => (buckets[b.key] || []).length > 0);

  return (
    <div className="px-5 pt-6 pb-24">
      <p className="rw-eyebrow">Curriculum</p>
      <h1 className="mt-1 rw-serif text-4xl">Programs</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Complete each level to unlock the next. Inner Peace stays alive with an
        activity meter.
      </p>

      <ActiveBanners placement="programs" className="mt-5" />

      {!anyProgram && (
        <div className="mt-8 grid place-items-center rounded-2xl bg-neutral-50 py-14">
          <Sparkles className="h-6 w-6 text-[hsl(var(--rw-gold))]" />
          <p className="mt-2 rw-serif text-lg">No programs yet</p>
          <p className="text-xs text-muted-foreground">
            The admin will publish programs shortly.
          </p>
        </div>
      )}

      {BUCKETS.map((b) => {
        const items = buckets?.[b.key] || [];
        if (!items.length) return null;
        return (
          <section key={b.key} className="mt-8">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="rw-serif text-2xl">{b.label}</h2>
              <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
                {items.length}
              </span>
            </div>
            <div className="grid gap-4" data-testid={`${TID.programsList}-${b.key}`}>
              {items.map((entry) => (
                <ProgramCard
                  key={entry.program.id}
                  program={toCardShape(entry, b.key)}
                />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function toCardShape(entry, bucket) {
  const p = entry.program;
  return {
    id: p.id,
    name: p.name,
    tagline: p.short_description || "",
    thumbnail:
      p.thumbnail_url ||
      "https://images.unsplash.com/photo-1518241353330-0f7941c2d9b5?auto=format&fit=crop&w=800&q=60",
    price: p.price,
    discount: p.discount,
    gst_percent: p.gst_percent,
    validity_days: p.validity_days,
    is_subscription: p.is_subscription,
    level: p.level,
    purchased: bucket === "purchased" || bucket === "completed",
    locked: bucket === "locked",
    progress: Math.round(entry.progress?.percentage || 0),
  };
}
