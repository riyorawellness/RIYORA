import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { CheckCircle2, ChevronLeft, ChevronRight, Lock, PlayCircle, FileText, Headphones, GraduationCap } from "lucide-react";
import { MODULES_BY_PROGRAM, PROGRAMS } from "@/mock/data";
import { TID } from "@/constants/testIds";

const ICONS = { video: PlayCircle, audio: Headphones, pdf: FileText, assessment: GraduationCap };

export default function ProgramDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const program = PROGRAMS.find((p) => p.id === id);
  const modules = MODULES_BY_PROGRAM[id] || [];

  if (!program) {
    return <div className="px-5 pt-10 text-center text-muted-foreground">Program not found</div>;
  }

  const priceAfter = program.price - (program.discount || 0);
  const gstAmount = Math.round((priceAfter * program.gst_percent) / 100);
  const total = priceAfter + gstAmount;

  return (
    <div>
      <div className="relative h-56">
        <img src={program.banner} alt="" className="h-full w-full object-cover" />
        <div className="absolute inset-0" style={{ background: "linear-gradient(180deg, transparent 30%, hsl(var(--rw-royal-deep)) 100%)" }} />
        <button
          onClick={() => nav(-1)}
          className="absolute left-4 top-4 grid h-10 w-10 place-items-center rounded-full bg-white/90"
          data-testid="detail-back"
        >
          <ChevronLeft className="h-5 w-5 text-[hsl(var(--rw-royal-deep))]" />
        </button>
        <div className="absolute inset-x-0 bottom-0 p-5 text-white">
          <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-white/70">
            {program.level === 0 ? "Recurring" : `Level ${program.level}`}
          </p>
          <h1 className="mt-1 rw-serif text-3xl">{program.name}</h1>
          <p className="text-sm text-white/80">{program.tagline}</p>
        </div>
      </div>

      <div className="px-5 pb-4 pt-5">
        {/* meta strip */}
        <div className="grid grid-cols-3 gap-2 text-center">
          <Meta k="Duration" v={program.duration} />
          <Meta k="Validity" v={`${program.validity_days}d`} />
          <Meta k="GST" v={`${program.gst_percent}%`} />
        </div>

        {/* description */}
        <section className="mt-6">
          <h3 className="rw-serif text-xl">About</h3>
          <p className="mt-2 text-sm text-muted-foreground">{program.description}</p>
        </section>

        {/* benefits */}
        <section className="mt-6">
          <h3 className="rw-serif text-xl">What&apos;s included</h3>
          <ul className="mt-3 space-y-2">
            {program.benefits.map((b) => (
              <li key={b} className="flex items-start gap-2 text-sm">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--rw-royal))]" /> {b}
              </li>
            ))}
          </ul>
        </section>

        {/* modules */}
        <section className="mt-6" data-testid={TID.programModuleList}>
          <h3 className="rw-serif text-xl">Modules</h3>
          {modules.length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">Modules will unlock once the program is live.</p>
          ) : (
            <div className="mt-3 space-y-2">
              {modules.map((m) => {
                const Icon = ICONS[m.type] || PlayCircle;
                const locked = m.status === "locked";
                const done = m.status === "completed";
                return (
                  <Link
                    key={m.id}
                    to={locked ? "#" : `/app/programs/${id}/module/${m.id}`}
                    onClick={(e) => {
                      if (locked) {
                        e.preventDefault();
                        toast.error("Complete the previous module to unlock");
                      }
                    }}
                    className={`flex items-center gap-3 rounded-2xl border p-3 ${locked ? "opacity-60" : ""}`}
                    style={{ borderColor: "hsl(var(--rw-grey-100))" }}
                    data-testid={TID.moduleCard(m.id)}
                  >
                    <div className={`grid h-11 w-11 place-items-center rounded-full ${
                      done ? "bg-[hsl(var(--rw-gold-soft))] text-[hsl(35_60%_38%)]"
                        : locked ? "bg-[hsl(var(--rw-grey-100))] text-[hsl(var(--rw-grey-500))]"
                        : "bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal-deep))]"
                    }`}>
                      {locked ? <Lock className="h-4 w-4" /> : done ? <CheckCircle2 className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                        Module {m.module_number} · {m.type}
                      </div>
                      <div className="truncate font-semibold">{m.name}</div>
                    </div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </Link>
                );
              })}
            </div>
          )}
        </section>
      </div>

      {/* sticky purchase bar */}
      <div className="sticky bottom-24 z-30 mx-4 mt-4 rw-card p-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <div className="text-[11px] uppercase tracking-widest text-muted-foreground">Total</div>
            <div className="rw-serif text-2xl text-[hsl(var(--rw-royal-deep))]">
              ₹{total.toLocaleString("en-IN")}
              {program.discount > 0 && (
                <span className="ml-2 text-xs font-medium text-muted-foreground line-through">
                  ₹{program.price.toLocaleString("en-IN")}
                </span>
              )}
            </div>
            <div className="text-[10px] text-muted-foreground">
              ₹{priceAfter.toLocaleString("en-IN")} + ₹{gstAmount.toLocaleString("en-IN")} GST
            </div>
          </div>
          {program.purchased ? (
            <span className="rw-chip rw-chip-gold">Already purchased</span>
          ) : program.locked ? (
            <button className="rw-btn-pill bg-[hsl(var(--rw-grey-100))] text-muted-foreground" disabled>
              <Lock className="h-4 w-4" /> Locked
            </button>
          ) : (
            <button
              className="rw-btn-pill rw-btn-primary"
              onClick={() => toast.success("Purchase coming in the payments phase")}
              data-testid={TID.programPurchaseBtn}
            >
              Purchase
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Meta({ k, v }) {
  return (
    <div className="rw-card p-3">
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">{k}</div>
      <div className="mt-1 rw-serif text-lg">{v}</div>
    </div>
  );
}
