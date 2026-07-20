import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ChevronLeft, Download, Loader2, Share2, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { TID } from "@/constants/testIds";
import api, { formatApiError } from "@/lib/api";

/**
 * Real Certificate page — reads /api/certificates/me/{id} (backend-issued
 * on final module completion) and renders program name + completion date +
 * membership + cert / verification numbers. No mocks.
 */
export default function Certificate() {
  const nav = useNavigate();
  const { user } = useAuth();
  const { id } = useParams();
  const [cert, setCert] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(`/certificates/me/${id}`);
        setCert(data);
      } catch (e) {
        setError(formatApiError(e, "Could not load certificate"));
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  const downloadPdf = async () => {
    if (!cert) return;
    setDownloading(true);
    try {
      const { data } = await api.get(`/certificates/me/${cert.id}/pdf`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(new Blob([data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `RIYORA-Certificate-${cert.certificate_number || cert.id}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      // Give the browser a beat to start the save dialog before revoking.
      setTimeout(() => URL.revokeObjectURL(url), 4000);
    } catch (e) {
      toast.error(formatApiError(e, "Could not download PDF"));
    } finally {
      setDownloading(false);
    }
  };

  const share = async () => {
    const text = cert
      ? `I just completed ${cert.program_name} on RIYORA Wellness · Cert # ${cert.certificate_number}`
      : "";
    try {
      if (navigator.share) {
        await navigator.share({ title: "My RIYORA Certificate", text });
        return;
      }
      await navigator.clipboard.writeText(text);
      toast.success("Copied to clipboard");
    } catch {
      /* user dismissed native share sheet */
    }
  };

  return (
    <div className="min-h-screen bg-[hsl(var(--rw-off-white))]">
      <div className="rw-phone rw-safe-top px-5 pt-5">
        <button
          onClick={() => nav(-1)}
          className="grid h-9 w-9 place-items-center rounded-full"
          data-testid="cert-back-btn"
        >
          <ChevronLeft className="h-5 w-5 text-[hsl(var(--rw-royal-deep))]" />
        </button>

        {loading && (
          <div className="mt-16 grid place-items-center text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin" />
            <p className="mt-2 text-sm">Loading your certificate…</p>
          </div>
        )}

        {!loading && error && (
          <div className="mt-16 rounded-2xl bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {!loading && cert && (
          <>
            <h1 className="mt-6 rw-serif text-3xl">Your certificate</h1>
            <p className="text-sm text-muted-foreground">
              Congratulations — you&apos;ve completed{" "}
              <span className="font-semibold text-[hsl(var(--rw-royal-deep))]">
                {cert.program_name}
              </span>
              .
            </p>

            <div className="mt-6 rw-card overflow-hidden p-0" data-testid={TID.certificatePreview}>
              <div className="rw-card-royal p-8 text-center">
                <p className="text-[11px] uppercase tracking-[0.3em] text-white/70">
                  Certificate of completion
                </p>
                <p className="mt-6 text-sm text-white/70">This certifies that</p>
                <h2 className="mt-1 rw-serif text-4xl text-white" data-testid="cert-user-name">
                  {cert.user_name || user?.full_name}
                </h2>
                <p className="mt-4 text-sm text-white/70">has successfully completed</p>
                <p className="mt-1 rw-serif text-2xl text-[hsl(var(--rw-gold))]" data-testid="cert-program-name">
                  {cert.program_name}
                </p>
                <p className="mt-6 text-[11px] uppercase tracking-widest text-white/50" data-testid="cert-completion-date">
                  Completed · {formatDate(cert.completion_date || cert.issue_date)}
                </p>
              </div>
              <div
                className="grid grid-cols-2 divide-x p-5 text-center"
                style={{ borderColor: "hsl(var(--rw-grey-100))" }}
              >
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                    Membership
                  </div>
                  <div className="mt-1 rw-serif text-lg" data-testid="cert-membership">
                    {user?.membership_id}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                    Cert No.
                  </div>
                  <div className="mt-1 rw-serif text-lg" data-testid="cert-number">
                    {cert.certificate_number}
                  </div>
                </div>
              </div>
              <div
                className="flex items-center justify-center gap-1.5 border-t px-4 py-3 text-[10px] uppercase tracking-widest text-muted-foreground"
                style={{ borderColor: "hsl(var(--rw-grey-100))" }}
              >
                <ShieldCheck className="h-3 w-3" />
                Verification · {cert.verification_number}
              </div>
            </div>

            <div className="mt-6 grid grid-cols-2 gap-3">
              <button
                onClick={downloadPdf}
                disabled={downloading}
                className="rw-btn-pill rw-btn-ghost disabled:opacity-60"
                data-testid="cert-download-btn"
              >
                {downloading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" /> Preparing…
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4" /> Download PDF
                  </>
                )}
              </button>
              <button
                onClick={share}
                className="rw-btn-pill rw-btn-primary"
                data-testid="cert-share-btn"
              >
                <Share2 className="h-4 w-4" /> Share
              </button>
            </div>

            <p className="mt-4 text-center text-[10px] text-muted-foreground">
              Issued on {formatDate(cert.issue_date)} · RIYORA Wellness
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function formatDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "long",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}
