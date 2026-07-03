import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ChevronLeft, FastForward, Rewind, Pause, Play, Volume2 } from "lucide-react";
import { MODULES_BY_PROGRAM, PROGRAMS } from "@/mock/data";
import { useAuth } from "@/context/AuthContext";
import { TID } from "@/constants/testIds";

/**
 * A unified mock player for video / audio / pdf. Streaming UI only — no download.
 * A watermark shows the user's full name + membership id on all content types
 * as per the anti-piracy requirement.
 */
export default function ModulePlayer() {
  const { id, moduleId } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const program = PROGRAMS.find((p) => p.id === id);
  const module = (MODULES_BY_PROGRAM[id] || []).find((m) => m.id === moduleId);
  const [playing, setPlaying] = useState(false);

  if (!module || !program) {
    return <div className="px-5 pt-10 text-center text-muted-foreground">Module not found</div>;
  }

  if (module.type === "assessment") {
    // Route to quiz
    nav(`/app/programs/${id}/assessment/${moduleId}`, { replace: true });
    return null;
  }

  const isVideo = module.type === "video";
  const isPDF = module.type === "pdf";
  const watermark = `${user?.full_name} · ${user?.membership_id}`;

  return (
    <div className="min-h-screen bg-white">
      {isPDF ? (
        <PDFView title={module.name} program={program} module={module} watermark={watermark} nav={nav} />
      ) : (
        <div className="rw-player-bg text-white">
          <div className="flex items-center justify-between px-5 pt-6">
            <button
              onClick={() => nav(-1)}
              className="grid h-10 w-10 place-items-center rounded-full bg-white/15"
              data-testid={TID.playerBack}
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
            <div className="text-xs text-white/70">
              {isVideo ? "Streaming · No download" : "Meditation audio"}
            </div>
            <div className="h-10 w-10" />
          </div>

          {/* Poster / album art */}
          <div className="mx-5 mt-4 aspect-[4/5] overflow-hidden rounded-3xl relative">
            <img src={program.banner} alt="" className="h-full w-full object-cover" />
            <div className="absolute inset-0 bg-black/30" />
            {/* watermark */}
            <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-4 text-[10px] font-medium text-white/45">
              <span>{watermark}</span>
              <span className="self-end">{watermark}</span>
            </div>
            {/* play overlay */}
            <button
              onClick={() => setPlaying((p) => !p)}
              className="absolute inset-0 grid place-items-center"
              data-testid={TID.playerPlay}
            >
              <span className="grid h-20 w-20 place-items-center rounded-full bg-white/90 text-[hsl(var(--rw-royal))] shadow-2xl">
                {playing ? <Pause className="h-8 w-8 fill-current" /> : <Play className="h-8 w-8 fill-current translate-x-0.5" />}
              </span>
            </button>
          </div>

          <div className="px-5 pb-8 pt-6">
            <p className="text-[11px] uppercase tracking-[0.3em] text-white/60">
              Module {module.module_number} · {program.name}
            </p>
            <h1 className="mt-1 rw-serif text-3xl">{module.name}</h1>

            {/* progress bar (mock) */}
            <div className="mt-6">
              <div className="relative h-1.5 rounded-full bg-white/20">
                <div className="absolute inset-y-0 left-0 rounded-full bg-[hsl(var(--rw-gold))]" style={{ width: playing ? "48%" : "22%" }} />
              </div>
              <div className="mt-2 flex justify-between text-[10px] text-white/60">
                <span>{playing ? "10:15" : "04:38"}</span>
                <span>{module.duration_min ? `${module.duration_min}:00` : "22:00"}</span>
              </div>
            </div>

            {/* controls */}
            <div className="mt-6 flex items-center justify-center gap-6">
              <button className="grid h-12 w-12 place-items-center rounded-full bg-white/10">
                <Rewind className="h-5 w-5" />
              </button>
              <button
                onClick={() => setPlaying((p) => !p)}
                className="grid h-16 w-16 place-items-center rounded-full bg-white text-[hsl(var(--rw-royal))] shadow-xl"
              >
                {playing ? <Pause className="h-6 w-6 fill-current" /> : <Play className="h-6 w-6 fill-current translate-x-0.5" />}
              </button>
              <button className="grid h-12 w-12 place-items-center rounded-full bg-white/10">
                <FastForward className="h-5 w-5" />
              </button>
            </div>
            <div className="mt-6 flex items-center justify-center gap-2 text-[11px] text-white/60">
              <Volume2 className="h-3 w-3" /> Stream quality auto · Downloads disabled
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PDFView({ title, program, module, watermark, nav }) {
  return (
    <div className="min-h-screen bg-[hsl(var(--rw-off-white))] pb-8">
      <div className="flex items-center gap-3 border-b bg-white px-5 py-3" style={{ borderColor: "hsl(var(--rw-grey-100))" }}>
        <button onClick={() => nav(-1)} className="grid h-9 w-9 place-items-center rounded-full hover:bg-[hsl(var(--rw-grey-50))]" data-testid={TID.playerBack}>
          <ChevronLeft className="h-5 w-5 text-[hsl(var(--rw-royal-deep))]" />
        </button>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] uppercase tracking-widest text-muted-foreground">PDF · {module.pages} pages</p>
          <h1 className="truncate rw-serif text-xl">{title}</h1>
        </div>
        <span className="rw-chip rw-chip-grey">View only</span>
      </div>

      <div className="mx-5 mt-4 relative rw-card overflow-hidden">
        {/* fake page */}
        <div className="relative p-8 leading-relaxed">
          <div className="pointer-events-none absolute inset-0 grid place-items-center opacity-[0.06] rotate-[-24deg]">
            <span className="rw-serif text-4xl">{watermark}</span>
          </div>
          <p className="rw-eyebrow">Chapter 1</p>
          <h2 className="mt-2 rw-serif text-3xl">{module.name}</h2>
          <p className="mt-4 text-sm text-muted-foreground">
            (Companion Notes preview) Peace is not the absence of sound. It is the
            practiced return to the still centre inside the noise.
          </p>
          <p className="mt-3 text-sm text-muted-foreground">
            Each morning, sit for one long breath. Feel the exhale reach further
            than the inhale. Notice the pause. That pause is your first teacher.
          </p>
          <p className="mt-3 text-sm text-muted-foreground">
            The workbook that follows is a set of small experiments — 4 minute
            practices, one for each week. Do not chase results. Show up daily,
            and let the practice arrive on its own schedule.
          </p>
          <div className="mt-8 flex items-center justify-between text-[10px] text-muted-foreground">
            <span>{watermark}</span>
            <span>Page 1 / {module.pages}</span>
          </div>
        </div>
      </div>

      <p className="mt-4 text-center text-[11px] text-muted-foreground">
        Screenshots &amp; downloads disabled for content security.
      </p>
    </div>
  );
}
