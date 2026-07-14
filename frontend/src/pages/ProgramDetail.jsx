import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Lock,
  PlayCircle,
  FileText,
  Headphones,
  GraduationCap,
  Loader2,
  Sparkles,
} from "lucide-react";

import CheckoutModal from "@/components/CheckoutModal";
import { programsApi } from "@/services/programs";
import { paymentsApi } from "@/services/payments";
import { manualPaymentsApi } from "@/services/manualPayments";
import { useAuth } from "@/context/AuthContext";
import { TID } from "@/constants/testIds";
import { formatApiError } from "@/lib/api";

const ICONS = {
  video: PlayCircle,
  audio: Headphones,
  pdf: FileText,
  assessment: GraduationCap,
  content: FileText,
};

const TYPE_LABELS = {
  video: "Video",
  audio: "Audio",
  pdf: "PDF",
  assessment: "Assessment",
  content: "Content",
};

export default function ProgramDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const isDummy = !!user?.is_dummy;

  const [status, setStatus] = useState(null);
  const [modules, setModules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [paymentMode, setPaymentMode] = useState("razorpay");
  const [pendingReq, setPendingReq] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const [st, mods] = await Promise.all([
        programsApi.status(id),
        programsApi.modulesByProgram(id).catch(() => ({ modules: [] })),
      ]);
      setStatus(st);
      setModules(mods?.modules || mods?.items || []);
      // Per-program payment mode (falls back to global)
      try {
        const modeRes = await manualPaymentsApi.getMode({ program_id: id });
        setPaymentMode(modeRes?.payment_mode || "razorpay");
      } catch {
        setPaymentMode("razorpay");
      }
      // fetch pending request for this program (if any)
      try {
        const pending = await manualPaymentsApi.myPending();
        const match = (pending?.items || []).find((r) => r.program_id === id);
        setPendingReq(match || null);
      } catch { /* non-blocking */ }
    } catch (e) {
      toast.error(formatApiError(e, "Could not load program"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const handleSubscribe = async (plan) => {
    try {
      await paymentsApi.createSubscription(id, plan);
      toast.success("Subscription activated");
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Could not start subscription"));
    }
  };

  if (loading) {
    return (
      <div className="grid place-items-center py-24 text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }
  if (!status?.program) {
    return (
      <div className="px-5 pt-10 text-center text-muted-foreground">
        Program not found
      </div>
    );
  }
  const program = status.program;
  const hasAccess = !!status.has_access;
  const priceAfter = (program.price || 0) - (program.discount || 0);
  const gstAmount = Math.round((priceAfter * (program.gst_percent || 18)) / 100);
  const total = priceAfter + gstAmount;
  const percentage = Math.round(status.progress?.percentage || 0);
  const banner =
    program.banner_url ||
    program.thumbnail_url ||
    "https://images.unsplash.com/photo-1506126613408-eca07ce68773?auto=format&fit=crop&w=1400&q=60";

  return (
    <div>
      <div className="relative h-56">
        <img src={banner} alt="" className="h-full w-full object-cover" />
        <div
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(180deg, transparent 30%, hsl(var(--rw-royal-deep)) 100%)",
          }}
        />
        <button
          onClick={() => nav(-1)}
          className="absolute left-4 top-4 grid h-10 w-10 place-items-center rounded-full bg-white/90"
          data-testid="detail-back"
        >
          <ChevronLeft className="h-5 w-5 text-[hsl(var(--rw-royal-deep))]" />
        </button>
        <div className="absolute inset-x-0 bottom-0 p-5 text-white">
          <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-white/70">
            {program.is_subscription
              ? "Subscription"
              : program.level
              ? `Level ${program.level}`
              : ""}
          </p>
          <h1 className="mt-1 rw-serif text-3xl">{program.name}</h1>
          <p className="text-sm text-white/80">{program.short_description}</p>
        </div>
      </div>

      <div className="px-5 pb-4 pt-5">
        {/* meta strip */}
        <div className="grid grid-cols-3 gap-2 text-center">
          <Meta k="Validity" v={`${program.validity_days || 0}d`} />
          <Meta k="GST" v={`${program.gst_percent || 18}%`} />
          <Meta
            k="Status"
            v={hasAccess ? "Active" : status.certificate ? "Completed" : "Locked"}
          />
        </div>

        {hasAccess && (
          <div className="mt-4 rounded-2xl bg-[hsl(var(--rw-sky-soft))] p-4">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-[hsl(var(--rw-royal-deep))]">
                Progress
              </span>
              <span className="text-muted-foreground">
                Expires {formatDate(status.active_purchase?.expiry_date)}
              </span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-white">
              <div
                className="h-full bg-[hsl(var(--rw-royal))]"
                style={{ width: `${percentage}%` }}
              />
            </div>
            <div className="mt-1 text-right text-xs font-semibold text-[hsl(var(--rw-royal-deep))]">
              {percentage}%
            </div>
          </div>
        )}

        {/* description */}
        {program.description && (
          <section className="mt-6">
            <h3 className="rw-serif text-xl">About</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              {program.description}
            </p>
          </section>
        )}

        {/* modules */}
        <section className="mt-6 pb-40" data-testid={TID.programModuleList}>
          <h3 className="rw-serif text-xl">Modules</h3>
          {!hasAccess ? (
            <div className="mt-3 grid place-items-center rounded-2xl bg-neutral-50 p-8 text-center">
              <Lock className="h-6 w-6 text-muted-foreground" />
              <p className="mt-2 text-sm text-muted-foreground">
                Purchase this program to unlock modules.
              </p>
            </div>
          ) : modules.length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">
              Modules will unlock once published.
            </p>
          ) : (
            <div className="mt-3 space-y-2">
              {modules.map((m) => {
                const type = m.type || pickType(m);
                const Icon = ICONS[type] || PlayCircle;
                // Backend returns is_unlocked / is_completed. Older seed data
                // may use `unlocked` / `completed` — fall back so both work.
                const locked = !(m.is_unlocked ?? m.unlocked);
                const done = m.is_completed ?? m.completed;
                return (
                  <Link
                    key={m.id}
                    to={
                      locked
                        ? "#"
                        : `/app/programs/${id}/module/${m.id}`
                    }
                    onClick={(e) => {
                      if (locked) {
                        e.preventDefault();
                        toast.error(
                          "This module is locked. Complete the previous one first, or ask an admin to disable sequential unlock.",
                        );
                      }
                    }}
                    className={`flex items-center gap-3 rounded-2xl border p-3 ${
                      locked ? "opacity-60" : ""
                    }`}
                    style={{ borderColor: "hsl(var(--rw-grey-100))" }}
                    data-testid={TID.moduleCard(m.id)}
                  >
                    <div
                      className={`grid h-11 w-11 place-items-center rounded-full ${
                        done
                          ? "bg-[hsl(var(--rw-gold-soft))] text-[hsl(35_60%_38%)]"
                          : locked
                          ? "bg-[hsl(var(--rw-grey-100))] text-[hsl(var(--rw-grey-500))]"
                          : "bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal-deep))]"
                      }`}
                    >
                      {locked ? (
                        <Lock className="h-4 w-4" />
                      ) : done ? (
                        <CheckCircle2 className="h-4 w-4" />
                      ) : (
                        <Icon className="h-4 w-4" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                        Module {m.module_number} · {TYPE_LABELS[type] || "Content"}
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

      {/* sticky purchase / subscribe bar */}
      <div className="sticky bottom-24 z-30 mx-4 mt-4 rw-card p-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <div className="text-[11px] uppercase tracking-widest text-muted-foreground">
              Total
            </div>
            <div className="rw-serif text-2xl text-[hsl(var(--rw-royal-deep))]">
              ₹{total.toLocaleString("en-IN")}
              {program.discount > 0 && (
                <span className="ml-2 text-xs font-medium text-muted-foreground line-through">
                  ₹{program.price.toLocaleString("en-IN")}
                </span>
              )}
            </div>
            <div className="text-[10px] text-muted-foreground">
              ₹{priceAfter.toLocaleString("en-IN")} + ₹
              {gstAmount.toLocaleString("en-IN")} GST
            </div>
          </div>
          {status.certificate ? (
            <span className="rw-chip rw-chip-gold">
              <Sparkles className="h-3 w-3" /> Completed
            </span>
          ) : hasAccess ? (
            <span className="rw-chip rw-chip-sky">
              <CheckCircle2 className="h-3 w-3" /> Active
            </span>
          ) : pendingReq ? (
            <button
              className="rw-btn-pill bg-amber-500 text-white opacity-90 cursor-not-allowed"
              disabled
              data-testid="program-pending-verification-btn"
            >
              <Loader2 className="h-3 w-3 animate-spin" /> Pending Verification
            </button>
          ) : status.eligibility && !status.eligibility.eligible ? (
            <div className="flex flex-col items-end gap-1" data-testid="program-level-locked">
              <span className="rw-chip bg-neutral-100 text-neutral-700">
                <Lock className="h-3 w-3" /> Locked
              </span>
              <p className="max-w-[260px] text-right text-[10px] text-muted-foreground">
                {status.eligibility.reason || "Complete the previous level first."}
              </p>
            </div>
          ) : isDummy ? (
            <button
              className="rw-btn-pill bg-emerald-600 text-white hover:bg-emerald-700"
              onClick={async () => {
                try {
                  const res = await paymentsApi.markPaidDummy(id);
                  toast.success(res.already_active ? "You already have access" : "Marked as paid (Tester mode)");
                  load();
                } catch (e) {
                  toast.error(formatApiError(e, "Mark as paid failed"));
                }
              }}
              data-testid="program-dummy-mark-paid-btn"
            >
              Mark as Paid (Tester)
            </button>
          ) : paymentMode === "both" ? (
            <div className="flex flex-wrap items-end justify-end gap-2">
              <button
                className="rw-btn-pill rw-btn-primary"
                onClick={() => setCheckoutOpen(true)}
                data-testid={TID.programPurchaseBtn}
              >
                Pay online
              </button>
              <button
                className="rw-btn-pill bg-neutral-900 text-white"
                onClick={() => nav(`/app/pay/${id}`)}
                data-testid="program-purchase-qr-btn"
              >
                Pay via QR
              </button>
            </div>
          ) : (
            <button
              className="rw-btn-pill rw-btn-primary"
              onClick={() => {
                if (paymentMode === "manual_qr") {
                  nav(`/app/pay/${id}`);
                } else {
                  setCheckoutOpen(true);
                }
              }}
              data-testid={TID.programPurchaseBtn}
            >
              {paymentMode === "manual_qr" ? "Pay via QR" : "Purchase"}
            </button>
          )}
        </div>
      </div>

      <CheckoutModal
        open={checkoutOpen}
        onOpenChange={setCheckoutOpen}
        programId={id}
        onSuccess={(res) => {
          setCheckoutOpen(false);
          toast.success(`Access unlocked · Invoice ${res.invoice_number}`);
          load();
        }}
      />
    </div>
  );
}

function Meta({ k, v }) {
  return (
    <div className="rw-card p-3">
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
        {k}
      </div>
      <div className="mt-1 rw-serif text-lg">{v}</div>
    </div>
  );
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return "—";
  }
}

function pickType(m) {
  // Pick the module's media type strictly from what the admin actually uploaded.
  // Order matters: video → audio → pdf → assessment → generic content.
  // (Previously fell back to "video" which mislabelled audio/pdf-only modules.)
  if (m.video_url) return "video";
  if (m.audio_url) return "audio";
  if (m.pdf_url) return "pdf";
  if (m.quiz_id) return "assessment";
  return "content";
}
