import { Link } from "react-router-dom";
import { Lock, Check } from "lucide-react";
import { TID } from "@/constants/testIds";

export default function ProgramCard({ program }) {
  const priceAfter = program.price - (program.discount || 0);
  return (
    <Link
      to={`/app/programs/${program.id}`}
      className="rw-card block overflow-hidden p-0"
      data-testid={TID.programCard(program.id)}
    >
      <div className="relative aspect-[16/9] w-full overflow-hidden">
        <img
          src={program.thumbnail}
          alt={program.name}
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
        />
        <div className="absolute left-3 top-3 flex gap-2">
          {program.purchased ? (
            <span className="rw-chip rw-chip-gold">
              <Check className="h-3 w-3" /> Purchased
            </span>
          ) : program.locked ? (
            <span className="rw-chip rw-chip-grey">
              <Lock className="h-3 w-3" /> Locked
            </span>
          ) : (
            <span className="rw-chip rw-chip-sky">Available</span>
          )}
        </div>
      </div>

      <div className="p-4">
        <p className="rw-eyebrow">
          {program.level === 0 ? "Recurring" : `Level ${program.level}`}
        </p>
        <h3 className="mt-1 rw-serif text-xl text-foreground">{program.name}</h3>
        <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{program.tagline}</p>

        <div className="mt-3 flex items-end justify-between">
          <div>
            <div className="text-lg font-semibold text-[hsl(var(--rw-royal-deep))]">
              ₹{priceAfter.toLocaleString("en-IN")}
              {program.discount > 0 && (
                <span className="ml-2 text-xs font-medium text-muted-foreground line-through">
                  ₹{program.price.toLocaleString("en-IN")}
                </span>
              )}
            </div>
            <div className="text-[11px] text-muted-foreground">
              Valid {program.validity_days} days · +GST
            </div>
          </div>
          {program.purchased && program.progress > 0 && (
            <div className="text-right">
              <div className="text-[11px] uppercase tracking-widest text-muted-foreground">
                Progress
              </div>
              <div className="text-lg font-semibold text-[hsl(var(--rw-royal))]">
                {program.progress}%
              </div>
            </div>
          )}
        </div>
      </div>
    </Link>
  );
}
