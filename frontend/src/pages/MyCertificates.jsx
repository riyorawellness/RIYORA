import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Award, ChevronLeft, Loader2 } from "lucide-react";
import api, { formatApiError } from "@/lib/api";

/**
 * My Certificates — grid of the user's issued certificates. Backend auto-
 * issues one on the final module completion of each program.
 */
export default function MyCertificates() {
  const nav = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/certificates/me", {
          params: { page: 1, page_size: 50, sort: "-issue_date" },
        });
        setItems(data.items || []);
      } catch (e) {
        setError(formatApiError(e, "Could not load your certificates"));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="min-h-screen bg-[hsl(var(--rw-off-white))]">
      <div className="rw-phone rw-safe-top px-5 pt-5">
        <button
          onClick={() => nav(-1)}
          className="grid h-9 w-9 place-items-center rounded-full"
          data-testid="my-certs-back-btn"
        >
          <ChevronLeft className="h-5 w-5 text-[hsl(var(--rw-royal-deep))]" />
        </button>

        <div className="mt-6">
          <p className="rw-eyebrow">Achievements</p>
          <h1 className="mt-1 rw-serif text-3xl">My Certificates</h1>
          <p className="text-sm text-muted-foreground">
            Certificates are automatically issued when you complete every module of a program.
          </p>
        </div>

        {loading && (
          <div className="mt-16 grid place-items-center text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin" />
            <p className="mt-2 text-sm">Loading…</p>
          </div>
        )}

        {!loading && error && (
          <div className="mt-8 rounded-2xl bg-red-50 p-4 text-sm text-red-700">{error}</div>
        )}

        {!loading && !error && items.length === 0 && (
          <div
            className="mt-8 rw-card p-8 text-center"
            data-testid="my-certs-empty"
          >
            <Award className="mx-auto h-8 w-8 text-[hsl(var(--rw-gold))]" />
            <h3 className="mt-3 rw-serif text-xl">No certificates yet</h3>
            <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
              Complete every module of a program and your certificate will show up here.
            </p>
            <Link
              to="/app/programs"
              className="mt-4 inline-flex rw-btn-pill rw-btn-primary"
            >
              Browse programs
            </Link>
          </div>
        )}

        {!loading && items.length > 0 && (
          <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid="my-certs-grid">
            {items.map((c) => (
              <Link
                key={c.id}
                to={`/app/certificate/${c.id}`}
                className="block rw-card overflow-hidden p-0"
                data-testid={`my-cert-row-${c.id}`}
              >
                <div className="rw-card-royal p-5">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.28em] text-white/70">
                        Certificate
                      </p>
                      <h3 className="mt-2 rw-serif text-xl text-white line-clamp-2">
                        {c.program_name}
                      </h3>
                    </div>
                    <Award className="h-6 w-6 text-[hsl(var(--rw-gold))]" />
                  </div>
                  <p className="mt-4 text-[11px] uppercase tracking-widest text-white/60">
                    {c.certificate_number}
                  </p>
                </div>
                <div className="grid grid-cols-2 divide-x p-3 text-center text-[11px]">
                  <div>
                    <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                      Completed
                    </div>
                    <div className="mt-0.5 font-semibold text-[hsl(var(--rw-royal-deep))]">
                      {formatDate(c.completion_date || c.issue_date)}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                      Issued
                    </div>
                    <div className="mt-0.5 font-semibold text-[hsl(var(--rw-royal-deep))]">
                      {formatDate(c.issue_date)}
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
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
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}
