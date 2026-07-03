import { useNavigate, useParams } from "react-router-dom";
import { ChevronLeft, Download, Share2 } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { PROGRAMS } from "@/mock/data";
import { TID } from "@/constants/testIds";

export default function Certificate() {
  const nav = useNavigate();
  const { user } = useAuth();
  const { id } = useParams();
  const program = PROGRAMS.find((p) => p.id === id) || PROGRAMS[0];

  return (
    <div className="min-h-screen bg-[hsl(var(--rw-off-white))]">
      <div className="rw-phone rw-safe-top px-5 pt-5">
        <button onClick={() => nav(-1)} className="grid h-9 w-9 place-items-center rounded-full">
          <ChevronLeft className="h-5 w-5 text-[hsl(var(--rw-royal-deep))]" />
        </button>

        <h1 className="mt-6 rw-serif text-3xl">Your certificate</h1>
        <p className="text-sm text-muted-foreground">Congratulations — you&apos;ve completed {program.name}.</p>

        <div className="mt-6 rw-card overflow-hidden p-0" data-testid={TID.certificatePreview}>
          <div className="rw-card-royal p-8 text-center">
            <p className="text-[11px] uppercase tracking-[0.3em] text-white/70">Certificate of completion</p>
            <p className="mt-6 text-sm text-white/70">This certifies that</p>
            <h2 className="mt-1 rw-serif text-4xl text-white">{user?.full_name}</h2>
            <p className="mt-4 text-sm text-white/70">has completed the program</p>
            <p className="mt-1 rw-serif text-2xl text-[hsl(var(--rw-gold))]">{program.name}</p>
            <p className="mt-6 text-[11px] uppercase tracking-widest text-white/50">
              Issued · 3 July 2026
            </p>
          </div>
          <div className="grid grid-cols-2 divide-x p-5 text-center" style={{ borderColor: "hsl(var(--rw-grey-100))" }}>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Membership</div>
              <div className="mt-1 rw-serif text-lg">{user?.membership_id}</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Cert No.</div>
              <div className="mt-1 rw-serif text-lg">RW-{program.id.toUpperCase()}</div>
            </div>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-3">
          <button
            onClick={() => toast.info("PDF download unlocks in the next phase")}
            className="rw-btn-pill rw-btn-ghost"
          >
            <Download className="h-4 w-4" /> Download
          </button>
          <button
            onClick={() => toast.success("Sharing coming soon")}
            className="rw-btn-pill rw-btn-primary"
          >
            <Share2 className="h-4 w-4" /> Share
          </button>
        </div>
      </div>
    </div>
  );
}
