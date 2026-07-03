import { PROGRAMS } from "@/mock/data";
import ProgramCard from "@/components/ProgramCard";
import { TID } from "@/constants/testIds";

export default function Programs() {
  return (
    <div className="px-5 pt-6">
      <p className="rw-eyebrow">Curriculum</p>
      <h1 className="mt-1 rw-serif text-4xl">Programs</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Sequential path — one level at a time.
      </p>

      <div className="mt-6 grid gap-4" data-testid={TID.programsList}>
        {PROGRAMS.map((p) => (
          <ProgramCard key={p.id} program={p} />
        ))}
      </div>
    </div>
  );
}
